"""T134 — Tenant isolation tests for Users & Roles.

Verifies that cross-tenant access to member and role resources is always
denied.  A member of Company A must not be able to read, create, or modify
any data belonging to Company B.

Note on HTTP status: the membership guard (``get_current_company_member``)
returns HTTP 403 when the requesting user is not an active member of the
targeted company.  This is consistent with the existing non-member guard
and provides an explicit denial rather than a 404 that could mislead callers
into believing the company resource does not exist.

Spec ref: spec.md §BR-055, FR-062, FR-069, tasks T134.
"""

from __future__ import annotations

import uuid
from typing import Any

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
    return str(resp.json()["data"]["access_token"])


def _auth(token: str) -> dict[str, Any]:
    return {"Authorization": f"Bearer {token}"}


def _create_company(client: TestClient, token: str, suffix: str) -> str:
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Tenant {suffix} Corp",
            "email": f"tenant_{suffix}@example.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, f"Company creation failed: {resp.text}"
    return str(resp.json()["data"]["id"])


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def two_tenants(test_client: TestClient, db_session: Session):
    """Seed two users, each owning one company with seeded system roles.

    Returns (token_a, company_a_id, token_b, company_b_id, member_b_id).
    ``member_b_id`` is the owner-member ID inside Company B, used to
    verify that Company A's token cannot access it.
    """
    prefix = uuid.uuid4().hex[:8]

    user_a, pwd_a = create_test_user(
        db_session, email=f"iso_tenant_a_{prefix}@example.com"
    )
    user_b, pwd_b = create_test_user(
        db_session, email=f"iso_tenant_b_{prefix}@example.com"
    )

    token_a = _login(test_client, user_a.email, pwd_a)
    token_b = _login(test_client, user_b.email, pwd_b)

    company_a_id = _create_company(test_client, token_a, f"a_{prefix}")
    company_b_id = _create_company(test_client, token_b, f"b_{prefix}")

    # Seed system roles for both companies so roles endpoint is populated
    a_uuid = uuid.UUID(company_a_id)
    b_uuid = uuid.UUID(company_b_id)
    seed_system_roles(db_session, a_uuid, user_a.id)
    seed_system_roles(db_session, b_uuid, user_b.id)

    # Ensure User A has an owner membership in Company A
    from modules.users_roles.repositories.role_repository import RoleRepository

    role_repo = RoleRepository(db_session)
    owner_role_b = role_repo.get_by_slug(b_uuid, "owner")
    assert owner_role_b is not None

    # Create User B as an explicit member in Company B with Owner role
    create_test_member(
        db_session,
        company_id=b_uuid,
        user_id=user_b.id,
        role_id=owner_role_b.id,
    )

    # Fetch User B's member ID in Company B for cross-tenant detail tests
    from modules.users_roles.repositories.company_member_repository import (
        CompanyMemberRepository,
    )

    member_repo = CompanyMemberRepository(db_session)
    member_b = member_repo.get_by_user_id(user_id=user_b.id, company_id=b_uuid)
    assert member_b is not None

    return token_a, company_a_id, token_b, company_b_id, str(member_b.id)


# ---------------------------------------------------------------------------
# Member endpoint isolation
# ---------------------------------------------------------------------------


class TestMemberTenantIsolation:
    """User A cannot access Company B's member resources."""

    def test_list_members_of_other_tenant_returns_403(
        self, test_client: TestClient, two_tenants: tuple[Any, ...]
    ) -> None:
        """GET /members on Company B using Company A's token returns 403."""
        token_a, _, _, company_b_id, _ = two_tenants
        resp = test_client.get(
            f"/api/v1/companies/{company_b_id}/members",
            headers=_auth(token_a),
        )
        assert resp.status_code == 403

    def test_get_specific_member_of_other_tenant_returns_403(
        self, test_client: TestClient, two_tenants: tuple[Any, ...]
    ) -> None:
        """GET /members/{id} on Company B using Company A's token returns 403."""
        token_a, _, _, company_b_id, member_b_id = two_tenants
        resp = test_client.get(
            f"/api/v1/companies/{company_b_id}/members/{member_b_id}",
            headers=_auth(token_a),
        )
        assert resp.status_code == 403

    def test_add_member_to_other_tenant_returns_403(
        self, test_client: TestClient, two_tenants: tuple[Any, ...]
    ) -> None:
        """POST /members on Company B using Company A's token returns 403."""
        token_a, _, _, company_b_id, _ = two_tenants
        resp = test_client.post(
            f"/api/v1/companies/{company_b_id}/members",
            json={"email": "victim@example.com", "role_id": str(uuid.uuid4())},
            headers=_auth(token_a),
        )
        assert resp.status_code == 403

    def test_patch_member_of_other_tenant_returns_403(
        self, test_client: TestClient, two_tenants: tuple[Any, ...]
    ) -> None:
        """PATCH /members/{id} on Company B using Company A's token returns 403."""
        token_a, _, _, company_b_id, member_b_id = two_tenants
        resp = test_client.patch(
            f"/api/v1/companies/{company_b_id}/members/{member_b_id}",
            json={"job_title": "Intruder"},
            headers=_auth(token_a),
        )
        assert resp.status_code == 403

    def test_cross_tenant_member_response_is_not_404(
        self, test_client: TestClient, two_tenants: tuple[Any, ...]
    ) -> None:
        """Cross-tenant member list must be explicitly denied (403), not 404."""
        token_a, _, _, company_b_id, _ = two_tenants
        resp = test_client.get(
            f"/api/v1/companies/{company_b_id}/members",
            headers=_auth(token_a),
        )
        # 403 signals an explicit denial; 404 would mask the reason
        assert resp.status_code == 403
        assert resp.status_code != 404


# ---------------------------------------------------------------------------
# Role endpoint isolation
# ---------------------------------------------------------------------------


class TestRoleTenantIsolation:
    """User A cannot access Company B's role resources."""

    def test_list_roles_of_other_tenant_returns_403(
        self, test_client: TestClient, two_tenants: tuple[Any, ...]
    ) -> None:
        """GET /roles on Company B using Company A's token returns 403."""
        token_a, _, _, company_b_id, _ = two_tenants
        resp = test_client.get(
            f"/api/v1/companies/{company_b_id}/roles",
            headers=_auth(token_a),
        )
        assert resp.status_code == 403

    def test_create_role_in_other_tenant_returns_403(
        self, test_client: TestClient, two_tenants: tuple[Any, ...]
    ) -> None:
        """POST /roles on Company B using Company A's token returns 403."""
        token_a, _, _, company_b_id, _ = two_tenants
        resp = test_client.post(
            f"/api/v1/companies/{company_b_id}/roles",
            json={"name": "Shadow Role", "rank": 30},
            headers=_auth(token_a),
        )
        assert resp.status_code == 403

    def test_get_role_of_other_tenant_returns_403(
        self, test_client: TestClient, two_tenants: tuple[Any, ...], db_session: Session
    ) -> None:
        """GET /roles/{role_id} on Company B using Company A's token returns 403."""
        token_a, _, _, company_b_id, _ = two_tenants
        from modules.users_roles.repositories.role_repository import RoleRepository

        role_repo = RoleRepository(db_session)
        owner_role = role_repo.get_by_slug(uuid.UUID(company_b_id), "owner")
        assert owner_role is not None

        resp = test_client.get(
            f"/api/v1/companies/{company_b_id}/roles/{owner_role.id}",
            headers=_auth(token_a),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Audit log isolation (via companies endpoint)
# ---------------------------------------------------------------------------


class TestAuditLogTenantIsolation:
    """User A cannot access Company B's audit log."""

    def test_audit_log_of_other_tenant_returns_403(
        self, test_client: TestClient, two_tenants: tuple[Any, ...]
    ) -> None:
        """GET /companies/{company_b_id}/audit-logs returns 403 for Company A user."""
        token_a, _, _, company_b_id, _ = two_tenants
        resp = test_client.get(
            f"/api/v1/companies/{company_b_id}/audit-logs",
            headers=_auth(token_a),
        )
        assert resp.status_code == 403
