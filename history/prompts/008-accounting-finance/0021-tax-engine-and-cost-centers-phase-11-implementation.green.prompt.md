---
id: 0021
title: Tax Engine and Cost Centers Phase 11 Implementation
stage: green
date: 2026-08-09
surface: agent
model: claude-sonnet-5
feature: 008-accounting-finance
branch: 008-accounting-finance
user: Muhammad Amir
command: /sp.implement
labels: ["accounting", "tax-engine", "cost-centers", "phase-11", "vat", "wht", "reporting"]
links:
  spec: specs/008-accounting-finance/spec.md#23-tax-management
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/accounting/models/tax.py
  - backend/modules/accounting/models/cost.py
  - backend/modules/accounting/models/__init__.py
  - backend/modules/accounting/repositories/tax.py
  - backend/modules/accounting/repositories/cost.py
  - backend/modules/accounting/repositories/gl.py
  - backend/modules/accounting/repositories/payments.py
  - backend/modules/accounting/services/tax_calculator.py
  - backend/modules/accounting/services/tax_service.py
  - backend/modules/accounting/services/cost_center_service.py
  - backend/modules/accounting/schemas/tax.py
  - backend/modules/accounting/schemas/cost.py
  - backend/modules/accounting/dependencies.py
  - backend/modules/accounting/router.py
  - backend/modules/accounting/constants.py
  - backend/modules/accounting/exceptions.py
  - backend/migrations/versions/045_accounting_tax_engine.py
  - backend/migrations/versions/046_accounting_cost_centers.py
  - backend/tests/unit/modules/accounting/test_tax_calculator.py
  - backend/tests/integration/repositories/accounting/test_tax_engine.py
  - backend/tests/integration/api/v1/accounting/test_tax_api.py
  - frontend/src/lib/api/accounting.ts
  - frontend/src/app/(protected)/(accounting)/tax/codes/page.tsx
  - frontend/src/app/(protected)/(accounting)/tax/groups/page.tsx
  - frontend/src/app/(protected)/(accounting)/reports/tax-summary/page.tsx
  - frontend/src/app/(protected)/(accounting)/cost-centers/page.tsx
  - frontend/src/app/(protected)/(accounting)/reports/cost-center-pl/page.tsx
  - specs/008-accounting-finance/tasks.md
tests:
  - backend/tests/unit/modules/accounting/test_tax_calculator.py (8 tests)
  - backend/tests/integration/repositories/accounting/test_tax_engine.py (6 tests)
  - backend/tests/integration/api/v1/accounting/test_tax_api.py (14 tests)
  - full accounting regression suite (444 tests: 443 passed, 1 pre-existing unrelated failure — see PHR 0017)
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
Phase: 11
Phase Name: "Tax Engine & Cost Centers (US11, US12)"

Implement ONLY this phase. Do NOT implement any future phases.

[Full command body specified: pre-implementation reading requirements,
architecture rules (Modular Monolith, Clean Architecture, DDD, Repository
Pattern, Service Layer, DI, SOLID, DRY, KISS, Feature Flags, Soft Delete,
Audit Logging, Multi-Tenant SaaS, RBAC, Company Isolation), accounting
principles, implementation rules, database migration rules, GL posting
rules, API conventions, frontend UX requirements, testing requirements,
validation requirements (formatting, linting, type-checking, tests, Docker
build/compose, migrations, financial validation, app startup, API health),
Docker verification checklist, financial validation checklist, final
quality review against spec/plan/tasks, and a 12-point completion output
format. Full verbatim text preserved in the session's command invocation.]

## Response snapshot

Read spec.md §23 (Tax Management) and §25 (Cost Accounting), plan.md's
"Phase 10: Tax Engine & Cost Centers" section (plan.md's internal
numbering predates the later Cash Management/Payments insertions —
tasks.md's actual "Phase 11" section header is authoritative, same
resolution used in every prior phase this session), data-model.md §2.9
TaxManagement, and tasks.md T224–T246 (23 tasks) in full, plus
research.md Decision 7 (pluggable JurisdictionAdapter — noted as an
extension point, not required by tasks.md's concrete `TaxCalculator`
signature, so not built) and Decision 14 (cost centers optional per
account, `requires_cost_center`/`cost_center_id` already live since
Phase 4 — confirmed via code inspection before writing anything).

**Key design decisions** (documented in module docstrings for
auditability):
- **No `tax_code_id` on `JournalLine`**: tax reports correlate postings to
  a `TaxCode` via that code's own `gl_account_id` (one dedicated account
  per code, per data-model.md), mirroring `GLReportRepository.
  account_balance_query()`'s established account-as-join-key pattern —
  avoids altering the append-only `accounting_journal_lines` table, which
  tasks.md never lists as in scope.
- **VAT summary classification by GL direction, not `applicability`**: a
  BOTH-scoped tax code's own field can't disambiguate an individual
  posting's sales-vs-purchase origin; a credit to a tax account is always
  output tax, a debit is always input tax, regardless of how the code is
  scoped. "Recoverable" input tax is `TaxCode.is_input_tax_recoverable`
  (spec.md §23.6) — Net Payable = Output Tax − recoverable Input Tax.
- **Compound tax**: within a `TaxGroup`, a member coded COMPOUND uses
  `original_base + sum(tax already computed earlier in the group)` as its
  own base, evaluated in `display_order` — standard tax-on-tax semantics.
- **OUT_OF_SCOPE produces no `TaxAmount` line at all** (spec.md: "not
  reportable"); ZERO_RATED/EXEMPT naturally produce a 0.00 line as a
  consequence of a 0%-configured `TaxRate` — no special-casing needed,
  since a real rate lookup at 0% already IS "reportable zero."
- **WHT report reads Phase 10's `Payment.wht_amount` directly** — no
  retroactive `TaxCode` linkage invented for a field that never had one;
  added one new repository method (`find_wht_payments`) to Phase 10's own
  `repositories/payments.py` rather than touching its business logic.
- **`update_tax_rate()`'s "no overlap" validation** auto-closes a
  predecessor open-ended rate (`effective_to = new_effective_from - 1
  day`) when adding a new ongoing rate — the standard "rate change"
  workflow — while still rejecting any other genuine overlap; verified
  live via API test (`test_add_rate_and_reject_overlap`).
- **`Department`/`CostCenter`/`Project`** reference (not FK-constrain)
  `JournalLine.cost_center_id`/etc. — those columns were already bare
  UUID with no FK since Phase 4 (research.md Decision 14); not retrofitted,
  matching the established deferred-FK convention.

**Implemented**: `TaxCode`/`TaxRate`/`TaxGroup`/`TaxGroupLine` and
`Department`/`CostCenter`/`Project` models; 7 repositories; `TaxCalculator`
domain service (T231 — rate resolution, tax-inclusive backing-out,
rounding-rule-aware, group compounding); `TaxService` (T232 — CRUD +
3 reports); `CostCenterService` (T233 — CRUD + 2 P&L reports, added
`cost_center_pl_query()`/`project_pl_query()` to the shared
`GLReportRepository`); 13 Pydantic schemas; 22 new API endpoints;
migrations 045/046 (7 tables); 5 frontend pages + 30 new typed API client
functions.

**Verified `plan.md`'s two PostingEngine acceptance criteria were already
satisfied by Phase 4** rather than re-implementing them: `account.
requires_cost_center` enforcement and rejection of journal lines missing
`cost_center_id` were both already live (Step 4 of `PostingEngine.
_finalize_posting_uncommitted()`), confirmed via a new regression test
(`test_posting_rejects_missing_cost_center_on_required_account`) rather
than assumed.

## Outcome

- ✅ Impact: Phase 11 (Tax Engine & Cost Centers, US11/US12) fully
  implemented — configurable tax codes/rates/groups, tax calculation with
  correct effective-date resolution, VAT/tax-detail/WHT reports, cost
  centers/departments/projects, and Cost Center/Project P&L reporting, all
  built without modifying any prior phase's business logic. Stopped at
  phase boundary; no future-phase work started.
- 🧪 Tests: 28/28 new tests pass (8 TaxCalculator unit, 6 tax-engine
  integration including the phase's own Independent Test — VAT summary
  output exactly equals the sum of posted tax entries, verified across
  3 separate postings — 14 API); full accounting regression 443/444 (the
  1 failure is the pre-existing, already root-caused
  `test_recurring_journal_service.py` test-isolation defect from PHR
  0017 — confirmed identical, unrelated to Phase 11). ruff clean; mypy
  strict clean on all 11 new standalone application files (test-file mypy
  warnings confirmed pre-existing/codebase-wide by diffing against
  Phase 10's own already-shipped test file, which carries 12 identical
  warnings from the same `dict`-fixture convention). `tsc --noEmit` 0
  errors; ESLint 0 errors, only the same pre-existing
  `react-hooks/exhaustive-deps` warning class seen on every prior phase's
  pages.
- 📁 Files: 6 new backend modules (models×2/repositories×2/services×2),
  2 schema files, 2 migrations, 3 test files, 5 frontend pages, plus edits
  to dependencies.py/router.py/constants.py/exceptions.py/gl.py (2 new
  report queries)/payments.py (1 new WHT query)/accounting.ts.
- 🔁 Next prompts: Phase 12 — Multi-Currency & Exchange Rates (US12) is
  the next tasks.md phase (labeled "US12" a second time in tasks.md — a
  pre-existing spec numbering artifact, not something this session
  introduced or needs to resolve).
- 🧠 Reflection: Two acceptance criteria in plan.md's Phase 10 section
  ("Cost center assignment enforced," "PostingEngine rejects journal
  lines missing cost_center_id") described behavior that turned out to
  already exist from Phase 4 — verifying this via direct code inspection
  before writing any new validation logic avoided duplicating an existing,
  working mechanism; the only real gap was the missing regression test
  proving it, which was added.

## Evaluation notes (flywheel)

- Failure modes observed: none in the implemented code — all 28 new
  tests, the full 443-test regression subset, ruff, mypy, tsc, and eslint
  passed on essentially first attempts (one ruff-auto-fixable import-order
  issue in a test file, immediately fixed and re-verified).
- Graders run and results (PASS/FAIL): ruff PASS; mypy strict PASS (11
  new application files, 0 issues; test-file warnings confirmed
  pre-existing via Phase 10 diff); pytest (new, 28 tests) PASS; pytest
  (full accounting regression, 444 tests) PASS 443/444 (1 pre-existing,
  unrelated, per PHR 0017); tsc --noEmit PASS (0 errors); eslint PASS (0
  errors, pre-existing warning class only). Docker/live-PostgreSQL
  verification not attempted this session — prior session (PHR 0020)
  already established the working Docker access path
  (`/Docker/host/bin/docker`) for a future verification pass if requested.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
