"""[T068, T069] API-level proof of the Administrator/RBAC route-specific
acceptance criteria that the Phase-5 permission matrix (T076) does not
itself exercise: duplicate-administrator 409, deactivation's session
revocation, last-Platform-Owner-deactivation 409, and unknown-permission
422 on role create/update.

T076 already proves the generic auth/permission shape (401/403) for all
6 operations; this file proves each operation's own distinctive business
outcome on the success/conflict paths.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.config.settings import get_settings
from core.utils.datetime import utcnow
from modules.auth.models.user import User
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.platform_rbac import PlatformAdminRoleAssignment
from modules.platform_admin.models.platform_session import PlatformSession
from modules.platform_admin.repositories.platform_rbac_repository import (
    PlatformRbacRepository,
)
from modules.platform_admin.services.platform_jwt_service import PlatformJwtService
from modules.platform_admin.services.platform_rbac_seed_service import (
    PlatformRbacSeedService,
)
from tests.fixtures.auth_fixtures import create_test_user


def _make_platform_administrator(db: Session) -> PlatformAdministrator:
    user = User(
        email=f"platform-route-{uuid.uuid4().hex[:12]}@example.test",
        display_name="Platform Admin",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    db.commit()
    return administrator


def _make_token_with_permissions(
    db: Session, codes: set[str]
) -> tuple[PlatformAdministrator, str]:
    administrator = _make_platform_administrator(db)
    rbac_repo = PlatformRbacRepository(db)
    PlatformRbacSeedService(db, rbac_repo).seed_all()
    role = rbac_repo.create_role(
        code=f"test-route-role-{uuid.uuid4().hex[:10]}", name="Test Route Role"
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
    token = PlatformJwtService(get_settings()).create_access_token(
        platform_administrator_id=administrator.id, session_id=session.id
    )
    return administrator, token


def _isolate_as_sole_owner(
    db: Session, rbac_repo: PlatformRbacRepository, owner_role, keep_admin_id
) -> None:
    """See test_rbac_escalation.py's identical helper — necessary because
    `count_active_administrators_with_role` is a genuine global count with
    no per-test scope under the shared, leaky `db_session` fixture."""
    from sqlalchemy import select

    stmt = select(PlatformAdminRoleAssignment.platform_administrator_id).where(
        PlatformAdminRoleAssignment.role_id == owner_role.id,
        PlatformAdminRoleAssignment.platform_administrator_id != keep_admin_id,
    )
    for other_admin_id in db.execute(stmt).scalars().all():
        rbac_repo.remove_assignment(
            platform_administrator_id=other_admin_id, role_id=owner_role.id
        )
    db.commit()


class TestCreateAdministratorUnknownUserRejected:
    def test_creating_an_administrator_for_a_nonexistent_user_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        _, token = _make_token_with_permissions(db_session, {"platform.admins.manage"})

        response = test_client.post(
            "/api/v1/platform/administrators",
            json={"user_id": str(uuid.uuid4())},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404


class TestAssignRoleUnknownTargetsRejected:
    def test_assigning_to_a_nonexistent_administrator_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        rbac_repo = PlatformRbacRepository(db_session)
        PlatformRbacSeedService(db_session, rbac_repo).seed_all()
        analyst_role = rbac_repo.get_role_by_code("read_only_platform_analyst")
        assert analyst_role is not None
        _, token = _make_token_with_permissions(db_session, {"platform.rbac.manage"})

        response = test_client.post(
            f"/api/v1/platform/administrators/{uuid.uuid4()}/roles",
            json={"role_id": str(analyst_role.id)},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    def test_assigning_a_nonexistent_role_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        _, token = _make_token_with_permissions(db_session, {"platform.rbac.manage"})
        target = _make_platform_administrator(db_session)

        response = test_client.post(
            f"/api/v1/platform/administrators/{target.id}/roles",
            json={"role_id": str(uuid.uuid4())},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404


class TestCreateAdministratorDuplicateRejected:
    def test_creating_a_second_administrator_for_the_same_user_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        _, token = _make_token_with_permissions(db_session, {"platform.admins.manage"})
        target_user = User(
            email=f"dup-target-{uuid.uuid4().hex[:12]}@example.test",
            display_name="Dup Target",
        )
        db_session.add(target_user)
        db_session.commit()

        first = test_client.post(
            "/api/v1/platform/administrators",
            json={"user_id": str(target_user.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert first.status_code == 201

        second = test_client.post(
            "/api/v1/platform/administrators",
            json={"user_id": str(target_user.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert second.status_code == 409


class TestDeactivateRevokesActiveSessions:
    def test_patch_deactivate_revokes_the_targets_active_session(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = f"route-deactivate-{uuid.uuid4().hex[:12]}@example.com"
        password = "RouteTestPassword@123"
        user, _ = create_test_user(db_session, email=email, password=password)
        target = PlatformAdministrator(user_id=user.id, is_active=True)
        db_session.add(target)
        db_session.commit()

        login = test_client.post(
            "/api/v1/platform/auth/login", json={"email": email, "password": password}
        )
        assert login.status_code == 200
        target_access_token = login.json()["data"]["access_token"]

        _, actor_token = _make_token_with_permissions(
            db_session, {"platform.admins.manage"}
        )

        response = test_client.patch(
            f"/api/v1/platform/administrators/{target.id}",
            json={"is_active": False, "reason": "route test deactivation"},
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["is_active"] is False

        still_valid = test_client.post(
            "/api/v1/platform/auth/logout",
            headers={"Authorization": f"Bearer {target_access_token}"},
        )
        assert still_valid.status_code == 401


class TestDeactivateLastOwnerRejected:
    def test_deactivating_the_sole_platform_owner_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        rbac_repo = PlatformRbacRepository(db_session)
        PlatformRbacSeedService(db_session, rbac_repo).seed_all()
        owner_role = rbac_repo.get_role_by_code("platform_owner")
        assert owner_role is not None

        sole_owner = _make_platform_administrator(db_session)
        # assigned_by=sole_owner.id (self), NOT None: migration 057
        # reserves assigned_by IS NULL exclusively for the genuine
        # bootstrap-created first assignment (see test_bootstrap.py) —
        # this is direct test setup, not a bootstrap flow.
        rbac_repo.assign_role(
            platform_administrator_id=sole_owner.id,
            role_id=owner_role.id,
            assigned_by=sole_owner.id,
            assigned_at=utcnow(),
        )
        db_session.commit()
        _isolate_as_sole_owner(db_session, rbac_repo, owner_role, sole_owner.id)

        _, actor_token = _make_token_with_permissions(
            db_session, {"platform.admins.manage"}
        )

        response = test_client.patch(
            f"/api/v1/platform/administrators/{sole_owner.id}",
            json={"is_active": False, "reason": "attempted last-owner deactivation"},
            headers={"Authorization": f"Bearer {actor_token}"},
        )

        assert response.status_code == 409
        db_session.refresh(sole_owner)
        assert sole_owner.is_active is True


class TestCreateRoleRejectsUnknownPermissionCodes:
    def test_unknown_permission_code_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        _, token = _make_token_with_permissions(db_session, {"platform.rbac.manage"})

        response = test_client.post(
            "/api/v1/platform/roles",
            json={
                "code": f"bad-role-{uuid.uuid4().hex[:10]}",
                "name": "Bad Role",
                "permission_codes": ["platform.does_not_exist"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422


class TestAssignRoleSelfEscalationRejectedViaHttp:
    def test_actor_without_owner_role_cannot_grant_owner_role_via_http(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        rbac_repo = PlatformRbacRepository(db_session)
        PlatformRbacSeedService(db_session, rbac_repo).seed_all()
        owner_role = rbac_repo.get_role_by_code("platform_owner")
        assert owner_role is not None

        _, actor_token = _make_token_with_permissions(
            db_session, {"platform.rbac.manage"}
        )
        target = _make_platform_administrator(db_session)

        response = test_client.post(
            f"/api/v1/platform/administrators/{target.id}/roles",
            json={"role_id": str(owner_role.id)},
            headers={"Authorization": f"Bearer {actor_token}"},
        )

        assert response.status_code == 403
        assert not rbac_repo.has_role(target.id, "platform_owner")
