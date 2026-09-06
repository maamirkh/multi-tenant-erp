"""T138 — Member listing performance tests.

Measures p95 latency for GET /api/v1/companies/{company_id}/members with
a seeded dataset of 1000 members to verify performance meets the enterprise
target (p95 < 500ms).

Test setup:
- Creates one owner user and one company.
- Bulk-inserts 1000 CompanyMember records directly into the test database
  (bypassing the API to keep setup time minimal).
- Runs 50 sample requests and calculates p95 latency.

Note: Performance is measured against the in-memory SQLite TestClient.
SQLite is faster than a real PostgreSQL instance for small datasets but
may behave differently under contention. For PostgreSQL-level benchmarking,
seed the database with the provided script and measure against a live server.

Spec ref: spec.md NFR-003, NFR-004, tasks T138.
"""

from __future__ import annotations

import time
import uuid as _uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user
from tests.fixtures.users_roles_fixtures import seed_system_roles

_SEED_MEMBER_COUNT = 1000
_SAMPLE_COUNT = 50
_P95_THRESHOLD_MS = 500


# ---------------------------------------------------------------------------
# Seed fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded_members(test_client: TestClient, db_session: Session):
    """Seed 1000 members in one company and return an authenticated owner token.

    Members are inserted directly via the ORM for speed; the company creation
    and authentication are done via the API to ensure a valid JWT.

    Returns:
        (owner_token, company_id_str)
    """
    from modules.users_roles.models.company_member import CompanyMember
    from modules.users_roles.models.enums import MembershipStatus

    prefix = _uuid.uuid4().hex[:8]
    owner_user, owner_pwd = create_test_user(
        db_session, email=f"perf_ml_owner_{prefix}@example.com"
    )

    # Create company via API so the router/bootstrap chain runs correctly
    resp = test_client.post(
        "/api/v1/auth/login",
        json={"email": owner_user.email, "password": owner_pwd},
    )
    assert resp.status_code == 200
    owner_token = resp.json()["data"]["access_token"]

    company_resp = test_client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"PerfML Corp {prefix}",
            "email": f"perf_ml_{prefix}@example.com",
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert company_resp.status_code == 201
    company_id_str = company_resp.json()["data"]["id"]
    company_id = _uuid.UUID(company_id_str)

    # Seed system roles
    roles = seed_system_roles(db_session, company_id, owner_user.id)
    role_map = {r.slug: r for r in roles}
    viewer_role = role_map["viewer"]

    # Bulk-insert members directly (ORM) to keep fixture fast
    statuses = [s.value for s in MembershipStatus]
    members = []
    for i in range(_SEED_MEMBER_COUNT):
        status = (
            MembershipStatus.active.value
            if i % 4 != 3
            else MembershipStatus.inactive.value
        )
        dep = f"Department_{i % 20}"
        members.append(
            CompanyMember(
                company_id=company_id,
                user_id=_uuid.uuid4(),  # synthetic user IDs (no FK check in SQLite)
                role_id=viewer_role.id,
                status=status,
                department=dep,
            )
        )
    db_session.bulk_save_objects(members)
    db_session.flush()

    return owner_token, company_id_str


# ---------------------------------------------------------------------------
# Performance test
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestMemberListPerformance:
    """GET /members — p95 latency must be below 500ms with 1000 members."""

    def test_member_list_p95_under_500ms(
        self,
        test_client: TestClient,
        db_session: Session,
        seeded_members: tuple,
    ) -> None:
        """p95 latency for paginated member list with 1000 members < 500ms."""
        owner_token, company_id = seeded_members
        headers = {"Authorization": f"Bearer {owner_token}"}
        url = f"/api/v1/companies/{company_id}/members?page=1&page_size=25"

        latencies: list[float] = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = test_client.get(url, headers=headers)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200, (
                f"Unexpected status {resp.status_code}: {resp.text[:200]}"
            )

        latencies.sort()
        p95_index = max(int(len(latencies) * 0.95) - 1, 0)
        p95_ms = latencies[p95_index]

        print(
            f"\nGET /members (1000 seeded) p95: {p95_ms:.1f}ms"
            f" (threshold: {_P95_THRESHOLD_MS}ms, samples: {_SAMPLE_COUNT})"
        )

        assert p95_ms < _P95_THRESHOLD_MS, (
            f"Member list p95 latency {p95_ms:.1f}ms exceeds "
            f"{_P95_THRESHOLD_MS}ms threshold"
        )

    def test_member_list_with_status_filter_p95_under_500ms(
        self,
        test_client: TestClient,
        db_session: Session,
        seeded_members: tuple,
    ) -> None:
        """p95 latency for filtered member list (status=active) < 500ms."""
        owner_token, company_id = seeded_members
        headers = {"Authorization": f"Bearer {owner_token}"}
        url = (
            f"/api/v1/companies/{company_id}/members?status=active&page=1&page_size=25"
        )

        latencies: list[float] = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = test_client.get(url, headers=headers)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        latencies.sort()
        p95_index = max(int(len(latencies) * 0.95) - 1, 0)
        p95_ms = latencies[p95_index]

        print(
            f"\nGET /members?status=active p95: {p95_ms:.1f}ms"
            f" (threshold: {_P95_THRESHOLD_MS}ms, samples: {_SAMPLE_COUNT})"
        )

        assert p95_ms < _P95_THRESHOLD_MS, (
            f"Filtered member list p95 latency {p95_ms:.1f}ms exceeds "
            f"{_P95_THRESHOLD_MS}ms threshold"
        )

    def test_member_list_with_department_filter_p95_under_500ms(
        self,
        test_client: TestClient,
        db_session: Session,
        seeded_members: tuple,
    ) -> None:
        """p95 latency for department-filtered member list < 500ms."""
        owner_token, company_id = seeded_members
        headers = {"Authorization": f"Bearer {owner_token}"}
        url = (
            f"/api/v1/companies/{company_id}/members"
            "?department=Department_1&page=1&page_size=25"
        )

        latencies: list[float] = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = test_client.get(url, headers=headers)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        latencies.sort()
        p95_index = max(int(len(latencies) * 0.95) - 1, 0)
        p95_ms = latencies[p95_index]

        print(
            f"\nGET /members?department=Department_1 p95: {p95_ms:.1f}ms"
            f" (threshold: {_P95_THRESHOLD_MS}ms, samples: {_SAMPLE_COUNT})"
        )

        assert p95_ms < _P95_THRESHOLD_MS, (
            f"Department-filtered member list p95 latency {p95_ms:.1f}ms exceeds "
            f"{_P95_THRESHOLD_MS}ms threshold"
        )
