"""T111 — Integration tests for POST /api/v1/auth/login.

Spec ref: spec.md §7 FR-001, US-01.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.auth.models.enums import AccountStatus
from tests.fixtures.auth_fixtures import create_test_user


class TestLoginValid:
    def test_valid_credentials_returns_200_with_tokens(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="login_valid@example.com")
        resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0


class TestLoginWrongPassword:
    def test_wrong_password_returns_401_invalid_credentials(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, _ = create_test_user(db_session, email="login_wrong@example.com")
        resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "WrongPass@12345"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


class TestLoginNonexistentEmail:
    def test_unknown_email_returns_401_same_message(
        self, test_client: TestClient
    ) -> None:
        resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@nowhere.example.com", "password": "AnyPass@1234567"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


class TestLoginLockedAccount:
    def test_locked_account_returns_423(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(
            db_session,
            email="login_locked@example.com",
            account_status=AccountStatus.LOCKED,
        )
        resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        assert resp.status_code == 423


class TestLoginEmailNormalization:
    def test_trailing_spaces_in_email_are_rejected(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, _ = create_test_user(db_session, email="trim_test@example.com")
        # FastAPI/Pydantic validates email format; trailing spaces fail validation.
        resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": "trim_test@example.com  ", "password": "WrongPass@1"},
        )
        # Either 422 (invalid format) or 401 (normalised and not found) is acceptable.
        assert resp.status_code in (401, 422)
