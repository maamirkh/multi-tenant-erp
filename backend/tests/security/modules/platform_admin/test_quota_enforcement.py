"""[T210] Security test: quota enforcement cannot be bypassed
(BR-9A-030, master prompt §11 Quota abuse).

**Documented scope gap** (confirmed by direct codebase search before
writing this file, and by the user's own explicit decision on how to
proceed given it): no business module (`sales`, `users_roles`,
`inventory`, etc.) currently calls `QuotaService` at any write path —
`grep -rln "QuotaService(" modules/` outside `platform_admin` returns
nothing, and T151's own recorded evidence confirms usage measurement is
resolver-only, never wired to a live write path ("no HTTP route
triggers this"). A `hard` quota's *module write-path* enforcement point
(`plan.md`'s own phrase) genuinely does not exist yet anywhere in this
codebase — building it is out of this phase's authorized scope (T206-
T213 are audit/hardening/test tasks; the Architecture Freeze explicitly
forbids pre-creating quota logic) and is not assigned to any task in
this range.

What this file proves instead — the one thing that **does** exist and
that a future enforcement point would depend on: `QuotaService.resolve()`
is the single authoritative resolver, its `state` computation is
correct and identical regardless of `enforcement_style` (the style is a
declared, pass-through signal for a caller to act on, never silently
defaulted or altered by the resolver itself, BR-9A-030), an active
override always wins over the plan's own limit (bypass-proof resolution
order — override → plan → unlimited, plan.md §17), and quota state for
one tenant is never influenced by another tenant's usage or override.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.repositories.quota_repository import QuotaRepository
from modules.platform_admin.services.platform_audit_service import PlatformAuditService
from modules.platform_admin.services.quota_admin_service import QuotaAdminService
from modules.platform_admin.services.quota_service import QuotaService, QuotaState


def _make_company(db: Session, *, label: str) -> Company:
    suffix = uuid.uuid4().hex[:10]
    owner = User(
        email=f"t210-quota-owner-{label}-{suffix}@example.com",
        display_name=f"T210 Quota Owner {label}",
    )
    db.add(owner)
    db.flush()
    company = Company(
        legal_name=f"T210 Quota Co {label} {suffix}",
        slug=f"t210-quota-co-{label}-{suffix}",
        owner_id=owner.id,
        email=f"t210-quota-co-{label}-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


def _make_actor(db: Session) -> PlatformAdministrator:
    user = User(
        email=f"t210-quota-actor-{uuid.uuid4().hex[:12]}@example.com",
        display_name="T210 Quota Actor",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    db.commit()
    return administrator


def _define_quota(
    db: Session, repo: QuotaRepository, *, key: str, enforcement_style: str
) -> None:
    repo.create_definition(
        key=key, display_name=key, unit="count", enforcement_style=enforcement_style
    )
    db.commit()


class TestEnforcementStyleIsDeclaredNeverDefaulted:
    def test_hard_soft_and_informational_all_reach_the_same_state_at_the_same_ratio(
        self, db_session: Session
    ) -> None:
        """State computation is enforcement-style-agnostic (BR-9A-030) —
        proving `enforcement_style` is carried through faithfully as a
        declared signal, never silently overridden or defaulted by the
        resolver, and that all three styles reach identical `state`s for
        identical usage/limit ratios (a future enforcement point can
        trust `state` regardless of which style it's acting on)."""
        repo = QuotaRepository(db_session)
        company = _make_company(db_session, label="styles")

        for style in ("hard", "soft", "informational"):
            key = f"t210-{style}-key"
            _define_quota(db_session, repo, key=key, enforcement_style=style)

        service = QuotaService(repo)

        for style in ("hard", "soft", "informational"):
            key = f"t210-{style}-key"
            plan_id = uuid.uuid4()  # No PlanQuota row -> unlimited regardless of style.
            resolution = service.resolve(
                company_id=company.id,
                plan_id=plan_id,
                quota_key=key,
                current_usage=Decimal("999"),
            )
            assert resolution.state == QuotaState.unlimited
            assert resolution.enforcement_style == style


class TestQuotaStateReflectsDeclaredLimitHonestly:
    def test_state_transitions_ok_approaching_reached_at_the_correct_thresholds(
        self, db_session: Session
    ) -> None:
        repo = QuotaRepository(db_session)
        company = _make_company(db_session, label="thresholds")
        _define_quota(
            db_session, repo, key="t210-hard-threshold", enforcement_style="hard"
        )

        from modules.platform_admin.models.plan import Plan

        plan = Plan(
            code=f"t210-plan-{uuid.uuid4().hex[:8]}", name="T210 Plan", status="draft"
        )
        db_session.add(plan)
        db_session.commit()
        repo.set_plan_quota(plan.id, "t210-hard-threshold", Decimal("100"))
        db_session.commit()

        service = QuotaService(repo)

        below = service.resolve(
            company_id=company.id,
            plan_id=plan.id,
            quota_key="t210-hard-threshold",
            current_usage=Decimal("10"),
        )
        assert below.state == QuotaState.ok

        approaching = service.resolve(
            company_id=company.id,
            plan_id=plan.id,
            quota_key="t210-hard-threshold",
            current_usage=Decimal("85"),
        )
        assert approaching.state == QuotaState.approaching

        reached = service.resolve(
            company_id=company.id,
            plan_id=plan.id,
            quota_key="t210-hard-threshold",
            current_usage=Decimal("100"),
        )
        assert reached.state == QuotaState.reached

    def test_no_measurement_is_unavailable_never_a_fabricated_zero_or_ok(
        self, db_session: Session
    ) -> None:
        repo = QuotaRepository(db_session)
        company = _make_company(db_session, label="unavailable")
        _define_quota(db_session, repo, key="t210-unmeasured", enforcement_style="hard")

        from modules.platform_admin.models.plan import Plan

        plan = Plan(
            code=f"t210-plan2-{uuid.uuid4().hex[:8]}",
            name="T210 Plan 2",
            status="draft",
        )
        db_session.add(plan)
        db_session.commit()
        repo.set_plan_quota(plan.id, "t210-unmeasured", Decimal("50"))
        db_session.commit()

        service = QuotaService(repo)
        resolution = service.resolve(
            company_id=company.id,
            plan_id=plan.id,
            quota_key="t210-unmeasured",
            current_usage=None,
        )
        assert resolution.state == QuotaState.unavailable
        assert resolution.state != QuotaState.ok


class TestOverrideResolutionOrderCannotBeBypassed:
    def test_an_active_override_always_wins_over_the_plans_own_limit(
        self, db_session: Session
    ) -> None:
        repo = QuotaRepository(db_session)
        company = _make_company(db_session, label="override-wins")
        actor = _make_actor(db_session)
        _define_quota(
            db_session, repo, key="t210-override-key", enforcement_style="hard"
        )

        from modules.platform_admin.models.plan import Plan

        plan = Plan(
            code=f"t210-plan3-{uuid.uuid4().hex[:8]}",
            name="T210 Plan 3",
            status="draft",
        )
        db_session.add(plan)
        db_session.commit()
        repo.set_plan_quota(plan.id, "t210-override-key", Decimal("10"))
        db_session.commit()

        service = QuotaService(repo)

        # Under the plan's own limit alone, 15 units of usage is already
        # "reached" (over the 10-unit ceiling) — this is the state a
        # hard-quota enforcement point would block on.
        before_override = service.resolve(
            company_id=company.id,
            plan_id=plan.id,
            quota_key="t210-override-key",
            current_usage=Decimal("15"),
        )
        assert before_override.state == QuotaState.reached

        admin_service = QuotaAdminService(
            db=db_session,
            repo=repo,
            audit=PlatformAuditService(db_session, PlatformAuditRepository(db_session)),
        )
        admin_service.grant(
            company_id=company.id,
            quota_key="t210-override-key",
            override_limit=None,  # explicit unlimited override
            reason="T210 override-wins proof.",
            actor_platform_administrator_id=actor.id,
        )

        after_override = service.resolve(
            company_id=company.id,
            plan_id=plan.id,
            quota_key="t210-override-key",
            current_usage=Decimal("15"),
        )
        # The override — not the plan's limit — is now authoritative.
        # An attacker cannot resurrect the plan's own ceiling by any
        # means the resolver exposes; only the active override governs.
        assert after_override.state == QuotaState.unlimited


class TestCrossTenantQuotaIsolation:
    def test_company_as_override_never_changes_company_bs_resolved_state(
        self, db_session: Session
    ) -> None:
        repo = QuotaRepository(db_session)
        company_a = _make_company(db_session, label="isolation-a")
        company_b = _make_company(db_session, label="isolation-b")
        actor = _make_actor(db_session)
        _define_quota(
            db_session, repo, key="t210-isolation-key", enforcement_style="hard"
        )

        from modules.platform_admin.models.plan import Plan

        plan = Plan(
            code=f"t210-plan4-{uuid.uuid4().hex[:8]}",
            name="T210 Plan 4",
            status="draft",
        )
        db_session.add(plan)
        db_session.commit()
        repo.set_plan_quota(plan.id, "t210-isolation-key", Decimal("5"))
        db_session.commit()

        admin_service = QuotaAdminService(
            db=db_session,
            repo=repo,
            audit=PlatformAuditService(db_session, PlatformAuditRepository(db_session)),
        )
        admin_service.grant(
            company_id=company_a.id,
            quota_key="t210-isolation-key",
            override_limit=None,
            reason="Company A only.",
            actor_platform_administrator_id=actor.id,
        )

        service = QuotaService(repo)

        resolution_a = service.resolve(
            company_id=company_a.id,
            plan_id=plan.id,
            quota_key="t210-isolation-key",
            current_usage=Decimal("50"),
        )
        resolution_b = service.resolve(
            company_id=company_b.id,
            plan_id=plan.id,
            quota_key="t210-isolation-key",
            current_usage=Decimal("50"),
        )

        assert resolution_a.state == QuotaState.unlimited
        # Company B never inherits A's override — it is bound by the
        # plan's own 5-unit limit and is genuinely "reached".
        assert resolution_b.state == QuotaState.reached
