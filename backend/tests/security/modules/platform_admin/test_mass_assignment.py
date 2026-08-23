"""[T208] Security test: mass-assignment protection on every Platform
write schema (master prompt §11/§19 Feature-Toggle/RBAC hardening
mirror, plan.md §28 risk analysis).

Every request schema under `modules/platform_admin/schemas/` carries an
explicit field allow-list (each schema's own docstring documents this).
This proves the runtime behaviour matches: sending an extra/unprivileged
field alongside a legitimate request — `status`, `is_active`, a
client-chosen `id`, or a client-chosen `expires_at` where none is
accepted — is silently ignored by Pydantic's default `extra="ignore"`
behaviour and never reaches the persisted row. No privileged field is
settable through an unintended endpoint.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.config.settings import get_settings
from core.utils.datetime import utcnow
from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.platform_admin.models.plan import Plan
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.platform_session import PlatformSession
from modules.platform_admin.repositories.platform_rbac_repository import (
    PlatformRbacRepository,
)
from modules.platform_admin.services.platform_jwt_service import PlatformJwtService
from modules.platform_admin.services.platform_rbac_seed_service import (
    PlatformRbacSeedService,
)
from modules.platform_admin.services.support_access_service import (
    DEFAULT_GRANT_DURATION_HOURS,
)


def _make_token_with_permissions(db: Session, codes: set[str]) -> str:
    user = User(
        email=f"t208-mass-admin-{uuid.uuid4().hex[:12]}@example.test",
        display_name="T208 Mass-Assignment Admin",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    rbac_repo = PlatformRbacRepository(db)
    PlatformRbacSeedService(db, rbac_repo).seed_all()
    role = rbac_repo.create_role(
        code=f"t208-mass-role-{uuid.uuid4().hex[:10]}", name="T208 Mass Role"
    )
    rbac_repo.set_role_permissions(role.id, set(codes))
    rbac_repo.assign_role(
        platform_administrator_id=administrator.id,
        role_id=role.id,
        assigned_by=None,
        assigned_at=utcnow(),
    )
    db.commit()
    session = PlatformSession(
        platform_administrator_id=administrator.id,
        expires_at=utcnow() + timedelta(days=1),
    )
    db.add(session)
    db.flush()
    db.commit()
    return PlatformJwtService(get_settings()).create_access_token(
        platform_administrator_id=administrator.id, session_id=session.id
    )


def _make_company(db: Session, *, label: str) -> Company:
    suffix = uuid.uuid4().hex[:10]
    owner = User(
        email=f"t208-mass-owner-{label}-{suffix}@example.test",
        display_name=f"T208 Mass Owner {label}",
    )
    db.add(owner)
    db.flush()
    company = Company(
        legal_name=f"T208 Mass Co {label} {suffix}",
        slug=f"t208-mass-co-{label}-{suffix}",
        owner_id=owner.id,
        email=f"t208-mass-co-{label}-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


class TestPlanMassAssignment:
    def test_create_plan_ignores_injected_status_field_always_creates_draft(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(db_session, {"platform.plans.manage"})
        response = test_client.post(
            "/api/v1/platform/plans",
            json={
                "code": f"t208-plan-{uuid.uuid4().hex[:10]}",
                "name": "Mass Assignment Plan",
                # Privileged/unintended field — must never bypass the
                # draft-only creation invariant.
                "status": "published",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201, response.text
        assert response.json()["data"]["status"] == "draft"

    def test_update_plan_ignores_injected_status_field_outside_the_action_enum(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(db_session, {"platform.plans.manage"})
        plan = Plan(
            code=f"t208-plan2-{uuid.uuid4().hex[:10]}", name="Plan", status="draft"
        )
        db_session.add(plan)
        db_session.commit()

        response = test_client.patch(
            f"/api/v1/platform/plans/{plan.id}",
            json={
                "name": "Renamed",
                # There is no `status` field on UpdatePlanRequest — only
                # `action` may transition status, and "update" (the
                # default) never touches it.
                "status": "retired",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["status"] == "draft"
        assert response.json()["data"]["name"] == "Renamed"


class TestAdministratorMassAssignment:
    def test_create_administrator_ignores_injected_is_active_field(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(db_session, {"platform.admins.manage"})
        new_user = User(
            email=f"t208-new-admin-{uuid.uuid4().hex[:12]}@example.test",
            display_name="New",
        )
        db_session.add(new_user)
        db_session.commit()

        response = test_client.post(
            "/api/v1/platform/administrators",
            json={
                "user_id": str(new_user.id),
                # CreatePlatformAdministratorRequest carries no
                # `is_active`/role field at all — an administrator is
                # always created active regardless of what's injected.
                "is_active": False,
                "role_id": str(uuid.uuid4()),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201, response.text
        assert response.json()["data"]["is_active"] is True


class TestRoleMassAssignment:
    def test_create_role_ignores_a_client_supplied_id(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(db_session, {"platform.rbac.manage"})
        attacker_supplied_id = str(uuid.uuid4())

        response = test_client.post(
            "/api/v1/platform/roles",
            json={
                "id": attacker_supplied_id,
                "code": f"t208-role-{uuid.uuid4().hex[:10]}",
                "name": "Mass Assignment Role",
                "permission_codes": [],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["id"] != attacker_supplied_id


class TestSubscriptionMassAssignment:
    def test_assign_subscription_ignores_injected_status_field(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(
            db_session, {"platform.subscriptions.manage"}
        )
        company = _make_company(db_session, label="mass-sub")
        plan = Plan(
            code=f"t208-plan3-{uuid.uuid4().hex[:10]}", name="Plan", status="published"
        )
        db_session.add(plan)
        db_session.commit()

        response = test_client.post(
            f"/api/v1/platform/tenants/{company.id}/subscription",
            json={
                "plan_id": str(plan.id),
                "effective_date": "2026-01-01",
                # AssignSubscriptionRequest carries no `status` field —
                # a new Subscription is always created "active".
                "status": "cancelled",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["status"] == "active"


class TestEntitlementOverrideMassAssignment:
    def test_grant_override_ignores_injected_is_active_field(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(
            db_session, {"platform.entitlements.override"}
        )
        company = _make_company(db_session, label="mass-override")

        response = test_client.post(
            f"/api/v1/platform/tenants/{company.id}/entitlement-overrides",
            json={
                "capability_key": "crm",
                "reason": "Mass assignment test.",
                # GrantEntitlementOverrideRequest carries no `is_active`/
                # `revoked_at` field — a newly-granted override is always
                # active.
                "is_active": False,
                "revoked_at": "2020-01-01T00:00:00Z",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201, response.text
        assert response.json()["data"]["is_active"] is True
        assert response.json()["data"]["revoked_at"] is None


class TestSupportAccessMassAssignment:
    def test_initiate_grant_ignores_injected_expires_at_field(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(
            db_session, {"platform.support_access.initiate"}
        )
        company = _make_company(db_session, label="mass-support")

        response = test_client.post(
            f"/api/v1/platform/tenants/{company.id}/support-access",
            json={
                "reason": "Mass assignment test.",
                # InitiateSupportAccessRequest carries no `expires_at` —
                # the grant window is always server-determined
                # (DEFAULT_GRANT_DURATION_HOURS), never client-chosen.
                "expires_at": "2099-01-01T00:00:00Z",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        started_at = data["started_at"]
        expires_at = data["expires_at"]
        # Never the attacker-supplied 2099 date.
        assert not expires_at.startswith("2099")
        assert expires_at != "2099-01-01T00:00:00Z"
        # Genuinely server-computed: ~DEFAULT_GRANT_DURATION_HOURS after start.
        from datetime import datetime

        started_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        assert expires_dt - started_dt == timedelta(hours=DEFAULT_GRANT_DURATION_HOURS)
