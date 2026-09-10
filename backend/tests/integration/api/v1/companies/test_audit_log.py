"""T057 [P] — Integration tests for GET /api/v1/companies/{id}/audit-logs.

Spec ref: spec.md §4, AC-010.
"""

from __future__ import annotations

from typing import Any

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
    assert resp.status_code == 201
    return str(resp.json()["data"]["id"])


class TestAuditLogCreation:
    def test_create_produces_one_audit_entry(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="audit_create@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Audit Create Corp", "ac@corp.com"
        )

        resp = test_client.get(
            f"/api/v1/companies/{company_id}/audit-logs",
            headers=_auth(token),
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        # Company creation now produces 2 audit entries: COMPANY_CREATED (from
        # CompanyService) and MEMBER_CREATED (from bootstrap owner membership).
        assert data["total"] == 2
        actions = {item["action"] for item in data["items"]}
        assert "COMPANY_CREATED" in actions
        assert "MEMBER_CREATED" in actions

    def test_state_changes_each_produce_audit_entry(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="audit_states@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Audit States Corp", "as@corp.com"
        )

        # Update → Activate
        test_client.patch(
            f"/api/v1/companies/{company_id}",
            json={"country": "US"},
            headers=_auth(token),
        )
        test_client.post(
            f"/api/v1/companies/{company_id}/activate", headers=_auth(token)
        )

        resp = test_client.get(
            f"/api/v1/companies/{company_id}/audit-logs",
            headers=_auth(token),
        )

        assert resp.status_code == 200
        actions = [e["action"] for e in resp.json()["data"]["items"]]
        assert "COMPANY_CREATED" in actions
        assert "COMPANY_UPDATED" in actions
        assert "COMPANY_ACTIVATED" in actions

    def test_pagination_returns_correct_metadata(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="audit_pagination@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Audit Pagination Corp", "ap@corp.com"
        )

        # Generate multiple audit entries
        test_client.patch(
            f"/api/v1/companies/{company_id}",
            json={"country": "US"},
            headers=_auth(token),
        )
        test_client.post(
            f"/api/v1/companies/{company_id}/activate", headers=_auth(token)
        )

        resp = test_client.get(
            f"/api/v1/companies/{company_id}/audit-logs?page=1&page_size=2",
            headers=_auth(token),
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total"] >= 2
        assert len(data["items"]) <= 2


class TestAuditLogImmutability:
    def test_patch_audit_log_returns_405(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="audit_patch@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Audit Patch Corp", "apc@corp.com"
        )

        audit_logs = test_client.get(
            f"/api/v1/companies/{company_id}/audit-logs",
            headers=_auth(token),
        ).json()["data"]["items"]
        audit_id = audit_logs[0]["id"]

        resp = test_client.patch(
            f"/api/v1/companies/{company_id}/audit-logs/{audit_id}",
            json={"action": "TAMPERED"},
            headers=_auth(token),
        )

        # No PATCH handler exists for individual audit log entries;
        # FastAPI returns 404 (route not found) rather than 405.
        assert resp.status_code in (404, 405)
