---
id: "0014"
title: Phase 7 Sales Returns Implementation
stage: green
date: 2026-08-04
surface: agent
model: claude-sonnet-4-6
feature: 007-sales-management
branch: 007-sales-management
user: shehla83
command: /sp.implement
labels: ["phase-7", "sales-returns", "rma", "state-machine", "inventory-restock", "resolution-types", "domain-events"]
links:
  spec: specs/007-sales-management/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/sales/models/sales_return.py
  - backend/modules/sales/events/return_events.py
  - backend/modules/sales/repositories/sales_return.py
  - backend/modules/sales/schemas/sales_return.py
  - backend/modules/sales/services/return_service.py
  - backend/migrations/versions/032_sales_returns.py
  - backend/modules/sales/dependencies.py
  - backend/modules/sales/models/__init__.py
  - backend/modules/sales/router.py
  - frontend/src/lib/api/sales.ts
  - frontend/src/app/(protected)/(sales)/returns/page.tsx
  - frontend/src/app/(protected)/(sales)/returns/[id]/page.tsx
  - backend/tests/unit/modules/sales/test_return_entity.py
  - backend/tests/integration/repositories/sales/test_return_generation.py
  - backend/tests/integration/api/v1/sales/test_return_api.py
  - specs/007-sales-management/tasks.md
tests:
  - tests/unit/modules/sales/test_return_entity.py (29 passed)
  - tests/integration/repositories/sales/test_return_generation.py (20 passed)
  - tests/integration/api/v1/sales/test_return_api.py (16 passed)
---

## Prompt

/sp.implement — Phase 7: Sales Returns (P1). Implement T184–T203 covering the complete Sales Return (RMA) lifecycle including ORM models, domain events, repositories, Pydantic schemas, service layer with state machine (DRAFT→PENDING_APPROVAL→APPROVED→RECEIVED→COMPLETED), inventory restock on receipt (Epic 5 ADJUSTMENT_IN), resolution types (CREDIT_NOTE/REPLACEMENT/REFUND_READINESS), Alembic migration, API endpoints, frontend pages/components, API client updates, and all tests.

## Response snapshot

Implemented Phase 7 "Sales Returns (P1)" end-to-end across 16 files:

**Backend:**
- `models/sales_return.py`: SalesReturn (state machine), ReturnLine (condition tracking, qty accepted/rejected) ORM models; table name `sales_return_lines` to avoid collision with purchase module's `return_lines`
- `events/return_events.py`: 7 domain events — ReturnCreated, ReturnSubmitted, ReturnApproved, ReturnRejected, ReturnReceived, ReturnCompleted, ReturnRefundReady
- `repositories/sales_return.py`: SalesReturnRepository (list with customer/status/order/resolution filters), ReturnLineRepository
- `schemas/sales_return.py`: Full Pydantic v2 schema set — ReturnLineCreate/Read, SalesReturnCreate/Read/ListItem/ListResponse, ReturnSubmitRequest, ReturnApproveRequest, ReturnRejectRequest, ReturnReceiveRequest (with ReturnLineReceiptItem), ReturnCompleteRequest
- `services/return_service.py`: ReturnService with gap-free numbering (SR- prefix), state machine, approval workflow inline, inventory restock via StockLedgerService.record_adjustment(ADJUSTMENT_IN) for accepted lines (best-effort), 3 resolution types, replacement SO stub
- `migrations/032_sales_returns.py`: Creates sales_returns and sales_return_lines tables with indexes
- Router: 8 new endpoints — list, create, get, submit, approve, reject, receive, complete, cancel, lines
- `dependencies.py`: `get_return_service` factory added

**Frontend:**
- `returns/page.tsx`: Return list with status filter and pagination
- `returns/[id]/page.tsx`: Return detail with header (status badge), submit/approve/reject/cancel actions, lines table, notes
- `sales.ts`: Full TypeScript API client — listSalesReturns, createSalesReturn, getSalesReturn, submitSalesReturn, approveSalesReturn, rejectSalesReturn, receiveSalesReturn, completeSalesReturn, cancelSalesReturn, listReturnLines

**Tests:**
- Unit: 29 tests — state machine, schema validators (quantity positive, condition enum, rejection reason non-empty)
- Integration: 20 tests — creation, sequential numbers, state machine, resolution types, list filtering, tenant isolation
- API: 16 tests — CRUD, lifecycle transitions, RBAC, tenant isolation

**Key fixes during implementation:**
- Table name collision: purchase module already uses `return_lines` for `VendorReturnLine`; renamed to `sales_return_lines`
- Duplicate index: `TenantBaseModel` auto-creates `ix_<tablename>_company_id` via `index=True`; removed explicit duplicate Index from `__table_args__`
- Unused `DateTime` import removed from sales_return.py

## Outcome

- ✅ Impact: Complete sales return lifecycle from DRAFT to terminal states; 65 new Phase 7 tests; all 113 Phase 6+7 tests passing
- 🧪 Tests: 65 passed (29 unit + 20 integration + 16 API); 0 failures
- 📁 Files: 16 files created/modified across backend models/services/router/tests and frontend pages/components/API client
- 🔁 Next prompts: Phase 8 (Sales Analytics/Reporting) or Phase 9 (Integration, Contracts & Import/Export)
- 🧠 Reflection: The purchase module's `return_lines` table name conflict was caught at test time, not at design time — always check for table name collisions across modules. `TenantBaseModel.company_id` with `index=True` automatically creates `ix_<tablename>_company_id`; do not duplicate this in `__table_args__`.

## Evaluation notes (flywheel)

- Failure modes observed: Table name collision (return_lines used by purchase module); duplicate index from TenantBaseModel auto-index; unused import causing ruff errors
- Graders run and results (PASS/FAIL): All 65 Phase 7 tests PASS; 113 total Phase 6+7 sales tests PASS
- Prompt variant (if applicable): /sp.implement continuation from Phase 6 session (resumed from context compaction)
- Next experiment: Add real inventory restock integration test with actual stock positions when Epic 5 stock service is fully wired in test DB
