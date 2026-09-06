"""T108 — Company read/update performance tests.

Measures p95 latency for:
  - GET /api/v1/companies/{id}  — target < 200ms
  - PATCH /api/v1/companies/{id} — target < 500ms

A session-scoped fixture bulk-inserts 200 company records directly into the
SQLite test database (bypassing service layer) so that the query path is
exercised with realistic data volume without the overhead of the full creation
workflow per test.

Note: Performance is measured against the in-memory SQLite TestClient to keep
CI self-contained.  For PostgreSQL-level benchmarking, run the seed script
(`python scripts/seed_companies.py`) and use the real server.

Spec ref: spec.md §6.1 NFR-001, NFR-002.
"""

from __future__ import annotations

import time
import uuid as _uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

_SAMPLE_COUNT = 50
_P95_GET_THRESHOLD_MS = 200
_P95_PATCH_THRESHOLD_MS = 500
_SEED_COUNT = 200  # companies pre-seeded in fixture


# ---------------------------------------------------------------------------
# Session-scoped seed fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded_company(test_client: TestClient, db_session: Session):
    """Return a (company_id, token) pair after seeding companies into the DB.

    Bulk-inserts _SEED_COUNT company rows directly, then creates and logs in
    the owning user so we have a valid token for API calls.
    """
    user, pwd = create_test_user(db_session, email="perf_read@example.com")

    # Insert companies via ORM so that Uuid(as_uuid=True) column types are
    # handled correctly for both SQLite (BLOB) and PostgreSQL (native UUID).
    from modules.companies.models.company import Company

    # Use a run-unique prefix so slugs don't collide across test runs in the
    # same session-scoped SQLite engine (in case a previous test's rollback
    # hasn't fully propagated to the unique index).
    _prefix = _uuid.uuid4().hex[:8]
    first_id = None
    for i in range(_SEED_COUNT):
        company = Company(
            owner_id=user.id,
            legal_name=f"Perf Read Co {_prefix}-{i:04d}",
            slug=f"pr-{_prefix}-{i:04d}",
            email=f"pr{_prefix}{i:04d}@example.com",
            status="pending_setup",
        )
        db_session.add(company)
        if first_id is None:
            db_session.flush()  # flush so company.id is populated
            first_id = company.id

    db_session.flush()  # make all rows visible within the current transaction

    # Login to obtain token
    resp = test_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": pwd},
    )
    assert resp.status_code == 200
    token = resp.json()["data"]["access_token"]
    return first_id, token


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestCompanyReadPerformance:
    """GET /api/v1/companies/{id} — p95 < 200ms with 200 pre-seeded records."""

    def test_get_company_p95_under_threshold(
        self,
        test_client: TestClient,
        db_session: Session,
        seeded_company: tuple[str, str],
    ) -> None:
        company_id, token = seeded_company
        headers = {"Authorization": f"Bearer {token}"}

        latencies: list[float] = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = test_client.get(
                f"/api/v1/companies/{company_id}",
                headers=headers,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        latencies.sort()
        p95_index = max(int(len(latencies) * 0.95) - 1, 0)
        p95_ms = latencies[p95_index]

        print(
            f"\nGET /companies/{{id}} p95: {p95_ms:.1f}ms"
            f" (threshold: {_P95_GET_THRESHOLD_MS}ms,"
            f" samples: {_SAMPLE_COUNT})"
        )
        assert p95_ms < _P95_GET_THRESHOLD_MS, (
            f"p95 GET latency {p95_ms:.1f}ms exceeds {_P95_GET_THRESHOLD_MS}ms threshold"
        )


@pytest.mark.slow
class TestCompanyUpdatePerformance:
    """PATCH /api/v1/companies/{id} — p95 < 500ms with 200 pre-seeded records."""

    def test_patch_company_p95_under_threshold(
        self,
        test_client: TestClient,
        db_session: Session,
        seeded_company: tuple[str, str],
    ) -> None:
        company_id, token = seeded_company
        headers = {"Authorization": f"Bearer {token}"}

        latencies: list[float] = []
        for i in range(_SAMPLE_COUNT):
            payload = {"trade_name": f"Updated Name {i}"}
            start = time.perf_counter()
            resp = test_client.patch(
                f"/api/v1/companies/{company_id}",
                json=payload,
                headers=headers,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        latencies.sort()
        p95_index = max(int(len(latencies) * 0.95) - 1, 0)
        p95_ms = latencies[p95_index]

        print(
            f"\nPATCH /companies/{{id}} p95: {p95_ms:.1f}ms"
            f" (threshold: {_P95_PATCH_THRESHOLD_MS}ms,"
            f" samples: {_SAMPLE_COUNT})"
        )
        assert p95_ms < _P95_PATCH_THRESHOLD_MS, (
            f"p95 PATCH latency {p95_ms:.1f}ms exceeds {_P95_PATCH_THRESHOLD_MS}ms threshold"
        )
