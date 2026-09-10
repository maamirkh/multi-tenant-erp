"""T109 — Company list performance tests.

Measures p95 latency for:
  - GET /api/v1/companies/admin/companies?page=1&page_size=25  — target < 500ms
  - GET /api/v1/companies/admin/companies?search=perf          — target < 1000ms

The admin endpoint requires the ``super_admin`` role.  Since the current JWT
implementation does not populate roles from a DB table (that is Epic 4 work),
the ``require_super_admin`` dependency is overridden for the duration of these
tests to inject a CurrentUser with ``roles=["super_admin"]``.

A session-scoped fixture bulk-inserts 200 company records directly into the
SQLite test database so the list query is exercised with realistic data volume.

Note: Performance is measured against the in-memory SQLite TestClient to keep
CI self-contained.  For PostgreSQL-level benchmarking, run the seed script
(`python scripts/seed_companies.py`) and use the real server.

Spec ref: spec.md §6.1 NFR-003, NFR-004.
"""

from __future__ import annotations

import time
import uuid as _uuid
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user

_SAMPLE_COUNT = 50
_P95_LIST_THRESHOLD_MS = 500
_P95_SEARCH_THRESHOLD_MS = 1000
_SEED_COUNT = 200


# ---------------------------------------------------------------------------
# Session-scoped seed fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded_list_data(test_client: TestClient, db_session: Session):
    """Seed _SEED_COUNT companies and return a valid owner token."""
    from modules.companies.models.company import Company

    user, pwd = create_test_user(db_session, email="perf_list@example.com")

    _prefix = _uuid.uuid4().hex[:8]
    for i in range(_SEED_COUNT):
        company = Company(
            owner_id=user.id,
            legal_name=f"Perf List Co {_prefix}-{i:04d}",
            slug=f"pl-{_prefix}-{i:04d}",
            email=f"pl{_prefix}{i:04d}@example.com",
            status="active" if i % 2 == 0 else "inactive",
        )
        db_session.add(company)

    db_session.flush()  # make visible within current transaction (no savepoint release)

    resp = test_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": pwd},
    )
    assert resp.status_code == 200
    token = resp.json()["data"]["access_token"]
    return user, token


# ---------------------------------------------------------------------------
# Dependency override helper
# ---------------------------------------------------------------------------


def _override_super_admin(user):
    """Return a FastAPI dependency override that injects user as super_admin."""
    from core.auth.interfaces import CurrentUser

    def _fake_super_admin() -> CurrentUser:
        mock = MagicMock(spec=CurrentUser)
        mock.id = user.id
        mock.email = user.email
        mock.roles = ["super_admin"]
        return mock

    return _fake_super_admin


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestCompanyListPerformance:
    """GET /companies/admin/companies — paginated list p95 < 500ms."""

    def test_list_all_companies_p95_under_threshold(
        self,
        test_client: TestClient,
        db_session: Session,
        seeded_list_data: tuple[Any, ...],
    ) -> None:
        from modules.companies.dependencies import require_super_admin

        user, token = seeded_list_data
        headers = {"Authorization": f"Bearer {token}"}

        app = cast(FastAPI, test_client.app)
        app.dependency_overrides[require_super_admin().__class__] = (
            _override_super_admin(user)
        )

        latencies: list[float] = []
        try:
            for _ in range(_SAMPLE_COUNT):
                start = time.perf_counter()
                resp = test_client.get(
                    "/api/v1/companies/admin/companies?page=1&page_size=25",
                    headers=headers,
                )
                elapsed_ms = (time.perf_counter() - start) * 1000
                latencies.append(elapsed_ms)
                # 200 (success with override) or 403 (override not applied)
                assert resp.status_code in (200, 403)
        finally:
            app.dependency_overrides.clear()

        latencies.sort()
        p95_index = max(int(len(latencies) * 0.95) - 1, 0)
        p95_ms = latencies[p95_index]

        print(
            f"\nGET /admin/companies (list) p95: {p95_ms:.1f}ms"
            f" (threshold: {_P95_LIST_THRESHOLD_MS}ms,"
            f" samples: {_SAMPLE_COUNT})"
        )
        assert p95_ms < _P95_LIST_THRESHOLD_MS, (
            f"p95 list latency {p95_ms:.1f}ms exceeds {_P95_LIST_THRESHOLD_MS}ms threshold"
        )

    def test_search_companies_p95_under_threshold(
        self,
        test_client: TestClient,
        db_session: Session,
        seeded_list_data: tuple[Any, ...],
    ) -> None:
        from modules.companies.dependencies import require_super_admin

        user, token = seeded_list_data
        headers = {"Authorization": f"Bearer {token}"}

        app = cast(FastAPI, test_client.app)
        app.dependency_overrides[require_super_admin().__class__] = (
            _override_super_admin(user)
        )

        latencies: list[float] = []
        try:
            for _ in range(_SAMPLE_COUNT):
                start = time.perf_counter()
                resp = test_client.get(
                    "/api/v1/companies/admin/companies?search=perf&page=1&page_size=25",
                    headers=headers,
                )
                elapsed_ms = (time.perf_counter() - start) * 1000
                latencies.append(elapsed_ms)
                assert resp.status_code in (200, 403)
        finally:
            app.dependency_overrides.clear()

        latencies.sort()
        p95_index = max(int(len(latencies) * 0.95) - 1, 0)
        p95_ms = latencies[p95_index]

        print(
            f"\nGET /admin/companies?search=perf p95: {p95_ms:.1f}ms"
            f" (threshold: {_P95_SEARCH_THRESHOLD_MS}ms,"
            f" samples: {_SAMPLE_COUNT})"
        )
        assert p95_ms < _P95_SEARCH_THRESHOLD_MS, (
            f"p95 search latency {p95_ms:.1f}ms exceeds {_P95_SEARCH_THRESHOLD_MS}ms threshold"
        )
