"""``ReportExecutionService`` — the one path every report execution goes
through (plan.md §9, spec §21). ``_authorize_and_validate()`` is a shared
preamble ``execute()`` and (Phase 6) ``ReportExportService.export()`` both
call, so the two paths can never silently diverge.

This is the **one and only** place ``InstallmentsServicingContinuityGate``
(Phase 2, T110/T111) is wired into a live request path — Phase 2's
``InstallmentsAdapter`` deliberately contains zero entitlement logic
(verified there by an AST-scan); the Case A/B decision lives here,
one layer up, exactly as designed.

Importing ``modules.reports.registry.load_all`` here (not from
``registry/__init__.py`` itself, which would recreate the circular
import Gate 2 discovered and fixed) guarantees ``REPORT_REGISTRY``/
``ADAPTER_REGISTRY`` are fully populated the moment anything imports this
service — the real app's only consumer of a populated registry at
request time.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal
from urllib.parse import urlencode
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

import modules.reports.registry.load_all  # noqa: F401 — see comment below
from modules.accounting.dependencies import (
    build_allocation_engine,
    build_ar_service,
    build_payment_service,
)
from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.late_charge import (
    InstallmentLateChargeRepository,
)
from modules.installments.repositories.plan_template import (
    InstallmentPlanTemplateRepository,
)
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.services.accounting_gateway import (
    AccountingIntegrationGateway,
)
from modules.installments.services.reporting_service import InstallmentReportingService
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.services.entitlement_service import (
    PlatformEntitlementService,
)
from modules.reports.exceptions import (
    FilterValidationError,
    ReportNotEntitledError,
    ReportNotFoundError,
    ReportPermissionDeniedError,
    UnsupportedSortFieldError,
)
from modules.reports.registry.definitions import (
    REPORT_REGISTRY,
    ReportDefinition,
    ReportExecutionKind,
    ReportStatus,
)
from modules.reports.schemas.common import ComparisonRequest, DrillDownRef
from modules.reports.services.adapters.base import ADAPTER_REGISTRY, BaseReportResult
from modules.reports.services.installments_continuity_gate import (
    InstallmentsAccessState,
    InstallmentsServicingContinuityGate,
)
from modules.reports.services.permission_check import user_has_reports_permission

_INSTALLMENTS_DOMAIN_KEY = "installments"


def _build_installments_reporting_service(db: Session) -> InstallmentReportingService:
    """Mirrors ``installments_adapter.py``'s own private builder — kept as
    a separate, small, local copy rather than a cross-file import so the
    execution service and the (entitlement-free) adapter never share
    construction code that could couple their responsibilities."""
    gateway = AccountingIntegrationGateway(
        ar_service=build_ar_service(db),
        payment_service=build_payment_service(db),
        allocation_engine=build_allocation_engine(db),
    )
    return InstallmentReportingService(
        contract_repo=InstallmentContractRepository(db),
        schedule_repo=InstallmentScheduleRepository(db),
        allocation_ref_repo=InstallmentAllocationReferenceRepository(db),
        late_charge_repo=InstallmentLateChargeRepository(db),
        audit_repo=InstallmentAuditLogRepository(db),
        plan_template_repo=InstallmentPlanTemplateRepository(db),
        accounting_gateway=gateway,
        access_policy=None,
    )


def _build_drill_down_route(
    target_route: str,
    preserves_filters: tuple[str, ...],
    applied_filters: dict[str, object],
) -> str:
    """Append the originating request's preserved filter values as query
    params on the drill-down target route (T136, FR-RPT-182) — a
    drill-down link never becomes a means to browse outside the scope of
    the report it came from."""
    preserved = {
        field: applied_filters[field]
        for field in preserves_filters
        if applied_filters.get(field) is not None
    }
    if not preserved:
        return target_route
    return f"{target_route}?{urlencode(preserved)}"


def _build_entitlement_service(db: Session) -> PlatformEntitlementService:
    return PlatformEntitlementService(
        db=db,
        plan_repo=PlanRepository(db),
        subscription_repo=SubscriptionRepository(db),
    )


class ReportExecutionService:
    """Stateless — every method takes ``db`` explicitly, matching every
    Phase 2 adapter's own stateless convention."""

    def _authorize_and_validate(
        self,
        db: Session,
        *,
        company_id: UUID,
        user_id: UUID | None,
        report_key: str,
        raw_filters: Mapping[str, object],
        sort: str | None,
        permission_kind: Literal["view", "export"],
        user_roles: list[str] | None = None,
    ) -> tuple[ReportDefinition, BaseModel, bool]:
        """``permission_kind`` — not a raw permission-code string — is what
        lets this one preamble serve both ``execute()`` (always "view")
        and Phase 6's ``ReportExportService.export()`` (always "export"):
        the actual code (``definition.required_permission`` vs.
        ``definition.export_permission``) can only be resolved *after*
        step 1's registry lookup, so the caller can't supply the string
        itself without duplicating that lookup.

        Returns ``(definition, validated_filters, is_servicing_continuity)``
        — the third value is ``True`` only for an Installments report
        served under Case B (T142); the caller sets
        ``result.meta.read_only_servicing_continuity`` from it after the
        (entitlement-unaware) adapter returns."""
        # Step 1 — registry lookup. A DEFERRED or COMPOSITE-kind key is
        # indistinguishable from an unregistered one (FR-RPT-011):
        # composite reports (exec.dashboard, crossmodule.customer_360)
        # have their own dedicated routes with differently-shaped inputs,
        # never reachable via this generic path.
        definition = REPORT_REGISTRY.get(report_key)
        if (
            definition is None
            or definition.status is not ReportStatus.NOW
            or definition.execution_kind is not ReportExecutionKind.ADAPTER
        ):
            raise ReportNotFoundError(report_key)

        required_permission = (
            definition.required_permission
            if permission_kind == "view"
            else definition.export_permission
        )
        if required_permission is None:
            # A report with no export_permission at all (aggregate/no-export
            # reports) can never satisfy an export request.
            raise ReportPermissionDeniedError(f"reports.{definition.domain}.export")

        # Step 2 — domain entitlement.
        is_servicing_continuity = False
        if definition.domain_capability_key == _INSTALLMENTS_DOMAIN_KEY:
            entitlement_service = _build_entitlement_service(db)
            reporting_service = _build_installments_reporting_service(db)
            gate = InstallmentsServicingContinuityGate(
                entitlement_service=entitlement_service,
                reporting_service=reporting_service,
            )
            state = gate.evaluate(company_id)
            if not InstallmentsServicingContinuityGate.is_allowed(
                definition.key, state
            ):
                raise ReportNotEntitledError(_INSTALLMENTS_DOMAIN_KEY)
            is_servicing_continuity = (
                state is InstallmentsAccessState.SERVICING_CONTINUITY
            )
        elif definition.domain_capability_key is not None:
            entitlement_service = _build_entitlement_service(db)
            entitlement = entitlement_service.resolve_effective_entitlement(
                company_id=company_id,
                capability_key=definition.domain_capability_key,
            )
            if not entitlement.available:
                raise ReportNotEntitledError(definition.domain_capability_key)

        # Step 3 — RBAC permission.
        if not user_has_reports_permission(
            db,
            company_id,
            user_id,
            required_permission,
            user_roles=user_roles,
        ):
            raise ReportPermissionDeniedError(required_permission)

        # Step 4 — filter validation (extra="forbid" rejects unknown
        # fields, including a branch_id the report doesn't declare —
        # FR-RPT-162 enforced structurally, never by a runtime `if`).
        try:
            validated_filters = definition.supported_filters(**raw_filters)
        except ValidationError as exc:
            raise FilterValidationError(report_key, str(exc)) from exc

        # Step 5 — sort field.
        if sort is not None and sort not in definition.sortable_fields:
            raise UnsupportedSortFieldError(report_key, sort)

        return definition, validated_filters, is_servicing_continuity

    def execute(
        self,
        db: Session,
        *,
        company_id: UUID,
        user_id: UUID | None,
        report_key: str,
        raw_filters: Mapping[str, object],
        page: int,
        page_size: int,
        sort: str | None,
        comparison: ComparisonRequest | None,
        user_roles: list[str] | None = None,
    ) -> BaseReportResult:
        definition, validated_filters, is_servicing_continuity = (
            self._authorize_and_validate(
                db,
                company_id=company_id,
                user_id=user_id,
                report_key=report_key,
                raw_filters=raw_filters,
                sort=sort,
                permission_kind="view",
                user_roles=user_roles,
            )
        )
        adapter = ADAPTER_REGISTRY[definition.domain]
        result = adapter.run(
            db,
            company_id,
            definition.key,
            validated_filters,
            page,
            page_size,
            sort,
            comparison,
        )
        if is_servicing_continuity:
            result.meta.read_only_servicing_continuity = True
        if definition.drill_down_targets:
            filters_dict = validated_filters.model_dump(mode="json")
            result.meta.drill_down = [
                DrillDownRef(
                    label=target.label,
                    target_route=_build_drill_down_route(
                        target.target_route, target.preserves_filters, filters_dict
                    ),
                    required_permission=target.required_permission,
                )
                for target in definition.drill_down_targets
            ]
        return result
