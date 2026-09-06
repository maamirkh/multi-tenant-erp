"""[T115] Retiring a `Plan` keeps existing Subscriptions intact but makes
the Plan unassignable for any *new* Subscription (BR-9A-018,
FR-9A-152, spec US-4 scenario 2).
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.companies.repositories.company_repository import CompanyRepository
from modules.platform_admin.exceptions import (
    PlanNotAssignableError,
    PlanTransitionError,
)
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
from modules.platform_admin.services.quota_service import QuotaService
from modules.platform_admin.services.subscription_service import SubscriptionService


def _make_actor(db: Session) -> PlatformAdministrator:
    user = User(
        email=f"plan-lifecycle-actor-{uuid.uuid4().hex[:10]}@example.test",
        display_name="Plan Lifecycle Actor",
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
        legal_name=f"Plan Lifecycle Co {suffix}",
        slug=f"plan-lifecycle-co-{suffix}",
        owner_id=owner_id,
        email=f"plan-lifecycle-co-{suffix}@example.test",
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


class TestRetiredPlanKeepsExistingSubscriptionsIntact:
    def test_retire_does_not_touch_existing_subscription(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        plan_service = _make_plan_service(db_session)
        subscription_service = _make_subscription_service(db_session)

        plan = plan_service.create(
            code=f"plan-{uuid.uuid4().hex[:8]}",
            name="Retirement Test Plan",
            capability_map={"inventory.basic": True},
            actor_platform_administrator_id=actor.id,
        )
        plan_service.publish(plan, actor_platform_administrator_id=actor.id)

        subscription = subscription_service.assign_or_change(
            company_id=company.id,
            plan_id=plan.id,
            effective_date=date.today(),
            actor_platform_administrator_id=actor.id,
            reason="T115 initial assignment",
        )
        assert subscription.status == "active"
        assert subscription.plan_id == plan.id

        retired = plan_service.retire(plan, actor_platform_administrator_id=actor.id)
        assert retired.status == "retired"

        # The tenant's existing Subscription is completely untouched.
        still_current = SubscriptionRepository(db_session).get_active_for_company(
            company.id
        )
        assert still_current is not None
        assert still_current.id == subscription.id
        assert still_current.status == "active"
        assert still_current.plan_id == plan.id

        # Entitlements (capability ceiling) are unchanged by retirement.
        assert PlanRepository(db_session).get_capability_map(plan.id) == {
            "inventory.basic": True
        }

    def test_retired_plan_rejects_a_new_assignment(self, db_session: Session) -> None:
        actor = _make_actor(db_session)
        subscribed_company = _make_company(db_session, owner_id=actor.user_id)
        new_company = _make_company(db_session, owner_id=actor.user_id)
        plan_service = _make_plan_service(db_session)
        subscription_service = _make_subscription_service(db_session)

        plan = plan_service.create(
            code=f"plan-{uuid.uuid4().hex[:8]}",
            name="Unassignable After Retirement",
            actor_platform_administrator_id=actor.id,
        )
        plan_service.publish(plan, actor_platform_administrator_id=actor.id)
        subscription_service.assign_or_change(
            company_id=subscribed_company.id,
            plan_id=plan.id,
            effective_date=date.today(),
            actor_platform_administrator_id=actor.id,
        )
        plan_service.retire(plan, actor_platform_administrator_id=actor.id)

        with pytest.raises(PlanNotAssignableError):
            subscription_service.assign_or_change(
                company_id=new_company.id,
                plan_id=plan.id,
                effective_date=date.today(),
                actor_platform_administrator_id=actor.id,
            )

        # The new tenant genuinely has no active Subscription now.
        assert (
            SubscriptionRepository(db_session).get_active_for_company(new_company.id)
            is None
        )

    def test_retired_plan_remains_visible_read_only(self, db_session: Session) -> None:
        actor = _make_actor(db_session)
        plan_service = _make_plan_service(db_session)
        plan = plan_service.create(
            code=f"plan-{uuid.uuid4().hex[:8]}",
            name="Visible After Retirement",
            actor_platform_administrator_id=actor.id,
        )
        plan_service.publish(plan, actor_platform_administrator_id=actor.id)
        retired = plan_service.retire(plan, actor_platform_administrator_id=actor.id)

        fetched = PlanRepository(db_session).get_by_id(retired.id)
        assert fetched is not None
        assert fetched.status == "retired"


class TestPlanStatusTransitionGuards:
    def test_cannot_retire_a_draft_plan(self, db_session: Session) -> None:
        actor = _make_actor(db_session)
        plan_service = _make_plan_service(db_session)
        plan = plan_service.create(
            code=f"plan-{uuid.uuid4().hex[:8]}",
            name="Draft Plan",
            actor_platform_administrator_id=actor.id,
        )
        with pytest.raises(PlanTransitionError):
            plan_service.retire(plan, actor_platform_administrator_id=actor.id)

    def test_cannot_publish_an_already_published_plan(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        plan_service = _make_plan_service(db_session)
        plan = plan_service.create(
            code=f"plan-{uuid.uuid4().hex[:8]}",
            name="Twice Published Plan",
            actor_platform_administrator_id=actor.id,
        )
        plan_service.publish(plan, actor_platform_administrator_id=actor.id)
        with pytest.raises(PlanTransitionError):
            plan_service.publish(plan, actor_platform_administrator_id=actor.id)

    def test_cannot_assign_a_draft_plan(self, db_session: Session) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        plan_service = _make_plan_service(db_session)
        subscription_service = _make_subscription_service(db_session)
        plan = plan_service.create(
            code=f"plan-{uuid.uuid4().hex[:8]}",
            name="Draft Not Yet Assignable",
            actor_platform_administrator_id=actor.id,
        )
        with pytest.raises(PlanNotAssignableError):
            subscription_service.assign_or_change(
                company_id=company.id,
                plan_id=plan.id,
                effective_date=date.today(),
                actor_platform_administrator_id=actor.id,
            )
