---
id: 0009
title: Epic 10 Phase 0 database schema migrations
stage: green
date: 2026-08-25
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: /sp.implement
labels: [installments, epic-10, phase-0, migrations, postgresql, alembic, partial-unique-index, capability-seed, permission-backfill]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/migrations/versions/062_installments_foundation.py
 - backend/migrations/versions/063_installments_templates.py
 - backend/migrations/versions/064_installments_contracts.py
 - backend/migrations/versions/065_installments_schedule.py
 - backend/migrations/versions/066_installments_allocation_and_charges.py
 - backend/migrations/versions/067_installments_idempotency.py
 - backend/migrations/versions/068_installments_audit.py
 - backend/migrations/versions/069_installments_indexes.py
 - backend/migrations/versions/070_installments_capability_seed.py
 - backend/migrations/versions/071_installments_permission_backfill.py
 - backend/tests/integration/migrations/test_installments_migration_cycle_postgres.py
 - backend/tests/integration/migrations/test_057_preflight.py
 - backend/tests/integration/migrations/test_no_bootstrap_in_migrations.py
 - specs/010-installments/tasks.md
tests:
 - backend/tests/integration/migrations/ (full suite, real Postgres via Docker `db` service) — 12 passed, 0 failed
 - ruff check (10 new migrations + 3 test files) — all checks passed
 - manual `\d` introspection of installment_contracts, installment_configurations, installment_schedule_lines, installment_idempotency_keys, installment_allocation_references on live devsphere_dev (auto-migrated to head via the API container's reload-triggered migration hook)
 - manual SQL verification of capabilities row + 16 installments.* permissions + per-role role_permissions grant counts against real seeded company/role data (54 companies confirmed consistent across all 7 granted roles)
---

## Prompt

# Epic 10 — Installments
# MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT

Implement, verify, audit, and close ONLY the following phase of Epic 10.

Phase Number: `0`
Phase Name: `Database Schema (Migrations) — prerequisite for all phases`
Task Range: `T001 to T011`

Feature Branch: 010-installments

[Full 47-section master prompt supplied verbatim by the user, covering:
primary objective and no-correction-pass standard; strict phase scope
(implement only T001-T011, no future-phase pre-creation); authoritative
sources and authority order (Constitution > Spec > Plan > Tasks >
supporting artifacts > repository conventions); branch/working-tree
safety; pre-implementation task audit; repository-reality check before
new abstractions; per-task IMPLEMENT/TEST/VERIFY/NEGATIVE-PATH/
DEPENDENCY-RECHECK discipline; architecture freeze (Accounting
source-of-truth, no shadow balances, named lifecycle methods only,
REJECTED never persisted, operation-sensitive entitlement, Platform/
Support boundary, no AI); financial-transaction hard rules (staged/
finalize atomicity, no hidden commits) — N/A to this schema-only phase;
idempotency/Phase-5.5/Phase-6 hard gates — N/A, not yet reached;
database & migration hard rules (approved range 062-071, expected
pre-Epic-10 head 061, InstallmentConfiguration's two-partial-unique-index
requirement, no plain UNIQUE(company_id, branch_id)); API contract lock,
data-model audit, frontend rules — N/A to this phase; full testing
pyramid; failure-injection/atomicity proof — N/A; pre-existing-failure
policy (characterize every failure, fix if attributable to current
phase); real PostgreSQL/Docker verification requirement; live HTTP/
browser verification — N/A; requirement traceability review; mandatory
self-review and adversarial-completeness pass (10 named failure-injection
questions A-I); full diff review before closure; task-checkbox truthfulness
rule; exact phase Exit Condition proof requirement; hard-gate rule — N/A;
regression verification; no-correction-pass final contradiction search;
PHR requirement; pre-commit check; commit policy (one coherent phase
commit, correct conventional-commit prefix); post-commit verification;
an exhaustive Required Final Report template (sections A-S covering task
completion, files, database, tests, accounting/financial integrity,
idempotency, security, tenant isolation, RBAC/entitlement, contract, gate,
exit condition, defects discovered, pre-existing failures, self-audit,
git state, scope confirmation, final verdict); and a final stop rule
(implement, test, audit, gate-verify, commit, post-commit-verify, then
STOP — no speculative next-phase work).]

## Response snapshot

Read spec.md/plan.md/tasks.md/data-model.md (Phase 0 section, tasks.md
lines 1-205) plus targeted plan.md sections (§7 persistence design, §16.1
permission catalogue, §17 audit architecture, §20.1 idempotency schema,
§30/§30.1 migration strategy and mandatory backfill table, §33 indexing).
Verified pre-implementation state via `git branch --show-current` (clean,
`010-installments`) and confirmed pre-existing head `061` matched tasks.md's
generation-time assumption exactly (no drift). Researched exact codebase
conventions before writing any DDL: `TenantBaseModel`/`BaseModel`/`Base`
column shapes (`core/database/models/`), the CRM foundation migration
(055) and permission-backfill migration (056) as direct structural
precedents, the platform capability-seed migration (058) for the
`capabilities`/`plan_capabilities` FK shape, and dispatched a research
agent to confirm the exact "append-only, plain `Base`" precedent
(`JournalLine`/`AccountingAuditLog` in `modules/accounting/models/gl.py`)
and the exact tenant-scoped sequence-locking precedent (`SalesSequence`/
`AccountingSequence`, confirming `AccountingSequence` — not the older
`SalesSequence` shape with `deleted_by`/`updated_by` — is the current
`TenantBaseModel`-based convention to mirror).

Implemented all 10 migrations (T001-T010) exactly per tasks.md/plan.md,
with one filled-in implementation detail not spelled out verbatim in
tasks.md but required by data-model.md's own explicit FK declaration:
`installment_contracts.active_schedule_version_id` and
`installment_schedule_versions` have a forward-reference cycle (064 needs
a column referencing 065's table; 065's table FKs back to 064's table) —
resolved with the same deferred-FK technique migration 055 already uses
for `crm_leads`/`crm_opportunities` (column created without its FK in
064, `op.create_foreign_key()` closes it in 065, downgrade order reversed
to match). All partial unique indexes (`installment_configurations`'
NULL-semantics-safe two-index pair; `installment_contracts`' one-non-
terminal-per-obligation index) implemented as raw `CREATE UNIQUE INDEX
... WHERE ...` via `op.execute()`, matching the `uq_subscriptions_company_active`/
055's pipeline-default-index precedent. Migration 070's downgrade guards
the capability-row delete against the real `fk_plan_capabilities_capability_key`
`ON DELETE RESTRICT` FK (skip-if-referenced, rather than blowing up).
Migration 071 mirrors 056's exact idempotent `op.execute()` SQL style,
16 `installments.*` permission codes, and the exact per-role grant table
from plan.md §30.1 (including the deliberate cashier/store-keeper
deviation from CRM's zero-grant precedent, justified by spec's own
Cashier/Collector actor).

T011 (real-Postgres bidirectional verification) surfaced an unplanned but
informative event: the running dev API container auto-runs
`alembic upgrade head` on every `uvicorn --reload` restart, and its
`WatchFiles` reloader detected each new migration file as it was written
(bind-mounted `backend/`) — so migrations 062→071 were incrementally
applied against the live `devsphere_dev` database automatically, in
real time, as evidence of forward-migration correctness on real
PostgreSQL. Did not rely on this alone: wrote
`test_installments_migration_cycle_postgres.py` (mirroring the existing
Epic 9A `test_migration_cycle_postgres.py` precedent, reusing its shared
`pg_test_db`/`alembic_upgrade`/`alembic_downgrade` conftest fixtures
against a throwaway, uniquely-named database — never the live dev DB) to
formally prove the exact T011 sequence: upgrade 061→071, assert every
table/partial-index/CHECK-constraint/deferred-FK/capability-row/
permission-count, downgrade 071→061, assert full removal, upgrade
061→071 again, re-assert everything — plus a from-empty-database
`upgrade head` test. Both new tests passed on first run.

Running the full pre-existing `tests/integration/migrations/` suite for
regression (Section 40) surfaced two genuine pre-existing-test failures,
both caused by the current phase's approved, planned work (adding
migrations past 061) colliding with two Epic 9A tests that had
hard-coded "no migration 062 exists" / "head must equal 061" as literal,
permanent assertions (`test_no_bootstrap_in_migrations.py`'s
`test_no_migration_062_exists_and_head_is_061`, and two
`alembic_upgrade(pg_test_db, "head")` calls in
`test_057_preflight.py` that were written when "head" and "061" were
synonymous). Treated this as the master prompt's Section 2/24 "repository
reality vs. approved requirement" scenario: per the stated authority order
(Constitution > Spec > Plan > Tasks > supporting artifacts > repository
conventions), tasks.md's own generation-time prerequisite check had
already independently confirmed migrations 062-071 as valid and required
("current Alembic head is 061 ... the planned migration range 062-071 is
confirmed valid, no renumbering required") — so this is a stale Epic-9A-
authored regression test asserting a self-imposed, epic-scoped completion
marker (061's own docstring: "This is the final Epic 9A migration ...
no 062 exists or may be created") as if it were a permanent, all-epics-
forever platform invariant, not a substantive ADR-8 violation. The actual
ADR-8 guarantee (no migration ever provisions bootstrap Platform Owner
credentials) is untouched and still separately, fully enforced by the
sibling test `test_no_migration_file_references_bootstrap_env_vars`
(still passing). Fixed both tests minimally: `test_057_preflight.py`'s
two `alembic_upgrade(pg_test_db, "head")` calls now target `"061"`
explicitly (preserving the test's actual original intent — "Epic 9A's
own chain still completes cleanly" — without depending on no future epic
ever existing); `test_no_bootstrap_in_migrations.py`'s test was renamed
and rescoped to assert Epic 9A's own 057→061 sub-chain is internally
consistent (each revision resolves, in the right order, and nothing but
Epic 10's approved 062 branches from 061) rather than asserting a global,
forever-frozen head value. Re-ran the full migrations suite after both
fixes: 12/12 passed.

Verified `ruff check` clean on all 10 new migrations + 3 touched test
files. `black --check` (container's black 26.5.1) flagged reformatting on
9/13 files, but the same check against an already-merged, already-reviewed
prior migration (055) fails identically — confirmed this is a
black-major-version skew (container has 26.5.1; `.pre-commit-config.yaml`/
CI pin `24.10.0`, whose older string-splitting rules match the style
already used throughout the existing migration files, including this
session's new ones) rather than a real formatting defect introduced here;
documented as a known non-blocking environment discrepancy, not
remediated further to avoid reformatting unrelated pre-existing files
under a different tool version than CI actually runs.

Manually introspected the live (auto-migrated) `devsphere_dev` database
with `\d` for `installment_contracts`, `installment_configurations`,
`installment_schedule_lines`, `installment_idempotency_keys`, and
`installment_allocation_references` — every column type/nullability/
default, CHECK constraint, partial unique index, and FK matched
data-model.md/plan.md exactly. Verified the capability row
(`key='installments', module='installments', grain='module',
is_active=true`), exactly 16 `installments.*` permission rows, and
per-role `role_permissions` grant counts against real seeded company
data: `owner`/`admin` 864 = 16 × 54 companies, `manager` 540 = 10 × 54,
`accountant` 216 = 4 × 54, `salesperson` 162 = 3 × 54, `cashier`/`viewer`
108 = 2 × 54, `store-keeper` absent (zero grants) — an exact match to
plan.md §30.1's table across every currently-existing tenant.

Checked off T001-T011 in `specs/010-installments/tasks.md`. Confirmed
via `git status`/`git diff --stat` that only Phase-0-scoped files changed:
10 new migrations, 1 new test, 2 corrected pre-existing tests, and the
tasks.md checkbox update — no `backend/modules/installments/` directory
was created (correctly deferred to Phase 1), no future-phase model/
service/router/schema files exist anywhere in the diff.

## Outcome

- ✅ Impact: Phase 0 (T001-T011) complete. All 10 Installments migrations
  (062-071) exist, apply and downgrade cleanly against real PostgreSQL in
  both directions (proven twice: incrementally via the dev container's
  auto-migrate-on-reload hook, and formally via a new isolated-database
  bidirectional-cycle test), every partial unique index and CHECK
  constraint verified present via direct `\d` introspection, the
  capability seed and mandatory permission backfill verified against real
  multi-tenant seeded data. Two stale Epic 9A regression tests (asserting
  a self-imposed, now-superseded "head must stay 061 forever" freeze)
  were discovered and corrected to reflect that Epic 10 legitimately,
  approvedly continues the migration chain, without weakening the actual
  ADR-8 guarantee they were meant to protect.
- 🧪 Tests: `backend/tests/integration/migrations/` — 12 passed, 0 failed,
  0 skipped (real Postgres, Docker `db` service). `ruff check` — all
  checks passed on every new/modified file.
- 📁 Files: 10 new migration files, 1 new test file, 2 corrected
  pre-existing test files, `specs/010-installments/tasks.md` (T001-T011
  checked off).
- 🔁 Next prompts: Phase 1 (Module Foundation, T012-T020) — module
  skeleton, permission/enum constants, exception hierarchy, base schemas —
  not started, per the master prompt's explicit stop rule.
- 🧠 Reflection: The dev stack's auto-migrate-on-file-change behavior
  (WatchFiles reload → `core.migrations` startup hook → `alembic upgrade
  head`) is a useful, fast forward-migration signal during active
  migration authoring, but it is not a substitute for the project's
  established isolated-throwaway-database bidirectional-cycle test
  convention — both were used here, deliberately, for different purposes
  (fast incremental forward-only feedback vs. formal up/down/up proof).
  The two stale-test discoveries reinforce a pattern worth watching in
  future epics: an epic-closure test that hard-codes "this is the final
  migration, head equals N" as an executable assertion (rather than
  scoping the assertion to "this epic's own N0-N1 sub-chain is internally
  consistent") will always break the very next epic that legitimately
  extends the chain, and should be written the second, chain-scoped way
  from the start.

## Evaluation notes (flywheel)

- Failure modes observed: two pre-existing Epic 9A tests encoded an
  epic-scoped completion marker as a permanent global assertion, breaking
  on the very next (correctly planned/approved) epic. Root cause and fix
  documented above.
- Graders run and results (PASS/FAIL): migrations test suite — PASS
  (12/12 after fix); ruff — PASS; black — environment version skew, not
  a real defect (documented, not blocking).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): when writing an epic-closure
  "frozen migration range" guard test in a future epic, scope its
  assertion to that epic's own sub-chain (as corrected here) rather than
  the platform's global head, so it never needs a corrective pass from
  the next epic.
