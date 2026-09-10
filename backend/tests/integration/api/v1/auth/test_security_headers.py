"""T118 — Integration tests for security headers on auth endpoints.

Verifies that SecurityHeadersMiddleware injects the required headers on
every response (including health endpoint — confirming middleware is global).
Spec ref: spec.md §8 NFR-014, plan.md §3 (SecurityHeadersMiddleware).
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

_REQUIRED_HEADERS = {
    "x-frame-options": "DENY",
    "x-content-type-options": "nosniff",
    "x-xss-protection": "1; mode=block",
    "referrer-policy": "strict-origin-when-cross-origin",
}


def _assert_security_headers(response_headers: dict[str, Any]) -> None:
    for name, value in _REQUIRED_HEADERS.items():
        assert response_headers.get(name) == value, (
            f"Missing or wrong security header: {name}={response_headers.get(name)!r}"
        )


class TestSecurityHeadersOnAuthEndpoints:
    def test_login_includes_security_headers(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="hdr_login@example.com")
        resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        _assert_security_headers(resp.headers)

    def test_me_includes_security_headers(self, test_client: TestClient) -> None:
        resp = test_client.get("/api/v1/auth/me")
        # 401 is expected (no token) but headers must still be present.
        _assert_security_headers(resp.headers)

    def test_refresh_includes_security_headers(self, test_client: TestClient) -> None:
        resp = test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "fake-token"},
        )
        _assert_security_headers(resp.headers)

    def test_forgot_password_includes_security_headers(
        self, test_client: TestClient
    ) -> None:
        resp = test_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "headers@example.com"},
        )
        _assert_security_headers(resp.headers)


class TestSecurityHeadersOnHealthEndpoint:
    def test_health_endpoint_includes_security_headers(
        self, test_client: TestClient
    ) -> None:
        resp = test_client.get("/api/v1/health")
        _assert_security_headers(resp.headers)
