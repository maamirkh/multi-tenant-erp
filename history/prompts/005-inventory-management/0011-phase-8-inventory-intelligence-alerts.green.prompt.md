---
id: "0011"
title: "phase-8-inventory-intelligence-alerts"
stage: green
date: 2026-07-22
surface: agent
model: claude-sonnet-4-6
feature: 005-inventory-management
branch: main
user: shehla83
command: sp.implement
labels: ["phase-8", "alerts", "reorder-rules", "low-stock", "intelligence", "inventory"]
links:
  spec: specs/005-inventory-management/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/inventory/models/alerts.py
  - backend/migrations/versions/013_inventory_alerts.py
  - backend/modules/inventory/repositories/alerts_repository.py
  - backend/modules/inventory/services/alert_service.py
  - backend/modules/inventory/services/stock_service.py
  - backend/modules/inventory/schemas/alerts.py
  - backend/modules/inventory/constants.py
  - backend/modules/inventory/models/__init__.py
  - backend/modules/inventory/dependencies.py
  - backend/modules/inventory/router.py
  - backend/tests/unit/modules/inventory/test_alert_entities.py
  - backend/tests/integration/api/v1/inventory/test_alerts_api.py
  - frontend/src/app/(protected)/(inventory)/inventory/alerts/page.tsx
  - frontend/src/app/(protected)/(inventory)/inventory/reorder-rules/page.tsx
  - frontend/src/app/(protected)/(inventory)/inventory/suggestions/page.tsx
  - specs/005-inventory-management/tasks.md
tests:
  - tests/unit/modules/inventory/test_alert_entities.py (unit, 12 tests)
  - tests/integration/api/v1/inventory/test_alerts_api.py (integration/API, 18 tests)
  - Full regression: 1637 passed
---

## Prompt

Epic 5 Phase 8 — Inventory Intelligence & Alerts implementation via `/sp.implement`.

## Response

### Completed Tasks (T214–T234)

**Models & Migration (T214–T219)**
- `LowStockAlert` with state machine OPEN→ACKNOWLEDGED→RESOLVED, partial unique index `uq_inv_alert_open_dedup WHERE status='OPEN'` (deduplication)
- `ReorderRule` with global/warehouse-specific rules (warehouse_id nullable)
- `ReorderSuggestion` auto-generated on LOW_STOCK breach when rule exists
- Added `sqlite_where=text("status = 'OPEN'")` alongside `postgresql_where` for test DB compatibility
- Migration 013 applied to production DB and test DB; alembic current = 013 (head)

**Repositories (T217 + T220)**
- `ReorderRuleRepository.get_for_product()` — warehouse-specific rules sorted before global ones
- `LowStockAlertRepository.get_open_alert()` — deduplication check for existing OPEN alert
- `ReorderSuggestionRepository.list_for_company()` — filterable by status/product

**AlertEvaluationService (T221–T224)**
- Non-raising `evaluate()` entry point — exceptions are caught/logged so alert errors never block stock writes
- Threshold priority: OUT_OF_STOCK > SAFETY_STOCK_BREACH > LOW_STOCK; OVERSTOCK gated by `inventory.overstock_alerts` flag (default disabled)
- Auto-resolves OPEN alerts when stock rises above threshold
- Creates `ReorderSuggestion` on LOW_STOCK if active rule exists (warehouse-specific first)
- Publishes `inventory.low_stock_alert_raised` / `inventory.out_of_stock_alert_raised` via `InProcessEventBus`
- `_is_flag_enabled()` checks DB override, falls back to `INVENTORY_FLAG_BY_KEY` defaults

**StockLedgerService integration (T222)**
- Added optional `alert_svc` parameter to `StockLedgerService.__init__`
- Hook called after every stock write: `record_opening_stock`, `record_adjustment`, `record_transfer_movement`
- All DI factories in `dependencies.py` updated to wire `AlertEvaluationService` into the ledger service

**API Endpoints (T225)**
- `POST/GET /reorder-rules` — CRUD with list/get/update/delete
- `GET /alerts` — filterable by status, type, product, warehouse
- `POST /alerts/{id}/acknowledge` — transitions OPEN→ACKNOWLEDGED
- `GET /suggestions` — list with status filter
- `POST /suggestions/{id}/acknowledge` — transitions PENDING→ACKNOWLEDGED

**Frontend Pages (T226–T228)**
- `inventory/alerts/page.tsx` — alert dashboard with type/status badges, acknowledge button
- `inventory/reorder-rules/page.tsx` — CRUD form, activate/deactivate, delete
- `inventory/suggestions/page.tsx` — list with status filter, acknowledge action

**Tests (T229–T233)**
- 12 unit tests: threshold detection, deduplication, auto-resolve, suggestion creation, error isolation
- 18 integration/API tests: CRUD for rules, alert lifecycle, tenant isolation, 401 checks, 409 conflict checks

**Key implementation notes**
- `sqlite_where=text(...)` added to partial unique index so SQLite test DB enforces the same constraint as PostgreSQL
- `CurrentUser.user_id` (not `.id`) used in acknowledge endpoint
- Product creation in tests uses DB direct insert (not API) to avoid UOM FK complexity

### Results
- 30 Phase 8 tests pass
- 1637 total tests pass (0 failures, regression clean)
- Docker: migration at head, models importable, health endpoint OK
- Tasks T214–T234 marked complete
- Phase 8 exit criteria all satisfied
