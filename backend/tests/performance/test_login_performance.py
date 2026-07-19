"""T129 — Login performance test.

Measures 10 sequential login requests; asserts p95 latency < 800ms.
Note: Argon2 hashing is the bottleneck; SQLite in-memory is used to
eliminate network overhead.
Spec ref: spec.md §8 NFR-020.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

_SAMPLE_COUNT = 10
_P95_THRESHOLD_MS = 800


@pytest.mark.slow
class TestLoginPerformance:
    def test_sequential_login_p95_under_threshold(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        user, password = create_test_user(db_session, email="perf_login@example.com")

        latencies: list[float] = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = test_client.post(
                "/api/v1/auth/login",
                json={"email": user.email, "password": password},
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        latencies.sort()
        p95_index = int(len(latencies) * 0.95) - 1
        p95_ms = latencies[max(p95_index, 0)]

        print(f"\nLogin p95 latency: {p95_ms:.1f}ms (threshold: {_P95_THRESHOLD_MS}ms)")
        assert (
            p95_ms < _P95_THRESHOLD_MS
        ), f"p95 login latency {p95_ms:.1f}ms exceeds {_P95_THRESHOLD_MS}ms threshold"
