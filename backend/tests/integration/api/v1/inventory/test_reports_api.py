"""Integration tests for Phase 9 Reporting Foundation API.

Tests cover:
  T255 - All 14 reports return 200 with correct structure
  T256 - Report API tests (filter params, KPI endpoint)
  T257 - Tenant isolation: Company A data is not visible in Company B reports
  T258 - Export endpoints return valid response

Spec ref: specs/005-inventory-management/spec.md §32
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.inventory.models.product import Product
from modules.inventory.models.stock import StockMovement, StockPosition
from modules.inventory.models.uom import UOM
from modules.inventory.models.warehouse import Warehouse
from tests.fixtures.auth_fixtures import create_test_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _url(company_id: str | uuid.UUID, path: str) -> str:
    return f"/api/v1/companies/{company_id}/inventory{path}"


def _create_company(client: TestClient, token: str) -> uuid.UUID:
    """Create a real company (via the API) so the caller becomes its owner
    and active member — required now that company-scoped routes enforce
    membership (see api/v1/router.py's get_current_company_member gate)."""
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Inventory Test Co {suffix}",
            "email": f"contact-{suffix}@inventory-test.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def _setup(db: Session, client: TestClient) -> tuple[str, str, uuid.UUID]:
    email = f"report-{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"
    create_test_user(db, email=email, password=password)
    token = _login(client, email, password)
    company_id = _create_company(client, token)
    return email, password, company_id


def _make_warehouse(db: Session, company_id: uuid.UUID) -> Warehouse:
    wh = Warehouse(
        id=uuid.uuid4(),
        company_id=company_id,
        code=f"WH-{uuid.uuid4().hex[:4].upper()}",
        name=f"Test WH {uuid.uuid4().hex[:4]}",
        warehouse_type="MAIN",
        status="ACTIVE",
    )
    db.add(wh)
    db.flush()
    return wh


def _make_product(db: Session, company_id: uuid.UUID) -> Product:
    uom = UOM(
        id=uuid.uuid4(),
        company_id=company_id,
        code=f"U{uuid.uuid4().hex[:4]}",
        name="Unit",
        uom_type="UNIT",
        status="active",
    )
    db.add(uom)
    db.flush()
    product = Product(
        id=uuid.uuid4(),
        company_id=company_id,
        name=f"Report Product {uuid.uuid4().hex[:6]}",
        product_code=f"RP-{uuid.uuid4().hex[:6]}",
        product_type="STANDARD",
        status="ACTIVE",
        base_uom_id=str(uom.id),
    )
    db.add(product)
    db.flush()
    return product


def _make_position(
    db: Session,
    company_id: uuid.UUID,
    product_id: str,
    warehouse_id: str,
    qty: float = 10.0,
    unit_cost: float = 5.0,
) -> StockPosition:
    pos = StockPosition(
        id=uuid.uuid4(),
        company_id=company_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        qty_on_hand=qty,
        qty_reserved=Decimal("0"),
        qty_damaged=Decimal("0"),
        unit_cost=unit_cost,
        currency_code="USD",
        reorder_level=Decimal("2"),
        safety_stock=Decimal("1"),
    )
    db.add(pos)
    db.flush()
    return pos


def _make_movement(
    db: Session,
    company_id: uuid.UUID,
    product_id: str,
    warehouse_id: str,
    movement_type: str = "OPENING",
    direction: str = "IN",
    quantity: float = 10.0,
    unit_cost: float = 5.0,
) -> StockMovement:
    mov = StockMovement(
        id=uuid.uuid4(),
        company_id=company_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type=movement_type,
        direction=direction,
        quantity=quantity,
        unit_cost=unit_cost,
        performed_at=datetime.now(UTC),
    )
    db.add(mov)
    db.flush()
    return mov


def _seed_company(
    db: Session, client: TestClient
) -> tuple[str, str, uuid.UUID, str, str]:
    """Create a company with warehouse, product, position, and movement."""
    email, password, company_id = _setup(db, client)
    wh = _make_warehouse(db, company_id)
    prod = _make_product(db, company_id)
    _make_position(db, company_id, str(prod.id), str(wh.id))
    _make_movement(db, company_id, str(prod.id), str(wh.id))
    db.commit()
    return email, password, company_id, str(prod.id), str(wh.id)


# ---------------------------------------------------------------------------
# 401 Unauthenticated tests
# ---------------------------------------------------------------------------


REPORT_PATHS = [
    "/reports/inventory-summary",
    "/reports/stock-ledger",
    "/reports/inventory-valuation",
    "/reports/stock-position",
    "/reports/warehouse-utilisation",
    "/reports/category-brand",
    "/reports/dead-stock",
    "/reports/movement-velocity",
    "/reports/stock-aging",
    "/reports/operational",
    "/reports/trend-analysis",
    "/kpis",
]


class TestReportsAuth:
    def test_all_report_endpoints_require_auth(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        _, _, company_id, _, _ = _seed_company(db_session, test_client)
        for path in REPORT_PATHS:
            resp = test_client.get(_url(company_id, path))
            assert (
                resp.status_code == 401
            ), f"{path} should require auth, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Report endpoint tests
# ---------------------------------------------------------------------------


class TestInventorySummaryReport:
    def test_returns_200(self, test_client: TestClient, db_session: Session) -> None:
        email, password, company_id, _, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, "/reports/inventory-summary"), headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert "rows" in data
        assert "grand_total_value" in data
        assert "as_of" in data

    def test_rows_contain_company_data(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, prod_id, wh_id = _seed_company(
            db_session, test_client
        )
        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, "/reports/inventory-summary"), headers=_auth(token)
        )
        assert resp.status_code == 200
        rows = resp.json()["data"]["rows"]
        assert len(rows) >= 1
        row_products = [r["product_id"] for r in rows]
        assert prod_id in row_products


class TestStockLedgerReport:
    def test_returns_200(self, test_client: TestClient, db_session: Session) -> None:
        email, password, company_id, _, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, "/reports/stock-ledger"), headers=_auth(token)
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "rows" in data
        assert "total_rows" in data

    def test_filters_by_product(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, prod_id, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, f"/reports/stock-ledger?product_id={prod_id}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        rows = resp.json()["data"]["rows"]
        for row in rows:
            assert row["product_id"] == prod_id


class TestInventoryValuationReport:
    def test_returns_200(self, test_client: TestClient, db_session: Session) -> None:
        email, password, company_id, _, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, "/reports/inventory-valuation"), headers=_auth(token)
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "rows" in data
        assert "grand_total_value" in data

    def test_valuation_method_is_wac(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, "/reports/inventory-valuation"), headers=_auth(token)
        )
        assert resp.status_code == 200
        rows = resp.json()["data"]["rows"]
        for row in rows:
            assert row["valuation_method"] == "WAC"


class TestStockPositionReport:
    def test_returns_200(self, test_client: TestClient, db_session: Session) -> None:
        email, password, company_id, _, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, "/reports/stock-position"), headers=_auth(token)
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "rows" in data
        assert "total_rows" in data

    def test_reorder_flags_populated(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, "/reports/stock-position"), headers=_auth(token)
        )
        assert resp.status_code == 200
        rows = resp.json()["data"]["rows"]
        for row in rows:
            assert "is_below_reorder" in row
            assert "is_out_of_stock" in row


class TestWarehouseUtilisationReport:
    def test_returns_200(self, test_client: TestClient, db_session: Session) -> None:
        email, password, company_id, _, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, "/reports/warehouse-utilisation"), headers=_auth(token)
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "rows" in data


class TestCategoryBrandReport:
    def test_returns_200(self, test_client: TestClient, db_session: Session) -> None:
        email, password, company_id, _, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, "/reports/category-brand"), headers=_auth(token)
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "categories" in data
        assert "brands" in data


class TestDeadStockReport:
    def test_returns_200(self, test_client: TestClient, db_session: Session) -> None:
        email, password, company_id, _, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, "/reports/dead-stock"), headers=_auth(token)
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "rows" in data
        assert "threshold_days" in data
        assert data["threshold_days"] == 90

    def test_custom_threshold(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, "/reports/dead-stock?threshold_days=30"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["threshold_days"] == 30


class TestMovementVelocityReport:
    def test_returns_200(self, test_client: TestClient, db_session: Session) -> None:
        email, password, company_id, _, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, "/reports/movement-velocity"), headers=_auth(token)
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "fast_moving" in data
        assert "slow_moving" in data
        assert "period_days" in data


class TestStockAgingReport:
    def test_returns_200(self, test_client: TestClient, db_session: Session) -> None:
        email, password, company_id, _, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, "/reports/stock-aging"), headers=_auth(token)
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "rows" in data
        assert "as_of" in data


class TestOperationalReport:
    def test_returns_200(self, test_client: TestClient, db_session: Session) -> None:
        email, password, company_id, _, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, "/reports/operational"), headers=_auth(token)
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "adjustments" in data
        assert "transfers" in data


class TestTrendAnalysisReport:
    def test_requires_product_id(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, "/reports/trend-analysis"), headers=_auth(token)
        )
        assert resp.status_code == 400

    def test_returns_200_with_product_id(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, prod_id, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, f"/reports/trend-analysis?product_id={prod_id}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["product_id"] == prod_id
        assert "data_points" in data


# ---------------------------------------------------------------------------
# KPI Dashboard tests (T256)
# ---------------------------------------------------------------------------


class TestKPIDashboard:
    def test_returns_200(self, test_client: TestClient, db_session: Session) -> None:
        email, password, company_id, _, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.get(_url(company_id, "/kpis"), headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "inventory_turnover" in data
        assert "total_inventory_value" in data
        assert "period_days" in data

    def test_all_10_kpis_present(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.get(_url(company_id, "/kpis"), headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()["data"]
        expected = {
            "inventory_turnover",
            "average_inventory_value",
            "inventory_accuracy",
            "dead_stock_percentage",
            "stock_accuracy_percentage",
            "warehouse_efficiency",
            "total_inventory_value",
            "reorder_frequency",
            "stockout_rate",
            "overstock_rate",
        }
        for key in expected:
            assert key in data, f"Missing KPI: {key}"

    def test_custom_period_days(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, "/kpis?period_days=30"), headers=_auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["period_days"] == 30

    def test_requires_auth(self, test_client: TestClient, db_session: Session) -> None:
        _, _, company_id, _, _ = _seed_company(db_session, test_client)
        resp = test_client.get(_url(company_id, "/kpis"))
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Tenant Isolation tests (T257)
# ---------------------------------------------------------------------------


class TestReportTenantIsolation:
    def test_inventory_summary_isolates_companies(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email_a, pass_a, cid_a, prod_a, _ = _seed_company(db_session, test_client)
        email_b, pass_b, cid_b, prod_b, _ = _seed_company(db_session, test_client)

        token_a = _login(test_client, email_a, pass_a)
        resp = test_client.get(
            _url(cid_a, "/reports/inventory-summary"), headers=_auth(token_a)
        )
        assert resp.status_code == 200
        product_ids_a = {r["product_id"] for r in resp.json()["data"]["rows"]}
        assert prod_b not in product_ids_a
        assert prod_a in product_ids_a

    def test_stock_ledger_isolates_companies(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email_a, pass_a, cid_a, prod_a, _ = _seed_company(db_session, test_client)
        _, _, cid_b, prod_b, _ = _seed_company(db_session, test_client)

        token_a = _login(test_client, email_a, pass_a)
        resp = test_client.get(
            _url(cid_a, "/reports/stock-ledger"), headers=_auth(token_a)
        )
        assert resp.status_code == 200
        product_ids_a = {r["product_id"] for r in resp.json()["data"]["rows"]}
        assert prod_b not in product_ids_a

    def test_kpis_isolates_companies(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email_a, pass_a, cid_a, _, _ = _seed_company(db_session, test_client)
        # Company B has no stock
        email_b = f"report-{uuid.uuid4().hex[:8]}@test.com"
        create_test_user(db_session, email=email_b, password="TestPass123!")
        db_session.commit()

        token_b = _login(test_client, email_b, "TestPass123!")
        cid_b = _create_company(test_client, token_b)
        resp_b = test_client.get(_url(cid_b, "/kpis"), headers=_auth(token_b))
        assert resp_b.status_code == 200
        # Company B should have zero inventory value
        assert float(resp_b.json()["data"]["total_inventory_value"]) == 0.0


# ---------------------------------------------------------------------------
# Export endpoint tests (T258)
# ---------------------------------------------------------------------------


class TestExportEndpoints:
    def test_export_inventory_summary_csv(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.post(
            _url(company_id, "/reports/inventory-summary/export"),
            json={"format": "csv"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "download_url" in data
        assert "file_name" in data
        assert data["format"] == "csv"

    def test_export_inventory_summary_xlsx(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.post(
            _url(company_id, "/reports/inventory-summary/export"),
            json={"format": "xlsx"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["format"] == "xlsx"
        assert data["file_name"].endswith(".xlsx")

    def test_export_stock_ledger_csv(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id, _, _ = _seed_company(db_session, test_client)
        token = _login(test_client, email, password)
        resp = test_client.post(
            _url(company_id, "/reports/stock-ledger/export"),
            json={"format": "csv"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["format"] == "csv"

    def test_export_requires_auth(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        _, _, company_id, _, _ = _seed_company(db_session, test_client)
        resp = test_client.post(
            _url(company_id, "/reports/inventory-summary/export"),
            json={"format": "csv"},
        )
        assert resp.status_code == 401
