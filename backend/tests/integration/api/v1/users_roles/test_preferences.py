"""T067 [US4] — Integration tests for preferences endpoints.

Tests: GET /preferences (with and without existing record), PUT /preferences
(valid language, timezone, date_format, theme), invalid values return 400,
auth required.

Uses the test_client / db_session fixtures from conftest.py.

Spec reference: contracts/profile-api.yaml, tasks T067.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return str(resp.json()["data"]["access_token"])


def _auth(token: str) -> dict[str, Any]:
    return {"Authorization": f"Bearer {token}"}


def _create_user_and_login(client: TestClient, db: Session) -> str:
    """Create a user, login, return token."""
    email = f"pref_{uuid.uuid4().hex[:8]}@example.com"
    user, password = create_test_user(db, email=email)
    return _login(client, email, password)


# ---------------------------------------------------------------------------
# TestGetPreferences
# ---------------------------------------------------------------------------


class TestGetPreferences:
    def test_returns_defaults_on_first_call(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """GET /preferences creates defaults and returns them."""
        token = _create_user_and_login(test_client, db_session)

        resp = test_client.get("/api/v1/preferences", headers=_auth(token))

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["language"] == "en"
        assert data["timezone"] == "UTC"
        assert data["theme"] == "system"
        assert data["date_format"] == "YYYY-MM-DD"
        assert "notification_preferences" in data

    def test_requires_auth(self, test_client: TestClient) -> None:
        """GET /preferences returns 401 without auth."""
        resp = test_client.get("/api/v1/preferences")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# TestUpdatePreferences
# ---------------------------------------------------------------------------


class TestUpdatePreferences:
    def test_update_language(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """PUT /preferences updates language."""
        token = _create_user_and_login(test_client, db_session)

        resp = test_client.put(
            "/api/v1/preferences",
            json={"language": "fr"},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["language"] == "fr"

    def test_update_timezone(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """PUT /preferences updates timezone."""
        token = _create_user_and_login(test_client, db_session)

        resp = test_client.put(
            "/api/v1/preferences",
            json={"timezone": "America/New_York"},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["timezone"] == "America/New_York"

    def test_update_theme(self, test_client: TestClient, db_session: Session) -> None:
        """PUT /preferences updates theme."""
        token = _create_user_and_login(test_client, db_session)

        resp = test_client.put(
            "/api/v1/preferences",
            json={"theme": "dark"},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["theme"] == "dark"

    def test_update_date_format(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """PUT /preferences updates date_format."""
        token = _create_user_and_login(test_client, db_session)

        resp = test_client.put(
            "/api/v1/preferences",
            json={"date_format": "DD/MM/YYYY"},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["date_format"] == "DD/MM/YYYY"

    def test_invalid_timezone_returns_400(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """PUT /preferences with invalid timezone returns 400."""
        token = _create_user_and_login(test_client, db_session)

        resp = test_client.put(
            "/api/v1/preferences",
            json={"timezone": "Not/A/ValidTimezone"},
            headers=_auth(token),
        )

        assert resp.status_code == 400

    def test_invalid_theme_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """PUT /preferences with invalid theme (not in enum) returns 422."""
        token = _create_user_and_login(test_client, db_session)

        resp = test_client.put(
            "/api/v1/preferences",
            json={"theme": "neon"},
            headers=_auth(token),
        )

        # Pydantic Literal validation catches this before the service
        assert resp.status_code == 422

    def test_requires_auth(self, test_client: TestClient) -> None:
        """PUT /preferences returns 401 without auth."""
        resp = test_client.put("/api/v1/preferences", json={"theme": "dark"})
        assert resp.status_code == 401
