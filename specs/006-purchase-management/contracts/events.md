# Purchase Domain Events — Contract Reference

**Epic 6 — Purchase Management**
**Phase 10 — Integration Foundation**
**Generated**: 2026-07-29
**Spec Ref**: specs/006-purchase-management/spec.md §33 Domain Events
**Tasks**: T233, T237

---

## Overview

All purchase domain events are published via the `InProcessEventBus` singleton
(`modules.purchase.events.get_event_bus()`).  The bus is synchronous and
in-process.  A future message-broker adapter (RabbitMQ, Redis Streams) can
replace `InProcessEventBus` without changing any publisher or subscriber.

**Total events**: 33 across 6 aggregates.

---

## Base Envelope

Every event serialises to a dict with the following **base fields**:

| Field            | Type             | Description                                               |
|------------------|------------------|-----------------------------------------------------------|
| `event_id`       | string (UUID4)   | Unique occurrence identifier — use for idempotency checks |
| `event_type`     | string           | Dot-separated event name (see per-event tables below)     |
| `aggregate_type` | string           | Domain aggregate class name (e.g. `"Supplier"`)           |
| `aggregate_id`   | string (UUID4)   | ID of the entity that produced the event                  |
| `company_id`     | string (UUID4)   | Tenant identifier — always present                        |
| `occurred_at`    | string (ISO8601) | UTC timestamp                                             |
| `actor_id`       | string\|null     | User UUID who triggered the action, or null for system    |
| `correlation_id` | string\|null     | Optional trace / request correlation token                |

---

## Supplier Events (9)

Publisher: `modules.purchase.services.supplier_service.SupplierService`

### `supplier.created`

Published when a new supplier record is created (status = DRAFT).

| Extra Field     | Type   | Description              |
|-----------------|--------|--------------------------|
| `supplier_code` | string | Unique supplier code      |
| `legal_name`    | string | Legal business name       |

### `supplier.updated`

Published when mutable supplier fields are updated.

| Extra Field      | Type           | Description                          |
|------------------|----------------|--------------------------------------|
| `changed_fields` | list\[string\] | Names of fields that were changed     |

### `supplier.activated`

Published when supplier transitions to ACTIVE (from DRAFT or INACTIVE).

| Extra Field       | Type   | Description           |
|-------------------|--------|-----------------------|
| `previous_status` | string | Status before change  |

### `supplier.deactivated`

Published when ACTIVE → INACTIVE.

| Extra Field | Type         | Description                      |
|-------------|--------------|----------------------------------|
| `reason`    | string\|null | Optional reason for deactivation |

### `supplier.blocked`

Published when supplier is placed under a compliance or dispute block.

| Extra Field | Type   | Description         |
|-------------|--------|---------------------|
| `reason`    | string | Reason for blocking |

### `supplier.reactivated`

Published when a BLOCKED or INACTIVE supplier returns to ACTIVE.

| Extra Field       | Type         | Description                      |
|-------------------|--------------|----------------------------------|
| `previous_status` | string       | `"BLOCKED"` or `"INACTIVE"`      |
| `reason`          | string\|null | Optional reason for reactivation |

### `supplier.archived`

Published when supplier is permanently archived (ARCHIVED status).

| Extra Field       | Type   | Description          |
|-------------------|--------|----------------------|
| `previous_status` | string | Status before archive |

### `supplier.rating_updated`

Published when a supplier's composite rating score is recomputed or manually overridden.

| Extra Field          | Type    | Description                                |
|----------------------|---------|--------------------------------------------|
| `composite_score`    | string  | Decimal rating score (e.g. `"4.20"`)       |
| `gr_count_window`    | integer | Number of GRs used for score computation   |
| `is_manual_override` | boolean | True if manually overridden by a manager   |

### `supplier.preferred_designated`

Published when a supplier's preferred flag is toggled.

| Extra Field          | Type    | Description                |
|----------------------|---------|----------------------------|
| `is_preferred`       | boolean | New preferred flag value   |
| `previous_preferred` | boolean | Previous preferred flag    |

---

## Purchase Request Events (6)

Publisher: `modules.purchase.services.pr_service.PurchaseRequestService`

### `purchase_request.created`

Published when a PR is created in DRAFT status.

| Extra Field     | Type         | Description                          |
|-----------------|--------------|--------------------------------------|
| `pr_number`     | string       | System-assigned PR number            |
| `title`         | string       | PR title / description               |
| `requestor_id`  | string       | UUID of the requesting user          |
| `department`    | string\|null | Department code (optional)           |

### `purchase_request.submitted`

Published when a DRAFT PR is submitted for approval.

| Extra Field    | Type   | Description                 |
|----------------|--------|-----------------------------|
| `pr_number`    | string | PR number                   |
| `requestor_id` | string | UUID of the requesting user |

### `purchase_request.approved`

Published when a PR is fully approved (all levels approved or auto-approved).

| Extra Field    | Type    | Description                                |
|----------------|---------|--------------------------------------------|
| `pr_number`    | string  | PR number                                  |
| `auto_approved`| boolean | True if approval was auto-bypassed         |

### `purchase_request.rejected`

Published when a PR is rejected by an approver.

| Extra Field        | Type   | Description                 |
|--------------------|--------|-----------------------------|
| `pr_number`        | string | PR number                   |
| `rejection_reason` | string | Mandatory rejection reason  |
| `rejected_by`      | string | UUID of the rejecting user  |

### `purchase_request.cancelled`

Published when a PR is cancelled.

| Extra Field           | Type         | Description               |
|-----------------------|--------------|---------------------------|
| `pr_number`           | string       | PR number                 |
| `cancellation_reason` | string\|null | Optional cancellation note |

### `purchase_request.converted_to_po`

Published when an approved PR is converted to a Purchase Order.

| Extra Field  | Type   | Description           |
|--------------|--------|-----------------------|
| `pr_number`  | string | PR number             |
| `po_id`      | string | UUID of the new PO    |
| `po_number`  | string | System PO number      |

---

## Purchase Order Events (7)

Publisher: `modules.purchase.services.po_service.POService`

### `purchase.po.submitted`

Published when a PO is submitted for approval (DRAFT → PENDING_APPROVAL).

| Extra Field     | Type   | Description                             |
|-----------------|--------|-----------------------------------------|
| `po_number`     | string | System-assigned PO number               |
| `supplier_id`   | string | UUID of the supplier                    |
| `total`         | string | Decimal total amount (e.g. `"1500.00"`) |
| `currency_code` | string | ISO 4217 currency code (default `"USD"`) |

### `purchase.po.approved`

Published when a PO is approved (PENDING_APPROVAL → APPROVED).

| Extra Field    | Type    | Description                           |
|----------------|---------|---------------------------------------|
| `po_number`    | string  | PO number                             |
| `supplier_id`  | string  | UUID of the supplier                  |
| `auto_approved`| boolean | True if auto-approved (no matrix rule) |

### `purchase.po.rejected`

Published when a PO is rejected by an approver.

| Extra Field        | Type   | Description                 |
|--------------------|--------|-----------------------------|
| `po_number`        | string | PO number                   |
| `rejection_reason` | string | Mandatory rejection reason  |
| `rejected_by`      | string | UUID of the rejecting user  |

### `purchase.po.amended`

Published when an approved PO enters amendment workflow.

| Extra Field        | Type    | Description                       |
|--------------------|---------|-----------------------------------|
| `po_number`        | string  | PO number                         |
| `amendment_number` | integer | Sequential amendment counter      |
| `reason`           | string  | Reason for amendment              |

### `purchase.po.cancelled`

Published when a PO is cancelled.

| Extra Field           | Type         | Description               |
|-----------------------|--------------|---------------------------|
| `po_number`           | string       | PO number                 |
| `cancellation_reason` | string\|null | Optional cancellation note |

### `purchase.po.closed`

Published when a PO is closed (manually or after all goods received).

| Extra Field                  | Type   | Description                              |
|------------------------------|--------|------------------------------------------|
| `po_number`                  | string | PO number                                |
| `final_status_before_close`  | string | PO status immediately before closing     |

### `purchase.po.fully_received`

Published when all PO lines have been fully received.

| Extra Field   | Type   | Description          |
|---------------|--------|----------------------|
| `po_number`   | string | PO number            |
| `supplier_id` | string | UUID of the supplier |

---

## Goods Receipt Events (4)

Publisher: `modules.purchase.services.gr_service.GRService`

### `purchase.gr.confirmed`

Published when a Goods Receipt is confirmed (DRAFT → CONFIRMED).

| Extra Field      | Type   | Description                               |
|------------------|--------|-------------------------------------------|
| `gr_number`      | string | System GR number                          |
| `po_id`          | string | UUID of the source PO                     |
| `supplier_id`    | string | UUID of the supplier                      |
| `total_received` | string | Total quantity received (decimal string)   |

### `purchase.gr.goods_rejected`

Published when one or more GR lines have rejection quantity > 0.

| Extra Field      | Type   | Description                               |
|------------------|--------|-------------------------------------------|
| `gr_number`      | string | GR number                                 |
| `po_id`          | string | UUID of the source PO                     |
| `supplier_id`    | string | UUID of the supplier                      |
| `total_rejected` | string | Total quantity rejected (decimal string)   |

### `purchase.gr.partially_received`

Published when one or more GR lines received less than the open quantity.

| Extra Field   | Type   | Description            |
|---------------|--------|------------------------|
| `gr_number`   | string | GR number              |
| `po_id`       | string | UUID of the source PO  |
| `supplier_id` | string | UUID of the supplier   |

### `purchase.gr.over_receipt`

Published when one or more GR lines received more than the open quantity.

| Extra Field           | Type    | Description                           |
|-----------------------|---------|---------------------------------------|
| `gr_number`           | string  | GR number                             |
| `po_id`               | string  | UUID of the source PO                 |
| `supplier_id`         | string  | UUID of the supplier                  |
| `over_received_lines` | integer | Number of lines with over-receipt     |

---

## Vendor Return (RMA) Events (4)

Publisher: `modules.purchase.services.rma_service.RMAService`

### `purchase.rma.initiated`

Published when an RMA is submitted (DRAFT → SUBMITTED).

| Extra Field   | Type   | Description                  |
|---------------|--------|------------------------------|
| `rma_number`  | string | System RMA number            |
| `gr_id`       | string | UUID of the source GR        |
| `supplier_id` | string | UUID of the supplier         |

### `purchase.rma.approved`

Published when an RMA is approved (SUBMITTED → APPROVED).

| Extra Field   | Type   | Description           |
|---------------|--------|-----------------------|
| `rma_number`  | string | RMA number            |
| `gr_id`       | string | UUID of the source GR |
| `supplier_id` | string | UUID of the supplier  |

### `purchase.rma.dispatched`

Published when goods are dispatched back to the supplier (APPROVED → DISPATCHED).
At this point the Epic 5 `PURCHASE_RETURN_OUTBOUND` stock movement has been created.

| Extra Field      | Type   | Description                              |
|------------------|--------|------------------------------------------|
| `rma_number`     | string | RMA number                               |
| `gr_id`          | string | UUID of the source GR                    |
| `supplier_id`    | string | UUID of the supplier                     |
| `total_returned` | string | Total quantity returned (decimal string)  |

### `purchase.rma.completed`

Published when an RMA is completed (DISPATCHED → COMPLETED). `credit_note_pending`
is set to `True` on the VendorReturn at this point.

| Extra Field          | Type    | Description                              |
|----------------------|---------|------------------------------------------|
| `rma_number`         | string  | RMA number                               |
| `gr_id`              | string  | UUID of the source GR                    |
| `supplier_id`        | string  | UUID of the supplier                     |
| `credit_note_pending`| boolean | Always `true` — signals AP for credit    |

---

## Purchase Costing Events (3)

Publisher: `modules.purchase.services.cost_service.PurchaseCostService`

### `purchase.cost.recorded`

Published when a `PurchaseCostEntry` is created on GR confirmation.

| Extra Field       | Type   | Description                             |
|-------------------|--------|-----------------------------------------|
| `gr_id`           | string | UUID of the confirmed GR                |
| `po_id`           | string | UUID of the source PO                   |
| `supplier_id`     | string | UUID of the supplier                    |
| `subtotal`        | string | Goods subtotal (decimal string)         |
| `total_charges`   | string | Sum of additional charges               |
| `total_discounts` | string | Sum of discounts                        |
| `tax_amount`      | string | Tax amount                              |
| `total`           | string | Grand total                             |

### `purchase.cost.ppv_alert`

Published when a GR line's Purchase Price Variance (PPV%) exceeds the configured
threshold (requires `purchase.ppv_alerts` feature flag enabled).

| Extra Field         | Type   | Description                             |
|---------------------|--------|-----------------------------------------|
| `gr_id`             | string | UUID of the GR                          |
| `gr_line_id`        | string | UUID of the GR line with PPV alert      |
| `po_id`             | string | UUID of the source PO                   |
| `product_id`        | string | UUID of the product (empty if not set)  |
| `ppv_amount`        | string | Absolute PPV amount (decimal string)    |
| `ppv_percentage`    | string | PPV as percentage (4dp decimal string)  |
| `threshold_percent` | string | Configured alert threshold              |

### `purchase.cost.charge_recorded`

Published when a `POAdditionalCharge` is added or updated on a PO.

| Extra Field   | Type   | Description                                       |
|---------------|--------|---------------------------------------------------|
| `po_id`       | string | UUID of the PO                                    |
| `charge_type` | string | Charge category (e.g. `FREIGHT`, `HANDLING`)      |
| `amount`      | string | Charge amount (decimal string)                    |
| `description` | string | Optional description                              |

---

## Epic 5 Integration Contract

**Feature flag**: `purchase.gr_barcode_scan`

When `purchase.gr_barcode_scan` is enabled, the purchase module proxies
barcode scan requests to the Epic 5 Inventory barcode API:

```
GET /companies/{company_id}/purchase/goods-receipts/barcode/{barcode}
```

**Upstream Inventory endpoint** (Epic 5):

```
GET /companies/{company_id}/inventory/products/barcode/{barcode}
```

**Response shape** (when wired):
```json
{
  "product_id": "<uuid>",
  "sku": "PROD-001",
  "barcode": "1234567890123",
  "name": "Product Name",
  "unit_of_measure": "EA"
}
```

**Current status**: Endpoint returns HTTP 501 (stub) until the Inventory
integration is formally wired in a future phase. The feature flag must be
enabled per-company to activate the stub endpoint.

---

## Subscribing to Events

```python
from modules.purchase.events import get_event_bus

def on_supplier_created(event):
    # event.to_dict() returns the full serialisable payload
    print(event.event_type, event.aggregate_id)

get_event_bus().subscribe("supplier.created", on_supplier_created)
# or subscribe to all events:
get_event_bus().subscribe("*", on_supplier_created)
```

Handlers that raise exceptions are **caught and logged** — they do not
propagate to the publisher so a faulty subscriber cannot break the
primary business operation.

---

## Event Count Summary

| Aggregate        | Count | Event Types                                                                         |
|------------------|-------|-------------------------------------------------------------------------------------|
| Supplier         | 9     | created, updated, activated, deactivated, blocked, reactivated, archived, rating_updated, preferred_designated |
| Purchase Request | 6     | created, submitted, approved, rejected, cancelled, converted_to_po                  |
| Purchase Order   | 7     | submitted, approved, rejected, amended, cancelled, closed, fully_received            |
| Goods Receipt    | 4     | confirmed, goods_rejected, partially_received, over_receipt                         |
| Vendor Return    | 4     | initiated, approved, dispatched, completed                                          |
| Purchase Costing | 3     | recorded, ppv_alert, charge_recorded                                                |
| **Total**        | **33**|                                                                                     |
