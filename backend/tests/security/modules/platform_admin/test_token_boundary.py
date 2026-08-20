"""[T055, T056, T058] Tenant/Platform token-boundary tests.

Covers tasks.md T055 (tenant token -> Platform API denied), T056 (Platform
token never accepted as a tenant session), T058 (unauthenticated request
to a Platform API denied). "Every /api/v1/platform/* route existing at
this point" is, at end of Phase 4, exactly 3 operations: `/auth/login`
and `/auth/refresh` are deliberately public (no `x-permission`, contract
`security: []`) — a bearer token is never consulted by either, so "token
rejection" is not a meaningful concept for them. `/auth/logout` is the
sole route requiring authentication at this phase, and is what T055/T058
exercise.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.config.settings import get_settings
from core.utils.datetime import utcnow
from modules.auth.models.session import Session as TenantSession
from modules.auth.models.user import User
from modules.auth.services.jwt_service import JWTService
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.platform_session import PlatformSession
from modules.platform_admin.services.platform_jwt_service import PlatformJwtService


def _make_tenant_access_token(db: Session, *, role_hint: str = "owner") -> str:
    """Create a genuine tenant User + Session and mint a real access token
    for it, mirroring what a real tenant login would produce."""
    user = User(
        email=f"tenant-boundary-{uuid.uuid4().hex[:12]}@example.test",
        display_name=f"Tenant {role_hint}",
    )
    db.add(user)
    db.flush()

    session = TenantSession(user_id=user.id)
    db.add(session)
    db.flush()
    db.commit()

    settings = get_settings()
    jwt_svc = JWTService(settings)
    return jwt_svc.create_access_token(
        user_id=user.id, email=user.email, session_id=session.id
    )


def _make_platform_access_token(db: Session) -> str:
    """Create a genuine PlatformAdministrator + PlatformSession and mint a
    real Platform access token for it."""
    user = User(
        email=f"platform-boundary-{uuid.uuid4().hex[:12]}@example.test",
        display_name="Platform Admin",
    )
    db.add(user)
    db.flush()

    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()

    platform_session = PlatformSession(
        platform_administrator_id=administrator.id,
        expires_at=utcnow() + timedelta(days=1),
    )
    db.add(platform_session)
    db.flush()
    db.commit()

    settings = get_settings()
    jwt_svc = PlatformJwtService(settings)
    return jwt_svc.create_access_token(
        platform_administrator_id=administrator.id, session_id=platform_session.id
    )


class TestTenantTokenRejectedByPlatformApi:
    """T055 — a tenant access token is rejected by every Platform API
    that exists at this point in the epic (the sole authenticated one:
    /auth/logout), regardless of the tenant user's role."""

    def test_tenant_token_rejected_by_platform_logout(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        tenant_token = _make_tenant_access_token(db_session, role_hint="owner")

        response = test_client.post(
            "/api/v1/platform/auth/logout",
            headers={"Authorization": f"Bearer {tenant_token}"},
        )

        assert response.status_code == 401


class TestPlatformTokenNeverSatisfiesTenantAuth:
    """T056 — a platform_access token is rejected by get_current_user()
    (unmodified — rejection is structural, via the sub/typ design, spec
    §11 scenario 4), and does not implicitly unlock any tenant endpoint."""

    def test_platform_token_rejected_by_tenant_me_endpoint(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        platform_token = _make_platform_access_token(db_session)

        response = test_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {platform_token}"},
        )

        assert response.status_code == 401

    def test_platform_token_does_not_unlock_a_tenant_protected_route(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        platform_token = _make_platform_access_token(db_session)

        response = test_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {platform_token}"},
        )

        assert response.status_code == 401


class TestUnauthenticatedRequestToPlatformApiDenied:
    """T058 — no /api/v1/platform/* route requiring auth is reachable
    without a valid Platform token."""

    def test_no_authorization_header_rejected(self, test_client: TestClient) -> None:
        response = test_client.post("/api/v1/platform/auth/logout")
        assert response.status_code == 401

    def test_malformed_authorization_header_rejected(
        self, test_client: TestClient
    ) -> None:
        response = test_client.post(
            "/api/v1/platform/auth/logout",
            headers={"Authorization": "NotBearer sometoken"},
        )
        assert response.status_code == 401


class TestPlatformRefreshTokenRejectedAsAccessToken:
    """T052 — the reverse typ-crossover direction: a platform_refresh
    token must not authenticate a route protected by
    get_current_platform_admin(), which requires exactly
    typ="platform_access"."""

    def test_refresh_typed_token_rejected_by_access_dependency(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        import uuid as _uuid
        from datetime import timedelta as _timedelta

        from core.config.settings import get_settings as _get_settings
        from core.utils.datetime import utcnow as _utcnow

        user = User(
            email=f"refresh-as-access-{_uuid.uuid4().hex[:12]}@example.test",
            display_name="Platform Admin",
        )
        db_session.add(user)
        db_session.flush()
        administrator = PlatformAdministrator(user_id=user.id, is_active=True)
        db_session.add(administrator)
        db_session.flush()
        platform_session = PlatformSession(
            platform_administrator_id=administrator.id,
            expires_at=_utcnow() + _timedelta(days=1),
        )
        db_session.add(platform_session)
        db_session.flush()
        db_session.commit()

        refresh_token = PlatformJwtService(_get_settings()).create_refresh_token(
            platform_administrator_id=administrator.id, session_id=platform_session.id
        )

        response = test_client.post(
            "/api/v1/platform/auth/logout",
            headers={"Authorization": f"Bearer {refresh_token}"},
        )
        assert response.status_code == 401
