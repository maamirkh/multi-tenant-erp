---
id: 0015
title: Phase 2 database migration foundation gate A
stage: green
date: 2026-08-19
surface: agent
model: claude-sonnet-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.implement
labels: ["platform-admin", "implement", "phase-2", "migrations", "gate-a", "postgresql"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/migrations/versions/057_platform_admin_foundation.py
 - backend/migrations/versions/058_platform_plans_entitlements.py
 - backend/migrations/versions/059_platform_quotas_overrides.py
 - backend/migrations/versions/060_platform_usage_ai_readiness.py
 - backend/migrations/versions/061_platform_support_access.py
 - backend/tests/integration/migrations/__init__.py
 - backend/tests/integration/migrations/conftest.py
 - backend/tests/integration/migrations/test_057_preflight.py
 - backend/tests/integration/migrations/test_migration_cycle_postgres.py
 - backend/tests/integration/migrations/test_no_bootstrap_in_migrations.py
 - backend/tests/integration/migrations/test_existing_tenant_preservation.py
 - specs/009a-platform-admin/tasks.md
tests:
 - backend/tests/integration/migrations/ (real Docker/PostgreSQL, 9 tests, ephemeral per-test databases) — 9 passed
---

## Prompt

# Epic 9A — MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT

Implement, verify, audit, and close **Phase 2 — Database & Migration
Foundation (Gate A), tasks T010-T031** of `specs/009a-platform-admin/tasks.md`.

[37-section brief. Key requirements: strict phase scope (no future-phase
models/services/routes/frontend); git safety preflight (branch, clean tree,
Phase 1 present in history); pre-implementation task audit of every
dependency; repository-reality check before creating abstractions;
IMPLEMENT→TEST→VERIFY→ADVERSARIAL REVIEW→REGRESSION CHECK→CLOSE per task;
architecture freeze (13 named areas — Platform identity, sessions, RBAC,
bootstrap, lifecycle, auth freshness, cross-tenant safety, entitlements,
quotas, context separation, audit, support access, AI, infrastructure);
migration hard rules (057-061 frozen, no 062, PostgreSQL semantics, not
SQLite); migration-057 preflight rule (fail before mutating on a pre-existing
suspended row, never guess); API contract lock (N/A — no HTTP surface this
phase); security adversarial testing categories; tenant isolation audit;
testing pyramid; pre-existing-failure policy (record both full-suite and
isolation results, never rewrite a failure as a pass); real PostgreSQL/Docker
verification requirement (SQLite not final proof); data-model↔implementation
audit; self-review as if reviewing another engineer's PR; adversarial
completeness pass (7 named questions); full diff review before closure; task
checkbox rule (evidence-based only); phase exit condition proven explicitly;
Gate rule (STOP on failure, Gate order A→B→E→C→D→F→G); requirement
traceability review; final consistency search across all planning artifacts;
PHR requirement; pre-commit check; commit policy (one coherent commit, only
if genuinely complete); post-commit verification; 16-part final report
format (A-P) ending in an exact verdict string; final stop rule (no
speculative next-phase work). Full verbatim text in the conversation
transcript for this turn — the user separately requested "commit Phase 1"
first, which was completed as its own prior turn, unblocking this phase's
clean-tree precondition.]

## Response snapshot

**Preflight**: branch `009a-platform-admin`, clean tree, Phase 1 (`843b585`)
present in history. Checklist gate 16/16 PASS. Read Phase 2's full task text
(T010-T031), plan.md §26/§33/§33.1, and data-model.md's complete field-level
spec for all 19 new tables + the 2 additive `companies` columns. Studied
migration 055 (`crm_foundation.py`, 8-table single-migration precedent) and
049 (`add_column`/`create_check_constraint`/`drop_constraint` precedent) to
match this codebase's exact raw-DDL Alembic style — confirmed no ORM models
exist for these tables yet (Phase 3's job per its own Objective line: "moved
ahead of identity/RBAC" for the audit foundation), so **zero model files
were created**, avoiding future-phase leakage.

**Implemented 5 migrations** (`057`-`061`), each with upgrade+downgrade:
`057` creates the 8 Identity & Session tables plus the 2 additive `companies`
columns, their 2 CHECK constraints, and the mandatory suspended-row preflight
guard (verbatim `RuntimeError` message from plan.md §33.1, run immediately
before constraint creation); `058` creates Entitlement (`capabilities`,
`plans`, `plan_capabilities`, `subscriptions` + the partial unique index +
the real FK on the pre-existing `companies.subscription_id`); `059` creates
Quotas & Overrides (4 tables, 2 more partial unique indexes, value/expiry
CHECK constraints); `060` creates Usage & AI Readiness (2 tables,
provider-neutral); `061` creates `support_access_grants` and closes the
deferred `platform_audit_events.support_access_grant_id` FK using the same
technique migration 055 uses for its own two-table cycle.

**Deliberate judgment calls, recorded rather than silently made**: (1)
`grain`/`enforcement_style` fields data-model.md describes as `enum(...)`
were implemented as VARCHAR+CHECK, matching `Plan.status`'s explicit
"not a PG ENUM" convention and this codebase's project-wide pattern — no
native PostgreSQL ENUM type appears anywhere in the 5 migrations. (2)
`Subscription.reason` and `AiCreditLedgerEntry.reason` are nullable at the
DB level because data-model.md states each is conditionally required
("NOT NULL for administrative changes" / "Required when
actor_platform_administrator_id is populated") — a service-layer rule for a
later phase, not an unconditional DB constraint; a blanket NOT NULL here
would have been a real defect. (3) Added `expires_at > started_at` to
`support_access_grants` even though data-model.md's compact table doesn't
restate it in that section, because plan.md §26 explicitly names
"support-access tables" alongside override tables for this exact check —
cross-referencing the plan surfaced a requirement the compact data-model
table alone would have missed.

**Sanity-verified on real PostgreSQL before writing any tests**: fresh
database, full `alembic upgrade head` (001→061, ~20s), then
`downgrade 056` → `upgrade head` again — clean both directions. Inspected
`\d+` output for `companies`, `subscriptions`, `tenant_quota_overrides`,
`entitlement_overrides`, `platform_audit_events` to confirm every column,
CHECK constraint, partial unique index, and deferred FK matches data-model.md
exactly.

**Built a real-PostgreSQL test harness** (`tests/integration/migrations/
conftest.py`) rather than reusing the project's SQLite in-memory fixtures,
which cannot represent partial unique indexes or CHECK constraints
faithfully (plan.md §32). Each test gets its own uniquely-named, empty
database on the same `db` Docker Compose service the application uses —
created via an autocommit-isolation admin connection, dropped in teardown —
never touching the live `devsphere_dev` database. `alembic.command.upgrade`/
`downgrade` are invoked directly (matching how `migrations/env.py` already
reads `DATABASE_URL` fresh from the environment on every invocation), not
shelled out to a CLI.

**Wrote and ran 9 tests across 4 files**, all passing on real PostgreSQL:
`test_057_preflight.py` (T024 clean-DB success; T025 refusal with the
affected slug and both remediation options named; T026 byte-for-byte
unchanged schema + unmoved `alembic_version` after a refused run; T028 full
remediate→succeed→up→down→up path), `test_migration_cycle_postgres.py`
(T027 — the Gate A `056→061→056→061` cycle, asserting all 19 new tables and
the `companies`/`subscriptions` schema state after every step),
`test_no_bootstrap_in_migrations.py` (T029 — 3 tests: zero
`platform_administrators` rows after `upgrade head`; no migration file
references either bootstrap env var; no `062_*.py` file and single head
`061`), `test_existing_tenant_preservation.py` (T030 — seeded
companies/roles/company_members/inventory_feature_flags rows at `056`,
proved every field byte-for-byte identical after `061`, both new `companies`
columns NULL). One real defect caught and fixed during this pass: the first
`inventory_feature_flags` seed row violated `ck_inventory_ff_key_prefix`
(flag keys must be prefixed `inventory.`) — fixed the fixture, re-ran clean.

**Full diff review**: exactly 12 files touched — 5 migrations, 6 new test
files (including `conftest.py`/`__init__.py`), and `tasks.md`'s Phase 2
result annotations. No models, services, routers, schemas, or frontend files
— confirmed no future-phase leakage via `git status`/`git diff --stat`. No
TODO/debug/commented-out code, no hardcoded secrets (grepped explicitly).

**Marked T010-T031 `[X]`** with dated Result lines, same convention as
Phase 1. Machine-verified afterward: 225 tasks still sequential T001-T225,
17 phases unchanged, exactly T001-T031 marked complete. Confirmed the
Requirement Traceability Matrix's `ADR-12 migration preflight` row
(`T012, T013 | T024–T028`) is now fully implemented and verified — no drift
between that row and what was actually built/tested.

## Outcome

- ✅ Impact: Gate A is genuinely satisfied — the entire Epic 9A schema
  foundation (19 tables + 2 additive columns across 5 migrations) exists,
  is proven reversible on real PostgreSQL, and the single highest-risk
  behaviour in this phase (the suspended-row preflight guard) is proven to
  both refuse correctly *and* leave zero partial state, not merely to "throw
  an error." Phase 3 (Platform Domain, Audit Foundation & Administrator
  Identity) can now safely build ORM models atop schema that is verified to
  match data-model.md exactly.
- 🧪 Tests: 9/9 passed, real Docker/PostgreSQL, 0 skipped, 0 SQLite
  substitution. One real fixture defect found and fixed during the pass
  (feature-flag key prefix CHECK), not left as a silent failure.
- 📁 Files: 5 migrations + 6 test files (new) + `tasks.md` (Phase 2 section
  only, 22 tasks marked `[X]` with evidence). `constitution.md`, `spec.md`,
  `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`
  untouched. No ORM models, services, routers, or frontend files — Phase 3+
  scope not started.
- 🔁 Next prompts: Phase 3 (not started, per the strict phase-lock scope and
  final stop rule — awaiting Product Owner instruction).
- 🧠 Reflection: the three "deliberate judgment call" items above are the
  generalisable finding — data-model.md's compact per-table field lists are
  necessarily lossy (a business-conditional NOT NULL, a plan.md-only CHECK,
  an "enum" that means "CHECK domain" not "PG ENUM type") and plan.md's
  prose sections are where those nuances actually live. Reading only the
  data-model table would have produced two real defects (a wrongly-strict
  NOT NULL, a missing CHECK) and one unnecessary architecture deviation
  (a native PG ENUM inconsistent with the rest of the schema).

## Evaluation notes (flywheel)

- Failure modes observed: (a) initial fixture data for the tenant-preservation
  test violated a real CHECK constraint (`inventory.` prefix requirement) —
  caught immediately by the real-Postgres test run, not silently passed,
  because SQLite's looser constraint enforcement would likely have let it
  through; this is itself a small piece of evidence for why plan.md §32
  insists on real PostgreSQL for this phase. (b) An initial draft had a
  misplaced `import pytest` at module end (functionally harmless due to
  Python's late name binding inside function bodies, but bad style/violates
  "no accidental churn") — caught during self-review before running tests,
  moved to the top.
- Graders run and results (PASS/FAIL): task count PASS (225); phase count
  PASS (17); T001-T031 exclusively marked `[X]` PASS; real-Postgres test
  suite PASS (9/9); up/down/up cycle PASS; preflight refusal PASS; preflight
  no-partial-state PASS; remediation path PASS; no-bootstrap-in-migrations
  PASS (3/3); tenant-preservation PASS; full diff review PASS (12 files, all
  in-scope, no future-phase leakage, no secrets, no debug code); traceability
  matrix reconciliation PASS (ADR-12 row).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
