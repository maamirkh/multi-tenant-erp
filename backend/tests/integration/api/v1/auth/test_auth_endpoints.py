"""Integration tests for authentication API endpoints.

These tests use the FastAPI TestClient with SQLite in-memory database via the
shared ``test_client`` fixture from conftest.py.

NOTE: Tests that require Argon2 hashing are slower due to the bcrypt/argon2
computation time. ARGON2_TIME_COST=1 and reduced memory cost are applied via
the test settings to keep tests fast.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user


class TestLoginEndpoint:
    def test_login_with_valid_credentials_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session)
        response = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
        assert data["data"]["token_type"] == "bearer"

    def test_login_with_wrong_password_returns_401(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, _ = create_test_user(db_session, email="wrong_pass@example.com")
        response = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "WrongPassword@1234"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "INVALID_CREDENTIALS"

    def test_login_with_unknown_email_returns_401(
        self, test_client: TestClient
    ) -> None:
        response = test_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@nonexistent.com", "password": "AnyPass@1234567"},
        )
        assert response.status_code == 401

    def test_login_missing_email_returns_422(self, test_client: TestClient) -> None:
        response = test_client.post(
            "/api/v1/auth/login",
            json={"password": "AnyPass@1234567"},
        )
        assert response.status_code == 422

    def test_login_missing_password_returns_422(self, test_client: TestClient) -> None:
        response = test_client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com"},
        )
        assert response.status_code == 422

    def test_login_invalid_email_format_returns_422(
        self, test_client: TestClient
    ) -> None:
        response = test_client.post(
            "/api/v1/auth/login",
            json={"email": "not-an-email", "password": "AnyPass@1234567"},
        )
        assert response.status_code == 422


class TestGetMeEndpoint:
    def test_get_me_without_token_returns_401(self, test_client: TestClient) -> None:
        response = test_client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_get_me_with_valid_token_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="me_endpoint@example.com")
        login_resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        assert login_resp.status_code == 200
        access_token = login_resp.json()["data"]["access_token"]

        me_resp = test_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me_resp.status_code == 200
        profile = me_resp.json()["data"]
        assert profile["email"] == user.email
        assert "password" not in str(profile)
        assert "password_hash" not in str(profile)

    def test_get_me_with_invalid_token_returns_401(
        self, test_client: TestClient
    ) -> None:
        response = test_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.value"},
        )
        assert response.status_code == 401


class TestRefreshEndpoint:
    def test_refresh_with_valid_token_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="refresh_test@example.com")
        login_resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        refresh_token = login_resp.json()["data"]["refresh_token"]

        refresh_resp = test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_resp.status_code == 200
        data = refresh_resp.json()["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["refresh_token"] != refresh_token  # Token was rotated

    def test_refresh_with_invalid_token_returns_400(
        self, test_client: TestClient
    ) -> None:
        response = test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "not-a-real-token"},
        )
        assert response.status_code in (400, 401)

    def test_old_refresh_token_rejected_after_rotation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="rotation_test@example.com")
        login_resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        old_token = login_resp.json()["data"]["refresh_token"]

        # Rotate the token.
        test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_token},
        )

        # Try using the old (now revoked) token again.
        retry_resp = test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_token},
        )
        assert retry_resp.status_code in (400, 401)


class TestLogoutEndpoint:
    def test_logout_without_token_returns_401(self, test_client: TestClient) -> None:
        response = test_client.post("/api/v1/auth/logout")
        assert response.status_code == 401

    def test_logout_with_valid_token_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="logout_test@example.com")
        login_resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        access_token = login_resp.json()["data"]["access_token"]

        logout_resp = test_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert logout_resp.status_code == 200


class TestForgotPasswordEndpoint:
    def test_forgot_password_registered_email_returns_200(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, _ = create_test_user(db_session, email="forgot_registered@example.com")
        response = test_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": user.email},
        )
        assert response.status_code == 200

    def test_forgot_password_unknown_email_returns_200(
        self, test_client: TestClient
    ) -> None:
        response = test_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nobody@unknown.example.com"},
        )
        assert response.status_code == 200

    def test_forgot_password_responses_are_identical(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, _ = create_test_user(db_session, email="enum_test_reg@example.com")

        resp_registered = test_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": user.email},
        )
        resp_unknown = test_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "no-such-user@enumtest.com"},
        )

        assert resp_registered.json() == resp_unknown.json()


class TestResetPasswordEndpoint:
    def test_reset_with_invalid_token_returns_400(
        self, test_client: TestClient
    ) -> None:
        response = test_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": "invalid-reset-token",
                "new_password": "NewPassword@12345",
                "confirm_password": "NewPassword@12345",
            },
        )
        assert response.status_code == 400

    def test_reset_with_mismatched_passwords_returns_422(
        self, test_client: TestClient
    ) -> None:
        response = test_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": "some-token",
                "new_password": "NewPassword@12345",
                "confirm_password": "DifferentPassword@12345",
            },
        )
        assert response.status_code == 422


class TestVerifyEmailEndpoint:
    def test_verify_email_with_invalid_token_returns_400(
        self, test_client: TestClient
    ) -> None:
        response = test_client.post(
            "/api/v1/auth/verify-email",
            json={"token": "invalid-verify-token"},
        )
        assert response.status_code == 400


class TestSecurityHeaders:
    def test_login_response_includes_security_headers(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="headers_test@example.com")
        response = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        headers = response.headers
        assert headers.get("x-frame-options") == "DENY"
        assert headers.get("x-content-type-options") == "nosniff"
        assert headers.get("x-xss-protection") == "1; mode=block"
        assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_health_endpoint_includes_security_headers(
        self, test_client: TestClient
    ) -> None:
        response = test_client.get("/api/v1/health")
        headers = response.headers
        assert headers.get("x-frame-options") == "DENY"
