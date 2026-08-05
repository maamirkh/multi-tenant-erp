---
id: "0007"
title: "Phase 1 Customer Master Implementation"
stage: green
date: 2026-08-01
surface: agent
model: claude-opus-4-6
feature: 007-sales-management
branch: 005-inventory-management
user: shehla83
command: /sp.implement
labels: ["customer-master","sales","phase1","implementation","tests"]
links:
  spec: specs/007-sales-management/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/sales/models/customer.py
  - backend/modules/sales/models/__init__.py
  - backend/modules/sales/events/customer_events.py
  - backend/modules/sales/repositories/customer.py
  - backend/modules/sales/schemas/customer.py
  - backend/modules/sales/services/customer_service.py
  - backend/modules/sales/services/customer_import_service.py
  - backend/modules/sales/services/customer_export_service.py
  - backend/modules/sales/dependencies.py
  - backend/modules/sales/router.py
  - backend/migrations/versions/026_sales_customers.py
  - frontend/src/app/(protected)/(sales)/customers/page.tsx
  - frontend/src/app/(protected)/(sales)/customers/new/page.tsx
  - frontend/src/app/(protected)/(sales)/customers/[id]/page.tsx
  - frontend/src/app/(protected)/(sales)/customers/import/page.tsx
  - frontend/src/components/sales/CustomerStatusActions.tsx
  - frontend/src/lib/api/sales.ts
  - backend/tests/unit/modules/sales/test_customer_events.py
  - backend/tests/unit/modules/sales/test_customer_service.py
  - backend/tests/integration/repositories/sales/test_customer_repositories.py
  - backend/tests/integration/api/v1/sales/test_customer_api.py
  - specs/007-sales-management/tasks.md
tests:
  - backend/tests/unit/modules/sales/test_customer_events.py (13 tests — PASS)
  - backend/tests/unit/modules/sales/test_customer_service.py (20 tests — PASS)
  - backend/tests/integration/repositories/sales/test_customer_repositories.py (14 tests — PASS)
  - backend/tests/integration/api/v1/sales/test_customer_api.py (14 tests — PASS)
---

## Prompt

/sp.implement — Epic 7 Sales Management Phase 1 "Customer Master (P1)". Implement all 30 tasks (T032–T061) from the approved tasks.md, maintaining compatibility with Epics 0–6 and following the Engineering Constitution.

## Response snapshot

Implemented Epic 7 Sales Management Phase 1 (Customer Master) — all 30 tasks T032–T061 complete.

**Backend:**
- 5 ORM models: Customer (with TSVECTOR FTS, JSONB custom_fields, optimistic locking), CustomerContact, CustomerAddress, CustomerBankDetail, CustomerNote
- 5 repositories with tenant isolation and FTS search (PostgreSQL tsvector, SQLite ILIKE fallback)
- CustomerService with state machine (DRAFT→ACTIVE→ON_HOLD/BLOCKED→ACTIVE→INACTIVE), activation invariants (≥1 contact, ≥1 billing address, payment_term set), credit status auto-calculation (GOOD/WARNING/EXCEEDED/HOLD)
- 10 domain events (non-frozen @dataclass matching purchase module pattern)
- Bulk CSV import (BATCH_SIZE=500), CSV export with UTF-8 BOM
- 28 REST API routes (CRUD, transitions, contacts, addresses, bank-details, notes, import, export)
- Alembic migration 026_sales_customers with PostgreSQL FTS trigger

**Frontend (T051–T055):**
- Customer list page (search, filter by status/type/category/group, pagination)
- Customer detail page (tabbed: General/Contacts/Addresses/Notes + status actions)
- Customer create form
- Bulk import page (template download, file upload, progress, error report)
- CustomerStatusActions component (state-aware buttons with reason dialog)
- Phase 1 API client functions appended to sales.ts

**Tests:** 61 tests total — 33 unit + 14 repository integration + 14 API integration — all pass (129 tests pass in full sales suite).

**Key bug fixed:** `CurrentUser.user_id` not `.id` — all router actor_id references corrected. Non-frozen `@dataclass` pattern for domain events (matches purchase module).

**Tasks marked:** T032–T061 → [X] in tasks.md.
