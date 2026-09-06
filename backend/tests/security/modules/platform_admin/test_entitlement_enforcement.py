"""[T134, T135, T136] **Gate D** — Plan ceiling enforced at point of use,
across all five business modules (plan.md §13.1 Correction 1, spec.md
§17.2).

Real HTTP on the tenant side (a genuine login, a genuine access token,
the actual mounted `require_capability_entitled(...)` dependency) — this
is the point-of-use enforcement Gate D exists to prove, not a resolver
unit test (T121 already covers the resolver's own matrix directly). Plan/
Subscription setup on the Platform Admin side uses direct service calls
(the same convention Phase 7/8's own security tests use), since the
surface under test here is the tenant-facing module endpoint, not the
Platform Admin management endpoints (already covered by their own tests).
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.companies.models.company import Company
from modules.companies.repositories.company_repository import CompanyRepository
from modules.crm.constants import CRM_ENABLED_FLAG_KEY
from modules.crm.repositories.feature_flag_repository import CrmFeatureFlagRepository
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
from modules.platform_admin.services.platform_audit_service import PlatformAuditService
from modules.platform_admin.services.quota_service import QuotaService
from modules.platform_admin.services.subscription_service import SubscriptionService
from tests.fixtures.auth_fixtures import create_test_user
from tests.fixtures.users_roles_fixtures import (
    create_member_with_role,
    seed_system_roles,
)

# (capability_key, path suffix under /api/v1/companies/{id}/...) — one
# minimal, low-dependency GET endpoint per module, each requiring only
# require_authenticated beyond the router-mount-level gates under test.
_MODULE_ENDPOINTS: tuple[tuple[str, str], ...] = (
    ("inventory", "inventory/feature-flags"),
    ("purchase", "purchase/feature-flags"),
    ("sales", "sales/feature-flags"),
    ("accounting", "accounting/feature-flags"),
    ("crm", "crm/my-permissions"),
)


def _make_actor(db: Session) -> PlatformAdministrator:
    from modules.auth.models.user import User

    user = User(
        email=f"t134-actor-{uuid.uuid4().hex[:10]}@example.test",
        display_name="T134 Actor",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    db.commit()
    return administrator


def _make_plan(db: Session, *, capability_key: str, allowed: bool) -> Plan:
    suffix = uuid.uuid4().hex[:10]
    plan = Plan(
        code=f"t134-plan-{suffix}", name="T134 Enforcement Plan", status="published"
    )
    db.add(plan)
    db.flush()
    PlanRepository(db).set_capabilities(plan.id, {capability_key: allowed})
    db.commit()
    return plan


def _subscription_service(db: Session) -> SubscriptionService:
    return SubscriptionService(
        db=db,
        repo=SubscriptionRepository(db),
        company_repo=CompanyRepository(db),
        quota_service=QuotaService(QuotaRepository(db)),
        audit=PlatformAuditService(db, PlatformAuditRepository(db)),
    )


def _subscribe(
    db: Session, *, company: Company, plan: Plan, actor: PlatformAdministrator
):
    return _subscription_service(db).assign_or_change(
        company_id=company.id,
        plan_id=plan.id,
        effective_date=date.today(),
        actor_platform_administrator_id=actor.id,
        reason="T134-136 Gate D enforcement test.",
    )


def _login_tenant(
    test_client: TestClient, db: Session, *, capability_key: str
) -> tuple[Company, dict[str, str]]:
    email = f"t134-{capability_key}-{uuid.uuid4().hex[:10]}@example.com"
    password = "GateDEnforcement@123"
    user, _ = create_test_user(db, email=email, password=password)

    suffix = uuid.uuid4().hex[:10]
    company = Company(
        legal_name=f"T134 {capability_key} Co {suffix}",
        slug=f"t134-{capability_key}-co-{suffix}",
        owner_id=user.id,
        email=f"t134-{capability_key}-co-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()

    seed_system_roles(db, company.id)
    create_member_with_role(
        db, company_id=company.id, user_id=user.id, role_slug="owner"
    )
    db.commit()

    login = test_client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    return company, {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("capability_key,endpoint_suffix", _MODULE_ENDPOINTS)
class TestPlanAllowsAndTogglePermitsIsAllowed:
    def test_plan_allowed_toggle_enabled_returns_200(
        self,
        test_client: TestClient,
        db_session: Session,
        capability_key: str,
        endpoint_suffix: str,
    ) -> None:
        actor = _make_actor(db_session)
        company, headers = _login_tenant(
            test_client, db_session, capability_key=capability_key
        )
        plan = _make_plan(db_session, capability_key=capability_key, allowed=True)
        _subscribe(db_session, company=company, plan=plan, actor=actor)
        if capability_key == "crm":
            CrmFeatureFlagRepository(db_session).upsert(
                company_id=company.id, flag_key=CRM_ENABLED_FLAG_KEY, is_enabled=True
            )
            db_session.commit()

        response = test_client.get(
            f"/api/v1/companies/{company.id}/{endpoint_suffix}", headers=headers
        )
        assert response.status_code == 200, response.text


@pytest.mark.parametrize("capability_key,endpoint_suffix", _MODULE_ENDPOINTS)
class TestPlanDeniesIsUnavailableRegardlessOfToggle:
    def test_plan_denied_toggle_enabled_returns_403(
        self,
        test_client: TestClient,
        db_session: Session,
        capability_key: str,
        endpoint_suffix: str,
    ) -> None:
        actor = _make_actor(db_session)
        company, headers = _login_tenant(
            test_client, db_session, capability_key=capability_key
        )
        plan = _make_plan(db_session, capability_key=capability_key, allowed=False)
        _subscribe(db_session, company=company, plan=plan, actor=actor)
        if capability_key == "crm":
            # Toggle enabled — proves the Plan ceiling denies first,
            # regardless of the tenant's own toggle preference.
            CrmFeatureFlagRepository(db_session).upsert(
                company_id=company.id, flag_key=CRM_ENABLED_FLAG_KEY, is_enabled=True
            )
            db_session.commit()

        response = test_client.get(
            f"/api/v1/companies/{company.id}/{endpoint_suffix}", headers=headers
        )
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "CAPABILITY_NOT_ENTITLED"


class TestDowngradeDeniesAccessWithoutTouchingTheToggle:
    """[T135] The Correction-1 bypass regression guard: a Plan downgrade
    takes effect on the tenant's very next request, with the tenant's
    stored toggle value left completely untouched."""

    def test_downgrade_denies_next_request_and_toggle_row_stays_true(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company, headers = _login_tenant(test_client, db_session, capability_key="crm")

        allowing_plan = _make_plan(db_session, capability_key="crm", allowed=True)
        _subscribe(db_session, company=company, plan=allowing_plan, actor=actor)
        CrmFeatureFlagRepository(db_session).upsert(
            company_id=company.id, flag_key=CRM_ENABLED_FLAG_KEY, is_enabled=True
        )
        db_session.commit()

        before = test_client.get(
            f"/api/v1/companies/{company.id}/crm/my-permissions", headers=headers
        )
        assert before.status_code == 200, before.text

        # Platform Admin moves the tenant to a plan that no longer grants
        # crm — no toggle table is touched by this step.
        denying_plan = _make_plan(db_session, capability_key="crm", allowed=False)
        _subscribe(db_session, company=company, plan=denying_plan, actor=actor)

        after = test_client.get(
            f"/api/v1/companies/{company.id}/crm/my-permissions", headers=headers
        )
        assert after.status_code == 403, after.text
        assert after.json()["error"]["code"] == "CAPABILITY_NOT_ENTITLED"

        stored = CrmFeatureFlagRepository(db_session).get_by_key(
            company_id=company.id, flag_key=CRM_ENABLED_FLAG_KEY
        )
        assert stored is not None
        assert stored.is_enabled is True


class TestReUpgradeRestoresAccessAtPreservedPreference:
    """[T136] Re-upgrading resumes access automatically, with no toggle
    mutation at any point in the whole downgrade -> re-upgrade cycle."""

    def test_re_upgrade_restores_access_without_any_toggle_mutation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company, headers = _login_tenant(test_client, db_session, capability_key="crm")

        allowing_plan = _make_plan(db_session, capability_key="crm", allowed=True)
        _subscribe(db_session, company=company, plan=allowing_plan, actor=actor)
        CrmFeatureFlagRepository(db_session).upsert(
            company_id=company.id, flag_key=CRM_ENABLED_FLAG_KEY, is_enabled=True
        )
        db_session.commit()

        denying_plan = _make_plan(db_session, capability_key="crm", allowed=False)
        _subscribe(db_session, company=company, plan=denying_plan, actor=actor)
        denied = test_client.get(
            f"/api/v1/companies/{company.id}/crm/my-permissions", headers=headers
        )
        assert denied.status_code == 403, denied.text

        # Re-upgrade back to an allowing plan — no toggle mutation at any
        # point in this cycle.
        re_upgrade_plan = _make_plan(db_session, capability_key="crm", allowed=True)
        _subscribe(db_session, company=company, plan=re_upgrade_plan, actor=actor)

        restored = test_client.get(
            f"/api/v1/companies/{company.id}/crm/my-permissions", headers=headers
        )
        assert restored.status_code == 200, restored.text

        stored = CrmFeatureFlagRepository(db_session).get_by_key(
            company_id=company.id, flag_key=CRM_ENABLED_FLAG_KEY
        )
        assert stored is not None
        assert stored.is_enabled is True
