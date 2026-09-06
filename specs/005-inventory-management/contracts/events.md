# Inventory Domain Events — Contract Reference

**Epic**: 005 – Inventory Management
**Phase**: 10 – Integration Foundation & Domain Events
**Version**: 1.0
**Spec ref**: spec.md §31 Domain Events

---

## Overview

All inventory domain events inherit from `InventoryDomainEvent` and are published
via the in-process event bus (`modules.inventory.events.InProcessEventBus`).

Events carry a stable, serialisable payload and can be consumed by any registered
handler within the same process.  Future phases may forward events to an external
message broker (Kafka, RabbitMQ) without changing the event schema.

---

## Base Fields (all events)

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | UUID | Unique identifier for this event instance |
| `event_type` | str | Class name (set automatically, immutable) |
| `aggregate_type` | str | Aggregate root name (set automatically) |
| `aggregate_id` | UUID | ID of the owning aggregate |
| `company_id` | UUID | Tenant identifier — always present |
| `occurred_at` | str | ISO-8601 UTC timestamp |
| `actor_id` | UUID \| None | User who triggered the action, if known |
| `correlation_id` | str \| None | Optional correlation/request ID |

---

## Serialisation

Every event exposes `to_dict() -> dict` which returns all base + payload fields.
The dict is JSON-serialisable (UUIDs are cast to `str`).

```python
import json
event_dict = event.to_dict()
json_str   = json.dumps(event_dict)   # round-trip safe
```

---

## Product Events

### `ProductCreated`

Raised when a new product is created.

**Aggregate type**: `Product`

| Field | Type |
|-------|------|
| `product_code` | str |
| `product_name` | str |
| `product_type` | str |
| `category_id` | str \| None |
| `brand_id` | str \| None |

---

### `ProductUpdated`

Raised when product fields are modified.

**Aggregate type**: `Product`

| Field | Type |
|-------|------|
| `changed_fields` | list[str] |

---

### `ProductActivated`

Raised when a product transitions to ACTIVE status.

**Aggregate type**: `Product`

| Field | Type |
|-------|------|
| `product_code` | str |
| `previous_status` | str |

---

### `ProductDeactivated`

Raised when a product is deactivated.

**Aggregate type**: `Product`

| Field | Type |
|-------|------|
| `product_code` | str |
| `reason` | str \| None |

---

### `ProductArchived`

Raised when a product is archived.

**Aggregate type**: `Product`

| Field | Type |
|-------|------|
| `product_code` | str |
| `previous_status` | str |

---

### `ProductDiscontinued`

Raised when a product is discontinued.

**Aggregate type**: `Product`

| Field | Type |
|-------|------|
| `product_code` | str |

---

### `ProductVariantCreated`

Raised when a variant is added to a product.

**Aggregate type**: `Product`

| Field | Type |
|-------|------|
| `variant_id` | str |
| `variant_code` | str |
| `product_code` | str |

---

### `ProductVariantUpdated`

Raised when variant attributes are modified.

**Aggregate type**: `Product`

| Field | Type |
|-------|------|
| `variant_id` | str |
| `changed_fields` | list[str] |

---

### `BarcodeAssigned`

Raised when a barcode is attached to a product or variant.

**Aggregate type**: `Product`

| Field | Type |
|-------|------|
| `barcode_value` | str |
| `barcode_type` | str |
| `variant_id` | str \| None |

---

## Stock Events

### `OpeningStockRecorded`

Raised when opening stock is set for a product.

**Aggregate type**: `StockPosition`

| Field | Type |
|-------|------|
| `product_id` | str |
| `warehouse_id` | str |
| `quantity` | str (Decimal) |
| `unit_cost` | str (Decimal) |

---

### `StockIncreased`

Raised on any inbound stock movement (purchase, return, etc.).

**Aggregate type**: `StockPosition`

| Field | Type |
|-------|------|
| `product_id` | str |
| `warehouse_id` | str |
| `quantity` | str (Decimal) |
| `movement_type` | str |
| `reference_id` | str \| None |

---

### `StockReduced`

Raised on any outbound stock movement (sale, damage write-off, etc.).

**Aggregate type**: `StockPosition`

| Field | Type |
|-------|------|
| `product_id` | str |
| `warehouse_id` | str |
| `quantity` | str (Decimal) |
| `movement_type` | str |
| `reference_id` | str \| None |

---

### `StockReserved`

Raised when stock is reserved for an order.

**Aggregate type**: `StockPosition`

| Field | Type |
|-------|------|
| `product_id` | str |
| `warehouse_id` | str |
| `reserved_quantity` | str (Decimal) |
| `reservation_reference` | str \| None |

---

### `StockReservationReleased`

Raised when a stock reservation is cancelled or fulfilled.

**Aggregate type**: `StockPosition`

| Field | Type |
|-------|------|
| `product_id` | str |
| `warehouse_id` | str |
| `released_quantity` | str (Decimal) |
| `reservation_reference` | str \| None |

---

### `StockAdjusted`

Raised after an inventory adjustment is applied.

**Aggregate type**: `StockPosition`

| Field | Type |
|-------|------|
| `product_id` | str |
| `warehouse_id` | str |
| `adjustment_qty` | str (Decimal) |
| `adjustment_id` | str |
| `reason_code` | str \| None |

---

### `StockTransferred`

Raised when stock moves between warehouses.

**Aggregate type**: `StockPosition`

| Field | Type |
|-------|------|
| `product_id` | str |
| `from_warehouse_id` | str |
| `to_warehouse_id` | str |
| `quantity` | str (Decimal) |
| `transfer_id` | str |

---

### `DamagedStockRecorded`

Raised when stock is written off as damaged.

**Aggregate type**: `StockPosition`

| Field | Type |
|-------|------|
| `product_id` | str |
| `warehouse_id` | str |
| `quantity` | str (Decimal) |
| `reason_code` | str \| None |

---

### `ReturnedStockReceived`

Raised when returned goods are received back into stock.

**Aggregate type**: `StockPosition`

| Field | Type |
|-------|------|
| `product_id` | str |
| `warehouse_id` | str |
| `quantity` | str (Decimal) |
| `source_reference` | str \| None |

---

### `LowStockAlertRaised`

Raised when stock falls below the minimum threshold.

**Aggregate type**: `StockPosition`

| Field | Type |
|-------|------|
| `product_id` | str |
| `warehouse_id` | str |
| `current_qty` | str (Decimal) |
| `minimum_stock` | str (Decimal) |
| `alert_id` | str |

---

### `ReorderSuggestionGenerated`

Raised when the system creates a reorder suggestion.

**Aggregate type**: `StockPosition`

| Field | Type |
|-------|------|
| `product_id` | str |
| `warehouse_id` | str |
| `suggested_qty` | str (Decimal) |
| `suggestion_id` | str |

---

### `OutOfStockDetected`

Raised when `qty_on_hand` reaches zero or below.

**Aggregate type**: `StockPosition`

| Field | Type |
|-------|------|
| `product_id` | str |
| `warehouse_id` | str |

---

## Warehouse Events

### `WarehouseCreated`

Raised when a new warehouse is provisioned.

**Aggregate type**: `Warehouse`

| Field | Type |
|-------|------|
| `warehouse_code` | str |
| `warehouse_name` | str |

---

### `WarehouseUpdated`

Raised when warehouse details are modified.

**Aggregate type**: `Warehouse`

| Field | Type |
|-------|------|
| `changed_fields` | list[str] |

---

### `WarehouseDeactivated`

Raised when a warehouse is deactivated.

**Aggregate type**: `Warehouse`

| Field | Type |
|-------|------|
| `warehouse_code` | str |

---

### `WarehouseArchived`

Raised when a warehouse is archived.

**Aggregate type**: `Warehouse`

| Field | Type |
|-------|------|
| `warehouse_code` | str |

---

## Stock Transfer Events

### `StockTransferInitiated`

Raised when a warehouse-to-warehouse transfer is created.

**Aggregate type**: `StockTransfer`

| Field | Type |
|-------|------|
| `transfer_id` | str |
| `from_warehouse_id` | str |
| `to_warehouse_id` | str |

---

### `StockTransferDispatched`

Raised when goods leave the source warehouse.

**Aggregate type**: `StockTransfer`

| Field | Type |
|-------|------|
| `transfer_id` | str |
| `from_warehouse_id` | str |
| `to_warehouse_id` | str |

---

### `StockTransferReceived`

Raised when goods arrive at the destination warehouse.

**Aggregate type**: `StockTransfer`

| Field | Type |
|-------|------|
| `transfer_id` | str |
| `from_warehouse_id` | str |
| `to_warehouse_id` | str |

---

### `StockTransferCancelled`

Raised when a transfer is cancelled before completion.

**Aggregate type**: `StockTransfer`

| Field | Type |
|-------|------|
| `transfer_id` | str |
| `reason` | str \| None |

---

## Inventory Adjustment Events

### `InventoryAdjustmentSubmitted`

Raised when an adjustment is submitted (pending approval or auto-approved).

**Aggregate type**: `InventoryAdjustment`

| Field | Type |
|-------|------|
| `adjustment_id` | str |
| `product_id` | str |
| `warehouse_id` | str |
| `qty_delta` | str (Decimal) |

---

### `InventoryAdjustmentApproved`

Raised when an adjustment is approved and applied.

**Aggregate type**: `InventoryAdjustment`

| Field | Type |
|-------|------|
| `adjustment_id` | str |
| `approved_by` | str |

---

### `InventoryAdjustmentRejected`

Raised when an adjustment is rejected.

**Aggregate type**: `InventoryAdjustment`

| Field | Type |
|-------|------|
| `adjustment_id` | str |
| `rejected_by` | str |
| `reason` | str \| None |

---

## Event Bus

```python
from modules.inventory.events import get_event_bus

bus = get_event_bus()

# Subscribe
@bus.subscribe("ProductCreated")
def on_product_created(event: ProductCreated) -> None:
    ...

# Publish (done internally by services)
bus.publish(ProductCreated(...))
```

Handlers are called synchronously in the publishing thread.  Any exception in a
handler is logged but does not abort the service operation.

---

## Event Summary

| Domain | Events |
|--------|--------|
| Product | `ProductCreated`, `ProductUpdated`, `ProductActivated`, `ProductDeactivated`, `ProductArchived`, `ProductDiscontinued`, `ProductVariantCreated`, `ProductVariantUpdated`, `BarcodeAssigned` |
| Stock | `OpeningStockRecorded`, `StockIncreased`, `StockReduced`, `StockReserved`, `StockReservationReleased`, `StockAdjusted`, `StockTransferred`, `DamagedStockRecorded`, `ReturnedStockReceived`, `LowStockAlertRaised`, `ReorderSuggestionGenerated`, `OutOfStockDetected` |
| Warehouse | `WarehouseCreated`, `WarehouseUpdated`, `WarehouseDeactivated`, `WarehouseArchived` |
| Stock Transfer | `StockTransferInitiated`, `StockTransferDispatched`, `StockTransferReceived`, `StockTransferCancelled` |
| Adjustment | `InventoryAdjustmentSubmitted`, `InventoryAdjustmentApproved`, `InventoryAdjustmentRejected` |

**Total**: 32 event types
