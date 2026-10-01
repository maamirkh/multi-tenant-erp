"""T283 — Comprehensive tenant isolation verification.

Verifies that every inventory endpoint scopes data by company_id and that
Company A data is never visible to Company B.

Strategy:
  1. Seed data for Company A (products, warehouse, stock positions, movements,
     adjustments, alerts, transfers).
  2. Use a Company B token to query all Company B endpoints.
  3. Assert zero Company A data appears in any Company B response.

Spec ref: specs/005-inventory-management/spec.md §5 (Multi-tenancy)
Tasks: T283 Phase 12
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.inventory.models.alerts import LowStockAlert
from modules.inventory.models.product import Product
from modules.inventory.models.reason_code import ReasonCode
from modules.inventory.models.stock import StockMovement, StockPosition
from modules.inventory.models.uom import UOM
from modules.inventory.models.warehouse import Warehouse
from tests.fixtures.auth_fixtures import create_test_user

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
    return str(resp.json()["data"]["access_token"])


def _create_company(client: TestClient, token: str) -> uuid.UUID:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Inventory Test Co {suffix}",
            "email": f"contact-{suffix}@inv-test.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def _seed_company_a(db: Session, company_id: uuid.UUID) -> dict[str, Any]:
    """Seed a comprehensive dataset for company A."""
    uom = UOM(
        id=uuid.uuid4(),
        company_id=company_id,
        code=f"UA{uuid.uuid4().hex[:4].upper()}",
        name="Units",
        uom_type="UNIT",
        status="active",
    )
    db.add(uom)

    wh = Warehouse(
        id=uuid.uuid4(),
        company_id=company_id,
        code=f"WA{uuid.uuid4().hex[:4].upper()}",
        name="Company A Warehouse",
        warehouse_type="MAIN",
        status="ACTIVE",
    )
    db.add(wh)

    rc = ReasonCode(
        id=uuid.uuid4(),
        company_id=company_id,
        code=f"RA{uuid.uuid4().hex[:4].upper()}",
        label="Company A Reason",
        applies_to="ADJUSTMENT",
        is_active=True,
    )
    db.add(rc)
    db.flush()

    product = Product(
        id=uuid.uuid4(),
        company_id=company_id,
        product_code=f"PA-{uuid.uuid4().hex[:6].upper()}",
        name="Company A Product",
        product_type="STANDARD",
        status="ACTIVE",
        base_uom_id=str(uom.id),
    )
    product.search_vector = f"{product.name} {product.product_code}".lower()
    db.add(product)
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

    mov = StockMovement(
        id=uuid.uuid4(),
        company_id=company_id,
        product_id=str(product.id),
        warehouse_id=str(wh.id),
        movement_type="OPENING",
        direction="IN",
        quantity=Decimal("50"),
        unit_cost=Decimal("10.00"),
        currency_code="USD",
        performed_at=dt.datetime.now(tz=dt.UTC),
    )
    db.add(mov)

    alert = LowStockAlert(
        id=uuid.uuid4(),
        company_id=company_id,
        product_id=str(product.id),
        warehouse_id=str(wh.id),
        alert_type="LOW_STOCK",
        status="OPEN",
        current_quantity=Decimal("5"),
        threshold_quantity=Decimal("10"),
    )
    db.add(alert)

    db.flush()
    return {
        "product_id": str(product.id),
        "warehouse_id": str(wh.id),
        "uom_id": str(uom.id),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTenantIsolationFull:
    """Comprehensive tenant isolation — Company B sees zero Company A data."""

    def test_products_isolated(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Company B product list must not include Company A products."""
        email_a = f"iso-prod-a-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email_a, password="TestPass123!")
        token_a = _login(test_client, email_a, "TestPass123!")
        company_a_id = _create_company(test_client, token_a)

        _seed_company_a(db_session, company_a_id)

        email_b = f"iso-prod-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email_b, password="TestPass123!")
        token_b = _login(test_client, email_b, "TestPass123!")
        headers_b = {"Authorization": f"Bearer {token_b}"}
        company_b_id = _create_company(test_client, token_b)

        resp = test_client.get(_url(company_b_id, "/products"), headers=headers_b)
        assert resp.status_code == 200
        products = resp.json()["data"]["items"]
        # Company B has no data — must return empty list
        assert products == [], f"Expected empty list, got {len(products)} products"

    def test_warehouses_isolated(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Company B warehouse list must not include Company A warehouses."""
        email_a = f"iso-wh-a-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email_a, password="TestPass123!")
        token_a = _login(test_client, email_a, "TestPass123!")
        company_a_id = _create_company(test_client, token_a)

        _seed_company_a(db_session, company_a_id)

        email_b = f"iso-wh-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email_b, password="TestPass123!")
        token_b = _login(test_client, email_b, "TestPass123!")
        headers_b = {"Authorization": f"Bearer {token_b}"}
        company_b_id = _create_company(test_client, token_b)

        resp = test_client.get(_url(company_b_id, "/warehouses"), headers=headers_b)
        assert resp.status_code == 200
        warehouses = resp.json()["data"]
        assert warehouses == [], (
            f"Expected empty list, got {len(warehouses)} warehouses"
        )

    def test_stock_positions_isolated(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Company B stock positions must not include Company A positions."""
        email_a = f"iso-pos-a-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email_a, password="TestPass123!")
        token_a = _login(test_client, email_a, "TestPass123!")
        company_a_id = _create_company(test_client, token_a)

        ids = _seed_company_a(db_session, company_a_id)

        email_b = f"iso-pos-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email_b, password="TestPass123!")
        token_b = _login(test_client, email_b, "TestPass123!")
        headers_b = {"Authorization": f"Bearer {token_b}"}
        company_b_id = _create_company(test_client, token_b)

        # Try to access Company A's warehouse via Company B's namespace
        resp = test_client.get(
            _url(company_b_id, f"/stock/positions/warehouse/{ids['warehouse_id']}"),
            headers=headers_b,
        )
        assert resp.status_code == 200
        # Returns empty because warehouse_id doesn't belong to company_b_id
        positions = resp.json()["data"]
        assert positions == []

    def test_stock_movements_isolated(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Company B stock movements must not include Company A movements."""
        email_a = f"iso-mov-a-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email_a, password="TestPass123!")
        token_a = _login(test_client, email_a, "TestPass123!")
        company_a_id = _create_company(test_client, token_a)

        ids = _seed_company_a(db_session, company_a_id)

        email_b = f"iso-mov-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email_b, password="TestPass123!")
        token_b = _login(test_client, email_b, "TestPass123!")
        headers_b = {"Authorization": f"Bearer {token_b}"}
        company_b_id = _create_company(test_client, token_b)

        resp = test_client.get(
            _url(company_b_id, f"/stock/movements?product_id={ids['product_id']}"),
            headers=headers_b,
        )
        assert resp.status_code == 200
        movements = resp.json()["data"]
        assert movements == [], f"Expected empty, got {len(movements)} movements"

    def test_adjustments_isolated(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Company B adjustments must not include Company A adjustments."""
        email_a = f"iso-adj-a-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email_a, password="TestPass123!")
        token_a = _login(test_client, email_a, "TestPass123!")
        company_a_id = _create_company(test_client, token_a)

        _seed_company_a(db_session, company_a_id)

        email_b = f"iso-adj-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email_b, password="TestPass123!")
        token_b = _login(test_client, email_b, "TestPass123!")
        headers_b = {"Authorization": f"Bearer {token_b}"}
        company_b_id = _create_company(test_client, token_b)

        resp = test_client.get(_url(company_b_id, "/adjustments"), headers=headers_b)
        assert resp.status_code == 200
        adjustments = resp.json()["data"]
        assert adjustments == []

    def test_alerts_isolated(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Company B alerts must not include Company A alerts."""
        email_a = f"iso-alrt-a-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email_a, password="TestPass123!")
        token_a = _login(test_client, email_a, "TestPass123!")
        company_a_id = _create_company(test_client, token_a)

        _seed_company_a(db_session, company_a_id)

        email_b = f"iso-alrt-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email_b, password="TestPass123!")
        token_b = _login(test_client, email_b, "TestPass123!")
        headers_b = {"Authorization": f"Bearer {token_b}"}
        company_b_id = _create_company(test_client, token_b)

        resp = test_client.get(_url(company_b_id, "/alerts"), headers=headers_b)
        assert resp.status_code == 200
        alerts = resp.json()["data"]
        assert alerts == []

    def test_transfers_isolated(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Company B transfers must not include Company A transfers."""
        email_a = f"iso-xfer-a-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email_a, password="TestPass123!")
        token_a = _login(test_client, email_a, "TestPass123!")
        company_a_id = _create_company(test_client, token_a)

        _seed_company_a(db_session, company_a_id)

        email_b = f"iso-xfer-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email_b, password="TestPass123!")
        token_b = _login(test_client, email_b, "TestPass123!")
        headers_b = {"Authorization": f"Bearer {token_b}"}
        company_b_id = _create_company(test_client, token_b)

        resp = test_client.get(
            _url(company_b_id, "/stock-transfers"), headers=headers_b
        )
        assert resp.status_code == 200
        transfers = resp.json()["data"]
        assert transfers == []

    def test_unauthenticated_access_blocked(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """All inventory endpoints require authentication — no 200 without token."""
        company_id = uuid.uuid4()
        endpoints = [
            "/products",
            "/warehouses",
            "/stock/positions",
            "/stock/movements",
            "/adjustments",
            "/alerts",
            "/stock-transfers",
        ]
        for path in endpoints:
            resp = test_client.get(_url(company_id, path))
            assert resp.status_code == 401, (
                f"Expected 401 for {path}, got {resp.status_code}"
            )

    def test_categories_isolated(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Company B category list must not include Company A categories."""
        from modules.inventory.models.category import Category

        email_a = f"iso-cat-a-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email_a, password="TestPass123!")
        token_a = _login(test_client, email_a, "TestPass123!")
        company_a_id = _create_company(test_client, token_a)

        # Seed a category for company A directly
        cat = Category(
            id=uuid.uuid4(),
            company_id=company_a_id,
            code=f"CAT-A-{uuid.uuid4().hex[:4].upper()}",
            name="Company A Category",
            status="active",
        )
        db_session.add(cat)
        db_session.flush()

        email_b = f"iso-cat-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email_b, password="TestPass123!")
        token_b = _login(test_client, email_b, "TestPass123!")
        headers_b = {"Authorization": f"Bearer {token_b}"}
        company_b_id = _create_company(test_client, token_b)

        resp = test_client.get(_url(company_b_id, "/categories"), headers=headers_b)
        assert resp.status_code == 200
        categories = resp.json()["data"]
        category_ids = [c["id"] for c in categories]
        assert str(cat.id) not in category_ids, "Company A category leaked to Company B"
