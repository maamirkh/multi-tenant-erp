"""T051 [P] [US1] — Integration tests for GET /api/v1/companies/{id}.

Spec ref: spec.md §4 US1, AC-002.
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


def _create_company(client: TestClient, token: str, name: str = "Get Test Corp") -> str:
    """Create a company and return its UUID."""
    resp = client.post(
        "/api/v1/companies",
        json={"legal_name": name, "email": "get@testcorp.com"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return resp.json()["data"]["id"]


class TestGetCompanyValid:
    def test_get_valid_company_returns_200_with_all_fields(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="get_valid@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token)

        resp = test_client.get(f"/api/v1/companies/{company_id}", headers=_auth(token))

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == company_id
        assert data["legal_name"] == "Get Test Corp"
        assert data["owner_id"] == str(user.id)
        assert "addresses" in data
        assert "settings" in data


class TestGetCompanyNotFound:
    def test_get_nonexistent_company_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="get_404@example.com")
        token = _login(test_client, user.email, password)

        resp = test_client.get(
            "/api/v1/companies/00000000-0000-0000-0000-000000000000",
            headers=_auth(token),
        )

        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "COMPANY_NOT_FOUND"


class TestGetCompanyCrossTenant:
    def test_cross_tenant_get_returns_403(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        # Owner creates a company
        owner, owner_pwd = create_test_user(db_session, email="get_owner@example.com")
        owner_token = _login(test_client, owner.email, owner_pwd)
        company_id = _create_company(test_client, owner_token, name="Owner's Corp")

        # Different user tries to access
        other, other_pwd = create_test_user(db_session, email="get_other@example.com")
        other_token = _login(test_client, other.email, other_pwd)

        resp = test_client.get(
            f"/api/v1/companies/{company_id}", headers=_auth(other_token)
        )

        assert resp.status_code == 403


class TestGetCompanyUnauthenticated:
    def test_no_auth_returns_401(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="get_noauth@example.com")
        token = _login(test_client, user.email, password)
        company_id = _create_company(test_client, token, name="No Auth Corp")

        resp = test_client.get(f"/api/v1/companies/{company_id}")
        assert resp.status_code == 401
