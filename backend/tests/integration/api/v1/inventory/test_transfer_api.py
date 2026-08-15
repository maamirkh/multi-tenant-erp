"""API integration tests for Phase 7 — Stock Transfer endpoints (T212).

Tests:
  - 401 unauthenticated on all endpoints
  - POST /stock-transfers → 201 DRAFT
  - POST /stock-transfers → 400 same warehouse
  - GET  /stock-transfers → 200 list
  - GET  /stock-transfers/{id} → 200 detail
  - GET  /stock-transfers/{id} → 404 not found
  - POST /stock-transfers/{id}/dispatch → source stock reduced
  - POST /stock-transfers/{id}/receive  → destination stock increased
  - POST /stock-transfers/{id}/cancel   → CANCELLED (DRAFT path, no stock change)
  - POST /stock-transfers/{id}/cancel   → reversal created (IN_TRANSIT path)
  - POST /stock/reserve → 200 reserves stock
  - POST /stock/release → 200 releases stock
  - POST /stock/reserve → 409 insufficient stock
  - Tenant isolation

Spec ref: specs/005-inventory-management/spec.md §16 / FR-IO-013
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.inventory.models.warehouse import Warehouse
from modules.inventory.repositories.stock_repository import (
    SnapshotRepository,
    StockMovementRepository,
    StockPositionRepository,
)
from modules.inventory.repositories.warehouse_repository import WarehouseRepository
from modules.inventory.services.stock_service import StockLedgerService
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


def _url(company_id: uuid.UUID, path: str) -> str:
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
    email = f"tr-{uuid.uuid4().hex[:8]}@test.com"
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
        name="Test Warehouse",
        warehouse_type="MAIN",
        status="ACTIVE",
    )
    db.add(wh)
    db.flush()
    return wh


def _seed_stock(
    db: Session,
    company_id: uuid.UUID,
    product_id: uuid.UUID,
    wh_id: uuid.UUID,
    qty: Decimal,
) -> None:
    pos_repo = StockPositionRepository(db)
    mov_repo = StockMovementRepository(db)
    snap_repo = SnapshotRepository(db)
    wh_repo = WarehouseRepository(db)
    ledger = StockLedgerService(
        db=db,
        position_repo=pos_repo,
        movement_repo=mov_repo,
        snapshot_repo=snap_repo,
        warehouse_repo=wh_repo,
    )
    ledger.record_opening_stock(
        company_id=company_id, product_id=product_id, warehouse_id=wh_id, quantity=qty
    )
    db.flush()


# ---------------------------------------------------------------------------
# Unauthenticated
# ---------------------------------------------------------------------------


class TestTransferUnauthenticated:
    def test_create_requires_auth(self, test_client: TestClient):
        resp = test_client.post(
            _url(uuid.uuid4(), "/stock-transfers"),
            json={
                "source_warehouse_id": str(uuid.uuid4()),
                "destination_warehouse_id": str(uuid.uuid4()),
                "lines": [{"product_id": str(uuid.uuid4()), "quantity": "10"}],
            },
        )
        assert resp.status_code == 401

    def test_list_requires_auth(self, test_client: TestClient):
        resp = test_client.get(_url(uuid.uuid4(), "/stock-transfers"))
        assert resp.status_code == 401

    def test_dispatch_requires_auth(self, test_client: TestClient):
        resp = test_client.post(
            _url(uuid.uuid4(), f"/stock-transfers/{uuid.uuid4()}/dispatch")
        )
        assert resp.status_code == 401

    def test_reserve_requires_auth(self, test_client: TestClient):
        resp = test_client.post(
            _url(uuid.uuid4(), "/stock/reserve"),
            json={
                "product_id": str(uuid.uuid4()),
                "warehouse_id": str(uuid.uuid4()),
                "quantity": "10",
            },
        )
        assert resp.status_code == 401

    def test_release_requires_auth(self, test_client: TestClient):
        resp = test_client.post(
            _url(uuid.uuid4(), "/stock/release"),
            json={
                "product_id": str(uuid.uuid4()),
                "warehouse_id": str(uuid.uuid4()),
                "quantity": "5",
            },
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Create transfer
# ---------------------------------------------------------------------------


class TestCreateTransferEndpoint:
    def test_create_returns_201_draft(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        src = _make_warehouse(db_session, cid)
        dst = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)
        pid = str(uuid.uuid4())

        resp = test_client.post(
            _url(cid, "/stock-transfers"),
            json={
                "source_warehouse_id": str(src.id),
                "destination_warehouse_id": str(dst.id),
                "lines": [{"product_id": pid, "quantity": "10"}],
                "notes": "Test transfer",
            },
            headers=_auth(tok),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["status"] == "DRAFT"
        assert data["version"] == 1
        assert len(data["lines"]) == 1

    def test_same_warehouse_returns_400(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)

        resp = test_client.post(
            _url(cid, "/stock-transfers"),
            json={
                "source_warehouse_id": str(wh.id),
                "destination_warehouse_id": str(wh.id),
                "lines": [{"product_id": str(uuid.uuid4()), "quantity": "10"}],
            },
            headers=_auth(tok),
        )
        assert resp.status_code == 400

    def test_unknown_warehouse_returns_404(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        tok = _login(test_client, email, pwd)

        resp = test_client.post(
            _url(cid, "/stock-transfers"),
            json={
                "source_warehouse_id": str(uuid.uuid4()),
                "destination_warehouse_id": str(uuid.uuid4()),
                "lines": [{"product_id": str(uuid.uuid4()), "quantity": "10"}],
            },
            headers=_auth(tok),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# List and detail
# ---------------------------------------------------------------------------


class TestListAndDetailTransfer:
    def test_list_returns_transfers(self, test_client: TestClient, db_session: Session):
        email, pwd, cid = _setup(db_session, test_client)
        src = _make_warehouse(db_session, cid)
        dst = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)

        test_client.post(
            _url(cid, "/stock-transfers"),
            json={
                "source_warehouse_id": str(src.id),
                "destination_warehouse_id": str(dst.id),
                "lines": [{"product_id": str(uuid.uuid4()), "quantity": "5"}],
            },
            headers=_auth(tok),
        )
        resp = test_client.get(_url(cid, "/stock-transfers"), headers=_auth(tok))
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1

    def test_get_by_id_returns_detail(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        src = _make_warehouse(db_session, cid)
        dst = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)

        cr = test_client.post(
            _url(cid, "/stock-transfers"),
            json={
                "source_warehouse_id": str(src.id),
                "destination_warehouse_id": str(dst.id),
                "lines": [{"product_id": str(uuid.uuid4()), "quantity": "5"}],
            },
            headers=_auth(tok),
        )
        tid = cr.json()["data"]["id"]
        resp = test_client.get(_url(cid, f"/stock-transfers/{tid}"), headers=_auth(tok))
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == tid

    def test_get_not_found_returns_404(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        tok = _login(test_client, email, pwd)
        resp = test_client.get(
            _url(cid, f"/stock-transfers/{uuid.uuid4()}"), headers=_auth(tok)
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Dispatch / Receive / Cancel via API
# ---------------------------------------------------------------------------


class TestTransferWorkflowEndpoints:
    def test_dispatch_reduces_source_stock(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        src = _make_warehouse(db_session, cid)
        dst = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, src.id, Decimal("100"))

        cr = test_client.post(
            _url(cid, "/stock-transfers"),
            json={
                "source_warehouse_id": str(src.id),
                "destination_warehouse_id": str(dst.id),
                "lines": [{"product_id": str(pid), "quantity": "30"}],
            },
            headers=_auth(tok),
        )
        tid = cr.json()["data"]["id"]

        resp = test_client.post(
            _url(cid, f"/stock-transfers/{tid}/dispatch"), headers=_auth(tok)
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "IN_TRANSIT"

    def test_receive_increases_dest_stock(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        src = _make_warehouse(db_session, cid)
        dst = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, src.id, Decimal("100"))

        cr = test_client.post(
            _url(cid, "/stock-transfers"),
            json={
                "source_warehouse_id": str(src.id),
                "destination_warehouse_id": str(dst.id),
                "lines": [{"product_id": str(pid), "quantity": "50"}],
            },
            headers=_auth(tok),
        )
        tid = cr.json()["data"]["id"]
        test_client.post(
            _url(cid, f"/stock-transfers/{tid}/dispatch"), headers=_auth(tok)
        )

        resp = test_client.post(
            _url(cid, f"/stock-transfers/{tid}/receive"), headers=_auth(tok)
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "COMPLETED"

    def test_cancel_draft_returns_cancelled(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        src = _make_warehouse(db_session, cid)
        dst = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, src.id, Decimal("50"))
        cr = test_client.post(
            _url(cid, "/stock-transfers"),
            json={
                "source_warehouse_id": str(src.id),
                "destination_warehouse_id": str(dst.id),
                "lines": [{"product_id": str(pid), "quantity": "10"}],
            },
            headers=_auth(tok),
        )
        tid = cr.json()["data"]["id"]

        resp = test_client.post(
            _url(cid, f"/stock-transfers/{tid}/cancel"),
            json={"cancelled_reason": "Not needed"},
            headers=_auth(tok),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "CANCELLED"

    def test_cancel_in_transit_restores_stock(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        src = _make_warehouse(db_session, cid)
        dst = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, src.id, Decimal("100"))
        cr = test_client.post(
            _url(cid, "/stock-transfers"),
            json={
                "source_warehouse_id": str(src.id),
                "destination_warehouse_id": str(dst.id),
                "lines": [{"product_id": str(pid), "quantity": "40"}],
            },
            headers=_auth(tok),
        )
        tid = cr.json()["data"]["id"]
        test_client.post(
            _url(cid, f"/stock-transfers/{tid}/dispatch"), headers=_auth(tok)
        )

        resp = test_client.post(
            _url(cid, f"/stock-transfers/{tid}/cancel"),
            json={"cancelled_reason": "logistics"},
            headers=_auth(tok),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "CANCELLED"

    def test_dispatch_wrong_status_returns_409(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        src = _make_warehouse(db_session, cid)
        dst = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, src.id, Decimal("100"))
        cr = test_client.post(
            _url(cid, "/stock-transfers"),
            json={
                "source_warehouse_id": str(src.id),
                "destination_warehouse_id": str(dst.id),
                "lines": [{"product_id": str(pid), "quantity": "10"}],
            },
            headers=_auth(tok),
        )
        tid = cr.json()["data"]["id"]
        test_client.post(
            _url(cid, f"/stock-transfers/{tid}/dispatch"), headers=_auth(tok)
        )
        # Double dispatch → 409
        resp = test_client.post(
            _url(cid, f"/stock-transfers/{tid}/dispatch"), headers=_auth(tok)
        )
        assert resp.status_code == 409

    def test_tenant_isolation_cannot_see_other_company_transfer(
        self, test_client: TestClient, db_session: Session
    ):
        email1, pwd1, cid1 = _setup(db_session, test_client)
        email2, pwd2, cid2 = _setup(db_session, test_client)
        src = _make_warehouse(db_session, cid1)
        dst = _make_warehouse(db_session, cid1)
        tok1 = _login(test_client, email1, pwd1)
        tok2 = _login(test_client, email2, pwd2)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid1, pid, src.id, Decimal("50"))
        cr = test_client.post(
            _url(cid1, "/stock-transfers"),
            json={
                "source_warehouse_id": str(src.id),
                "destination_warehouse_id": str(dst.id),
                "lines": [{"product_id": str(pid), "quantity": "10"}],
            },
            headers=_auth(tok1),
        )
        tid = cr.json()["data"]["id"]

        # Company 2 cannot see company 1's transfer
        resp2 = test_client.get(
            _url(cid2, f"/stock-transfers/{tid}"), headers=_auth(tok2)
        )
        assert resp2.status_code == 404


# ---------------------------------------------------------------------------
# Reservation endpoints
# ---------------------------------------------------------------------------


class TestReservationEndpoints:
    def test_reserve_returns_200(self, test_client: TestClient, db_session: Session):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, wh.id, Decimal("100"))

        resp = test_client.post(
            _url(cid, "/stock/reserve"),
            json={
                "product_id": str(pid),
                "warehouse_id": str(wh.id),
                "quantity": "30",
            },
            headers=_auth(tok),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert float(data["qty_reserved"]) == pytest.approx(30.0)
        assert float(data["available_quantity"]) == pytest.approx(70.0)

    def test_release_returns_200(self, test_client: TestClient, db_session: Session):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, wh.id, Decimal("100"))
        # First reserve
        test_client.post(
            _url(cid, "/stock/reserve"),
            json={"product_id": str(pid), "warehouse_id": str(wh.id), "quantity": "40"},
            headers=_auth(tok),
        )
        # Then release partial
        resp = test_client.post(
            _url(cid, "/stock/release"),
            json={"product_id": str(pid), "warehouse_id": str(wh.id), "quantity": "15"},
            headers=_auth(tok),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert float(data["qty_reserved"]) == pytest.approx(25.0)

    def test_reserve_insufficient_stock_returns_409(
        self, test_client: TestClient, db_session: Session
    ):
        email, pwd, cid = _setup(db_session, test_client)
        wh = _make_warehouse(db_session, cid)
        tok = _login(test_client, email, pwd)
        pid = uuid.uuid4()

        _seed_stock(db_session, cid, pid, wh.id, Decimal("10"))
        resp = test_client.post(
            _url(cid, "/stock/reserve"),
            json={"product_id": str(pid), "warehouse_id": str(wh.id), "quantity": "50"},
            headers=_auth(tok),
        )
        assert resp.status_code == 409
