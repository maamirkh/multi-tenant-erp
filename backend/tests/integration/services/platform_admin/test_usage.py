"""[T153] Usage unavailability vs genuine zero — Epic 9A Phase 11
(FR-9A-060/062, T151/T152).

Proves the distinction `QuotaService.resolve()` already promised in
Phase 8's docstring but had no real caller for until this phase: absence
of a current-period `UsageRecord` resolves `unavailable`; a genuinely
computed zero (e.g. a company with zero active members) resolves `ok`
(or whatever state its magnitude implies) — never conflated.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.companies.repositories.company_repository import CompanyRepository
from modules.platform_admin.models.plan import Plan
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.repositories.quota_repository import QuotaRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.repositories.usage_repository import UsageRepository
from modules.platform_admin.services.platform_audit_service import PlatformAuditService
from modules.platform_admin.services.quota_service import QuotaService, QuotaState
from modules.platform_admin.services.subscription_service import SubscriptionService
from modules.platform_admin.services.usage_service import (
    UsageService,
    current_month_period,
)
from tests.fixtures.users_roles_fixtures import create_test_member, create_test_role


def _make_actor(db: Session) -> PlatformAdministrator:
    user = User(
        email=f"t153-actor-{uuid.uuid4().hex[:10]}@example.test",
        display_name="T153 Actor",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    db.commit()
    return administrator


def _make_company(db: Session, *, owner_id: UUID) -> Company:
    suffix = uuid.uuid4().hex[:10]
    company = Company(
        legal_name=f"T153 Usage Co {suffix}",
        slug=f"t153-usage-co-{suffix}",
        owner_id=owner_id,
        email=f"t153-usage-co-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    return company


def _subscribe_with_users_limit(
    db: Session, *, company: Company, actor: PlatformAdministrator, limit_value: int
) -> UUID:
    suffix = uuid.uuid4().hex[:10]
    plan = Plan(code=f"t153-plan-{suffix}", name="T153 Usage Plan", status="published")
    db.add(plan)
    db.flush()
    PlanRepository(db).set_capabilities(plan.id, {"inventory": True})
    QuotaRepository(db).set_plan_quota(plan.id, "users", Decimal(limit_value))
    db.commit()

    SubscriptionService(
        db=db,
        repo=SubscriptionRepository(db),
        company_repo=CompanyRepository(db),
        quota_service=QuotaService(QuotaRepository(db)),
        audit=PlatformAuditService(db, PlatformAuditRepository(db)),
    ).assign_or_change(
        company_id=company.id,
        plan_id=plan.id,
        effective_date=date.today(),
        actor_platform_administrator_id=actor.id,
    )
    return plan.id


class TestUsageUnavailableVersusGenuineZero:
    def test_absence_of_usage_record_resolves_unavailable(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        plan_id = _subscribe_with_users_limit(
            db_session, company=company, actor=actor, limit_value=10
        )

        # No UsageRecord has ever been computed for this company/period.
        usage_repo = UsageRepository(db_session)
        period_start, period_end = current_month_period()
        record = usage_repo.get_for_period(
            company_id=company.id,
            metric_key="users",
            period_start=period_start,
            period_end=period_end,
        )
        assert record is None

        resolution = QuotaService(QuotaRepository(db_session)).resolve(
            company_id=company.id,
            plan_id=plan_id,
            quota_key="users",
            current_usage=record.quantity if record else None,
        )
        assert resolution.state == QuotaState.unavailable
        assert resolution.current_usage is None

    def test_genuine_zero_usage_resolves_ok_not_unavailable(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        plan_id = _subscribe_with_users_limit(
            db_session, company=company, actor=actor, limit_value=10
        )
        # A freshly-created Company (direct model insert, as this test's
        # own _make_company helper does) has zero CompanyMember rows —
        # a genuine, deliberate zero, not an accident of fixture setup.

        usage_service = UsageService(db_session, UsageRepository(db_session))
        period_start, period_end = current_month_period()
        usage_service.compute_for_company(
            company_id=company.id, period_start=period_start, period_end=period_end
        )

        usage_repo = UsageRepository(db_session)
        record = usage_repo.get_for_period(
            company_id=company.id,
            metric_key="users",
            period_start=period_start,
            period_end=period_end,
        )
        assert record is not None
        assert record.quantity == Decimal(0)

        resolution = QuotaService(QuotaRepository(db_session)).resolve(
            company_id=company.id,
            plan_id=plan_id,
            quota_key="users",
            current_usage=record.quantity,
        )
        # Genuinely zero and measured — must resolve `ok`, never
        # `unavailable` (that would conflate "measured zero" with
        # "never measured").
        assert resolution.state == QuotaState.ok
        assert resolution.current_usage == Decimal(0)

    def test_compute_reflects_real_active_member_count(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        _subscribe_with_users_limit(
            db_session, company=company, actor=actor, limit_value=10
        )

        role = create_test_role(db_session, company.id, slug="t153-member-role")
        for _ in range(3):
            member_user = User(
                email=f"t153-member-{uuid.uuid4().hex[:10]}@example.test",
                display_name="T153 Member",
            )
            db_session.add(member_user)
            db_session.flush()
            create_test_member(
                db_session,
                company_id=company.id,
                user_id=member_user.id,
                role_id=role.id,
                status="active",
            )

        usage_service = UsageService(db_session, UsageRepository(db_session))
        period_start, period_end = current_month_period()
        records = usage_service.compute_for_company(
            company_id=company.id, period_start=period_start, period_end=period_end
        )
        assert len(records) == 1
        assert records[0].quantity == Decimal(3)

    def test_compute_for_company_is_idempotent_per_period(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        _subscribe_with_users_limit(
            db_session, company=company, actor=actor, limit_value=10
        )

        usage_service = UsageService(db_session, UsageRepository(db_session))
        period_start, period_end = current_month_period()

        usage_service.compute_for_company(
            company_id=company.id, period_start=period_start, period_end=period_end
        )
        usage_service.compute_for_company(
            company_id=company.id, period_start=period_start, period_end=period_end
        )

        usage_repo = UsageRepository(db_session)
        # Only "users" is a live-measurable metric in this phase (module
        # docstring) and this test only ever computes for one period, so
        # a metric_key filter alone is sufficient — comparing the SQLite
        # round-tripped (naive) period_start/period_end against the
        # original aware values would spuriously never match.
        all_records = [
            r
            for r in usage_repo.list_for_company(company.id)
            if r.metric_key == "users"
        ]
        assert len(all_records) == 1
