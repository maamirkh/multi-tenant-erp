"""T112 — Integration tests for POST /api/v1/auth/logout.

Spec ref: spec.md §7 FR-009, US-02.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user


class TestLogoutAuthenticated:
    def test_authenticated_logout_returns_success(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="logout_auth@example.com")
        login_resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        access_token = login_resp.json()["data"]["access_token"]

        resp = test_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        # Spec allows 200 (with body) or 204 (no body).
        assert resp.status_code in (200, 204)

    def test_refresh_token_rejected_after_logout(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="logout_rt@example.com")
        login_resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        tokens = login_resp.json()["data"]
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        # Logout.
        test_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        # Former refresh token must now be rejected.
        retry = test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert retry.status_code in (400, 401)


class TestLogoutUnauthenticated:
    def test_logout_without_token_returns_401(self, test_client: TestClient) -> None:
        resp = test_client.post("/api/v1/auth/logout")
        assert resp.status_code == 401
