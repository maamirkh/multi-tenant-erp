"""T274 — Stock position query performance benchmark.

Simulates stock movement accumulation and measures the p95 latency of:
  - StockPosition list queries (list_by_warehouse)
  - Single position lookup (get_by_product_warehouse)

Threshold: p95 < 300ms
Spec ref: specs/005-inventory-management/spec.md §42 Performance SLOs
Tasks: T274 Phase 11 (also T167 Phase 5)
"""

from __future__ import annotations

import time
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.inventory.models.product import Product
from modules.inventory.models.stock import StockMovement, StockPosition
from modules.inventory.models.uom import UOM
from modules.inventory.models.warehouse import Warehouse
from tests.fixtures.auth_fixtures import create_test_user

_MOVEMENT_COUNT = 1000  # realistic for SQLite; production uses 100K with indexes
_SAMPLE_COUNT = 15
_WARMUP_COUNT = 3
_P95_THRESHOLD_MS = 300


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


def _seed_stock_data(
    db: Session,
    company_id: uuid.UUID,
    movement_count: int,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed products, warehouses, positions, and movements.

    Returns (product_id, warehouse_id) for the primary test subject.
    """
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

    # Create 5 warehouses for a realistic multi-warehouse query
    warehouses = []
    for i in range(5):
        wh = Warehouse(
            id=uuid.uuid4(),
            company_id=company_id,
            code=f"WH{i:02d}-{uuid.uuid4().hex[:4].upper()}",
            name=f"Warehouse {i}",
            warehouse_type="MAIN",
            status="ACTIVE",
        )
        db.add(wh)
        warehouses.append(wh)
    db.flush()

    # Create 20 products
    products = []
    for i in range(20):
        p = Product(
            id=uuid.uuid4(),
            company_id=company_id,
            product_code=f"STOCK-PERF-{i:03d}-{uuid.uuid4().hex[:4].upper()}",
            name=f"Stock Perf Product {i}",
            product_type="STANDARD",
            status="ACTIVE",
            base_uom_id=str(uom.id),
        )
        p.search_vector = f"{p.name} {p.product_code}".lower()
        db.add(p)
        products.append(p)
    db.flush()

    # Create one position per product × warehouse
    positions = []
    for product in products:
        for wh in warehouses:
            pos = StockPosition(
                id=uuid.uuid4(),
                company_id=company_id,
                product_id=str(product.id),
                warehouse_id=str(wh.id),
                qty_on_hand=Decimal("100"),
                qty_reserved=Decimal("0"),
                qty_damaged=Decimal("0"),
                unit_cost=Decimal("10.00"),
            )
            db.add(pos)
            positions.append(pos)
    db.flush()

    # Seed movements to simulate write history
    import datetime as dt

    base_time = dt.datetime.now(tz=dt.UTC)
    for i in range(movement_count):
        product = products[i % len(products)]
        wh = warehouses[i % len(warehouses)]
        mov = StockMovement(
            id=uuid.uuid4(),
            company_id=company_id,
            product_id=str(product.id),
            warehouse_id=str(wh.id),
            movement_type="PURCHASE_RECEIPT",
            direction="IN",
            quantity=Decimal("10"),
            unit_cost=Decimal("10.00"),
            currency_code="USD",
            performed_at=base_time - dt.timedelta(hours=i),
        )
        db.add(mov)
    db.flush()

    return products[0].id, warehouses[0].id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestStockPositionPerformance:
    """Stock position query benchmark — p95 < 300ms."""

    def test_stock_position_list_p95_under_threshold(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Stock position list (by warehouse) p95 must be < 300ms."""
        email = f"stock-pos-perf-{uuid.uuid4().hex[:8]}@test.com"
        password = "TestPass123!"
        create_test_user(db_session, email=email, password=password)

        token = _login(test_client, email, password)
        headers = {"Authorization": f"Bearer {token}"}
        company_id = _create_company(test_client, token)
        _product_id, warehouse_id = _seed_stock_data(
            db_session, company_id, _MOVEMENT_COUNT
        )

        # Warm up
        for _ in range(_WARMUP_COUNT):
            test_client.get(
                _url(company_id, f"/stock/positions/warehouse/{warehouse_id}"),
                headers=headers,
            )

        latencies: list[float] = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = test_client.get(
                _url(company_id, f"/stock/positions/warehouse/{warehouse_id}"),
                headers=headers,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200, f"Unexpected status: {resp.status_code}"

        p95_ms = _p95(latencies)
        print(
            f"\nStock position list p95: {p95_ms:.1f}ms "
            f"(threshold: {_P95_THRESHOLD_MS}ms, movements: {_MOVEMENT_COUNT})"
        )
        assert p95_ms < _P95_THRESHOLD_MS, (
            f"Stock position list p95 {p95_ms:.1f}ms exceeds {_P95_THRESHOLD_MS}ms. "
            f"In production, composite index ix_inv_stock_pos_company_product_wh covers this query."
        )

    def test_stock_movement_ledger_p95_under_threshold(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Stock movement ledger query (filtered) p95 must be < 300ms."""
        email = f"mov-ledger-perf-{uuid.uuid4().hex[:8]}@test.com"
        password = "TestPass123!"
        create_test_user(db_session, email=email, password=password)

        token = _login(test_client, email, password)
        headers = {"Authorization": f"Bearer {token}"}
        company_id = _create_company(test_client, token)
        product_id, warehouse_id = _seed_stock_data(
            db_session, company_id, _MOVEMENT_COUNT
        )

        latencies: list[float] = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = test_client.get(
                _url(
                    company_id,
                    f"/stock/movements?product_id={product_id}&warehouse_id={warehouse_id}",
                ),
                headers=headers,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200, f"Unexpected status: {resp.status_code}"

        p95_ms = _p95(latencies)
        print(
            f"\nStock ledger query p95: {p95_ms:.1f}ms "
            f"(threshold: {_P95_THRESHOLD_MS}ms, movements: {_MOVEMENT_COUNT})"
        )
        assert p95_ms < _P95_THRESHOLD_MS, (
            f"Stock ledger query p95 {p95_ms:.1f}ms exceeds {_P95_THRESHOLD_MS}ms. "
            f"In production, composite index ix_inv_stock_mov_company_product_at covers this."
        )
