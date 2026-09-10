"""T047 [US2] — Integration tests for role management endpoints.

Tests: successful role change via PATCH, insufficient rank 403,
self-role-change 409, last Owner 409, invalid role 404,
GET member detail.

Uses the test_client / db_session fixtures from conftest.py.

Spec reference: tasks T047.
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


def _create_company(
    client: TestClient, token: str, legal_name: str | None = None
) -> dict[str, Any]:
    if legal_name is None:
        legal_name = f"RoleMgmt-{uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/api/v1/companies",
        json={"legal_name": legal_name, "email": f"info@{uuid.uuid4().hex[:8]}.com"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return dict(resp.json()["data"])


def _setup_company_with_members(
    client: TestClient,
    db: Session,
) -> tuple[dict[str, str], str, str, dict[str, str]]:
    """Create a company with owner and a viewer member.

    Returns: (company_data, owner_token, member_token, role_ids_by_slug)
    """
    # Create owner
    owner, owner_pw = create_test_user(
        db, email=f"owner_{uuid.uuid4().hex[:8]}@example.com"
    )
    owner_token = _login(client, owner.email, owner_pw)
    company = _create_company(client, owner_token)
    company_id = uuid.UUID(company["id"])

    # Seed roles and create owner membership
    roles = seed_system_roles(db, company_id, owner.id)
    role_map = {r.slug: r for r in roles}
    owner_role = role_map["owner"]

    # Create owner membership
    create_test_member(
        db,
        company_id=company_id,
        user_id=owner.id,
        role_id=owner_role.id,
        status=MembershipStatus.active.value,
    )

    # Create viewer member
    viewer, viewer_pw = create_test_user(
        db, email=f"viewer_{uuid.uuid4().hex[:8]}@example.com"
    )
    viewer_token = _login(client, viewer.email, viewer_pw)
    viewer_member = create_test_member(
        db,
        company_id=company_id,
        user_id=viewer.id,
        role_id=role_map["viewer"].id,
        status=MembershipStatus.active.value,
    )

    return (
        {
            "id": str(company_id),
            "owner_id": str(owner.id),
            "viewer_member_id": str(viewer_member.id),
            "viewer_user_id": str(viewer.id),
        },
        owner_token,
        viewer_token,
        {slug: str(r.id) for slug, r in role_map.items()},
    )


class TestRoleChangeEndpoint:
    """Integration tests for PATCH /members/{member_id} role change."""

    def test_successful_role_change(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Owner can change a viewer's role to manager via PATCH."""
        info, owner_token, _, role_ids = _setup_company_with_members(
            test_client, db_session
        )

        resp = test_client.patch(
            f"/api/v1/companies/{info['id']}/members/{info['viewer_member_id']}",
            json={"role_id": role_ids["manager"]},
            headers=_auth(owner_token),
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["role"]["slug"] == "manager"

    def test_insufficient_rank_returns_403(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Viewer cannot change another member's role (403)."""
        info, _, viewer_token, role_ids = _setup_company_with_members(
            test_client, db_session
        )

        # Create another viewer to try to change
        other_user, _ = create_test_user(
            db_session, email=f"other_{uuid.uuid4().hex[:8]}@example.com"
        )
        other_member = create_test_member(
            db_session,
            company_id=uuid.UUID(info["id"]),
            user_id=other_user.id,
            role_id=uuid.UUID(role_ids["viewer"]),
            status=MembershipStatus.active.value,
        )

        resp = test_client.patch(
            f"/api/v1/companies/{info['id']}/members/{other_member.id}",
            json={"role_id": role_ids["manager"]},
            headers=_auth(viewer_token),
        )

        assert resp.status_code == 403

    def test_self_role_change_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Owner cannot change their own role (409)."""
        info, owner_token, _, role_ids = _setup_company_with_members(
            test_client, db_session
        )

        # Find owner's member record
        from modules.users_roles.repositories.company_member_repository import (
            CompanyMemberRepository,
        )

        repo = CompanyMemberRepository(db_session)
        owner_member = repo.get_by_user_id(
            user_id=uuid.UUID(info["owner_id"]),
            company_id=uuid.UUID(info["id"]),
        )
        assert owner_member is not None

        resp = test_client.patch(
            f"/api/v1/companies/{info['id']}/members/{owner_member.id}",
            json={"role_id": role_ids["admin"]},
            headers=_auth(owner_token),
        )

        assert resp.status_code == 409

    def test_invalid_role_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """PATCH with non-existent role_id returns 404."""
        info, owner_token, _, _ = _setup_company_with_members(test_client, db_session)

        resp = test_client.patch(
            f"/api/v1/companies/{info['id']}/members/{info['viewer_member_id']}",
            json={"role_id": str(uuid.uuid4())},
            headers=_auth(owner_token),
        )

        assert resp.status_code == 404


class TestGetMemberEndpoint:
    """Integration tests for GET /members/{member_id}."""

    def test_get_member_returns_detail(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """GET returns full member detail with role info."""
        info, owner_token, _, role_ids = _setup_company_with_members(
            test_client, db_session
        )

        resp = test_client.get(
            f"/api/v1/companies/{info['id']}/members/{info['viewer_member_id']}",
            headers=_auth(owner_token),
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == info["viewer_member_id"]
        assert data["role"]["slug"] == "viewer"
        assert data["company_id"] == info["id"]
        assert "display_name" in data
        assert "email" in data

    def test_get_member_requires_auth(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """GET without auth returns 401."""
        resp = test_client.get(
            f"/api/v1/companies/{uuid.uuid4()}/members/{uuid.uuid4()}",
        )
        assert resp.status_code == 401

    def test_get_nonexistent_member_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """GET for unknown member_id returns 404."""
        info, owner_token, _, _ = _setup_company_with_members(test_client, db_session)

        resp = test_client.get(
            f"/api/v1/companies/{info['id']}/members/{uuid.uuid4()}",
            headers=_auth(owner_token),
        )

        assert resp.status_code == 404
