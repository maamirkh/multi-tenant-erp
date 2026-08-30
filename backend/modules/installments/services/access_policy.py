"""``InstallmentAccessPolicy`` — the centralized, per-service-method
entitlement gate (tasks.md T188, plan.md §15.2).

Unlike CRM/Sales/Purchase/Accounting, whose ``require_capability_entitled``
ceiling is enforced once at router-mount time (a blanket, whole-router
gate), Installments' spec (§22.3/22.4, FR-INST-353-358) requires
**operation-level** granularity: origination of new obligations is
blocked while the module is disabled for a tenant, but servicing of
obligations that already existed remains available. A router-mount gate
cannot express that distinction (plan.md §15.1, ADR-INST-06) — so this
check lives inside each service method instead, called as the first
statement, before any repository access.

Resolution goes through the single authoritative
``PlatformEntitlementService.resolve_effective_entitlement()`` — the same
Plan x Toggle x Override resolver every other entitled module uses handled
via ``require_capability_entitled`` — never re-implemented or duplicated
here. Never cached across calls (FR-9A-170's "resolved fresh" discipline).

Suspended tenants are handled entirely upstream by
``get_current_company_member`` (plan.md §2) — this policy deliberately
never re-checks ``Company.status`` (plan.md §15.3).
"""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from modules.installments.exceptions import InstallmentsNotEntitledError
from modules.platform_admin.services.entitlement_service import (
    PlatformEntitlementService,
)

INSTALLMENTS_CAPABILITY_KEY = "installments"


class InstallmentOperationClass(str, Enum):
    """Every Installments service-method call is classified into exactly
    one of these four (plan.md §15.2)."""

    ORIGINATION = "ORIGINATION"
    """New quote, new contract, activation of a NEW contract, plan/
    template CRUD, configuration changes, reschedule, cancel, default,
    writeoff (FR-INST-353/357) — blocked while disabled."""

    SERVICING = "SERVICING"
    """View existing contract/schedule/history, collection, allocation,
    reversal/correction, ordinary payoff, early settlement of an EXISTING
    contract, statements, late-charge application/waiver (FR-INST-356) —
    always permitted, entitled or not."""

    READ = "READ"
    """Pure read of existing data — always allowed."""

    ADMIN = "ADMIN"
    """The module enable/disable toggle itself — reachable while disabled
    (chicken-and-egg, same as CRM's admin_router). Bypasses this check
    entirely."""


class InstallmentAccessPolicy:
    """Classifies every Installments operation and enforces
    FR-INST-353/356/357/358 — never the RBAC permission check itself
    (that remains ``user_has_installments_permission()``, checked
    separately in ``router.py``); this only governs entitlement."""

    def __init__(self, entitlement_service: PlatformEntitlementService) -> None:
        self._entitlement_service = entitlement_service

    def authorize(
        self, *, company_id: UUID, operation: InstallmentOperationClass
    ) -> None:
        if operation is InstallmentOperationClass.ADMIN:
            return
        entitlement = self._entitlement_service.resolve_effective_entitlement(
            company_id=company_id, capability_key=INSTALLMENTS_CAPABILITY_KEY
        )
        if entitlement.available:
            return
        if operation in (
            InstallmentOperationClass.SERVICING,
            InstallmentOperationClass.READ,
        ):
            return
        raise InstallmentsNotEntitledError()
