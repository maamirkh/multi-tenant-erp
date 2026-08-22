"""[T144] Unit tests for `PlatformEntitlementService.is_within_plan_ceiling()`
— the mutation-point secondary guard (FR-9A-185, plan.md §14).

**Reachability note, discovered during Phase 10 implementation and
verified directly via a real HTTP call (not assumed)**: for Inventory,
Sales, and Purchase, Phase 9's mount-level `require_capability_entitled
(<module>)` dependency already denies the *entire* module the moment a
Plan denies its module-grain capability — before the request ever
reaches the endpoint body where this secondary guard's own call lives.
The observed HTTP response in that exact scenario carries the *primary*
gate's error shape (`details: {"capability_key", "reason": "plan_ceiling"}`,
no `flag_key`), not the secondary guard's own (`details: {"capability_key",
"flag_key"}`) — confirming the secondary guard's own code path inside
`update_feature_flag` is currently unreachable for these three modules'
own toggle-mutation endpoints specifically. This exactly parallels Phase
9's own discovered finding that `require_crm_enabled` is unreachable-for-
denial downstream of `require_capability_entitled("crm")`.

This is not a defect: plan.md §14 itself states "removing it [the
secondary guard] would not create a runtime bypass" — its purpose is
explicitly defense-in-depth / fail-fast, not coverage of a scenario the
primary gate misses. `is_within_plan_ceiling()` is still real, correct,
callable code (used by the router exactly as plan.md §14 specifies, and
would become live again if the router's dependency composition ever
changes) — proven directly here rather than only implicitly via an HTTP
path where a different layer happens to intercept first.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.platform_admin.models.plan import Plan
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.services.entitlement_service import (
    PlatformEntitlementService,
)


def _make_actor(db: Session) -> PlatformAdministrator:
    user = User(
        email=f"t144-actor-{uuid.uuid4().hex[:10]}@example.com",
        display_name="T144 Actor",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    return administrator


def _make_company(db: Session, *, owner_id) -> Company:
    suffix = uuid.uuid4().hex[:10]
    company = Company(
        legal_name=f"T144 Ceiling Co {suffix}",
        slug=f"t144-ceiling-co-{suffix}",
        owner_id=owner_id,
        email=f"t144-ceiling-co-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    return company


def _subscribe(
    db: Session, *, company: Company, actor: PlatformAdministrator, capability_map: dict
) -> None:
    suffix = uuid.uuid4().hex[:10]
    plan = Plan(
        code=f"t144-plan-{suffix}", name="T144 Ceiling Plan", status="published"
    )
    db.add(plan)
    db.flush()
    PlanRepository(db).set_capabilities(plan.id, capability_map)
    db.commit()

    from modules.companies.repositories.company_repository import CompanyRepository
    from modules.platform_admin.repositories.platform_audit_repository import (
        PlatformAuditRepository,
    )
    from modules.platform_admin.repositories.quota_repository import QuotaRepository
    from modules.platform_admin.services.platform_audit_service import (
        PlatformAuditService,
    )
    from modules.platform_admin.services.quota_service import QuotaService
    from modules.platform_admin.services.subscription_service import (
        SubscriptionService,
    )

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


def _service(db: Session) -> PlatformEntitlementService:
    return PlatformEntitlementService(
        db=db,
        plan_repo=PlanRepository(db),
        subscription_repo=SubscriptionRepository(db),
    )


class TestIsWithinPlanCeiling:
    def test_denying_plan_returns_false(self, db_session: Session) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        _subscribe(
            db_session,
            company=company,
            actor=actor,
            capability_map={"inventory": False},
        )

        result = _service(db_session).is_within_plan_ceiling(
            company_id=company.id, capability_key="inventory"
        )
        assert result is False

    def test_allowing_plan_returns_true(self, db_session: Session) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        _subscribe(
            db_session, company=company, actor=actor, capability_map={"inventory": True}
        )

        result = _service(db_session).is_within_plan_ceiling(
            company_id=company.id, capability_key="inventory"
        )
        assert result is True

    def test_no_subscription_defers_and_returns_true(self, db_session: Session) -> None:
        """Matches resolve_effective_entitlement's own "no Subscription
        -> ceiling inapplicable" rule exactly — never blocks an enable
        attempt just because no Plan has been assigned yet."""
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)

        result = _service(db_session).is_within_plan_ceiling(
            company_id=company.id, capability_key="inventory"
        )
        assert result is True

    def test_capability_absent_from_map_returns_false(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        _subscribe(db_session, company=company, actor=actor, capability_map={})

        result = _service(db_session).is_within_plan_ceiling(
            company_id=company.id, capability_key="inventory"
        )
        assert result is False
