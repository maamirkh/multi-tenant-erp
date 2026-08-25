---
id: 0013
title: Epic 10 Phase 4 schedule engine
stage: green
date: 2026-08-26
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: /sp.implement
labels: [installments, epic-10, phase-4, schedule-engine, determinism, rounding, month-end-anchoring, quote-preview, immutable-schedule]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/installments/services/schedule_engine.py
 - backend/modules/installments/services/business_date.py
 - backend/modules/installments/services/quote_service.py
 - backend/modules/installments/models/schedule.py
 - backend/modules/installments/models/__init__.py
 - backend/modules/installments/repositories/schedule.py
 - backend/modules/installments/schemas/schedule.py
 - backend/modules/installments/dependencies.py
 - backend/modules/installments/router.py
 - backend/tests/unit/modules/installments/test_schedule_engine_frequency.py
 - backend/tests/unit/modules/installments/test_schedule_engine_month_end.py
 - backend/tests/unit/modules/installments/test_schedule_engine_leap_year.py
 - backend/tests/unit/modules/installments/test_schedule_engine_rounding.py
 - backend/tests/unit/modules/installments/test_schedule_engine_degenerate.py
 - backend/tests/unit/modules/installments/test_schedule_engine_determinism.py
 - backend/tests/unit/modules/installments/test_quote_service.py
 - backend/tests/integration/repositories/installments/test_schedule_immutability.py
 - backend/tests/integration/repositories/installments/test_schedule_persistence.py
 - specs/010-installments/tasks.md
tests:
 - backend/tests/unit/modules/installments/test_schedule_engine_*.py — 23 passed (frequency, month-end, leap-year, rounding, degenerate, determinism)
 - backend/tests/unit/modules/installments/test_quote_service.py — 6 passed
 - backend/tests/integration/repositories/installments/test_schedule_immutability.py (structural) — 2 passed
 - backend/tests/integration/repositories/installments/test_schedule_persistence.py (real Postgres, migration 065 schema) — 4 passed
 - full Installments module regression (unit+repository+API+security, all phases 0-4) — 72 passed, 0 failed
---

## Prompt

# Epic 10 — Installments
# MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT

Implement, verify, audit, and close ONLY the following phase of Epic 10.

Phase Number: `4`
Phase Name: `Schedule Engine`
Task Range: `T057 to T073`

Feature Branch: 010-installments

[Full 47-section master phase implementation prompt — identical structure
to Phases 0-3: strict phase scope, authoritative sources, branch safety,
pre-implementation task audit, repository-reality check, task
implementation rule, architecture freeze, financial transaction hard
rule, Accounting source-of-truth rule, idempotency hard rule, Phase 5.5/
Phase 6 hard gates, concurrency rule, audit fail-closed rule, transactional
outbox rule, tenant isolation audit, RBAC/maker-checker, entitlement
adversarial testing, Platform/Support boundary, database & migration hard
rules, API contract lock, data model ↔ implementation audit, frontend
rule, testing pyramid, failure-injection/atomicity proof, pre-existing
failure policy, real PostgreSQL/Docker verification, live HTTP/browser
verification, requirement traceability review, self-review, adversarial
completeness pass, full diff review, task checkbox rule, phase exit
condition, hard gate rule, regression verification, no-correction-pass
standard, PHR/implementation history, pre-commit check, commit policy,
post-commit verification, required final report (sections A-S), and
final stop rule — verbatim, as used for every prior phase in this epic.]

Followed by the standing PHR-creation instruction appended after every
`/sp.implement` invocation.

## Response snapshot

Implemented T057-T073 (Phase 4: Schedule Engine) exactly as scoped —
no Phase 5+ artifacts (lifecycle transitions, idempotency, Accounting
mutation calls) pre-created.

**ScheduleEngine** (`schedule_engine.py`, T057/T058/T060): a stateless,
pure `ScheduleEngine.generate()` — zero DB/HTTP imports, verified by
direct import inspection. `_add_months()` clamps day-of-month to the
target month's actual last day via `calendar.monthrange()`. Amount
splitting uses the exact plan.md §10.3 algorithm (base line quantized to
`Decimal("0.000001")`, residual absorbed entirely into the final line by
subtraction, `DegenerateScheduleError` — reused unchanged from Phase 1 —
raised if the final line would be `<=0`).

**Design correction found during implementation**: the original mental
model of advancing due dates iteratively from the *previous* line's due
date (`_add_months(previous, 1)` chained) would silently drift once a
month-end clamp occurred (Jan 31 → Feb 28 → Mar 28, losing the day-31
anchor forever instead of correctly landing on Mar 31). Fixed by
computing every line's due date as an offset from the *original*
`first_due_date` anchor (`_add_months(first_due_date, index)` /
`index * 3` for quarterly / `timedelta(weeks=index)` for weekly) — this
is what T062/T063's month-end and leap-year tests actually caught before
any code was marked complete, per Section 6's negative-path-proof step.

**`get_business_date()`** (T059): discovered and reused the platform's
existing `core.utils.datetime.utcnow()` helper instead of a fresh
`datetime.now(timezone.utc)` call — smaller diff, avoids a `ruff` UP017
flag, and is the same helper the rest of the backend already uses.

**Schedule persistence** (T067/T068): `InstallmentScheduleVersion`
(`TenantBaseModel`) / `InstallmentScheduleLine` (plain `Base`, explicit
`company_id`, no soft-delete — mirrors `JournalLine`) match migration
065's columns exactly. `InstallmentScheduleRepository` is flush-only
(never commits) — mirrors `JournalLineRepository`'s established
convention — and exposes exactly `create_version_with_lines()`,
`get_active_version()`, `get_version()`, `get_lines()`; no
update/delete/edit/modify/set_ method exists anywhere on the class,
proven structurally by T072's reflection test.

**Quote/Preview** (T069/T070/T071): `InstallmentQuoteService.preview()`
reuses Phase 3's already-built `InstallmentEligibilityService` (for the
invoice's live outstanding amount and eligibility gating — an
earlier-completed-phase artifact, explicitly permitted for reuse) and
Phase 2's `InstallmentConfigurationService` (for the tenant's configured
`rounding_policy`, defaulting to `ROUND_HALF_UP` when unconfigured),
then delegates all arithmetic to `ScheduleEngine.generate()` — zero
persistence, zero audit call, proven by a structural source-inspection
test (`test_preview_never_persists_or_audits`) asserting no
`Repository`/`AuditService`/`.create(`/`.commit(` symbol appears
anywhere in the service's source. `POST /quotes` added to `router.py`
(not yet mounted — mounting remains T190/Phase 11), enforcing
`installments.contract.create` inline, matching the OpenAPI contract's
`x-permission`/`x-operation-class: ORIGINATION`/`x-idempotent: false`.

**Defect found and fixed**: `ScheduleEngine.generate()` treats an
unsupported `frequency`/`rounding_policy` as a `ValueError` (a
pure-function input-contract violation) — at the `/quotes` client-facing
boundary this would have surfaced as an unhandled 500 instead of the
OpenAPI-documented 422. Fixed by catching `ValueError` in
`InstallmentQuoteService.preview()` and re-raising as a `ValidationException`
with `code="INVALID_SCHEDULE_TERMS"`. Verified by a new test asserting a
`DAILY` frequency raises `ValidationException`, not an unhandled crash.

**Documented, not fixed (pre-existing, out of scope)**: the OpenAPI
`/quotes` comment mentions a "422: terms outside configured policy
bounds" response, implying validation against
`InstallmentConfiguration.min_term`/`max_term`/`min_down_payment_*`/
`max_financed_amount`/`allowed_frequencies`. No task anywhere in
tasks.md's full 15-phase breakdown (Phase 2 through Phase 15) assigns
wiring this validation into either `create_draft()` (Phase 3, already
committed) or `preview()` (this phase) — confirmed by grep across the
entire task list. This is a pre-existing planning-to-task gap that
predates this phase and is not introduced by it; documented per Section
41 ("unrelated pre-existing issue → document without expanding scope")
rather than silently building unassigned validation logic.

**Testing**: 23 ScheduleEngine unit tests (frequency sequencing,
month-end anchoring including the drift-prevention fix, leap-year
crossing, `ROUND_HALF_UP` vs `ROUND_HALF_EVEN` divergence at a genuine
decimal tie, degenerate-schedule rejection, determinism across repeated
calls and all frequency/policy combinations) — all passed, zero DB/HTTP
fixtures used anywhere (proving the "100% unit-tested with zero DB/HTTP
dependency" exit-gate clause directly). 6 quote-service unit tests
(fake collaborators). 2 structural immutability tests. 4 real-Postgres
repository tests against the actual migration-065 schema (atomicity via
flush-then-rollback showing nothing durable until the caller commits,
retrieval after commit, the real unique-constraint violation with the
exact `uq_installment_schedule_lines_version_sequence` constraint-name
signature, and independent multi-version persistence). A live HTTP
smoke test (throwaway, cleaned up) proved `POST /quotes` end-to-end
through the real router/dependency wiring with `dependency_overrides`
for the Sales/Accounting-facing gateways only. Full Installments module
regression (all phases 0-4 combined): 72 passed, 0 failed — zero
regressions. `ruff check` and `black --check` clean on every new/modified
file.

Committed as a single Phase 4 completion commit; `tasks.md` T057-T073
checked off with evidence; PHR written; STOP per Section 47 — Phase 5
(Contract Lifecycle) not started.

## Outcome

- ✅ Impact: Phase 4 (Schedule Engine) complete — `ScheduleEngine` is a
  pure, deterministic, 100%-unit-tested domain function with zero DB/HTTP
  coupling; quote/preview is live and provably non-mutating; schedule
  persistence is structurally immutable and proven against real Postgres.
- 🧪 Tests: 23 + 6 + 2 + 4 = 35 new tests, all passed; full Installments
  regression 72/72 passed.
- 📁 Files: 9 new, 3 modified (dependencies.py, router.py,
  models/__init__.py), plus tasks.md checkbox updates.
- 🔁 Next prompts: Phase 5 (Contract Lifecycle, T074-T084) — awaiting
  explicit Product Owner instruction per the Final Stop Rule.
- 🧠 Reflection: The month-end due-date-drift bug (iterative vs.
  anchor-based `_add_months`) is exactly the class of defect the
  negative-path-proof/adversarial-review steps exist to catch before
  a task is marked `[X]` — it was caught by writing the month-end test
  BEFORE trusting the first implementation, not after.

## Evaluation notes (flywheel)

- Failure modes observed: (1) iterative month-end date chaining drifts
  away from the original anchor once a clamp occurs — fixed by always
  offsetting from `first_due_date`; (2) a pure-function `ValueError`
  reaching an HTTP boundary unmapped would have produced an unhandled
  500 instead of the documented 422 — fixed with an explicit catch/
  translate at the service boundary.
- Graders run and results (PASS/FAIL): self-audit against Constitution/
  Spec/Plan/Tasks/OpenAPI/data-model — PASS; Exit Condition — PASS
  (ScheduleEngine 100% unit-tested with zero DB/HTTP dependency; quote
  preview provably non-mutating/non-audited; schedule persistence
  structurally immutable).
- Prompt variant (if applicable): n/a — identical master-phase template
  reused verbatim from Phases 0-3.
- Next experiment (smallest change to try): none required; Phase 5 will
  reuse this same template unchanged.
