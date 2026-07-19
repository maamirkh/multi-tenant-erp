"""T135 [P] — Rank enforcement security tests.

Verifies that the RBAC rank hierarchy is strictly enforced:
- A lower-ranked member cannot assign a role equal to or above their own rank.
- An equal-ranked member (excluding Owner) cannot change another peer's role.
- A member cannot change their own role (self-role-change prevention, BR-013).
- A custom role's rank cannot exceed the creating actor's rank.

HTTP status conventions in this implementation:
- ``InsufficientRankError`` → 403 (rank guard: actor rank too low to act on target)
- ``CannotModifyOwnRoleError`` → 409 (business rule: self-role-change prohibited)
- ``InvalidRoleRankError`` → 422 (role creation: rank out of allowed range)

Lifecycle operations (deactivate/suspend/archive) require Admin+ rank but do NOT
enforce actor-rank > target-rank — that check applies only to role assignment.
Owner protection for lifecycle operations is tested separately in
``test_owner_protection.py``.

Spec ref: spec.md BR-011, BR-013, tasks T135.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user
from tests.fixtures.users_roles_fixtures import (
    create_test_member,
    seed_system_roles,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_company(client: TestClient, token: str, suffix: str) -> str:
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Rank Test Corp {suffix}",
            "email": f"ranktest_{suffix}@example.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, f"Company creation failed: {resp.text}"
    return resp.json()["data"]["id"]


# ---------------------------------------------------------------------------
# Fixture: company with owner + admin + manager + viewer members
# ---------------------------------------------------------------------------


@pytest.fixture()
def ranked_company(test_client: TestClient, db_session: Session):
    """Seed a company with an owner, admin, manager, and viewer.

    Returns:
        dict with keys: company_id, owner_token, admin_token, manager_token,
        viewer_token, owner_member_id, admin_member_id, manager_member_id,
        viewer_member_id, role_ids (slug → UUID str).
    """
    prefix = uuid.uuid4().hex[:8]

    owner_user, owner_pwd = create_test_user(
        db_session, email=f"rank_owner_{prefix}@example.com"
    )
    admin_user, admin_pwd = create_test_user(
        db_session, email=f"rank_admin_{prefix}@example.com"
    )
    manager_user, manager_pwd = create_test_user(
        db_session, email=f"rank_manager_{prefix}@example.com"
    )
    viewer_user, viewer_pwd = create_test_user(
        db_session, email=f"rank_viewer_{prefix}@example.com"
    )

    owner_token = _login(test_client, owner_user.email, owner_pwd)
    admin_token = _login(test_client, admin_user.email, admin_pwd)
    manager_token = _login(test_client, manager_user.email, manager_pwd)
    viewer_token = _login(test_client, viewer_user.email, viewer_pwd)

    company_id_str = _create_company(test_client, owner_token, prefix)
    company_id = uuid.UUID(company_id_str)

    roles = seed_system_roles(db_session, company_id, owner_user.id)
    role_map = {r.slug: r for r in roles}

    # Bootstrap owner membership is created at company creation; ensure correct role
    owner_member = create_test_member(
        db_session,
        company_id=company_id,
        user_id=owner_user.id,
        role_id=role_map["owner"].id,
    )
    admin_member = create_test_member(
        db_session,
        company_id=company_id,
        user_id=admin_user.id,
        role_id=role_map["admin"].id,
    )
    manager_member = create_test_member(
        db_session,
        company_id=company_id,
        user_id=manager_user.id,
        role_id=role_map["manager"].id,
    )
    viewer_member = create_test_member(
        db_session,
        company_id=company_id,
        user_id=viewer_user.id,
        role_id=role_map["viewer"].id,
    )

    return {
        "company_id": company_id_str,
        "owner_token": owner_token,
        "admin_token": admin_token,
        "manager_token": manager_token,
        "viewer_token": viewer_token,
        "owner_member_id": str(owner_member.id),
        "admin_member_id": str(admin_member.id),
        "manager_member_id": str(manager_member.id),
        "viewer_member_id": str(viewer_member.id),
        "role_ids": {slug: str(r.id) for slug, r in role_map.items()},
    }


# ---------------------------------------------------------------------------
# Lower-rank cannot assign higher-rank roles (BR-011, role management)
# ---------------------------------------------------------------------------


class TestLowerRankCannotAssignHigherRankRole:
    """Lower-ranked member cannot assign a role above their own rank via PATCH."""

    def test_manager_cannot_assign_admin_role_to_viewer(
        self, test_client: TestClient, ranked_company: dict
    ) -> None:
        """Manager (rank 60) cannot assign Admin role (rank 80) to Viewer — 403."""
        resp = test_client.patch(
            f"/api/v1/companies/{ranked_company['company_id']}/members"
            f"/{ranked_company['viewer_member_id']}",
            json={"role_id": ranked_company["role_ids"]["admin"]},
            headers=_auth(ranked_company["manager_token"]),
        )
        assert resp.status_code == 403

    def test_admin_cannot_assign_owner_role(
        self, test_client: TestClient, ranked_company: dict
    ) -> None:
        """Admin (rank 80) cannot assign Owner role (rank 100) to Viewer — 403."""
        resp = test_client.patch(
            f"/api/v1/companies/{ranked_company['company_id']}/members"
            f"/{ranked_company['viewer_member_id']}",
            json={"role_id": ranked_company["role_ids"]["owner"]},
            headers=_auth(ranked_company["admin_token"]),
        )
        assert resp.status_code == 403

    def test_viewer_cannot_assign_any_role(
        self, test_client: TestClient, ranked_company: dict
    ) -> None:
        """Viewer (rank 20) cannot assign Viewer role to Manager — 403."""
        resp = test_client.patch(
            f"/api/v1/companies/{ranked_company['company_id']}/members"
            f"/{ranked_company['manager_member_id']}",
            json={"role_id": ranked_company["role_ids"]["viewer"]},
            headers=_auth(ranked_company["viewer_token"]),
        )
        assert resp.status_code == 403

    def test_manager_cannot_manage_admin_lifecycle(
        self, test_client: TestClient, ranked_company: dict
    ) -> None:
        """Manager (rank 60) lacks Admin+ rank to access lifecycle endpoints — 403."""
        resp = test_client.post(
            f"/api/v1/companies/{ranked_company['company_id']}/members"
            f"/{ranked_company['admin_member_id']}/deactivate",
            headers=_auth(ranked_company["manager_token"]),
        )
        # Manager rank 60 < Admin rank 80 required by require_rank(ADMIN_RANK)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Equal-rank cannot change peer's role (BR-011, role management)
# ---------------------------------------------------------------------------


class TestEqualRankCannotChangePeerRole:
    """Equal-ranked members (excluding Owner) cannot change each other's role."""

    def test_admin_cannot_change_another_admins_role(
        self, test_client: TestClient, db_session: Session, ranked_company: dict
    ) -> None:
        """Admin A cannot change Admin B's role (equal rank 80) — 403."""
        prefix = uuid.uuid4().hex[:8]
        second_admin, second_pwd = create_test_user(
            db_session, email=f"rank_admin2_{prefix}@example.com"
        )

        company_id = uuid.UUID(ranked_company["company_id"])
        from modules.users_roles.repositories.role_repository import RoleRepository

        role_repo = RoleRepository(db_session)
        admin_role = role_repo.get_by_slug(company_id, "admin")

        second_admin_member = create_test_member(
            db_session,
            company_id=company_id,
            user_id=second_admin.id,
            role_id=admin_role.id,
        )

        # Admin A tries to change Admin B's role to Manager
        resp = test_client.patch(
            f"/api/v1/companies/{ranked_company['company_id']}/members"
            f"/{second_admin_member.id}",
            json={"role_id": ranked_company["role_ids"]["manager"]},
            headers=_auth(ranked_company["admin_token"]),
        )
        assert resp.status_code == 403

    def test_manager_cannot_change_another_managers_role(
        self, test_client: TestClient, db_session: Session, ranked_company: dict
    ) -> None:
        """Manager A cannot change Manager B's role (equal rank 60) — 403."""
        prefix = uuid.uuid4().hex[:8]
        second_manager, second_pwd = create_test_user(
            db_session, email=f"rank_mgr2_{prefix}@example.com"
        )

        company_id = uuid.UUID(ranked_company["company_id"])
        from modules.users_roles.repositories.role_repository import RoleRepository

        role_repo = RoleRepository(db_session)
        manager_role = role_repo.get_by_slug(company_id, "manager")

        second_manager_member = create_test_member(
            db_session,
            company_id=company_id,
            user_id=second_manager.id,
            role_id=manager_role.id,
        )

        # Manager A tries to change Manager B's role to Viewer
        resp = test_client.patch(
            f"/api/v1/companies/{ranked_company['company_id']}/members"
            f"/{second_manager_member.id}",
            json={"role_id": ranked_company["role_ids"]["viewer"]},
            headers=_auth(ranked_company["manager_token"]),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Self-role-change prevention (BR-013)
# ---------------------------------------------------------------------------


class TestSelfRoleChangePrevented:
    """A member must not be able to change their own role (BR-013).

    ``CannotModifyOwnRoleError`` maps to HTTP 409 (business conflict),
    not 403 (authorization), because the actor has sufficient rank in
    principle — the prohibition is a business rule, not a rank check.
    """

    def test_admin_cannot_change_own_role(
        self, test_client: TestClient, ranked_company: dict
    ) -> None:
        """Admin attempting to change own role returns 409 (BR-013)."""
        resp = test_client.patch(
            f"/api/v1/companies/{ranked_company['company_id']}/members"
            f"/{ranked_company['admin_member_id']}",
            json={"role_id": ranked_company["role_ids"]["manager"]},
            headers=_auth(ranked_company["admin_token"]),
        )
        assert resp.status_code == 409

    def test_owner_cannot_change_own_role(
        self, test_client: TestClient, ranked_company: dict
    ) -> None:
        """Owner attempting to change own role returns 409 (BR-013)."""
        resp = test_client.patch(
            f"/api/v1/companies/{ranked_company['company_id']}/members"
            f"/{ranked_company['owner_member_id']}",
            json={"role_id": ranked_company["role_ids"]["admin"]},
            headers=_auth(ranked_company["owner_token"]),
        )
        assert resp.status_code == 409

    def test_viewer_cannot_change_own_role(
        self, test_client: TestClient, ranked_company: dict
    ) -> None:
        """Viewer attempting to change own role returns 403 (insufficient rank for PATCH)."""
        resp = test_client.patch(
            f"/api/v1/companies/{ranked_company['company_id']}/members"
            f"/{ranked_company['viewer_member_id']}",
            json={"role_id": ranked_company["role_ids"]["salesperson"]},
            headers=_auth(ranked_company["viewer_token"]),
        )
        # Viewer rank 20 < minimum required for role change; 403 fires before 409
        assert resp.status_code in (403, 409)


# ---------------------------------------------------------------------------
# Custom role rank cannot exceed creator rank (BR-011)
# ---------------------------------------------------------------------------


class TestCustomRoleRankCannotExceedCreatorRank:
    """Custom role rank must not exceed the creating actor's rank.

    ``InvalidRoleRankError`` maps to HTTP 422 when rank is out of range.
    Admin (rank 80) may only create roles with rank 1–79.
    """

    def test_admin_cannot_create_role_with_owner_rank(
        self, test_client: TestClient, ranked_company: dict
    ) -> None:
        """Admin (rank 80) cannot create a custom role with rank 100 — 422."""
        resp = test_client.post(
            f"/api/v1/companies/{ranked_company['company_id']}/roles",
            json={"name": "Super Custom", "rank": 100},
            headers=_auth(ranked_company["admin_token"]),
        )
        assert resp.status_code in (403, 422)

    def test_admin_cannot_create_role_with_equal_admin_rank(
        self, test_client: TestClient, ranked_company: dict
    ) -> None:
        """Admin (rank 80) cannot create a custom role with rank >= 80 — 422."""
        resp = test_client.post(
            f"/api/v1/companies/{ranked_company['company_id']}/roles",
            json={"name": "Clone Admin Role", "rank": 80},
            headers=_auth(ranked_company["admin_token"]),
        )
        assert resp.status_code in (403, 422)

    def test_admin_can_create_role_below_own_rank(
        self, test_client: TestClient, ranked_company: dict
    ) -> None:
        """Admin (rank 80) can create a custom role with rank 79 — 201."""
        resp = test_client.post(
            f"/api/v1/companies/{ranked_company['company_id']}/roles",
            json={"name": f"Senior Manager {uuid.uuid4().hex[:4]}", "rank": 79},
            headers=_auth(ranked_company["admin_token"]),
        )
        assert resp.status_code == 201
