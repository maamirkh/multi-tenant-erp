"""QuotaService — the effective-quota resolver, the single authoritative
resolution path in the codebase (T108, FR-9A-181).

Resolution order (plan.md §17): **override → plan quota → unlimited**.
A tenant's active `TenantQuotaOverride` for a key always wins if one
exists — even an override whose own `override_limit` is NULL (an
explicit "unlimited override", data-model.md), which is a *different*
condition from "no override row exists at all" and must never fall
through to the plan's own limit. Absent an override, the ceiling comes
from `PlanQuota.limit_value` for the caller-supplied `plan_id`; absent
*that* row too, the key is unlimited for that plan.

"Current usage" is deliberately an **explicit caller-supplied input**,
never looked up here — this phase (8) builds the quota foundation only;
periodic/batch usage measurement (`UsageRecord`) is Phase 11's scope
(plan.md §18, "never real-time per-event writes"). Passing
``current_usage=None`` is how a caller signals "measurement not
available for this period" — resolved to the explicit ``unavailable``
state (FR-9A-062), never silently treated as zero.

This is the **only** quota resolver in the codebase — Phase 11 consumes
it (by supplying real `current_usage` from `UsageRecord` once that
exists) rather than re-implementing resolution logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from uuid import UUID

from modules.platform_admin.repositories.quota_repository import QuotaRepository

# plan.md §17 explicitly deferred the exact "approaching" threshold to the
# Tasks/Implementation phase ("configurable threshold, default TBD ... not
# fabricated [in the Plan]"). 80% is this phase's deliberate, documented
# default — a plain module constant, trivially adjustable later; it is not
# read from any config source because no such source was specified.
APPROACHING_THRESHOLD_RATIO = Decimal("0.80")


class QuotaState(str, Enum):
    """FR-9A-181's five required, mutually-exclusive states."""

    ok = "ok"
    approaching = "approaching"
    reached = "reached"
    unlimited = "unlimited"
    unavailable = "unavailable"


@dataclass(frozen=True)
class QuotaResolution:
    """The result of resolving one quota key for one tenant."""

    quota_key: str
    state: QuotaState
    limit: Decimal | None
    current_usage: Decimal | None
    enforcement_style: str | None


class QuotaService:
    """Domain service implementing the effective-quota resolution path."""

    def __init__(self, repo: QuotaRepository) -> None:
        self._repo = repo

    def resolve(
        self,
        *,
        company_id: UUID,
        plan_id: UUID | None,
        quota_key: str,
        current_usage: Decimal | None,
    ) -> QuotaResolution:
        """Resolve the effective quota state for *quota_key* for the
        tenant *company_id*, against plan *plan_id* (the tenant's
        current or, for a pending downgrade check, prospective plan).
        """
        definition = self._repo.get_definition(quota_key)
        enforcement_style = definition.enforcement_style if definition else None

        override = self._repo.get_active_override(company_id, quota_key)
        if override is not None:
            # An active override always wins, even if its own limit is
            # NULL (an explicit unlimited grant) — never fall through to
            # the plan's limit in this branch.
            limit = override.override_limit
        elif plan_id is not None:
            plan_quota = self._repo.get_plan_quota(plan_id, quota_key)
            limit = plan_quota.limit_value if plan_quota is not None else None
        else:
            limit = None

        if limit is None:
            return QuotaResolution(
                quota_key=quota_key,
                state=QuotaState.unlimited,
                limit=None,
                current_usage=current_usage,
                enforcement_style=enforcement_style,
            )

        if current_usage is None:
            return QuotaResolution(
                quota_key=quota_key,
                state=QuotaState.unavailable,
                limit=limit,
                current_usage=None,
                enforcement_style=enforcement_style,
            )

        if current_usage >= limit:
            state = QuotaState.reached
        elif limit > 0 and current_usage >= limit * APPROACHING_THRESHOLD_RATIO:
            state = QuotaState.approaching
        else:
            state = QuotaState.ok

        return QuotaResolution(
            quota_key=quota_key,
            state=state,
            limit=limit,
            current_usage=current_usage,
            enforcement_style=enforcement_style,
        )
