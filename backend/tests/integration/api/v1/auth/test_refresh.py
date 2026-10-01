"""T113 — Integration tests for POST /api/v1/auth/refresh.

Spec ref: spec.md §7 FR-007, US-03.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user


def _login(client: TestClient, email: str, password: str) -> dict[str, Any]:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200
    return dict(resp.json()["data"])


class TestRefreshValid:
    def test_valid_token_returns_200_with_new_tokens(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="refresh_valid@example.com")
        tokens = _login(test_client, user.email, password)

        resp = test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert resp.status_code == 200
        new_data = resp.json()["data"]
        assert "access_token" in new_data
        assert "refresh_token" in new_data

    def test_old_token_rejected_after_rotation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(
            db_session, email="refresh_rotate@example.com"
        )
        tokens = _login(test_client, user.email, password)
        old_rt = tokens["refresh_token"]

        # Rotate.
        test_client.post("/api/v1/auth/refresh", json={"refresh_token": old_rt})

        # Old token must be rejected.
        retry = test_client.post("/api/v1/auth/refresh", json={"refresh_token": old_rt})
        assert retry.status_code in (400, 401)


class TestRefreshInvalid:
    def test_expired_or_invalid_token_returns_4xx(
        self, test_client: TestClient
    ) -> None:
        resp = test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "totally-invalid-token"},
        )
        assert resp.status_code in (400, 401)


class TestConcurrentRefresh:
    def test_second_use_of_same_token_returns_401(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Simulates concurrent refresh by calling the same token twice sequentially.

        In a real concurrent scenario only one should win; sequentially we
        verify the second call is always rejected after the first rotation.
        """
        user, password = create_test_user(
            db_session, email="refresh_concurrent@example.com"
        )
        tokens = _login(test_client, user.email, password)
        rt = tokens["refresh_token"]

        first = test_client.post("/api/v1/auth/refresh", json={"refresh_token": rt})
        second = test_client.post("/api/v1/auth/refresh", json={"refresh_token": rt})

        assert first.status_code == 200
        assert second.status_code in (400, 401)
