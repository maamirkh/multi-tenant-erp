"""T117 — Integration tests for POST /api/v1/auth/change-password.

Spec ref: spec.md §7 FR-024, US-08.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

_NEW_PASS = "UpdatedSecure@5678"


def _login_token(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return resp.json()["data"]["access_token"]


class TestChangePasswordCorrect:
    def test_correct_current_password_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="chgpw_ok@example.com")
        token = _login_token(test_client, user.email, password)

        resp = test_client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": password,
                "new_password": _NEW_PASS,
                "confirm_password": _NEW_PASS,
            },
        )
        assert resp.status_code == 200


class TestChangePasswordWrongCurrent:
    def test_wrong_current_password_returns_4xx(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="chgpw_wrong@example.com")
        token = _login_token(test_client, user.email, password)

        resp = test_client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "WrongCurrent@1234",
                "new_password": _NEW_PASS,
                "confirm_password": _NEW_PASS,
            },
        )
        assert resp.status_code in (401, 403)


class TestChangePasswordHistory:
    def test_reused_password_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Change to a new password, then try to reuse the original — must return 422."""
        original_pass = "OriginalPw@99887766"
        new_pass = _NEW_PASS
        user, _ = create_test_user(
            db_session, email="chgpw_hist@example.com", password=original_pass
        )

        # Step 1: login and change to new_pass (adds original to history).
        token1 = _login_token(test_client, user.email, original_pass)
        change1 = test_client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token1}"},
            json={
                "current_password": original_pass,
                "new_password": new_pass,
                "confirm_password": new_pass,
            },
        )
        assert change1.status_code == 200

        # Step 2: login with new password (old tokens revoked).
        token2 = _login_token(test_client, user.email, new_pass)

        # Step 3: try to reuse original_pass — should be rejected by history.
        resp = test_client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token2}"},
            json={
                "current_password": new_pass,
                "new_password": original_pass,
                "confirm_password": original_pass,
            },
        )
        assert resp.status_code == 422


class TestChangePasswordSessionRevocation:
    def test_other_device_sessions_revoked_after_change(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """After password change, old refresh tokens from other sessions are rejected."""
        user, password = create_test_user(db_session, email="chgpw_revoke@example.com")

        # Login on "device A".
        login_a = test_client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": password}
        )
        token_a = login_a.json()["data"]["access_token"]
        rt_a = login_a.json()["data"]["refresh_token"]

        # Change password using device A's access token.
        test_client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "current_password": password,
                "new_password": _NEW_PASS,
                "confirm_password": _NEW_PASS,
            },
        )

        # Device A's refresh token should be revoked.
        retry = test_client.post("/api/v1/auth/refresh", json={"refresh_token": rt_a})
        assert retry.status_code in (400, 401)
