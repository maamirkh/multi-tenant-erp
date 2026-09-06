"""[T076] [Gate B] Permission-enforcement test over the routes that exist
at the end of Phase 5.

Scope is deliberately the **exactly 9 operations** that exist by now — 3
public `/auth/*` operations (no `x-permission`) plus the 6
Administrator/RBAC operations from T068/T069. The exhaustive 30-operation
matrix across every Platform router is T206 (Phase 16), after every
router exists; this file's `IN_SCOPE_OPERATIONS` structure lets T206
assert completeness against it later without re-deriving the split.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.config.settings import get_settings
from core.utils.datetime import utcnow
from modules.auth.models.session import Session as TenantSession
from modules.auth.models.user import User
from modules.auth.services.jwt_service import JWTService
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

# ---------------------------------------------------------------------------
# The exact Phase-5 operation surface (3 public + 6 guarded = 9 total).
# ---------------------------------------------------------------------------

PUBLIC_AUTH_OPERATIONS = (
    ("POST", "/api/v1/platform/auth/login"),
    ("POST", "/api/v1/platform/auth/refresh"),
    ("POST", "/api/v1/platform/auth/logout"),
)

GUARDED_OPERATIONS = (
    ("GET", "/api/v1/platform/administrators", "platform.admins.read"),
    ("POST", "/api/v1/platform/administrators", "platform.admins.manage"),
    ("PATCH", "/api/v1/platform/administrators/{adminId}", "platform.admins.manage"),
    ("GET", "/api/v1/platform/roles", "platform.rbac.read"),
    ("POST", "/api/v1/platform/roles", "platform.rbac.manage"),
    ("POST", "/api/v1/platform/administrators/{adminId}/roles", "platform.rbac.manage"),
)

IN_SCOPE_OPERATIONS = {
    "public": PUBLIC_AUTH_OPERATIONS,
    "guarded": GUARDED_OPERATIONS,
}

_UNRELATED_PERMISSION = "platform.dashboard.view"


def test_in_scope_operation_count_is_exactly_nine_split_three_and_six() -> None:
    assert len(IN_SCOPE_OPERATIONS["public"]) == 3
    assert len(IN_SCOPE_OPERATIONS["guarded"]) == 6
    assert len(IN_SCOPE_OPERATIONS["public"]) + len(IN_SCOPE_OPERATIONS["guarded"]) == 9
    guarded_permissions = {op[2] for op in IN_SCOPE_OPERATIONS["guarded"]}
    # 4 distinct permission codes cover the 6 guarded operations (read/manage
    # for each of the 2 resource areas — admins and rbac).
    assert guarded_permissions == {
        "platform.admins.read",
        "platform.admins.manage",
        "platform.rbac.read",
        "platform.rbac.manage",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tenant_access_token(db: Session) -> str:
    user = User(
        email=f"tenant-perm-matrix-{uuid.uuid4().hex[:12]}@example.test",
        display_name="Tenant User",
    )
    db.add(user)
    db.flush()
    session = TenantSession(user_id=user.id)
    db.add(session)
    db.flush()
    db.commit()
    jwt_svc = JWTService(get_settings())
    return jwt_svc.create_access_token(
        user_id=user.id, email=user.email, session_id=session.id
    )


def _make_platform_administrator(db: Session) -> PlatformAdministrator:
    user = User(
        email=f"platform-perm-matrix-{uuid.uuid4().hex[:12]}@example.test",
        display_name="Platform Admin",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    db.commit()
    return administrator


def _make_platform_token_with_permissions(
    db: Session, codes: set[str]
) -> tuple[PlatformAdministrator, str]:
    """A fresh PlatformAdministrator holding EXACTLY *codes* (a bespoke
    single-purpose role, never a broad candidate bundle) — proving
    "holding one permission never implies another" precisely, per
    BR-9A-008."""
    administrator = _make_platform_administrator(db)

    rbac_repo = PlatformRbacRepository(db)
    PlatformRbacSeedService(db, rbac_repo).seed_all()

    role_code = f"test-matrix-role-{uuid.uuid4().hex[:10]}"
    role = rbac_repo.create_role(code=role_code, name="Test Matrix Role")
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

    token = PlatformJwtService(get_settings()).create_access_token(
        platform_administrator_id=administrator.id, session_id=session.id
    )
    return administrator, token


def _request(
    test_client: TestClient, method: str, path: str, token: str | None
) -> object:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if method == "GET":
        return test_client.get(path, headers=headers)
    if method == "POST":
        return test_client.post(path, json={}, headers=headers)
    if method == "PATCH":
        return test_client.patch(path, json={"is_active": True}, headers=headers)
    raise AssertionError(f"Unhandled method {method}")


# ---------------------------------------------------------------------------
# The 6 permission-guarded Administrator/RBAC operations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method,path,permission", GUARDED_OPERATIONS)
def test_guarded_operation_rejects_unauthenticated(
    test_client: TestClient,
    db_session: Session,
    method: str,
    path: str,
    permission: str,
) -> None:
    target = _make_platform_administrator(db_session)
    resolved_path = path.format(adminId=str(target.id))

    response = _request(test_client, method, resolved_path, token=None)

    assert response.status_code == 401


@pytest.mark.parametrize("method,path,permission", GUARDED_OPERATIONS)
def test_guarded_operation_rejects_tenant_token(
    test_client: TestClient,
    db_session: Session,
    method: str,
    path: str,
    permission: str,
) -> None:
    target = _make_platform_administrator(db_session)
    resolved_path = path.format(adminId=str(target.id))
    tenant_token = _make_tenant_access_token(db_session)

    response = _request(test_client, method, resolved_path, token=tenant_token)

    assert response.status_code == 401


@pytest.mark.parametrize("method,path,permission", GUARDED_OPERATIONS)
def test_guarded_operation_rejects_adjacent_permission(
    test_client: TestClient,
    db_session: Session,
    method: str,
    path: str,
    permission: str,
) -> None:
    target = _make_platform_administrator(db_session)
    resolved_path = path.format(adminId=str(target.id))
    _, token = _make_platform_token_with_permissions(
        db_session, {_UNRELATED_PERMISSION}
    )

    response = _request(test_client, method, resolved_path, token=token)

    assert response.status_code == 403


@pytest.mark.parametrize("method,path,permission", GUARDED_OPERATIONS)
def test_guarded_operation_succeeds_with_required_permission(
    test_client: TestClient,
    db_session: Session,
    method: str,
    path: str,
    permission: str,
) -> None:
    target = _make_platform_administrator(db_session)
    resolved_path = path.format(adminId=str(target.id))
    _, token = _make_platform_token_with_permissions(db_session, {permission})

    if method == "GET":
        response = test_client.get(
            resolved_path, headers={"Authorization": f"Bearer {token}"}
        )
    elif method == "POST" and path == "/api/v1/platform/administrators":
        new_user = User(
            email=f"new-admin-target-{uuid.uuid4().hex[:12]}@example.test",
            display_name="New Admin Target",
        )
        db_session.add(new_user)
        db_session.commit()
        response = test_client.post(
            resolved_path,
            json={"user_id": str(new_user.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
    elif method == "POST" and path == "/api/v1/platform/roles":
        response = test_client.post(
            resolved_path,
            json={
                "code": f"matrix-created-role-{uuid.uuid4().hex[:10]}",
                "name": "Matrix Created Role",
                "permission_codes": [],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    elif method == "POST" and resolved_path.endswith("/roles"):
        rbac_repo = PlatformRbacRepository(db_session)
        analyst_role = rbac_repo.get_role_by_code("read_only_platform_analyst")
        assert analyst_role is not None
        response = test_client.post(
            resolved_path,
            json={"role_id": str(analyst_role.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
    elif method == "PATCH":
        response = test_client.patch(
            resolved_path,
            json={"is_active": True},
            headers={"Authorization": f"Bearer {token}"},
        )
    else:
        raise AssertionError(f"Unhandled case: {method} {path}")

    assert response.status_code in (200, 201), response.text


# ---------------------------------------------------------------------------
# The 3 public authentication operations — no Platform RBAC permission is
# required or asserted for these; they carry their own public/auth
# semantics instead (contract `security: []`).
# ---------------------------------------------------------------------------


class TestPublicAuthOperationsCarryNoRbacPermission:
    def test_login_issues_tokens_only_for_an_active_administrator(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = f"matrix-login-{uuid.uuid4().hex[:12]}@example.com"
        password = "MatrixTestPassword@123"
        user, _ = create_test_user(db_session, email=email, password=password)
        administrator = PlatformAdministrator(user_id=user.id, is_active=True)
        db_session.add(administrator)
        db_session.commit()

        response = test_client.post(
            "/api/v1/platform/auth/login", json={"email": email, "password": password}
        )
        assert response.status_code == 200
        assert "access_token" in response.json()["data"]

    def test_login_generic_failure_for_user_with_no_administrator_account(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = f"matrix-no-admin-{uuid.uuid4().hex[:12]}@example.com"
        password = "MatrixTestPassword@123"
        create_test_user(db_session, email=email, password=password)
        # Deliberately no PlatformAdministrator row created for this user.

        response = test_client.post(
            "/api/v1/platform/auth/login", json={"email": email, "password": password}
        )
        assert response.status_code == 401

    def test_login_generic_failure_for_inactive_administrator(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = f"matrix-inactive-{uuid.uuid4().hex[:12]}@example.com"
        password = "MatrixTestPassword@123"
        user, _ = create_test_user(db_session, email=email, password=password)
        administrator = PlatformAdministrator(user_id=user.id, is_active=False)
        db_session.add(administrator)
        db_session.commit()

        response = test_client.post(
            "/api/v1/platform/auth/login", json={"email": email, "password": password}
        )
        assert response.status_code == 401

    def test_refresh_rejects_a_revoked_session(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = f"matrix-refresh-revoked-{uuid.uuid4().hex[:12]}@example.com"
        password = "MatrixTestPassword@123"
        user, _ = create_test_user(db_session, email=email, password=password)
        administrator = PlatformAdministrator(user_id=user.id, is_active=True)
        db_session.add(administrator)
        db_session.commit()

        login_response = test_client.post(
            "/api/v1/platform/auth/login", json={"email": email, "password": password}
        )
        assert login_response.status_code == 200
        refresh_token = login_response.json()["data"]["refresh_token"]

        logout_response = test_client.post(
            "/api/v1/platform/auth/logout",
            headers={
                "Authorization": f"Bearer {login_response.json()['data']['access_token']}"
            },
        )
        assert logout_response.status_code == 204

        refresh_response = test_client.post(
            "/api/v1/platform/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert refresh_response.status_code == 401

    def test_refresh_rejects_deactivated_administrator(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = f"matrix-refresh-deactivated-{uuid.uuid4().hex[:12]}@example.com"
        password = "MatrixTestPassword@123"
        user, _ = create_test_user(db_session, email=email, password=password)
        administrator = PlatformAdministrator(user_id=user.id, is_active=True)
        db_session.add(administrator)
        db_session.commit()

        login_response = test_client.post(
            "/api/v1/platform/auth/login", json={"email": email, "password": password}
        )
        refresh_token = login_response.json()["data"]["refresh_token"]

        administrator.is_active = False
        db_session.add(administrator)
        db_session.commit()

        refresh_response = test_client.post(
            "/api/v1/platform/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert refresh_response.status_code == 401

    def test_logout_revokes_the_session(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = f"matrix-logout-{uuid.uuid4().hex[:12]}@example.com"
        password = "MatrixTestPassword@123"
        user, _ = create_test_user(db_session, email=email, password=password)
        administrator = PlatformAdministrator(user_id=user.id, is_active=True)
        db_session.add(administrator)
        db_session.commit()

        login_response = test_client.post(
            "/api/v1/platform/auth/login", json={"email": email, "password": password}
        )
        access_token = login_response.json()["data"]["access_token"]

        logout_response = test_client.post(
            "/api/v1/platform/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert logout_response.status_code == 204

        second_logout = test_client.post(
            "/api/v1/platform/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert second_logout.status_code == 401

    def test_tenant_token_never_accepted_as_platform_session(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        tenant_token = _make_tenant_access_token(db_session)

        response = test_client.post(
            "/api/v1/platform/auth/logout",
            headers={"Authorization": f"Bearer {tenant_token}"},
        )
        assert response.status_code == 401

    def test_platform_access_token_never_accepted_by_get_current_user(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        administrator = _make_platform_administrator(db_session)
        session = PlatformSession(
            platform_administrator_id=administrator.id,
            expires_at=utcnow() + timedelta(days=1),
        )
        db_session.add(session)
        db_session.flush()
        db_session.commit()
        token = PlatformJwtService(get_settings()).create_access_token(
            platform_administrator_id=administrator.id, session_id=session.id
        )

        response = test_client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401
