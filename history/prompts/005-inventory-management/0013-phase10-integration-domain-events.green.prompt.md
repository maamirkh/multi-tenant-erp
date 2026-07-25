---
id: "0013"
title: "phase10-integration-domain-events"
stage: green
date: "2026-07-24"
surface: agent
model: claude-sonnet-4-6
feature: 005-inventory-management
branch: main
user: shehla83
command: sp.implement
labels: ["phase10", "domain-events", "scanner-lookup", "label-data", "openapi", "performance"]
links:
  spec: specs/005-inventory-management/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/inventory/domain_events.py
  - backend/modules/inventory/services/product_service.py
  - backend/modules/inventory/services/stock_service.py
  - backend/modules/inventory/services/warehouse_service.py
  - backend/modules/inventory/services/adjustment_service.py
  - backend/modules/inventory/services/transfer_service.py
  - backend/modules/inventory/services/alert_service.py
  - backend/modules/inventory/schemas/product.py
  - backend/modules/inventory/router.py
  - backend/modules/inventory/repositories/product_repository.py
  - backend/tests/unit/modules/inventory/test_domain_events.py
  - backend/tests/integration/api/v1/inventory/test_lookup_api.py
  - backend/tests/performance/inventory/__init__.py
  - backend/tests/performance/inventory/test_lookup_performance.py
  - specs/005-inventory-management/contracts/inventory-v1.json
  - specs/005-inventory-management/contracts/events.md
  - specs/005-inventory-management/tasks.md
tests:
  - "tests/unit/modules/inventory/test_domain_events.py — 196 passed (all 32 event types)"
  - "tests/integration/api/v1/inventory/test_lookup_api.py — 12 passed"
  - "tests/performance/inventory/test_lookup_performance.py — 3 passed (p95: barcode 42.9ms, SKU 35.9ms, label 44.5ms)"
  - "tests/unit/modules/inventory + tests/integration/api/v1/inventory — 774 passed"
---

## Prompt

Epic 5, Phase 10 — Integration Foundation & Domain Events implementation (T260–T269).

## Response

### Tasks Completed

**T260** — Created `backend/modules/inventory/domain_events.py` with 32 typed domain event dataclasses:
- Product (9): ProductCreated, ProductUpdated, ProductActivated, ProductDeactivated, ProductArchived, ProductDiscontinued, ProductVariantCreated, ProductVariantUpdated, BarcodeAssigned
- Stock (12): OpeningStockRecorded, StockIncreased, StockReduced, StockReserved, StockReservationReleased, StockAdjusted, StockTransferred, DamagedStockRecorded, ReturnedStockReceived, LowStockAlertRaised, ReorderSuggestionGenerated, OutOfStockDetected
- Warehouse (4): WarehouseCreated, WarehouseUpdated, WarehouseDeactivated, WarehouseArchived
- Transfer (4): StockTransferInitiated, StockTransferDispatched, StockTransferReceived, StockTransferCancelled
- Adjustment (3): InventoryAdjustmentSubmitted, InventoryAdjustmentApproved, InventoryAdjustmentRejected
- All implement `to_dict()` with JSON-serialisable payload; `event_type`/`aggregate_type` auto-set via `field(default=..., init=False)`

**T261** — Updated all 6 services to publish typed events:
- ProductService: 8 event types (create, update, status transitions, variant, barcode)
- StockLedgerService: 4 event types (opening, increase, reduce, out-of-stock)
- WarehouseService: 4 event types (create, update, status transitions)
- AdjustmentService: 3 event types (submit, approve, reject)
- TransferService: 4 event types (initiate, dispatch, receive, cancel)
- AlertService: 2 event types (low-stock, reorder suggestion)

**T262** — 196-test unit suite in `test_domain_events.py` covering all 32 event types: event_type correctness, aggregate_type, payload fields, JSON round-trip, unique event_id per instance.

**T263** — Added to `router.py`: `GET /companies/{company_id}/inventory/lookup/barcode/{barcode_value}` and `GET /companies/{company_id}/inventory/lookup/sku/{sku}` returning `LookupResult` with product + stock positions.

**T264** — Added to `router.py`: `GET /companies/{company_id}/inventory/products/{product_id}/label-data` returning `LabelData` (product_id, product_code, product_name, barcode_value, barcode_type, uom_code, uom_name).

**T265** — 12-test API integration suite covering: barcode found/not-found, SKU found/not-found/case-insensitive, label-data found/no-barcode/not-found, unauthenticated 401/403, and tenant isolation.

**T266** — Performance benchmark in `test_lookup_performance.py`: barcode p95=42.9ms, SKU p95=35.9ms, label-data p95=44.5ms (all < 100ms threshold).

**T267** — Generated `specs/005-inventory-management/contracts/inventory-v1.json` with 196 inventory OpenAPI paths from the running FastAPI app.

**T268** — Created `specs/005-inventory-management/contracts/events.md` documenting all 32 domain events with base fields, payload schemas, serialisation notes, and event bus usage.

**T269** — Docker CLI unavailable in WSL; equivalent verification via: app startup OK, 196 OpenAPI paths registered, 32 domain event classes loaded, all 774 inventory tests passing.

### Key Technical Decisions

- **Two-step barcode lookup**: Rewrote `ProductRepository.get_by_barcode()` to use two separate queries (barcode row → product by UUID) instead of a JOIN with `func.cast()`. This avoids a UUID format mismatch in SQLite tests where `Uuid(as_uuid=True)` stores 32-char hex but `PG_UUID(as_uuid=False)` stores 36-char strings with dashes.
- **Warm-up in performance tests**: Added 3 warm-up requests before the 20-sample measurement loop to eliminate cold-start bias on the first test after app startup.
- **Domain event field overrides**: Used `field(default="ClassName", init=False)` pattern in dataclasses to auto-set `event_type` and `aggregate_type` without requiring them as constructor parameters.
