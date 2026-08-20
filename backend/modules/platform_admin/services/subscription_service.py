"""SubscriptionService.assign_or_change() — a tenant's plan assignment
(T112, BR-9A-014), with the downgrade usage-conflict acknowledgement
gate (T113, FR-9A-165/166).

Fail-closed atomicity (ADR-5): ends the previous active Subscription (if
any), creates the new one, and syncs the denormalised
`companies.subscription_id` pointer (ADR-9) — all flush-only — then
stages an audit row and performs a single service-level `db.commit()`.

**Usage-conflict scope note (Phase 8)**: FR-9A-165 requires comparing
"current usage" against the target plan's limits, but periodic/batch
usage measurement (`UsageRecord`) is Phase 11's scope (plan.md §18) —
this phase builds the quota *foundation* only. The one quota category
with a genuine real-time source available right now is `users`, counted
live from `CompanyMember` (exactly the worked example in spec.md US-5
scenario 1: "a tenant on Plan A with 40 users... Plan B with a 25-user
limit"). Other quota categories (`branches`, `transactions`, `storage`,
`api_calls`, `ai_credits`) have no live source in this phase and are
therefore not included in the conflict check — `QuotaService.resolve()`
already correctly reports `unavailable` for any key given no usage
input, so nothing is silently treated as "no conflict" versus "unlimited
usage" for those. Phase 11 extends this check once `UsageRecord` exists,
without changing this method's shape.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.exceptions.base import NotFoundException, ValidationException
from modules.companies.repositories.company_repository import CompanyRepository
from modules.platform_admin.exceptions import (
    PlanNotAssignableError,
    SubscriptionUsageConflictError,
)
from modules.platform_admin.models.subscription import Subscription
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.services.platform_audit_service import PlatformAuditService
from modules.platform_admin.services.quota_service import QuotaService, QuotaState
from modules.users_roles.models.company_member import CompanyMember

_LIVE_MEASURABLE_QUOTA_KEY = "users"


def _subscription_snapshot(subscription: Subscription) -> dict[str, Any]:
    return {
        "plan_id": str(subscription.plan_id),
        "status": subscription.status,
        "effective_date": subscription.effective_date.isoformat(),
    }


class SubscriptionService:
    """Domain service for assigning/changing a tenant's Subscription."""

    def __init__(
        self,
        db: Session,
        repo: SubscriptionRepository,
        company_repo: CompanyRepository,
        quota_service: QuotaService,
        audit: PlatformAuditService,
        plan_repo: PlanRepository | None = None,
    ) -> None:
        self._db = db
        self._repo = repo
        self._company_repo = company_repo
        self._quota_service = quota_service
        self._audit = audit
        self._plan_repo = plan_repo if plan_repo is not None else PlanRepository(db)

    def _current_live_usage(self, company_id: UUID) -> dict[str, Decimal]:
        """Usage sources genuinely measurable in real time, within this
        phase's scope (see module docstring)."""
        count = self._db.execute(
            select(func.count())
            .select_from(CompanyMember)
            .where(
                CompanyMember.company_id == company_id,
                CompanyMember.status == "active",
            )
        ).scalar_one()
        return {_LIVE_MEASURABLE_QUOTA_KEY: Decimal(count)}

    def _find_usage_conflicts(self, company_id: UUID, plan_id: UUID) -> list[str]:
        conflicts: list[str] = []
        for quota_key, usage in self._current_live_usage(company_id).items():
            resolution = self._quota_service.resolve(
                company_id=company_id,
                plan_id=plan_id,
                quota_key=quota_key,
                current_usage=usage,
            )
            if resolution.state == QuotaState.reached:
                conflicts.append(quota_key)
        return conflicts

    def assign_or_change(
        self,
        *,
        company_id: UUID,
        plan_id: UUID,
        effective_date: date,
        end_date: date | None = None,
        actor_platform_administrator_id: UUID,
        reason: str | None = None,
        acknowledged: bool = False,
    ) -> Subscription:
        """Assign a Plan to a tenant for the first time, or change an
        existing assignment.

        Raises:
            ValidationException: `end_date` precedes `effective_date`
                (spec Edge Case #16) — rejected before any write.
            NotFoundException: `plan_id` does not reference an existing
                Plan.
            PlanNotAssignableError: the target Plan is not `published`
                (BR-9A-018/FR-9A-152) — a `retired` Plan blocks only this
                **new**-assignment path; its existing Subscriptions are
                never touched by this check.
            SubscriptionUsageConflictError: current usage exceeds the
                target plan's limits and `acknowledged` is not True
                (FR-9A-165).
        """
        if end_date is not None and end_date < effective_date:
            raise ValidationException(
                "end_date must not be before effective_date.",
                details={
                    "effective_date": effective_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
            )

        plan = self._plan_repo.get_by_id(plan_id)
        if plan is None:
            raise NotFoundException(message="Plan not found.")
        if plan.status != "published":
            raise PlanNotAssignableError(
                details={"plan_id": str(plan_id), "plan_status": plan.status}
            )

        conflicts = self._find_usage_conflicts(company_id, plan_id)
        if conflicts and not acknowledged:
            raise SubscriptionUsageConflictError(
                details={"conflicting_quota_keys": conflicts}
            )

        existing_active = self._repo.get_active_for_company(company_id)
        before_state = (
            _subscription_snapshot(existing_active) if existing_active else None
        )

        if existing_active is not None:
            self._repo.end(existing_active, ended_at=datetime.now(UTC))

        new_subscription = self._repo.create(
            company_id=company_id,
            plan_id=plan_id,
            status="active",
            effective_date=effective_date,
            actor_id=actor_platform_administrator_id,
            reason=reason,
        )

        company = self._company_repo.get_by_id(company_id)
        if company is not None:
            self._company_repo.set_subscription_id(company, new_subscription.id)

        self._audit.record(
            action="subscription.assign_or_change",
            target_type="Subscription",
            target_id=new_subscription.id,
            company_id=company_id,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason=reason,
            before_state=before_state,
            after_state=_subscription_snapshot(new_subscription)
            | {"acknowledged_usage_conflicts": conflicts},
        )
        self._db.commit()
        return new_subscription
