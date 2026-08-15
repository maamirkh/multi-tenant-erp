---
id: 0018
title: Payment Processing Allocation Phase 10 Implementation
stage: green
date: 2026-08-09
surface: agent
model: claude-sonnet-5
feature: 008-accounting-finance
branch: 008-accounting-finance
user: Muhammad Amir
command: /sp.implement
labels: ["accounting", "payments", "allocation-engine", "phase-10", "fx-gain-loss", "wht"]
links:
  spec: specs/008-accounting-finance/spec.md#22-payments
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/accounting/models/payments.py
  - backend/modules/accounting/models/__init__.py
  - backend/modules/accounting/repositories/payments.py
  - backend/modules/accounting/repositories/ar.py
  - backend/modules/accounting/repositories/ap.py
  - backend/modules/accounting/repositories/gl.py
  - backend/modules/accounting/schemas/payments.py
  - backend/modules/accounting/services/allocation_engine.py
  - backend/modules/accounting/services/payment_service.py
  - backend/modules/accounting/dependencies.py
  - backend/modules/accounting/router.py
  - backend/modules/accounting/constants.py
  - backend/modules/accounting/exceptions.py
  - backend/modules/accounting/handlers/integration_handlers.py
  - backend/migrations/versions/044_accounting_payments.py
  - backend/tests/unit/modules/accounting/test_allocation_engine.py
  - backend/tests/unit/modules/accounting/test_wht.py
  - backend/tests/integration/repositories/accounting/test_payment_allocation.py
  - backend/tests/integration/api/v1/accounting/test_payment_api.py
  - frontend/src/lib/api/accounting.ts
  - frontend/src/app/(protected)/(accounting)/payments/customer/page.tsx
  - frontend/src/app/(protected)/(accounting)/payments/supplier/page.tsx
  - frontend/src/app/(protected)/(accounting)/payments/unallocated/page.tsx
  - specs/008-accounting-finance/tasks.md
tests:
  - backend/tests/unit/modules/accounting/test_allocation_engine.py (8 tests)
  - backend/tests/unit/modules/accounting/test_wht.py (5 tests)
  - backend/tests/integration/repositories/accounting/test_payment_allocation.py (5 tests)
  - backend/tests/integration/api/v1/accounting/test_payment_api.py (8 tests)
  - full accounting regression suite (413 tests, 1 pre-existing unrelated failure — see PHR 0017)
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

Epic: Epic 8 – Accounting & Finance
Phase: 10
Phase Name: "Payment Processing & Allocation (US10)"

Implement ONLY this phase. Do NOT implement any future phases.

[Full command body specified: pre-implementation reading requirements,
architecture rules (Modular Monolith, Clean Architecture, DDD, Repository
Pattern, Service Layer, DI, SOLID, DRY, KISS, Feature Flags, Soft Delete,
Audit Logging, Multi-Tenant SaaS, RBAC, Company Isolation), accounting
principles (double-entry, balanced journals, immutable ledger, auditability,
period integrity), implementation rules (backend/frontend/domain/
application/infrastructure/repositories/services/validation/authorization/
events/tests/docs), database migration rules, GL posting rules, API
conventions, frontend UX requirements, testing requirements, validation
requirements (formatting, linting, type-checking, tests, Docker build/
compose, migrations, financial validation, app startup, API health), Docker
verification checklist, financial validation checklist (debit=credit,
ledger balances, trial balance, audit trail), final quality review against
spec/plan/tasks, and a 12-point completion output format. Full verbatim
text preserved in the session's command invocation.]

## Response snapshot

Read spec.md §22 (Payments), plan.md's "Phase 9: Payments" section
(plan.md's internal numbering predates the later Cash Management insertion
— tasks.md's actual "Phase 10" section header is authoritative, same
resolution as Phase 9's session), data-model.md §2.8 Payment aggregate and
§4.3 AllocationEngine, and tasks.md T204–T223 (20 tasks) in full before
writing code.

**Key design decisions** (documented as deliberate resolutions where
authoritative sources diverged, favoring tasks.md's concrete field lists
per "follow the approved implementation strategy exactly"):
- **Unified `PaymentAllocationLine`** (T205's explicit new model in
  `payments.py`) supersedes Phase 6/7's provisional per-domain
  `ARPaymentAllocation`/`APPaymentAllocation` placeholders — those tables
  were built before the unified `Payment` aggregate existed and remain
  permanently unpopulated, exactly as their own docstrings anticipated
  ("Phase 9 populates this").
- **Every payment gets a paired "credit" AR/APTransaction** (negative
  outstanding, `source_document_type="Payment"`) created atomically with
  the payment's own GL entry. `AllocationEngine.allocate()` locks and
  decrements both the target invoice/bill AND this credit transaction
  symmetrically — one mechanism that gives partial payments, overpayments
  (spec §22.5), and advances (spec §22.4) all "for free" without special-
  casing, since a credit is just a transaction with a negative outstanding
  balance reusing the AR/AP subsidiary ledger's existing state machine.
- **FX gain/loss sign convention** derived and verified against concrete
  worked examples (documented in the module docstring): AR gain/loss =
  `amount_foreign × (settlement_rate − booking_rate)`; AP is the mirror.
  Discount, gain/loss, and advance-release adjustments net into a single
  combined journal entry per allocation line (not three), referenced by
  `PaymentAllocationLine.gain_loss_journal_entry_id`.
- **Advance/WHT-payable accounts are caller-supplied per-request**
  (`advance_account_id`, `wht_payable_account_id`), matching the Cash/Bank
  precedent for GL accounts outside `AccountingConfiguration`'s fixed set,
  rather than adding new config columns.
- **T212/T213 confirmed as still-correct stubs**: per the codebase's own
  Phase 4/0 verification findings, `HandleSalesPaymentReceived`/
  `HandleSupplierPaymentMade` were never real inbound events — Sales/
  Purchase publish nothing to subscribe to. Updated their docstrings to
  cross-reference the now-real capability (`PaymentService.
  create_customer_payment()`/`create_supplier_payment()` via the new API
  endpoints), mirroring exactly how Phase 7 resolved the analogous
  `HandlePurchaseBillPosted` stub.

**Implemented**: `Payment`/`PaymentAllocationLine`/`PaymentRefund` models;
4 repositories (plus `get_by_id_locked()` SELECT-FOR-UPDATE additions to
`ARTransactionRepository`/`APTransactionRepository`); `AllocationEngine`
(T207); `PaymentService` (T208–T211: customer/supplier payments, advance
handling, overpayment, WHT with feature-flag gating, cancel via
`PostingEngine.reverse()`, refund, reallocation); 13 Pydantic schemas; 10
API endpoints; migration 044 (3 tables); 3 frontend pages + 19 new typed
API client functions.

**Bug found and fixed** (pre-existing, Phase 4/6 code, not introduced this
session): `GLReportRepository.account_balance_query()` filtered
`status == "POSTED"` only, silently excluding `REVERSED` journal entries
from balance queries — meaning a reversed entry's original effect vanished
from the balance while its reversal's opposite-direction lines still
counted, corrupting the result by the full reversed amount. Discovered via
`cancel_payment()`'s own regression test (`test_cancel_unallocated_
payment_reverses_gl_and_closes_credit`) — the first test in this codebase
to query GL balance immediately after a `PostingEngine.reverse()` call.
Fixed by widening the filter to `status.in_(["POSTED", "REVERSED"])`
(a reversed entry is immutable, real history; only its separate reversal
entry nets it out — excluding it breaks "Immutable Ledger"). Verified safe
across all 4 existing callers (Cash/AP/AR/Bank reconciliation) and the full
296-test pre-Phase-10 accounting suite, which passed unchanged.

## Outcome

- ✅ Impact: Phase 10 (Payment Processing & Allocation, US10) fully
  implemented — customer/supplier payments, the AllocationEngine (partial/
  advance/overpayment via one unified mechanism), realized FX gain/loss,
  early payment discounts, WHT, refunds, cancellation, reallocation. Plus
  one real latent bug fixed in shared Phase 4/6 GL-reporting infrastructure.
  Stopped at phase boundary; Phase 11 not started.
- 🧪 Tests: 26/26 new tests pass (8 AllocationEngine unit, 5 WHT unit, 5
  integration Sales-to-Cash/Purchase-to-Pay/cancel/refund, 8 API); full
  accounting regression 412/413 (the 1 failure is the pre-existing,
  already root-caused `test_recurring_journal_service.py` test-isolation
  defect from PHR 0017 — confirmed identical, unrelated to Phase 10).
  ruff clean; mypy strict clean on all 5 new standalone files plus the
  modified AR/AP/GL repositories; `tsc --noEmit` 0 errors; ESLint 0
  errors/warnings on new frontend files.
- 📁 Files: 4 new backend modules (models/repositories/schemas/services ×2:
  AllocationEngine + PaymentService), 1 migration, 4 test files, 3 frontend
  pages, plus edits to dependencies.py/router.py/constants.py/exceptions.py/
  integration_handlers.py/ar.py/ap.py/gl.py (the bug fix)/accounting.ts.
- 🔁 Next prompts: Phase 11 — Tax Engine & Cost Centers (US11, US12).
- 🧠 Reflection: The FX gain/loss and combined-adjustment-entry design
  required working through several concrete numeric examples by hand
  before writing code (documented in the module docstrings so the sign
  convention is auditable, not just asserted) — for double-entry logic,
  deriving the formula against a worked example first and writing the
  derivation into the code as documentation caught what would otherwise
  have been a plausible-looking but wrong DR/CR direction. The GL-balance
  bug was only found because the test suite exercised a genuinely new
  code path (query balance right after a reversal) that no prior phase
  had combined before.

## Evaluation notes (flywheel)

- Failure modes observed: (1) initial test fixture passed a GL `Account`
  id where a `BankAccount` entity id was required — caught immediately by
  the first test run, not a design flaw; (2) one test's own assertion
  (AR-control nets to zero) was invalid given a fixture that never posted
  the invoice's own GL entry — fixed the test, not the code, after
  confirming the invariant it meant to check; (3) the `GLReportRepository.
  account_balance_query()` REVERSED-entry exclusion bug (see above) — a
  genuine pre-existing defect, fixed with a scoped, well-justified change
  and verified against the full existing regression suite before treating
  it as safe.
- Graders run and results (PASS/FAIL): ruff PASS (after one auto-fixable
  import-order pass); mypy strict PASS on all new/modified files (3 real
  type-narrowing issues found and fixed — union-typed local variables
  across if/else branches, and an unchecked `UUID | None` parameter);
  pytest (new, 26 tests) PASS; pytest (full accounting regression, 413
  tests) PASS 412/413 (1 pre-existing, unrelated); tsc --noEmit PASS (0
  errors); eslint PASS (0 errors, 0 warnings).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
