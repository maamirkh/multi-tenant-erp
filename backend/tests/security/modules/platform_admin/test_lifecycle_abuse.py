"""[T209] Security test: tenant lifecycle transition abuse (spec.md
§23.1, master prompt §7 Architecture Freeze — Tenant Lifecycle).

Every prohibited transition is rejected with a specific, named error —
never a generic 403:

  - `suspended → deleted` directly (owner-side, via existing
    `soft_delete_company`) — rejected by the pre-existing
    `_OWNER_TRANSITIONS[suspended] = set()` guard
    (`InvalidStatusTransitionError`, 409).
  - `suspended → inactive` directly (owner-side, via
    `deactivate_company`) — same guard.
  - `pending_setup → suspended` (Platform-side, via
    `POST /tenants/{companyId}/suspend`) — rejected by
    `TenantLifecycleService.suspend()`'s `_SUSPENDABLE_STATUSES` check
    (`TenantLifecycleTransitionError`, 409).
  - Repeated suspension of an already-suspended tenant (Edge Case #1) and
    reactivation of a non-suspended tenant (Edge Case #2) — both 409,
    both a specific error code, never a generic 403/500.
  - An actor lacking the specific required permission — 403, distinct
    from the transition-conflict 409s above (complements T206's
    exhaustive permission matrix).
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
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.platform_session import PlatformSession
from modules.platform_admin.repositories.platform_rbac_repository import (
    PlatformRbacRepository,
)
from modules.platform_admin.services.platform_jwt_service import PlatformJwtService
from modules.platform_admin.services.platform_rbac_seed_service import (
    PlatformRbacSeedService,
)
from tests.fixtures.auth_fixtures import create_test_user


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_platform_token_with_permissions(db: Session, codes: set[str]) -> str:
    user = User(
        email=f"t209-lifecycle-admin-{uuid.uuid4().hex[:12]}@example.com",
        display_name="T209 Lifecycle Admin",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    rbac_repo = PlatformRbacRepository(db)
    PlatformRbacSeedService(db, rbac_repo).seed_all()
    role = rbac_repo.create_role(
        code=f"t209-lifecycle-role-{uuid.uuid4().hex[:10]}", name="T209 Lifecycle Role"
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


def _make_company_via_api(
    test_client: TestClient, db: Session, *, label: str
) -> tuple[str, str]:
    """Creates a genuine, activated Company via the real HTTP owner flow.
    Returns (company_id, owner_access_token)."""
    user, password = create_test_user(
        db, email=f"t209-owner-{label}-{uuid.uuid4().hex[:10]}@example.com"
    )
    token = _login(test_client, user.email, password)
    create_response = test_client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"T209 Lifecycle Co {label} {uuid.uuid4().hex[:8]}",
            "email": f"t209-co-{label}-{uuid.uuid4().hex[:8]}@example.com",
        },
        headers=_auth(token),
    )
    assert create_response.status_code == 201, create_response.text
    company_id = create_response.json()["data"]["id"]

    test_client.patch(
        f"/api/v1/companies/{company_id}", json={"country": "US"}, headers=_auth(token)
    )
    activate_response = test_client.post(
        f"/api/v1/companies/{company_id}/activate", headers=_auth(token)
    )
    assert activate_response.status_code == 200, activate_response.text

    return company_id, token


class TestPlatformSideProhibitedTransitions:
    def test_pending_setup_to_suspended_is_rejected_with_specific_error(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        admin_token = _make_platform_token_with_permissions(
            db_session, {"platform.tenants.suspend"}
        )
        # A pending_setup company (never activated) is never suspendable.
        owner = User(
            email=f"t209-pending-owner-{uuid.uuid4().hex[:10]}@example.com",
            display_name="Pending Owner",
        )
        db_session.add(owner)
        db_session.flush()
        company = Company(
            legal_name=f"T209 Pending Co {uuid.uuid4().hex[:8]}",
            slug=f"t209-pending-co-{uuid.uuid4().hex[:8]}",
            owner_id=owner.id,
            email=f"t209-pending-{uuid.uuid4().hex[:8]}@example.com",
            status="pending_setup",
        )
        db_session.add(company)
        db_session.commit()

        response = test_client.post(
            f"/api/v1/platform/tenants/{company.id}/suspend",
            json={"reason": "Attempted invalid transition."},
            headers=_auth(admin_token),
        )

        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] != "FORBIDDEN"

    def test_suspending_an_already_suspended_tenant_is_rejected_with_specific_error(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        admin_token = _make_platform_token_with_permissions(
            db_session, {"platform.tenants.suspend"}
        )
        company_id, _ = _make_company_via_api(
            test_client, db_session, label="double-suspend"
        )

        first = test_client.post(
            f"/api/v1/platform/tenants/{company_id}/suspend",
            json={"reason": "First suspend."},
            headers=_auth(admin_token),
        )
        assert first.status_code == 200, first.text

        second = test_client.post(
            f"/api/v1/platform/tenants/{company_id}/suspend",
            json={"reason": "Second suspend attempt."},
            headers=_auth(admin_token),
        )
        assert second.status_code == 409, second.text
        assert "suspend" in second.json()["error"]["message"].lower()

    def test_reactivating_a_non_suspended_tenant_is_rejected_with_specific_error(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        admin_token = _make_platform_token_with_permissions(
            db_session, {"platform.tenants.reactivate"}
        )
        company_id, _ = _make_company_via_api(
            test_client, db_session, label="bad-reactivate"
        )

        response = test_client.post(
            f"/api/v1/platform/tenants/{company_id}/reactivate",
            json={"reason": "Not currently suspended."},
            headers=_auth(admin_token),
        )

        assert response.status_code == 409, response.text
        assert "reactivate" in response.json()["error"]["message"].lower()

    def test_suspend_without_the_specific_permission_is_403_not_a_transition_conflict(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        # Holds an adjacent permission, never platform.tenants.suspend —
        # rejected on authorization grounds, distinctly from the 409
        # transition-conflict cases above.
        admin_token = _make_platform_token_with_permissions(
            db_session, {"platform.dashboard.view"}
        )
        company_id, _ = _make_company_via_api(
            test_client, db_session, label="no-permission"
        )

        response = test_client.post(
            f"/api/v1/platform/tenants/{company_id}/suspend",
            json={"reason": "Should be rejected on permission grounds."},
            headers=_auth(admin_token),
        )

        assert response.status_code == 403, response.text


class TestOwnerSideProhibitedTransitionsFromSuspended:
    """`get_current_company()` (T084, Phase 10) checks
    `assert_company_access_allowed` before any owner-transition logic
    runs: a suspended company raises `CompanySuspendedError` (403,
    code `COMPANY_SUSPENDED`) — a specific, named error distinct from a
    generic 403, and distinct from `INVALID_STATUS_TRANSITION`. Either
    way, the owner cannot reach `deactivate`/`delete`'s transition logic
    at all while the tenant is Platform-suspended — the prohibited
    `suspended → inactive`/`suspended → deleted` direct transitions are
    blocked one layer earlier than the owner-transition table itself."""

    def test_owner_cannot_deactivate_a_platform_suspended_tenant(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id, owner_token = _make_company_via_api(
            test_client, db_session, label="owner-deactivate-suspended"
        )
        company = db_session.get(Company, uuid.UUID(company_id))
        assert company is not None
        company.status = "suspended"
        company.pre_suspension_status = "active"
        db_session.add(company)
        db_session.commit()

        response = test_client.post(
            f"/api/v1/companies/{company_id}/deactivate",
            json={"reason": "Attempted owner-side deactivate of a suspended tenant."},
            headers=_auth(owner_token),
        )

        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "COMPANY_SUSPENDED"

    def test_owner_cannot_delete_a_platform_suspended_tenant(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id, owner_token = _make_company_via_api(
            test_client, db_session, label="owner-delete-suspended"
        )
        company = db_session.get(Company, uuid.UUID(company_id))
        assert company is not None
        company.status = "suspended"
        company.pre_suspension_status = "active"
        db_session.add(company)
        db_session.commit()

        response = test_client.request(
            "DELETE",
            f"/api/v1/companies/{company_id}",
            json={"reason": "Attempted owner-side delete of a suspended tenant."},
            headers=_auth(owner_token),
        )

        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "COMPANY_SUSPENDED"
