"""T115 [P] — Company creation rate limiting tests.

Verifies that POST /api/v1/companies is rate-limited at 10 requests per minute
per IP address.  The 11th request from the same IP within one minute must
return HTTP 429 Too Many Requests.

Rate limiting is provided by SlowAPI (slowapi.Limiter) using ``get_remote_address``
as the key function.  The limiter singleton lives in ``modules.auth.router``
and is attached to ``app.state.limiter`` by ``create_app()``.

The autouse ``_reset_rate_limiter`` fixture in conftest.py clears counters
before each test so requests start from zero.

Note: SlowAPI uses ``get_remote_address`` (client IP) as the key, not the
authenticated user ID.  In the TestClient all requests originate from the same
pseudo-IP ("testclient"), so independent-user isolation cannot be verified
in unit tests without forking processes.  This is documented as a known gap.

Spec ref: spec.md §13.6 NFR-014.
"""

from __future__ import annotations

import uuid as _uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

_RATE_LIMIT = 10  # requests per minute allowed before 429
_CREATE_URL = "/api/v1/companies"


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return str(resp.json()["data"]["access_token"])


def _auth(token: str) -> dict[str, Any]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def authed_user(test_client: TestClient, db_session: Session):
    """Return a valid access token for a fresh test user."""
    prefix = _uuid.uuid4().hex[:8]
    user, pwd = create_test_user(db_session, email=f"ratelimit_{prefix}@example.com")
    token = _login(test_client, user.email, pwd)
    return token


class TestCompanyCreateRateLimit:
    """POST /companies is limited to 10 requests per minute per IP."""

    def test_eleventh_request_returns_429(
        self, test_client: TestClient, authed_user: str
    ) -> None:
        """10 requests succeed; the 11th is rate-limited."""
        token = authed_user
        statuses: list[int] = []
        prefix = _uuid.uuid4().hex[:8]

        for i in range(_RATE_LIMIT + 1):
            resp = test_client.post(
                _CREATE_URL,
                json={
                    "legal_name": f"RL Corp {prefix}-{i:03d}",
                    "email": f"rl{prefix}{i:03d}@example.com",
                },
                headers=_auth(token),
            )
            statuses.append(resp.status_code)

        # First 10 must NOT be rate-limited (201 created).
        for i, code in enumerate(statuses[:_RATE_LIMIT]):
            assert code == 201, (
                f"Request #{i + 1} should succeed (201), got {code}. "
                f"All statuses: {statuses}"
            )

        # 11th must be rate-limited.
        assert statuses[_RATE_LIMIT] == 429, (
            f"Expected 429 on request #{_RATE_LIMIT + 1}, got {statuses[_RATE_LIMIT]}. "
            f"All statuses: {statuses}"
        )

    def test_rate_limited_response_body_contains_error(
        self, test_client: TestClient, authed_user: str
    ) -> None:
        """429 response must include an error field in the JSON body."""
        token = authed_user
        prefix = _uuid.uuid4().hex[:8]
        last_resp = None

        for i in range(_RATE_LIMIT + 1):
            last_resp = test_client.post(
                _CREATE_URL,
                json={
                    "legal_name": f"RL Body Corp {prefix}-{i:03d}",
                    "email": f"rlbody{prefix}{i:03d}@example.com",
                },
                headers=_auth(token),
            )

        assert last_resp is not None
        assert last_resp.status_code == 429
        body = last_resp.json()
        assert "error" in body, f"429 body missing 'error' field: {body}"
