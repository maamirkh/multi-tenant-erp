---
id: "0008"
title: Epic 6 Phase 4 Purchase Requests Implementation
stage: green
date: 2026-07-27
surface: agent
model: claude-sonnet-4-6
feature: 006-purchase-management
branch: 005-inventory-management
user: shehla83
command: sp.implement
labels: ["purchase-requests","phase4","purchase-management","epic6","fastapi","sqlalchemy","state-machine"]
links:
  spec: specs/006-purchase-management/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/purchase/models/purchase_request.py
  - backend/migrations/versions/019_purchase_requests.py
  - backend/modules/purchase/repositories/purchase_request.py
  - backend/modules/purchase/services/pr_service.py
  - backend/modules/purchase/schemas/purchase_request.py
  - backend/modules/purchase/events/pr_events.py
  - backend/modules/purchase/dependencies.py
  - backend/modules/purchase/router.py
  - backend/modules/purchase/models/__init__.py
  - backend/tests/unit/modules/purchase/test_pr_service.py
  - backend/tests/unit/modules/purchase/test_pr_events.py
  - backend/tests/unit/modules/purchase/test_pr_feature_flags.py
  - backend/tests/integration/repositories/purchase/test_pr_repository.py
  - backend/tests/integration/api/v1/purchase/test_pr_api.py
  - frontend/src/app/(protected)/(purchase)/purchase-requests/page.tsx
  - frontend/src/app/(protected)/(purchase)/purchase-requests/new/page.tsx
  - frontend/src/app/(protected)/(purchase)/purchase-requests/[id]/page.tsx
  - specs/006-purchase-management/tasks.md
tests:
  - tests/unit/modules/purchase/test_pr_service.py — 23 passed
  - tests/unit/modules/purchase/test_pr_events.py — 15 passed
  - tests/unit/modules/purchase/test_pr_feature_flags.py — 10 passed
  - tests/integration/repositories/purchase/test_pr_repository.py — 17 passed
  - tests/integration/api/v1/purchase/test_pr_api.py — 20 passed
---

## Prompt

Continuing Epic 6 Phase 4 — "Purchase Requests (P1)" implementation.

Tasks T099–T119: Complete Purchase Request lifecycle including ORM models (PurchaseRequest,
PRLine, PurchaseOrder stub), Alembic migration 019, repositories, PRService with state machine/
invariants/submit/approve/reject/cancel/convert_to_po, Pydantic schemas, domain events,
20+ API endpoints, frontend pages, and full test suite.

## Response snapshot

Implemented all 21 Phase 4 tasks (T099–T119):

**Domain Models** (`models/purchase_request.py`): 3 ORM models.
- `PurchaseRequest`: 11 columns, CheckConstraint on status (6 values), UniqueConstraint(company_id, pr_number)
- `PRLine`: 9 columns, CheckConstraint quantity > 0, CheckConstraint estimated_unit_cost >= 0
- `PurchaseOrder` stub: minimal 4 columns for convert_to_po support; Phase 5 expands via ALTER TABLE

**Key fix**: TenantBaseModel uses `index=True` on company_id which auto-creates `ix_{table}_company_id` — explicit Index with same name causes SQLite "already exists" error. Removed duplicate company_id indexes from `__table_args__`.

**Migration** (`019_purchase_requests.py`): Creates purchase_requests, pr_lines, purchase_orders. Revision 019 (tasks.md says 018 but that was already taken by approval engine).

**Repositories** (`repositories/purchase_request.py`): PurchaseRequestRepository + PRLineRepository.
- PurchaseRequestRepository: CRUD, status/requestor filters, update_status, update_total_cost, set_converted_to_po
- PRLineRepository: list_for_pr, get_max_line_number, delete_all_for_pr

**Service** (`services/pr_service.py`): Full PRService with:
- `ALLOWED_TRANSITIONS` dict + `_assert_transition` for state machine validation
- `create_pr`: generates PR number via PurchaseSequenceService, creates PR + lines, publishes PurchaseRequestCreated
- `update_pr`: DRAFT-only guard
- `add_line/update_line/remove_line`: DRAFT-only, recalculates total
- `submit_pr`: validates has lines, transitions DRAFT→SUBMITTED, publishes PurchaseRequestSubmitted
- `approve_pr`: transitions to APPROVED (auto or manual), publishes PurchaseRequestApproved
- `reject_pr`: requires non-empty reason, publishes PurchaseRequestRejected
- `cancel_pr`: DRAFT/SUBMITTED only, publishes PurchaseRequestCancelled
- `convert_to_po`: APPROVED only, creates PO stub, sets converted_to_po_id, publishes PurchaseRequestConvertedToPO

**Events** (`events/pr_events.py`): 6 events with create() factories and to_dict().

**API** (`router.py`): 13 Phase 4 endpoints for PR CRUD, line management, submit/approve/reject/cancel/convert-to-po actions.

**DI** (`dependencies.py`): get_purchase_request_repo, get_pr_line_repo, get_pr_service factories.

**Tests**: 85/85 passing across all 5 test files. Full regression: 511/511 passing.

## Outcome

- ✅ Impact: Phase 4 Purchase Requests fully implemented and tested. 21/21 tasks complete.
- 🧪 Tests: 85 passed Phase 4 (23 unit + 10 feature flags + 15 events + 17 repo integration + 20 API integration); 511 total passing (no regressions)
- 📁 Files: 18 files created/modified
- 🔁 Next prompts: Phase 5 — Purchase Orders (T120+)
- 🧠 Reflection: TenantBaseModel's `index=True` auto-creates `ix_{table}_company_id` — never add an explicit Index with the same name. Migration numbering mismatch (tasks.md said 018, actual was 019) required adjustment.

## Evaluation notes (flywheel)

- Failure modes observed: Duplicate index name from TenantBaseModel's implicit `index=True` vs explicit `Index(...)`, fixture name `db` vs `db_session` mismatch
- Graders run and results (PASS/FAIL): pytest 85/85 PASS, full suite 511/511 PASS
- Prompt variant (if applicable): sp.implement Phase 4
- Next experiment (smallest change to try): Add migration numbering check to prevent task.md mismatch in future phases
