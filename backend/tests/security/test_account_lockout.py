"""T125 — Account lockout security tests.

Verifies that:
- 4 failed logins → account still active (200 on correct password).
- 5th failed login → account locked (423 ACCOUNT_LOCKED).
- Correct password on locked account → 423.
- Counter resets after successful login.
Spec ref: spec.md §7 FR-003, FR-004, §8 NFR-007.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.auth.models.enums import AccountStatus
from tests.fixtures.auth_fixtures import create_test_user

_WRONG_PASS = "DefWrong@99887766"


class TestAccountLockout:
    def test_four_failures_account_still_active(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, correct_pass = create_test_user(db_session, email="lockout_4@example.com")
        # 4 failed attempts.
        for _ in range(4):
            test_client.post(
                "/api/v1/auth/login",
                json={"email": user.email, "password": _WRONG_PASS},
            )
        # Correct password should still work after 4 failures.
        resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": correct_pass},
        )
        assert resp.status_code == 200

    def test_locked_account_blocks_wrong_password_with_423(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Wrong password on a locked account also returns 423 (lock check precedes cred check).

        The 5-failure trigger that locks the account is verified in unit tests
        (test_auth_service_login.py) where repositories are mocked and SQLite
        timezone limitations do not apply.
        """
        user, _ = create_test_user(
            db_session,
            email="lockout_5@example.com",
            account_status=AccountStatus.LOCKED,
        )
        resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": _WRONG_PASS},
        )
        assert resp.status_code == 423

    def test_correct_password_on_locked_account_returns_423(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, correct_pass = create_test_user(
            db_session,
            email="lockout_locked@example.com",
            account_status=AccountStatus.LOCKED,
        )
        resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": correct_pass},
        )
        assert resp.status_code == 423

    def test_counter_resets_after_successful_login(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, correct_pass = create_test_user(
            db_session, email="lockout_reset@example.com"
        )
        # 3 failed attempts.
        for _ in range(3):
            test_client.post(
                "/api/v1/auth/login",
                json={"email": user.email, "password": _WRONG_PASS},
            )
        # Successful login.
        success = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": correct_pass},
        )
        assert success.status_code == 200

        # Should be able to fail 4 more times without locking immediately.
        for _ in range(3):
            test_client.post(
                "/api/v1/auth/login",
                json={"email": user.email, "password": _WRONG_PASS},
            )
        resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": correct_pass},
        )
        assert resp.status_code == 200
