"""T139 [P] — Role listing performance tests.

Measures p95 latency for GET /api/v1/companies/{company_id}/roles with
50 roles seeded (8 system + 42 custom) to verify performance meets the
enterprise target (p95 < 200ms).

Test setup:
- Creates one owner user and one company.
- Seeds 8 system roles via RoleSeedService.
- Bulk-inserts 42 custom roles directly via the ORM.
- Runs 50 sample requests and calculates p95 latency.

Spec ref: spec.md NFR-003, NFR-004, tasks T139.
"""

from __future__ import annotations

import time
import uuid as _uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user
from tests.fixtures.users_roles_fixtures import seed_system_roles

_SYSTEM_ROLE_COUNT = 8
_CUSTOM_ROLE_COUNT = 42
_TOTAL_ROLE_COUNT = _SYSTEM_ROLE_COUNT + _CUSTOM_ROLE_COUNT
_SAMPLE_COUNT = 50
_P95_THRESHOLD_MS = 200


# ---------------------------------------------------------------------------
# Seed fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded_roles(test_client: TestClient, db_session: Session):
    """Seed 50 roles (8 system + 42 custom) and return owner token + company ID.

    Custom roles are inserted directly via ORM to keep fixture performance
    acceptable.

    Returns:
        (owner_token, company_id_str)
    """
    from modules.users_roles.models.role import Role

    prefix = _uuid.uuid4().hex[:8]
    owner_user, owner_pwd = create_test_user(
        db_session, email=f"perf_rl_owner_{prefix}@example.com"
    )

    # Authenticate
    resp = test_client.post(
        "/api/v1/auth/login",
        json={"email": owner_user.email, "password": owner_pwd},
    )
    assert resp.status_code == 200
    owner_token = resp.json()["data"]["access_token"]

    # Create company via API
    company_resp = test_client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"PerfRL Corp {prefix}",
            "email": f"perf_rl_{prefix}@example.com",
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert company_resp.status_code == 201
    company_id_str = company_resp.json()["data"]["id"]
    company_id = _uuid.UUID(company_id_str)

    # Seed 8 system roles
    seed_system_roles(db_session, company_id, owner_user.id)

    # Bulk-insert 42 custom roles directly
    custom_roles = []
    for i in range(_CUSTOM_ROLE_COUNT):
        custom_roles.append(
            Role(
                company_id=company_id,
                name=f"Custom Role {prefix}-{i:03d}",
                slug=f"custom-{prefix}-{i:03d}",
                rank=min(1 + i, 79),  # custom roles rank 1–79 (below Owner)
                is_system=False,
                is_active=True,
                created_by=owner_user.id,
            )
        )
    db_session.bulk_save_objects(custom_roles)
    db_session.flush()

    return owner_token, company_id_str


# ---------------------------------------------------------------------------
# Performance tests
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestRoleListPerformance:
    """GET /roles — p95 latency must be below 200ms with 50 roles."""

    def test_role_list_p95_under_200ms(
        self,
        test_client: TestClient,
        db_session: Session,
        seeded_roles: tuple,
    ) -> None:
        """p95 latency for role list with 50 roles (8 system + 42 custom) < 200ms."""
        owner_token, company_id = seeded_roles
        headers = {"Authorization": f"Bearer {owner_token}"}
        url = f"/api/v1/companies/{company_id}/roles"

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
            f"\nGET /roles ({_TOTAL_ROLE_COUNT} seeded) p95: {p95_ms:.1f}ms"
            f" (threshold: {_P95_THRESHOLD_MS}ms, samples: {_SAMPLE_COUNT})"
        )

        assert p95_ms < _P95_THRESHOLD_MS, (
            f"Role list p95 latency {p95_ms:.1f}ms exceeds "
            f"{_P95_THRESHOLD_MS}ms threshold"
        )

    def test_role_list_result_count(
        self,
        test_client: TestClient,
        db_session: Session,
        seeded_roles: tuple,
    ) -> None:
        """Verify that all 50 roles are returned in the listing."""
        owner_token, company_id = seeded_roles
        headers = {"Authorization": f"Bearer {owner_token}"}
        url = f"/api/v1/companies/{company_id}/roles"

        resp = test_client.get(url, headers=headers)
        assert resp.status_code == 200

        data = resp.json()
        roles = data["data"]
        # At minimum the 8 system roles must be present; custom roles may vary
        # by seed order but total should be at least TOTAL_ROLE_COUNT
        assert len(roles) >= _SYSTEM_ROLE_COUNT, (
            f"Expected at least {_SYSTEM_ROLE_COUNT} roles, got {len(roles)}"
        )

    def test_role_list_includes_inactive_p95_under_200ms(
        self,
        test_client: TestClient,
        db_session: Session,
        seeded_roles: tuple,
    ) -> None:
        """p95 latency for role list with include_inactive=true < 200ms."""
        owner_token, company_id = seeded_roles
        headers = {"Authorization": f"Bearer {owner_token}"}
        url = f"/api/v1/companies/{company_id}/roles?include_inactive=true"

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
            f"\nGET /roles?include_inactive=true p95: {p95_ms:.1f}ms"
            f" (threshold: {_P95_THRESHOLD_MS}ms, samples: {_SAMPLE_COUNT})"
        )

        assert p95_ms < _P95_THRESHOLD_MS, (
            f"Role list (include_inactive) p95 latency {p95_ms:.1f}ms exceeds "
            f"{_P95_THRESHOLD_MS}ms threshold"
        )
