"""[Phase 2] Installments Capability registration and entitlement
resolution — mirrors the Epic 9A CRM precedent
(``test_entitlement_rollout.py``'s
``TestEveryExistingTenantResolvesToPriorEffectiveAccess``).

Covers tasks.md T041: a Platform Admin can grant/toggle the
``installments`` capability and it resolves via
``PlatformEntitlementService.resolve_effective_entitlement()`` through
the unmodified entitlement resolution path — proving T032's
``InstallmentsModuleEnablementProvider`` registration and T033's
``installments`` capability-catalogue entry are both genuinely wired,
not just present as inert code.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.companies.repositories.company_repository import CompanyRepository
from modules.installments.repositories.feature_flag import (
    InstallmentsFeatureFlagRepository,
)
from modules.installments.services.feature_flag_service import (
    INSTALLMENTS_ENABLED_FLAG_KEY,
)
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.repositories.capability_repository import (
    CapabilityRepository,
)
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.repositories.quota_repository import QuotaRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.services.capability_seed_service import (
    CapabilitySeedService,
)
from modules.platform_admin.services.entitlement_service import (
    PlatformEntitlementService,
)
from modules.platform_admin.services.plan_service import PlanService
from modules.platform_admin.services.platform_audit_service import PlatformAuditService
from modules.platform_admin.services.quota_service import QuotaService
from modules.platform_admin.services.rollout_service import RolloutService
from modules.platform_admin.services.subscription_service import SubscriptionService


def _make_actor(db: Session) -> PlatformAdministrator:
    user = User(
        email=f"t041-actor-{uuid.uuid4().hex[:10]}@example.test",
        display_name="T041 Actor",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    db.commit()
    return administrator


def _make_company(db: Session, *, owner_id, suffix: str) -> Company:
    company = Company(
        legal_name=f"T041 Installments Co {suffix}",
        slug=f"t041-installments-co-{suffix}",
        owner_id=owner_id,
        email=f"t041-installments-co-{suffix}@example.test",
        status="active",
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


def _rollout_service(db: Session) -> RolloutService:
    audit = PlatformAuditService(db, PlatformAuditRepository(db))
    return RolloutService(
        db=db,
        capability_repo=CapabilityRepository(db),
        quota_repo=QuotaRepository(db),
        plan_repo=PlanRepository(db),
        plan_service=PlanService(db=db, repo=PlanRepository(db), audit=audit),
        company_repo=CompanyRepository(db),
        subscription_service=SubscriptionService(
            db=db,
            repo=SubscriptionRepository(db),
            company_repo=CompanyRepository(db),
            quota_service=QuotaService(QuotaRepository(db)),
            audit=audit,
        ),
    )


def _entitlement_service(db: Session) -> PlatformEntitlementService:
    return PlatformEntitlementService(
        db=db,
        plan_repo=PlanRepository(db),
        subscription_repo=SubscriptionRepository(db),
    )


class TestInstallmentsCapabilityRegistration:
    def test_installments_capability_is_seeded(self, db_session: Session) -> None:
        created = CapabilitySeedService(
            db_session, CapabilityRepository(db_session)
        ).seed_capabilities()
        assert created > 0

        capability = CapabilityRepository(db_session).get("installments")
        assert capability is not None
        assert capability.module == "installments"
        assert capability.grain == "module"


class TestInstallmentsEntitlementResolution:
    def test_disabled_toggle_denies_installments_within_plan_ceiling(
        self, db_session: Session
    ) -> None:
        """A Plan ceiling that includes 'installments' still defers to
        the tenant's own toggle — same two-layer resolution CRM already
        proves (Plan x Toggle)."""
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id, suffix="off")

        CapabilitySeedService(
            db_session, CapabilityRepository(db_session)
        ).seed_capabilities()
        rollout = _rollout_service(db_session)
        plan = rollout.create_baseline_plan(actor_platform_administrator_id=actor.id)
        rollout.bulk_assign_existing_tenants(
            baseline_plan=plan, actor_platform_administrator_id=actor.id
        )

        # No InstallmentsFeatureFlag row yet -> defaults to disabled
        # (InstallmentsFeatureFlagService.is_enabled()'s documented default).
        service = _entitlement_service(db_session)
        result = service.resolve_effective_entitlement(
            company_id=company.id, capability_key="installments"
        )
        assert result.available is False

    def test_enabled_toggle_grants_installments_within_plan_ceiling(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, owner_id=actor.user_id, suffix="on")

        CapabilitySeedService(
            db_session, CapabilityRepository(db_session)
        ).seed_capabilities()
        rollout = _rollout_service(db_session)
        plan = rollout.create_baseline_plan(actor_platform_administrator_id=actor.id)
        rollout.bulk_assign_existing_tenants(
            baseline_plan=plan, actor_platform_administrator_id=actor.id
        )

        InstallmentsFeatureFlagRepository(db_session).upsert(
            company_id=company.id,
            flag_key=INSTALLMENTS_ENABLED_FLAG_KEY,
            is_enabled=True,
        )
        db_session.commit()

        service = _entitlement_service(db_session)
        result = service.resolve_effective_entitlement(
            company_id=company.id, capability_key="installments"
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
        rollout = _rollout_service(db_session)
        plan = rollout.create_baseline_plan(actor_platform_administrator_id=actor.id)
        rollout.bulk_assign_existing_tenants(
            baseline_plan=plan, actor_platform_administrator_id=actor.id
        )

        flag_repo = InstallmentsFeatureFlagRepository(db_session)
        flag_repo.upsert(
            company_id=company.id,
            flag_key=INSTALLMENTS_ENABLED_FLAG_KEY,
            is_enabled=True,
        )
        db_session.commit()

        service = _entitlement_service(db_session)
        assert (
            service.resolve_effective_entitlement(
                company_id=company.id, capability_key="installments"
            ).available
            is True
        )

        flag_repo.upsert(
            company_id=company.id,
            flag_key=INSTALLMENTS_ENABLED_FLAG_KEY,
            is_enabled=False,
        )
        db_session.commit()

        assert (
            service.resolve_effective_entitlement(
                company_id=company.id, capability_key="installments"
            ).available
            is False
        )
