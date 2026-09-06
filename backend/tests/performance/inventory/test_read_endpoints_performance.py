"""T276 — Read endpoint latency benchmark for all inventory list endpoints.

Verifies that all read (GET list) endpoints return p95 < 200ms on the
test environment (SQLite in-memory).

Spec ref: specs/005-inventory-management/spec.md §42 Performance SLOs
Tasks: T276 Phase 11
"""

from __future__ import annotations

import time
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.inventory.models.adjustment import InventoryAdjustment
from modules.inventory.models.alerts import LowStockAlert
from modules.inventory.models.product import Product
from modules.inventory.models.stock import StockMovement, StockPosition
from modules.inventory.models.uom import UOM
from modules.inventory.models.warehouse import Warehouse
from tests.fixtures.auth_fixtures import create_test_user

_SAMPLE_COUNT = 15
_WARMUP_COUNT = 3
_P95_THRESHOLD_MS = 200


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


def _measure_endpoint(
    client: TestClient,
    url: str,
    headers: dict[str, str],
    sample_count: int = _SAMPLE_COUNT,
    warmup_count: int = _WARMUP_COUNT,
) -> float:
    """Measure p95 latency for a GET endpoint. Returns p95 in ms."""
    for _ in range(warmup_count):
        client.get(url, headers=headers)

    latencies: list[float] = []
    for _ in range(sample_count):
        start = time.perf_counter()
        resp = client.get(url, headers=headers)
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)
        assert resp.status_code == 200, f"Unexpected {resp.status_code} for {url}"

    return _p95(latencies)


def _seed_all(db: Session, company_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """Seed representative data across all inventory entities. Returns key IDs."""
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

    wh = Warehouse(
        id=uuid.uuid4(),
        company_id=company_id,
        code=f"WH-{uuid.uuid4().hex[:4].upper()}",
        name="Main Warehouse",
        warehouse_type="MAIN",
        status="ACTIVE",
    )
    db.add(wh)
    db.flush()

    from modules.inventory.models.reason_code import ReasonCode

    rc = ReasonCode(
        id=uuid.uuid4(),
        company_id=company_id,
        code=f"DMG{uuid.uuid4().hex[:4].upper()}",
        label="Damage",
        applies_to="ADJUSTMENT",
        is_active=True,
    )
    db.add(rc)
    db.flush()

    products = []
    for i in range(20):
        p = Product(
            id=uuid.uuid4(),
            company_id=company_id,
            product_code=f"READ-{i:03d}-{uuid.uuid4().hex[:4].upper()}",
            name=f"Read Perf Product {i}",
            product_type="STANDARD",
            status="ACTIVE",
            base_uom_id=str(uom.id),
        )
        p.search_vector = f"{p.name} {p.product_code}".lower()
        db.add(p)
        products.append(p)
    db.flush()

    positions = []
    for p in products:
        pos = StockPosition(
            id=uuid.uuid4(),
            company_id=company_id,
            product_id=str(p.id),
            warehouse_id=str(wh.id),
            qty_on_hand=Decimal("50"),
            qty_reserved=Decimal("0"),
            qty_damaged=Decimal("0"),
            unit_cost=Decimal("10.00"),
        )
        db.add(pos)
        positions.append(pos)
    db.flush()

    import datetime as dt

    base_time = dt.datetime.now(tz=dt.UTC)
    for i, p in enumerate(products[:10]):
        mov = StockMovement(
            id=uuid.uuid4(),
            company_id=company_id,
            product_id=str(p.id),
            warehouse_id=str(wh.id),
            movement_type="OPENING",
            direction="IN",
            quantity=Decimal("50"),
            unit_cost=Decimal("10.00"),
            currency_code="USD",
            performed_at=base_time - dt.timedelta(hours=i),
        )
        db.add(mov)

    for i, p in enumerate(products[:5]):
        adj = InventoryAdjustment(
            id=uuid.uuid4(),
            company_id=company_id,
            product_id=str(p.id),
            warehouse_id=str(wh.id),
            reason_code_id=str(rc.id),
            quantity=2.0,
            movement_type="ADJUSTMENT_IN",
            old_quantity=Decimal("50"),
            status="DRAFT",
        )
        db.add(adj)

    for i, p in enumerate(products[:5]):
        alert = LowStockAlert(
            id=uuid.uuid4(),
            company_id=company_id,
            product_id=str(p.id),
            warehouse_id=str(wh.id),
            alert_type="LOW_STOCK",
            status="OPEN",
            current_quantity=Decimal("5"),
            threshold_quantity=Decimal("10"),
        )
        db.add(alert)

    db.flush()

    return {
        "warehouse_id": wh.id,
        "product_id": products[0].id,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestReadEndpointsPerformance:
    """All inventory read endpoints p95 < 200ms benchmark."""

    def test_all_read_endpoints_p95(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """All inventory list endpoints must respond with p95 < 200ms."""
        email = f"read-perf-{uuid.uuid4().hex[:8]}@test.com"
        password = "TestPass123!"
        create_test_user(db_session, email=email, password=password)

        token = _login(test_client, email, password)
        headers = {"Authorization": f"Bearer {token}"}
        company_id = _create_company(test_client, token)
        ids = _seed_all(db_session, company_id)

        endpoints = [
            ("/products", "Product list"),
            ("/categories", "Category list"),
            ("/warehouses", "Warehouse list"),
            (f"/stock/positions/warehouse/{ids['warehouse_id']}", "Stock positions"),
            ("/stock/movements", "Stock movements"),
            ("/adjustments", "Adjustments list"),
            ("/alerts", "Alerts list"),
            ("/stock-transfers", "Transfers list"),
        ]

        failures = []
        results = []
        for path, label in endpoints:
            p95_ms = _measure_endpoint(
                test_client,
                _url(company_id, path),
                headers,
            )
            status = "PASS" if p95_ms < _P95_THRESHOLD_MS else "FAIL"
            results.append((label, p95_ms, status))
            if p95_ms >= _P95_THRESHOLD_MS:
                failures.append(
                    f"{label}: p95={p95_ms:.1f}ms (threshold: {_P95_THRESHOLD_MS}ms)"
                )

        # Print benchmark table
        print("\n\nRead Endpoint Benchmark Results:")
        print(f"{'Endpoint':<35} {'p95 (ms)':>10} {'Status':>8}")
        print("-" * 55)
        for label, p95_ms, status in results:
            print(f"{label:<35} {p95_ms:>10.1f} {status:>8}")

        assert not failures, (
            f"The following endpoints exceed {_P95_THRESHOLD_MS}ms p95:\n"
            + "\n".join(failures)
        )

    def test_reports_endpoints_p95(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Inventory report endpoints must respond with p95 < 200ms."""
        email = f"rpt-perf-{uuid.uuid4().hex[:8]}@test.com"
        password = "TestPass123!"
        create_test_user(db_session, email=email, password=password)

        token = _login(test_client, email, password)
        headers = {"Authorization": f"Bearer {token}"}
        company_id = _create_company(test_client, token)
        _seed_all(db_session, company_id)

        report_endpoints = [
            ("/reports/inventory-summary", "Inventory Summary"),
            ("/reports/stock-position", "Stock Position Report"),
            ("/reports/inventory-valuation", "Inventory Valuation"),
            ("/kpis", "KPI Dashboard"),
        ]

        failures = []
        results = []
        for path, label in report_endpoints:
            p95_ms = _measure_endpoint(
                test_client,
                _url(company_id, path),
                headers,
            )
            status = "PASS" if p95_ms < _P95_THRESHOLD_MS else "FAIL"
            results.append((label, p95_ms, status))
            if p95_ms >= _P95_THRESHOLD_MS:
                failures.append(
                    f"{label}: p95={p95_ms:.1f}ms (threshold: {_P95_THRESHOLD_MS}ms)"
                )

        print("\n\nReport Endpoint Benchmark Results:")
        print(f"{'Endpoint':<35} {'p95 (ms)':>10} {'Status':>8}")
        print("-" * 55)
        for label, p95_ms, status in results:
            print(f"{label:<35} {p95_ms:>10.1f} {status:>8}")

        assert not failures, (
            f"The following report endpoints exceed {_P95_THRESHOLD_MS}ms p95:\n"
            + "\n".join(failures)
        )
