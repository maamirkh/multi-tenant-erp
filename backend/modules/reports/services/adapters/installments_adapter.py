"""``InstallmentsAdapter`` — wraps Installments' already-implemented
``InstallmentReportingService`` behind the Reports ``ReportAdapter``
Protocol. Every figure is read through the service's own
``AccountingIntegrationGateway`` calls; this adapter recomputes nothing
(FR-RPT-102, T113).

**This adapter contains zero entitlement/Case-A/B logic** — it is called
only after Phase 3's ``_authorize_and_validate()`` has already decided the
request is allowed (T112). It therefore never imports
``PlatformEntitlementService`` or ``InstallmentsServicingContinuityGate``
(T115's AST-scan verifies this structurally) — the one entitlement-shaped
call any read here makes is ``InstallmentReportingService._authorize_read()``,
which is permanently a no-op for ``InstallmentOperationClass.READ``
regardless of tenant entitlement (see ``access_policy.py``), so
constructing the service with ``access_policy=None`` below is safe and
never itself raises.

``installments.due_overdue``/``installments.aging``/
``installments.settlement_writeoff`` combine two of the service's own
report methods each (due+overdue; settlement+default-writeoff) — combined
via the existing bounded population cap
(``InstallmentReportingService._DUE_STATE_POPULATION_BOUND`` = 50,000),
fetched once per source, concatenated, then sliced here — never a
separate re-derivation of either source's own filtering logic.

No filter schema in this domain accepts ``branch_id`` (correction pass,
FR-RPT-160/162): although ``InstallmentContract`` carries a ``branch_id``
column, none of ``InstallmentReportingService``'s public methods accepts
one, and Installments is not one of the 3 sanctioned T047/T075/T087
bounded-read seams — so no seam exists to honor it. Exposing the field
anyway would have meant silently accepting and discarding it (FR-RPT-162
forbids exactly that); every filter schema is ``extra="forbid"``, so a
caller that tries to pass ``branch_id`` gets a 422 validation error
instead (see ``test_installments_branch_filter.py``).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

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
from modules.installments.services.reporting_service import (
    InstallmentReportingService,
)
from modules.reports.exceptions import ReportNotFoundError
from modules.reports.schemas.common import ComparisonRequest, ReportEnvelopeMeta
from modules.reports.schemas.installments import (
    CollectionsFilter,
    ContractRegisterFilter,
    DueOverdueFilter,
    InstallmentAgingFilter,
    InstallmentDashboardFilter,
    InstallmentDashboardResponse,
    InstallmentReportRow,
    PlanPerformanceFilter,
    PlanPerformanceResponse,
    SettlementWriteoffFilter,
)
from modules.reports.services.adapters.base import (
    AggregateReportResult,
    BaseReportResult,
    PaginatedReportResult,
)

#: Mirrors ``InstallmentReportingService._DUE_STATE_POPULATION_BOUND`` —
#: the largest realistic live-obligation population for any tenant.
_POPULATION_BOUND = 50_000

_LIST_REPORT_KEYS: frozenset[str] = frozenset(
    {
        "installments.register",
        "installments.collections",
        "installments.due_overdue",
        "installments.aging",
        "installments.settlement_writeoff",
    }
)


def _build_reporting_service(db: Session) -> InstallmentReportingService:
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


def _meta(report_key: str, filters: BaseModel) -> ReportEnvelopeMeta:
    from modules.reports.schemas.common import FreshnessClassification, PeriodResolution

    return ReportEnvelopeMeta(
        report_key=report_key,
        applied_filters=filters.model_dump(mode="json"),
        period=PeriodResolution(
            start="1970-01-01T00:00:00+00:00",
            end="1970-01-01T00:00:00+00:00",
            timezone="UTC",
        ),
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
    )


class InstallmentsAdapter:
    """Stateless domain adapter for ``ReportDomain.INSTALLMENTS``'s 7
    "Now" reports."""

    def run(
        self,
        db: Session,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
        page: int,
        page_size: int,
        sort: str | None,
        comparison: ComparisonRequest | None,
    ) -> BaseReportResult:
        service = _build_reporting_service(db)

        if report_key == "installments.plan_performance":
            assert isinstance(filters, PlanPerformanceFilter)
            rows, total = service.get_plan_performance_report(company_id)
            return AggregateReportResult[PlanPerformanceResponse](
                meta=_meta(report_key, filters),
                data=PlanPerformanceResponse(
                    rows=[InstallmentReportRow.model_validate(r) for r in rows],
                    total=total,
                ),
            )
        if report_key == "installments.dashboard":
            assert isinstance(filters, InstallmentDashboardFilter)
            dashboard = service.get_dashboard(company_id, as_of_date=filters.as_of_date)
            return AggregateReportResult[InstallmentDashboardResponse](
                meta=_meta(report_key, filters),
                data=InstallmentDashboardResponse(
                    active_contract_count=dashboard.active_contract_count,
                    outstanding_amount=dashboard.outstanding_amount,
                    due_today_amount=dashboard.due_today_amount,
                    due_this_month_amount=dashboard.due_this_month_amount,
                    collected_today_amount=dashboard.collected_today_amount,
                    collected_this_month_amount=dashboard.collected_this_month_amount,
                    overdue_amount=dashboard.overdue_amount,
                    overdue_count=dashboard.overdue_count,
                    collection_rate=dashboard.collection_rate,
                    aging_distribution=dashboard.aging_distribution,
                    defaulted_balance=dashboard.defaulted_balance,
                    written_off_balance=dashboard.written_off_balance,
                    upcoming_receivables_amount=dashboard.upcoming_receivables_amount,
                ),
            )

        rows, total = self._run_list_report(
            service, report_key, filters, company_id, page, page_size
        )
        return PaginatedReportResult[InstallmentReportRow](
            meta=_meta(report_key, filters),
            items=[InstallmentReportRow.model_validate(r) for r in rows],
            total=total,
        )

    def count_export_rows(
        self, db: Session, company_id: UUID, report_key: str, filters: BaseModel
    ) -> int:
        if report_key not in _LIST_REPORT_KEYS:
            raise ValueError(f"'{report_key}' has no export-row count seam.")
        service = _build_reporting_service(db)
        _rows, total = self._run_list_report(
            service, report_key, filters, company_id, page=1, page_size=1
        )
        return total

    def iter_export_rows(
        self,
        db: Session,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
        sort: str | None,
        batch_size: int,
    ) -> Iterator[list[BaseModel]]:
        if report_key not in _LIST_REPORT_KEYS:
            raise ValueError(f"'{report_key}' has no export-row iteration seam.")
        service = _build_reporting_service(db)
        offset = 0
        while True:
            rows, total = self._run_list_report(
                service,
                report_key,
                filters,
                company_id,
                page=(offset // batch_size) + 1,
                page_size=batch_size,
            )
            if not rows:
                return
            batch: list[BaseModel] = [
                InstallmentReportRow.model_validate(r) for r in rows
            ]
            yield batch
            offset += batch_size
            if offset >= total:
                return

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_list_report(
        self,
        service: InstallmentReportingService,
        report_key: str,
        filters: BaseModel,
        company_id: UUID,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        skip = (page - 1) * page_size

        if report_key == "installments.register":
            assert isinstance(filters, ContractRegisterFilter)
            return service.get_contract_register(
                company_id, status=filters.status, skip=skip, limit=page_size
            )
        if report_key == "installments.collections":
            assert isinstance(filters, CollectionsFilter)
            return service.get_collection_report(
                company_id,
                since=filters.since,
                until=filters.until,
                skip=skip,
                limit=page_size,
            )
        if report_key == "installments.due_overdue":
            assert isinstance(filters, DueOverdueFilter)
            due_rows, _due_total = service.get_due_report(
                company_id, skip=0, limit=_POPULATION_BOUND
            )
            overdue_rows, _overdue_total = service.get_overdue_report(
                company_id, skip=0, limit=_POPULATION_BOUND
            )
            combined = due_rows + overdue_rows
            return combined[skip : skip + page_size], len(combined)
        if report_key == "installments.aging":
            assert isinstance(filters, InstallmentAgingFilter)
            rows, total = service.get_aging_report(
                company_id,
                as_of_date=filters.as_of_date,
                skip=0,
                limit=_POPULATION_BOUND,
            )
            return rows[skip : skip + page_size], total
        if report_key == "installments.settlement_writeoff":
            assert isinstance(filters, SettlementWriteoffFilter)
            settlement_rows, _settlement_total = service.get_settlement_report(
                company_id, skip=0, limit=_POPULATION_BOUND
            )
            writeoff_rows, _writeoff_total = service.get_default_writeoff_report(
                company_id, skip=0, limit=_POPULATION_BOUND
            )
            combined = settlement_rows + writeoff_rows
            return combined[skip : skip + page_size], len(combined)
        raise ReportNotFoundError(report_key)
