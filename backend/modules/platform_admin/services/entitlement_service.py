"""PlatformEntitlementService — the single authoritative entitlement
resolver (T120, ADR-3, FR-9A-170, BR-9A-015/016).

Implements spec.md §17.2's resolution table exactly:

| Plan Entitlement | Tenant Toggle | Effective Result |
|---|---|---|
| Allowed | Enabled | Available |
| Allowed | Disabled | Unavailable (tenant's own choice) |
| Not Allowed | (any) | Unavailable — the Plan ceiling, never exceeded by a toggle |
| Not Allowed, active Override | (irrelevant) | Available for the override's duration |
| Moved to a plan lacking a previously-entitled module | (was Enabled) | Unavailable immediately; toggle preserved, not deleted |

Resolved fresh **per request** (never cached indefinitely, FR-9A-170) —
callers must not memoise a result across requests.

**Tenant-lifecycle scope note**: this resolver deliberately does not
re-check ``Company.status``/suspension itself. Every caller (the
``require_capability_entitled`` mount-level dependency, T122, and the
read-only endpoint, T123) only ever runs after
``get_current_company_member`` has already gated the request via
``assert_company_access_allowed`` (Phase 7, Gate C) — company lifecycle
is that layer's concern, not this resolver's. Duplicating it here would
be a second, divergent enforcement point for the same fact. "Current
subscription" **is** consulted directly (via ``SubscriptionRepository``).

**No active Subscription — the ceiling does not (yet) apply.** spec.md
§17.2's resolution table implicitly assumes a Plan Entitlement value
already exists; it does not define a "no Plan at all" row. A company can
be in this state either because it predates Epic 9A's rollout (§34
step 4 has not run for it yet) or because it is a brand-new tenant that
has not yet been assigned a commercial Plan by anyone. Both cases are
resolved identically and deliberately: the Plan ceiling is treated as
**not yet in effect**, and the result defers entirely to the Tenant
Toggle — i.e. exactly the pre-Epic-9A behaviour (no entitlement layer
existed at all; CRM was gated only by its own toggle, and the other four
modules had no gate whatsoever). This is not a weakening of the ceiling
for any tenant that *does* have an active Subscription — for those, an
explicit ``PlanCapability.allowed=false`` still denies unconditionally,
regardless of the toggle, exactly as §17.2 specifies. Treating "no
Subscription" as "Unavailable" was evaluated and rejected: it would
retroactively lock every pre-existing company created without going
through the one-time rollout (verified directly — it reproducibly turns
every pre-Epic-9A module's own test suite into a wall of 403s, and would
identically brick every brand-new tenant signup, since nothing outside
this Epic's scope creates a Subscription at company-creation time). That
contradicts plan.md's repeated, explicit guarantee that Epic 9A "must not
instantly change existing tenant access" (§34) and "Existing tenants
unaffected" (§33.1) — a guarantee this resolver must honour for any
company Epic 9A has not yet (or may never) assign a Subscription to, not
only the ones the one-time rollout happened to reach.

**Override — documented Phase 9 scope gap**: ``EntitlementOverride`` (the
model backing §17.2's "active Override" row) does not exist until Phase
11 (tasks.md T145) — creating it now would be future-phase leakage. This
service exposes an injectable ``OverrideChecker`` seam (mirroring
``PlatformAdministratorService``'s ``SessionRevoker`` seam, T040/T054) so
Phase 11's T147 can wire in real override consultation, including
expiry-at-read-time semantics, without rewriting this method's shape.
With no checker injected (the Phase 9 state), the Override branch of the
resolution table is unreachable and every other row resolves exactly as
specified.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.services.module_enablement import (
    get_module_enablement_provider,
)


class OverrideChecker(Protocol):
    """Seam for Phase 11's T147 to inject real
    ``EntitlementOverride`` consultation (with expiry-at-read-time
    semantics), without this service needing to change."""

    def has_active_override(self, company_id: UUID, capability_key: str) -> bool: ...


@dataclass(frozen=True)
class EffectiveEntitlement:
    """The result of resolving one capability for one tenant."""

    capability_key: str
    available: bool
    reason: str
    """One of: "override", "plan_ceiling", "no_subscription_ceiling_inapplicable",
    "tenant_toggle_disabled", "plan_and_toggle"."""


class PlatformEntitlementService:
    """Domain service implementing the Plan x Toggle x Override
    resolution — the **only** entitlement resolver in the codebase; no
    module re-implements this logic (BR-9A-015/016)."""

    def __init__(
        self,
        db: Session,
        plan_repo: PlanRepository,
        subscription_repo: SubscriptionRepository,
        override_checker: OverrideChecker | None = None,
    ) -> None:
        self._db = db
        self._plan_repo = plan_repo
        self._subscription_repo = subscription_repo
        self._override_checker = override_checker

    def resolve_effective_entitlement(
        self, *, company_id: UUID, capability_key: str
    ) -> EffectiveEntitlement:
        """Resolve *capability_key* for *company_id*, evaluated fresh —
        never cached (FR-9A-170)."""
        if self._override_checker is not None:
            has_override = self._override_checker.has_active_override(
                company_id, capability_key
            )
            if has_override:
                return EffectiveEntitlement(
                    capability_key=capability_key, available=True, reason="override"
                )

        subscription = self._subscription_repo.get_active_for_company(company_id)
        if subscription is None:
            # No Plan ceiling exists yet for this tenant — defer entirely
            # to the Tenant Toggle (see module docstring).
            provider = get_module_enablement_provider(capability_key, self._db)
            return EffectiveEntitlement(
                capability_key=capability_key,
                available=provider.is_enabled(company_id),
                reason="no_subscription_ceiling_inapplicable",
            )

        capability_map = self._plan_repo.get_capability_map(subscription.plan_id)
        if not capability_map.get(capability_key, False):
            # Plan ceiling — a tenant toggle can never exceed this,
            # regardless of its own stored value (never inspected here).
            return EffectiveEntitlement(
                capability_key=capability_key, available=False, reason="plan_ceiling"
            )

        provider = get_module_enablement_provider(capability_key, self._db)
        if not provider.is_enabled(company_id):
            return EffectiveEntitlement(
                capability_key=capability_key,
                available=False,
                reason="tenant_toggle_disabled",
            )

        return EffectiveEntitlement(
            capability_key=capability_key, available=True, reason="plan_and_toggle"
        )
