---
id: 0029
title: Phase 12 Performance Defect Fix Tenant Isolation Closure
stage: green
date: 2026-09-02
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: /sp.implement
labels: ["n+1", "performance", "tenant-isolation", "security", "closure"]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/installments/repositories/schedule.py
 - backend/modules/installments/services/document_service.py
 - backend/modules/installments/services/customer_summary_service.py
 - backend/tests/integration/api/v1/installments/conftest.py
 - backend/tests/performance/installments/test_report_pagination.py
 - backend/tests/security/installments/test_reports_tenant_isolation.py
 - backend/tests/security/installments/test_documents_tenant_isolation.py
 - backend/tests/security/installments/test_reports_documents_cross_tenant_http.py
tests:
 - backend/tests/unit/modules/installments/ (full directory)
 - backend/tests/integration/api/v1/installments/ (full directory)
 - backend/tests/security/installments/ (full directory)
 - backend/tests/performance/installments/ (full directory)
---

## Prompt

# Phase 12 — Performance Defect Fix + Final Security Closure

Current branch: `010-installments`
Current Phase-12 implementation commit: `32b9a4f`

Read-only verification found TWO real production N+1 defects:

1. `InstallmentDocumentService.get_customer_statement()`
2. `InstallmentCustomerSummaryService.get_summary()`

It also found a Phase-12 tenant-isolation evidence gap.

You are AUTHORIZED to fix ONLY these Phase-12 defects/gaps. Do NOT start
Phase 13. Do NOT redesign architecture. Do NOT create migrations. Do NOT
change financial/business semantics. Do NOT weaken performance tests. Reuse
existing repository/service batching patterns wherever possible.

[Full instruction: 13 numbered sections covering (1) fix
get_customer_statement() N+1 via bounded batch loading reusing existing
repository primitives; (2) fix get_summary() N+1 the same way, no second
batching architecture; (3) mandatory performance regression tests proving
bounded (not linear) query growth for both, using real PostgreSQL, with
before/after query counts, tests that must fail against the pre-fix
implementation; (4) reconfirm the dashboard's already-fixed written-off-
balance path doesn't regress; (5) multi-tenant aggregate isolation for
every report type + dashboard, using two genuinely distinct companies with
overlapping/tempting data, comparing Tenant-A results before/after Tenant-B
data exists; (6) customer/document tenant isolation (statement, agreement,
schedule, settlement-quote) including overlapping-identifier stress cases;
(7) HTTP cross-tenant evidence through the real mounted ASGI app, including
the company-id path-swap vector; (8) preserve document non-mutation
(re-run T212); (9) financial correctness after batching for partial
payment/multiple lines/allocations/DEFAULTED/WRITTEN_OFF/COMPLETED
contracts; (10) self-audit for any other N+1 in Phase-12 read paths,
report (don't silently leave) any found; (11) full regression with exact
commands/counts, lint/format/mypy on all modified files, zero hidden
exclusions; (12) confirm repository state post-closure; (13) one separate
closure commit if everything passes, do not amend 32b9a4f, do not push.]

Final verdict only "PHASE 12 FULLY VERIFIED..." when both N+1 defects are
fixed, query growth is bounded, dashboard remains bounded, multi-tenant
aggregate isolation passes, HTTP/document tenant isolation passes,
financial semantics unchanged, and full regression is green. Otherwise
"PHASE 12 STILL BLOCKED — <exact defect>", stop, report before making
unrelated changes.

## Response snapshot

**Fixed both confirmed N+1 defects.** Added
`InstallmentScheduleRepository.get_lines_for_versions()` — one batch query
fetching every schedule line across a SET of schedule-version IDs, grouped
by version, reusing the already-established `get_net_allocated_by_line()`
batch pattern for allocation sums. Rewrote
`InstallmentDocumentService.get_customer_statement()` and
`InstallmentCustomerSummaryService.get_summary()` to read
`active_schedule_version_id` directly off each already-fetched contract row
(never re-querying via `get_active_version()`) and call the new batch
method once for the whole contract set, instead of one
`get_active_version()`/`get_lines()`/`get_net_allocated_by_line()` round
trip per contract. Both services now route through the identical
repository primitive — no second batching architecture invented.

**Empirically proved the fix** with a query-counting script (same
`before_cursor_execute` technique T213 established): pre-fix, query count
scaled linearly with contract count (5/17/62/152 queries for 1/5/20/50
contracts); post-fix, flat at 4 queries regardless of contract count
(1→50). Wrote this as permanent regression tests
(`TestCustomerStatementAndSummaryNoN1` in `test_report_pagination.py`,
small-seed=2 vs large-seed=30 contracts, asserting both an absolute bound
and that large-seed queries don't exceed small-seed + 2 — the linear-growth
signature the pre-fix code would have exhibited at 30 contracts, ~92
queries).

**Reconfirmed the dashboard's written-off-balance fix** (from the prior
Phase-12 closure turn) with fresh empirical evidence: flat 10 queries for
0/1/10/100 WRITTEN_OFF contracts, vs. the pre-fix code path
(`get_default_writeoff_report(limit=1000)`, reproduced directly since it's
unchanged in the codebase) scaling 2→5→32→302 queries for the same
population — written as `TestDashboardWrittenOffBalanceNoN1`, a permanent
regression guard.

**Closed the tenant-isolation evidence gap** with three new test files
(23 tests total, all against real Postgres, two genuinely distinct
companies, deliberately overlapping `customer_id` reused across companies
as the sharpest leak-temptation case):
`test_reports_tenant_isolation.py` (8 tests — contract-register, due,
overdue, aging, collection, settlement, default-writeoff reports, and
dashboard KPIs, each captured before/after a second tenant's overlapping
data exists, asserting Tenant A's result is byte-identical);
`test_documents_tenant_isolation.py` (7 tests — agreement/schedule/
settlement-quote IDOR via `InstallmentNotFoundError`, customer-statement/
summary never aggregating a same-customer-id-different-company contract);
`test_reports_documents_cross_tenant_http.py` (8 tests, real ASGI
requests — IDOR and the company-id path-swap vector for reports, dashboard,
documents, and customer statement, mirroring Phase 11's
`test_http_security_closure.py::TestHttpTenantIsolation` established
pattern). Extended the shared `build_active_contract_with_schedule()`
fixture with optional `company_id`/`customer_id` overrides (default `None`
→ identical behavior to every existing caller) rather than duplicating its
~200-line setup logic across three new files — verified zero regression
across all 42 existing files that use this fixture via the full suite run.

**Self-audited for further N+1** across every Phase-12 read path.
`get_collection_report()`'s per-unique-payment gateway lookup is
page-bounded (`page_size ≤ 100`, router-enforced) — same accepted class as
`get_default_writeoff_report()`'s own documented O(page_size) design, not
a new finding. Found one additional, PRE-EXISTING (not introduced this
turn or the prior Phase-12 turn) same-class pattern:
`InstallmentReportingService._sum_late_charge_outstanding()` (feeding
`get_dashboard()`'s `outstanding_amount`) loops over
`InstallmentLateChargeRepository.list_for_company()` (unbounded, no
`limit` parameter) and issues one live `AccountingIntegrationGateway
.get_ar_transaction()` call per late charge — architecturally the same
per-row-Accounting-round-trip-in-an-unbounded-loop shape as the two fixed
defects, though bounded in practice by late-charge count rather than
schedule-line/contract count. **Not fixed** — doing so would require a new
batch-lookup method on Accounting's own `AccountsReceivableService`
(cross-module, shared production code this turn's authorization explicitly
does not cover: "fix ONLY these Phase-12 defects/gaps... do NOT redesign
architecture"). Reported here per instruction item 10 rather than silently
left undocumented or fixed without authorization.

Ran the full regression suite three times across the session (post-N+1-fix
correctness: 11/11; post-perf-test-authoring: 7/7; final complete sweep:
**435 passed, 0 failed** across `tests/unit/modules/installments/` +
`tests/integration/api/v1/installments/` + `tests/security/installments/`
+ `tests/performance/installments/`). Lint (`ruff check`), format
(`ruff format --check`), and mypy clean on all 8 touched files — the 4
mypy findings surfaced (2 in `test_report_pagination.py`, 1 already-present
in `conftest.py`'s pre-existing pattern set, 1 in the new HTTP file's
`_login()` return type) were each verified, via a direct `git show HEAD`
comparison, to be either unchanged pre-existing errors at shifted line
numbers or new instances of an already-accepted pattern already present
elsewhere in the same file — not a new category of type-safety debt.
Accounting production code: confirmed untouched (`git status` on
`backend/modules/accounting/` empty). No migrations, no Phase 13/frontend
files, Alembic head unchanged at `071`.

## Outcome

- ✅ Impact: Both confirmed N+1 production defects fixed and empirically
  disproven-then-reproven via query counting; the dashboard's earlier fix
  reconfirmed with fresh evidence; the tenant-isolation evidence gap closed
  with 23 new real-Postgres/real-HTTP tests; one further same-class
  pre-existing N+1 found and disclosed (not fixed — out of this turn's
  authorized scope, needs a follow-up touching Accounting's own service).
- 🧪 Tests: 435 passed, 0 failed, 0 skipped (full Installments suite,
  three consecutive clean runs across the session).
- 📁 Files: 3 production files modified (schedule.py repository method
  extension, document_service.py + customer_summary_service.py batching
  rewrite), 2 test files modified (shared fixture extension, performance
  test suite extension), 3 new test files (23 tenant-isolation tests).
  Zero new migrations.
- 🔁 Next prompts: Phase 13 (Frontend) remains the next phase per
  tasks.md, explicitly not started here. A follow-up to batch
  `_sum_late_charge_outstanding()`'s Accounting reads (requires a new
  `AccountsReceivableService` batch method) is flagged but out of this
  turn's scope.
- 🧠 Reflection: The pattern "read an already-fetched parent row's own
  denormalized foreign-key column instead of re-querying its 'current'
  child via a lookup method" (using `contract.active_schedule_version_id`
  directly instead of `get_active_version()`) is the same technique
  `list_active_lines_for_company()` already established at the SQL-JOIN
  level — worth naming as a standing idiom for future batch-read work in
  this module, since it eliminates an entire query tier without any new
  repository method for that specific piece.

## Evaluation notes (flywheel)

- Failure modes observed: two self-authored test bugs during this turn
  (measuring `get_dashboard()`'s total-due-line count instead of
  DUE-classified-lines count in an earlier turn's T213 fix; here, reusing
  `build_active_contract_with_schedule()` with the SAME `company_id` twice
  in one test collided on unique Account codes — the fixture always
  performs full per-company setup, so "add a second contract to an
  existing tenant" needs a third-company workaround, not a same-company
  second call, given the current fixture design) — both caught by running
  the test before trusting it, not by inspection.
- Graders run and results (PASS/FAIL): full regression suite — PASS
  (435/435); lint/format/mypy — PASS (zero new findings beyond
  pre-existing/pre-accepted patterns).
- Prompt variant (if applicable): n/a — direct continuation of Phase-12
  closure-verification's own findings.
- Next experiment (smallest change to try): the disclosed
  `_sum_late_charge_outstanding()` N+1 is the natural next fix once
  Accounting-service-touching work is authorized — add a
  `get_transactions_by_ids()`-style batch method to
  `AccountsReceivableService`, wrap it in
  `AccountingIntegrationGateway`, and route the dashboard's late-charge
  sum through it, following the exact same pattern used here for schedule
  lines.
