"""Integration tests for GET /api/v1/companies (list the current user's
own companies).

Regression guard for a real defect found live during Epic 9A Phase 17
T220 browser E2E verification: the frontend's `listCompanies()`
(`lib/api/companies.ts`) has always called `GET /api/v1/companies`, and
`CompanyService.list_user_companies()` existed to back it, but no router
endpoint ever wired the two together — the route simply did not exist
(405 Method Not Allowed), breaking the "My Companies" page for every
user. Only real end-to-end browser testing surfaced this; it is
orthogonal to Epic 9A's own scope but was blocking T220/T221's tenant
navigation, so it is fixed here per the master prompt's "fix only the
smallest root cause" rule.
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


def _create_company(client: TestClient, token: str, name: str) -> str:
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": name,
            "email": f"{name.lower().replace(' ', '')}@example.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return resp.json()["data"]["id"]


class TestListMyCompanies:
    def test_returns_only_the_current_users_own_companies(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="list_mine@example.com")
        token = _login(test_client, user.email, password)
        company_a_id = _create_company(test_client, token, "List Mine Corp A")
        company_b_id = _create_company(test_client, token, "List Mine Corp B")

        other, other_pwd = create_test_user(db_session, email="list_other@example.com")
        other_token = _login(test_client, other.email, other_pwd)
        _create_company(test_client, other_token, "List Other Corp")

        resp = test_client.get("/api/v1/companies", headers=_auth(token))

        assert resp.status_code == 200
        ids = {item["id"] for item in resp.json()["data"]}
        assert ids == {company_a_id, company_b_id}

    def test_returns_empty_list_for_a_user_with_no_companies(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="list_none@example.com")
        token = _login(test_client, user.email, password)

        resp = test_client.get("/api/v1/companies", headers=_auth(token))

        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_no_auth_returns_401(self, test_client: TestClient) -> None:
        resp = test_client.get("/api/v1/companies")
        assert resp.status_code == 401
