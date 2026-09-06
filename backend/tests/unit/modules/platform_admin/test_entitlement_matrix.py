"""[T121] Unit tests: the full entitlement matrix (spec.md §17.2).

Covers every row of the resolution table:
    Allowed   + Enabled  -> Available
    Allowed   + Disabled -> Unavailable (tenant's own choice)
    Not Allowed + Enabled  -> Unavailable (ceiling)
    Not Allowed + Disabled -> Unavailable
    Not Allowed, active Override -> Available for the override's duration
    Moved to a plan lacking a previously-entitled module -> Unavailable
        immediately; the tenant's toggle setting is preserved, not deleted.

CRM (the one module with a genuine on/off toggle) is used for every
Toggle-sensitive row; Inventory (a default-rule module, plan.md §40) is
used to prove the four toggle-less modules can never be denied by their
(nonexistent) module-grain toggle.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.crm.constants import CRM_ENABLED_FLAG_KEY
from modules.crm.repositories.feature_flag_repository import CrmFeatureFlagRepository
from modules.platform_admin.models.plan import Plan
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.subscription import Subscription
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.services.entitlement_service import (
    PlatformEntitlementService,
)


def _make_actor(db: Session) -> PlatformAdministrator:
    user = User(
        email=f"t121-actor-{uuid.uuid4().hex[:10]}@example.test",
        display_name="T121 Actor",
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
        legal_name=f"T121 Entitlement Co {suffix}",
        slug=f"t121-entitlement-co-{suffix}",
        owner_id=owner_id,
        email=f"t121-entitlement-co-{suffix}@example.test",
        status="active",
    )
    db.add(company)
    db.flush()
    return company


def _make_plan(db: Session, *, capability_map: dict[str, bool]) -> Plan:
    suffix = uuid.uuid4().hex[:10]
    plan = Plan(code=f"t121-plan-{suffix}", name="T121 Plan", status="published")
    db.add(plan)
    db.flush()
    PlanRepository(db).set_capabilities(plan.id, capability_map)
    return plan


def _subscribe(
    db: Session, *, company: Company, plan: Plan, actor: PlatformAdministrator
) -> Subscription:
    subscription = SubscriptionRepository(db).create(
        company_id=company.id,
        plan_id=plan.id,
        status="active",
        effective_date=date.today(),
        actor_id=actor.id,
    )
    db.commit()
    return subscription


def _set_crm_toggle(db: Session, *, company_id, enabled: bool) -> None:
    CrmFeatureFlagRepository(db).upsert(
        company_id=company_id, flag_key=CRM_ENABLED_FLAG_KEY, is_enabled=enabled
    )
    db.commit()


def _service(db: Session) -> PlatformEntitlementService:
    return PlatformEntitlementService(
        db=db,
        plan_repo=PlanRepository(db),
        subscription_repo=SubscriptionRepository(db),
    )


class TestAllowedAndEnabledIsAvailable:
    def test_crm_allowed_and_toggle_enabled_is_available(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        plan = _make_plan(db_session, capability_map={"crm": True})
        _subscribe(db_session, company=company, plan=plan, actor=actor)
        _set_crm_toggle(db_session, company_id=company.id, enabled=True)

        result = _service(db_session).resolve_effective_entitlement(
            company_id=company.id, capability_key="crm"
        )
        assert result.available is True
        assert result.reason == "plan_and_toggle"


class TestAllowedAndDisabledIsUnavailable:
    def test_crm_allowed_and_toggle_disabled_is_unavailable(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        plan = _make_plan(db_session, capability_map={"crm": True})
        _subscribe(db_session, company=company, plan=plan, actor=actor)
        _set_crm_toggle(db_session, company_id=company.id, enabled=False)

        result = _service(db_session).resolve_effective_entitlement(
            company_id=company.id, capability_key="crm"
        )
        assert result.available is False
        assert result.reason == "tenant_toggle_disabled"

    def test_crm_allowed_with_no_toggle_row_at_all_defaults_disabled(
        self, db_session: Session
    ) -> None:
        """CRM defaults to disabled with no override row (unlike the
        four default-rule modules, per CrmFeatureFlagService's own
        documented default)."""
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        plan = _make_plan(db_session, capability_map={"crm": True})
        _subscribe(db_session, company=company, plan=plan, actor=actor)

        result = _service(db_session).resolve_effective_entitlement(
            company_id=company.id, capability_key="crm"
        )
        assert result.available is False
        assert result.reason == "tenant_toggle_disabled"


class TestNotAllowedIsAlwaysUnavailableRegardlessOfToggle:
    def test_crm_not_allowed_and_toggle_enabled_is_unavailable_ceiling(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        plan = _make_plan(db_session, capability_map={"crm": False})
        _subscribe(db_session, company=company, plan=plan, actor=actor)
        _set_crm_toggle(db_session, company_id=company.id, enabled=True)

        result = _service(db_session).resolve_effective_entitlement(
            company_id=company.id, capability_key="crm"
        )
        assert result.available is False
        assert result.reason == "plan_ceiling"

    def test_crm_not_allowed_and_toggle_disabled_is_unavailable(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        plan = _make_plan(db_session, capability_map={"crm": False})
        _subscribe(db_session, company=company, plan=plan, actor=actor)
        _set_crm_toggle(db_session, company_id=company.id, enabled=False)

        result = _service(db_session).resolve_effective_entitlement(
            company_id=company.id, capability_key="crm"
        )
        assert result.available is False
        assert result.reason == "plan_ceiling"

    def test_capability_absent_from_plan_capability_map_is_unavailable(
        self, db_session: Session
    ) -> None:
        """A capability key never written to `plan_capabilities` for this
        Plan behaves identically to an explicit `allowed=False` row."""
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        plan = _make_plan(db_session, capability_map={})
        _subscribe(db_session, company=company, plan=plan, actor=actor)

        result = _service(db_session).resolve_effective_entitlement(
            company_id=company.id, capability_key="crm"
        )
        assert result.available is False
        assert result.reason == "plan_ceiling"


class TestNoActiveSubscriptionDefersToToggleOnly:
    """No Subscription at all — the ceiling from §17.2 has not (yet) come
    into effect for this tenant (pre-rollout, or a brand-new signup never
    assigned a plan). Backward-compatibility requirement (plan.md §34/
    §33.1, "must not instantly change existing tenant access"): this must
    reproduce pre-Epic-9A behaviour exactly, never a blanket denial —
    verified directly against a real regression this exact design choice
    fixes (every pre-existing module's own API test suite, which creates
    companies with no Subscription, would otherwise 403 on every request)."""

    def test_no_subscription_crm_toggle_disabled_is_unavailable(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)

        result = _service(db_session).resolve_effective_entitlement(
            company_id=company.id, capability_key="crm"
        )
        assert result.available is False
        assert result.reason == "no_subscription_ceiling_inapplicable"

    def test_no_subscription_crm_toggle_enabled_is_available(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        _set_crm_toggle(db_session, company_id=company.id, enabled=True)

        result = _service(db_session).resolve_effective_entitlement(
            company_id=company.id, capability_key="crm"
        )
        assert result.available is True
        assert result.reason == "no_subscription_ceiling_inapplicable"

    def test_no_subscription_default_rule_module_is_always_available(
        self, db_session: Session
    ) -> None:
        """Inventory/Sales/Purchase/Accounting have no module-grain
        toggle at all — with no Subscription either, access is
        unconditional, exactly reproducing their pre-Epic-9A reality."""
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)

        result = _service(db_session).resolve_effective_entitlement(
            company_id=company.id, capability_key="inventory"
        )
        assert result.available is True
        assert result.reason == "no_subscription_ceiling_inapplicable"


class TestActiveOverrideWinsOverADenyingPlan:
    def test_override_checker_makes_a_denied_capability_available(
        self, db_session: Session
    ) -> None:
        """Phase 9 exposes the seam (T120's module docstring); this test
        exercises it directly with a stub, since the real
        `EntitlementOverride` model is Phase 11's scope (T145)."""
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        plan = _make_plan(db_session, capability_map={"crm": False})
        _subscribe(db_session, company=company, plan=plan, actor=actor)

        class _AlwaysOverride:
            def has_active_override(self, company_id, capability_key) -> bool:
                return True

        service = PlatformEntitlementService(
            db=db_session,
            plan_repo=PlanRepository(db_session),
            subscription_repo=SubscriptionRepository(db_session),
            override_checker=_AlwaysOverride(),
        )
        result = service.resolve_effective_entitlement(
            company_id=company.id, capability_key="crm"
        )
        assert result.available is True
        assert result.reason == "override"

    def test_with_no_override_checker_injected_ceiling_still_governs(
        self, db_session: Session
    ) -> None:
        """Phase 9's documented gap: without Phase 11's real override
        wiring, the ceiling is never bypassed."""
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        plan = _make_plan(db_session, capability_map={"crm": False})
        _subscribe(db_session, company=company, plan=plan, actor=actor)

        result = _service(db_session).resolve_effective_entitlement(
            company_id=company.id, capability_key="crm"
        )
        assert result.available is False
        assert result.reason == "plan_ceiling"


class TestDefaultRuleModulesCannotBeDeniedByToggle:
    """Inventory/Sales/Purchase/Accounting have no module-grain master
    toggle (plan.md §40) — their Tenant Toggle is always enabled, so the
    Plan ceiling is the only thing that can deny them."""

    def test_inventory_allowed_is_available_with_no_toggle_row_anywhere(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        plan = _make_plan(db_session, capability_map={"inventory": True})
        _subscribe(db_session, company=company, plan=plan, actor=actor)

        result = _service(db_session).resolve_effective_entitlement(
            company_id=company.id, capability_key="inventory"
        )
        assert result.available is True
        assert result.reason == "plan_and_toggle"

    def test_inventory_not_allowed_is_unavailable_ceiling(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        plan = _make_plan(db_session, capability_map={"inventory": False})
        _subscribe(db_session, company=company, plan=plan, actor=actor)

        result = _service(db_session).resolve_effective_entitlement(
            company_id=company.id, capability_key="inventory"
        )
        assert result.available is False
        assert result.reason == "plan_ceiling"


class TestMovedToPlanLackingPreviouslyEntitledModuleTogglePreserved:
    def test_downgrade_denies_access_and_never_touches_the_stored_toggle(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        allowing_plan = _make_plan(db_session, capability_map={"crm": True})
        denying_plan = _make_plan(db_session, capability_map={"crm": False})
        _subscribe(db_session, company=company, plan=allowing_plan, actor=actor)
        _set_crm_toggle(db_session, company_id=company.id, enabled=True)

        before = _service(db_session).resolve_effective_entitlement(
            company_id=company.id, capability_key="crm"
        )
        assert before.available is True

        # Move the tenant to a plan that no longer grants crm — no toggle
        # table is touched by this step.
        SubscriptionRepository(db_session).end(
            SubscriptionRepository(db_session).get_active_for_company(company.id),
            ended_at=datetime.now(UTC),
        )
        _subscribe(db_session, company=company, plan=denying_plan, actor=actor)

        after = _service(db_session).resolve_effective_entitlement(
            company_id=company.id, capability_key="crm"
        )
        assert after.available is False
        assert after.reason == "plan_ceiling"

        # The tenant's toggle preference is preserved exactly as it was —
        # never rewritten by the subscription change.
        stored = CrmFeatureFlagRepository(db_session).get_by_key(
            company_id=company.id, flag_key=CRM_ENABLED_FLAG_KEY
        )
        assert stored is not None
        assert stored.is_enabled is True

        # And re-upgrading resumes access automatically, at the preserved
        # preference, with no toggle mutation at any point.
        SubscriptionRepository(db_session).end(
            SubscriptionRepository(db_session).get_active_for_company(company.id),
            ended_at=datetime.now(UTC),
        )
        _subscribe(db_session, company=company, plan=allowing_plan, actor=actor)
        restored = _service(db_session).resolve_effective_entitlement(
            company_id=company.id, capability_key="crm"
        )
        assert restored.available is True
        assert restored.reason == "plan_and_toggle"
        stored_after_restore = CrmFeatureFlagRepository(db_session).get_by_key(
            company_id=company.id, flag_key=CRM_ENABLED_FLAG_KEY
        )
        assert stored_after_restore is not None
        assert stored_after_restore.is_enabled is True
