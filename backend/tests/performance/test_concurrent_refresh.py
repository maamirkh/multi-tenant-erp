"""T131 — Concurrent refresh token rotation test.

Launches 5 concurrent refresh requests with the SAME refresh token using
asyncio.gather; asserts exactly one returns 200 and the rest return 401.
This verifies atomic rotation prevents token duplication.
Spec ref: spec.md §7 FR-007, §8 NFR-009.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

_CONCURRENT_REQUESTS = 5


@pytest.mark.slow
class TestConcurrentRefresh:
    def test_exactly_one_winner_among_concurrent_requests(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Use ThreadPoolExecutor to simulate concurrent refresh requests.

        The TestClient is thread-safe; each thread sends the same refresh
        token.  Only one should succeed (200); the rest should fail (401/400).
        """
        user, password = create_test_user(
            db_session, email="concurrent_refresh@example.com"
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
            return int(resp.status_code)

        with ThreadPoolExecutor(max_workers=_CONCURRENT_REQUESTS) as executor:
            futures = [executor.submit(do_refresh) for _ in range(_CONCURRENT_REQUESTS)]
            for future in as_completed(futures):
                results.append(future.result())

        successes = results.count(200)
        failures = sum(1 for r in results if r in (400, 401))

        print(f"\nConcurrent refresh results: {results}")
        print(f"Successes: {successes}, Failures: {failures}")

        assert successes == 1, (
            f"Expected exactly 1 success among {_CONCURRENT_REQUESTS} concurrent requests, "
            f"got {successes}. Results: {results}"
        )
        assert failures == _CONCURRENT_REQUESTS - 1
