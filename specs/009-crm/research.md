# Research: Epic 9 — CRM

Written at Epic closure (Phase 10, T103). Documents implementation-time decisions and discoveries **not already captured** in plan.md's 13 ADRs — i.e., things learned or decided while building, not while planning.

## Decision 1: Idempotent Lead-Conversion Retry Must Recall, Not Assume, `customer_matched`

**Context**: `LeadConversionService.convert()`'s idempotency guard (spec.md §16.3, SEC-10) returns the existing result when a Lead is already `CONVERTED`, without re-running the match-or-create logic.

**Defect found during Phase 10 (T096 SEC-10 test)**: the guard unconditionally returned `customer_matched=True` on every repeat call, regardless of whether the *original* conversion actually matched an existing Customer or created a new one. A Lead converted via the new-customer path (`customer_matched=False` on the first call) would silently report `True` on every subsequent idempotent retry — a real, client-visible correctness defect (misleading response data), not a test artifact.

**Fix**: `CrmAuditService` gained `find_latest_after_state(company_id, entity_type, entity_id, action)`, which recalls the original conversion's audit-log `after_state` (already recorded, unchanged, by the existing `LEAD_CONVERTED` audit entry). The idempotent-retry branch now reads the real historical fact instead of assuming one, falling back to `True` only if no audit entry exists at all (defensive, not expected in practice since auditing is unconditional on every conversion).

**Why this approach, not a new column**: adding a persisted `Lead.converted_customer_matched` boolean would require a new migration for one narrow question already answerable from data already being written (the audit log). Reusing the audit trail avoids a schema change for a fact CRM already durably records.

## Decision 2: Performance Test Methodology — SQLite Regression Guards, Not the Literal Row Counts

**Context**: spec.md §47 targets are stated at production scale (100,000 rows, 10,000 open Opportunities). The full backend test suite runs against SQLite in-memory (see `backend/tests/conftest.py`), which has no cost-based query planner and behaves non-linearly at very large row counts in ways that do not represent PostgreSQL's real, indexed, cost-based behavior — an issue independently discovered and documented during Epic 8's own Phase 13 performance work (`tests/performance/accounting/test_report_performance.py`).

**Decision**: T092–T095 seed a reduced-but-representative row count (5,000 for list endpoints, 3,000 open Opportunities for the pipeline report, the literal 500 for Customer 360 since that number is a *bound*, not a scale test, and the literal 25-sample real-time measurement for Lead conversion since a single conversion is a small constant-size transaction) against SQLite, asserting a generous guard threshold — not the literal spec-mandated number. This exactly matches the established, audited Epic 8 precedent rather than inventing a new methodology.

**What this does and does not prove**: these tests are fast regression guards that catch a regressed missing index or an accidentally-introduced N+1 query. They are **not** a substitute for the real 100,000-row / 10,000-row PostgreSQL numbers, which require live-Postgres verification (spec.md §48.5) — tracked as an explicit, separate, not-yet-executed Epic-9-closure verification step (see quickstart.md's "Live Verification" section), consistent with this epic's own kickoff instruction to defer the full expensive live-verification protocol to a dedicated pass after phase-level work completes.

## Decision 3: `tests/conftest.py` Is a 4th Modified File, Beyond Plan.md §29.2's List

**Context**: plan.md §29.2 lists exactly 3 modified Epic 1–8 files (`users_roles/constants.py`, `api/v1/router.py`, `main.py`). Discovered during Phase 10's T102 git-diff audit: `backend/tests/conftest.py` is also modified — one additive line (`import modules.crm.models`) registering CRM's ORM models with `Base.metadata` so the shared SQLite in-memory test database's `create_all()` can resolve CRM's tables.

**Assessment**: this is a test-infrastructure-only file (never shipped to production), the change is a single additive import line (confirmed via `git diff`, zero deletions), and it is *necessary* — without it, every CRM test would fail at fixture setup with a missing-table error. It does not violate the "zero other Epic 1–8 file touched" backward-compatibility guarantee in spirit (no production behavior changes for any existing module), but it is a minor gap in plan.md's own "exhaustive" file list, documented here for completeness rather than silently left unreconciled.

## Decision 4: Dev Database Migration-State Drift, Discovered and Fixed During T100 Live Verification

**Context**: T100's live-Postgres verification (item 1, migration cycle test) uncovered that the local dev Docker Postgres database's `alembic_version` table claimed head `056` (migrations 055 and 056 both "applied"), but only `crm_feature_flags` actually existed in the schema — the other 7 CRM tables were missing entirely.

**Root cause**: migration `055`'s own docstring documents it was built in two parts within a single revision file — "Part A (Phase 1) created only the module gate: `crm_feature_flags`. Part B (this revision, Phase 2) appends the remaining 7 tables... to this SAME migration file." This dev database had run `alembic upgrade head` back when `055` contained only Part A's DDL; the file was later edited in-place (same revision ID, per plan.md's single-linear-migration design) to add Part B's 7 tables. Since Alembic tracks applied state purely by revision ID, and `055` was never re-run once already marked applied, this dev database silently kept Part A's incomplete schema while `alembic_version` claimed the full, current migration had run.

**This is not a CRM code defect** — verified by running the *current* migration file's full upgrade→downgrade→upgrade cycle from scratch against an isolated, empty Postgres container: all 8 tables, every constraint, every index created correctly, and cleanly removed on downgrade. The migration file itself is correct; only this one specific, already-iterated-on local dev database's history was stale.

**Fix applied** (dev-environment-only, not a code or migration change): `alembic stamp 054` (rewind the version pointer without running SQL) → drop the now-redundant empty `crm_feature_flags` table → `alembic upgrade head` (re-runs the complete, current `055`+`056` from that point). Verified via `\dt crm_*`, `pg_constraint`, and `pg_indexes` afterward — full schema now matches the migration file exactly.

**Lesson for future epics**: editing an in-progress migration file in place (rather than creating a new revision) is fine and intentional *before* any real environment has applied it, but any developer's local dev database that ran the migration mid-iteration will silently drift exactly like this. Worth a one-line callout in a future epic's own kickoff checklist: if a migration file is edited after Phase 1's initial partial version already shipped to a shared/long-lived dev database, that database needs an explicit `alembic stamp` + re-`upgrade` reconciliation — it will not self-heal.

## Decision 5: Sales' Real Event-Type String Differs From spec.md's Prose

Already documented in `contracts/events.md` in full; summarized here as a research decision: spec.md names the Quotation-acceptance event `sales.quotation.accepted`, but the actual, currently-published event type (verified against `modules.sales.events.quotation_events.QuotationAccepted` before implementing the integration handler, per this epic's own "verify against the real codebase" mandate) is `quotation.accepted` — no `sales.` prefix. CRM's handler subscribes to the real, verified string, not the spec's prose name.
