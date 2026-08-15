---
id: 0010
title: Fiscal Calendar Phase 3 implementation
stage: green
date: 2026-08-06
surface: agent
model: claude-sonnet-5
feature: 008-accounting-finance
branch: 008-accounting-finance
user: Muhammad Amir
command: /sp.implement
labels: ["epic-8", "accounting", "fiscal-calendar", "phase-3"]
links:
  spec: specs/008-accounting-finance/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/accounting/models/fiscal.py
 - backend/modules/accounting/models/__init__.py (registered FiscalYear/FiscalPeriod/OpeningBalance)
 - backend/modules/accounting/repositories/fiscal.py
 - backend/modules/accounting/events/fiscal_events.py
 - backend/modules/accounting/handlers/period_lock_handler.py
 - backend/modules/accounting/services/fiscal_service.py
 - backend/modules/accounting/schemas/fiscal.py
 - backend/modules/accounting/exceptions.py (added 7 fiscal exceptions)
 - backend/modules/accounting/dependencies.py (fiscal repo/service DI factories)
 - backend/modules/accounting/router.py (11 fiscal-calendar endpoints)
 - backend/main.py (register_period_lock_handlers() at startup)
 - backend/migrations/versions/037_accounting_fiscal_calendar.py
 - backend/tests/unit/modules/accounting/test_fiscal_state_machine.py
 - backend/tests/unit/modules/accounting/test_fiscal_service.py
 - backend/tests/integration/repositories/accounting/test_fiscal_repository.py
 - backend/tests/integration/api/v1/accounting/test_fiscal_api.py
 - frontend/src/lib/api/accounting.ts (fiscal calendar types + API functions)
 - frontend/src/app/(protected)/(accounting)/fiscal-calendar/page.tsx
 - frontend/src/app/(protected)/(accounting)/fiscal-calendar/[yearId]/periods/page.tsx
 - frontend/src/app/(protected)/(accounting)/fiscal-calendar/[yearId]/opening-balances/page.tsx
 - frontend/src/components/accounting/YearEndCloseWizard.tsx
 - specs/008-accounting-finance/tasks.md (T068-T088 marked complete with implementation notes)
tests:
 - backend/tests/unit/modules/accounting/test_fiscal_state_machine.py (10 tests)
 - backend/tests/unit/modules/accounting/test_fiscal_service.py (15 tests)
 - backend/tests/integration/repositories/accounting/test_fiscal_repository.py (6 tests)
 - backend/tests/integration/api/v1/accounting/test_fiscal_api.py (11 tests)
 - full accounting module regression: 184 passed, 0 failed
---

## Prompt

You are the Principal Software Architect, Chief Financial Systems Architect,
Enterprise SaaS Architect and Senior Staff Engineer for DevSphere ERP.

Implement ONLY the following phase from Epic 8 exactly as defined in the approved:

• Engineering Constitution
• Epic 8 spec.md
• Epic 8 plan.md
• Epic 8 tasks.md

===============================================================================
IMPLEMENTATION TARGET
===============================================================================

Epic:
Epic 8 – Accounting & Finance

Phase: 3

Phase Name: "Fiscal Calendar (US3)"

Implement ONLY this phase.

Do NOT implement any future phases.

===============================================================================
PRE-IMPLEMENTATION
===============================================================================

Before writing code:

1. Read the Engineering Constitution completely.
2. Read Epic 8 spec.md completely.
3. Read Epic 8 plan.md completely.
4. Read Epic 8 tasks.md completely.
5. Review all dependencies from previous Epics.
6. Validate architectural consistency.
7. Follow the approved implementation strategy exactly.

Maintain full compatibility with:

• Epic 0 – Engineering Constitution
• Epic 1 – Foundation
• Epic 2 – Authentication
• Epic 3 – Companies
• Epic 4 – Users & Roles
• Epic 5 – Inventory
• Epic 6 – Purchase
• Epic 7 – Sales

===============================================================================
ARCHITECTURE RULES
===============================================================================

Strictly follow:

• Modular Monolith
• Clean Architecture
• Domain Driven Design (DDD)
• Repository Pattern
• Service Layer
• Dependency Injection
• SOLID Principles
• DRY
• KISS
• Separation of Concerns
• Feature Flags
• Soft Delete
• Audit Logging
• Multi-Tenant SaaS
• RBAC
• Company Isolation

Do not introduce architectural changes unless absolutely necessary.

===============================================================================
ACCOUNTING PRINCIPLES
===============================================================================

Every implementation must preserve:

• Double Entry Accounting
• Balanced Journal Validation
• Immutable Ledger
• Auditability
• Financial Integrity
• Period Integrity
• Company Financial Isolation
• Accurate Financial Reporting

Never compromise financial correctness.

===============================================================================
IMPLEMENTATION RULES
===============================================================================

Implement everything defined for this phase including:

• Backend
• Frontend (if required)
• Domain
• Application
• Infrastructure
• Repositories
• Services
• Validation
• Authorization
• Integration
• Domain Events
• Tests
• Documentation updates (if required)

Complete every task for this phase before stopping.

===============================================================================
DATABASE
===============================================================================

If database changes are required:

• Create/update Alembic migrations.
• Preserve existing financial data.
• Maintain backward compatibility.
• Validate migration execution.
• Never break previous Epics.

===============================================================================
GENERAL LEDGER
===============================================================================

Whenever this phase affects financial posting:

Ensure:

• Balanced Journals
• Posting Validation
• Ledger Integrity
• Immutable History
• Audit Logging
• Correct Debit/Credit Rules

Never allow invalid financial postings.

===============================================================================
API
===============================================================================

If APIs are required:

• Follow existing API conventions.
• Apply authentication.
• Apply authorization.
• Validate RBAC.
• Validate tenant isolation.
• Return consistent responses.
• Handle financial errors gracefully.

===============================================================================
FRONTEND
===============================================================================

If UI changes are required:

Follow existing design system.

Ensure:

• Responsive UI
• Loading States
• Empty States
• Error States
• Form Validation
• Accessibility
• Consistent UX

===============================================================================
TESTING
===============================================================================

Implement all required tests for this phase.

Include:

• Unit Tests
• Integration Tests
• Repository Tests
• Service Tests
• Workflow Tests
• Posting Engine Tests
• Financial Validation Tests
• RBAC Tests
• Tenant Isolation Tests
• Regression Tests

Fix all failing tests before completion.

===============================================================================
VALIDATION
===============================================================================

After implementation verify:

• Code Formatting
• Linting
• Type Checking
• Unit Tests
• Integration Tests
• Docker Build
• Docker Compose
• Database Migrations
• Financial Validation
• Application Startup
• API Health Checks

Resolve every issue before finishing.

===============================================================================
DOCKER VERIFICATION
===============================================================================

Run the application using Docker Compose.

Verify:

• API starts successfully.
• Frontend starts successfully.
• PostgreSQL is healthy.
• Redis is healthy.
• MinIO is healthy.
• Migrations execute successfully.
• No startup exceptions.
• No dependency injection errors.
• No migration failures.
• No tenant isolation issues.
• Financial services initialize correctly.

===============================================================================
FINANCIAL VALIDATION
===============================================================================

If this phase affects accounting:

Verify:

• Debit = Credit
• Ledger balances remain correct
• Trial Balance remains balanced
• Journal integrity maintained
• Audit trail generated
• Financial reports remain consistent

===============================================================================
FINAL QUALITY REVIEW
===============================================================================

Before finishing:

Review implementation against:

• Epic 8 spec.md
• Epic 8 plan.md
• Epic 8 tasks.md

Ensure every task for this phase is complete.

Do not leave partial implementations.

Do not continue to the next phase automatically.

===============================================================================
OUTPUT
===============================================================================

When implementation is complete provide:

1. Summary of completed work.
2. Files created.
3. Files modified.
4. Database changes.
5. APIs added/updated.
6. UI changes.
7. Financial components implemented.
8. Tests executed.
9. Docker verification results.
10. Financial validation results.
11. Any assumptions made.
12. Confirmation that the phase is complete and ready for the next phase.

Only implement the requested phase.

Stop after completing the selected phase.

## Response snapshot

Implemented all 21 tasks (T068-T088) of Phase 3 "Fiscal Calendar (US3)". Backend: `FiscalYear`/`FiscalPeriod`/`OpeningBalance` ORM models (models/fiscal.py) with self-consistent check constraints (status enums, date-range, period-number 1-13, opening-balance one-sidedness); `FiscalYearRepository`/`FiscalPeriodRepository`/`OpeningBalanceRepository`; `FiscalCalendarService` with `create_fiscal_year()` (auto-generates 12 contiguous monthly periods spanning any start/end date, verified via a manual script to sum exactly to the fiscal year span with no gaps), `lock_period()`/`unlock_period()` (mandatory reason, publishes events), `close_period()` (only reachable internally via year-end close — direct calls rejected), `get_open_period_for_posting()` (the exact validation Phase 4's PostingEngine Step 3 will call), `setup_opening_balances()` (validates sum debit == sum credit), `execute_year_end_close()` (validates all periods LOCKED, cascades periods to CLOSED, transitions the year to CLOSED, publishes `accounting.fiscalyear.closed`). `FiscalPeriodStateMachine` enforces OPEN->LOCKED->OPEN->CLOSED with CLOSED strictly terminal. 4 new domain events (period.locked/unlocked/closed, fiscalyear.closed) plus a `PeriodLockCache` handler subscribed to Accounting's own event bus at app startup. 7 new domain exceptions. 11 new REST endpoints under `/accounting/fiscal-years/...`. Migration 037 (fiscal_years/fiscal_periods/opening_balances tables with FKs to accounting_accounts/accounting_fiscal_years).

Two structural gaps were hit and handled the same way Phase 1/2 handled theirs — documented explicitly rather than silently worked around or invented: (1) T076 asked to wire the period-lock cache into Sales/Purchase/Inventory's own PostingServices, but code search confirmed none of those three modules has any GL-posting concept today, and no module in this codebase subscribes to another module's event bus — building that now would invent a cross-module contract ahead of Phase 4's real integration point (Accounting consuming their *outbound* events). Built the cache fully functional against Accounting's own bus instead, ready for Phase 4. (2) `execute_year_end_close()`/`setup_opening_balances()` cannot actually post PostingEngine journal entries (retained-earnings closing entry / OPENING_BALANCE journal) because the PostingEngine and JournalEntry aggregate don't exist until Phase 4 — implemented everything Phase 3 data allows and documented the exact call Phase 4 must wire in, mirroring Phase 2's GL-activity-on-deactivation gap.

Frontend: Fiscal Year list+create page, Period Dashboard (lock/unlock with mandatory-reason inline form), Opening Balance entry screen (live running debit/credit totals with balanced/imbalanced badge), `YearEndCloseWizard` (periods-locked check server-enforced; bank-reconciled/AR-AP-confirmed as manual attestation checkboxes since those modules don't exist yet).

Validation: 42 new tests (10 state-machine + 15 service + 6 repository + 11 API), all passing; full accounting module regression 184 passed/0 failed (includes Phase 1/2's 142 tests, confirming no regression); ruff clean; mypy clean (only pre-existing repo-wide FastAPI Ellipsis-default warnings, present identically on every other endpoint in this router since Phase 1); frontend `tsc --noEmit` and `eslint` clean (only the same pre-existing `useEffect` dependency warning already present on chart-of-accounts/page.tsx). Docker: rebuilt api+web containers; migrations 001-037 apply cleanly against real PostgreSQL (`alembic current` -> `037 (head)`); `accounting_fiscal_years`/`accounting_fiscal_periods`/`accounting_opening_balances` confirmed via `psql \dt`; all 4 containers healthy; frontend build succeeded with all 3 new fiscal-calendar routes compiling; live curl checks confirm `/`, `/login`, `/chart-of-accounts`, `/fiscal-calendar` all return 200 and the new API endpoints correctly return 401 unauthenticated.

Also flagged (not implemented, no corresponding tasks.md task ID): plan.md's narrative mention of "next fiscal year initialization with opening balances carried from prior year closing" has no task ID in T068-T088, so it was not added — flagged in tasks.md rather than silently included or omitted.

## Outcome

- ✅ Impact: Phase 3 (Fiscal Calendar) is fully implemented and independently testable per its Independent Test criterion — locking a period correctly blocks the exact posting-date validation Phase 4's PostingEngine will use, and year-end close correctly gates on all periods being locked. Two genuine spec/reality gaps (cross-module event wiring; PostingEngine-dependent journal posting) were handled by documenting them precisely rather than inventing unrequested cross-Epic changes or fake GL entries.
- 🧪 Tests: 42 new tests, all passing. Full accounting module suite: 184 passed, 0 failed (Phase 1: 85, Phase 2: 57, Phase 3: 42).
- 📁 Files: 12 new backend files, 3 modified backend files (exceptions.py, dependencies.py, router.py, models/__init__.py, main.py), 1 new migration, 4 new test files, 1 modified frontend lib file, 4 new frontend files (3 pages + 1 component), tasks.md updated.
- 🔁 Next prompts: Phase 4 (PostingEngine & General Ledger) is the natural next step — it must wire `FiscalCalendarService.get_open_period_for_posting()` into `PostingEngine`'s Step 3, and must give `execute_year_end_close()`/`setup_opening_balances()` the ability to actually post journal entries via the PostingEngine once it exists.
- 🧠 Reflection: The recurring pattern across Phases 1-3 of this epic is that tasks.md sometimes describes behavior (calling the PostingEngine) that structurally cannot exist yet because it's scoped to a later phase. The correct response each time has been the same: implement everything the current phase's actual data model supports, and document the exact gap and what the future phase must wire in — never fabricate a fake integration or silently skip the requirement.

## Evaluation notes (flywheel)

- Failure modes observed: None during implementation; a manual SQLite smoke-test script (outside pytest, using a raw engine without the project's `gen_random_uuid()` SQLite shim registered in conftest.py) failed with "unknown function: gen_random_uuid" — not a code bug, just a reminder that ad-hoc verification scripts must replicate conftest.py's `event.listen(engine, "connect", _add_sqlite_functions)` shim if they bypass the real test fixtures.
- Graders run and results (PASS/FAIL): N/A (no formal grader harness invoked this turn).
- Prompt variant (if applicable): N/A.
- Next experiment (smallest change to try): When Phase 4 implements the PostingEngine, grep this phase's two "documented gap" docstrings (`execute_year_end_close`, `setup_opening_balances`) first — they specify exactly what Phase 4 needs to wire in, avoiding re-deriving the requirement from spec.md again.
