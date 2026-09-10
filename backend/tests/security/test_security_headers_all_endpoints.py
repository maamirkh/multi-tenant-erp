"""T138 — Security headers validation on all 8 auth endpoints.

Validates that all 7 OWASP-required headers are present on every response
from every auth endpoint, regardless of authentication status or request validity.
Spec ref: spec.md §13.7, NFR-017.

The 8 auth endpoints:
  POST /api/v1/auth/login
  POST /api/v1/auth/logout
  POST /api/v1/auth/refresh
  GET  /api/v1/auth/me
  POST /api/v1/auth/forgot-password
  POST /api/v1/auth/reset-password
  POST /api/v1/auth/change-password
  POST /api/v1/auth/verify-email
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

_REQUIRED_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "x-xss-protection": "1; mode=block",
    "referrer-policy": "strict-origin-when-cross-origin",
    "content-security-policy": "default-src 'self'",
    "strict-transport-security": "max-age=31536000; includeSubDomains",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
}

_ENDPOINTS = [
    ("POST", "/api/v1/auth/login", {"email": "hdr_chk@example.com", "password": "x"}),
    ("POST", "/api/v1/auth/logout", None),
    ("POST", "/api/v1/auth/refresh", {"refresh_token": "fake-token"}),
    ("GET", "/api/v1/auth/me", None),
    ("POST", "/api/v1/auth/forgot-password", {"email": "hdr_chk@example.com"}),
    (
        "POST",
        "/api/v1/auth/reset-password",
        {"token": "fake", "new_password": "short", "confirm_password": "short"},
    ),
    ("POST", "/api/v1/auth/change-password", None),
    ("POST", "/api/v1/auth/verify-email", {"token": "fake-verification-token"}),
]


def _assert_all_security_headers(headers: dict[str, Any], endpoint: str) -> None:
    """Assert that all 7 required security headers are present and correct."""
    for name, expected_value in _REQUIRED_HEADERS.items():
        actual = headers.get(name)
        assert actual == expected_value, (
            f"Endpoint {endpoint!r}: "
            f"header {name!r} expected {expected_value!r}, got {actual!r}"
        )


class TestSecurityHeadersAllEndpoints:
    """Validate all 7 security headers on all 8 auth endpoints."""

    def test_login_has_all_security_headers(self, test_client: TestClient) -> None:
        resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": "hdr_login@example.com", "password": "any"},
        )
        _assert_all_security_headers(resp.headers, "/auth/login")

    def test_logout_has_all_security_headers(self, test_client: TestClient) -> None:
        resp = test_client.post("/api/v1/auth/logout")
        _assert_all_security_headers(resp.headers, "/auth/logout")

    def test_refresh_has_all_security_headers(self, test_client: TestClient) -> None:
        resp = test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "fake-token"},
        )
        _assert_all_security_headers(resp.headers, "/auth/refresh")

    def test_me_has_all_security_headers(self, test_client: TestClient) -> None:
        resp = test_client.get("/api/v1/auth/me")
        _assert_all_security_headers(resp.headers, "/auth/me")

    def test_forgot_password_has_all_security_headers(
        self, test_client: TestClient
    ) -> None:
        resp = test_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "hdr_forgot@example.com"},
        )
        _assert_all_security_headers(resp.headers, "/auth/forgot-password")

    def test_reset_password_has_all_security_headers(
        self, test_client: TestClient
    ) -> None:
        resp = test_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": "fake-reset-token",
                "new_password": "NewValid@Pass1234",
                "confirm_password": "NewValid@Pass1234",
            },
        )
        _assert_all_security_headers(resp.headers, "/auth/reset-password")

    def test_change_password_has_all_security_headers(
        self, test_client: TestClient
    ) -> None:
        resp = test_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "old",
                "new_password": "NewValid@Pass1234",
                "confirm_password": "NewValid@Pass1234",
            },
        )
        _assert_all_security_headers(resp.headers, "/auth/change-password")

    def test_verify_email_has_all_security_headers(
        self, test_client: TestClient
    ) -> None:
        resp = test_client.post(
            "/api/v1/auth/verify-email",
            json={"token": "fake-verification-token"},
        )
        _assert_all_security_headers(resp.headers, "/auth/verify-email")

    def test_all_endpoints_covered(self, test_client: TestClient) -> None:
        """Smoke test: all 8 endpoints are reachable and return security headers."""
        results: list[tuple[str, bool]] = []
        for method, path, body in _ENDPOINTS:
            if method == "GET":
                resp = test_client.get(path)
            else:
                resp = test_client.post(path, json=body)
            passed = all(resp.headers.get(h) == v for h, v in _REQUIRED_HEADERS.items())
            results.append((path, passed))

        failed = [p for p, ok in results if not ok]
        assert len(failed) == 0, f"Security headers missing on endpoints: {failed}"
