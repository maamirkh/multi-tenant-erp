"""T289 — Domain event coverage verification.

Verifies that:
  1. All 32 domain event classes can be instantiated.
  2. All events produce valid JSON-serialisable ``to_dict()`` output.
  3. Services that use the global EventBus fire their events correctly.
  4. Events published via get_event_bus() can be subscribed to and captured.

Note: ProductService uses its own internal InProcessEventBus instance (by design
for isolated dependency injection). Warehouse, Stock, Adjustment, Transfer,
and Alert services use the global event bus (get_event_bus()).

This test verifies all 32 event classes are correct dataclasses, and that
representative events from each service domain are properly published.

Spec ref: specs/005-inventory-management/spec.md §31 (Domain Events)
Tasks: T289 Phase 12
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.inventory import domain_events as de
from modules.inventory.events import InProcessEventBus, get_event_bus, set_event_bus
from modules.inventory.models.uom import UOM
from modules.inventory.models.warehouse import Warehouse
from tests.fixtures.auth_fixtures import create_test_user

# ---------------------------------------------------------------------------
# All 32 domain event classes
# ---------------------------------------------------------------------------

ALL_EVENT_CLASSES = [
    de.ProductCreated,
    de.ProductUpdated,
    de.ProductActivated,
    de.ProductDeactivated,
    de.ProductArchived,
    de.ProductDiscontinued,
    de.ProductVariantCreated,
    de.ProductVariantUpdated,
    de.BarcodeAssigned,
    de.OpeningStockRecorded,
    de.StockIncreased,
    de.StockReduced,
    de.StockReserved,
    de.StockReservationReleased,
    de.StockAdjusted,
    de.StockTransferred,
    de.DamagedStockRecorded,
    de.ReturnedStockReceived,
    de.LowStockAlertRaised,
    de.ReorderSuggestionGenerated,
    de.OutOfStockDetected,
    de.WarehouseCreated,
    de.WarehouseUpdated,
    de.WarehouseDeactivated,
    de.WarehouseArchived,
    de.StockTransferInitiated,
    de.StockTransferDispatched,
    de.StockTransferReceived,
    de.StockTransferCancelled,
    de.InventoryAdjustmentSubmitted,
    de.InventoryAdjustmentApproved,
    de.InventoryAdjustmentRejected,
]


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
            "legal_name": f"Inventory Test Co {suffix}",
            "email": f"contact-{suffix}@inv-test.example.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def _auth(client: TestClient, db: Session) -> tuple[dict, uuid.UUID]:
    email = f"evt-{uuid.uuid4().hex[:8]}@test.com"
    create_test_user(db, email=email, password="TestPass123!")
    token = _login(client, email, "TestPass123!")
    company_id = _create_company(client, token)
    return {"Authorization": f"Bearer {token}"}, company_id


def _make_event_kwargs(event_cls) -> dict:
    """Build minimal kwargs to instantiate any domain event class."""
    import dataclasses

    company_id = uuid.uuid4()
    aggregate_id = uuid.uuid4()

    # Base kwargs that all events inherit
    base = {
        "aggregate_id": aggregate_id,
        "company_id": company_id,
    }

    # Per-class additional required fields (non-default, non-init=False fields)
    field_defaults = {
        # Product events
        "product_id": uuid.uuid4(),
        "product_code": "TEST-001",
        "name": "Test Product",
        "product_type": "STANDARD",
        "status": "ACTIVE",
        # Stock events
        "warehouse_id": uuid.uuid4(),
        "quantity": Decimal("10"),
        "unit_cost": Decimal("5.00"),
        "currency_code": "USD",
        "movement_type": "OPENING",
        "direction": "IN",
        "position_qty": Decimal("10"),
        "position_after": Decimal("10"),
        "qty_reserved": Decimal("0"),
        "available_qty": Decimal("10"),
        "on_hand_before": Decimal("20"),
        "on_hand_after": Decimal("10"),
        "reserved_qty": Decimal("5"),
        "qty_released": Decimal("5"),
        "adjustment_id": uuid.uuid4(),
        "old_quantity": Decimal("10"),
        "new_quantity": Decimal("15"),
        "reason_code": "DMG",
        "damaged_quantity": Decimal("2"),
        "returned_quantity": Decimal("3"),
        # Warehouse events
        "warehouse_code": "WH-001",
        "warehouse_name": "Test Warehouse",
        "warehouse_type": "MAIN",
        # Transfer events
        "transfer_id": uuid.uuid4(),
        "source_warehouse_id": uuid.uuid4(),
        "destination_warehouse_id": uuid.uuid4(),
        "total_lines": 1,
        "received_at": datetime.now(tz=UTC),
        "dispatched_at": datetime.now(tz=UTC),
        "cancelled_at": datetime.now(tz=UTC),
        "cancel_reason": "Test",
        # Alert events
        "alert_id": uuid.uuid4(),
        "alert_type": "LOW_STOCK",
        "current_qty": Decimal("5"),
        "threshold_qty": Decimal("10"),
        "suggested_qty": Decimal("50"),
        "reorder_point": Decimal("10"),
        "reorder_qty": Decimal("50"),
        # Barcode event
        "barcode": "1234567890",
        "barcode_type": "EAN13",
        # Variant events
        "variant_id": uuid.uuid4(),
        "variant_sku": "SKU-001",
        # Adjustment submitted/approved/rejected
        "submitted_by": uuid.uuid4(),
        "approved_by": uuid.uuid4(),
        "rejected_by": uuid.uuid4(),
        "rejection_reason": "Test rejection",
    }

    # Get the dataclass fields for this event class
    try:
        fields = dataclasses.fields(event_cls)
    except TypeError:
        return base

    kwargs = dict(base)
    for f in fields:
        if not f.init or f.name in base:
            continue
        if (
            f.default is not dataclasses.MISSING
            or f.default_factory is not dataclasses.MISSING
        ):
            continue
        # Required field — use our defaults if available
        if f.name in field_defaults:
            kwargs[f.name] = field_defaults[f.name]

    return kwargs


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEventCoverage:
    """All 32 domain event classes are instantiable and JSON-serialisable."""

    def test_all_32_event_classes_exist(self) -> None:
        """Verify exactly 32 domain event classes are defined."""
        assert (
            len(ALL_EVENT_CLASSES) == 32
        ), f"Expected 32 domain event classes, found {len(ALL_EVENT_CLASSES)}"

    @pytest.mark.parametrize("event_cls", ALL_EVENT_CLASSES, ids=lambda c: c.__name__)
    def test_event_class_instantiable(self, event_cls) -> None:
        """Each event class can be instantiated with required fields."""
        kwargs = _make_event_kwargs(event_cls)
        try:
            event = event_cls(**kwargs)
        except Exception as exc:
            pytest.fail(
                f"Failed to instantiate {event_cls.__name__} with kwargs {list(kwargs)}: {exc}"
            )

        assert event.event_type, f"{event_cls.__name__} has empty event_type"
        assert event.company_id is not None
        assert event.aggregate_id is not None

    @pytest.mark.parametrize("event_cls", ALL_EVENT_CLASSES, ids=lambda c: c.__name__)
    def test_event_class_to_dict_json_serialisable(self, event_cls) -> None:
        """Each event's to_dict() produces valid JSON."""
        kwargs = _make_event_kwargs(event_cls)
        try:
            event = event_cls(**kwargs)
            d = event.to_dict()
            serialised = json.dumps(d)
        except Exception as exc:
            pytest.fail(f"Failed to serialise {event_cls.__name__}.to_dict(): {exc}")

        assert (
            len(serialised) > 2
        ), f"{event_cls.__name__}.to_dict() returned empty JSON"
        # Round-trip check
        parsed = json.loads(serialised)
        assert parsed["event_type"] == event.event_type

    def test_event_bus_subscribe_and_capture(self) -> None:
        """InProcessEventBus correctly captures published events via wildcard subscribe."""
        captured = []
        bus = InProcessEventBus()
        bus.subscribe("*", lambda e: captured.append(e))

        # Publish a sample event
        event = de.WarehouseCreated(
            aggregate_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            warehouse_code="WH-TEST",
            warehouse_name="Test",
        )
        bus.publish(event)

        assert len(captured) == 1
        assert captured[0].event_type == "WarehouseCreated"

    def test_global_event_bus_captures_warehouse_events(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """WarehouseCreated event is captured via global event bus on API call."""
        captured = []
        original_bus = get_event_bus()
        tracking_bus = InProcessEventBus()
        tracking_bus.subscribe("*", lambda e: captured.append(e))
        set_event_bus(tracking_bus)

        try:
            headers, company_id = _auth(test_client, db_session)
            resp = test_client.post(
                _url(company_id, "/warehouses"),
                json={
                    "code": f"EC{uuid.uuid4().hex[:4].upper()}",
                    "name": "Event Coverage WH",
                    "warehouse_type": "MAIN",
                },
                headers=headers,
            )
            assert resp.status_code == 201
        finally:
            set_event_bus(original_bus)

        event_types = {e.event_type for e in captured}
        assert (
            "WarehouseCreated" in event_types
        ), f"WarehouseCreated not captured. Got: {sorted(event_types)}"

    def test_global_event_bus_captures_stock_events(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """OpeningStockRecorded event is captured via global event bus on API call."""
        captured = []
        original_bus = get_event_bus()
        tracking_bus = InProcessEventBus()
        tracking_bus.subscribe("*", lambda e: captured.append(e))
        set_event_bus(tracking_bus)

        try:
            headers, company_id = _auth(test_client, db_session)

            uom = UOM(
                id=uuid.uuid4(),
                company_id=company_id,
                code=f"EC{uuid.uuid4().hex[:4].upper()}",
                name="Units",
                uom_type="UNIT",
                status="active",
            )
            db_session.add(uom)
            wh = Warehouse(
                id=uuid.uuid4(),
                company_id=company_id,
                code=f"ES{uuid.uuid4().hex[:4].upper()}",
                name="Event Stock WH",
                warehouse_type="MAIN",
                status="ACTIVE",
            )
            db_session.add(wh)
            db_session.flush()

            resp = test_client.post(
                _url(company_id, "/products"),
                json={
                    "product_code": f"EV-{uuid.uuid4().hex[:6].upper()}",
                    "name": "Event Coverage Product",
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
                    "quantity": "10",
                    "unit_cost": "5.00",
                    "currency_code": "USD",
                },
                headers=headers,
            )
            assert resp.status_code == 201
        finally:
            set_event_bus(original_bus)

        event_types = {e.event_type for e in captured}
        assert (
            "OpeningStockRecorded" in event_types
        ), f"OpeningStockRecorded not captured. Got: {sorted(event_types)}"

    def test_all_event_types_documented(self) -> None:
        """Assert the event type strings match the expected spec §31 catalogue."""
        expected_event_types = {
            "ProductCreated",
            "ProductUpdated",
            "ProductActivated",
            "ProductDeactivated",
            "ProductArchived",
            "ProductDiscontinued",
            "ProductVariantCreated",
            "ProductVariantUpdated",
            "BarcodeAssigned",
            "OpeningStockRecorded",
            "StockIncreased",
            "StockReduced",
            "StockReserved",
            "StockReservationReleased",
            "StockAdjusted",
            "StockTransferred",
            "DamagedStockRecorded",
            "ReturnedStockReceived",
            "LowStockAlertRaised",
            "ReorderSuggestionGenerated",
            "OutOfStockDetected",
            "WarehouseCreated",
            "WarehouseUpdated",
            "WarehouseDeactivated",
            "WarehouseArchived",
            "StockTransferInitiated",
            "StockTransferDispatched",
            "StockTransferReceived",
            "StockTransferCancelled",
            "InventoryAdjustmentSubmitted",
            "InventoryAdjustmentApproved",
            "InventoryAdjustmentRejected",
        }

        actual_event_types = set()
        for cls in ALL_EVENT_CLASSES:
            kwargs = _make_event_kwargs(cls)
            try:
                event = cls(**kwargs)
                actual_event_types.add(event.event_type)
            except Exception:
                pass

        missing = expected_event_types - actual_event_types
        assert (
            not missing
        ), f"Missing domain event types from catalogue: {sorted(missing)}"
