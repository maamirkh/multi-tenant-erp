---
id: "0011"
title: Epic 6 Phase 7 Vendor Returns RMA
stage: green
date: 2026-07-27
surface: agent
model: claude-sonnet-4-6
feature: 006-purchase-management
branch: 006-purchase-management
user: shehla83
command: /sp.implement
labels: ["vendor-returns","rma","phase7","epic6","purchase-management","state-machine","atomic-dispatch","credit-note"]
links:
  spec: specs/006-purchase-management/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/purchase/models/vendor_return.py
  - backend/modules/purchase/events/rma_events.py
  - backend/modules/purchase/schemas/vendor_return.py
  - backend/migrations/versions/022_purchase_vendor_returns.py
  - backend/modules/purchase/repositories/vendor_return.py
  - backend/modules/purchase/services/rma_service.py
  - backend/modules/purchase/dependencies.py
  - backend/modules/purchase/router.py
  - backend/modules/purchase/models/__init__.py
  - frontend/src/app/(protected)/(purchase)/vendor-returns/page.tsx
  - frontend/src/app/(protected)/(purchase)/vendor-returns/new/page.tsx
  - frontend/src/app/(protected)/(purchase)/vendor-returns/[id]/page.tsx
  - backend/tests/unit/modules/purchase/test_rma_service.py
  - backend/tests/unit/modules/purchase/test_rma_events.py
  - backend/tests/integration/repositories/purchase/test_rma_transaction.py
  - backend/tests/integration/api/v1/purchase/test_rma_api.py
  - specs/006-purchase-management/tasks.md
tests:
  - backend/tests/unit/modules/purchase/test_rma_events.py (11 tests — PASSED)
  - backend/tests/unit/modules/purchase/test_rma_service.py (20 tests — PASSED)
  - backend/tests/integration/repositories/purchase/test_rma_transaction.py (11 tests — PASSED)
  - backend/tests/integration/api/v1/purchase/test_rma_api.py (12 tests — PASSED)
---

## Prompt

# =============================================================================
# DevSphere ERP
# Epic 6 – Purchase Management
# Phase 7 – "Vendor Returns (P1)"
# Enterprise Implementation Prompt
# =============================================================================

Implement Epic 6, Phase 7 "Vendor Returns (P1)" — tasks T169–T188.

Continue implementation strictly according to the approved documentation.

## Response snapshot

Implemented all 20 tasks (T169–T188) for Phase 7 Vendor Returns (RMA):

**Domain Models (T169–T170)**
- `VendorReturn`: rma_number (unique per company), status (DRAFT/SUBMITTED/APPROVED/DISPATCHED/COMPLETED/CANCELLED), gr_id (FK to CONFIRMED GR), supplier_id, initiated_by, reason_id, notes, replacement_po_id, credit_note_pending, dispatched_at, completed_at
- `ReturnLine`: return_id, gr_line_id, product_id, quantity_returned, reason_id, notes
- Indexes: gr_id, status, supplier_id; unique constraint on (company_id, rma_number)

**Migration (T171)**
- Alembic migration `022_purchase_vendor_returns.py` (revision 022, down_revision 021)

**Repository (T177)**
- `VendorReturnRepository`: list_for_company (status/gr_id/supplier_id filters), count_for_company, get_by_id_or_none, update_status
- `ReturnLineRepository`: list_for_rma, get_by_id_or_none, delete_all_for_rma (soft-delete)

**Service (T172–T176)**
- `RMAService`: create_rma (validates GR is CONFIRMED), _build_return_line (validates qty_returned ≤ accepted), submit_rma (DRAFT→SUBMITTED), approve_rma (SUBMITTED→APPROVED), dispatch_rma (APPROVED→DISPATCHED, atomic Epic 5 PURCHASE_RETURN_OUTBOUND stock movement), complete_rma (DISPATCHED→COMPLETED, credit_note_pending=True), cancel_rma (SUBMITTED/APPROVED→CANCELLED), link_replacement_po (state-neutral)
- State machine: DRAFT → SUBMITTED → APPROVED → DISPATCHED → COMPLETED; SUBMITTED/APPROVED → CANCELLED
- `_MUTABLE_STATUSES = {"DRAFT"}` — only DRAFT allows header/line edits
- `RMAImmutableError`, `RMAInvalidGRStatusError`, `RMAInvalidTransitionError`, `RMAReturnQuantityError`

**Domain Events (T178)**
- GoodsReturnInitiated, GoodsReturnApproved, GoodsReturned (with total_returned), GoodsReturnCompleted (with credit_note_pending)

**API Endpoints (T179) — 8 endpoints**
- GET/POST /vendor-returns
- GET/PUT /vendor-returns/{rma_id}
- PUT /vendor-returns/{rma_id}/lines
- POST /vendor-returns/{rma_id}/submit
- POST /vendor-returns/{rma_id}/approve
- POST /vendor-returns/{rma_id}/dispatch
- POST /vendor-returns/{rma_id}/complete
- POST /vendor-returns/{rma_id}/cancel

**Schemas (T180)**: VendorReturnCreate/Update/Read/ListRead, ReturnLineCreate/Read, RMAFilter

**Frontend (T181–T183)**
- RMA list page with status filter and color-coded badges
- RMA create form with GR ID input and dynamic return lines
- RMA detail with full workflow action buttons (Submit/Approve/Dispatch/Complete/Cancel)

**Tests (T184–T187)**
- 54 total tests: 11 unit (events) + 20 unit (service) + 11 repository integration + 12 API integration
- ALL 54 PASSED

**Docker Verification (T188)**
- 8 RMA endpoints visible in OpenAPI spec at /openapi.json

## Outcome

- ✅ Impact: Phase 7 Vendor Returns fully implemented — complete RMA lifecycle (DRAFT→SUBMITTED→APPROVED→DISPATCHED→COMPLETED), atomic stock deduction via Epic 5, credit_note_pending flag, 8 REST endpoints, 3 frontend pages
- 🧪 Tests: 54/54 passed (11 unit events, 20 unit service, 11 repository integration, 12 API integration)
- 📁 Files: 17 files created/modified
- 🔁 Next prompts: /sp.implement Phase 8 Purchase Costing (T189+)
- 🧠 Reflection: MagicMock fields for Optional[str] columns must be explicitly set to None (not left as MagicMock auto-attributes) to pass Pydantic model_validate(). Pattern: always explicitly set nullable string fields in test fixtures.

## Evaluation notes (flywheel)

- Failure modes observed: MagicMock auto-attribute for Optional[str] fields fails Pydantic validation (type=string_type error). Fix: explicitly set `rma.initiated_by = None`, `rma.reason_id = None`, `rma.notes = None` in MagicMock helpers.
- Graders run and results (PASS/FAIL): 54 pytest tests — PASS
- Prompt variant (if applicable): sp.implement Phase 7
- Next experiment (smallest change to try): Phase 8 Purchase Costing
