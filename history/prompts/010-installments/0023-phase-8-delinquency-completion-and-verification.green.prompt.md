---
id: 0023
title: Phase 8 delinquency completion and verification
stage: green
date: 2026-08-29
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: none
labels: [installments, epic-10, phase-8, delinquency, late-charges, aging, due-state, concurrency, accounting-integration, postgresql, verification]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/tests/integration/api/v1/installments/test_late_charge_atomicity.py
 - backend/tests/integration/api/v1/installments/test_concurrent_collection_vs_late_charge.py
 - backend/tests/integration/repositories/installments/test_schedule_immutability.py
 - specs/010-installments/tasks.md
tests:
 - backend/tests/unit/modules/installments/ (142 passed)
 - backend/tests/integration/api/v1/installments/test_late_charge_atomicity.py::TestLateChargeAtomicityLayerB (2 tests)
 - backend/tests/integration/api/v1/installments/test_concurrent_collection_vs_late_charge.py::TestConcurrentCollectionVsLateCharge (1 test)
 - Phase 8 closure tests (6 files, 13 tests) — full run
 - full suite: backend/tests/integration/api/v1/installments/ + integration/repositories/installments/ + unit/modules/installments/ (232 passed after immutability-whitelist fix)
 - full suite: backend/tests/unit/modules/accounting + integration/api/v1/accounting + integration/repositories/accounting + security/accounting (583 passed)
---

## Prompt

Turn 1 (after a cancelled `/resume`): "continue"

Turn 2 (after I reported the environment state and asked how to proceed): "done, go ahead" — in response to my question about whether to enable Docker Desktop's WSL integration so I could run the real-Postgres suite, versus leaving Phase 8 unverified.

(Full context: this was a resumed session with no carried-over conversation history — only the git working-tree snapshot and CLAUDE.md/tasks.md were available. I had to reconstruct what was in flight from `git status`, `tasks.md`, and reading the actual code before taking any action.)

## Response snapshot

Reconstructed session state from scratch: `git status` showed Phase 8 (Delinquency, tasks.md T138–T153) already substantially implemented on disk from an earlier, now-lost session — `DueStateCalculator`, `InstallmentAgingCalculator`, `InstallmentLateCharge` model/repository, `InstallmentDelinquencyService` (`apply_late_charge()`/`waive_late_charge()`), delinquency schemas, dependency wiring, and 6 of 8 Phase-8 test files — but `tasks.md` still showed the whole phase unchecked and no PHR existed for it. Read every touched/new file (`delinquency_service.py`, `late_charge.py` model+repo, the `outstanding_service.py`/`collection_service.py`/`allocation_policy.py` diffs that thread late-charge AR into `assert_zero_outstanding()` and oldest-first collection allocation) to confirm the implementation was coherent and internally consistent before trusting it, rather than assuming the working tree was correct.

Identified exactly two gaps against tasks.md: T152 (Layer-B cross-module late-charge atomicity, real-Postgres forced-failure test) and T153 (Concurrency Test D — collection vs. late-charge race). Wrote both, mirroring the established Phase 6/7 patterns (`test_stage_adjustment_atomicity.py` for the stage/finalize replication technique, `test_collection_atomicity.py` for the Layer-B second-independent-connection verification shape, `test_concurrent_collections.py` for the two-thread real-Postgres race harness):
- `test_late_charge_atomicity.py`: replicates `apply_late_charge()`'s exact staged sequence (`stage_adjustment()` → stage `InstallmentLateCharge`/audit/outbox → inject failure before `finalize_adjustment()`), proves `JournalEntry`/`ARTransaction`/`CustomerLedger` balance/`InstallmentLateCharge`/`InstallmentAuditLog`/outbox event are all simultaneously absent post-rollback, plus a normal-path companion test.
- `test_concurrent_collection_vs_late_charge.py`: races `record_collection()` (paying exactly the schedule amount) against `apply_late_charge()` on the same single-line contract via the shared `FOR UPDATE` lock on `InstallmentContract`. Proved both possible lock orderings are safe: collection-wins → late charge loses against the now-COMPLETED contract with the documented `InstallmentActivationFailedError` guard; late-charge-wins → the collection sees the fresh late-charge AR as additional outstanding and correctly withholds completion (stays ACTIVE). Asserted the authoritative invariant directly against a third, independent verification session: a contract is never observed COMPLETED with an open, non-waived late-charge AR outstanding.

Environment blocker: this WSL session had no Docker/Postgres reachable (port 5432 refused, Docker Desktop's WSL integration not enabled for this distro). Asked the user how to proceed rather than either fabricating results or silently leaving Phase 8 unverified; user chose to enable Docker Desktop's WSL integration for the Ubuntu distro. After confirmation, verified `docker ps` reached the existing `erp-system-db-1` container. Hit a second environment issue: the Windows-native `.venv/Scripts/python.exe` (invoked via WSL interop) does not inherit `export`ed WSL environment variables by default, so `tests/conftest.py`'s `os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test_dummy")` dummy fallback was winning even after exporting the real `DATABASE_URL` — fixed by also exporting `WSLENV=DATABASE_URL`, which explicitly forwards that variable across the WSL/Windows interop boundary.

Ran, in order: unit tests (142 passed) → the 6 Phase-8 closure test files including the 2 new ones (13 passed) → full Installments regression (`integration/api/v1/installments` + `integration/repositories/installments` + `unit/modules/installments`), which surfaced one real regression: `test_schedule_immutability.py::test_repository_only_exposes_the_documented_read_and_create_methods` failed because the already-present (pre-session) `InstallmentScheduleRepository.get_line_by_id()` (added to support `apply_late_charge()`'s line lookup) wasn't in that test's hardcoded whitelist. Read the test's own docstring/intent — it's a structural guard against *mutating* methods being added to the immutable-schedule repository (a `forbidden_substrings` check for `update`/`delete`/`edit`/`modify`/`set_` is the actual immutability proof, in the sibling test in the same file), not a closed list of reads — so added `"get_line_by_id"` to the documented-methods set rather than removing the method. Re-ran: full Installments suite 232/232 passed; full Accounting suite (unit+integration+repository+security) 583/583 passed — zero regressions.

Marked tasks.md T138–T153 `[x]`. No production code was changed beyond the one-line test whitelist fix — everything else this session was net-new test files plus verification.

## Outcome

- ✅ Impact: Phase 8 (Delinquency) is now fully implemented, tested, and verified against real PostgreSQL — due-state derivation, aging buckets, late-charge application/waiver as genuine collectible/reversible AR (never GL-only), late-charge collectibility via the unmodified oldest-first allocation policy, and the collection-vs-late-charge concurrency race are all proven. Per the Phase 8 exit gate's own wording, Phase 9 (Settlement) is now clear to start.
- 🧪 Tests: 142 unit + 232 full Installments integration/unit + 583 full Accounting regression = 957 passed, 0 failed, across three separate real-Postgres runs (one regression found and fixed mid-session).
- 📁 Files: 2 new test files (`test_late_charge_atomicity.py`, `test_concurrent_collection_vs_late_charge.py`), 1 test file fixed (`test_schedule_immutability.py`, whitelist addition only), `tasks.md` checkboxes updated. No production code touched this session — Phase 8's actual implementation code predates this session and was reviewed, not written, here.
- 🔁 Next prompts: Decide whether to commit this session's work (2 new test files + 1 whitelist fix + tasks.md checkboxes, on top of the pre-existing uncommitted Phase 8 implementation) as one or more commits; then start Phase 9 (Settlement, T154–T165).
- 🧠 Reflection: Two environment-plumbing issues (Docker Desktop WSL integration not enabled; WSLENV needed to forward `DATABASE_URL` from bash to the Windows-native venv's `python.exe`) cost more turns than the actual test-writing. Neither was guessable from the repo alone — both required investigating the actual `OperationalError` message (which named the wrong user, "test", pointing at `tests/conftest.py`'s dummy fallback rather than a credentials typo) rather than assuming the first plausible cause (e.g. wrong password in `.env`).

## Evaluation notes (flywheel)

- Failure modes observed: one real (if narrow) test-whitelist regression from a pre-existing, out-of-session code change (`get_line_by_id()`); two environment/tooling failures (Docker WSL integration, WSL→Windows env-var forwarding) that had nothing to do with the code under test.
- Graders run and results (PASS/FAIL): 4 real-Postgres pytest runs — PASS (142/142, 13/13, 232/232 [after fix], 583/583).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
