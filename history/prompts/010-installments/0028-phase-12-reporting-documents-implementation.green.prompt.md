---
id: 0028
title: Phase 12 Reporting Documents Implementation
stage: green
date: 2026-09-02
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: /sp.implement
labels: ["reporting", "documents", "dashboard", "n+1", "performance"]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/installments/services/reporting_service.py
 - backend/modules/installments/services/document_service.py
 - backend/modules/installments/services/customer_summary_service.py
 - backend/modules/installments/schemas/reports.py
 - backend/modules/installments/repositories/contract.py
 - backend/modules/installments/repositories/schedule.py
 - backend/modules/installments/repositories/allocation_reference.py
 - backend/modules/installments/repositories/late_charge.py
 - backend/modules/installments/repositories/audit.py
 - backend/modules/installments/services/accounting_gateway.py
 - backend/modules/installments/dependencies.py
 - backend/modules/installments/router.py
 - backend/tests/integration/api/v1/installments/test_reporting_service.py
 - backend/tests/integration/api/v1/installments/test_document_service.py
 - backend/tests/integration/api/v1/installments/test_customer_summary_service.py
 - backend/tests/unit/modules/installments/test_dashboard_no_double_count.py
 - backend/tests/unit/modules/installments/test_documents_non_mutating.py
 - backend/tests/unit/modules/installments/conftest.py
 - backend/tests/performance/installments/test_report_pagination.py
 - backend/tests/performance/installments/conftest.py
 - backend/tests/security/installments/test_reports_documents_http.py
 - specs/010-installments/tasks.md
tests:
 - backend/tests/unit/modules/installments/ (full directory)
 - backend/tests/integration/api/v1/installments/ (full directory)
 - backend/tests/security/installments/ (full directory)
 - backend/tests/performance/installments/ (full directory)
---

## Prompt

This PHR closes out Phase 12 — Reporting / Documents (T204–T213) of Epic 10
(Installments), continuing from a prior session that was compacted due to
context limits. The original master "Phase 12 implementation & closure"
prompt (an ~1000+ line structured directive following the repo's standard
47-section `/sp.implement` template — scope lock, authoritative sources,
architecture freeze, financial/idempotency/concurrency hard rules, testing
pyramid, adversarial completeness pass, required final report sections A–S)
was issued in the pre-compaction portion of this session and is not
reproducible verbatim here; its substance is preserved in the session
summary carried into this continuation. The bulk of Phase 12's
implementation (InstallmentReportingService's 8 report types + dashboard,
InstallmentDocumentService, InstallmentCustomerSummaryService, schemas,
router endpoint groups, and most tests) was already written and passing
before this visible turn began.

The verbatim user input actually received in this visible turn consisted of
three brief Urdu status-check questions during long-running background test
suites ("kafi time hogaya hai aur kitna time lagega complete hone mai" /
"aur kitna time lagega" / "kitna time baqi hai" — "it's taking a while, how
much longer" asked three times across different background runs), answered
each time with an elapsed-time-based estimate. No other direct user
instruction was given in this visible turn; work continued autonomously per
the standing Phase 12 closure mandate carried over from the compacted
portion of the session.

## Response snapshot

Diagnosed and fixed the one item left open at the point of compaction: T213's
performance test suite was failing all 4 tests with a
`ForeignKeyViolation` on `installment_contracts.active_schedule_version_id`.
Root cause: the test's bulk-seed function inserted `InstallmentContract` rows
before `InstallmentScheduleVersion` rows despite a circular FK pair between
the two tables. Fixed by inserting contracts with `active_schedule_version_id
= NULL` first, then schedule versions (validly referencing the now-existing
contracts), then a bulk `UPDATE ... FROM VALUES`-style parameterized update
(via SQLAlchemy Core `update(Model.__table__)` + `bindparam`) to backfill the
FK — required working around two further SQLAlchemy 2.0 ORM-bulk-update
pitfalls (`synchronize_session` requirement, then "ORM Bulk UPDATE by Primary
Key" auto-detection triggering on an ORM-mapped `update()` target, resolved
by targeting the Core `__table__` instead of the ORM class). A second,
genuine test-assertion bug surfaced once seeding worked: the due-report
query-count test asserted `total == _CONTRACT_COUNT * _LINES_PER_CONTRACT`,
but only the first of each contract's 3 schedule lines is actually due
"today" (the other two are 30/60 days out) — corrected the expected total to
`_CONTRACT_COUNT`.

With T213 green, ran the previously-unexecuted `test_reports_documents_http.py`
(8 live-HTTP tests, all passing), then a full Installments regression sweep
(408 passed). Lint/format-checked and mypy-checked every file in the phase's
diff, scoped strictly to touched files (pre-existing debt in ~100 untouched
files elsewhere in the codebase was left alone). Fixed 3 genuine mypy errors
in Phase 12's own new code (two `Sequence[Row]`→`list[tuple]`/`dict`
coercions needing explicit comprehensions instead of bare `list()`/`dict()`
calls, one missing `dict[str, Any]` return-type argument).

During a self-directed adversarial re-review of the reporting service against
plan.md §25's explicit N+1 prohibition, found and fixed one more real defect:
`InstallmentReportingService._sum_written_off_balance()` (feeding the
dashboard's `written_off_balance` KPI) called
`get_default_writeoff_report(company_id, skip=0, limit=1000)` — a
per-written-off-contract loop (2+ queries each) disguised as a single method
call, invisible to T213's existing tests because their seed data contains
zero WRITTEN_OFF contracts. Fixed by adding
`InstallmentScheduleRepository.sum_schedule_outstanding_for_statuses()`, a
status-parameterized generalization of the existing
`sum_schedule_outstanding_for_company()` aggregate query, and pointing the
dashboard's written-off-balance computation at it directly — one SQL
statement instead of an unbounded per-contract loop. Added a new integration
test (`test_written_off_balance_reflects_a_written_off_contract_without_per_contract_query`)
proving the figure's correctness post-fix.

A final full regression run then surfaced two failures
(`test_due_report_includes_line_due_today`,
`test_due_report_page_is_fast_and_query_count_is_bounded`) that were absent
from every prior run. Root-caused conclusively (not guessed) via a direct
Python check: the test server's local clock (PKT, UTC+5) had crossed into
the next calendar day while `get_business_date()` — correctly, per
FR-INST-115's documented UTC convention — still read the prior day. The
shared Phase-7-era test fixture `build_active_contract_with_schedule()`
seeds "due today" using local `date.today()`, creating a latent,
non-deterministic flake near the local/UTC midnight boundary that Phase 12's
own new exact-day-boundary assertions were the first to expose. Fixed
narrowly within Phase 12's own two new test files only (no edit to the
shared, cross-phase `conftest.py`) by monkeypatching
`reporting_service.get_business_date` to the same `date.today()` value the
seed fixture used, making both tests deterministic regardless of wall-clock
timezone skew.

Re-ran the full Installments regression suite (`tests/unit/modules/installments/`,
`tests/integration/api/v1/installments/`, `tests/security/installments/`,
`tests/performance/installments/`) end to end: **409 passed, 0 failed**.
Marked T204–T213 `[x]` in `specs/010-installments/tasks.md`. Confirmed via
`git status`/`git diff --stat` that the diff is scoped exactly to Phase 12's
intended file set — 8 modified files, 13 new files, zero migrations, zero
unrelated edits. Confirmed zero secrets, zero write/mutation calls in the
three new read-only services (`grep` for `.commit()`/`.flush()`/`.add()`/
`.delete()` returned nothing). Cross-checked the implementation against
`specs/010-installments/contracts/installments-api.yaml` (all 6 new GET
routes match path, permission, and operation-class exactly) and against
plan.md §25's truth-source table and §27's document architecture (both
followed exactly, including the deliberate design choice to source the
write-off report's amount from Installments' own immutable schedule rather
than a since-zeroed Accounting `ARTransaction.outstanding_amount`).

## Outcome

- ✅ Impact: Phase 12 (Reporting/Documents, T204–T213) closed. Two real
  production defects found and fixed by this phase's own review discipline
  (due/overdue/aging pagination-before-filtering; dashboard written-off-KPI
  N+1), plus one test-infrastructure flake (UTC/local midnight boundary)
  made deterministic without touching shared cross-phase fixtures.
- 🧪 Tests: 409 passed, 0 failed, 0 skipped across the full Installments
  suite (unit + integration + security + performance).
- 📁 Files: 8 modified, 13 new (see `files:` above); `specs/010-installments/tasks.md`
  updated to mark T204–T213 complete; zero new Alembic migrations.
- 🔁 Next prompts: Phase 13 (Frontend) is next per tasks.md's phase
  ordering, but is explicitly NOT started here per the master prompt's
  standing "stop after closure" rule.
- 🧠 Reflection: The two production defects both shared a root cause —
  treating a *computed* classification (due-state, outstanding-for-status)
  as if it were a stored, SQL-filterable column. Worth carrying forward as a
  standing review heuristic for any future report/KPI work in this module.

## Evaluation notes (flywheel)

- Failure modes observed: SQLAlchemy 2.0's ORM-bulk-update auto-detection
  ("ORM Bulk UPDATE by Primary Key") silently activates on `update(ORMClass)`
  + executemany params even when not intended, requiring the Core
  `__table__` target instead — worth documenting as a repo-wide gotcha.
- Graders run and results (PASS/FAIL): full regression suite — PASS (409/409).
- Prompt variant (if applicable): n/a — continuation of a pre-existing
  master closure prompt from a compacted session.
- Next experiment (smallest change to try): consider migrating the shared
  `build_active_contract_with_schedule()` fixture's "today" source from local
  `date.today()` to the same UTC convention `get_business_date()` uses, as a
  cross-phase test-infrastructure hardening pass (out of Phase 12's own
  scope, flagged here for future consideration).
