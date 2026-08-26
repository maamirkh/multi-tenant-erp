---
id: 0017
title: Epic 10 Phase 5.5 idempotency primitive
stage: green
date: 2026-08-26
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: /sp.implement
labels: [installments, epic-10, phase-5-5, idempotency, concurrency, hard-gate, postgresql-on-conflict]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/installments/models/idempotency.py
 - backend/modules/installments/models/__init__.py
 - backend/modules/installments/services/idempotency_service.py
 - backend/tests/unit/modules/installments/test_idempotency_reservation_no_abort.py
 - backend/tests/integration/repositories/installments/test_idempotency_concurrency.py
 - backend/tests/integration/repositories/installments/test_idempotency_scoping.py
 - specs/010-installments/tasks.md
tests:
 - backend/tests/unit/modules/installments/test_idempotency_reservation_no_abort.py (real Postgres, single-session) — 2 passed
 - backend/tests/integration/repositories/installments/test_idempotency_concurrency.py (real Postgres, two-session races) — 3 passed, re-run 4x total for flake-check, stable every time
 - backend/tests/integration/repositories/installments/test_idempotency_scoping.py (real Postgres) — 3 passed
 - full Installments module regression (unit+repository+API+security, all phases 0-5.5) — 140 passed, 0 failed
---

## Prompt

# Epic 10 — Installments
# MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT

Implement, verify, audit, and close ONLY the following phase of Epic 10.

Phase Number: `5.5`
Phase Name: `Idempotency Primitive (HARD PREREQUISITE for Phases 7–10's high-risk commands)`
Task Range: `T085 to T093`

Feature Branch: 010-installments

[Full 47-section master phase implementation prompt — identical structure
to Phases 0-5. Followed by the standing PHR-creation instruction.]

## Response snapshot

Implemented T085-T093 (Phase 5.5: Idempotency Primitive) exactly as
scoped — no Phase 6+ work (Accounting integration, activation,
collections) started. This is Epic 10's second hard gate — no Phase
7-10 high-risk-command task may begin implementation until this gate
genuinely passes.

**T085**: `InstallmentIdempotencyKey` model — plain `Base` (not
`TenantBaseModel`), matching migration 067's exact field list verbatim.
No `FAILED` status in the CHECK constraint (plan.md §20.1's explicit
correction: a failed operation rolls back its whole transaction
including this row, so `FAILED` could never actually be durably
committed).

**T086/T087/T088**: `InstallmentIdempotencyService.reserve()`/
`complete()` — implemented together as one cohesive method pair since
plan.md §20.2's pseudocode presents them as a single flow (T086 covers
the `INSERT...ON CONFLICT DO NOTHING...RETURNING` reservation attempt
and the two normal non-error outcomes returned as `ReservationResult`;
T088 covers the same method's exception-raising branches for the
conflict cases). Uses `sqlalchemy.dialects.postgresql.insert()` exactly
per plan.md §20.2 — never a bare `INSERT` + caught `IntegrityError`,
and no repository class exists for this primitive (no repository task
appears anywhere in Phase 5.5's task list; plan.md's own pseudocode
executes the Core statements directly in the service, which this
mirrors). `complete()` is flush-only via a Core `UPDATE` statement — no
internal commit; the caller commits together with the business mutation
the reservation guards, exactly as `AdjustmentRepository.update_status()`'s
established convention requires elsewhere in this codebase.

**Repository-reality tension resolved (smallest safe resolution)**:
T092's own task text says "genuinely different test type (SQLite/unit-
level, not the real-Postgres concurrency suite)," but the production
code it tests calls `postgresql.insert().on_conflict_do_nothing()` — a
Postgres-specific construct that does not compile under SQLite at all.
Testing it against SQLite would either crash for the wrong reason or
require weakening the approved design to a dialect-agnostic
abstraction, contradicting plan.md §20.2's explicit, deliberate choice.
Resolved by keeping T092's specified file path
(`tests/unit/modules/installments/test_idempotency_reservation_no_abort.py`)
but using the same real-Postgres throwaway-database fixtures used
elsewhere in this module — a single-session test, genuinely lighter-
weight and distinct from T089-091's two-thread concurrency suite, which
satisfies the task's actual intent (proving no session-abort) without
violating Section 31's "SQLite is not final proof of PostgreSQL-specific
behavior" hard rule. Documented transparently here rather than silently
patched.

**T089/T090/T091**: real two-session Postgres concurrency tests proving
all three of plan.md §20.3's exhaustive normal-outcome scenarios: (1)
A wins, B's `INSERT` blocks at the database level until A resolves, B
replays A's `COMPLETED` result on a fingerprint match — verified with a
fresh third session that exactly one row exists and is `COMPLETED`; (2)
same key, different fingerprint — B receives
`InstallmentIdempotencyConflictError(code="IDEMPOTENCY_PAYLOAD_MISMATCH")`
after A commits; (3) A's transaction rolls back after a successful
reservation (simulating a mid-operation business failure) — a retried
request with the same key succeeds fresh (`RESERVED`, not `REPLAY` or
`CONFLICT`), proving the key is never permanently stranded. A single
`threading.Barrier(2)` sequences "A's `INSERT` must be in-flight before
B attempts its own" without the deadlock risk documented in Phase 3's
own T053 history (that risk was specifically a barrier placed *between*
a flush and its commit on *both* sides; here only A does anything after
the barrier, B simply blocks at the database level, which resolves
independently once A commits or rolls back). Re-run 4 times total
(once as part of the full new-test batch, three additional dedicated
re-runs) with zero flakiness.

**T092**: proven per the "repository-reality tension" resolution above
— duplicate reservation with a matching fingerprint replays without
raising `IntegrityError`, and the session remains fully usable
immediately afterward (a third, unrelated reservation succeeds in the
same session with no rollback/savepoint recovery step); a mismatched-
fingerprint duplicate raises `InstallmentIdempotencyConflictError`
cleanly and the session is likewise still usable immediately after,
again with no recovery step.

**T093**: tenant/operation scoping proven against real Postgres — the
identical key string reserved under a different `company_id`, or under
a different `operation` for the same company, is treated as a fully
independent reservation; a negative control confirms the exact same
`(company_id, operation, key)` triple does correctly collide (`REPLAY`),
proving the scoping tests aren't vacuously true.

**Testing**: 8 new tests (2 + 3 + 3), all passed; the two-session
concurrency suite specifically re-run 4 times total for flakiness with
zero failures. Full Installments module regression (all phases 0-5.5
combined): 140 passed, 0 failed. `ruff check`/`black --check` clean on
every file.

**Self-audit highlights**: `idempotency_service.py` contains zero
`db.commit()` calls (grep-verified) — both `reserve()` and `complete()`
are strictly flush/execute-only, matching plan.md §21's "same
transaction as the business write" requirement for Phases 7-10 to build
on. Every query in the service filters by `company_id` (grep-verified);
no `FAILED` string appears anywhere except in explanatory comments
documenting its deliberate absence.

Committed as a single Phase 5.5 completion commit; `tasks.md` T085-T093
checked off with evidence; PHR written; STOP per Section 47 — Phase 6
(Accounting Integration — the other critical hard gate) not started.

## Outcome

- ✅ Impact: the idempotency primitive Phases 7-10's high-risk commands
  (activation, collection, settlement, reversal, rescheduling,
  cancellation, default, write-off) depend on is now live and proven
  race-safe under real Postgres for all three normal-outcome scenarios
  plus the session-abort-free property and tenant/operation scoping —
  Epic 10's second hard gate is closed.
- 🧪 Tests: 8 new tests, all passed (concurrency suite re-run 4x with
  zero flakiness); full Installments regression 140/140 passed.
- 📁 Files: 1 new model, 1 new service, 3 new test files, 1
  models/__init__.py update, tasks.md checkboxes.
- 🔁 Next prompts: Phase 6 (Accounting Integration — the other critical
  hard gate) — awaiting explicit Product Owner instruction.
- 🧠 Reflection: T092's task-text/production-code tension (SQLite vs. a
  genuinely Postgres-only construct) is exactly the kind of "planning
  contradiction" Section 41 asks to be resolved by the smallest safe
  option and documented, not silently patched or blocked on — the fix
  (real Postgres, single-session, distinct from the two-session suite)
  honored both the task's actual testing *intent* and the architecture's
  explicit Postgres-only design choice simultaneously.

## Evaluation notes (flywheel)

- Failure modes observed: none in the implementation itself; the only
  friction was the task-text/production-code dialect tension described
  above, resolved before any test was written (not discovered via a
  failing test).
- Graders run and results (PASS/FAIL): self-audit against plan.md
  §20.1-20.4/tasks.md Phase 5.5 — PASS; Exit Condition — PASS (race-safe
  under real Postgres for all three normal outcomes; session-abort mode
  proven absent; no FAILED status ever persisted; tenant/operation
  scoping proven).
- Prompt variant (if applicable): n/a — identical master-phase template
  reused verbatim from Phases 0-5.
- Next experiment (smallest change to try): when Phase 6 wires
  `AccountingIntegrationGateway`'s staged/finalize extensions, the same
  "does this repository/service call ever commit internally" grep-audit
  performed here should be repeated on every new Accounting-side method
  before trusting the atomicity claim.
