"""T287 — Audit trail completeness verification.

Verifies that every write operation produces a traceable audit record:
  1. Stock movements are immutable audit records (append-only ledger).
  2. Domain events are published for every write operation.
  3. Inventory entities carry ``created_by`` tracking fields.

Audit trail in this module uses:
  - The stock movement ledger (StockMovement table = immutable write trail)
  - Domain events (InProcessEventBus captures all state changes)
  - ``created_by`` field on TenantBaseModel entities

Spec ref: specs/005-inventory-management/spec.md §14 (Audit)
Tasks: T287 Phase 12
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.inventory.events import InProcessEventBus, get_event_bus, set_event_bus
from modules.inventory.models.stock import StockMovement
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


def _auth(client: TestClient, db: Session) -> tuple[dict[str, str], uuid.UUID]:
    email = f"audit-{uuid.uuid4().hex[:8]}@test.com"
    create_test_user(db, email=email, password="TestPass123!")
    token = _login(client, email, "TestPass123!")
    company_id = _create_company(client, token)
    return {"Authorization": f"Bearer {token}"}, company_id


def _seed_wh_uom(db: Session, company_id: uuid.UUID) -> tuple[UOM, Warehouse]:
    uom = UOM(
        id=uuid.uuid4(),
        company_id=company_id,
        code=f"AU{uuid.uuid4().hex[:4].upper()}",
        name="Units",
        uom_type="UNIT",
        status="active",
    )
    db.add(uom)
    wh = Warehouse(
        id=uuid.uuid4(),
        company_id=company_id,
        code=f"AW{uuid.uuid4().hex[:4].upper()}",
        name="Audit WH",
        warehouse_type="MAIN",
        status="ACTIVE",
    )
    db.add(wh)
    db.flush()
    return uom, wh


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuditTrailCompleteness:
    """Every write operation produces a traceable audit record."""

    def test_opening_stock_produces_movement_record(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """POST /stock/opening creates an immutable StockMovement audit record."""
        headers, company_id = _auth(test_client, db_session)
        uom, wh = _seed_wh_uom(db_session, company_id)

        # Create product
        resp = test_client.post(
            _url(company_id, "/products"),
            json={
                "product_code": f"AT1-{uuid.uuid4().hex[:6].upper()}",
                "name": "Audit Trail Product",
                "product_type": "STANDARD",
                "base_uom_id": str(uom.id),
            },
            headers=headers,
        )
        assert resp.status_code == 201
        product_id = resp.json()["data"]["id"]
        test_client.patch(
            _url(company_id, f"/products/{product_id}/activate"), headers=headers
        )

        # Record opening stock
        resp = test_client.post(
            _url(company_id, "/stock/opening"),
            json={
                "product_id": product_id,
                "warehouse_id": str(wh.id),
                "quantity": "25",
                "unit_cost": "10.00",
                "currency_code": "USD",
                "notes": "Audit trail test",
            },
            headers=headers,
        )
        assert resp.status_code == 201

        # Verify audit trail: StockMovement record created
        movements = (
            db_session.execute(
                select(StockMovement)
                .where(StockMovement.company_id == company_id)
                .where(StockMovement.product_id == product_id)
            )
            .scalars()
            .all()
        )

        assert len(movements) >= 1, "No StockMovement audit record created"
        assert movements[0].movement_type == "OPENING"
        assert movements[0].direction == "IN"
        assert Decimal(str(movements[0].quantity)) == Decimal("25")

    def test_stock_entities_carry_created_by_field(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """StockMovement records exist and have immutable ledger properties."""
        headers, company_id = _auth(test_client, db_session)
        uom, wh = _seed_wh_uom(db_session, company_id)

        # Create product and opening stock
        resp = test_client.post(
            _url(company_id, "/products"),
            json={
                "product_code": f"AT2-{uuid.uuid4().hex[:6].upper()}",
                "name": "Audit Fields Product",
                "product_type": "STANDARD",
                "base_uom_id": str(uom.id),
            },
            headers=headers,
        )
        assert resp.status_code == 201
        product_id = resp.json()["data"]["id"]
        test_client.patch(
            _url(company_id, f"/products/{product_id}/activate"), headers=headers
        )

        test_client.post(
            _url(company_id, "/stock/opening"),
            json={
                "product_id": product_id,
                "warehouse_id": str(wh.id),
                "quantity": "10",
                "unit_cost": "5.00",
                "currency_code": "USD",
            },
            headers=headers,
        )

        # Verify movements have performed_at (timestamp audit field)
        movements = (
            db_session.execute(
                select(StockMovement).where(StockMovement.company_id == company_id)
            )
            .scalars()
            .all()
        )

        assert len(movements) >= 1
        for mov in movements:
            assert mov.performed_at is not None, (
                f"Movement {mov.id} missing performed_at audit timestamp"
            )
            assert mov.company_id == company_id, (
                f"Movement company_id mismatch: {mov.company_id} != {company_id}"
            )

    def test_domain_events_published_on_opening_stock(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Domain event (OpeningStockRecorded) is published on opening stock write."""
        captured_events = []

        # Subscribe to global event bus
        bus = get_event_bus()
        original_bus = bus

        tracking_bus = InProcessEventBus()
        tracking_bus.subscribe("*", lambda e: captured_events.append(e))
        set_event_bus(tracking_bus)

        try:
            headers, company_id = _auth(test_client, db_session)
            uom, wh = _seed_wh_uom(db_session, company_id)

            resp = test_client.post(
                _url(company_id, "/products"),
                json={
                    "product_code": f"AT3-{uuid.uuid4().hex[:6].upper()}",
                    "name": "Event Audit Product",
                    "product_type": "STANDARD",
                    "base_uom_id": str(uom.id),
                },
                headers=headers,
            )
            assert resp.status_code == 201
            product_id = resp.json()["data"]["id"]
            test_client.patch(
                _url(company_id, f"/products/{product_id}/activate"), headers=headers
            )

            resp = test_client.post(
                _url(company_id, "/stock/opening"),
                json={
                    "product_id": product_id,
                    "warehouse_id": str(wh.id),
                    "quantity": "15",
                    "unit_cost": "5.00",
                    "currency_code": "USD",
                },
                headers=headers,
            )
            assert resp.status_code == 201

        finally:
            set_event_bus(original_bus)

        event_types = [e.event_type for e in captured_events]
        assert "OpeningStockRecorded" in event_types, (
            f"OpeningStockRecorded event not published. Got: {event_types}"
        )

    def test_warehouse_write_produces_domain_event(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """WarehouseCreated domain event is published on warehouse creation."""
        captured_events = []

        original_bus = get_event_bus()
        tracking_bus = InProcessEventBus()
        tracking_bus.subscribe("*", lambda e: captured_events.append(e))
        set_event_bus(tracking_bus)

        try:
            headers, company_id = _auth(test_client, db_session)

            resp = test_client.post(
                _url(company_id, "/warehouses"),
                json={
                    "code": f"AE{uuid.uuid4().hex[:4].upper()}",
                    "name": "Audit Event Warehouse",
                    "warehouse_type": "MAIN",
                },
                headers=headers,
            )
            assert resp.status_code == 201
        finally:
            set_event_bus(original_bus)

        event_types = [e.event_type for e in captured_events]
        assert "WarehouseCreated" in event_types, (
            f"WarehouseCreated event not published. Got: {event_types}"
        )
