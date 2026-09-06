"""Integration tests for Phase 10 scanner lookup and label-data endpoints.

Tests cover:
  T265 - Barcode lookup found / not found
  T265 - SKU lookup found / not found
  T265 - Auth enforcement (unauthenticated returns 401/403)
  T265 - Label data endpoint returns correct fields

Spec ref: specs/005-inventory-management/spec.md §46 Integration Readiness
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.inventory.models.product import Product, ProductBarcode
from modules.inventory.models.stock import StockPosition
from modules.inventory.models.uom import UOM
from modules.inventory.models.warehouse import Warehouse
from tests.fixtures.auth_fixtures import create_test_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(test_client: TestClient, email: str, password: str) -> str:
    resp = test_client.post(
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
    email = f"lookup-{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"
    create_test_user(db, email=email, password=password)
    token = _login(client, email, password)
    company_id = _create_company(client, token)
    return email, password, company_id


def _make_uom(db: Session, company_id: uuid.UUID) -> UOM:
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
    return uom


def _make_product(db: Session, company_id: uuid.UUID, uom_id: uuid.UUID) -> Product:
    code = f"P-{uuid.uuid4().hex[:6].upper()}"
    product = Product(
        id=uuid.uuid4(),
        company_id=company_id,
        product_code=code,
        name=f"Product {code}",
        product_type="STANDARD",
        status="ACTIVE",
        base_uom_id=str(uom_id),
    )
    db.add(product)
    db.flush()
    return product


def _make_barcode(
    db: Session,
    company_id: uuid.UUID,
    product: Product,
    value: str = "",
    is_primary: bool = True,
) -> ProductBarcode:
    barcode_value = value or f"EAN{uuid.uuid4().int % 10**12:012d}"
    bc = ProductBarcode(
        id=uuid.uuid4(),
        company_id=company_id,
        product_id=str(product.id),
        barcode_value=barcode_value,
        barcode_type="EAN13",
        is_primary=is_primary,
    )
    db.add(bc)
    db.flush()
    return bc


def _make_stock_position(
    db: Session,
    company_id: uuid.UUID,
    product: Product,
    warehouse: Warehouse,
    qty: Decimal = Decimal("10"),
) -> StockPosition:
    pos = StockPosition(
        id=uuid.uuid4(),
        company_id=company_id,
        product_id=str(product.id),
        warehouse_id=str(warehouse.id),
        qty_on_hand=qty,
        qty_reserved=Decimal("0"),
        qty_damaged=Decimal("0"),
        unit_cost=Decimal("25.00"),
    )
    db.add(pos)
    db.flush()
    return pos


def _make_warehouse(db: Session, company_id: uuid.UUID) -> Warehouse:
    wh = Warehouse(
        id=uuid.uuid4(),
        company_id=company_id,
        code=f"WH-{uuid.uuid4().hex[:4].upper()}",
        name="Test Warehouse",
        warehouse_type="MAIN",
        status="ACTIVE",
    )
    db.add(wh)
    db.flush()
    return wh


# ---------------------------------------------------------------------------
# Barcode lookup tests
# ---------------------------------------------------------------------------


class TestBarcodeLookup:
    def test_barcode_found(self, test_client: TestClient, db_session: Session) -> None:
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom.id)
        wh = _make_warehouse(db_session, company_id)
        barcode_value = f"EAN{uuid.uuid4().int % 10**12:012d}"
        _make_barcode(db_session, company_id, product, value=barcode_value)
        _make_stock_position(db_session, company_id, product, wh)
        db_session.flush()

        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, f"/lookup/barcode/{barcode_value}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["product_code"] == product.product_code
        assert data["barcode_value"] == barcode_value
        assert len(data["stock_positions"]) == 1
        assert Decimal(data["stock_positions"][0]["qty_on_hand"]) == Decimal("10")

    def test_barcode_not_found_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id = _setup(db_session, test_client)
        db_session.flush()

        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, "/lookup/barcode/NONEXISTENT-BC-9999"),
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_barcode_lookup_unauthenticated_returns_401_or_403(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        resp = test_client.get(_url(company_id, "/lookup/barcode/ANY123"))
        assert resp.status_code in (401, 403)

    def test_barcode_tenant_isolation(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Barcode from company A must not be visible under company B."""
        email_a, password_a, company_a = _setup(db_session, test_client)
        _, _, company_b = _setup(db_session, test_client)

        uom = _make_uom(db_session, company_a)
        product = _make_product(db_session, company_a, uom.id)
        barcode_value = f"TEN{uuid.uuid4().int % 10**9:09d}"
        _make_barcode(db_session, company_a, product, value=barcode_value)
        db_session.flush()

        token_a = _login(test_client, email_a, password_a)
        # User A is not a member of company B — denied either at the
        # membership gate (403) or, if it got past that, at the repository's
        # company_id scoping (404). Both are correct "access denied" outcomes
        # (see tests/security/inventory/test_security.py).
        resp = test_client.get(
            _url(company_b, f"/lookup/barcode/{barcode_value}"),
            headers=_auth(token_a),
        )
        assert resp.status_code in (403, 404)


# ---------------------------------------------------------------------------
# SKU lookup tests
# ---------------------------------------------------------------------------


class TestSKULookup:
    def test_sku_found(self, test_client: TestClient, db_session: Session) -> None:
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom.id)
        db_session.flush()

        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, f"/lookup/sku/{product.product_code}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["product_code"] == product.product_code
        assert data["product_name"] == product.name

    def test_sku_case_insensitive(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom.id)
        db_session.flush()

        token = _login(test_client, email, password)
        sku_lower = product.product_code.lower()
        resp = test_client.get(
            _url(company_id, f"/lookup/sku/{sku_lower}"),
            headers=_auth(token),
        )
        assert resp.status_code == 200

    def test_sku_not_found_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id = _setup(db_session, test_client)
        db_session.flush()

        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, "/lookup/sku/NONEXISTENT-SKU-9999"),
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_sku_lookup_unauthenticated_returns_401_or_403(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        resp = test_client.get(_url(company_id, "/lookup/sku/ANY"))
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Label data tests
# ---------------------------------------------------------------------------


class TestLabelData:
    def test_label_data_returned(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom.id)
        barcode_value = f"EAN{uuid.uuid4().int % 10**12:012d}"
        _make_barcode(
            db_session, company_id, product, value=barcode_value, is_primary=True
        )
        db_session.flush()

        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, f"/products/{product.id}/label-data"),
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["product_id"] == str(product.id)
        assert data["product_code"] == product.product_code
        assert data["product_name"] == product.name
        assert data["barcode_value"] == barcode_value
        assert data["barcode_type"] == "EAN13"
        assert data["uom_code"] == uom.code
        assert data["uom_name"] == uom.name

    def test_label_data_no_barcode(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Products without barcodes return label data with barcode_value=None."""
        email, password, company_id = _setup(db_session, test_client)
        uom = _make_uom(db_session, company_id)
        product = _make_product(db_session, company_id, uom.id)
        db_session.flush()

        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, f"/products/{product.id}/label-data"),
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["barcode_value"] is None

    def test_label_data_product_not_found(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email, password, company_id = _setup(db_session, test_client)
        db_session.flush()

        token = _login(test_client, email, password)
        resp = test_client.get(
            _url(company_id, f"/products/{uuid.uuid4()}/label-data"),
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_label_data_unauthenticated(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        resp = test_client.get(_url(company_id, f"/products/{uuid.uuid4()}/label-data"))
        assert resp.status_code in (401, 403)
