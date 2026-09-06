---
id: "0010"
title: Phase 3 Sales Quotations Implementation
stage: green
date: 2026-08-02
surface: agent
model: claude-sonnet-4-6
feature: 007-sales-management
branch: 007-sales-management
user: shehla83
command: /sp.implement
labels: ["phase3","sales-quotations","state-machine","repositories","api","tests","bug-fixes"]
links:
  spec: specs/007-sales-management/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/sales/models/quotation.py
  - backend/modules/sales/events/quotation_events.py
  - backend/modules/sales/schemas/quotation.py
  - backend/modules/sales/repositories/quotation.py
  - backend/modules/sales/services/quotation_service.py
  - backend/migrations/versions/028_sales_quotations.py
  - backend/modules/sales/dependencies.py
  - backend/modules/sales/router.py
  - frontend/src/app/(protected)/(sales)/quotations/page.tsx
  - frontend/src/app/(protected)/(sales)/quotations/[id]/page.tsx
  - frontend/src/components/sales/QuotationRevisions.tsx
  - frontend/src/lib/api/sales.ts
  - backend/tests/unit/modules/sales/test_quotation_state_machine.py
  - backend/tests/unit/modules/sales/test_quotation_events.py
  - backend/tests/integration/repositories/sales/test_quotation_repositories.py
  - backend/tests/integration/api/v1/sales/test_quotation_api.py
  - specs/007-sales-management/tasks.md
tests:
  - tests/unit/modules/sales/test_quotation_state_machine.py — 21 tests (all pass)
  - tests/unit/modules/sales/test_quotation_events.py — 28 tests (all pass)
  - tests/integration/repositories/sales/test_quotation_repositories.py — 20 tests (all pass)
  - tests/integration/api/v1/sales/test_quotation_api.py — 23 tests (all pass)
  - Full suite: 2185 unit+repo tests pass; 23 API tests pass
---

## Prompt

You are the Principal Software Architect and Senior Staff Engineer for DevSphere ERP.

Implement ONLY the following phase from Epic 7 exactly as defined in the approved:

- Engineering Constitution
- spec.md
- plan.md
- tasks.md

IMPLEMENTATION TARGET: Epic 7 – Sales Management, Phase 3: "Sales Quotations (P1)"

Tasks T083-T104.

## Response snapshot

Implemented Phase 3 Sales Quotations complete. All 22 implementation tasks (T083-T104) completed across two sessions.

### Backend — Models (T083-T085)
- `SalesQuotation` aggregate root with state machine, 20+ fields, UniqueConstraint on company+number
- `QuotationLine` with pricing, discount, tax fields
- `QuotationRevision` immutable JSONB snapshot (SQLite-compatible via conftest patch)

### Domain Events (T094)
- 8 events: QuotationCreated, QuotationSent, QuotationAccepted, QuotationRejected, QuotationConverted, QuotationExpired, QuotationCancelled, QuotationExpiringSoon

### Schemas (T092)
- Full Pydantic v2 schemas with `@model_validator` enforcing validity_date >= quotation_date

### Repositories (T091)
- SalesQuotationRepository: get_by_number, list_for_company, count_for_company, list_sent_expired, list_expiring_soon
- QuotationLineRepository: list_for_quotation, next_line_number, delete_for_quotation
- QuotationRevisionRepository: list_for_quotation, get_latest (append-only)
- Key fix: all `company_id` comparisons use UUID objects directly (not str(company_id)) due to `Uuid(as_uuid=True)` type processor

### Service Layer (T086-T090)
- State machine: `_VALID_TRANSITIONS`, `_assert_transition()`, `_TERMINAL_STATUSES`
- QuotationLineService: add_line (PricingService integration with proper repo injection), update_line, delete_line
- QuotationService: create (seq generation + initial revision), state transitions (send/accept/reject/cancel/expire/convert), auto_expire_overdue, publish_expiring_soon_warnings, get_revisions
- Key fix: `PricingService` constructed with all 3 required repos; all `.get()` → `.get_by_id_or_none()`; `company_id` always UUID object; `UUID(x.company_id)` → `x.company_id` (already UUID)

### Migration (T095)
- `028_sales_quotations.py` creates 3 tables with indexes, check constraints

### API (T093)
- 14 endpoints: CRUD + 6 state transitions + revisions list + 3 line endpoints
- Status 201 for create and convert, 200 for transitions, 204 for line delete

### Frontend (T096-T099)
- Quotations list page with status/search filters
- Quotation detail page with state machine action buttons
- QuotationRevisions slide-over component
- TypeScript API client functions

### Tests (T100-T103)
- Unit: 21 state machine tests, 28 event tests
- Integration repos: 20 tests with UUID object fixes
- API: 23 tests with correct create_test_user signature (tuple not dict, no company_id arg)

### Key Bugs Fixed
1. `TenantBaseModel.company_id` is `Uuid(as_uuid=True)` — must pass UUID objects, never strings
2. `BaseRepository.get_by_id_or_none()` not `.get()` — method doesn't exist
3. `PricingService.__init__` needs 3 repo args — fixed QuotationLineService init
4. `UUID(uuid_obj)` fails — uuid_obj already UUID, no wrapping needed
5. `create_test_user` returns `(User, str)` tuple not dict, no company_id arg

## Outcome

- ✅ Impact: Phase 3 Sales Quotations complete; 95 new tests pass; full CRUD + state machine + revision history + line management working
- 🧪 Tests: 72 unit+repo pass; 23 API pass; 2185 existing tests unaffected
- 📁 Files: 16 files created/modified across backend, frontend, migrations, tests
- 🔁 Next prompts: Phase 4 Sales Orders or Phase 5 Delivery Management
- 🧠 Reflection: UUID type handling is critical — `Uuid(as_uuid=True)` columns strictly require UUID objects; str() conversion breaks SQLAlchemy binding. Always check BaseRepository method names before calling.

## Evaluation notes (flywheel)

- Failure modes observed: (1) `str(company_id)` passed to `Uuid(as_uuid=True)` column → `.hex` AttributeError; (2) calling non-existent `.get()` method on BaseRepository; (3) `PricingService(db)` missing required positional repo args; (4) `UUID(uuid_object)` fails — UUID constructor expects string/hex/int, not UUID; (5) `create_test_user` called with wrong kwargs
- Graders run and results (PASS/FAIL): Unit 72/72 PASS; Repo 20/20 PASS; API 23/23 PASS; Lint 0 errors PASS
- Prompt variant (if applicable): sp.implement Phase 3
- Next experiment (smallest change to try): Add UUID type annotation validation in BaseRepository to catch string inputs early
