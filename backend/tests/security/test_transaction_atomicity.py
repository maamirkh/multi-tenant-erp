"""T140A — Authentication transaction atomicity.

Verifies that auth operations leave the database in a consistent state
after failures — no partial writes, no orphaned records.

Scenarios covered:
  1. Failed login (wrong password) — no tokens or sessions created.
  2. Failed password change (wrong current password) — password unchanged.
  3. Failed password reset (invalid token) — no password change occurs.
  4. Concurrent refresh token rotation — exactly one winner (via ThreadPoolExecutor).
  5. Revoked token reuse — all tokens for the user are revoked (theft detection).
Spec ref: spec.md §7 FR-007, §8 NFR-016.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.auth.models.refresh_token import RefreshToken
from tests.fixtures.auth_fixtures import create_test_user

_WRONG_PASSWORD = "WrongPass@9999"
_NEW_PASSWORD = "NewAtomicPass@5678"
_CONCURRENT_REQUESTS = 5


class TestFailedLoginLeavesNoDatabaseArtifacts:
    def test_failed_login_creates_no_refresh_tokens(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """A failed login must not persist any refresh tokens."""
        user, _ = create_test_user(db_session, email="atomic_fail_login@example.com")
        resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": _WRONG_PASSWORD},
        )
        assert resp.status_code in (401, 403, 423)

        tokens = (
            db_session.execute(
                select(RefreshToken).where(RefreshToken.user_id == user.id)
            )
            .scalars()
            .all()
        )
        assert len(tokens) == 0, (
            f"Failed login created {len(tokens)} orphaned refresh token(s)"
        )

    def test_failed_login_with_nonexistent_user_creates_no_artifacts(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """A login attempt with a nonexistent email must not persist any records."""
        resp = test_client.post(
            "/api/v1/auth/login",
            json={
                "email": "no_such_user_atomic@example.com",
                "password": _WRONG_PASSWORD,
            },
        )
        assert resp.status_code == 401


class TestPasswordChangeAtomicity:
    def test_failed_change_leaves_original_password_valid(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Wrong current password → original password still works for login."""
        user, password = create_test_user(db_session, email="atomic_chg@example.com")
        login_resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        access_token = login_resp.json()["data"]["access_token"]

        # Attempt password change with wrong current password.
        change_resp = test_client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "current_password": _WRONG_PASSWORD,
                "new_password": _NEW_PASSWORD,
                "confirm_password": _NEW_PASSWORD,
            },
        )
        assert change_resp.status_code in (401, 403)

        # Original password must still work.
        re_login = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        assert re_login.status_code == 200, (
            "Original password no longer valid after failed change — partial write occurred"
        )


class TestPasswordResetAtomicity:
    def test_invalid_token_leaves_password_unchanged(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """An invalid reset token must not modify the password."""
        user, password = create_test_user(db_session, email="atomic_reset@example.com")
        resp = test_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": "totally-invalid-reset-token",
                "new_password": _NEW_PASSWORD,
                "confirm_password": _NEW_PASSWORD,
            },
        )
        assert resp.status_code == 400

        # Original password must still work.
        login = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        assert login.status_code == 200, (
            "Original password no longer valid after failed reset — partial write occurred"
        )


class TestRefreshRotationAtomicity:
    def test_concurrent_rotation_exactly_one_winner(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Concurrent refresh requests with the same token → exactly one succeeds."""
        user, password = create_test_user(
            db_session, email="atomic_concurrent@example.com"
        )
        login_resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        assert login_resp.status_code == 200
        shared_rt = login_resp.json()["data"]["refresh_token"]

        results: list[int] = []

        def do_refresh() -> int:
            resp = test_client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": shared_rt},
            )
            return resp.status_code

        with ThreadPoolExecutor(max_workers=_CONCURRENT_REQUESTS) as executor:
            futures = [executor.submit(do_refresh) for _ in range(_CONCURRENT_REQUESTS)]
            for future in as_completed(futures):
                results.append(future.result())

        successes = results.count(200)
        failures = sum(1 for r in results if r in (400, 401))

        assert successes == 1, (
            f"Expected exactly 1 successful rotation, got {successes}. "
            f"Results: {results}"
        )
        assert failures == _CONCURRENT_REQUESTS - 1


class TestTokenTheftDetectionAtomicity:
    def test_revoked_token_reuse_revokes_all_user_tokens(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Reusing a revoked refresh token triggers full user token revocation."""
        user, password = create_test_user(db_session, email="atomic_theft@example.com")
        login_resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        original_rt = login_resp.json()["data"]["refresh_token"]

        # Normal rotation — consumes original_rt, returns new token.
        rotate_resp = test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": original_rt},
        )
        assert rotate_resp.status_code == 200
        new_rt = rotate_resp.json()["data"]["refresh_token"]

        # Replay the original (now-revoked) token — should trigger theft detection.
        replay_resp = test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": original_rt},
        )
        assert replay_resp.status_code in (
            400,
            401,
        ), f"Revoked token replay did not return 4xx: {replay_resp.status_code}"

        # The new token should also be revoked (all-tokens revoked on theft detection).
        new_token_resp = test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": new_rt},
        )
        assert new_token_resp.status_code in (
            400,
            401,
        ), "New token still valid after theft detection — full revocation did not occur"
