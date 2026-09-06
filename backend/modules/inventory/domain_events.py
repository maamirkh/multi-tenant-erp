"""Typed inventory domain event classes — Phase 10 Integration Foundation.

Every class inherits ``InventoryDomainEvent`` and adds event-specific
payload fields. The ``to_dict()`` method serialises the base fields; each
concrete class overrides it to include its payload.

Spec ref: specs/005-inventory-management/spec.md §31 Domain Events
Tasks:   T260 — create all 31 domain event classes

Event categories
----------------
  Product (9):    ProductCreated, ProductUpdated, ProductActivated,
                  ProductDeactivated, ProductArchived, ProductDiscontinued,
                  ProductVariantCreated, ProductVariantUpdated, BarcodeAssigned
  Stock (12):     OpeningStockRecorded, StockIncreased, StockReduced,
                  StockReserved, StockReservationReleased, StockAdjusted,
                  StockTransferred, DamagedStockRecorded, ReturnedStockReceived,
                  LowStockAlertRaised, ReorderSuggestionGenerated, OutOfStockDetected
  Warehouse (8):  WarehouseCreated, WarehouseUpdated, WarehouseDeactivated,
                  WarehouseArchived, StockTransferInitiated,
                  StockTransferDispatched, StockTransferReceived,
                  StockTransferCancelled
  Adjustment (3): InventoryAdjustmentSubmitted, InventoryAdjustmentApproved,
                  InventoryAdjustmentRejected
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from modules.inventory.events import InventoryDomainEvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    """Return ``base`` dict merged with ``extra`` payload."""
    result = base.copy()
    result.update(extra)
    return result


# ===========================================================================
# Product Events (9)
# ===========================================================================


@dataclass
class ProductCreated(InventoryDomainEvent):
    """Raised when a new product is created (status=DRAFT)."""

    event_type: str = field(default="ProductCreated", init=False)
    aggregate_type: str = field(default="Product", init=False)

    product_code: str = ""
    product_name: str = ""
    product_type: str = ""
    category_id: str | None = None
    brand_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "product_code": self.product_code,
                "product_name": self.product_name,
                "product_type": self.product_type,
                "category_id": self.category_id,
                "brand_id": self.brand_id,
            },
        )


@dataclass
class ProductUpdated(InventoryDomainEvent):
    """Raised when mutable product fields are changed."""

    event_type: str = field(default="ProductUpdated", init=False)
    aggregate_type: str = field(default="Product", init=False)

    changed_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _merge(super().to_dict(), {"changed_fields": self.changed_fields})


@dataclass
class ProductActivated(InventoryDomainEvent):
    """Raised when a product transitions to ACTIVE status."""

    event_type: str = field(default="ProductActivated", init=False)
    aggregate_type: str = field(default="Product", init=False)

    product_code: str = ""
    previous_status: str = "DRAFT"

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "product_code": self.product_code,
                "previous_status": self.previous_status,
            },
        )


@dataclass
class ProductDeactivated(InventoryDomainEvent):
    """Raised when a product transitions to INACTIVE status."""

    event_type: str = field(default="ProductDeactivated", init=False)
    aggregate_type: str = field(default="Product", init=False)

    product_code: str = ""
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {"product_code": self.product_code, "reason": self.reason},
        )


@dataclass
class ProductArchived(InventoryDomainEvent):
    """Raised when a product reaches terminal ARCHIVED status."""

    event_type: str = field(default="ProductArchived", init=False)
    aggregate_type: str = field(default="Product", init=False)

    product_code: str = ""
    previous_status: str = "INACTIVE"

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "product_code": self.product_code,
                "previous_status": self.previous_status,
            },
        )


@dataclass
class ProductDiscontinued(InventoryDomainEvent):
    """Raised when a product transitions to DISCONTINUED status."""

    event_type: str = field(default="ProductDiscontinued", init=False)
    aggregate_type: str = field(default="Product", init=False)

    product_code: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _merge(super().to_dict(), {"product_code": self.product_code})


@dataclass
class ProductVariantCreated(InventoryDomainEvent):
    """Raised when a new variant is added to a product."""

    event_type: str = field(default="ProductVariantCreated", init=False)
    aggregate_type: str = field(default="Product", init=False)

    variant_id: str = ""
    variant_code: str = ""
    product_code: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "variant_id": self.variant_id,
                "variant_code": self.variant_code,
                "product_code": self.product_code,
            },
        )


@dataclass
class ProductVariantUpdated(InventoryDomainEvent):
    """Raised when a product variant is modified."""

    event_type: str = field(default="ProductVariantUpdated", init=False)
    aggregate_type: str = field(default="Product", init=False)

    variant_id: str = ""
    changed_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {"variant_id": self.variant_id, "changed_fields": self.changed_fields},
        )


@dataclass
class BarcodeAssigned(InventoryDomainEvent):
    """Raised when a barcode is assigned to a product or variant."""

    event_type: str = field(default="BarcodeAssigned", init=False)
    aggregate_type: str = field(default="Product", init=False)

    barcode_value: str = ""
    barcode_type: str = ""
    variant_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "barcode_value": self.barcode_value,
                "barcode_type": self.barcode_type,
                "variant_id": self.variant_id,
            },
        )


# ===========================================================================
# Stock Events (12)
# ===========================================================================


@dataclass
class OpeningStockRecorded(InventoryDomainEvent):
    """Raised when opening stock is recorded for a product at a warehouse."""

    event_type: str = field(default="OpeningStockRecorded", init=False)
    aggregate_type: str = field(default="StockPosition", init=False)

    product_id: str = ""
    warehouse_id: str = ""
    quantity: str = "0"
    unit_cost: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "product_id": self.product_id,
                "warehouse_id": self.warehouse_id,
                "quantity": self.quantity,
                "unit_cost": self.unit_cost,
            },
        )


@dataclass
class StockIncreased(InventoryDomainEvent):
    """Raised when stock quantity increases (purchase receipt, return, etc.)."""

    event_type: str = field(default="StockIncreased", init=False)
    aggregate_type: str = field(default="StockPosition", init=False)

    product_id: str = ""
    warehouse_id: str = ""
    quantity: str = "0"
    movement_type: str = ""
    reference_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "product_id": self.product_id,
                "warehouse_id": self.warehouse_id,
                "quantity": self.quantity,
                "movement_type": self.movement_type,
                "reference_id": self.reference_id,
            },
        )


@dataclass
class StockReduced(InventoryDomainEvent):
    """Raised when stock quantity decreases (sale, write-off, damage, etc.)."""

    event_type: str = field(default="StockReduced", init=False)
    aggregate_type: str = field(default="StockPosition", init=False)

    product_id: str = ""
    warehouse_id: str = ""
    quantity: str = "0"
    movement_type: str = ""
    reference_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "product_id": self.product_id,
                "warehouse_id": self.warehouse_id,
                "quantity": self.quantity,
                "movement_type": self.movement_type,
                "reference_id": self.reference_id,
            },
        )


@dataclass
class StockReserved(InventoryDomainEvent):
    """Raised when stock is reserved (e.g. for a sales order)."""

    event_type: str = field(default="StockReserved", init=False)
    aggregate_type: str = field(default="StockPosition", init=False)

    product_id: str = ""
    warehouse_id: str = ""
    reserved_quantity: str = "0"
    reservation_reference: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "product_id": self.product_id,
                "warehouse_id": self.warehouse_id,
                "reserved_quantity": self.reserved_quantity,
                "reservation_reference": self.reservation_reference,
            },
        )


@dataclass
class StockReservationReleased(InventoryDomainEvent):
    """Raised when a reservation is released back to available stock."""

    event_type: str = field(default="StockReservationReleased", init=False)
    aggregate_type: str = field(default="StockPosition", init=False)

    product_id: str = ""
    warehouse_id: str = ""
    released_quantity: str = "0"
    reservation_reference: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "product_id": self.product_id,
                "warehouse_id": self.warehouse_id,
                "released_quantity": self.released_quantity,
                "reservation_reference": self.reservation_reference,
            },
        )


@dataclass
class StockAdjusted(InventoryDomainEvent):
    """Raised when an approved inventory adjustment is applied."""

    event_type: str = field(default="StockAdjusted", init=False)
    aggregate_type: str = field(default="StockPosition", init=False)

    product_id: str = ""
    warehouse_id: str = ""
    adjustment_qty: str = "0"
    adjustment_id: str = ""
    reason_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "product_id": self.product_id,
                "warehouse_id": self.warehouse_id,
                "adjustment_qty": self.adjustment_qty,
                "adjustment_id": self.adjustment_id,
                "reason_code": self.reason_code,
            },
        )


@dataclass
class StockTransferred(InventoryDomainEvent):
    """Raised when stock is moved between warehouses."""

    event_type: str = field(default="StockTransferred", init=False)
    aggregate_type: str = field(default="StockPosition", init=False)

    product_id: str = ""
    from_warehouse_id: str = ""
    to_warehouse_id: str = ""
    quantity: str = "0"
    transfer_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "product_id": self.product_id,
                "from_warehouse_id": self.from_warehouse_id,
                "to_warehouse_id": self.to_warehouse_id,
                "quantity": self.quantity,
                "transfer_id": self.transfer_id,
            },
        )


@dataclass
class DamagedStockRecorded(InventoryDomainEvent):
    """Raised when stock is recorded as damaged."""

    event_type: str = field(default="DamagedStockRecorded", init=False)
    aggregate_type: str = field(default="StockPosition", init=False)

    product_id: str = ""
    warehouse_id: str = ""
    quantity: str = "0"
    reason_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "product_id": self.product_id,
                "warehouse_id": self.warehouse_id,
                "quantity": self.quantity,
                "reason_code": self.reason_code,
            },
        )


@dataclass
class ReturnedStockReceived(InventoryDomainEvent):
    """Raised when returned goods are received back into stock."""

    event_type: str = field(default="ReturnedStockReceived", init=False)
    aggregate_type: str = field(default="StockPosition", init=False)

    product_id: str = ""
    warehouse_id: str = ""
    quantity: str = "0"
    source_reference: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "product_id": self.product_id,
                "warehouse_id": self.warehouse_id,
                "quantity": self.quantity,
                "source_reference": self.source_reference,
            },
        )


@dataclass
class LowStockAlertRaised(InventoryDomainEvent):
    """Raised when a product's stock falls below the minimum threshold."""

    event_type: str = field(default="LowStockAlertRaised", init=False)
    aggregate_type: str = field(default="StockPosition", init=False)

    product_id: str = ""
    warehouse_id: str = ""
    current_qty: str = "0"
    minimum_stock: str = "0"
    alert_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "product_id": self.product_id,
                "warehouse_id": self.warehouse_id,
                "current_qty": self.current_qty,
                "minimum_stock": self.minimum_stock,
                "alert_id": self.alert_id,
            },
        )


@dataclass
class ReorderSuggestionGenerated(InventoryDomainEvent):
    """Raised when the system generates an automatic reorder suggestion."""

    event_type: str = field(default="ReorderSuggestionGenerated", init=False)
    aggregate_type: str = field(default="StockPosition", init=False)

    product_id: str = ""
    warehouse_id: str = ""
    suggested_qty: str = "0"
    suggestion_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "product_id": self.product_id,
                "warehouse_id": self.warehouse_id,
                "suggested_qty": self.suggested_qty,
                "suggestion_id": self.suggestion_id,
            },
        )


@dataclass
class OutOfStockDetected(InventoryDomainEvent):
    """Raised when a product's on-hand quantity reaches zero."""

    event_type: str = field(default="OutOfStockDetected", init=False)
    aggregate_type: str = field(default="StockPosition", init=False)

    product_id: str = ""
    warehouse_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {"product_id": self.product_id, "warehouse_id": self.warehouse_id},
        )


# ===========================================================================
# Warehouse Events (8)
# ===========================================================================


@dataclass
class WarehouseCreated(InventoryDomainEvent):
    """Raised when a new warehouse is created."""

    event_type: str = field(default="WarehouseCreated", init=False)
    aggregate_type: str = field(default="Warehouse", init=False)

    warehouse_code: str = ""
    warehouse_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "warehouse_code": self.warehouse_code,
                "warehouse_name": self.warehouse_name,
            },
        )


@dataclass
class WarehouseUpdated(InventoryDomainEvent):
    """Raised when warehouse details are modified."""

    event_type: str = field(default="WarehouseUpdated", init=False)
    aggregate_type: str = field(default="Warehouse", init=False)

    changed_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _merge(super().to_dict(), {"changed_fields": self.changed_fields})


@dataclass
class WarehouseDeactivated(InventoryDomainEvent):
    """Raised when a warehouse is set to INACTIVE."""

    event_type: str = field(default="WarehouseDeactivated", init=False)
    aggregate_type: str = field(default="Warehouse", init=False)

    warehouse_code: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _merge(super().to_dict(), {"warehouse_code": self.warehouse_code})


@dataclass
class WarehouseArchived(InventoryDomainEvent):
    """Raised when a warehouse reaches terminal ARCHIVED status."""

    event_type: str = field(default="WarehouseArchived", init=False)
    aggregate_type: str = field(default="Warehouse", init=False)

    warehouse_code: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _merge(super().to_dict(), {"warehouse_code": self.warehouse_code})


@dataclass
class StockTransferInitiated(InventoryDomainEvent):
    """Raised when a warehouse transfer is created (status=DRAFT)."""

    event_type: str = field(default="StockTransferInitiated", init=False)
    aggregate_type: str = field(default="StockTransfer", init=False)

    transfer_id: str = ""
    from_warehouse_id: str = ""
    to_warehouse_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "transfer_id": self.transfer_id,
                "from_warehouse_id": self.from_warehouse_id,
                "to_warehouse_id": self.to_warehouse_id,
            },
        )


@dataclass
class StockTransferDispatched(InventoryDomainEvent):
    """Raised when stock leaves the source warehouse (status=IN_TRANSIT)."""

    event_type: str = field(default="StockTransferDispatched", init=False)
    aggregate_type: str = field(default="StockTransfer", init=False)

    transfer_id: str = ""
    from_warehouse_id: str = ""
    to_warehouse_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "transfer_id": self.transfer_id,
                "from_warehouse_id": self.from_warehouse_id,
                "to_warehouse_id": self.to_warehouse_id,
            },
        )


@dataclass
class StockTransferReceived(InventoryDomainEvent):
    """Raised when stock arrives at the destination warehouse (status=RECEIVED)."""

    event_type: str = field(default="StockTransferReceived", init=False)
    aggregate_type: str = field(default="StockTransfer", init=False)

    transfer_id: str = ""
    from_warehouse_id: str = ""
    to_warehouse_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "transfer_id": self.transfer_id,
                "from_warehouse_id": self.from_warehouse_id,
                "to_warehouse_id": self.to_warehouse_id,
            },
        )


@dataclass
class StockTransferCancelled(InventoryDomainEvent):
    """Raised when a pending transfer is cancelled."""

    event_type: str = field(default="StockTransferCancelled", init=False)
    aggregate_type: str = field(default="StockTransfer", init=False)

    transfer_id: str = ""
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {"transfer_id": self.transfer_id, "reason": self.reason},
        )


# ===========================================================================
# Adjustment Events (3)
# ===========================================================================


@dataclass
class InventoryAdjustmentSubmitted(InventoryDomainEvent):
    """Raised when an inventory adjustment is submitted for approval."""

    event_type: str = field(default="InventoryAdjustmentSubmitted", init=False)
    aggregate_type: str = field(default="InventoryAdjustment", init=False)

    adjustment_id: str = ""
    product_id: str = ""
    warehouse_id: str = ""
    qty_delta: str = "0"

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "adjustment_id": self.adjustment_id,
                "product_id": self.product_id,
                "warehouse_id": self.warehouse_id,
                "qty_delta": self.qty_delta,
            },
        )


@dataclass
class InventoryAdjustmentApproved(InventoryDomainEvent):
    """Raised when an adjustment is approved and applied to stock."""

    event_type: str = field(default="InventoryAdjustmentApproved", init=False)
    aggregate_type: str = field(default="InventoryAdjustment", init=False)

    adjustment_id: str = ""
    approved_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {"adjustment_id": self.adjustment_id, "approved_by": self.approved_by},
        )


@dataclass
class InventoryAdjustmentRejected(InventoryDomainEvent):
    """Raised when an adjustment is rejected."""

    event_type: str = field(default="InventoryAdjustmentRejected", init=False)
    aggregate_type: str = field(default="InventoryAdjustment", init=False)

    adjustment_id: str = ""
    rejected_by: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _merge(
            super().to_dict(),
            {
                "adjustment_id": self.adjustment_id,
                "rejected_by": self.rejected_by,
                "reason": self.reason,
            },
        )


# ===========================================================================
# Convenience: list of all event classes (for discovery/documentation)
# ===========================================================================

ALL_EVENT_TYPES: list[type[InventoryDomainEvent]] = [
    # Product (9)
    ProductCreated,
    ProductUpdated,
    ProductActivated,
    ProductDeactivated,
    ProductArchived,
    ProductDiscontinued,
    ProductVariantCreated,
    ProductVariantUpdated,
    BarcodeAssigned,
    # Stock (12)
    OpeningStockRecorded,
    StockIncreased,
    StockReduced,
    StockReserved,
    StockReservationReleased,
    StockAdjusted,
    StockTransferred,
    DamagedStockRecorded,
    ReturnedStockReceived,
    LowStockAlertRaised,
    ReorderSuggestionGenerated,
    OutOfStockDetected,
    # Warehouse (8)
    WarehouseCreated,
    WarehouseUpdated,
    WarehouseDeactivated,
    WarehouseArchived,
    StockTransferInitiated,
    StockTransferDispatched,
    StockTransferReceived,
    StockTransferCancelled,
    # Adjustment (3)
    InventoryAdjustmentSubmitted,
    InventoryAdjustmentApproved,
    InventoryAdjustmentRejected,
]


__all__ = [
    "ALL_EVENT_TYPES",
    "BarcodeAssigned",
    "DamagedStockRecorded",
    "InventoryAdjustmentApproved",
    "InventoryAdjustmentRejected",
    "InventoryAdjustmentSubmitted",
    "LowStockAlertRaised",
    "OpeningStockRecorded",
    "OutOfStockDetected",
    "ProductActivated",
    "ProductArchived",
    "ProductCreated",
    "ProductDeactivated",
    "ProductDiscontinued",
    "ProductUpdated",
    "ProductVariantCreated",
    "ProductVariantUpdated",
    "ReorderSuggestionGenerated",
    "ReturnedStockReceived",
    "StockAdjusted",
    "StockIncreased",
    "StockReduced",
    "StockReservationReleased",
    "StockReserved",
    "StockTransferCancelled",
    "StockTransferDispatched",
    "StockTransferInitiated",
    "StockTransferReceived",
    "StockTransferred",
    "WarehouseArchived",
    "WarehouseCreated",
    "WarehouseDeactivated",
    "WarehouseUpdated",
]
