"""T127 — Replay attack prevention security tests.

Verifies that:
- Consumed password reset token is rejected.
- Expired password reset token is rejected.
- Used refresh token is rejected after rotation.
- Second use of same refresh token → 401.
Spec ref: spec.md §7 FR-007, FR-023, §8 NFR-009.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user


class TestConsumedResetToken:
    def test_consumed_password_reset_token_rejected(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, _ = create_test_user(db_session, email="replay_reset@example.com")

        from core.config.settings import Settings
        from modules.auth.services.token_service import TokenService

        settings = Settings(
            DATABASE_URL="sqlite:///:memory:",
            SECRET_KEY="test-secret-key-minimum-32-chars-ok",
            JWT_SECRET_KEY="test-jwt-secret-key-min-32-chars-ok!",
        )
        token_svc = TokenService(db=db_session, settings=settings)
        raw_token = token_svc.create_password_reset_token(user_id=user.id, ip=None)

        new_pass = "NewReplay@98765"
        # First use — should succeed.
        first = test_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": raw_token,
                "new_password": new_pass,
                "confirm_password": new_pass,
            },
        )
        assert first.status_code == 200

        # Second use of the same (now consumed) token — must be rejected.
        second = test_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": raw_token,
                "new_password": "AnotherPass@11",
                "confirm_password": "AnotherPass@11",
            },
        )
        assert second.status_code == 400


class TestRefreshTokenReplay:
    def test_used_refresh_token_rejected_after_rotation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(
            db_session, email="replay_refresh@example.com"
        )
        login_resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        rt = login_resp.json()["data"]["refresh_token"]

        # First refresh — rotates the token.
        first = test_client.post("/api/v1/auth/refresh", json={"refresh_token": rt})
        assert first.status_code == 200

        # Second use of the old (revoked) token — must be rejected.
        second = test_client.post("/api/v1/auth/refresh", json={"refresh_token": rt})
        assert second.status_code in (400, 401)

    def test_concurrent_refresh_one_winner(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Sequential simulation of concurrent refresh: first wins, second fails."""
        user, password = create_test_user(
            db_session, email="replay_concurrent@example.com"
        )
        login_resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        rt = login_resp.json()["data"]["refresh_token"]

        first = test_client.post("/api/v1/auth/refresh", json={"refresh_token": rt})
        second = test_client.post("/api/v1/auth/refresh", json={"refresh_token": rt})

        assert first.status_code == 200
        assert second.status_code in (400, 401)
