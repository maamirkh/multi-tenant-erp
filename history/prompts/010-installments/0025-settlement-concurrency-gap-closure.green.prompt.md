---
id: 0025
title: Settlement concurrency gap closure
stage: green
date: 2026-08-29
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: /sp.implement
labels: ["installments", "settlement", "phase-9", "concurrency", "idempotency", "gap-closure"]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/tests/integration/api/v1/installments/test_settlement_concurrency.py
tests:
 - backend/tests/integration/api/v1/installments/test_settlement_concurrency.py (1 test, run 4x standalone to rule out flakiness, then once more as part of each suite below)
 - Phase-9-specific suite: 34 passed
 - full Installments suite: 261 passed
 - full Accounting suite: 532 passed
---

## Prompt

"Phase 9 — Final Settlement Concurrency Evidence Fix Only": close exactly the `SETTLEMENT CONCURRENCY EVIDENCE GAP` identified during the prior read-only Phase 9 verification pass. Do not start Phase 10, do not redesign production architecture, do not change migrations/API contracts/planning docs/unrelated tests. Add a real-PostgreSQL two-thread/two-session concurrency test for `InstallmentSettlementService.execute()` against the same contract, using the Phase 7 established pattern, directly exercising `execute()` (not `record_collection()` as a substitute). Required proof: exactly one settlement succeeds financially; exactly one Payment/ARTransaction/JournalEntry/InstallmentAllocationReference; no duplicate rows; correct final contract state; deterministic approved loser behavior; no orphan rows from the losing transaction; plus proof that `settlement.execute`'s own idempotency reservation interacts correctly with the `FOR UPDATE` lock under the race — using authoritative `company_id` + Accounting source/type discriminators, never relying only on winning IDs, PK uniqueness, code inspection, or Phase-7 inference. Test-only unless a genuine production defect is exposed (in which case: stop, report, do not fix without approval). Run the new test alone, all Phase-9 tests, full Installments suite, full Accounting suite, with exact counts; confirm Alembic head 071, no Phase-10 files, branch, production-code-unchanged, exact git status; commit only the test if everything passes.

## Response snapshot

Wrote `test_settlement_concurrency.py::TestConcurrentSettlementExecutions::test_exactly_one_of_two_concurrent_settlements_succeeds`, mirroring `test_concurrent_collections.py`'s exact two-thread/two-session-on-shared-`pg_engine` pattern: both threads call `InstallmentSettlementService.execute()` directly against the same contract with the SAME `quoted_amount`/`quoted_as_of_date` (from one shared prior `generate_quote()` call) but DIFFERENT idempotency keys — the realistic two-independent-sessions race, deliberately isolating the proof to the `FOR UPDATE` lock alone (two distinct keys never contend with each other at the reservation step).

Traced the expected outcome by hand before running: winner's commit flips the contract to `COMPLETED`; the loser, blocked on `get_by_id_locked()`, re-reads post-commit and is rejected by `execute()`'s own settleable-status guard (`InstallmentSettlementNotAllowedError`) — deterministic regardless of thread-scheduling order, since the outcome depends only on which commit happens first, not on timing precision. Ran the test standalone 4 times to rule out flakiness (all passed) before treating the trace as confirmed rather than lucky.

Verification queries deliberately follow the Phase-7 file's own two-tier structure: (1) checks anchored to the winning `Payment`/`InstallmentAllocationReference` row's own ids, then (2) fully unconditional, company-wide, non-winning-ID-filtered counts (all `Payment` rows for `company_id`, all `InstallmentAllocationReference` rows for `company_id`, all `posting_source="PAYMENT"` `JournalEntry` rows, all `transaction_type="PAYMENT"`/`source_document_type="Payment"` `ARTransaction` rows) — so a genuinely broken lock leaving behind an untracked duplicate could not hide from the assertions. Added a settlement-specific check beyond the Phase-7 template: queried `InstallmentIdempotencyKey` for `company_id` + `operation="settlement.execute"` company-wide and proved exactly one row exists (the winner's, `COMPLETED`) — the loser's own successfully-reserved (different-key) row is provably absent, not merely unobserved, confirming its failed transaction rolled back cleanly rather than leaving a stranded `IN_PROGRESS` reservation.

No production defect was found — the test passed on every run. Ran the required full verification: new test alone (4x), Phase-9-specific suite (34 passed), full Installments suite (261 passed), full Accounting suite (532 passed) — zero failures anywhere. `git status --porcelain` confirms exactly one new file and zero modifications to any existing file (production or test); Alembic head unaffected (no migration files touched). Committed as a single `test(010)` commit per the master prompt's commit-policy guidance for test/verification-only phases.

## Outcome

- ✅ Impact: Closes the sole remaining Phase 9 verification blocker — `InstallmentSettlementService.execute()` now has direct, real-Postgres, two-session concurrency evidence matching the rigor Phase 7 established for `record_collection()`, including a settlement-specific idempotency-reservation-vs-lock proof that Phase 7's own test doesn't need (single shared idempotency key isn't the relevant race there).
- 🧪 Tests: 1 new test, 0 failures across 4 standalone runs + 3 full-suite runs (34 + 261 + 532 = 827 total test executions, 0 failed, 0 skipped).
- 📁 Files: 1 new test file only; zero production code changes.
- 🔁 Next prompts: Phase 10 (Advanced Lifecycle) remains not started, awaiting explicit Product Owner instruction.
- 🧠 Reflection: The key design choice — using two *different* idempotency keys rather than the same key — was necessary to isolate which mechanism (lock vs. idempotency) actually resolves the race; a same-key test would have proven idempotent replay (already covered elsewhere) rather than genuine concurrent-request serialization, which is what the gap report specifically asked for.

## Evaluation notes (flywheel)

- Failure modes observed: None. No production defect surfaced.
- Graders run and results (PASS/FAIL): ruff PASS (0 errors); pytest PASS (827/827 across all verification runs, including 4 standalone repeats of the new concurrency test itself).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a — gap closed; awaiting Phase 10 authorization.
