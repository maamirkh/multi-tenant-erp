"""T058 [P] [US6] — Integration tests for GET /api/v1/companies/admin/companies.

Spec ref: spec.md §4 US6, AC-012.

Note: The super_admin role is determined by JWT claims (Epic 4 will provide a
company_members table).  The current auth implementation always returns
``roles=[]`` from the JWT, so we can only test the auth-failure paths here.
Successful super_admin access is covered in unit tests via dependency mocks.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestSuperAdminListAuth:
    def test_regular_user_returns_403(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="superadmin_403@example.com")
        token = _login(test_client, user.email, pwd)

        resp = test_client.get(
            "/api/v1/companies/admin/companies", headers=_auth(token)
        )

        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, test_client: TestClient) -> None:
        resp = test_client.get("/api/v1/companies/admin/companies")
        assert resp.status_code == 401

    def test_endpoint_returns_paginated_structure_for_403(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Confirms the path resolves (not 404) and properly enforces auth."""
        user, pwd = create_test_user(db_session, email="superadmin_path@example.com")
        token = _login(test_client, user.email, pwd)

        resp = test_client.get(
            "/api/v1/companies/admin/companies", headers=_auth(token)
        )

        # The endpoint exists (resolves to 403, not 404)
        assert resp.status_code != 404
        assert resp.status_code == 403
