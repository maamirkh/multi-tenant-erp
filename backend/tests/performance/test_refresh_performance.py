"""T130 — Refresh token performance test.

Measures 20 sequential refresh requests; asserts p95 latency < 200ms.
Each request rotates the token, so we login once and then chain
sequential refreshes using the latest token.
Spec ref: spec.md §8 NFR-020.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

_SAMPLE_COUNT = 20
_P95_THRESHOLD_MS = 200


@pytest.mark.slow
class TestRefreshPerformance:
    def test_sequential_refresh_p95_under_threshold(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="perf_refresh@example.com")
        login_resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        assert login_resp.status_code == 200
        current_rt = login_resp.json()["data"]["refresh_token"]

        latencies: list[float] = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = test_client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": current_rt},
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200
            current_rt = resp.json()["data"]["refresh_token"]

        latencies.sort()
        p95_index = int(len(latencies) * 0.95) - 1
        p95_ms = latencies[max(p95_index, 0)]

        print(
            f"\nRefresh p95 latency: {p95_ms:.1f}ms (threshold: {_P95_THRESHOLD_MS}ms)"
        )
        assert p95_ms < _P95_THRESHOLD_MS, (
            f"p95 refresh latency {p95_ms:.1f}ms exceeds {_P95_THRESHOLD_MS}ms threshold"
        )
