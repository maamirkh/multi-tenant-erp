---
id: "0013"
title: Phase 6 Sales Invoicing Implementation
stage: green
date: 2026-08-03
surface: agent
model: claude-sonnet-4-6
feature: 007-sales-management
branch: 007-sales-management
user: shehla83
command: /sp.implement
labels: ["phase-6", "invoicing", "gap-free-numbering", "state-machine", "domain-events"]
links:
  spec: specs/007-sales-management/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/sales/models/invoice.py
  - backend/modules/sales/events/invoice_events.py
  - backend/modules/sales/repositories/invoice.py
  - backend/modules/sales/schemas/invoice.py
  - backend/modules/sales/services/invoice_service.py
  - backend/migrations/versions/031_sales_invoices.py
  - backend/modules/sales/dependencies.py
  - backend/modules/sales/models/__init__.py
  - backend/modules/sales/router.py
  - frontend/src/lib/api/sales.ts
  - frontend/src/app/(protected)/(sales)/invoices/page.tsx
  - frontend/src/app/(protected)/(sales)/invoices/[id]/page.tsx
  - frontend/src/components/sales/InvoiceActions.tsx
  - backend/tests/unit/modules/sales/test_invoice_entity.py
  - backend/tests/integration/repositories/sales/test_invoice_sequence.py
  - backend/tests/integration/repositories/sales/test_invoice_generation.py
  - backend/tests/integration/api/v1/sales/test_invoice_api.py
  - specs/007-sales-management/tasks.md
tests:
  - tests/unit/modules/sales/test_invoice_entity.py (31 passed)
  - tests/integration/repositories/sales/test_invoice_sequence.py (5 passed)
  - tests/integration/repositories/sales/test_invoice_generation.py (19 passed)
  - tests/integration/api/v1/sales/test_invoice_api.py (17 passed)
---

## Prompt

/sp.implement — Phase 6: Sales Invoicing (P1). Implement T158–T183 covering the complete Sales Invoice lifecycle including ORM models, domain events, repositories, Pydantic schemas, service layer with gap-free numbering (SalesSequenceService SELECT FOR UPDATE), Alembic migration, API endpoints, frontend pages/components, API client updates, and all tests.

## Response snapshot

Implemented Phase 6 "Sales Invoicing (P1)" end-to-end across 17 files:

**Backend:**
- `models/invoice.py`: SalesInvoice (DRAFT→ISSUED|CANCELLED; ISSUED→PAID|CREDIT_NOTE_ISSUED), InvoiceLine, InvoiceCharge ORM models with all required attributes and check constraints
- `events/invoice_events.py`: 4 domain events — InvoiceCreated, InvoiceIssued, InvoiceCancelled, InvoiceCreditNoteIssued
- `repositories/invoice.py`: SalesInvoiceRepository (list with customer/status/order/DN/date filters), InvoiceLineRepository, InvoiceChargeRepository
- `schemas/invoice.py`: Full Pydantic v2 schema set — create (3 modes), read, list, issue, credit-note request
- `services/invoice_service.py`: InvoiceService with gap-free numbering (SalesSequenceService), 3 creation modes (from DN, from SO, manual), state machine, due-date calculation, amount-in-words, SO status auto-update (DELIVERED→INVOICED), PDF export (feature-flagged)
- `migrations/031_sales_invoices.py`: Alembic migration creating sales_invoices, invoice_lines, invoice_charges with all indexes
- Router: 8 new endpoints — list, create, get, issue, cancel, credit-note, lines, charges, export
- `dependencies.py`: `get_invoice_service` factory added

**Frontend:**
- `invoices/page.tsx`: Invoice list with status filter and pagination
- `invoices/[id]/page.tsx`: Invoice detail with lines, charges, totals, amount-in-words
- `InvoiceActions.tsx`: Issue/cancel/credit-note confirmation dialogs
- `sales.ts`: Full TypeScript API client — listInvoices, createInvoice, getInvoice, issueInvoice, cancelInvoice, issueCreditNote, listInvoiceLines, listInvoiceCharges

**Tests:**
- Unit: 31 tests — state machine, amount_in_words, schema validators
- Sequence integration: 5 tests — gap-free sequential, independent per company, cancelled number retained
- Generation integration: 19 tests — manual creation, amounts, transitions, listing/filtering
- API integration: 17 tests — full CRUD, state transitions, RBAC, tenant isolation

**Key fixes during implementation:**
- Router paths were `/companies/{company_id}/invoices/...` — corrected to `/invoices/...` (prefix applied by router mount)
- `user.id` → `user.user_id` (CurrentUser attribute name)
- `create_test_user()` doesn't accept `company_id` kwarg
- Tenant isolation test: use company_b URL to access company_a's invoice (returns 404), not company_a URL

## Outcome

- ✅ Impact: Complete sales invoicing lifecycle from DRAFT to terminal states; 72 new tests; 655 total sales tests passing
- 🧪 Tests: 72 passed (31 unit + 5 sequence + 19 generation + 17 API); 0 failures
- 📁 Files: 17 files created/modified across backend models/services/router/tests and frontend pages/components/API client
- 🔁 Next prompts: Phase 7 (Sales Returns/RMA) or Phase 8 (Sales Analytics/Reporting)
- 🧠 Reflection: State machine gap-free numbering works correctly with SQLite test sessions. `CurrentUser.user_id` (not `.id`) is the correct attribute — must check interface before using. Router paths must not repeat the URL prefix already applied at mount time.

## Evaluation notes (flywheel)

- Failure modes observed: Duplicate `company_id` path param (router prefix + endpoint path); wrong `user.id` vs `user.user_id`; `create_test_user` kwarg mismatch; tenant isolation test using wrong company URL
- Graders run and results (PASS/FAIL): All 72 Phase 6 tests PASS; 655 total sales tests PASS
- Prompt variant (if applicable): /sp.implement continuation from Phase 5 session
- Next experiment: Add invoice PDF generation (real PDF, not placeholder) when `sales.invoice_pdf_export` flag is enabled
