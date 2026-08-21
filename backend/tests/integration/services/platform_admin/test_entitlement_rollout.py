"""[T127, T128] Rollout verification (plan.md §34 steps 5 and 7).

T127: existing feature-toggle rows across all five modules are preserved
byte-for-byte by the rollout (capability seeding + baseline plan
creation + bulk-assign never touch a `*_feature_flags` table).

T128: for every pre-existing tenant x capability, effective entitlement
after the rollout matches pre-rollout effective access exactly — the
go/no-go gate before enforcement (T129-T133) is activated. Before Epic
9A, only CRM had any entitlement-adjacent gate at all
(`require_crm_enabled`, driven solely by the tenant's own toggle);
Inventory/Sales/Purchase/Accounting had no module-level gate whatsoever
— access was unconditional. The baseline "Legacy/Unlimited" plan (T125)
is specifically designed to reproduce that reality exactly.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from modules.accounting.models.feature_flag import AccountingFeatureFlag
from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.companies.repositories.company_repository import CompanyRepository
from modules.crm.constants import CRM_ENABLED_FLAG_KEY
from modules.crm.models.feature_flag import CrmFeatureFlag
from modules.crm.repositories.feature_flag_repository import CrmFeatureFlagRepository
from modules.inventory.models.feature_flag import InventoryFeatureFlag
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
from modules.purchase.models.feature_flag import PurchaseFeatureFlag
from modules.sales.models.feature_flag import SalesFeatureFlag

_CAPABILITIES = ("inventory", "purchase", "sales", "accounting", "crm")


def _make_actor(db: Session) -> PlatformAdministrator:
    user = User(
        email=f"t127-actor-{uuid.uuid4().hex[:10]}@example.test",
        display_name="T127 Actor",
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
        legal_name=f"T127 Rollout Co {suffix}",
        slug=f"t127-rollout-co-{suffix}",
        owner_id=owner_id,
        email=f"t127-rollout-co-{suffix}@example.test",
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


class TestFeatureToggleRowsPreservedByteForByteByRollout:
    def test_crm_and_inventory_toggle_rows_unchanged_after_rollout(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        suffix = uuid.uuid4().hex[:10]
        company_a = _make_company(
            db_session, owner_id=actor.user_id, suffix=f"a-{suffix}"
        )
        company_b = _make_company(
            db_session, owner_id=actor.user_id, suffix=f"b-{suffix}"
        )
        company_c = _make_company(
            db_session, owner_id=actor.user_id, suffix=f"c-{suffix}"
        )

        # CRM: three distinct toggle states across three tenants.
        CrmFeatureFlagRepository(db_session).upsert(
            company_id=company_a.id, flag_key=CRM_ENABLED_FLAG_KEY, is_enabled=True
        )
        CrmFeatureFlagRepository(db_session).upsert(
            company_id=company_b.id, flag_key=CRM_ENABLED_FLAG_KEY, is_enabled=False
        )
        # company_c: deliberately no row (default-disabled).
        db_session.commit()

        # A sub-feature override on a default-rule module, to prove those
        # tables are equally untouched.
        inventory_flag = InventoryFeatureFlag(
            company_id=company_a.id,
            flag_key="inventory.product_variants",
            is_enabled=False,
        )
        db_session.add(inventory_flag)
        db_session.commit()

        company_ids = {company_a.id, company_b.id, company_c.id}

        def _snapshot():
            crm_rows = {
                (row.company_id, row.flag_key, row.is_enabled)
                for row in db_session.query(CrmFeatureFlag).all()
                if row.company_id in company_ids
            }
            inventory_rows = {
                (row.company_id, row.flag_key, row.is_enabled)
                for row in db_session.query(InventoryFeatureFlag).all()
                if row.company_id in company_ids
            }
            sales_rows = {
                (row.company_id, row.flag_key, row.is_enabled)
                for row in db_session.query(SalesFeatureFlag).all()
                if row.company_id in company_ids
            }
            purchase_rows = {
                (row.company_id, row.flag_key, row.is_enabled)
                for row in db_session.query(PurchaseFeatureFlag).all()
                if row.company_id in company_ids
            }
            accounting_rows = {
                (row.company_id, row.flag_key, row.is_enabled)
                for row in db_session.query(AccountingFeatureFlag).all()
                if row.company_id in company_ids
            }
            return crm_rows, inventory_rows, sales_rows, purchase_rows, accounting_rows

        before = _snapshot()

        rollout = _rollout_service(db_session)
        CapabilitySeedService(
            db_session, CapabilityRepository(db_session)
        ).seed_capabilities()
        plan = rollout.create_baseline_plan(actor_platform_administrator_id=actor.id)
        rollout.bulk_assign_existing_tenants(
            baseline_plan=plan, actor_platform_administrator_id=actor.id
        )

        after = _snapshot()

        assert before == after
        # Explicitly re-confirm CRM's per-tenant state specifically —
        # the row most directly at risk of an accidental rewrite.
        crm_after = {
            (row.company_id, row.is_enabled)
            for row in db_session.query(CrmFeatureFlag).all()
            if row.company_id in company_ids
        }
        assert (company_a.id, True) in crm_after
        assert (company_b.id, False) in crm_after
        assert not any(cid == company_c.id for cid, _ in crm_after)


class TestEveryExistingTenantResolvesToPriorEffectiveAccess:
    def test_effective_entitlement_matches_pre_rollout_access_for_every_capability(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        suffix = uuid.uuid4().hex[:10]
        company_crm_on = _make_company(
            db_session, owner_id=actor.user_id, suffix=f"on-{suffix}"
        )
        company_crm_off = _make_company(
            db_session, owner_id=actor.user_id, suffix=f"off-{suffix}"
        )
        company_crm_default = _make_company(
            db_session, owner_id=actor.user_id, suffix=f"def-{suffix}"
        )

        CrmFeatureFlagRepository(db_session).upsert(
            company_id=company_crm_on.id, flag_key=CRM_ENABLED_FLAG_KEY, is_enabled=True
        )
        CrmFeatureFlagRepository(db_session).upsert(
            company_id=company_crm_off.id,
            flag_key=CRM_ENABLED_FLAG_KEY,
            is_enabled=False,
        )
        db_session.commit()

        # Pre-Epic-9A reality: CRM gated solely by its own toggle;
        # Inventory/Sales/Purchase/Accounting had no gate at all (always
        # accessible).
        pre_rollout_access = {
            company_crm_on.id: {
                "crm": True,
                "inventory": True,
                "sales": True,
                "purchase": True,
                "accounting": True,
            },
            company_crm_off.id: {
                "crm": False,
                "inventory": True,
                "sales": True,
                "purchase": True,
                "accounting": True,
            },
            company_crm_default.id: {
                "crm": False,
                "inventory": True,
                "sales": True,
                "purchase": True,
                "accounting": True,
            },
        }

        rollout = _rollout_service(db_session)
        CapabilitySeedService(
            db_session, CapabilityRepository(db_session)
        ).seed_capabilities()
        plan = rollout.create_baseline_plan(actor_platform_administrator_id=actor.id)
        rollout.bulk_assign_existing_tenants(
            baseline_plan=plan, actor_platform_administrator_id=actor.id
        )

        service = _entitlement_service(db_session)
        for company_id, expected_by_capability in pre_rollout_access.items():
            for capability_key in _CAPABILITIES:
                result = service.resolve_effective_entitlement(
                    company_id=company_id, capability_key=capability_key
                )
                assert result.available == expected_by_capability[capability_key], (
                    f"{company_id}/{capability_key}: expected "
                    f"{expected_by_capability[capability_key]}, got "
                    f"{result.available} ({result.reason})"
                )
