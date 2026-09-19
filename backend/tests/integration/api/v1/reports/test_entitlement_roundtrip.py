"""T009 — Reports Capability registration and entitlement resolution.

Mirrors the CRM/Installments precedent
(``tests/integration/api/v1/installments/test_entitlement_registration.py``).
Proves T004's ``reports`` capability-catalogue entry and T006's
``ReportsModuleEnablementProvider`` registration are genuinely wired, not
just present as inert code: ``resolve_effective_entitlement(company_id,
"reports")`` round-trips without ``ValueError`` and defaults to
``available=False`` (spec §18/FR-RPT-255) when no Reports feature-flag
override row exists yet.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.repositories.capability_repository import (
    CapabilityRepository,
)
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.services.capability_seed_service import (
    CapabilitySeedService,
)
from modules.platform_admin.services.entitlement_service import (
    PlatformEntitlementService,
)
from modules.reports.repositories.feature_flag import ReportsFeatureFlagRepository
from modules.reports.services.feature_flag_service import (
    REPORTS_ENABLED_FLAG_KEY,
    ReportsFeatureFlagService,
)


def _make_actor(db: Session) -> PlatformAdministrator:
    user = User(
        email=f"t009-actor-{uuid.uuid4().hex[:10]}@example.test",
        display_name="T009 Actor",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    db.commit()
    return administrator


def _make_company(db: Session, *, owner_id: uuid.UUID, suffix: str) -> Company:
    company = Company(
        legal_name=f"T009 Reports Co {suffix}",
        slug=f"t009-reports-co-{suffix}",
        owner_id=owner_id,
        email=f"t009-reports-co-{suffix}@example.test",
        status="active",
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


def _entitlement_service(db: Session) -> PlatformEntitlementService:
    return PlatformEntitlementService(
        db=db,
        plan_repo=PlanRepository(db),
        subscription_repo=SubscriptionRepository(db),
    )


class TestReportsCapabilityRegistration:
    def test_reports_capability_is_seeded(self, db_session: Session) -> None:
        created = CapabilitySeedService(
            db_session, CapabilityRepository(db_session)
        ).seed_capabilities()
        assert created > 0

        capability = CapabilityRepository(db_session).get("reports")
        assert capability is not None
        assert capability.module == "reports"
        assert capability.grain == "module"


class TestReportsEntitlementResolution:
    def test_no_subscription_defaults_to_disabled(self, db_session: Session) -> None:
        """No Subscription and no ReportsFeatureFlag override row -> the
        Tenant Toggle alone governs, and it defaults to False
        (FR-RPT-255) — the reverse of Sales/Purchase/Inventory/Accounting's
        DefaultAlwaysEnabledModuleProvider default."""
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id, suffix="default")

        CapabilitySeedService(
            db_session, CapabilityRepository(db_session)
        ).seed_capabilities()

        service = _entitlement_service(db_session)
        result = service.resolve_effective_entitlement(
            company_id=company.id, capability_key="reports"
        )
        assert result.available is False

    def test_enabling_the_toggle_grants_entitlement(self, db_session: Session) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id, suffix="on")

        CapabilitySeedService(
            db_session, CapabilityRepository(db_session)
        ).seed_capabilities()

        ReportsFeatureFlagRepository(db_session).upsert(
            company_id=company.id,
            flag_key=REPORTS_ENABLED_FLAG_KEY,
            is_enabled=True,
        )
        db_session.commit()

        service = _entitlement_service(db_session)
        result = service.resolve_effective_entitlement(
            company_id=company.id, capability_key="reports"
        )
        assert result.available is True

    def test_toggle_off_after_being_on_is_reflected_immediately(
        self, db_session: Session
    ) -> None:
        """FR-9A-170: resolved fresh every time, never cached."""
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id, suffix="flip")

        CapabilitySeedService(
            db_session, CapabilityRepository(db_session)
        ).seed_capabilities()

        flag_repo = ReportsFeatureFlagRepository(db_session)
        flag_repo.upsert(
            company_id=company.id, flag_key=REPORTS_ENABLED_FLAG_KEY, is_enabled=True
        )
        db_session.commit()

        service = _entitlement_service(db_session)
        assert (
            service.resolve_effective_entitlement(
                company_id=company.id, capability_key="reports"
            ).available
            is True
        )

        flag_repo.upsert(
            company_id=company.id, flag_key=REPORTS_ENABLED_FLAG_KEY, is_enabled=False
        )
        db_session.commit()

        assert (
            service.resolve_effective_entitlement(
                company_id=company.id, capability_key="reports"
            ).available
            is False
        )

    def test_feature_flag_service_defaults_disabled_without_repo_row(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id, suffix="svc")

        service = ReportsFeatureFlagService(
            flag_repo=ReportsFeatureFlagRepository(db_session)
        )
        assert service.is_enabled(company.id) is False
