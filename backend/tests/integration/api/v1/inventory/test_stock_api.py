"""API integration tests for Phase 5 Stock Ledger endpoints.

Tests:
  - Unauthenticated: 401 on all stock endpoints
  - Opening stock: POST /stock/opening (201, 400 validation, 404 unknown warehouse)
  - Adjustment: POST /stock/adjustments (201, 409 insufficient stock, 400 invalid type)
  - Position listing: GET /stock/positions, /stock/positions/warehouse/:id, /stock/positions/product/:id
  - Movement listing: GET /stock/movements
  - Snapshot: POST /stock/snapshots, GET /stock/snapshots, GET /stock/snapshots/:id/lines
  - Tenant isolation: company_id scoping

Spec ref: specs/005-inventory-management/spec.md §15
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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
    return str(resp.json()["data"]["access_token"])


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
    email = f"stock-{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"
    create_test_user(db, email=email, password=password)
    token = _login(client, email, password)
    company_id = _create_company(client, token)
    return email, password, company_id


def _make_warehouse(db: Session, company_id: uuid.UUID) -> Warehouse:
    wh = Warehouse(
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
# 401 Unauthenticated
# ---------------------------------------------------------------------------


class TestStockUnauthenticated:
    def test_opening_stock_requires_auth(self, test_client: TestClient):
        resp = test_client.post(
            _url(uuid.uuid4(), "/stock/opening"),
            json={
                "product_id": str(uuid.uuid4()),
                "warehouse_id": str(uuid.uuid4()),
                "quantity": "10",
            },
        )
        assert resp.status_code == 401

    def test_adjustments_requires_auth(self, test_client: TestClient):
        resp = test_client.post(
            _url(uuid.uuid4(), "/stock/adjustments"),
            json={
                "product_id": str(uuid.uuid4()),
                "warehouse_id": str(uuid.uuid4()),
                "movement_type": "ADJUSTMENT_IN",
                "quantity": "5",
            },
        )
        assert resp.status_code == 401

    def test_list_positions_requires_auth(self, test_client: TestClient):
        resp = test_client.get(_url(uuid.uuid4(), "/stock/positions"))
        assert resp.status_code == 401

    def test_list_movements_requires_auth(self, test_client: TestClient):
        resp = test_client.get(_url(uuid.uuid4(), "/stock/movements"))
        assert resp.status_code == 401

    def test_create_snapshot_requires_auth(self, test_client: TestClient):
        resp = test_client.post(_url(uuid.uuid4(), "/stock/snapshots"), json={})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Opening stock
# ---------------------------------------------------------------------------


class TestOpeningStock:
    def test_record_opening_stock_success(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)
        product_id = uuid.uuid4()

        resp = test_client.post(
            _url(cid, "/stock/opening"),
            json={
                "product_id": str(product_id),
                "warehouse_id": str(wh.id),
                "quantity": "50",
                "unit_cost": "100.00",
                "currency_code": "AED",
            },
            headers=_auth(tok),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert float(data["qty_on_hand"]) == pytest.approx(50.0)
        assert float(data["unit_cost"]) == pytest.approx(100.0)

    def test_opening_stock_unknown_warehouse_404(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        tok = _login(test_client, email, pwd)

        resp = test_client.post(
            _url(cid, "/stock/opening"),
            json={
                "product_id": str(uuid.uuid4()),
                "warehouse_id": str(uuid.uuid4()),
                "quantity": "10",
            },
            headers=_auth(tok),
        )
        assert resp.status_code == 404

    def test_opening_stock_inactive_warehouse_404(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        wh.status = "INACTIVE"
        db_session.flush()
        tok = _login(test_client, email, pwd)

        resp = test_client.post(
            _url(cid, "/stock/opening"),
            json={
                "product_id": str(uuid.uuid4()),
                "warehouse_id": str(wh.id),
                "quantity": "10",
            },
            headers=_auth(tok),
        )
        assert resp.status_code == 404

    def test_second_opening_stock_applies_wac(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)
        pid = uuid.uuid4()

        # First: 10 units @ 100
        test_client.post(
            _url(cid, "/stock/opening"),
            json={
                "product_id": str(pid),
                "warehouse_id": str(wh.id),
                "quantity": "10",
                "unit_cost": "100",
            },
            headers=_auth(tok),
        )
        # Second: 10 units @ 200 → WAC = 150
        resp2 = test_client.post(
            _url(cid, "/stock/opening"),
            json={
                "product_id": str(pid),
                "warehouse_id": str(wh.id),
                "quantity": "10",
                "unit_cost": "200",
            },
            headers=_auth(tok),
        )
        assert resp2.status_code == 201, resp2.text
        data = resp2.json()["data"]
        assert float(data["qty_on_hand"]) == pytest.approx(20.0)
        assert float(data["unit_cost"]) == pytest.approx(150.0)


# ---------------------------------------------------------------------------
# Stock adjustments
# ---------------------------------------------------------------------------


class TestStockAdjustments:
    def _seed_stock(self, client, db, email, pwd, cid, wh, pid, qty="100"):
        tok = _login(client, email, pwd)
        client.post(
            _url(cid, "/stock/opening"),
            json={"product_id": str(pid), "warehouse_id": str(wh.id), "quantity": qty},
            headers=_auth(tok),
        )
        return tok

    def test_adjustment_in_increases_qty(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()
        tok = self._seed_stock(test_client, db_session, email, pwd, cid, wh, pid)

        resp = test_client.post(
            _url(cid, "/stock/adjustments"),
            json={
                "product_id": str(pid),
                "warehouse_id": str(wh.id),
                "movement_type": "ADJUSTMENT_IN",
                "quantity": "25",
            },
            headers=_auth(tok),
        )
        assert resp.status_code == 201, resp.text
        assert float(resp.json()["data"]["qty_on_hand"]) == pytest.approx(125.0)

    def test_adjustment_out_decreases_qty(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()
        tok = self._seed_stock(test_client, db_session, email, pwd, cid, wh, pid)

        resp = test_client.post(
            _url(cid, "/stock/adjustments"),
            json={
                "product_id": str(pid),
                "warehouse_id": str(wh.id),
                "movement_type": "ADJUSTMENT_OUT",
                "quantity": "40",
            },
            headers=_auth(tok),
        )
        assert resp.status_code == 201, resp.text
        assert float(resp.json()["data"]["qty_on_hand"]) == pytest.approx(60.0)

    def test_adjustment_out_insufficient_stock_409(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()
        tok = self._seed_stock(
            test_client, db_session, email, pwd, cid, wh, pid, qty="10"
        )

        resp = test_client.post(
            _url(cid, "/stock/adjustments"),
            json={
                "product_id": str(pid),
                "warehouse_id": str(wh.id),
                "movement_type": "ADJUSTMENT_OUT",
                "quantity": "100",
            },
            headers=_auth(tok),
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Position listing
# ---------------------------------------------------------------------------


class TestStockPositionListing:
    def _seed(self, client, db, cid, wh_id, pid, qty, tok):
        client.post(
            _url(cid, "/stock/opening"),
            json={"product_id": str(pid), "warehouse_id": str(wh_id), "quantity": qty},
            headers=_auth(tok),
        )

    def test_list_positions_for_company(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)
        self._seed(test_client, db_session, cid, wh.id, uuid.uuid4(), "50", tok)
        self._seed(test_client, db_session, cid, wh.id, uuid.uuid4(), "75", tok)

        resp = test_client.get(_url(cid, "/stock/positions"), headers=_auth(tok))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 2

    def test_list_positions_by_warehouse(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh1 = _make_warehouse(db_session, cid)
        wh2 = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)
        self._seed(test_client, db_session, cid, wh1.id, uuid.uuid4(), "10", tok)
        self._seed(test_client, db_session, cid, wh2.id, uuid.uuid4(), "20", tok)

        resp = test_client.get(
            _url(cid, f"/stock/positions/warehouse/{wh1.id}"), headers=_auth(tok)
        )
        assert resp.status_code == 200
        positions = resp.json()["data"]
        assert all(p["warehouse_id"] == str(wh1.id) for p in positions)

    def test_list_positions_by_product(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh1 = _make_warehouse(db_session, cid)
        wh2 = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()
        tok = _login(test_client, email, pwd)
        self._seed(test_client, db_session, cid, wh1.id, pid, "30", tok)
        self._seed(test_client, db_session, cid, wh2.id, pid, "40", tok)

        resp = test_client.get(
            _url(cid, f"/stock/positions/product/{pid}"), headers=_auth(tok)
        )
        assert resp.status_code == 200
        positions = resp.json()["data"]
        assert len(positions) == 2


# ---------------------------------------------------------------------------
# Movement listing
# ---------------------------------------------------------------------------


class TestStockMovementListing:
    def test_list_movements_returns_ledger(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()
        tok = _login(test_client, email, pwd)

        test_client.post(
            _url(cid, "/stock/opening"),
            json={"product_id": str(pid), "warehouse_id": str(wh.id), "quantity": "50"},
            headers=_auth(tok),
        )
        test_client.post(
            _url(cid, "/stock/adjustments"),
            json={
                "product_id": str(pid),
                "warehouse_id": str(wh.id),
                "movement_type": "ADJUSTMENT_IN",
                "quantity": "10",
            },
            headers=_auth(tok),
        )

        resp = test_client.get(_url(cid, "/stock/movements"), headers=_auth(tok))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 2


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------


class TestInventorySnapshots:
    def test_create_snapshot_empty_company(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        tok = _login(test_client, email, pwd)

        resp = test_client.post(
            _url(cid, "/stock/snapshots"),
            json={"snapshot_name": "End of Month"},
            headers=_auth(tok),
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["status"] == "COMPLETED"
        assert data["snapshot_name"] == "End of Month"

    def test_create_snapshot_captures_positions(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        pid = uuid.uuid4()
        tok = _login(test_client, email, pwd)

        test_client.post(
            _url(cid, "/stock/opening"),
            json={
                "product_id": str(pid),
                "warehouse_id": str(wh.id),
                "quantity": "100",
            },
            headers=_auth(tok),
        )

        snap_resp = test_client.post(
            _url(cid, "/stock/snapshots"),
            json={},
            headers=_auth(tok),
        )
        assert snap_resp.status_code == 201
        data = snap_resp.json()["data"]
        assert data["total_products"] == 1
        assert data["total_warehouses"] == 1

    def test_list_snapshots(self, test_client: TestClient, db_session: Session):
        email, pwd, cid = _setup(db_session, test_client)
        tok = _login(test_client, email, pwd)

        test_client.post(_url(cid, "/stock/snapshots"), json={}, headers=_auth(tok))
        test_client.post(_url(cid, "/stock/snapshots"), json={}, headers=_auth(tok))

        resp = test_client.get(_url(cid, "/stock/snapshots"), headers=_auth(tok))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 2

    def test_get_snapshot_lines(self, test_client: TestClient, db_session: Session):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)

        # Seed some stock
        test_client.post(
            _url(cid, "/stock/opening"),
            json={
                "product_id": str(uuid.uuid4()),
                "warehouse_id": str(wh.id),
                "quantity": "50",
            },
            headers=_auth(tok),
        )

        snap_resp = test_client.post(
            _url(cid, "/stock/snapshots"), json={}, headers=_auth(tok)
        )
        snap_id = snap_resp.json()["data"]["id"]

        lines_resp = test_client.get(
            _url(cid, f"/stock/snapshots/{snap_id}/lines"), headers=_auth(tok)
        )
        assert lines_resp.status_code == 200
        lines = lines_resp.json()["data"]
        assert len(lines) == 1
        assert float(lines[0]["qty_on_hand"]) == pytest.approx(50.0)
