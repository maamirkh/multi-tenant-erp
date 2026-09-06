"""T086 [US8] — Integration tests for GET /companies/{company_id}/roles/{role_id}.

Tests: role detail view, full permission objects, permission module field,
member count accuracy, system role identification.

Spec reference: tasks T086, FR-074.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.users_roles.models.enums import MembershipStatus
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


def _create_company(client: TestClient, token: str) -> dict:
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"PermList Co {uuid.uuid4().hex[:6]}",
            "email": f"info@{uuid.uuid4().hex[:8]}.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, f"Company creation failed: {resp.text}"
    return resp.json()["data"]


def _setup_company(
    client: TestClient, db: Session, *, suffix: str = ""
) -> tuple[str, str, str, dict[str, str]]:
    """Create owner, company, seed roles, create owner membership.

    Returns:
        (company_id, owner_token, owner_member_id, role_ids_by_slug)
    """
    sfx = suffix or uuid.uuid4().hex[:8]
    owner, owner_pw = create_test_user(db, email=f"owner_{sfx}@example.com")
    owner_token = _login(client, owner.email, owner_pw)
    company = _create_company(client, owner_token)
    company_id = uuid.UUID(company["id"])

    roles = seed_system_roles(db, company_id, owner.id)
    role_map = {r.slug: r for r in roles}

    owner_member = create_test_member(
        db,
        company_id=company_id,
        user_id=owner.id,
        role_id=role_map["owner"].id,
        status=MembershipStatus.active.value,
        created_by=owner.id,
    )

    role_ids = {slug: str(r.id) for slug, r in role_map.items()}
    return str(company_id), owner_token, str(owner_member.id), role_ids


def _role_detail_url(company_id: str, role_id: str) -> str:
    return f"/api/v1/companies/{company_id}/roles/{role_id}"


# ---------------------------------------------------------------------------
# T086 — Role detail integration tests
# ---------------------------------------------------------------------------


class TestGetRoleDetail:
    """GET /companies/{company_id}/roles/{role_id} — role detail with permissions."""

    def test_get_role_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """GET /roles/{role_id} returns 200 for a valid role."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"rd_200_{sfx}"
        )
        resp = test_client.get(
            _role_detail_url(company_id, role_ids["owner"]),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200, resp.text

    def test_get_role_returns_role_detail_response(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Response contains all RoleDetailResponse fields."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"rd_fields_{sfx}"
        )
        resp = test_client.get(
            _role_detail_url(company_id, role_ids["admin"]),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        # All required fields present
        for field in (
            "id",
            "company_id",
            "name",
            "slug",
            "rank",
            "is_system",
            "is_active",
            "member_count",
            "permissions",
            "created_at",
            "updated_at",
        ):
            assert field in data, f"Missing field: {field}"

    def test_system_role_identified(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """System roles have is_system=True in the response."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"rd_sys_{sfx}"
        )
        resp = test_client.get(
            _role_detail_url(company_id, role_ids["owner"]),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["is_system"] is True

    def test_permissions_are_full_objects_not_codes(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """permissions field contains full PermissionResponse objects, not strings."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"rd_perms_{sfx}"
        )
        resp = test_client.get(
            _role_detail_url(company_id, role_ids["admin"]),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        permissions = resp.json()["data"]["permissions"]
        assert isinstance(permissions, list)
        if permissions:
            perm = permissions[0]
            for field in ("id", "code", "label", "module", "action"):
                assert field in perm, f"Permission missing field: {field}"

    def test_permissions_have_module_field(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Each permission has a non-empty module field (supports grouping)."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"rd_module_{sfx}"
        )
        resp = test_client.get(
            _role_detail_url(company_id, role_ids["owner"]),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        permissions = resp.json()["data"]["permissions"]
        for p in permissions:
            assert isinstance(p["module"], str) and p["module"], (
                "Module field missing/empty"
            )

    def test_permissions_sorted_by_module_then_code(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Permissions are returned sorted by module then code."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"rd_sort_{sfx}"
        )
        resp = test_client.get(
            _role_detail_url(company_id, role_ids["owner"]),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        permissions = resp.json()["data"]["permissions"]
        if len(permissions) > 1:
            keys = [(p["module"], p["code"]) for p in permissions]
            assert keys == sorted(keys), "Permissions not sorted by module then code"

    def test_member_count_accurate(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """member_count reflects actual members assigned to the role."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"rd_cnt_{sfx}"
        )
        # Owner has 1 member (the owner created in setup)
        resp = test_client.get(
            _role_detail_url(company_id, role_ids["owner"]),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["member_count"] == 1

    def test_member_count_zero_for_unassigned_role(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """member_count is 0 for roles with no assigned members."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"rd_zero_{sfx}"
        )
        # Viewer role has no members in this setup
        resp = test_client.get(
            _role_detail_url(company_id, role_ids["viewer"]),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["member_count"] == 0

    def test_get_role_not_found_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """GET /roles/{non_existent_role_id} returns 404."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, _ = _setup_company(
            test_client, db_session, suffix=f"rd_404_{sfx}"
        )
        fake_role_id = str(uuid.uuid4())
        resp = test_client.get(
            _role_detail_url(company_id, fake_role_id),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 404

    def test_get_role_requires_auth(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """GET /roles/{role_id} without auth returns 401."""
        fake_company = str(uuid.uuid4())
        fake_role = str(uuid.uuid4())
        resp = test_client.get(_role_detail_url(fake_company, fake_role))
        assert resp.status_code == 401

    def test_role_detail_for_custom_role_with_permissions(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Custom role GET returns its assigned permissions."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, _ = _setup_company(
            test_client, db_session, suffix=f"rd_custom_{sfx}"
        )
        # Create a custom role with specific permissions
        create_resp = test_client.post(
            f"/api/v1/companies/{company_id}/roles",
            json={
                "name": f"Custom Role {sfx}",
                "rank": 30,
                "permission_codes": ["members.read", "roles.read"],
            },
            headers=_auth(owner_token),
        )
        assert create_resp.status_code == 201
        role_id = create_resp.json()["data"]["id"]

        detail_resp = test_client.get(
            _role_detail_url(company_id, role_id),
            headers=_auth(owner_token),
        )
        assert detail_resp.status_code == 200
        data = detail_resp.json()["data"]
        assert data["is_system"] is False
        codes = {p["code"] for p in data["permissions"]}
        assert "members.read" in codes
        assert "roles.read" in codes
