"""[T074] [BR-9A-001] Tenant signup cannot create Platform authority.

Proves two independent things:

1.  Structural: no code anywhere in ``backend/modules/`` outside
    ``platform_admin`` itself ever constructs a ``PlatformAdministrator``
    or instantiates ``PlatformAdministratorRepository`` — in particular,
    nothing in ``backend/modules/auth/`` (the tenant authentication
    module) touches Platform authority at all.
2.  Behavioural: the only HTTP route that can create a
    ``PlatformAdministrator`` row — ``POST /api/v1/platform/administrators``
    — is unreachable without ``platform.admins.manage``, whether the
    caller is unauthenticated, holds a tenant token, or holds a Platform
    token with an unrelated (even adjacent-sounding) permission. In every
    rejected case, zero rows are written.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from pathlib import Path

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

_BACKEND_ROOT = Path(__file__).resolve().parents[4]
_MODULES_ROOT = _BACKEND_ROOT / "modules"


class TestNoNonPlatformCodeTouchesPlatformAuthority:
    """Structural proof — grepping the actual shipped source, not a
    snapshot/assumption, so this fails immediately if a future change
    reintroduces a stray reference."""

    def test_no_reference_anywhere_outside_platform_admin_module(self) -> None:
        offenders: list[str] = []
        for py_file in _MODULES_ROOT.rglob("*.py"):
            if "platform_admin" in py_file.parts:
                continue
            text = py_file.read_text(encoding="utf-8")
            if (
                "PlatformAdministrator(" in text
                or "PlatformAdministratorRepository(" in text
            ):
                offenders.append(str(py_file.relative_to(_BACKEND_ROOT)))
        assert offenders == [], (
            "Code outside modules/platform_admin references Platform "
            f"authority construction directly: {offenders}"
        )

    def test_auth_module_source_never_mentions_platform_administrators(self) -> None:
        auth_root = _MODULES_ROOT / "auth"
        offenders: list[str] = []
        for py_file in auth_root.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            if "platform_administrator" in text.lower():
                offenders.append(str(py_file.relative_to(_BACKEND_ROOT)))
        assert offenders == [], (
            f"backend/modules/auth/ references Platform authority: {offenders}"
        )


def _make_tenant_access_token(db: Session) -> str:
    user = User(
        email=f"tenant-bootstrap-abuse-{uuid.uuid4().hex[:12]}@example.test",
        display_name="Tenant User",
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


def _make_platform_access_token(db: Session, *, role_code: str | None = None) -> str:
    """A genuine PlatformAdministrator + PlatformSession, optionally
    holding *role_code* (seeded fresh, idempotently, via
    PlatformRbacSeedService — mirrors constants.py's candidate bundles)."""
    user = User(
        email=f"platform-bootstrap-abuse-{uuid.uuid4().hex[:12]}@example.test",
        display_name="Platform Admin",
    )
    db.add(user)
    db.flush()

    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()

    if role_code is not None:
        rbac_repo = PlatformRbacRepository(db)
        PlatformRbacSeedService(db, rbac_repo).seed_all()
        role = rbac_repo.get_role_by_code(role_code)
        assert role is not None, f"Role {role_code!r} was not seeded."
        rbac_repo.assign_role(
            platform_administrator_id=administrator.id,
            role_id=role.id,
            assigned_by=None,
            assigned_at=utcnow(),
        )

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


class TestCreateAdministratorRouteRejectsEveryUnauthorizedCaller:
    """Behavioural proof — the single HTTP route capable of writing a
    PlatformAdministrator row (POST /administrators) is unreachable
    without platform.admins.manage, and nothing is written on rejection."""

    def _count(self, db_session: Session) -> int:
        return db_session.query(PlatformAdministrator).count()

    def test_unauthenticated_request_rejected(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        before = self._count(db_session)
        target_user = User(
            email=f"target-{uuid.uuid4().hex[:12]}@example.test", display_name="Target"
        )
        db_session.add(target_user)
        db_session.commit()

        response = test_client.post(
            "/api/v1/platform/administrators",
            json={"user_id": str(target_user.id)},
        )

        assert response.status_code == 401
        assert self._count(db_session) == before

    def test_tenant_token_rejected(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        before = self._count(db_session)
        tenant_token = _make_tenant_access_token(db_session)
        target_user = User(
            email=f"target-{uuid.uuid4().hex[:12]}@example.test", display_name="Target"
        )
        db_session.add(target_user)
        db_session.commit()

        response = test_client.post(
            "/api/v1/platform/administrators",
            json={"user_id": str(target_user.id)},
            headers={"Authorization": f"Bearer {tenant_token}"},
        )

        assert response.status_code == 401
        assert self._count(db_session) == before

    def test_platform_token_with_no_role_rejected(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        # Count AFTER setting up the caller's own (permission-less)
        # PlatformAdministrator identity — that setup row is not the
        # thing under test; only the target request's effect is.
        platform_token = _make_platform_access_token(db_session, role_code=None)
        before = self._count(db_session)
        target_user = User(
            email=f"target-{uuid.uuid4().hex[:12]}@example.test", display_name="Target"
        )
        db_session.add(target_user)
        db_session.commit()

        response = test_client.post(
            "/api/v1/platform/administrators",
            json={"user_id": str(target_user.id)},
            headers={"Authorization": f"Bearer {platform_token}"},
        )

        assert response.status_code == 403
        assert self._count(db_session) == before

    def test_platform_token_with_adjacent_permission_rejected(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Holds platform.admins.read (an adjacent, read-only permission
        for the SAME resource area) — still must not be sufficient to
        create an administrator, since platform.admins.manage is a
        distinct code (BR-9A-008: holding one permission never implies
        another). `security_audit_admin` grants exactly this shape."""
        platform_token = _make_platform_access_token(
            db_session, role_code="security_audit_admin"
        )
        before = self._count(db_session)
        target_user = User(
            email=f"target-{uuid.uuid4().hex[:12]}@example.test", display_name="Target"
        )
        db_session.add(target_user)
        db_session.commit()

        response = test_client.post(
            "/api/v1/platform/administrators",
            json={"user_id": str(target_user.id)},
            headers={"Authorization": f"Bearer {platform_token}"},
        )

        assert response.status_code == 403
        assert self._count(db_session) == before
