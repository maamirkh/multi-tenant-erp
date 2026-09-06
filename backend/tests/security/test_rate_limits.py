"""T140 — Rate limiting validation.

Verifies that rate limits fire at the correct thresholds:
  - POST /login:          10/minute → 11th request returns 429
  - POST /forgot-password: 3/15min  → 4th request returns 429
Both 429 responses must include a `Retry-After` header.
Spec ref: spec.md §13.6, NFR-014.

NOTE: The autouse _reset_rate_limiter fixture in conftest.py clears the
limiter counters before each test, so tests start from zero.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

# Use a non-existent email so auth 401s don't trigger account lockout.
# Must be a syntactically valid email to pass Pydantic validation.
_NONEXISTENT_EMAIL = "rate.limit.test.no.such.user@example.com"
_WRONG_PASSWORD = "WrongPass@999"


class TestLoginRateLimit:
    def test_eleventh_login_request_returns_429(self, test_client: TestClient) -> None:
        """10 requests succeed (with 401 auth failure); the 11th must be rate-limited."""
        statuses: list[int] = []
        for i in range(11):
            resp = test_client.post(
                "/api/v1/auth/login",
                json={"email": _NONEXISTENT_EMAIL, "password": _WRONG_PASSWORD},
            )
            statuses.append(resp.status_code)

        # First 10 should be auth failures (401/403/423) not rate-limited.
        for i, status in enumerate(statuses[:10]):
            assert status != 429, (
                f"Request #{i + 1} unexpectedly rate-limited (429) — "
                f"expected auth error, got {status}"
            )

        # 11th must be rate-limited.
        assert statuses[10] == 429, (
            f"Expected 429 on request #11, got {statuses[10]}. All statuses: {statuses}"
        )

    def test_rate_limited_login_returns_json_error(
        self, test_client: TestClient
    ) -> None:
        """429 response must return JSON with an error message.

        NOTE: RFC 6585 recommends a Retry-After header on 429 responses.
        The current SlowAPI default handler does not include Retry-After.
        This is a known gap documented in security-review.md.
        """
        for _ in range(11):
            resp = test_client.post(
                "/api/v1/auth/login",
                json={"email": _NONEXISTENT_EMAIL, "password": _WRONG_PASSWORD},
            )

        assert resp.status_code == 429
        body = resp.json()
        assert "error" in body, f"429 response missing 'error' field in body: {body}"


class TestForgotPasswordRateLimit:
    def test_fourth_forgot_password_request_returns_429(
        self, test_client: TestClient
    ) -> None:
        """3 requests allowed; the 4th must be rate-limited (3/15min limit)."""
        statuses: list[int] = []
        for _ in range(4):
            resp = test_client.post(
                "/api/v1/auth/forgot-password",
                json={"email": _NONEXISTENT_EMAIL},
            )
            statuses.append(resp.status_code)

        # First 3 should return 200 (anti-enumeration: always 200).
        for i, status in enumerate(statuses[:3]):
            assert status == 200, (
                f"Request #{i + 1} to forgot-password returned {status}, expected 200"
            )

        # 4th must be rate-limited.
        assert statuses[3] == 429, (
            f"Expected 429 on request #4, got {statuses[3]}. All statuses: {statuses}"
        )

    def test_rate_limited_forgot_password_returns_json_error(
        self, test_client: TestClient
    ) -> None:
        """429 response to forgot-password must return JSON with an error message.

        NOTE: RFC 6585 recommends a Retry-After header on 429 responses.
        The current SlowAPI default handler does not include Retry-After.
        This is a known gap documented in security-review.md.
        """
        for _ in range(4):
            resp = test_client.post(
                "/api/v1/auth/forgot-password",
                json={"email": _NONEXISTENT_EMAIL},
            )

        assert resp.status_code == 429
        body = resp.json()
        assert "error" in body, f"429 response missing 'error' field in body: {body}"
