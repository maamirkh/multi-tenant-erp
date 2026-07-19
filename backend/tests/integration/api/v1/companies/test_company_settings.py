"""T055 [P] [US5] — Integration tests for PATCH /api/v1/companies/{id}/settings.

Spec ref: spec.md §4 US5, AC-006.
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


def _create_company(client: TestClient, token: str, name: str, email: str) -> str:
    resp = client.post(
        "/api/v1/companies",
        json={"legal_name": name, "email": email},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return resp.json()["data"]["id"]


class TestUpdateSettings:
    def test_known_key_with_valid_value_succeeds(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="settings_valid@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Settings Corp", "set@corp.com"
        )

        resp = test_client.patch(
            f"/api/v1/companies/{company_id}/settings",
            json={"settings": {"email_notifications_enabled": True}},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["settings"]["email_notifications_enabled"] is True

    def test_unknown_key_returns_400(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="settings_unknown@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(
            test_client, token, "Unknown Key Corp", "uk@corp.com"
        )

        resp = test_client.patch(
            f"/api/v1/companies/{company_id}/settings",
            json={"settings": {"unknown_setting_xyz": True}},
            headers=_auth(token),
        )

        assert resp.status_code == 400

    def test_settings_partial_merge_preserves_unmodified_keys(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, pwd = create_test_user(db_session, email="settings_merge@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(test_client, token, "Merge Corp", "merge@corp.com")

        # Set first key
        test_client.patch(
            f"/api/v1/companies/{company_id}/settings",
            json={"settings": {"email_notifications_enabled": True}},
            headers=_auth(token),
        )
        # Set second key — first should still be there
        resp = test_client.patch(
            f"/api/v1/companies/{company_id}/settings",
            json={"settings": {"approval_workflow_enabled": False}},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        settings = resp.json()["data"]["settings"]
        assert settings["email_notifications_enabled"] is True
        assert settings["approval_workflow_enabled"] is False
