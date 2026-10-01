"""``InstallmentsServicingContinuityGate`` — the Case A/B entitlement
decision for Installments' 7 report keys (spec §22.3/22.4,
FR-INST-353-358, mirrored for Reports per FR-RPT-104).

A pure, independently-testable service: it depends only on
``PlatformEntitlementService`` (resolves the Plan x Toggle x Override
entitlement, never re-implemented here) and ``InstallmentReportingService``
(read-only — its own ``_authorize_read()`` always passes for
``InstallmentOperationClass.READ``, so calling it here never itself
raises on a disabled tenant). It has **no dependency on the Reports
execution/router layer** (Phase 3's job, T126) — this is registration +
pure-decision plumbing only, exactly like ``InstallmentAccessPolicy``'s
own precedent one layer down in Installments itself.

Case A (disabled, no existing obligations) -> ``UNAVAILABLE``: every
``installments.*`` key is blocked.
Case B (disabled, but at least one existing contract) ->
``SERVICING_CONTINUITY``: only the 5 allow-listed, contract-linked
reports remain reachable (``plan_performance``/``dashboard`` are not —
they characterize adoption/aggregate health, not the servicing of a
specific existing obligation).
Entitled -> ``ENTITLED_FULL``: every key is reachable.
"""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from modules.installments.services.access_policy import INSTALLMENTS_CAPABILITY_KEY
from modules.installments.services.reporting_service import InstallmentReportingService
from modules.platform_admin.services.entitlement_service import (
    PlatformEntitlementService,
)


class InstallmentsAccessState(str, Enum):
    ENTITLED_FULL = "ENTITLED_FULL"
    SERVICING_CONTINUITY = "SERVICING_CONTINUITY"
    UNAVAILABLE = "UNAVAILABLE"


_SERVICING_CONTINUITY_ALLOWLIST = frozenset(
    {
        "installments.register",
        "installments.collections",
        "installments.due_overdue",
        "installments.aging",
        "installments.settlement_writeoff",
    }
)


class InstallmentsServicingContinuityGate:
    def __init__(
        self,
        entitlement_service: PlatformEntitlementService,
        reporting_service: InstallmentReportingService,
    ) -> None:
        self._entitlement_service = entitlement_service
        self._reporting_service = reporting_service

    def evaluate(self, company_id: UUID) -> InstallmentsAccessState:
        entitlement = self._entitlement_service.resolve_effective_entitlement(
            company_id=company_id, capability_key=INSTALLMENTS_CAPABILITY_KEY
        )
        if entitlement.available:
            return InstallmentsAccessState.ENTITLED_FULL

        _rows, total = self._reporting_service.get_contract_register(
            company_id, skip=0, limit=1
        )
        if total > 0:
            return InstallmentsAccessState.SERVICING_CONTINUITY
        return InstallmentsAccessState.UNAVAILABLE

    @staticmethod
    def is_allowed(report_key: str, state: InstallmentsAccessState) -> bool:
        if state is InstallmentsAccessState.ENTITLED_FULL:
            return True
        if state is InstallmentsAccessState.SERVICING_CONTINUITY:
            return report_key in _SERVICING_CONTINUITY_ALLOWLIST
        return False
