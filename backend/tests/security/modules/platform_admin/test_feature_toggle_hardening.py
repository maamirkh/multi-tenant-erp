"""[T142, T143, T144] Existing Feature-Toggle Mutation Hardening — Epic 9A
Phase 10 (plan.md §14, FR-9A-183/184/185).

T142: an ordinary active member cannot mutate feature-toggle state on
Inventory, Sales, or Purchase; an owner/admin can.
T143: Accounting and CRM's already-correct gates are unchanged (regression
guard — this phase modifies neither module's source).
T144: even a tenant owner (who holds the new *.settings.manage permission)
cannot enable a toggle beyond the Plan ceiling, proving T144's literal
acceptance text ("even a tenant owner's enable attempt is rejected with a
clear error").

**Reachability note**: for these three modules, this observable HTTP
behaviour is produced by Phase 9's *primary* mount-level
`require_capability_entitled(<module>)` dependency (verified directly —
the response body carries that gate's error shape, not the mutation-
point secondary guard's own), since a Plan denying the whole module
already blocks every request to it before the endpoint body runs. The
secondary guard's own logic (`PlatformEntitlementService.
is_within_plan_ceiling()`, plan.md §14) is separately proven directly in
`test_plan_ceiling_secondary_guard.py` — plan.md itself states removing
this secondary guard "would not create a runtime bypass" (defense-in-
depth intent, not coverage of a scenario the primary gate misses).

Real HTTP throughout — the point-of-use guarantee this phase exists to
prove is not meaningful as a resolver-level unit test alone.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.companies.models.company import Company
from modules.companies.repositories.company_repository import CompanyRepository
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

# (module, endpoint path suffix, a valid flag_key for that module)
_HARDENED_MODULES: tuple[tuple[str, str, str], ...] = (
    ("inventory", "inventory", "inventory.product_master"),
    ("sales", "sales", "sales.approval_required_so"),
    ("purchase", "purchase", "purchase.approval_required_pr"),
)


def _login_member(
    test_client: TestClient, db: Session, *, role_slug: str
) -> tuple[Company, dict[str, str]]:
    email = f"t142-{role_slug}-{uuid.uuid4().hex[:10]}@example.com"
    password = "FeatureToggleHardening@123"
    user, _ = create_test_user(db, email=email, password=password)

    suffix = uuid.uuid4().hex[:10]
    company = Company(
        legal_name=f"T142 {role_slug} Co {suffix}",
        slug=f"t142-{role_slug}-co-{suffix}",
        owner_id=user.id,
        email=f"t142-{role_slug}-co-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()

    seed_system_roles(db, company.id)
    create_member_with_role(
        db, company_id=company.id, user_id=user.id, role_slug=role_slug
    )
    db.commit()

    login = test_client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    return company, {"Authorization": f"Bearer {token}"}


def _login_non_owner_member(
    test_client: TestClient, db: Session, *, role_slug: str
) -> tuple[Company, dict[str, str]]:
    """Like ``_login_member``, but the returned user is genuinely NOT
    ``company.owner_id`` — required for any check (like CRM's
    ``require_admin_or_above()``) that consults the company's owner
    field directly rather than only the CompanyMember role rank."""
    suffix = uuid.uuid4().hex[:10]
    owner_email = f"t142-owner-{suffix}@example.com"
    owner_user, _ = create_test_user(db, email=owner_email, password="Owner@12345")

    company = Company(
        legal_name=f"T142 non-owner {role_slug} Co {suffix}",
        slug=f"t142-non-owner-{role_slug}-co-{suffix}",
        owner_id=owner_user.id,
        email=f"t142-non-owner-{role_slug}-co-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    seed_system_roles(db, company.id)

    member_email = f"t142-{role_slug}-{suffix}@example.com"
    member_password = "FeatureToggleHardening@123"
    member_user, _ = create_test_user(db, email=member_email, password=member_password)
    create_member_with_role(
        db, company_id=company.id, user_id=member_user.id, role_slug=role_slug
    )
    db.commit()

    login = test_client.post(
        "/api/v1/auth/login",
        json={"email": member_email, "password": member_password},
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    return company, {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("module,path,flag_key", _HARDENED_MODULES)
class TestOrdinaryMemberCannotMutateFeatureState:
    def test_viewer_role_denied(
        self,
        test_client: TestClient,
        db_session: Session,
        module: str,
        path: str,
        flag_key: str,
    ) -> None:
        company, headers = _login_member(test_client, db_session, role_slug="viewer")

        response = test_client.put(
            f"/api/v1/companies/{company.id}/{path}/feature-flags/{flag_key}",
            json={"is_enabled": True},
            headers=headers,
        )
        assert response.status_code == 403, response.text


@pytest.mark.parametrize("module,path,flag_key", _HARDENED_MODULES)
class TestOwnerAdminCanMutateFeatureState:
    @pytest.mark.parametrize("role_slug", ["owner", "admin"])
    def test_owner_and_admin_succeed(
        self,
        test_client: TestClient,
        db_session: Session,
        module: str,
        path: str,
        flag_key: str,
        role_slug: str,
    ) -> None:
        company, headers = _login_member(test_client, db_session, role_slug=role_slug)

        response = test_client.put(
            f"/api/v1/companies/{company.id}/{path}/feature-flags/{flag_key}",
            json={"is_enabled": True},
            headers=headers,
        )
        assert response.status_code == 200, response.text


class TestAccountingAndCrmRegressionUnchanged:
    """[T143] Neither module's source is touched by this phase — prove
    their pre-existing gates still behave exactly as before."""

    def test_accounting_toggle_still_requires_approvalworkflow_manage(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company, headers = _login_member(test_client, db_session, role_slug="viewer")

        response = test_client.put(
            f"/api/v1/companies/{company.id}/accounting/feature-flags/"
            "accounting.multicurrency.enabled",
            json={"is_enabled": True},
            headers=headers,
        )
        assert response.status_code == 403, response.text

    def test_accounting_toggle_succeeds_for_owner(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company, headers = _login_member(test_client, db_session, role_slug="owner")

        response = test_client.put(
            f"/api/v1/companies/{company.id}/accounting/feature-flags/"
            "accounting.multicurrency.enabled",
            json={"is_enabled": True},
            headers=headers,
        )
        assert response.status_code == 200, response.text

    def test_crm_enable_still_requires_admin_or_above(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        # require_admin_or_above() checks company.owner_id directly, not
        # only the CompanyMember role rank — this member must genuinely
        # NOT be the company's owner for this to be a meaningful check.
        company, headers = _login_non_owner_member(
            test_client, db_session, role_slug="viewer"
        )

        response = test_client.post(
            f"/api/v1/companies/{company.id}/crm/enable",
            headers=headers,
        )
        assert response.status_code == 403, response.text

    def test_crm_enable_succeeds_for_owner(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company, headers = _login_member(test_client, db_session, role_slug="owner")

        response = test_client.post(
            f"/api/v1/companies/{company.id}/crm/enable",
            headers=headers,
        )
        assert response.status_code == 200, response.text


def _make_actor(db: Session) -> PlatformAdministrator:
    from modules.auth.models.user import User

    user = User(
        email=f"t144-actor-{uuid.uuid4().hex[:10]}@example.com",
        display_name="T144 Actor",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    db.commit()
    return administrator


def _subscribe_denying(db: Session, *, company: Company, capability_key: str) -> None:
    actor = _make_actor(db)
    suffix = uuid.uuid4().hex[:10]
    plan = Plan(
        code=f"t144-deny-plan-{suffix}", name="T144 Denying Plan", status="published"
    )
    db.add(plan)
    db.flush()
    PlanRepository(db).set_capabilities(plan.id, {capability_key: False})
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


@pytest.mark.parametrize("module,path,flag_key", _HARDENED_MODULES)
class TestCannotEnableToggleBeyondPlanCeiling:
    def test_owner_enable_rejected_when_plan_denies_capability(
        self,
        test_client: TestClient,
        db_session: Session,
        module: str,
        path: str,
        flag_key: str,
    ) -> None:
        # Owner holds *.settings.manage (the permission gate passes) —
        # the rejection below must come from the entitlement ceiling,
        # not the permission check (in practice, Phase 9's primary
        # mount-level gate — see this file's module docstring).
        company, headers = _login_member(test_client, db_session, role_slug="owner")
        _subscribe_denying(db_session, company=company, capability_key=module)

        response = test_client.put(
            f"/api/v1/companies/{company.id}/{path}/feature-flags/{flag_key}",
            json={"is_enabled": True},
            headers=headers,
        )
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "CAPABILITY_NOT_ENTITLED"
