---
id: 0014
title: Accounts Payable Phase 7 Implementation
stage: green
date: 2026-08-08
surface: agent
model: claude-sonnet-5
feature: 008-accounting-finance
branch: 008-accounting-finance
user: Muhammad Amir
command: /sp.implement
labels: ["accounting", "accounts-payable", "phase-7", "posting-engine", "manual-entry", "reconciliation"]
links:
  spec: specs/008-accounting-finance/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/accounting/constants.py
 - backend/modules/accounting/exceptions.py
 - backend/modules/accounting/models/ap.py
 - backend/modules/accounting/models/__init__.py
 - backend/modules/accounting/repositories/ap.py
 - backend/modules/accounting/services/aging_calculator.py
 - backend/modules/accounting/events/ap_events.py
 - backend/modules/accounting/services/ap_service.py
 - backend/modules/accounting/handlers/integration_handlers.py
 - backend/modules/accounting/dependencies.py
 - backend/modules/accounting/schemas/ap.py
 - backend/modules/accounting/router.py
 - backend/modules/accounting/services/scheduler.py
 - backend/migrations/versions/041_accounting_ap_ledger.py
 - backend/tests/unit/modules/accounting/test_aging_calculator.py
 - backend/tests/integration/repositories/accounting/test_ap_repository.py
 - backend/tests/integration/api/v1/accounting/test_ap_api.py
 - frontend/src/lib/api/accounting.ts
 - frontend/src/app/(protected)/(accounting)/payables/suppliers/[supplierId]/page.tsx
 - frontend/src/app/(protected)/(accounting)/payables/aging/page.tsx
 - frontend/src/app/(protected)/(accounting)/payables/reconcile/page.tsx
 - specs/008-accounting-finance/tasks.md
tests:
 - backend/tests/unit/modules/accounting/test_aging_calculator.py (APAgingCalculator additions, 8 tests)
 - backend/tests/integration/repositories/accounting/test_ap_repository.py (8 tests)
 - backend/tests/integration/api/v1/accounting/test_ap_api.py (10 tests)
 - Full accounting regression suite: 357 passed
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

Phase: 7

Phase Name: "Accounts Payable (US7)"

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

Implemented Phase 7 (Accounts Payable, T156–T174) in full.

**Key architectural finding driving this phase's design**: Phase 0
verification (quickstart.md "Phase 0 Verification Findings") had already
confirmed Purchase (Epic 6) has no Bill/Invoice/AP entity or event at all —
spec 006 §60.2 explicitly defers Invoice Processing/Accounts Payable to
Epic 8's own future scope, and the already-documented resolution was "AP
bill capture built inside Accounting itself." This meant T163/T164's
literal wording ("wire HandlePurchaseBillPosted event handler") could not
be a real event subscription — there is no producer. I implemented the
identical atomic-posting capability those handlers would have used as
`AccountsPayableService.record_supplier_bill()`/`record_supplier_credit_
note()` (same `PostingEngine.stage_direct_posting()`+`finalize_and_
publish()` pattern as AR's Phase 6 `record_sales_invoice()`), invoked by
two new manual-entry API endpoints (`POST /accounting/ap/bills`,
`POST /accounting/ap/credit-notes`) rather than by event callbacks. The
existing `handle_purchase_bill_posted`/`handle_purchase_credit_note_posted`
stubs (already documented as unsubscribed in Phase 4/6) had their
docstrings updated to point at this real capture path instead of
speculating about a future event.

- **Models** (`models/ap.py`): `SupplierLedger`, `APTransaction`,
  `APPaymentAllocation` (payment_id deferred-FK, Phase 9),
  `SupplierStatementReconciliation`, `SupplierStatementReconciliationItem`
  — direct mirror of AR's Phase 6 model design (data-model.md §2.5 says
  as much explicitly: "Key Attributes: Mirror of CustomerLedger/
  ARTransaction with supplier context").
- **Repositories** (`repositories/ap.py`): `SupplierLedgerRepository`,
  `APTransactionRepository` (with `find_bills_due_within_across_
  companies()` and `find_overdue_across_companies()` cross-tenant scans),
  `APPaymentAllocationRepository`, `SupplierStatementReconciliationRepository`,
  `SupplierStatementReconciliationItemRepository`.
- **APAgingCalculator** (added to `services/aging_calculator.py` alongside
  AR's `AgingCalculator` — the two share the identical `_bucket_for()`
  boundary logic via a small shared module-level function rather than a
  premature generic base class).
- **AccountsPayableService** (`services/ap_service.py`): ledger access,
  atomic `record_supplier_bill()`/`record_supplier_credit_note()`,
  `adjust_payable()`, `reconcile_supplier_statement()` (statement-first
  exact-amount matching against open bills — research.md Decision 6's
  pattern, applied to AP; unmatched lines/bills left for manual follow-up
  rather than auto-resolved), `generate_remittance_advice()` (built from
  `APPaymentAllocation` rows sharing a `payment_id`; correctly empty until
  Phase 9 populates that table — no `Payment` entity exists yet),
  `reconcile_ap_control_account()` (T165 — note AP is liability/credit-
  normal, so the GL-balance sign convention is `credit − debit`, the
  opposite of AR's asset-normal `debit − credit`), and
  `run_bill_due_reminder_check()` (T166).
- **Scheduler** (`services/scheduler.py`): new dedicated
  `ap_bill_due_reminder_job()`, registered alongside the existing two daily
  jobs; `ar_ap_overdue_check_job()`'s AP half remains a documented no-op
  since T166 only asks for the due-*soon* reminder, not overdue-marking.
- **Schemas** (`schemas/ap.py`) and **7 API endpoints** (`router.py`):
  the 5 literally listed in T168, plus `POST /accounting/ap/bills` and
  `POST /accounting/ap/credit-notes` — a justified extension, since
  without a create endpoint the AP ledger would have no way to ever
  receive a bill in production use.
- **Migration** (`041_accounting_ap_ledger.py`): 5 tables, FKs, check
  constraints, and indexes — applied cleanly against live PostgreSQL.
- **Frontend**: 3 pages (Supplier Ledger, AP Aging Report, Supplier
  Statement Reconciliation workspace with side-by-side matched/unmatched
  display) plus corresponding `lib/api/accounting.ts` client additions.
- **Tests**: `test_ap_repository.py` (8 tests: bill/credit-note/adjustment
  posting + reconciliation, statement-reconciliation matching, AP aging
  boundaries), `test_ap_api.py` (10 tests: all endpoints incl. bill/credit-
  note creation, 401, 404, cross-tenant isolation, remittance-advice empty-
  until-Phase-9 behavior), plus 8 new `APAgingCalculator` unit tests added
  to `test_aging_calculator.py`. Full accounting suite: 357 passed (332
  from Phase 6 + 25 new), 0 regressions.
- **Docker verification**: rebuilt the `api` image, container started
  healthy, migration 041 applied automatically (`alembic_version`=041), no
  startup exceptions, all three scheduler jobs registered including the
  new `ap_bill_due_reminder_job`. Live smoke test against Postgres inside
  the container: posted a real bill, confirmed `APTransaction`/
  `SupplierLedger` state, called `reconcile_ap_control_account()` (held),
  posted a credit note and re-verified reconciliation, ran a full
  statement-reconciliation cycle (exact match → COMPLETED; partial/
  mismatched → IN_PROGRESS with correct UNMATCHED_STATEMENT/UNMATCHED_GL
  items), and ran the real `ap_bill_due_reminder_job()` function directly
  (no error) — all against genuine PostgreSQL, not mocks.
- Marked T156–T174 `[X]` in `tasks.md` with implementation notes
  (including the Purchase-event-doesn't-exist finding on T163/T164), and
  all 3 Phase 7 exit criteria `[X]`.

## Outcome

- ✅ Impact: Phase 7 (Accounts Payable) fully implemented and verified end-to-end against live PostgreSQL; AP mirrors AR's atomic GL integration and reconciliation guarantees, with bill capture correctly resolved as an in-Accounting manual-entry capability given Purchase's confirmed lack of a Bill/AP concept.
- 🧪 Tests: 357/357 accounting tests passing (18 new: 8 repository + 10 API, plus 8 new APAgingCalculator unit tests); ruff clean; mypy clean on all new/modified files (pre-existing unrelated errors elsewhere in the codebase, and the same pre-existing `body: X = ...` mypy pattern already present on every other router endpoint, untouched).
- 📁 Files: 13 backend files created/modified, 3 frontend pages + 1 API client file, 1 migration, 3 test files, tasks.md updated.
- 🔁 Next prompts: Phase 8 (Banking, US8) — not started per this command's explicit instruction to stop after Phase 7.
- 🧠 Reflection: The AR-vs-AP sign-convention difference (asset debit-normal vs liability credit-normal) in the two `reconcile_*_control_account()` methods is a subtle, easy-to-get-backwards detail — worth double-checking explicitly whenever a new subsidiary-ledger reconciliation is added in a future phase (e.g. if Payments/Phase 9 ever needs its own reconciliation against a bank/cash control account).

## Evaluation notes (flywheel)

- Failure modes observed: None requiring correction from the user in this segment — the Purchase-event-doesn't-exist situation was anticipated from Phase 6's own documented precedent (quickstart.md's Phase 0 findings already named this as a Phase 7 concern) rather than discovered as a surprise, so no rework was needed.
- Graders run and results (PASS/FAIL): ruff — PASS; mypy (scoped to new/modified files) — PASS; full accounting pytest suite — PASS (357/357); live Docker/PostgreSQL smoke test (bill, credit note, reconciliation, scheduler job) — PASS.
- Prompt variant (if applicable): Same `/sp.implement` mega-prompt template used for Phases 1–6, phase number/name substituted.
- Next experiment (smallest change to try): For Phase 8 (Banking) and beyond, check early whether the upstream module event this phase's tasks.md assumes actually exists (per quickstart.md's Phase 0 findings table) before starting implementation — this phase confirmed that check is now a reliable first step, not just a one-off Phase 6 concern.
