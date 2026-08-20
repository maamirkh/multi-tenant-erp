"""[T117] `SubscriptionService.assign_or_change()` — end-date validation
(spec Edge Case #16) and the downgrade usage-conflict acknowledgement
gate (FR-9A-165/166).
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from core.exceptions.base import ValidationException
from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.companies.repositories.company_repository import CompanyRepository
from modules.platform_admin.exceptions import SubscriptionUsageConflictError
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.repositories.quota_repository import QuotaRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.services.plan_service import PlanService
from modules.platform_admin.services.platform_audit_service import PlatformAuditService
from modules.platform_admin.services.quota_service import QuotaService, QuotaState
from modules.platform_admin.services.subscription_service import SubscriptionService
from tests.fixtures.users_roles_fixtures import create_test_member, create_test_role


def _make_actor(db: Session) -> PlatformAdministrator:
    user = User(
        email=f"t117-actor-{uuid.uuid4().hex[:10]}@example.test",
        display_name="T117 Actor",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    db.commit()
    return administrator


def _make_company(db: Session, *, owner_id) -> Company:
    suffix = uuid.uuid4().hex[:10]
    company = Company(
        legal_name=f"T117 Subscription Co {suffix}",
        slug=f"t117-subscription-co-{suffix}",
        owner_id=owner_id,
        email=f"t117-subscription-co-{suffix}@example.test",
        status="active",
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


def _make_plan_service(db: Session) -> PlanService:
    return PlanService(
        db=db,
        repo=PlanRepository(db),
        audit=PlatformAuditService(db, PlatformAuditRepository(db)),
    )


def _make_subscription_service(db: Session) -> SubscriptionService:
    return SubscriptionService(
        db=db,
        repo=SubscriptionRepository(db),
        company_repo=CompanyRepository(db),
        quota_service=QuotaService(QuotaRepository(db)),
        audit=PlatformAuditService(db, PlatformAuditRepository(db)),
        plan_repo=PlanRepository(db),
    )


def _make_published_plan(db: Session, actor: PlatformAdministrator, *, name: str):
    plan_service = _make_plan_service(db)
    plan = plan_service.create(
        code=f"t117-plan-{uuid.uuid4().hex[:8]}",
        name=name,
        actor_platform_administrator_id=actor.id,
    )
    return plan_service.publish(plan, actor_platform_administrator_id=actor.id)


def _get_or_create_users_quota_definition(db: Session):
    repo = QuotaRepository(db)
    existing = repo.get_definition("users")
    if existing is not None:
        return existing
    definition = repo.create_definition(
        key="users",
        display_name="Users",
        unit="count",
        enforcement_style="hard",
    )
    db.commit()
    return definition


def _add_active_members(db: Session, *, company_id, count: int) -> None:
    role = create_test_role(db, company_id, name="T117 Member Role", slug="t117-role")
    for _ in range(count):
        user = User(
            email=f"t117-member-{uuid.uuid4().hex[:10]}@example.test",
            display_name="T117 Member",
        )
        db.add(user)
        db.flush()
        create_test_member(
            db,
            company_id=company_id,
            user_id=user.id,
            role_id=role.id,
            status="active",
        )


class TestEndDateBeforeEffectiveDateRejected:
    def test_end_date_before_effective_date_raises_and_creates_nothing(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        plan = _make_published_plan(db_session, actor, name="Edge Case 16 Plan")
        subscription_service = _make_subscription_service(db_session)

        effective_date = date.today()
        end_date = effective_date - timedelta(days=1)

        with pytest.raises(ValidationException):
            subscription_service.assign_or_change(
                company_id=company.id,
                plan_id=plan.id,
                effective_date=effective_date,
                end_date=end_date,
                actor_platform_administrator_id=actor.id,
            )

        assert (
            SubscriptionRepository(db_session).get_active_for_company(company.id)
            is None
        )


class TestDowngradeUsageConflictAcknowledgement:
    def test_downgrade_over_limit_rejected_without_acknowledgement(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        _get_or_create_users_quota_definition(db_session)
        _add_active_members(db_session, company_id=company.id, count=3)

        plan_unlimited = _make_published_plan(
            db_session, actor, name="Unlimited Users Plan"
        )
        plan_limited = _make_published_plan(db_session, actor, name="2-User Limit Plan")
        quota_repo = QuotaRepository(db_session)
        quota_repo.set_plan_quota(plan_unlimited.id, "users", None)
        quota_repo.set_plan_quota(plan_limited.id, "users", Decimal("2"))
        db_session.commit()

        subscription_service = _make_subscription_service(db_session)
        original = subscription_service.assign_or_change(
            company_id=company.id,
            plan_id=plan_unlimited.id,
            effective_date=date.today(),
            actor_platform_administrator_id=actor.id,
        )

        with pytest.raises(SubscriptionUsageConflictError):
            subscription_service.assign_or_change(
                company_id=company.id,
                plan_id=plan_limited.id,
                effective_date=date.today(),
                actor_platform_administrator_id=actor.id,
            )

        # Rejected change never partially applied: the tenant's active
        # Subscription is still the original one, completely unchanged.
        still_current = SubscriptionRepository(db_session).get_active_for_company(
            company.id
        )
        assert still_current is not None
        assert still_current.id == original.id
        assert still_current.plan_id == plan_unlimited.id

    def test_downgrade_over_limit_applies_with_acknowledgement_and_flags_over_quota(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        _get_or_create_users_quota_definition(db_session)
        _add_active_members(db_session, company_id=company.id, count=3)

        plan_unlimited = _make_published_plan(
            db_session, actor, name="Unlimited Users Plan 2"
        )
        plan_limited = _make_published_plan(
            db_session, actor, name="2-User Limit Plan 2"
        )
        quota_repo = QuotaRepository(db_session)
        quota_repo.set_plan_quota(plan_unlimited.id, "users", None)
        quota_repo.set_plan_quota(plan_limited.id, "users", Decimal("2"))
        db_session.commit()

        subscription_service = _make_subscription_service(db_session)
        subscription_service.assign_or_change(
            company_id=company.id,
            plan_id=plan_unlimited.id,
            effective_date=date.today(),
            actor_platform_administrator_id=actor.id,
        )

        changed = subscription_service.assign_or_change(
            company_id=company.id,
            plan_id=plan_limited.id,
            effective_date=date.today(),
            actor_platform_administrator_id=actor.id,
            acknowledged=True,
        )
        assert changed.plan_id == plan_limited.id
        assert changed.status == "active"

        # No tenant data (CompanyMembers) was ever removed or truncated.
        from sqlalchemy import func, select

        from modules.users_roles.models.company_member import CompanyMember

        active_member_count = db_session.execute(
            select(func.count()).where(
                CompanyMember.company_id == company.id,
                CompanyMember.status == "active",
            )
        ).scalar_one()
        assert active_member_count == 3

        # The tenant is now naturally flagged over-quota: no new column,
        # QuotaService.resolve() reports 'reached' on the next check
        # against the new (lower) plan limit (FR-9A-166).
        quota_service = QuotaService(quota_repo)
        resolution = quota_service.resolve(
            company_id=company.id,
            plan_id=plan_limited.id,
            quota_key="users",
            current_usage=Decimal("3"),
        )
        assert resolution.state == QuotaState.reached
