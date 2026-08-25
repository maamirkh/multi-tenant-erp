"""``ModuleEnablementProvider`` — per-module Tenant Toggle lookup (T118,
T119, ADR-3, plan.md §13/§40).

Reconnaissance (plan.md §40) confirmed the five modules' feature-toggle
persistence is genuinely heterogeneous: CRM has exactly one module-wide
master flag (``feature.crm.enabled``); Inventory/Sales/Purchase/Accounting
each expose only fine-grained sub-feature flags (e.g.
``inventory.product_variants``) with **no** single "whole-module" master
key. Rather than assume a uniform convention, this module uses a small
adapter protocol — one lookup per module — resolved by
``PlatformEntitlementService`` (T120) via ``get_module_enablement_provider``.

**Documented default rule (plan.md §40, decided at planning time, not
fabricated here)**: a module with no module-grain master toggle returns
``enabled=True`` — that module has no tenant-level opt-out at module
grain, so the Plan Entitlement ceiling alone governs its availability.
This is deterministic, fails safe for existing tenants (§34 rollout), and
never invents a master flag key that doesn't exist. Per-module
fine-grained flags continue to work exactly as they do today, untouched.

Every provider is **read-only** — none ever writes a tenant toggle row.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from modules.crm.repositories.feature_flag_repository import CrmFeatureFlagRepository
from modules.crm.services.feature_flag_service import CrmFeatureFlagService
from modules.installments.repositories.feature_flag import (
    InstallmentsFeatureFlagRepository,
)
from modules.installments.services.feature_flag_service import (
    InstallmentsFeatureFlagService,
)


class ModuleEnablementProvider(Protocol):
    """Answers "is this module's Tenant Toggle currently enabled for
    company X" — one ~15-line implementation per module (plan.md §13)."""

    def is_enabled(self, company_id: UUID) -> bool: ...


class CrmModuleEnablementProvider:
    """CRM has exactly one module-wide master flag
    (``constants.CRM_ENABLED_FLAG_KEY``) — read via the existing
    ``CrmFeatureFlagService`` (the same one ``require_crm_enabled`` uses).
    Never writes."""

    def __init__(self, db: Session) -> None:
        self._service = CrmFeatureFlagService(
            db=db, flag_repo=CrmFeatureFlagRepository(db)
        )

    def is_enabled(self, company_id: UUID) -> bool:
        return self._service.is_enabled(company_id)


class InstallmentsModuleEnablementProvider:
    """Installments has exactly one module-wide master flag
    (``feature.installments.enabled``) — read via the existing
    ``InstallmentsFeatureFlagService`` (the same one
    ``InstallmentAccessPolicy.authorize()`` will use, plan.md §15.2/§15.4).
    Never writes."""

    def __init__(self, db: Session) -> None:
        self._service = InstallmentsFeatureFlagService(
            flag_repo=InstallmentsFeatureFlagRepository(db)
        )

    def is_enabled(self, company_id: UUID) -> bool:
        return self._service.is_enabled(company_id)


class DefaultAlwaysEnabledModuleProvider:
    """Applies plan.md §40's documented default rule for a module with no
    module-grain master toggle: Inventory, Sales, Purchase, and Accounting
    each expose only fine-grained sub-feature flags (verified — no
    "whole-module" key exists in any of their flag catalogues), so their
    Tenant Toggle is always considered enabled and the Plan Entitlement
    ceiling alone governs availability."""

    def is_enabled(self, company_id: UUID) -> bool:  # noqa: ARG002 — protocol shape
        return True


# Modules with no module-grain master toggle share one stateless instance —
# they are behaviourally identical (the documented default rule applies to
# all four), not four independently-behaving implementations.
_DEFAULT_PROVIDER = DefaultAlwaysEnabledModuleProvider()

_DEFAULT_RULE_MODULES = frozenset({"inventory", "sales", "purchase", "accounting"})


def get_module_enablement_provider(
    capability_key: str, db: Session
) -> ModuleEnablementProvider:
    """Resolve the ``ModuleEnablementProvider`` for *capability_key*
    (one of the five seeded module-grain ``Capability`` keys, T124)."""
    if capability_key == "crm":
        return CrmModuleEnablementProvider(db)
    if capability_key == "installments":
        return InstallmentsModuleEnablementProvider(db)
    if capability_key in _DEFAULT_RULE_MODULES:
        return _DEFAULT_PROVIDER
    raise ValueError(f"No ModuleEnablementProvider registered for {capability_key!r}.")
