"""Discovery: filters the Report Registry to what one user, in one
company, is actually permitted and entitled to reach (FR-RPT-032).

Only ``status == NOW`` entries are ever reachable — a ``DEFERRED`` entry
is never returned here, matching ``ReportExecutionService``'s identical
filtering rule (FR-RPT-011).

Installments follows the **same** servicing-continuity rule execution does
(Phase 9 correction, found by T259's real-browser check): with the
Installments entitlement disabled but existing obligations still being
serviced (Case B), the five allow-listed servicing reports stay
discoverable — exactly the set ``GET /reports/{key}`` still serves (T142) —
while ``plan_performance``/``dashboard`` stay hidden. Discovery previously
applied only the plain entitlement check, hiding every Installments key
under Case B, so navigation (driven solely by discovery, FR-RPT-320) could
not reach reports the user is entitled to service.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.services.entitlement_service import (
    PlatformEntitlementService,
)
from modules.reports.registry.definitions import (
    REPORT_REGISTRY,
    ReportDefinition,
    ReportStatus,
)
from modules.reports.services.execution_service import (
    _INSTALLMENTS_DOMAIN_KEY,
    _build_installments_reporting_service,
)
from modules.reports.services.installments_continuity_gate import (
    InstallmentsAccessState,
    InstallmentsServicingContinuityGate,
)
from modules.reports.services.permission_check import user_has_reports_permission


def list_discoverable_reports(
    db: Session, company_id: UUID, user_id: UUID | None
) -> list[ReportDefinition]:
    """Return every ``status == NOW`` ``ReportDefinition`` the requesting
    user currently holds ``required_permission`` for, and whose
    ``domain_capability_key`` (if any) resolves to entitled."""
    entitlement_service = PlatformEntitlementService(
        db=db,
        plan_repo=PlanRepository(db),
        subscription_repo=SubscriptionRepository(db),
    )

    installments_state: InstallmentsAccessState | None = None

    reachable: list[ReportDefinition] = []
    for definition in REPORT_REGISTRY.values():
        if definition.status is not ReportStatus.NOW:
            continue
        if not user_has_reports_permission(
            db, company_id, user_id, definition.required_permission
        ):
            continue
        if definition.domain_capability_key == _INSTALLMENTS_DOMAIN_KEY:
            # Evaluated once per request, and only if an Installments key
            # got this far — the identical gate _authorize_and_validate()
            # applies on execution.
            if installments_state is None:
                installments_state = InstallmentsServicingContinuityGate(
                    entitlement_service=entitlement_service,
                    reporting_service=_build_installments_reporting_service(db),
                ).evaluate(company_id)
            if not InstallmentsServicingContinuityGate.is_allowed(
                definition.key, installments_state
            ):
                continue
        elif definition.domain_capability_key is not None:
            entitlement = entitlement_service.resolve_effective_entitlement(
                company_id=company_id,
                capability_key=definition.domain_capability_key,
            )
            if not entitlement.available:
                continue
        reachable.append(definition)

    return reachable
