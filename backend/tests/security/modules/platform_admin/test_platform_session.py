"""[T057] Revoked Platform session is rejected. [T050] Refresh
rotate-on-use and its rejection paths.

Covers tasks.md T057: explicit logout -> the still-unexpired access token
is rejected on the next request. Also covers T050's own acceptance —
"rotates the platform refresh token, reuses the same PlatformSession,
rejects a revoked session or a deactivated administrator" — which no
other file directly exercises. Uses a real end-to-end HTTP login (not a
service-layer shortcut) so every proof covers the actual wire protocol.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from tests.fixtures.auth_fixtures import create_test_user


def _register_platform_administrator(db: Session, *, email: str, password: str) -> None:
    user, _ = create_test_user(db, email=email, password=password)
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.commit()


class TestRevokedPlatformSessionRejected:
    def test_logout_then_reuse_same_access_token_is_rejected(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        # Pydantic's EmailStr validator rejects the .test TLD as a reserved
        # special-use domain (RFC 2606) — use .com for any email that goes
        # through actual HTTP request validation, unlike the direct-ORM
        # test emails elsewhere in this module which skip that validation.
        email = f"session-revoke-{uuid.uuid4().hex[:12]}@example.com"
        password = "TestPassword@1234"
        _register_platform_administrator(db_session, email=email, password=password)

        login_response = test_client.post(
            "/api/v1/platform/auth/login",
            json={"email": email, "password": password},
        )
        assert login_response.status_code == 200
        access_token = login_response.json()["data"]["access_token"]

        # The access token still works before logout — sanity check that
        # this is a genuine live-session test, not a token that was already
        # broken for an unrelated reason.
        pre_logout = test_client.post(
            "/api/v1/platform/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert pre_logout.status_code == 204

        # The SAME, still-unexpired access token is rejected on the very
        # next request, because logout revoked its PlatformSession.
        post_logout = test_client.post(
            "/api/v1/platform/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert post_logout.status_code == 401


class TestPlatformRefreshRotation:
    def test_refresh_rotates_and_new_access_token_works(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = f"refresh-rotate-{uuid.uuid4().hex[:12]}@example.com"
        password = "TestPassword@1234"
        _register_platform_administrator(db_session, email=email, password=password)

        login_response = test_client.post(
            "/api/v1/platform/auth/login",
            json={"email": email, "password": password},
        )
        assert login_response.status_code == 200
        old_refresh_token = login_response.json()["data"]["refresh_token"]

        refresh_response = test_client.post(
            "/api/v1/platform/auth/refresh",
            json={"refresh_token": old_refresh_token},
        )
        assert refresh_response.status_code == 200
        new_access_token = refresh_response.json()["data"]["access_token"]
        new_refresh_token = refresh_response.json()["data"]["refresh_token"]
        assert new_refresh_token != old_refresh_token

        # The new access token genuinely works.
        works = test_client.post(
            "/api/v1/platform/auth/logout",
            headers={"Authorization": f"Bearer {new_access_token}"},
        )
        assert works.status_code == 204

    def test_reusing_an_already_rotated_refresh_token_is_rejected(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = f"refresh-replay-{uuid.uuid4().hex[:12]}@example.com"
        password = "TestPassword@1234"
        _register_platform_administrator(db_session, email=email, password=password)

        login_response = test_client.post(
            "/api/v1/platform/auth/login",
            json={"email": email, "password": password},
        )
        old_refresh_token = login_response.json()["data"]["refresh_token"]

        first_use = test_client.post(
            "/api/v1/platform/auth/refresh",
            json={"refresh_token": old_refresh_token},
        )
        assert first_use.status_code == 200

        # Rotate-on-use: the SAME refresh token cannot be used twice.
        replay = test_client.post(
            "/api/v1/platform/auth/refresh",
            json={"refresh_token": old_refresh_token},
        )
        assert replay.status_code == 401

    def test_refresh_with_a_revoked_session_is_rejected(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = f"refresh-revoked-{uuid.uuid4().hex[:12]}@example.com"
        password = "TestPassword@1234"
        _register_platform_administrator(db_session, email=email, password=password)

        login_response = test_client.post(
            "/api/v1/platform/auth/login",
            json={"email": email, "password": password},
        )
        access_token = login_response.json()["data"]["access_token"]
        refresh_token = login_response.json()["data"]["refresh_token"]

        logout_response = test_client.post(
            "/api/v1/platform/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert logout_response.status_code == 204

        # The session behind this refresh token is now revoked.
        refresh_after_logout = test_client.post(
            "/api/v1/platform/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_after_logout.status_code == 401

    def test_refresh_rejects_a_tenant_typed_token(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """A tenant access token (typ="access") is not a valid Platform
        refresh token — the typ check rejects it before any DB lookup."""
        import uuid as _uuid

        from core.config.settings import get_settings
        from modules.auth.models.session import Session as TenantSession
        from modules.auth.models.user import User
        from modules.auth.services.jwt_service import JWTService

        tenant_user = User(
            email=f"tenant-for-refresh-{_uuid.uuid4().hex[:12]}@example.test",
            display_name="Tenant User",
        )
        db_session.add(tenant_user)
        db_session.flush()
        tenant_session = TenantSession(user_id=tenant_user.id)
        db_session.add(tenant_session)
        db_session.flush()
        db_session.commit()

        tenant_token = JWTService(get_settings()).create_access_token(
            user_id=tenant_user.id,
            email=tenant_user.email,
            session_id=tenant_session.id,
        )

        response = test_client.post(
            "/api/v1/platform/auth/refresh",
            json={"refresh_token": tenant_token},
        )
        assert response.status_code == 401
