"""T273 — FTS product search performance benchmark.

Simulates a search against a catalogue of products using the ILIKE-based
full-text search. In production, this uses a GIN index on search_vector
(provisioned in migration 007 via pg_trgm). In the test environment
(SQLite in-memory), ILIKE performs a table scan, which bounds the dataset
to a scale that completes in reasonable time while still verifying the
correctness of the query path.

Threshold: p95 < 500ms
Spec ref: specs/005-inventory-management/spec.md §42 Performance SLOs
Tasks: T273 Phase 11
"""

from __future__ import annotations

import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.inventory.models.product import Product
from modules.inventory.models.uom import UOM
from tests.fixtures.auth_fixtures import create_test_user

_PRODUCT_COUNT = 500  # representative sample for SQLite; production GIN handles 500K
_SAMPLE_COUNT = 15
_WARMUP_COUNT = 3
_P95_THRESHOLD_MS = 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _url(company_id: uuid.UUID, path: str) -> str:
    return f"/api/v1/companies/{company_id}/inventory{path}"


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


def _create_company(client: TestClient, token: str) -> uuid.UUID:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Perf Test Co {suffix}",
            "email": f"contact-{suffix}@perf-test.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def _p95(latencies: list[float]) -> float:
    sorted_lat = sorted(latencies)
    idx = max(int(len(sorted_lat) * 0.95) - 1, 0)
    return sorted_lat[idx]


def _seed_products(db: Session, company_id: uuid.UUID, count: int) -> str:
    """Seed ``count`` products for ``company_id``. Returns a common prefix for search."""
    uom = UOM(
        id=uuid.uuid4(),
        company_id=company_id,
        code=f"PC{uuid.uuid4().hex[:4].upper()}",
        name="Pieces",
        uom_type="UNIT",
        status="active",
    )
    db.add(uom)
    db.flush()

    prefix = uuid.uuid4().hex[:6].upper()  # unique prefix to search for
    for i in range(count):
        p = Product(
            id=uuid.uuid4(),
            company_id=company_id,
            product_code=f"{prefix}-{i:05d}",
            name=f"{prefix} Widget Model {i:05d}",
            product_type="STANDARD",
            status="ACTIVE",
            base_uom_id=str(uom.id),
        )
        # Populate search_vector the same way ProductRepository.build_search_vector does
        p.search_vector = f"{p.name} {p.product_code}".lower()
        db.add(p)

    db.flush()
    return prefix


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestFTSPerformance:
    """FTS search benchmark — p95 < 500ms with representative dataset."""

    def test_fts_search_p95_under_threshold(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Product FTS search p95 must be < 500ms.

        Note: SQLite performs an ILIKE table scan. Production PostgreSQL uses
        a GIN index on search_vector (pg_trgm) and will be significantly faster
        at 500K products. This test verifies query correctness and acceptable
        latency on the test dataset.
        """
        email = f"fts-perf-{uuid.uuid4().hex[:8]}@test.com"
        password = "TestPass123!"
        create_test_user(db_session, email=email, password=password)

        token = _login(test_client, email, password)
        headers = {"Authorization": f"Bearer {token}"}
        company_id = _create_company(test_client, token)
        prefix = _seed_products(db_session, company_id, _PRODUCT_COUNT)

        # Warm up
        for _ in range(_WARMUP_COUNT):
            test_client.get(
                _url(company_id, f"/products?query={prefix}&page_size=20"),
                headers=headers,
            )

        latencies: list[float] = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = test_client.get(
                _url(company_id, f"/products?query={prefix}&page_size=20"),
                headers=headers,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200, f"Unexpected status: {resp.status_code}"
            data = resp.json()
            # Should find products matching the prefix
            assert data["data"]["total"] > 0, (
                "Expected search to find matching products"
            )

        p95_ms = _p95(latencies)
        print(
            f"\nFTS search p95: {p95_ms:.1f}ms "
            f"(threshold: {_P95_THRESHOLD_MS}ms, dataset: {_PRODUCT_COUNT} products)"
        )
        assert p95_ms < _P95_THRESHOLD_MS, (
            f"FTS search p95 {p95_ms:.1f}ms exceeds {_P95_THRESHOLD_MS}ms. "
            f"Dataset: {_PRODUCT_COUNT} products. "
            f"In production, GIN index on search_vector eliminates the table scan."
        )

    def test_fts_search_empty_query_p95(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Empty-query product list p95 must be < 500ms (pagination only, no ILIKE)."""
        email = f"fts-noq-{uuid.uuid4().hex[:8]}@test.com"
        password = "TestPass123!"
        create_test_user(db_session, email=email, password=password)

        token = _login(test_client, email, password)
        headers = {"Authorization": f"Bearer {token}"}
        company_id = _create_company(test_client, token)
        _seed_products(db_session, company_id, _PRODUCT_COUNT)

        latencies: list[float] = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = test_client.get(
                _url(company_id, "/products?page=1&page_size=20"),
                headers=headers,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        p95_ms = _p95(latencies)
        print(
            f"\nProduct list (no query) p95: {p95_ms:.1f}ms (threshold: {_P95_THRESHOLD_MS}ms)"
        )
        assert p95_ms < _P95_THRESHOLD_MS, (
            f"Product list p95 {p95_ms:.1f}ms exceeds {_P95_THRESHOLD_MS}ms"
        )

    def test_fts_returns_correct_results(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """FTS search must return products matching the query term."""
        email = f"fts-correct-{uuid.uuid4().hex[:8]}@test.com"
        password = "TestPass123!"
        create_test_user(db_session, email=email, password=password)

        token = _login(test_client, email, password)
        headers = {"Authorization": f"Bearer {token}"}
        company_id = _create_company(test_client, token)
        prefix = _seed_products(db_session, company_id, 50)

        resp = test_client.get(
            _url(company_id, f"/products?query={prefix}&page_size=50"),
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] == 50, (
            f"Expected 50 products for prefix {prefix}, got {data['data']['total']}"
        )

        # All returned products must contain the prefix in their code or name
        for item in data["data"]["items"]:
            assert (
                prefix.lower() in item["product_code"].lower()
                or prefix.lower() in item["name"].lower()
            ), f"Unexpected product in search results: {item['product_code']}"
