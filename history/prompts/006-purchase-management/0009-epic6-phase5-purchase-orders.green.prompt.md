---
id: "0009"
title: Epic 6 Phase 5 — Purchase Orders P1
stage: green
date: 2026-07-27
surface: agent
model: claude-sonnet-4-6
feature: 006-purchase-management
branch: 005-inventory-management
user: shehla83
command: /sp.implement
labels: ["purchase-orders","po-service","state-machine","domain-events","migration","tests","docker"]
links:
  spec: specs/006-purchase-management/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/purchase/models/purchase_order.py
  - backend/modules/purchase/schemas/purchase_order.py
  - backend/modules/purchase/services/po_service.py
  - backend/modules/purchase/repositories/purchase_order.py
  - backend/modules/purchase/events/po_events.py
  - backend/modules/purchase/router.py
  - backend/migrations/versions/019_purchase_requests.py
  - backend/migrations/versions/020_purchase_orders.py
  - backend/tests/unit/modules/purchase/test_po_service.py
  - backend/tests/unit/modules/purchase/test_po_events.py
  - backend/tests/unit/modules/purchase/test_po_business_rules.py
  - backend/tests/integration/repositories/purchase/test_po_repository.py
  - backend/tests/integration/api/v1/purchase/test_po_api.py
  - backend/tests/conftest.py
  - frontend/src/app/(protected)/(purchase)/purchase-orders/page.tsx
  - frontend/src/app/(protected)/(purchase)/purchase-orders/[id]/page.tsx
  - frontend/src/components/purchase/POStatusActions.tsx
  - specs/006-purchase-management/tasks.md
tests:
  - backend/tests/unit/modules/purchase/test_po_service.py (80 tests — PASS)
  - backend/tests/unit/modules/purchase/test_po_events.py (7 tests — PASS)
  - backend/tests/unit/modules/purchase/test_po_business_rules.py (9 tests — PASS)
  - backend/tests/integration/repositories/purchase/test_po_repository.py (34 tests — PASS)
  - backend/tests/integration/api/v1/purchase/test_po_api.py (27 tests — PASS)
---

## Prompt

/sp.implement

Epic 6 Phase 5 — "Purchase Orders (P1)"

Implement ONLY the tasks assigned to this phase (T120–T147).

## Response snapshot

Implemented all 28 Phase 5 tasks (T120–T147) for Purchase Orders:

**Domain Models** (`purchase_order.py`):
- `PurchaseOrder` ORM model: po_number, status, supplier_id, purchase_request_id, payment_terms_id, expected_delivery_date, supplier_reference, currency_code, subtotal, total_charges, total_discounts, tax_amount, total, notes, version (optimistic lock), branch_id reserved
- `POLine` ORM model: quantity_ordered, quantity_received, open_quantity, unit_cost, discount fields, line_total
- `POAdditionalCharge` ORM model: FREIGHT/HANDLING/INSURANCE/OTHER charge types
- `POAmendment` ORM model: amendment_number, reason, change_summary JSON, status

**Critical Bug Fixed**: REJECTED status was in the state machine but missing from the CheckConstraint — added to both ORM model and migration 019.

**State Machine** (ALLOWED_TRANSITIONS):
- DRAFT -> PENDING_APPROVAL, CANCELLED
- PENDING_APPROVAL -> APPROVED, REJECTED, CANCELLED
- APPROVED -> PARTIALLY_RECEIVED, FULLY_RECEIVED, CLOSED, CANCELLED (with has_confirmed_gr guard)
- REJECTED -> DRAFT
- PARTIALLY_RECEIVED -> FULLY_RECEIVED, CLOSED
- FULLY_RECEIVED -> CLOSED
- Terminal: CLOSED, CANCELLED -> []

**Services**: Full POService with create, update, submit, approve, reject, cancel, close, amend, add/update/remove line, add/update/remove charge, export_pdf, get_overdue, auto_update_status_on_gr.

**Repositories**: PurchaseOrderRepository, POLineRepository, POAdditionalChargeRepository, POAmendmentRepository (append-only).

**Migration 020**: Tables purchase_orders, po_lines, po_additional_charges, po_amendments with all indexes.

**Domain Events**: 7 events — PurchaseOrdered, PurchaseOrderApproved, PurchaseOrderRejected, PurchaseOrderAmended, PurchaseOrderCancelled, PurchaseOrderClosed, PurchaseOrderFullyReceived.

**API**: 15 REST endpoints including overdue query, PDF export, and full line/charge management.

**Frontend**: PO list page, PO create/edit form, POStatusActions component.

**Test Results**:
- 80 unit tests: PASS
- 7 event tests: PASS
- 9 business rule tests: PASS
- 34 repository integration tests: PASS
- 27 API integration tests: PASS

**Docker**: Build succeeded for both api and web images. Migration 020 applied (alembic_version=020). All Phase 5 tables confirmed in PostgreSQL. API health: status=healthy, database=ok.

**Fixes applied during testing**:
- Added REJECTED to CheckConstraint (critical — would cause IntegrityError in production)
- Added has_confirmed_gr field to POCancelRequest schema and wired to router
- Set JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440 in test conftest to survive WSL2 clock drift
- Fixed test_pr_service.py import: PurchaseOrder moved from purchase_request.py to purchase_order.py
- Fixed API test assertions: line management endpoints return StandardResponse[PurchaseOrderRead]
- Added all Decimal fields to _make_po() helper in business rule tests

## Outcome

- Impact: Full Purchase Order lifecycle (DRAFT -> CLOSED) operational with immutability enforcement, amendment workflow, cancel-blocked-by-GR guard, overdue detection, and PDF export
- Tests: 157 new tests — all passing (80 unit + 7 events + 9 business rules + 34 repo + 27 API)
- Files: 18 files created/modified across models, services, repos, events, schemas, router, migrations, tests, and frontend
- Next prompts: Phase 6 — Goods Receiving (T148+)
- Reflection: The REJECTED status missing from CheckConstraint was a production-critical bug caught only during integration testing — reinforces the value of running tests against the actual DB schema, not just mocks

## Evaluation notes (flywheel)

- Failure modes observed: (1) Ghost container 41753214c9f6 in Docker Desktop state caused docker compose up to fail; worked around by starting db without compose labels and manually connecting containers to network. (2) WSL2 clock drift caused JWT expiry in full test suite. (3) Missing REJECTED in CheckConstraint not caught by unit tests (mocked db).
- Graders run and results (PASS/FAIL): pytest unit PASS | pytest integration/repositories PASS | pytest integration/api PASS
- Prompt variant (if applicable): sp.implement Phase 5
- Next experiment: Add CheckConstraint validation in model-level tests to catch constraint/state-machine mismatches before integration tests
