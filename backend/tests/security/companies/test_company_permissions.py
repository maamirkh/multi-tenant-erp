"""T112 [P] — Company permissions matrix tests.

Phase 3 RBAC simplification (spec.md §8.2):
  - Owner:           full CRUD on their company.
  - Non-owner:       403 on all company-specific endpoints.
  - Unauthenticated: 401 on all endpoints.
  - SuperAdmin:      full access + admin list endpoint.

Note: Epic 4 roles (admin, manager, accountant, sales, inventory) are deferred
to the company_members table (see dependencies.py TODO Epic-4 comments).
SuperAdmin tests inject the role via dependency override because the JWT
implementation currently returns roles=[] (Epic 4 will populate from DB).

Spec ref: spec.md §8.2, Phase 3 RBAC simplification.
"""

from __future__ import annotations

import uuid as _uuid
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return str(resp.json()["data"]["access_token"])


def _auth(token: str) -> dict[str, Any]:
    return {"Authorization": f"Bearer {token}"}


def _create_company(client: TestClient, token: str, name: str, email: str) -> str:
    resp = client.post(
        "/api/v1/companies",
        json={"legal_name": name, "email": email},
        headers=_auth(token),
    )
    assert resp.status_code == 201, f"Company creation failed: {resp.json()}"
    return str(resp.json()["data"]["id"])


@pytest.fixture()
def owner_and_company(test_client: TestClient, db_session: Session):
    """Return (owner_token, stranger_token, company_id)."""
    prefix = _uuid.uuid4().hex[:8]

    owner, pwd_owner = create_test_user(
        db_session, email=f"perm_owner_{prefix}@example.com"
    )
    stranger, pwd_stranger = create_test_user(
        db_session, email=f"perm_stranger_{prefix}@example.com"
    )

    token_owner = _login(test_client, owner.email, pwd_owner)
    token_stranger = _login(test_client, stranger.email, pwd_stranger)

    company_id = _create_company(
        test_client,
        token_owner,
        f"Perm Test Corp {prefix}",
        f"perm_{prefix}@example.com",
    )

    return token_owner, token_stranger, company_id


class TestOwnerPermissions:
    """Owner has full read/write access to their own company."""

    def test_owner_can_get_company(
        self, test_client: TestClient, owner_and_company: tuple[Any, ...]
    ) -> None:
        token_owner, _, company_id = owner_and_company
        resp = test_client.get(
            f"/api/v1/companies/{company_id}", headers=_auth(token_owner)
        )
        assert resp.status_code == 200

    def test_owner_can_patch_company(
        self, test_client: TestClient, owner_and_company: tuple[Any, ...]
    ) -> None:
        token_owner, _, company_id = owner_and_company
        resp = test_client.patch(
            f"/api/v1/companies/{company_id}",
            json={"trade_name": "Updated"},
            headers=_auth(token_owner),
        )
        assert resp.status_code == 200

    def test_owner_can_view_audit_log(
        self, test_client: TestClient, owner_and_company: tuple[Any, ...]
    ) -> None:
        token_owner, _, company_id = owner_and_company
        resp = test_client.get(
            f"/api/v1/companies/{company_id}/audit-logs", headers=_auth(token_owner)
        )
        assert resp.status_code == 200


class TestNonOwnerPermissions:
    """Non-owner authenticated users receive 403 on company-specific operations."""

    def test_stranger_cannot_get_company(
        self, test_client: TestClient, owner_and_company: tuple[Any, ...]
    ) -> None:
        _, token_stranger, company_id = owner_and_company
        resp = test_client.get(
            f"/api/v1/companies/{company_id}", headers=_auth(token_stranger)
        )
        assert resp.status_code == 403

    def test_stranger_cannot_patch_company(
        self, test_client: TestClient, owner_and_company: tuple[Any, ...]
    ) -> None:
        _, token_stranger, company_id = owner_and_company
        resp = test_client.patch(
            f"/api/v1/companies/{company_id}",
            json={"trade_name": "Hacked"},
            headers=_auth(token_stranger),
        )
        assert resp.status_code == 403

    def test_stranger_cannot_view_audit_log(
        self, test_client: TestClient, owner_and_company: tuple[Any, ...]
    ) -> None:
        _, token_stranger, company_id = owner_and_company
        resp = test_client.get(
            f"/api/v1/companies/{company_id}/audit-logs", headers=_auth(token_stranger)
        )
        assert resp.status_code == 403

    def test_stranger_cannot_add_address(
        self, test_client: TestClient, owner_and_company: tuple[Any, ...]
    ) -> None:
        _, token_stranger, company_id = owner_and_company
        resp = test_client.post(
            f"/api/v1/companies/{company_id}/addresses",
            json={
                "address_type": "billing",
                "street_line_1": "1 Hack St",
                "city": "Hackville",
                "country": "US",
            },
            headers=_auth(token_stranger),
        )
        assert resp.status_code == 403


class TestUnauthenticatedPermissions:
    """Unauthenticated requests are rejected with 401."""

    def test_unauthenticated_cannot_create_company(
        self, test_client: TestClient
    ) -> None:
        resp = test_client.post(
            "/api/v1/companies",
            json={"legal_name": "Anon Corp", "email": "anon@example.com"},
        )
        assert resp.status_code == 401

    def test_unauthenticated_cannot_list_admin_companies(
        self, test_client: TestClient
    ) -> None:
        resp = test_client.get("/api/v1/companies/admin/companies")
        assert resp.status_code == 401

    def test_unauthenticated_cannot_get_company(self, test_client: TestClient) -> None:
        import uuid

        resp = test_client.get(f"/api/v1/companies/{uuid.uuid4()}")
        assert resp.status_code == 401


class TestSuperAdminPermissions:
    """SuperAdmin (injected via dependency override) can access the admin list endpoint."""

    def test_super_admin_can_list_all_companies(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        from core.auth.dependencies import require_authenticated
        from core.auth.interfaces import CurrentUser

        prefix = _uuid.uuid4().hex[:8]
        sa_user, _ = create_test_user(db_session, email=f"sa_perm_{prefix}@example.com")

        def _fake_super_admin() -> CurrentUser:
            mock = MagicMock(spec=CurrentUser)
            mock.user_id = sa_user.id
            mock.email = sa_user.email
            mock.roles = ["super_admin"]
            return mock

        app = cast(FastAPI, test_client.app)
        app.dependency_overrides[require_authenticated] = _fake_super_admin
        try:
            resp = test_client.get(
                "/api/v1/companies/admin/companies?page=1&page_size=10"
            )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()
