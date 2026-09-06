---
id: 0019
title: Phase 6 verification fix ledger hidden commit
stage: green
date: 2026-08-26
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: /sp.implement
labels: [installments, epic-10, phase-6, accounting-integration, hard-gate, bugfix, atomicity]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/accounting/services/ar_service.py
 - backend/tests/integration/repositories/accounting/test_stage_adjustment_atomicity.py
 - backend/tests/integration/repositories/accounting/test_get_or_create_ledger_no_premature_commit.py
tests:
 - backend/tests/integration/repositories/accounting/test_get_or_create_ledger_no_premature_commit.py (real Postgres) — 3 passed (new)
 - backend/tests/integration/repositories/accounting/test_stage_adjustment_atomicity.py (real Postgres) — 2 passed (strengthened assertion, was "ledger is None or balance==0", now strict "ledger is None")
 - Full Accounting regression (unit+api+repositories+security) — 580 passed, 0 failed
 - Full Installments regression, Phases 0-6 (unit+repository+API+security+performance) — 159 passed, 0 failed
 - ruff check / black --check — clean
tests_run: true
---

## Prompt

Fix the get_or_create_ledger() commit ordering

## Response snapshot

Fixed the mandatory Phase-6 acceptance gap found during the "Phase 6 Accounting Hard-Gate Final Verification" read-only audit (previous turn): `AccountsReceivableService.get_or_create_ledger()` called `CustomerLedgerRepository.create()`, which inherits `BaseRepository.create()`'s internal `db.commit()`. Since `get_or_create_ledger()` is `stage_adjustment()`'s first statement, this committed a new `CustomerLedger` — and anything else already flushed into the same session by a caller — before any validation ran, for any customer without a pre-existing ledger (the common case). Confirmed via a real-Postgres probe matching T114's exact fixture pattern: a caller-staged placeholder `Account` row, flushed before calling `stage_adjustment()`, survived an explicit rollback because the hidden commit inside `get_or_create_ledger()` had already made it durable.

Fix: `get_or_create_ledger()` now builds the new `CustomerLedger` via `db.add()`+`db.flush()` directly, mirroring `PaymentService._get_or_create_customer_ledger()`'s already-correct flush-only pattern — never a committing repository call. The caller commits together with the rest of its own unit of work, exactly as T094's original acceptance criterion required.

Verified safety across all five call sites of `get_or_create_ledger()`:
- `stage_adjustment()` (the reported defect) — now genuinely flush-only until `finalize_adjustment()`.
- `record_sales_invoice()`/`record_sales_credit_note()` — both already end with `finalize_and_publish()`; making ledger creation flush-only strictly improves their own atomicity too (previously the ledger could commit before the ARTransaction/GL side was staged).
- `set_credit_limit()`/`place_credit_hold()` — both call `self._ledgers.update(ledger)` later in the same method, which itself inherits `BaseRepository.update()`'s commit; net externally-visible behavior is unchanged (still one commit, now the ledger creation and its field updates commit together instead of in two separate commits — a strict improvement, not a behavior change any caller could observe).

Strengthened `test_stage_adjustment_atomicity.py`'s forced-failure assertion from `ledger is None or ledger.total_outstanding_base == Decimal("0")` to a strict `ledger is None` — the original looser assertion is exactly what let the defect pass T114 undetected (a prematurely-committed ledger with its default zero balance satisfies the old assertion). Added a new dedicated regression-guard file, `test_get_or_create_ledger_no_premature_commit.py`, with three tests: missing-config failure must not strand a committed ledger, a caller-staged row must not be stranded by a new ledger creation, and the happy path (ledger still created and committed once `finalize_adjustment()` runs) is unaffected.

## Outcome

- ✅ Impact: The Phase 6 Accounting Hard Gate's "no hidden commits" invariant now genuinely holds for `stage_adjustment()`, closing the gap the prior verification pass found. No other staged method (`stage_write_off()`, `stage_customer_payment()`) was affected by this defect — confirmed by reading each one's own ledger-access code, which never calls the committing `get_or_create_ledger()`/`CustomerLedgerRepository.create()` path.
- 🧪 Tests: 5 new/strengthened tests passing. Full Accounting regression 580/580. Full Installments regression 159/159. Zero regressions from changing a method used by 5 call sites across `ar_service.py`.
- 📁 Files: 1 modified service file, 1 modified test file (strengthened assertion), 1 new regression-guard test file.
- 🔁 Next prompts: Phase 6 should be re-verified once more (or this fix accepted as closing the prior BLOCKED finding) before Phase 7 begins.
- 🧠 Reflection: The defect was pre-existing since Epic 8 (identical code in the pre-Phase-6 `adjust_receivable()`), inherited verbatim by Phase 6's extraction — Phase 6 didn't introduce it, but Phase 6's own explicit "no commit anywhere in this method" acceptance criterion made it newly load-bearing. The original T114 test's overly-lenient assertion (accepting a surviving-but-zero-balance row) is a cautionary example of how a forced-failure test can produce a false-positive PASS if its assertion checks an observable side-effect (balance) rather than the row's existence directly.

## Evaluation notes (flywheel)

- Failure modes observed: An overly-lenient test assertion masked a real defect for one full verification cycle.
- Graders run and results (PASS/FAIL): Full Accounting regression PASS (580/580); full Installments regression PASS (159/159); new regression-guard tests PASS (3/3); strengthened atomicity test PASS (2/2, now with strict assertion).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): When writing forced-failure atomicity assertions, prefer checking row existence directly over checking a derived/computed field that could coincidentally match its default value.
