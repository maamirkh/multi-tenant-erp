# Domain Events: Epic 7 – Sales Management

**Generated**: 2026-07-30
**Total Events**: 38
**Transport**: InProcessEventBus (same as Epics 5, 6)

---

## Event Base Structure

All events include:

| Field | Type | Description |
|-------|------|-------------|
| event_id | UUID | Unique event identifier |
| event_type | String | Dot-notation event name |
| event_version | Integer | Schema version (starts at 1) |
| company_id | UUID | Tenant identifier |
| occurred_at | DateTime | UTC timestamp |
| actor_id | UUID | User who triggered the event |

---

## Customer Events (9)

### customer.created
| Field | Type |
|-------|------|
| customer_id | UUID |
| company_id | UUID |
| customer_code | String |
| customer_type | Enum |

### customer.updated
| Field | Type |
|-------|------|
| customer_id | UUID |
| company_id | UUID |
| changed_fields | List[String] |

### customer.activated
| Field | Type |
|-------|------|
| customer_id | UUID |
| company_id | UUID |

### customer.deactivated
| Field | Type |
|-------|------|
| customer_id | UUID |
| company_id | UUID |

### customer.blocked
| Field | Type |
|-------|------|
| customer_id | UUID |
| company_id | UUID |
| reason | String |

### customer.unblocked
| Field | Type |
|-------|------|
| customer_id | UUID |
| company_id | UUID |

### customer.credit_limit_changed
| Field | Type |
|-------|------|
| customer_id | UUID |
| company_id | UUID |
| old_limit | Decimal |
| new_limit | Decimal |

### customer.credit_hold_placed
| Field | Type |
|-------|------|
| customer_id | UUID |
| company_id | UUID |

### customer.credit_hold_released
| Field | Type |
|-------|------|
| customer_id | UUID |
| company_id | UUID |

---

## Quotation Events (8)

### sales.quotation.created
| Field | Type |
|-------|------|
| quotation_id | UUID |
| company_id | UUID |
| customer_id | UUID |

### sales.quotation.sent
| Field | Type |
|-------|------|
| quotation_id | UUID |
| company_id | UUID |

### sales.quotation.accepted
| Field | Type |
|-------|------|
| quotation_id | UUID |
| company_id | UUID |

### sales.quotation.rejected
| Field | Type |
|-------|------|
| quotation_id | UUID |
| company_id | UUID |

### sales.quotation.converted
| Field | Type |
|-------|------|
| quotation_id | UUID |
| company_id | UUID |
| sales_order_id | UUID |

### sales.quotation.expired
| Field | Type |
|-------|------|
| quotation_id | UUID |
| company_id | UUID |

### sales.quotation.cancelled
| Field | Type |
|-------|------|
| quotation_id | UUID |
| company_id | UUID |

### sales.quotation.expiring_soon
| Field | Type |
|-------|------|
| quotation_id | UUID |
| company_id | UUID |
| expiry_date | Date |

---

## Sales Order Events (10)

### sales.order.created
| Field | Type |
|-------|------|
| order_id | UUID |
| company_id | UUID |
| customer_id | UUID |

### sales.order.submitted
| Field | Type |
|-------|------|
| order_id | UUID |
| company_id | UUID |
| total_amount | Decimal |

### sales.order.approved
| Field | Type |
|-------|------|
| order_id | UUID |
| company_id | UUID |
| approved_by | UUID |

### sales.order.rejected
| Field | Type |
|-------|------|
| order_id | UUID |
| company_id | UUID |
| rejected_by | UUID |
| reason | String |

### sales.order.cancelled
| Field | Type |
|-------|------|
| order_id | UUID |
| company_id | UUID |
| reason | String |

### sales.order.partially_delivered
| Field | Type |
|-------|------|
| order_id | UUID |
| company_id | UUID |

### sales.order.delivered
| Field | Type |
|-------|------|
| order_id | UUID |
| company_id | UUID |

### sales.order.invoiced
| Field | Type |
|-------|------|
| order_id | UUID |
| company_id | UUID |
| invoice_id | UUID |

### sales.order.closed
| Field | Type |
|-------|------|
| order_id | UUID |
| company_id | UUID |

### sales.order.credit_hold
| Field | Type |
|-------|------|
| order_id | UUID |
| company_id | UUID |
| customer_id | UUID |

---

## Delivery Events (4)

### sales.delivery.created
| Field | Type |
|-------|------|
| delivery_id | UUID |
| company_id | UUID |
| order_id | UUID |

### sales.delivery.dispatched
| Field | Type |
|-------|------|
| delivery_id | UUID |
| company_id | UUID |
| order_id | UUID |

### sales.delivery.delivered
| Field | Type |
|-------|------|
| delivery_id | UUID |
| company_id | UUID |

### sales.delivery.cancelled
| Field | Type |
|-------|------|
| delivery_id | UUID |
| company_id | UUID |

---

## Invoice Events (4)

### sales.invoice.created
| Field | Type |
|-------|------|
| invoice_id | UUID |
| company_id | UUID |
| customer_id | UUID |

### sales.invoice.issued
| Field | Type |
|-------|------|
| invoice_id | UUID |
| company_id | UUID |
| total_amount | Decimal |
| due_date | Date |

### sales.invoice.cancelled
| Field | Type |
|-------|------|
| invoice_id | UUID |
| company_id | UUID |

### sales.invoice.credit_note_issued
| Field | Type |
|-------|------|
| invoice_id | UUID |
| company_id | UUID |
| credit_note_amount | Decimal |

---

## Return Events (7)

### sales.return.created
| Field | Type |
|-------|------|
| return_id | UUID |
| company_id | UUID |
| customer_id | UUID |

### sales.return.submitted
| Field | Type |
|-------|------|
| return_id | UUID |
| company_id | UUID |

### sales.return.approved
| Field | Type |
|-------|------|
| return_id | UUID |
| company_id | UUID |

### sales.return.rejected
| Field | Type |
|-------|------|
| return_id | UUID |
| company_id | UUID |

### sales.return.received
| Field | Type |
|-------|------|
| return_id | UUID |
| company_id | UUID |

### sales.return.completed
| Field | Type |
|-------|------|
| return_id | UUID |
| company_id | UUID |
| resolution_type | Enum |

### sales.return.refund_ready
| Field | Type |
|-------|------|
| return_id | UUID |
| company_id | UUID |

---

## Cross-Module Integration Events

### Sales → Inventory (Epic 5)

All stock movements are created by `DeliveryService` and `ReturnService` calling the
Epic 5 `StockMovementService` directly (in-process, no network hop). The
`InProcessEventBus` is used for event notification — no async broker required.

| Trigger | Stock Movement Type | Epic 5 Direction | Details |
|---------|-------------------|------------------|---------|
| DN Created (DRAFT) | `SALES_RESERVATION` | Reserve stock | `quantity_reserved` incremented on `InventoryLocation`; `StockMovement` record created |
| DN Dispatched | `SALES_DISPATCH` | Deduct on-hand | `quantity_on_hand` decremented; reservation released; `sales.delivery.dispatched` event published |
| DN Cancelled | `SALES_RESERVATION_RELEASE` | Release reservation | `quantity_reserved` decremented; no on-hand change |
| Return Received (APPROVED → RECEIVED) | `SALES_RETURN_INBOUND` | Restock accepted items | `quantity_on_hand` incremented for each accepted return line |
| SO Cancelled (when APPROVED) | Release associated reservations | Release | All DN reservations for the order are released via `SALES_RESERVATION_RELEASE` |

**Reservation Lifecycle:**
```
Customer places SO → (approval) → SO APPROVED
  ↓ DN Created      → SALES_RESERVATION   (qty_reserved++)
  ↓ DN Dispatched   → SALES_DISPATCH      (qty_on_hand--, qty_reserved--)
  ↓ DN Delivered    → no stock change (delivery confirmation only)
  ↓ DN Cancelled    → SALES_RESERVATION_RELEASE (qty_reserved--)
  ↓ Return Received → SALES_RETURN_INBOUND (qty_on_hand++)
```

**Stock Movement Reference Fields (Epic 5 `StockMovement` model):**
| Field | Value |
|-------|-------|
| `movement_type` | `SALES_DISPATCH` / `SALES_RESERVATION` / `SALES_RETURN_INBOUND` |
| `reference_type` | `DELIVERY_NOTE` / `SALES_RETURN` |
| `reference_id` | UUID of DN or SalesReturn |
| `company_id` | Tenant UUID (isolation enforced) |

---

### Sales → Purchase (Epic 6)

| Trigger | Event | Action |
|---------|-------|--------|
| Stock below reorder level after dispatch | `purchase.reorder.suggested` | Epic 6 suggests a Purchase Requisition (via `InProcessEventBus`) |

**Integration Pattern:** Sales subscribes to no Purchase events directly.
Purchase monitors inventory levels independently. The `InProcessEventBus` allows
future replacement with RabbitMQ/Redis Streams without changing callers.

---

### Inventory → Sales

| Trigger | Action |
|---------|--------|
| Stock Received (GR posted in Epic 6) | Epic 5 publishes `inventory.stock.received`; Sales can subscribe to check backorder queue |
| Product Updated (price/description change) | Advisory only — open DRAFT quotations/orders are not auto-updated |

---

### Event Bus Pattern (all modules)

```python
# Publishing (same pattern across Epics 5, 6, 7)
from modules.sales.events import get_event_bus
get_event_bus().publish(SalesDomainEvent(...))

# Subscribing
from modules.sales.events import get_event_bus, set_event_bus, InProcessEventBus
bus = InProcessEventBus()
bus.subscribe("sales.delivery.dispatched", handle_dispatch)
set_event_bus(bus)

# Test isolation
from modules.sales.events import set_event_bus, InProcessEventBus
test_bus = InProcessEventBus()
captured = []
test_bus.subscribe("*", captured.append)
set_event_bus(test_bus)
# ... run service ...
assert any(e.event_type == "sales.delivery.dispatched" for e in captured)
set_event_bus(original_bus)
```

**Future broker swap:** Replace `InProcessEventBus` with `RabbitMQEventBus` or
`RedisStreamsEventBus` implementing the same `EventBus` interface. No callers change.
