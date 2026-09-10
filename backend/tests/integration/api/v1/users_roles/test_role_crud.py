"""T056 [US3] — Integration tests for role CRUD endpoints.

Tests: create custom role, update custom role, delete custom role,
system role protection, list roles, GET permissions.

Uses the test_client / db_session fixtures from conftest.py.

Spec reference: tasks T056.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.users_roles.models.enums import MembershipStatus
from tests.fixtures.auth_fixtures import create_test_user
from tests.fixtures.users_roles_fixtures import (
    create_test_member,
    seed_system_roles,
)


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return str(resp.json()["data"]["access_token"])


def _auth(token: str) -> dict[str, Any]:
    return {"Authorization": f"Bearer {token}"}


def _create_company(client: TestClient, token: str) -> dict[str, Any]:
    legal_name = f"RoleCrud-{uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/api/v1/companies",
        json={"legal_name": legal_name, "email": f"info@{uuid.uuid4().hex[:8]}.com"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return dict(resp.json()["data"])


def _setup_owner(client: TestClient, db: Session) -> tuple[str, str, dict[str, str]]:
    """Create owner with company + seeded roles.

    Returns: (owner_token, company_id, role_ids_by_slug)
    """
    owner, owner_pw = create_test_user(
        db, email=f"owner_{uuid.uuid4().hex[:8]}@example.com"
    )
    owner_token = _login(client, owner.email, owner_pw)
    company = _create_company(client, owner_token)
    company_id = uuid.UUID(company["id"])

    roles = seed_system_roles(db, company_id, owner.id)
    role_map = {r.slug: r for r in roles}

    # Create owner membership
    create_test_member(
        db,
        company_id=company_id,
        user_id=owner.id,
        role_id=role_map["owner"].id,
        status=MembershipStatus.active.value,
    )

    return (
        owner_token,
        str(company_id),
        {slug: str(r.id) for slug, r in role_map.items()},
    )


class TestCreateRoleEndpoint:
    """Integration tests for POST /companies/{company_id}/roles."""

    def test_create_custom_role_success(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Owner can create a custom role."""
        owner_token, company_id, _ = _setup_owner(test_client, db_session)

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/roles",
            json={
                "name": "Warehouse Supervisor",
                "rank": 35,
                "description": "Manages warehouse operations",
                "permission_codes": ["members.read", "roles.read"],
            },
            headers=_auth(owner_token),
        )

        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "Warehouse Supervisor"
        assert data["rank"] == 35
        assert data["is_system"] is False
        assert any(p["code"] == "members.read" for p in data["permissions"])

    def test_create_role_system_rank_rejected(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """POST with a system role rank (e.g. 80) returns 422."""
        owner_token, company_id, _ = _setup_owner(test_client, db_session)

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/roles",
            json={"name": "Bad Rank", "rank": 80},
            headers=_auth(owner_token),
        )

        assert resp.status_code == 422

    def test_create_role_requires_auth(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """POST without auth returns 401."""
        resp = test_client.post(
            f"/api/v1/companies/{uuid.uuid4()}/roles",
            json={"name": "Test", "rank": 35},
        )
        assert resp.status_code == 401


class TestUpdateRoleEndpoint:
    """Integration tests for PATCH /companies/{company_id}/roles/{role_id}."""

    def test_update_custom_role_name(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Owner can update a custom role's name."""
        owner_token, company_id, _ = _setup_owner(test_client, db_session)

        # Create a custom role first
        create_resp = test_client.post(
            f"/api/v1/companies/{company_id}/roles",
            json={"name": "Original Name", "rank": 35},
            headers=_auth(owner_token),
        )
        assert create_resp.status_code == 201
        role_id = create_resp.json()["data"]["id"]

        # Update the name
        resp = test_client.patch(
            f"/api/v1/companies/{company_id}/roles/{role_id}",
            json={"name": "Updated Name"},
            headers=_auth(owner_token),
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Updated Name"

    def test_update_system_role_rejected(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """PATCH on a system role returns 403."""
        owner_token, company_id, role_ids = _setup_owner(test_client, db_session)

        resp = test_client.patch(
            f"/api/v1/companies/{company_id}/roles/{role_ids['admin']}",
            json={"name": "Renamed Admin"},
            headers=_auth(owner_token),
        )

        assert resp.status_code == 403


class TestDeleteRoleEndpoint:
    """Integration tests for DELETE /companies/{company_id}/roles/{role_id}."""

    def test_delete_empty_custom_role(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """DELETE custom role with no assignments returns 204."""
        owner_token, company_id, _ = _setup_owner(test_client, db_session)

        # Create a custom role
        create_resp = test_client.post(
            f"/api/v1/companies/{company_id}/roles",
            json={"name": "To Delete", "rank": 35},
            headers=_auth(owner_token),
        )
        role_id = create_resp.json()["data"]["id"]

        resp = test_client.delete(
            f"/api/v1/companies/{company_id}/roles/{role_id}",
            headers=_auth(owner_token),
        )

        assert resp.status_code == 204

    def test_delete_system_role_rejected(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """DELETE system role returns 403."""
        owner_token, company_id, role_ids = _setup_owner(test_client, db_session)

        resp = test_client.delete(
            f"/api/v1/companies/{company_id}/roles/{role_ids['viewer']}",
            headers=_auth(owner_token),
        )

        assert resp.status_code == 403

    def test_delete_role_with_assignments_rejected(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """DELETE role with active members returns 409."""
        owner_token, company_id, _ = _setup_owner(test_client, db_session)

        # Create a custom role
        create_resp = test_client.post(
            f"/api/v1/companies/{company_id}/roles",
            json={"name": "Assigned Role", "rank": 35},
            headers=_auth(owner_token),
        )
        role_id = create_resp.json()["data"]["id"]

        # Assign a member to this role
        user, _ = create_test_user(
            db_session, email=f"assigned_{uuid.uuid4().hex[:8]}@example.com"
        )
        create_test_member(
            db_session,
            company_id=uuid.UUID(company_id),
            user_id=user.id,
            role_id=uuid.UUID(role_id),
            status=MembershipStatus.active.value,
        )

        resp = test_client.delete(
            f"/api/v1/companies/{company_id}/roles/{role_id}",
            headers=_auth(owner_token),
        )

        assert resp.status_code == 409


class TestListRolesEndpoint:
    """Integration tests for GET /companies/{company_id}/roles."""

    def test_list_roles_returns_system_roles(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """GET /roles lists the 8 seeded system roles."""
        owner_token, company_id, _ = _setup_owner(test_client, db_session)

        resp = test_client.get(
            f"/api/v1/companies/{company_id}/roles",
            headers=_auth(owner_token),
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 8
        slugs = {r["slug"] for r in data}
        assert "owner" in slugs
        assert "admin" in slugs
        assert "viewer" in slugs


class TestPermissionsEndpoint:
    """Integration tests for GET /permissions."""

    def test_list_permissions_grouped(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """GET /permissions returns permissions grouped by module."""
        # Seed permissions first
        owner, owner_pw = create_test_user(
            db_session, email=f"perm_{uuid.uuid4().hex[:8]}@example.com"
        )
        owner_token = _login(test_client, owner.email, owner_pw)
        company = _create_company(test_client, owner_token)
        seed_system_roles(db_session, uuid.UUID(company["id"]), owner.id)

        resp = test_client.get(
            "/api/v1/permissions",
            headers=_auth(owner_token),
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 4  # members, roles, companies, profile
        modules = {g["module"] for g in data}
        assert "members" in modules
        assert "roles" in modules

    def test_permissions_requires_auth(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """GET /permissions without auth returns 401."""
        resp = test_client.get("/api/v1/permissions")
        assert resp.status_code == 401
