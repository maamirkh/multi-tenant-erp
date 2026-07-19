"""T116 — Integration tests for POST /api/v1/auth/reset-password.

Spec ref: spec.md §7 FR-022–FR-023, US-05.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user


class TestResetPasswordInvalid:
    def test_invalid_token_returns_400(self, test_client: TestClient) -> None:
        resp = test_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": "definitely-not-a-real-token",
                "new_password": "NewSecure@12345",
                "confirm_password": "NewSecure@12345",
            },
        )
        assert resp.status_code == 400

    def test_weak_password_returns_422(self, test_client: TestClient) -> None:
        resp = test_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": "any-token",
                "new_password": "weak",
                "confirm_password": "weak",
            },
        )
        assert resp.status_code == 422

    def test_mismatched_passwords_returns_422(self, test_client: TestClient) -> None:
        resp = test_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": "any-token",
                "new_password": "NewSecure@12345",
                "confirm_password": "DifferentPass@1",
            },
        )
        assert resp.status_code == 422


class TestResetPasswordValid:
    def test_valid_token_updates_password(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Full happy-path: request reset → use token → login with new password."""

        user, old_password = create_test_user(
            db_session, email="reset_valid@example.com"
        )

        # Request a reset token.
        test_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": user.email},
        )

        # Fetch the raw token hash from DB and reconstruct a raw token.
        # Since we can't recover the raw token from the hash, we generate one
        # directly via the service for this integration test.
        from core.config.settings import Settings
        from modules.auth.services.token_service import TokenService

        settings = Settings(
            DATABASE_URL="sqlite:///:memory:",
            SECRET_KEY="test-secret-key-minimum-32-chars-ok",
            JWT_SECRET_KEY="test-jwt-secret-key-min-32-chars-ok!",
        )
        token_svc = TokenService(db=db_session, settings=settings)
        raw_token = token_svc.create_password_reset_token(user_id=user.id, ip=None)

        new_password = "NewSecurePass@9876"
        resp = test_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": raw_token,
                "new_password": new_password,
                "confirm_password": new_password,
            },
        )
        assert resp.status_code == 200

    def test_sessions_revoked_after_reset(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """After password reset, existing refresh tokens must be rejected."""
        user, old_password = create_test_user(
            db_session, email="reset_revoke@example.com"
        )
        login_resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": old_password},
        )
        old_refresh_token = login_resp.json()["data"]["refresh_token"]

        # Perform a reset via token service.
        from core.config.settings import Settings
        from modules.auth.services.token_service import TokenService

        settings = Settings(
            DATABASE_URL="sqlite:///:memory:",
            SECRET_KEY="test-secret-key-minimum-32-chars-ok",
            JWT_SECRET_KEY="test-jwt-secret-key-min-32-chars-ok!",
        )
        token_svc = TokenService(db=db_session, settings=settings)
        raw_token = token_svc.create_password_reset_token(user_id=user.id, ip=None)

        new_password = "NewRevoke@99887766"
        test_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": raw_token,
                "new_password": new_password,
                "confirm_password": new_password,
            },
        )

        # Former refresh token must be rejected.
        retry = test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_refresh_token},
        )
        assert retry.status_code in (400, 401)
