"""[T109] [FR-9A-181] Unit tests for `QuotaService.resolve()` — the five
usage states, the override→plan_quota→unlimited resolution order, NULL
= unlimited semantics, and enforcement-style pass-through.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from modules.platform_admin.models.plan import Plan
from modules.platform_admin.repositories.quota_repository import QuotaRepository
from modules.platform_admin.services.quota_service import QuotaService, QuotaState


def _make_plan(db: Session) -> Plan:
    suffix = uuid.uuid4().hex[:10]
    plan = Plan(
        code=f"quota-test-plan-{suffix}", name="Quota Test Plan", status="draft"
    )
    db.add(plan)
    db.flush()
    return plan


def _ensure_definition(
    repo: QuotaRepository, db: Session, *, key: str, enforcement_style: str = "hard"
) -> None:
    if repo.get_definition(key) is None:
        repo.create_definition(
            key=key,
            display_name=key.title(),
            unit="count",
            enforcement_style=enforcement_style,
        )
        db.commit()


class TestNoLimitResolvesToUnlimited:
    def test_no_plan_quota_row_and_no_override_is_unlimited(
        self, db_session: Session
    ) -> None:
        repo = QuotaRepository(db_session)
        key = f"quota-{uuid.uuid4().hex[:8]}"
        _ensure_definition(repo, db_session, key=key)
        plan = _make_plan(db_session)
        db_session.commit()

        result = QuotaService(repo).resolve(
            company_id=uuid.uuid4(),
            plan_id=plan.id,
            quota_key=key,
            current_usage=Decimal(5),
        )
        assert result.state == QuotaState.unlimited
        assert result.limit is None

    def test_explicit_null_plan_quota_limit_is_unlimited_not_a_number(
        self, db_session: Session
    ) -> None:
        repo = QuotaRepository(db_session)
        key = f"quota-{uuid.uuid4().hex[:8]}"
        _ensure_definition(repo, db_session, key=key)
        plan = _make_plan(db_session)
        repo.set_plan_quota(plan.id, key, None)
        db_session.commit()

        result = QuotaService(repo).resolve(
            company_id=uuid.uuid4(),
            plan_id=plan.id,
            quota_key=key,
            current_usage=Decimal(999999),
        )
        assert result.state == QuotaState.unlimited
        assert result.limit is None

    def test_no_plan_id_at_all_is_unlimited(self, db_session: Session) -> None:
        repo = QuotaRepository(db_session)
        key = f"quota-{uuid.uuid4().hex[:8]}"
        _ensure_definition(repo, db_session, key=key)
        db_session.commit()

        result = QuotaService(repo).resolve(
            company_id=uuid.uuid4(),
            plan_id=None,
            quota_key=key,
            current_usage=Decimal(5),
        )
        assert result.state == QuotaState.unlimited


class TestOkApproachingReachedStates:
    def test_usage_well_below_limit_is_ok(self, db_session: Session) -> None:
        repo = QuotaRepository(db_session)
        key = f"quota-{uuid.uuid4().hex[:8]}"
        _ensure_definition(repo, db_session, key=key)
        plan = _make_plan(db_session)
        repo.set_plan_quota(plan.id, key, Decimal(100))
        db_session.commit()

        result = QuotaService(repo).resolve(
            company_id=uuid.uuid4(),
            plan_id=plan.id,
            quota_key=key,
            current_usage=Decimal(50),
        )
        assert result.state == QuotaState.ok
        assert result.limit == Decimal(100)

    def test_usage_at_80_percent_is_approaching(self, db_session: Session) -> None:
        repo = QuotaRepository(db_session)
        key = f"quota-{uuid.uuid4().hex[:8]}"
        _ensure_definition(repo, db_session, key=key)
        plan = _make_plan(db_session)
        repo.set_plan_quota(plan.id, key, Decimal(100))
        db_session.commit()

        result = QuotaService(repo).resolve(
            company_id=uuid.uuid4(),
            plan_id=plan.id,
            quota_key=key,
            current_usage=Decimal(80),
        )
        assert result.state == QuotaState.approaching

    def test_usage_just_below_approaching_threshold_is_still_ok(
        self, db_session: Session
    ) -> None:
        repo = QuotaRepository(db_session)
        key = f"quota-{uuid.uuid4().hex[:8]}"
        _ensure_definition(repo, db_session, key=key)
        plan = _make_plan(db_session)
        repo.set_plan_quota(plan.id, key, Decimal(100))
        db_session.commit()

        result = QuotaService(repo).resolve(
            company_id=uuid.uuid4(),
            plan_id=plan.id,
            quota_key=key,
            current_usage=Decimal(79),
        )
        assert result.state == QuotaState.ok

    def test_usage_at_limit_is_reached(self, db_session: Session) -> None:
        repo = QuotaRepository(db_session)
        key = f"quota-{uuid.uuid4().hex[:8]}"
        _ensure_definition(repo, db_session, key=key)
        plan = _make_plan(db_session)
        repo.set_plan_quota(plan.id, key, Decimal(100))
        db_session.commit()

        result = QuotaService(repo).resolve(
            company_id=uuid.uuid4(),
            plan_id=plan.id,
            quota_key=key,
            current_usage=Decimal(100),
        )
        assert result.state == QuotaState.reached

    def test_usage_over_limit_is_reached(self, db_session: Session) -> None:
        repo = QuotaRepository(db_session)
        key = f"quota-{uuid.uuid4().hex[:8]}"
        _ensure_definition(repo, db_session, key=key)
        plan = _make_plan(db_session)
        repo.set_plan_quota(plan.id, key, Decimal(100))
        db_session.commit()

        result = QuotaService(repo).resolve(
            company_id=uuid.uuid4(),
            plan_id=plan.id,
            quota_key=key,
            current_usage=Decimal(150),
        )
        assert result.state == QuotaState.reached


class TestUnavailableState:
    def test_no_current_usage_supplied_is_unavailable_never_zero(
        self, db_session: Session
    ) -> None:
        repo = QuotaRepository(db_session)
        key = f"quota-{uuid.uuid4().hex[:8]}"
        _ensure_definition(repo, db_session, key=key)
        plan = _make_plan(db_session)
        repo.set_plan_quota(plan.id, key, Decimal(100))
        db_session.commit()

        result = QuotaService(repo).resolve(
            company_id=uuid.uuid4(), plan_id=plan.id, quota_key=key, current_usage=None
        )
        assert result.state == QuotaState.unavailable
        assert result.current_usage is None
        # A limited quota's limit is still reported even when usage is
        # unavailable — only the usage comparison is skipped.
        assert result.limit == Decimal(100)


class TestOverrideTakesPrecedenceOverPlanQuota:
    def test_active_override_limit_wins_over_plan_quota(
        self, db_session: Session
    ) -> None:
        repo = QuotaRepository(db_session)
        key = f"quota-{uuid.uuid4().hex[:8]}"
        _ensure_definition(repo, db_session, key=key)
        plan = _make_plan(db_session)
        repo.set_plan_quota(plan.id, key, Decimal(100))
        company_id = uuid.uuid4()
        repo.create_override(
            company_id=company_id,
            quota_key=key,
            override_limit=Decimal(500),
            reason="test override",
            actor_id=uuid.uuid4(),
            granted_at=datetime.now(UTC),
        )
        db_session.commit()

        result = QuotaService(repo).resolve(
            company_id=company_id,
            plan_id=plan.id,
            quota_key=key,
            current_usage=Decimal(200),
        )
        # 200 < 500 -> ok, even though 200 > the plan's own 100-limit.
        assert result.state == QuotaState.ok
        assert result.limit == Decimal(500)

    def test_active_override_with_null_limit_is_unlimited_even_with_a_plan_limit(
        self, db_session: Session
    ) -> None:
        """An override row existing with override_limit=NULL is a
        *different* condition from no override existing at all — it must
        NOT fall through to the plan's own (finite) limit."""
        repo = QuotaRepository(db_session)
        key = f"quota-{uuid.uuid4().hex[:8]}"
        _ensure_definition(repo, db_session, key=key)
        plan = _make_plan(db_session)
        repo.set_plan_quota(plan.id, key, Decimal(10))
        company_id = uuid.uuid4()
        repo.create_override(
            company_id=company_id,
            quota_key=key,
            override_limit=None,
            reason="explicit unlimited override",
            actor_id=uuid.uuid4(),
            granted_at=datetime.now(UTC),
        )
        db_session.commit()

        result = QuotaService(repo).resolve(
            company_id=company_id,
            plan_id=plan.id,
            quota_key=key,
            current_usage=Decimal(999999),
        )
        assert result.state == QuotaState.unlimited
        assert result.limit is None

    def test_inactive_override_does_not_apply(self, db_session: Session) -> None:
        repo = QuotaRepository(db_session)
        key = f"quota-{uuid.uuid4().hex[:8]}"
        _ensure_definition(repo, db_session, key=key)
        plan = _make_plan(db_session)
        repo.set_plan_quota(plan.id, key, Decimal(100))
        company_id = uuid.uuid4()
        override = repo.create_override(
            company_id=company_id,
            quota_key=key,
            override_limit=Decimal(500),
            reason="test override",
            actor_id=uuid.uuid4(),
            granted_at=datetime.now(UTC),
        )
        override.is_active = False
        db_session.commit()

        result = QuotaService(repo).resolve(
            company_id=company_id,
            plan_id=plan.id,
            quota_key=key,
            current_usage=Decimal(150),
        )
        # The inactive override is ignored -> falls back to the plan's
        # 100-limit -> 150 exceeds it -> reached.
        assert result.state == QuotaState.reached
        assert result.limit == Decimal(100)


class TestEnforcementStyleAndEntitlementIndependence:
    def test_enforcement_style_is_passed_through_from_the_definition(
        self, db_session: Session
    ) -> None:
        repo = QuotaRepository(db_session)
        key = f"quota-{uuid.uuid4().hex[:8]}"
        _ensure_definition(repo, db_session, key=key, enforcement_style="informational")
        plan = _make_plan(db_session)
        repo.set_plan_quota(plan.id, key, Decimal(10))
        db_session.commit()

        result = QuotaService(repo).resolve(
            company_id=uuid.uuid4(),
            plan_id=plan.id,
            quota_key=key,
            current_usage=Decimal(20),
        )
        # Even though usage exceeds the limit (reached), the enforcement
        # style is reported as-declared (informational) — resolution
        # itself never blocks; enforcement is a separate concern applied
        # by the caller per the declared style (BR-9A-030).
        assert result.state == QuotaState.reached
        assert result.enforcement_style == "informational"

    def test_each_declared_enforcement_style_is_reported_verbatim(
        self, db_session: Session
    ) -> None:
        repo = QuotaRepository(db_session)
        service = QuotaService(repo)
        plan = _make_plan(db_session)
        for style in ("hard", "soft", "informational"):
            key = f"quota-{style}-{uuid.uuid4().hex[:8]}"
            _ensure_definition(repo, db_session, key=key, enforcement_style=style)
            repo.set_plan_quota(plan.id, key, Decimal(10))
            db_session.commit()

            result = service.resolve(
                company_id=uuid.uuid4(),
                plan_id=plan.id,
                quota_key=key,
                current_usage=Decimal(1),
            )
            assert result.enforcement_style == style

    def test_unknown_quota_key_reports_no_enforcement_style(
        self, db_session: Session
    ) -> None:
        """Entitlement (capability access) and quota are independent
        concepts (BR-9A-030 scope) — resolving a quota key with no
        catalogue entry doesn't raise, it just can't report a style."""
        repo = QuotaRepository(db_session)
        plan = _make_plan(db_session)
        db_session.commit()

        result = QuotaService(repo).resolve(
            company_id=uuid.uuid4(),
            plan_id=plan.id,
            quota_key="genuinely-nonexistent-quota-key",
            current_usage=Decimal(1),
        )
        assert result.enforcement_style is None
        assert result.state == QuotaState.unlimited
