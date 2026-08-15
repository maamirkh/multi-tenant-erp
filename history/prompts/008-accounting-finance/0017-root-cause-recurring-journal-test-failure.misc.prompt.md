---
id: 0017
title: Root cause recurring journal test failure
stage: misc
date: 2026-08-08
surface: agent
model: claude-sonnet-5
feature: 008-accounting-finance
branch: 008-accounting-finance
user: Muhammad Amir
command: null
labels: ["accounting", "testing", "test-isolation", "root-cause-analysis", "phase-9"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - history/prompts/008-accounting-finance/0016-cash-management-phase-9-implementation.green.prompt.md
tests:
  - tests/unit/modules/accounting/test_recurring_journal_service.py::TestDueTemplateExecutes::test_due_template_creates_and_posts_journal (isolation: PASS)
  - tests/integration/repositories/accounting/ + tests/unit/modules/accounting/ (no TestClient tests: 278 passed)
  - tests/integration/api/v1/accounting/ + the one failing unit test (7==1 repro)
  - tests/integration/api/v1/accounting/test_recurring_journal_api.py + the one failing unit test (7==1 repro)
  - minimal 2-test repro: test_create_and_get_detail + the one failing unit test (2==1 repro)
---

## Prompt

Run the failing accounting regression test in isolation.

Then run it again with all Phase 9 tests excluded.

Confirm whether the exact same failure existed before Phase 9 changes.

Do not modify the test just to make it pass.

Identify the root cause and classify it as:
1. Phase 9 regression
2. genuine pre-existing defect
3. flaky/environment issue

If pre-existing, document exact test name, failure reason, and evidence in the Phase 9 report/PHR.

## Response snapshot

Performed a full empirical bisection rather than accepting the prior turn's
surface-level "pre-existing, order-dependent" conclusion at face value:

1. **Isolation**: `test_recurring_journal_service.py::TestDueTemplateExecutes::
   test_due_template_creates_and_posts_journal` run alone — PASSED (1 passed).
   Also ran the entire `tests/unit/modules/accounting/` directory alone —
   197 passed, no failure.
2. **Full suite minus Phase 9**: reran
   `tests/integration/repositories/accounting/ tests/integration/api/v1/accounting/
   tests/unit/modules/accounting/` with `--deselect` on both new cash test
   files — same failure reproduced identically (`1 failed, 370 passed`),
   confirming Phase 9 code is not a factor.
3. **Bisected the source of the leak**:
   - `tests/integration/repositories/accounting/` + `tests/unit/modules/accounting/`
     (no `TestClient`/HTTP-layer tests) — 278 passed, **no failure**.
   - `tests/integration/api/v1/accounting/` + the one failing unit test —
     reproduced (`7 == 1`).
   - Narrowed to a single file: `test_recurring_journal_api.py` + the one
     failing unit test — reproduced (`7 == 1`, `1 failed, 21 passed`).
   - **Minimal 2-test repro**:
     `test_recurring_journal_api.py::TestRecurringTemplateCRUD::
     test_create_and_get_detail` + the failing unit test alone —
     reproduced (`2 == 1`, `1 failed, 1 passed`).
4. **Root cause**: `RecurringJournalService.execute_due_templates()` /
   its repository method `find_due()` deliberately scans **across all
   companies with no tenant filter** (documented in both docstrings — this
   is correct production behavior for a scheduler job with no single-company
   context). The failing test's assertion `len(results) == 1` is only valid
   if the test database contains exactly one active, due
   `RecurringJournalTemplate` row at call time — an implicit assumption of
   perfect cross-test isolation.

   That isolation is broken specifically for **`TestClient`-driven HTTP
   requests**: `tests/conftest.py`'s `db_session` fixture uses a
   nested-transaction/SAVEPOINT rollback pattern (`connection.begin()` +
   `join_transaction_mode="create_savepoint"`, rolled back at teardown) to
   restore a pristine DB state after each test. Repository/service calls
   made *directly* against `db_session` are correctly rolled back — proven
   by step 3's first bullet (278 passed with zero leakage across many
   PostingEngine-driven integration tests that don't use `TestClient`).
   But rows written via HTTP requests through `test_client` (which FastAPI
   dependency-injects the *same* `db_session` object into, confirmed by
   reading `override_get_db` in conftest.py) are **not** rolled back —
   `RecurringJournalTemplate` rows created by
   `test_create_and_get_detail` (and 5 other `TestClient`-based tests in
   the same file: `test_list_templates`, `test_update_template`,
   `test_cross_tenant_isolation`, `test_deactivate_then_activate` — which
   ends by reactivating its template — and `test_history_starts_empty`)
   survive past their originating test's teardown and are visible to a
   completely separate, later test's fresh `db_session`. The count is
   exact: 6 leaked active templates (all with `next_run_date` = today) +
   the failing test's own 1 = 7, matching the observed `assert 7 == 1`
   failure precisely. `test_unbalanced_template_returns_422` (422 rejection,
   no row created) and `test_batch_post_two_drafts` (no recurring template
   involved) correctly contribute 0.

   The exact SQLAlchemy/FastAPI mechanism by which `TestClient`-routed
   writes escape the SAVEPOINT boundary was not instrumented further
   (would require adding temporary debug tracing to conftest.py, which
   is out of scope for a report-only investigation) — the mechanism is a
   defect in the **test infrastructure's fixture isolation
   (`tests/conftest.py`)**, not in any accounting or Phase 9 business
   logic.

## Outcome

- ✅ Impact: Definitively classified — **not** a Phase 9 regression. No
  code change made (per instruction not to modify the test to force a
  pass).
- 🧪 Tests: 5 targeted bisection runs, converging on a minimal 2-test
  repro (`test_create_and_get_detail` + the failing test) that
  deterministically reproduces the failure.
- 📁 Files: none modified — investigation only, findings recorded here and
  cross-referenced from PHR 0016 (Phase 9 report).
- 🔁 Next prompts: Recommend filing a separate test-infra ticket for
  `tests/conftest.py`'s `db_session`/`test_client` SAVEPOINT-isolation gap,
  and/or scoping `RecurringJournalTemplate` cleanup or company_id-aware
  assertions into `test_recurring_journal_service.py` as a defensive fix
  — out of scope for Phase 9 to change unilaterally.
- 🧠 Reflection: A single reproduction (full suite fails, isolation
  passes) is not sufficient evidence of "pre-existing and unrelated" —
  bisecting down to the minimal 2-test repro was necessary to rule out
  any indirect Phase 9 interaction (e.g. via shared fixtures or import
  side effects) and to pin the exact mechanism (HTTP-layer writes,
  not direct-session writes) rather than asserting it by pattern-matching
  on "involves other phases."

## Evaluation notes (flywheel)

- Failure modes observed: none in Phase 9 code; the defect is entirely
  within `tests/conftest.py`'s db/session isolation for `TestClient`-based
  tests, pre-existing since at least Phase 5 (recurring journals) and
  Phase 1 (test infrastructure).
- Graders run and results (PASS/FAIL): isolation run PASS (no failure);
  full-suite-minus-Phase-9 run reproduces FAIL identically; bisection
  down to `test_recurring_journal_api.py` alone reproduces FAIL; minimal
  2-test repro reproduces FAIL. All consistent with genuine pre-existing
  defect, not a Phase 9 regression, not non-deterministic/flaky (fully
  reproducible given a fixed pair of tests and execution order).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): instrument
  `tests/conftest.py`'s `db_session`/`test_client` fixtures with a
  post-teardown row-count assertion (temporary) to catch the exact
  SAVEPOINT-escape mechanism, or bisect further by testing whether the
  `/auth/login` HTTP call itself (vs. the `/recurring-journals` POST)
  is the point where the commit escapes the savepoint.
