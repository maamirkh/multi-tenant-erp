"""Unit tests — JSON serialisation round-trip for all 32 domain events.

Tests verify that every concrete event class:
  1. Can be instantiated with minimal required args
  2. ``to_dict()`` produces a dict with the correct ``event_type``
  3. All payload fields are present in the dict
  4. Serialising to JSON string and back yields identical values

T262 — specs/005-inventory-management/tasks.md
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from modules.inventory.domain_events import (
    ALL_EVENT_TYPES,
    BarcodeAssigned,
    DamagedStockRecorded,
    InventoryAdjustmentApproved,
    InventoryAdjustmentRejected,
    InventoryAdjustmentSubmitted,
    LowStockAlertRaised,
    OpeningStockRecorded,
    OutOfStockDetected,
    ProductActivated,
    ProductArchived,
    ProductCreated,
    ProductDeactivated,
    ProductDiscontinued,
    ProductUpdated,
    ProductVariantCreated,
    ProductVariantUpdated,
    ReorderSuggestionGenerated,
    ReturnedStockReceived,
    StockAdjusted,
    StockIncreased,
    StockReduced,
    StockReservationReleased,
    StockReserved,
    StockTransferCancelled,
    StockTransferDispatched,
    StockTransferInitiated,
    StockTransferReceived,
    StockTransferred,
    WarehouseArchived,
    WarehouseCreated,
    WarehouseDeactivated,
    WarehouseUpdated,
)
from modules.inventory.events import InventoryDomainEvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COMPANY = uuid4()
_PRODUCT = uuid4()
_WAREHOUSE = uuid4()
_ALERT = uuid4()
_ADJ = uuid4()
_TRANSFER = uuid4()
_VARIANT = uuid4()


def _round_trip(event: InventoryDomainEvent) -> dict:
    """Serialise to JSON string then parse back to dict."""
    return json.loads(json.dumps(event.to_dict()))


# ---------------------------------------------------------------------------
# Coverage test: all registered event types
# ---------------------------------------------------------------------------


def test_all_event_types_count() -> None:
    """ALL_EVENT_TYPES should contain 32 entries (9+12+8+3)."""
    assert len(ALL_EVENT_TYPES) == 32


def test_all_event_types_are_subclasses() -> None:
    """Every entry in ALL_EVENT_TYPES must be a subclass of InventoryDomainEvent."""
    for cls in ALL_EVENT_TYPES:
        assert issubclass(
            cls, InventoryDomainEvent
        ), f"{cls} is not a subclass of InventoryDomainEvent"


# ---------------------------------------------------------------------------
# Product Events (9)
# ---------------------------------------------------------------------------


class TestProductCreated:
    def _make(self) -> ProductCreated:
        return ProductCreated(
            aggregate_id=_PRODUCT,
            company_id=_COMPANY,
            product_code="P001",
            product_name="Test Product",
            product_type="GOODS",
            category_id=str(uuid4()),
            brand_id=str(uuid4()),
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "ProductCreated"

    def test_aggregate_type(self) -> None:
        assert self._make().aggregate_type == "Product"

    def test_to_dict_contains_payload(self) -> None:
        d = self._make().to_dict()
        assert d["product_code"] == "P001"
        assert d["product_name"] == "Test Product"
        assert d["product_type"] == "GOODS"

    def test_round_trip(self) -> None:
        event = self._make()
        d = _round_trip(event)
        assert d["event_type"] == "ProductCreated"
        assert d["product_code"] == "P001"
        assert d["aggregate_id"] == str(_PRODUCT)
        assert d["company_id"] == str(_COMPANY)


class TestProductUpdated:
    def _make(self) -> ProductUpdated:
        return ProductUpdated(
            aggregate_id=_PRODUCT,
            company_id=_COMPANY,
            changed_fields=["name", "description"],
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "ProductUpdated"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "ProductUpdated"
        assert d["changed_fields"] == ["name", "description"]


class TestProductActivated:
    def _make(self) -> ProductActivated:
        return ProductActivated(
            aggregate_id=_PRODUCT,
            company_id=_COMPANY,
            product_code="P001",
            previous_status="DRAFT",
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "ProductActivated"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "ProductActivated"
        assert d["previous_status"] == "DRAFT"


class TestProductDeactivated:
    def _make(self) -> ProductDeactivated:
        return ProductDeactivated(
            aggregate_id=_PRODUCT,
            company_id=_COMPANY,
            product_code="P001",
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "ProductDeactivated"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "ProductDeactivated"


class TestProductArchived:
    def _make(self) -> ProductArchived:
        return ProductArchived(
            aggregate_id=_PRODUCT,
            company_id=_COMPANY,
            product_code="P001",
            previous_status="INACTIVE",
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "ProductArchived"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "ProductArchived"
        assert d["previous_status"] == "INACTIVE"


class TestProductDiscontinued:
    def _make(self) -> ProductDiscontinued:
        return ProductDiscontinued(
            aggregate_id=_PRODUCT,
            company_id=_COMPANY,
            product_code="P001",
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "ProductDiscontinued"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "ProductDiscontinued"


class TestProductVariantCreated:
    def _make(self) -> ProductVariantCreated:
        return ProductVariantCreated(
            aggregate_id=_PRODUCT,
            company_id=_COMPANY,
            variant_id=str(_VARIANT),
            variant_code="V-RED",
            product_code="P001",
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "ProductVariantCreated"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "ProductVariantCreated"
        assert d["variant_code"] == "V-RED"


class TestProductVariantUpdated:
    def _make(self) -> ProductVariantUpdated:
        return ProductVariantUpdated(
            aggregate_id=_PRODUCT,
            company_id=_COMPANY,
            variant_id=str(_VARIANT),
            changed_fields=["price"],
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "ProductVariantUpdated"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "ProductVariantUpdated"
        assert d["changed_fields"] == ["price"]


class TestBarcodeAssigned:
    def _make(self) -> BarcodeAssigned:
        return BarcodeAssigned(
            aggregate_id=_PRODUCT,
            company_id=_COMPANY,
            barcode_value="1234567890123",
            barcode_type="EAN13",
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "BarcodeAssigned"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "BarcodeAssigned"
        assert d["barcode_value"] == "1234567890123"
        assert d["barcode_type"] == "EAN13"
        assert d["variant_id"] is None


# ---------------------------------------------------------------------------
# Stock Events (12)
# ---------------------------------------------------------------------------


class TestOpeningStockRecorded:
    def _make(self) -> OpeningStockRecorded:
        return OpeningStockRecorded(
            aggregate_id=_PRODUCT,
            company_id=_COMPANY,
            product_id=str(_PRODUCT),
            warehouse_id=str(_WAREHOUSE),
            quantity="100",
            unit_cost="25.50",
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "OpeningStockRecorded"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "OpeningStockRecorded"
        assert d["quantity"] == "100"
        assert d["unit_cost"] == "25.50"


class TestStockIncreased:
    def _make(self) -> StockIncreased:
        return StockIncreased(
            aggregate_id=_PRODUCT,
            company_id=_COMPANY,
            product_id=str(_PRODUCT),
            warehouse_id=str(_WAREHOUSE),
            quantity="50",
            movement_type="PURCHASE_RECEIPT",
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "StockIncreased"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "StockIncreased"
        assert d["movement_type"] == "PURCHASE_RECEIPT"


class TestStockReduced:
    def _make(self) -> StockReduced:
        return StockReduced(
            aggregate_id=_PRODUCT,
            company_id=_COMPANY,
            product_id=str(_PRODUCT),
            warehouse_id=str(_WAREHOUSE),
            quantity="10",
            movement_type="SALES_ISSUE",
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "StockReduced"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "StockReduced"
        assert d["quantity"] == "10"


class TestStockReserved:
    def _make(self) -> StockReserved:
        return StockReserved(
            aggregate_id=_PRODUCT,
            company_id=_COMPANY,
            product_id=str(_PRODUCT),
            warehouse_id=str(_WAREHOUSE),
            reserved_quantity="5",
            reservation_reference="SO-001",
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "StockReserved"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "StockReserved"
        assert d["reservation_reference"] == "SO-001"


class TestStockReservationReleased:
    def _make(self) -> StockReservationReleased:
        return StockReservationReleased(
            aggregate_id=_PRODUCT,
            company_id=_COMPANY,
            product_id=str(_PRODUCT),
            warehouse_id=str(_WAREHOUSE),
            released_quantity="5",
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "StockReservationReleased"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "StockReservationReleased"


class TestStockAdjusted:
    def _make(self) -> StockAdjusted:
        return StockAdjusted(
            aggregate_id=_PRODUCT,
            company_id=_COMPANY,
            product_id=str(_PRODUCT),
            warehouse_id=str(_WAREHOUSE),
            adjustment_qty="3",
            adjustment_id=str(_ADJ),
            reason_code="DAMAGE",
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "StockAdjusted"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "StockAdjusted"
        assert d["reason_code"] == "DAMAGE"


class TestStockTransferred:
    def _make(self) -> StockTransferred:
        return StockTransferred(
            aggregate_id=_PRODUCT,
            company_id=_COMPANY,
            product_id=str(_PRODUCT),
            from_warehouse_id=str(_WAREHOUSE),
            to_warehouse_id=str(uuid4()),
            quantity="20",
            transfer_id=str(_TRANSFER),
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "StockTransferred"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "StockTransferred"
        assert d["quantity"] == "20"


class TestDamagedStockRecorded:
    def _make(self) -> DamagedStockRecorded:
        return DamagedStockRecorded(
            aggregate_id=_PRODUCT,
            company_id=_COMPANY,
            product_id=str(_PRODUCT),
            warehouse_id=str(_WAREHOUSE),
            quantity="2",
            reason_code="TRANSPORT",
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "DamagedStockRecorded"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "DamagedStockRecorded"
        assert d["reason_code"] == "TRANSPORT"


class TestReturnedStockReceived:
    def _make(self) -> ReturnedStockReceived:
        return ReturnedStockReceived(
            aggregate_id=_PRODUCT,
            company_id=_COMPANY,
            product_id=str(_PRODUCT),
            warehouse_id=str(_WAREHOUSE),
            quantity="3",
            source_reference="RET-001",
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "ReturnedStockReceived"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "ReturnedStockReceived"
        assert d["source_reference"] == "RET-001"


class TestLowStockAlertRaised:
    def _make(self) -> LowStockAlertRaised:
        return LowStockAlertRaised(
            aggregate_id=_ALERT,
            company_id=_COMPANY,
            product_id=str(_PRODUCT),
            warehouse_id=str(_WAREHOUSE),
            current_qty="2",
            minimum_stock="10",
            alert_id=str(_ALERT),
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "LowStockAlertRaised"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "LowStockAlertRaised"
        assert d["current_qty"] == "2"
        assert d["minimum_stock"] == "10"


class TestReorderSuggestionGenerated:
    def _make(self) -> ReorderSuggestionGenerated:
        return ReorderSuggestionGenerated(
            aggregate_id=_PRODUCT,
            company_id=_COMPANY,
            product_id=str(_PRODUCT),
            warehouse_id=str(_WAREHOUSE),
            suggested_qty="50",
            suggestion_id=str(uuid4()),
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "ReorderSuggestionGenerated"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "ReorderSuggestionGenerated"
        assert d["suggested_qty"] == "50"


class TestOutOfStockDetected:
    def _make(self) -> OutOfStockDetected:
        return OutOfStockDetected(
            aggregate_id=_PRODUCT,
            company_id=_COMPANY,
            product_id=str(_PRODUCT),
            warehouse_id=str(_WAREHOUSE),
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "OutOfStockDetected"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "OutOfStockDetected"
        assert d["product_id"] == str(_PRODUCT)


# ---------------------------------------------------------------------------
# Warehouse Events (8)
# ---------------------------------------------------------------------------


class TestWarehouseCreated:
    def _make(self) -> WarehouseCreated:
        return WarehouseCreated(
            aggregate_id=_WAREHOUSE,
            company_id=_COMPANY,
            warehouse_code="WH-MAIN",
            warehouse_name="Main Warehouse",
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "WarehouseCreated"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "WarehouseCreated"
        assert d["warehouse_code"] == "WH-MAIN"
        assert d["warehouse_name"] == "Main Warehouse"


class TestWarehouseUpdated:
    def _make(self) -> WarehouseUpdated:
        return WarehouseUpdated(
            aggregate_id=_WAREHOUSE,
            company_id=_COMPANY,
            changed_fields=["name", "city"],
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "WarehouseUpdated"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "WarehouseUpdated"


class TestWarehouseDeactivated:
    def _make(self) -> WarehouseDeactivated:
        return WarehouseDeactivated(
            aggregate_id=_WAREHOUSE,
            company_id=_COMPANY,
            warehouse_code="WH-MAIN",
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "WarehouseDeactivated"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "WarehouseDeactivated"


class TestWarehouseArchived:
    def _make(self) -> WarehouseArchived:
        return WarehouseArchived(
            aggregate_id=_WAREHOUSE,
            company_id=_COMPANY,
            warehouse_code="WH-OLD",
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "WarehouseArchived"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "WarehouseArchived"
        assert d["warehouse_code"] == "WH-OLD"


class TestStockTransferInitiated:
    def _make(self) -> StockTransferInitiated:
        return StockTransferInitiated(
            aggregate_id=_TRANSFER,
            company_id=_COMPANY,
            transfer_id=str(_TRANSFER),
            from_warehouse_id=str(_WAREHOUSE),
            to_warehouse_id=str(uuid4()),
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "StockTransferInitiated"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "StockTransferInitiated"
        assert d["transfer_id"] == str(_TRANSFER)


class TestStockTransferDispatched:
    def _make(self) -> StockTransferDispatched:
        return StockTransferDispatched(
            aggregate_id=_TRANSFER,
            company_id=_COMPANY,
            transfer_id=str(_TRANSFER),
            from_warehouse_id=str(_WAREHOUSE),
            to_warehouse_id=str(uuid4()),
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "StockTransferDispatched"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "StockTransferDispatched"


class TestStockTransferReceived:
    def _make(self) -> StockTransferReceived:
        return StockTransferReceived(
            aggregate_id=_TRANSFER,
            company_id=_COMPANY,
            transfer_id=str(_TRANSFER),
            from_warehouse_id=str(_WAREHOUSE),
            to_warehouse_id=str(uuid4()),
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "StockTransferReceived"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "StockTransferReceived"


class TestStockTransferCancelled:
    def _make(self) -> StockTransferCancelled:
        return StockTransferCancelled(
            aggregate_id=_TRANSFER,
            company_id=_COMPANY,
            transfer_id=str(_TRANSFER),
            reason="No longer needed",
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "StockTransferCancelled"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "StockTransferCancelled"
        assert d["reason"] == "No longer needed"


# ---------------------------------------------------------------------------
# Adjustment Events (3)
# ---------------------------------------------------------------------------


class TestInventoryAdjustmentSubmitted:
    def _make(self) -> InventoryAdjustmentSubmitted:
        return InventoryAdjustmentSubmitted(
            aggregate_id=_ADJ,
            company_id=_COMPANY,
            adjustment_id=str(_ADJ),
            product_id=str(_PRODUCT),
            warehouse_id=str(_WAREHOUSE),
            qty_delta="5",
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "InventoryAdjustmentSubmitted"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "InventoryAdjustmentSubmitted"
        assert d["qty_delta"] == "5"


class TestInventoryAdjustmentApproved:
    def _make(self) -> InventoryAdjustmentApproved:
        return InventoryAdjustmentApproved(
            aggregate_id=_ADJ,
            company_id=_COMPANY,
            adjustment_id=str(_ADJ),
            approved_by=str(uuid4()),
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "InventoryAdjustmentApproved"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "InventoryAdjustmentApproved"
        assert "approved_by" in d


class TestInventoryAdjustmentRejected:
    def _make(self) -> InventoryAdjustmentRejected:
        return InventoryAdjustmentRejected(
            aggregate_id=_ADJ,
            company_id=_COMPANY,
            adjustment_id=str(_ADJ),
            rejected_by=str(uuid4()),
            reason="Incorrect quantity",
        )

    def test_event_type(self) -> None:
        assert self._make().event_type == "InventoryAdjustmentRejected"

    def test_round_trip(self) -> None:
        d = _round_trip(self._make())
        assert d["event_type"] == "InventoryAdjustmentRejected"
        assert d["reason"] == "Incorrect quantity"


# ---------------------------------------------------------------------------
# Cross-cutting: base fields always present
# ---------------------------------------------------------------------------


class TestBaseFields:
    """Every event must include all mandatory base fields in to_dict()."""

    @pytest.mark.parametrize("event_cls", ALL_EVENT_TYPES)
    def test_base_fields_present(self, event_cls: type[InventoryDomainEvent]) -> None:
        event = event_cls(aggregate_id=_PRODUCT, company_id=_COMPANY)
        d = event.to_dict()
        required = {
            "event_id",
            "event_type",
            "aggregate_type",
            "aggregate_id",
            "company_id",
            "occurred_at",
        }
        missing = required - d.keys()
        assert not missing, f"{event_cls.__name__} missing keys: {missing}"

    @pytest.mark.parametrize("event_cls", ALL_EVENT_TYPES)
    def test_json_serialisable(self, event_cls: type[InventoryDomainEvent]) -> None:
        event = event_cls(aggregate_id=_PRODUCT, company_id=_COMPANY)
        d = _round_trip(event)
        assert d["event_type"] == event.event_type

    @pytest.mark.parametrize("event_cls", ALL_EVENT_TYPES)
    def test_event_id_unique_per_instance(
        self, event_cls: type[InventoryDomainEvent]
    ) -> None:
        e1 = event_cls(aggregate_id=_PRODUCT, company_id=_COMPANY)
        e2 = event_cls(aggregate_id=_PRODUCT, company_id=_COMPANY)
        assert e1.event_id != e2.event_id

    @pytest.mark.parametrize("event_cls", ALL_EVENT_TYPES)
    def test_event_type_matches_class_name(
        self, event_cls: type[InventoryDomainEvent]
    ) -> None:
        event = event_cls(aggregate_id=_PRODUCT, company_id=_COMPANY)
        assert (
            event.event_type == event_cls.__name__
        ), f"{event_cls.__name__}.event_type={event.event_type!r} does not match class name"
