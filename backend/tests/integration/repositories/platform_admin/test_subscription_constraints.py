"""[T116] One-active-subscription-per-company is enforced by a real
PostgreSQL partial unique index (``uq_subscriptions_company_active``,
migration 058) — not merely by application code.

Not meaningfully testable on SQLite (no partial-unique-index support),
so this test deliberately bypasses the shared ``db_session`` SQLite
fixture and connects directly to the real PostgreSQL database
(``core.database.session.SessionLocal``, the same ``DATABASE_URL`` the
live application uses), inserting rows directly at the ORM/session
level to prove the *database itself* rejects a second concurrently-
active Subscription row — mirroring T094's real-Postgres pattern.

All test data is created and torn down against the real database within
this test — nothing is left behind.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.exc import IntegrityError

from core.database.session import SessionLocal
from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.platform_admin.models.plan import Plan
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.subscription import Subscription


class TestOneActiveSubscriptionPerCompanyDbEnforced:
    def test_second_active_subscription_violates_partial_unique_index(self) -> None:
        session = SessionLocal()
        suffix = uuid.uuid4().hex[:10]
        user_id: uuid.UUID | None = None
        admin_id: uuid.UUID | None = None
        company_id: uuid.UUID | None = None
        plan_id: uuid.UUID | None = None
        subscription_ids: list[uuid.UUID] = []
        try:
            user = User(
                email=f"t116-actor-{suffix}@example.test",
                display_name="T116 Actor",
            )
            session.add(user)
            session.flush()
            user_id = user.id

            administrator = PlatformAdministrator(user_id=user.id, is_active=True)
            session.add(administrator)
            session.flush()
            admin_id = administrator.id

            company = Company(
                legal_name=f"T116 Constraint Co {suffix}",
                slug=f"t116-constraint-co-{suffix}",
                owner_id=user.id,
                email=f"t116-constraint-co-{suffix}@example.test",
                status="active",
            )
            session.add(company)
            session.flush()
            company_id = company.id

            plan = Plan(
                code=f"t116-plan-{suffix}",
                name="T116 Constraint Plan",
                status="published",
                is_commercially_available=True,
            )
            session.add(plan)
            session.flush()
            plan_id = plan.id
            session.commit()

            first = Subscription(
                company_id=company_id,
                plan_id=plan_id,
                status="active",
                effective_date=date.today(),
                actor_id=admin_id,
            )
            session.add(first)
            session.commit()
            subscription_ids.append(first.id)

            second = Subscription(
                company_id=company_id,
                plan_id=plan_id,
                status="active",
                effective_date=date.today(),
                actor_id=admin_id,
            )
            session.add(second)
            try:
                session.commit()
                # If this line is reached, the DB failed to enforce the
                # invariant — clean up the unexpected extra row too.
                subscription_ids.append(second.id)
                raise AssertionError(
                    "Expected IntegrityError from uq_subscriptions_company_active"
                )
            except IntegrityError as exc:
                session.rollback()
                assert "uq_subscriptions_company_active" in str(exc.orig)

            # A second ENDED subscription for the same company does NOT
            # violate the partial index (it only covers status='active'),
            # proving this is a targeted partial constraint, not a
            # blanket one-row-per-company rule.
            third = Subscription(
                company_id=company_id,
                plan_id=plan_id,
                status="ended",
                effective_date=date.today(),
                actor_id=admin_id,
            )
            session.add(third)
            session.commit()
            subscription_ids.append(third.id)
        finally:
            for sub_id in subscription_ids:
                session.execute(
                    Subscription.__table__.delete().where(Subscription.id == sub_id)
                )
            if plan_id is not None:
                session.execute(Plan.__table__.delete().where(Plan.id == plan_id))
            if company_id is not None:
                session.execute(
                    Company.__table__.delete().where(Company.id == company_id)
                )
            if admin_id is not None:
                session.execute(
                    PlatformAdministrator.__table__.delete().where(
                        PlatformAdministrator.id == admin_id
                    )
                )
            if user_id is not None:
                session.execute(User.__table__.delete().where(User.id == user_id))
            session.commit()
            session.close()
