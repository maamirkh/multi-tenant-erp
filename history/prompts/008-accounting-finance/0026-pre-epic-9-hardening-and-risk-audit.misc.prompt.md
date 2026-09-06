---
id: 0026
title: Pre-Epic-9 Hardening and Risk Audit
stage: misc
date: 2026-08-15
surface: agent
model: claude-sonnet-5
feature: 008-accounting-finance
branch: 008-accounting-finance
user: Muhammad Amir
command: none
labels: ["hardening", "security-audit", "transaction-integrity", "rbac", "tenant-isolation", "migration-integrity", "pre-epic-9"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/inventory/services/stock_service.py
  - backend/modules/inventory/services/transfer_service.py
  - backend/modules/inventory/services/product_service.py
  - backend/modules/inventory/services/warehouse_service.py
  - backend/modules/purchase/services/po_service.py
  - backend/modules/purchase/services/pr_service.py
  - backend/modules/purchase/services/supplier_service.py
  - backend/modules/sales/services/order_service.py
  - backend/modules/sales/services/quotation_service.py
  - backend/modules/sales/services/delivery_service.py
  - backend/modules/sales/services/return_service.py
  - backend/modules/sales/services/customer_import_service.py
  - backend/modules/sales/services/invoice_service.py
  - backend/modules/sales/models/quotation.py
  - backend/modules/accounting/router.py
  - backend/modules/accounting/services/payment_service.py
  - backend/modules/accounting/services/posting_engine.py
  - backend/migrations/versions/053_fix_missing_not_null_timestamps.py
  - backend/migrations/versions/054_fix_quotation_revision_modified_at_length.py
  - backend/tests/integration/api/v1/sales/test_invoice_api.py
  - backend/tests/integration/api/v1/accounting/test_journal_api.py
  - backend/tests/integration/repositories/accounting/test_audit_log.py
  - backend/tests/integration/repositories/accounting/test_payment_allocation.py
tests:
  - backend/tests/integration/api/v1/sales/test_invoice_api.py::TestCreateInvoiceAPI::test_create_invoice_zero_lines_201 (new)
  - backend/tests/integration/api/v1/sales/test_invoice_api.py::TestTenantIsolationAPI::test_invoice_due_date_ignores_foreign_payment_term (new)
  - backend/tests/integration/api/v1/accounting/test_journal_api.py::TestRejectRBAC::test_reject_blocked_without_journal_approve_permission (new)
  - backend/tests/integration/repositories/accounting/test_audit_log.py (updated, 3/3 pass)
  - backend/tests/integration/repositories/accounting/test_payment_allocation.py (updated, 11/11 pass)
  - Live Docker/Postgres targeted verification — 17/17 checks pass (Inventory 6/6, Purchase 4/4, Sales 3/3, RBAC 4/4)
  - Full Sales suite — 1579/1579 passed
  - Full Purchase suite — 1059/1059 passed, 8 skipped
  - Full Accounting suite — 566/566 passed (after fixing 3 pre-existing tests exposed by the new RBAC checks)
  - Full Inventory suite — 1070/1071 direct pass, 1 unrelated flaky performance test confirmed passing 4/5 isolated reruns
  - ruff — 100% clean on all files touched
  - mypy — zero new errors introduced (confirmed via diff against pre-existing baseline)
---

## Prompt

# DevSphere ERP — Pre-Epic-9 Hardening & Risk Audit

We have completed and consolidated live verification of DevSphere ERP Epics 1–8.

DO NOT start Epic 9.
DO NOT implement any new Epic 9 functionality.

Your task is ONLY to perform a controlled pre-Epic-9 hardening audit and fix ONLY issues that are genuinely important for the stability, correctness, security, data integrity, or future extensibility of Epics 1–8.

IMPORTANT:
Do not blindly fix every issue found.
Do not refactor unrelated code.
Do not introduce new architecture.
Do not change established behavior unless there is a demonstrated defect.
Do not modify documented out-of-scope functionality merely for completeness.

[Full task specification covered: (1) systematic transaction/commit audit across all Epic 1-8
backend services/repositories/handlers; (2) secondary audits for tenant isolation, RBAC,
financial integrity regressions, audit-trail DB-level immutability requirement, migration
integrity; (3) explicit exclusion list — do not fix mypy debt, ESLint warnings, year-end
retained-earnings automation, Purchase/Inventory auto-GL-posting, or other documented
future-phase gaps; (4) testing requirements — focused regression test per genuine defect,
PostgreSQL-compatible verification preferred, run smallest relevant suite first, not the
full 5000+ suite unless justified; (5) limited live verification — targeted Docker/Postgres
checks only for defects actually found, not a full re-verification; (6) required final report
in five sections (Findings / Fixed Issues / Not Fixed-Deferred / Epic 9 Readiness Decision
READY_FOR_EPIC_9 or BLOCK_EPIC_9 / Final Recommendation); (7) explicit stop condition — no
Epic 9 work, no Epic 9 specs/tasks, no CRM functionality, no unrelated refactoring.]

## Response snapshot

Ran 4 parallel Explore-agent audits (commit/transaction pattern across Inventory+Purchase+Sales
and separately Accounting+Companies+Users-Roles+Auth; tenant isolation; RBAC). Findings:

- **Commit/transaction audit**: confirmed the missing-commit defect class (found and partially
  fixed in the prior live-verification session) was far more pervasive than the original 9
  methods — roughly 50 additional write methods across 12 service files in Inventory, Purchase,
  and Sales had the same silent-data-loss pattern. Accounting/Companies/Users-Roles/Auth audited
  clean (every write path already commits directly or delegates to a self-committing helper).
  Fixed all confirmed instances with additive `db.commit()` calls, preserving intentional
  multi-step transaction boundaries (e.g. committing once after a full transfer-dispatch
  sequence, not mid-sequence).
- **Tenant isolation**: found and fixed a live, reachable cross-tenant lookup in
  `invoice_service.py` (payment_term_id and two related lookups queried without a company_id
  filter) — a caller in Company A could apply Company B's payment-term due_days to their own
  invoice. Two lower-severity, currently-non-exploitable defense-in-depth gaps documented but
  not fixed (would require a schema change, no live exploit path).
- **RBAC**: found and fixed 7 asymmetric permission gaps in the accounting router/services
  (reject_journal, reject_payment, cancel_payment, process_refund, fiscal-year create/update/
  opening-balances, feature-flag update, currency creation, 4 bank-account endpoints) — each
  fixed by reusing an existing, semantically-matching permission code rather than introducing
  new ones.
- **Migration integrity**: alembic history confirmed linear/single-head/zero-branches; found and
  fixed 36 columns with a NOT NULL drift (migration 053) distinct from the server-default drift
  already fixed in 051/052.
- **Audit-log immutability**: confirmed correctly out of scope — no update/delete method exists
  on `AccountingAuditLogRepository` at all, and plan.md's architecture doc scopes the DB-level
  trigger requirement to `accounting_journal_lines` only, not the audit log.

During targeted live-Postgres verification of the fixes, incidentally found and fixed two more
genuine, production-breaking defects (both invisible to the SQLite test suite, both 100%
reproducible on real Postgres): a zero-line invoice crash (`sum()` over an empty generator
returns int 0, not Decimal, then `.quantize()` fails), and quotation creation being completely
broken (a VARCHAR(30) column receiving a 32-character ISO timestamp). Also self-caught and fixed
a type-mismatch bug in my own tenant-isolation fix while writing its regression test.

All fixes verified via: dedicated regression tests (new + 3 pre-existing tests updated to grant
permissions their now-correctly-enforced code paths require), live Docker/Postgres targeted
checks (17/17 pass), and full re-runs of the Sales/Purchase/Accounting/Inventory suites (4274
tests, zero unrelated failures — one flaky, unrelated, read-only performance test confirmed via
repeated isolated runs to be host-timing noise, not a regression).

Final verdict: READY_FOR_EPIC_9.

## Outcome

- ✅ Impact: ~50 missing-commit defects, 1 tenant-isolation defect, 7 RBAC gaps, 1 migration
  drift, and 2 incidentally-discovered production-breaking Sales bugs found and fixed with the
  smallest safe change each; 2 low-severity defense-in-depth gaps documented, correctly deferred.
- 🧪 Tests: 4 new regression tests + 3 existing tests updated; full Sales/Purchase/Accounting
  suites 100% clean; Inventory 1070/1071 (1 confirmed unrelated flake).
- 📁 Files: 17 production files (12 service files, 3 accounting files, 1 model), 2 new
  migrations, 4 test files.
- 🔁 Next prompts: none — task's explicit stop condition honored, no Epic 9 work started.
- 🧠 Reflection: the SQLite-vs-Postgres commit/constraint-enforcement gap (established in the
  prior verification session) continues to be the single highest-yield place to look for latent
  defects in this codebase; live Postgres verification surfaced two unrelated genuine bugs
  purely as a side effect of exercising an edge case (zero lines) the SQLite suite never
  triggered non-fatally.

## Evaluation notes (flywheel)

- Failure modes observed: initial RBAC/tenant-isolation fixes broke 3 pre-existing tests that
  called service methods directly with unpermissioned/None actors — root-caused as test-setup
  gaps (never needed a permission grant before because no check existed), not regressions in
  the fix; corrected by aligning them with the sibling `approve`-path tests' existing pattern.
- Graders run and results (PASS/FAIL): ruff PASS (100% clean); mypy PASS (zero new errors,
  confirmed via diff); full regression suites PASS (4274/4275 direct, 4275/4275 effective).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): proactively add `company_id` parameters to
  `RolePermissionRepository` and the two journal-line/approval repository methods flagged as
  defense-in-depth gaps, before any future caller reuses them with an unvalidated ID.
