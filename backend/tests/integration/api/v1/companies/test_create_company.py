"""T050 [US1] — Integration tests for POST /api/v1/companies.

Spec ref: spec.md §4 US1, AC-001.
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


class TestCreateCompanyValid:
    def test_valid_data_returns_201_with_uuid_id(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="create_valid@example.com")
        token = _login(test_client, user.email, password)

        resp = test_client.post(
            "/api/v1/companies",
            json={"legal_name": "Acme Corp", "email": "contact@acme.com"},
            headers=_auth(token),
        )

        assert resp.status_code == 201
        data = resp.json()["data"]
        assert "id" in data
        assert len(data["id"]) == 36  # UUID4 string
        assert data["legal_name"] == "Acme Corp"
        assert data["status"] == "pending_setup"
        assert data["owner_id"] == str(user.id)

    def test_auto_derived_slug_from_legal_name(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="create_slug@example.com")
        token = _login(test_client, user.email, password)

        resp = test_client.post(
            "/api/v1/companies",
            json={"legal_name": "My Awesome Startup", "email": "hello@startup.com"},
            headers=_auth(token),
        )

        assert resp.status_code == 201
        assert resp.json()["data"]["slug"] == "my-awesome-startup"

    def test_audit_log_created_on_company_creation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="create_audit@example.com")
        token = _login(test_client, user.email, password)

        resp = test_client.post(
            "/api/v1/companies",
            json={"legal_name": "Audit Test LLC", "email": "audit@test.com"},
            headers=_auth(token),
        )
        assert resp.status_code == 201
        company_id = resp.json()["data"]["id"]

        audit_resp = test_client.get(
            f"/api/v1/companies/{company_id}/audit-logs",
            headers=_auth(token),
        )
        assert audit_resp.status_code == 200
        items = audit_resp.json()["data"]["items"]
        assert any(e["action"] == "COMPANY_CREATED" for e in items)


class TestCreateCompanyConflict:
    def test_duplicate_legal_name_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="create_dup@example.com")
        token = _login(test_client, user.email, password)

        payload = {"legal_name": "Duplicate Corp", "email": "dup@corp.com"}
        test_client.post("/api/v1/companies", json=payload, headers=_auth(token))
        resp = test_client.post("/api/v1/companies", json=payload, headers=_auth(token))

        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "COMPANY_NAME_CONFLICT"


class TestCreateCompanyValidation:
    def test_invalid_currency_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="create_cur@example.com")
        token = _login(test_client, user.email, password)

        resp = test_client.post(
            "/api/v1/companies",
            json={
                "legal_name": "Cur Corp",
                "email": "cur@corp.com",
                "default_currency": "XYZ",
            },
            headers=_auth(token),
        )

        assert resp.status_code == 422

    def test_missing_email_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(
            db_session, email="create_noemail@example.com"
        )
        token = _login(test_client, user.email, password)

        resp = test_client.post(
            "/api/v1/companies",
            json={"legal_name": "No Email Corp"},
            headers=_auth(token),
        )

        assert resp.status_code == 422

    def test_missing_auth_returns_401(self, test_client: TestClient) -> None:
        resp = test_client.post(
            "/api/v1/companies",
            json={"legal_name": "Unauth Corp", "email": "u@corp.com"},
        )
        assert resp.status_code == 401
