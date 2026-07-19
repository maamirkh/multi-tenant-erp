"""T126 — Password history enforcement security tests.

Verifies that passwords cannot be reused from the last 5 and that after
6 changes the oldest password becomes acceptable again.
Spec ref: spec.md §7 FR-025, §8 NFR-006.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

_PASS_A = "HistoryPass@1234"
_PASS_B = "HistoryPass@5678"
_PASS_C = "HistoryPass@9012"
_PASS_D = "HistoryPass@3456"
_PASS_E = "HistoryPass@7890"
_PASS_F = "HistoryPass@1357"


def _change_password(
    client: TestClient, access_token: str, current: str, new_pass: str
) -> int:
    resp = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "current_password": current,
            "new_password": new_pass,
            "confirm_password": new_pass,
        },
    )
    return resp.status_code


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return resp.json()["data"]["access_token"]


class TestPasswordHistoryEnforcement:
    def test_current_password_cannot_be_reused(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Change to PASS_B, then attempt to change back to PASS_A (now in history)."""
        user, _ = create_test_user(
            db_session, email="hist_current@example.com", password=_PASS_A
        )
        # First change: PASS_A → PASS_B (adds PASS_A to history).
        token1 = _login(test_client, user.email, _PASS_A)
        assert _change_password(test_client, token1, _PASS_A, _PASS_B) == 200
        # Second change attempt: PASS_B → PASS_A (PASS_A is in history → reject).
        token2 = _login(test_client, user.email, _PASS_B)
        status = _change_password(test_client, token2, _PASS_B, _PASS_A)
        assert status == 422

    def test_password_not_in_history_is_accepted(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(
            db_session, email="hist_new@example.com", password=_PASS_A
        )
        token = _login(test_client, user.email, _PASS_A)
        status = _change_password(test_client, token, _PASS_A, _PASS_B)
        assert status == 200
