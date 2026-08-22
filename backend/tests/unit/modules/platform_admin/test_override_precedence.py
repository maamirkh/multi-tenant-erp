"""[T148] Unit tests: entitlement override precedence and expiry —
Epic 9A Phase 11 (FR-9A-171/172, T146/T147).

Covers:
  - An active override wins over a denying Plan (precedence).
  - `has_active_override()` returns False and auto-reverts (audited) a
    row whose `expires_at` has passed, even though `is_active` is still
    stored as `true` — the resolver never trusts the stale flag.
  - A future `expires_at` (or none — permanent) keeps the override active.
  - `grant()` rejects a duplicate active override.
  - `revoke()` deactivates (audited) and frees the slot for a new grant.
  - `revoke()` on a missing/inactive override raises NotFoundException.
"""

from __future__ import annotations

import time
import uuid
from datetime import date, timedelta
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from core.exceptions.base import NotFoundException
from core.utils.datetime import utcnow
from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.companies.repositories.company_repository import CompanyRepository
from modules.platform_admin.exceptions import EntitlementOverrideAlreadyActiveError
from modules.platform_admin.models.plan import Plan
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.repositories.override_repository import OverrideRepository
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.repositories.quota_repository import QuotaRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.services.entitlement_service import (
    PlatformEntitlementService,
)
from modules.platform_admin.services.override_service import OverrideService
from modules.platform_admin.services.platform_audit_service import PlatformAuditService
from modules.platform_admin.services.quota_service import QuotaService
from modules.platform_admin.services.subscription_service import SubscriptionService


def _make_actor(db: Session) -> PlatformAdministrator:
    user = User(
        email=f"t148-actor-{uuid.uuid4().hex[:10]}@example.com",
        display_name="T148 Actor",
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
        legal_name=f"T148 Override Co {suffix}",
        slug=f"t148-override-co-{suffix}",
        owner_id=owner_id,
        email=f"t148-override-co-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    return company


def _subscribe_denying(
    db: Session, *, company: Company, actor: PlatformAdministrator
) -> None:
    """Subscribes *company* to a Plan that explicitly denies 'inventory' —
    the ceiling this override must be shown to override."""
    suffix = uuid.uuid4().hex[:10]
    plan = Plan(
        code=f"t148-plan-{suffix}", name="T148 Denying Plan", status="published"
    )
    db.add(plan)
    db.flush()
    PlanRepository(db).set_capabilities(plan.id, {"inventory": False})
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


def _override_service(db: Session) -> OverrideService:
    return OverrideService(
        db=db,
        repo=OverrideRepository(db),
        audit=PlatformAuditService(db, PlatformAuditRepository(db)),
    )


class TestOverridePrecedence:
    def test_active_override_wins_over_denying_plan(self, db_session: Session) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        _subscribe_denying(db_session, company=company, actor=actor)

        override_service = _override_service(db_session)
        override_service.grant(
            company_id=company.id,
            capability_key="inventory",
            reason="T148 precedence test — temporary access.",
            actor_platform_administrator_id=actor.id,
        )

        entitlement_service = PlatformEntitlementService(
            db=db_session,
            plan_repo=PlanRepository(db_session),
            subscription_repo=SubscriptionRepository(db_session),
            override_checker=override_service,
        )
        result = entitlement_service.resolve_effective_entitlement(
            company_id=company.id, capability_key="inventory"
        )
        assert result.available is True
        assert result.reason == "override"

    def test_no_override_falls_through_to_denying_plan(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)
        _subscribe_denying(db_session, company=company, actor=actor)

        override_service = _override_service(db_session)
        entitlement_service = PlatformEntitlementService(
            db=db_session,
            plan_repo=PlanRepository(db_session),
            subscription_repo=SubscriptionRepository(db_session),
            override_checker=override_service,
        )
        result = entitlement_service.resolve_effective_entitlement(
            company_id=company.id, capability_key="inventory"
        )
        assert result.available is False
        assert result.reason == "plan_ceiling"


class TestOverrideExpiryAtReadTime:
    def test_expired_override_is_treated_as_inactive_and_auto_reverted(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)

        override_service = _override_service(db_session)
        override = override_service.grant(
            company_id=company.id,
            capability_key="inventory",
            reason="T148 expiry test.",
            actor_platform_administrator_id=actor.id,
            expires_at=utcnow() + timedelta(milliseconds=50),
        )
        # Let real time pass so expires_at genuinely falls into the past
        # relative to now() while still satisfying the model's own
        # `expires_at > granted_at` CHECK constraint (it was granted a
        # moment earlier, well before this future expiry).
        time.sleep(0.2)

        assert override_service.has_active_override(company.id, "inventory") is False

        db_session.refresh(override)
        assert override.is_active is False
        assert override.revoked_at is not None

        events, total = PlatformAuditRepository(db_session).list_filtered(
            target_id=override.id, action="entitlement_override.auto_revert_expired"
        )
        assert total == 1
        assert (
            events[0].reason is not None and "Automatic reversion" in events[0].reason
        )

    def test_future_expiry_keeps_override_active(self, db_session: Session) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)

        override_service = _override_service(db_session)
        override_service.grant(
            company_id=company.id,
            capability_key="inventory",
            reason="T148 future-expiry test.",
            actor_platform_administrator_id=actor.id,
            expires_at=utcnow() + timedelta(days=30),
        )

        assert override_service.has_active_override(company.id, "inventory") is True

    def test_permanent_override_never_expires(self, db_session: Session) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)

        override_service = _override_service(db_session)
        override_service.grant(
            company_id=company.id,
            capability_key="inventory",
            reason="T148 permanent override test.",
            actor_platform_administrator_id=actor.id,
            expires_at=None,
        )

        assert override_service.has_active_override(company.id, "inventory") is True


class TestOverrideGrantRevokeLifecycle:
    def test_grant_rejects_duplicate_active_override(self, db_session: Session) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)

        override_service = _override_service(db_session)
        override_service.grant(
            company_id=company.id,
            capability_key="inventory",
            reason="First grant.",
            actor_platform_administrator_id=actor.id,
        )

        with pytest.raises(EntitlementOverrideAlreadyActiveError):
            override_service.grant(
                company_id=company.id,
                capability_key="inventory",
                reason="Second grant — should be rejected.",
                actor_platform_administrator_id=actor.id,
            )

    def test_revoke_frees_the_slot_for_a_new_grant(self, db_session: Session) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id)

        override_service = _override_service(db_session)
        first = override_service.grant(
            company_id=company.id,
            capability_key="inventory",
            reason="First grant.",
            actor_platform_administrator_id=actor.id,
        )
        override_service.revoke(
            override_id=first.id, actor_platform_administrator_id=actor.id
        )

        events, total = PlatformAuditRepository(db_session).list_filtered(
            target_id=first.id, action="entitlement_override.revoke"
        )
        assert total == 1

        second = override_service.grant(
            company_id=company.id,
            capability_key="inventory",
            reason="Second grant after revoke.",
            actor_platform_administrator_id=actor.id,
        )
        assert second.id != first.id
        assert override_service.has_active_override(company.id, "inventory") is True

    def test_revoke_missing_override_raises_not_found(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        override_service = _override_service(db_session)

        with pytest.raises(NotFoundException):
            override_service.revoke(
                override_id=uuid.uuid4(), actor_platform_administrator_id=actor.id
            )
