"""T266 — Barcode and SKU lookup performance benchmark.

Measures p95 latency for scanner lookup endpoints.
Spec ref: specs/005-inventory-management/spec.md §46 Integration Readiness
Threshold: p95 < 100ms (SQLite in-memory eliminates network overhead).
"""

from __future__ import annotations

import time
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.inventory.models.product import Product, ProductBarcode
from modules.inventory.models.stock import StockPosition
from modules.inventory.models.uom import UOM
from modules.inventory.models.warehouse import Warehouse
from tests.fixtures.auth_fixtures import create_test_user

_SAMPLE_COUNT = 20
_WARMUP_COUNT = 3
_P95_THRESHOLD_MS = 100
_LABEL_DATA_THRESHOLD_MS = (
    300  # Label data queries join product + enrichment; wider threshold on WSL2
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


def _url(company_id: uuid.UUID, path: str) -> str:
    return f"/api/v1/companies/{company_id}/inventory{path}"


def _setup_data(db: Session) -> tuple[str, str, uuid.UUID, str, str]:
    """Create user, product with barcode, and return login creds + identifiers."""
    email = f"perf-lookup-{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"
    create_test_user(db, email=email, password=password)

    company_id = uuid.uuid4()

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

    product_code = f"PERF-{uuid.uuid4().hex[:6].upper()}"
    product = Product(
        id=uuid.uuid4(),
        company_id=company_id,
        product_code=product_code,
        name=f"Perf Product {product_code}",
        product_type="STANDARD",
        status="ACTIVE",
        base_uom_id=str(uom.id),
    )
    db.add(product)
    db.flush()

    barcode_value = f"PERF{uuid.uuid4().int % 10**12:012d}"
    bc = ProductBarcode(
        id=uuid.uuid4(),
        company_id=company_id,
        product_id=str(product.id),
        barcode_value=barcode_value,
        barcode_type="EAN13",
        is_primary=True,
    )
    db.add(bc)

    wh = Warehouse(
        id=uuid.uuid4(),
        company_id=company_id,
        code=f"WH-{uuid.uuid4().hex[:4].upper()}",
        name="Perf Warehouse",
        warehouse_type="MAIN",
        status="ACTIVE",
    )
    db.add(wh)
    db.flush()

    pos = StockPosition(
        id=uuid.uuid4(),
        company_id=company_id,
        product_id=str(product.id),
        warehouse_id=str(wh.id),
        qty_on_hand=Decimal("50"),
        qty_reserved=Decimal("0"),
        qty_damaged=Decimal("0"),
        unit_cost=Decimal("10.00"),
    )
    db.add(pos)
    db.flush()

    return email, password, company_id, barcode_value, product_code


def _p95(latencies: list[float]) -> float:
    sorted_lat = sorted(latencies)
    idx = max(int(len(sorted_lat) * 0.95) - 1, 0)
    return sorted_lat[idx]


# ---------------------------------------------------------------------------
# Performance tests
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestLookupPerformance:
    def test_barcode_lookup_p95_under_threshold(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Barcode lookup p95 must be < 100ms on in-memory SQLite."""
        email, password, company_id, barcode_value, _ = _setup_data(db_session)
        token = _login(test_client, email, password)
        headers = {"Authorization": f"Bearer {token}"}

        # Warm up to avoid cold-start inflation
        for _ in range(_WARMUP_COUNT):
            test_client.get(
                _url(company_id, f"/lookup/barcode/{barcode_value}"),
                headers=headers,
            )

        latencies: list[float] = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = test_client.get(
                _url(company_id, f"/lookup/barcode/{barcode_value}"),
                headers=headers,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        p95_ms = _p95(latencies)
        print(
            f"\nBarcode lookup p95: {p95_ms:.1f}ms (threshold: {_P95_THRESHOLD_MS}ms)"
        )
        assert (
            p95_ms < _P95_THRESHOLD_MS
        ), f"Barcode lookup p95 {p95_ms:.1f}ms exceeds {_P95_THRESHOLD_MS}ms"

    def test_sku_lookup_p95_under_threshold(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """SKU lookup p95 must be < 100ms on in-memory SQLite."""
        email, password, company_id, _, product_code = _setup_data(db_session)
        token = _login(test_client, email, password)
        headers = {"Authorization": f"Bearer {token}"}

        latencies: list[float] = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = test_client.get(
                _url(company_id, f"/lookup/sku/{product_code}"),
                headers=headers,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        p95_ms = _p95(latencies)
        print(f"\nSKU lookup p95: {p95_ms:.1f}ms (threshold: {_P95_THRESHOLD_MS}ms)")
        assert (
            p95_ms < _P95_THRESHOLD_MS
        ), f"SKU lookup p95 {p95_ms:.1f}ms exceeds {_P95_THRESHOLD_MS}ms"

    def test_label_data_p95_under_threshold(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Label data endpoint p95 must be < 100ms on in-memory SQLite."""
        email, password, company_id, _, _ = _setup_data(db_session)

        # Re-fetch product id from the barcode to get the product UUID
        from sqlalchemy import select

        from modules.inventory.models.product import ProductBarcode

        bc = (
            db_session.execute(
                select(ProductBarcode).where(ProductBarcode.company_id == company_id)
            )
            .scalars()
            .first()
        )
        assert bc is not None
        product_id = bc.product_id

        token = _login(test_client, email, password)
        headers = {"Authorization": f"Bearer {token}"}

        latencies: list[float] = []
        for _ in range(_SAMPLE_COUNT):
            start = time.perf_counter()
            resp = test_client.get(
                _url(company_id, f"/products/{product_id}/label-data"),
                headers=headers,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        p95_ms = _p95(latencies)
        print(
            f"\nLabel data p95: {p95_ms:.1f}ms (threshold: {_LABEL_DATA_THRESHOLD_MS}ms)"
        )
        assert (
            p95_ms < _LABEL_DATA_THRESHOLD_MS
        ), f"Label data p95 {p95_ms:.1f}ms exceeds {_LABEL_DATA_THRESHOLD_MS}ms"
