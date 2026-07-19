"""T067 [US4] — Integration tests for profile endpoints.

Tests: GET /profile, PATCH /profile (display_name, phone), GET preferences,
PUT preferences (language, timezone, date_format, theme), validation errors.

Uses the test_client / db_session fixtures from conftest.py.

Spec reference: contracts/profile-api.yaml, tasks T067.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_user_and_login(
    client: TestClient, db: Session, display_name: str = "Test User"
) -> tuple[str, str]:
    """Create a user, login, return (token, user_email)."""
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    user, password = create_test_user(db, email=email, display_name=display_name)
    token = _login(client, email, password)
    return token, email


# ---------------------------------------------------------------------------
# TestGetProfile
# ---------------------------------------------------------------------------


class TestGetProfile:
    def test_get_profile_returns_user_data(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """GET /profile returns the authenticated user's profile."""
        token, email = _create_user_and_login(test_client, db_session, "Alice Profile")

        resp = test_client.get("/api/v1/profile", headers=_auth(token))

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["email"] == email
        assert data["display_name"] == "Alice Profile"
        assert "avatar_url" in data
        assert "phone" in data
        assert "id" in data
        assert "created_at" in data

    def test_get_profile_requires_auth(self, test_client: TestClient) -> None:
        """GET /profile returns 401 without auth."""
        resp = test_client.get("/api/v1/profile")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# TestUpdateProfile
# ---------------------------------------------------------------------------


class TestUpdateProfile:
    def test_update_display_name(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """PATCH /profile updates display_name."""
        token, _ = _create_user_and_login(test_client, db_session)

        resp = test_client.patch(
            "/api/v1/profile",
            json={"display_name": "New Display Name"},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["display_name"] == "New Display Name"

    def test_update_phone(self, test_client: TestClient, db_session: Session) -> None:
        """PATCH /profile updates phone number."""
        token, _ = _create_user_and_login(test_client, db_session)

        resp = test_client.patch(
            "/api/v1/profile",
            json={"phone": "+44 7911 123456"},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["phone"] == "+44 7911 123456"

    def test_update_profile_requires_auth(self, test_client: TestClient) -> None:
        """PATCH /profile returns 401 without auth."""
        resp = test_client.patch("/api/v1/profile", json={"display_name": "X"})
        assert resp.status_code == 401

    def test_display_name_too_short_fails(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """display_name < 2 chars returns 422."""
        token, _ = _create_user_and_login(test_client, db_session)

        resp = test_client.patch(
            "/api/v1/profile",
            json={"display_name": "X"},
            headers=_auth(token),
        )

        assert resp.status_code == 422
