"""T114 — Integration tests for GET /api/v1/auth/me.

Spec ref: spec.md §7 FR-006, US-06.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user


def _get_access_token(client: TestClient, db: Session, email: str) -> str:
    user, password = create_test_user(db, email=email)
    resp = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": password}
    )
    return resp.json()["data"]["access_token"]


class TestGetMeValid:
    def test_valid_jwt_returns_200_with_user_data(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _get_access_token(test_client, db_session, "me_valid@example.com")
        resp = test_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        profile = resp.json()["data"]
        assert "email" in profile
        assert "display_name" in profile
        assert "user_id" in profile

    def test_response_excludes_credentials(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _get_access_token(test_client, db_session, "me_nocred@example.com")
        resp = test_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        body = str(resp.json())
        assert "password" not in body
        assert "password_hash" not in body


class TestGetMeInvalid:
    def test_no_credential_returns_401(self, test_client: TestClient) -> None:
        resp = test_client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_expired_jwt_returns_401(self, test_client: TestClient) -> None:
        resp = test_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.xyz"},
        )
        assert resp.status_code == 401
