# Tasks: Epic 9A — Platform Administration / Super Admin

**Branch**: `009a-platform-admin` | **Date**: 2026-08-19 | **Revision**: 2 (dependency-correction pass)
**Input**: `specs/009a-platform-admin/spec.md` (30 sections) + `plan.md` (42 sections, 13 ADRs) + `research.md` + `data-model.md` + `contracts/platform-admin-v1.yaml` + `quickstart.md`
**Planning commit**: `fd3d55e` | **Constitution**: v1.2.1 (§50 authoritative)

## Format: `Txxx [P?] [Tag?] Description`

- **[P]**: Parallelizable — different files, no dependency on an incomplete task
- **Tags**: `[US-n]` user story (spec §10), `[FR-9A-nnn]`, `[BR-9A-nnn]`, `[SC-n]`, `[ADR-n]` (plan §37), `[Gate X]` critical gate
- Each task has: **Purpose**, **Files**, **Deps**, **Acceptance**
- Backend: `backend/modules/platform_admin/...` | Frontend: `frontend/src/app/(platform-admin)/...`, `frontend/src/lib/api/platform.ts`
- Tests: `backend/tests/{unit,integration,security,performance}/modules/platform_admin/`

> **Revision 2 note**: this file was corrected for dependency/order defects only — scope, architecture, security model, ADR decisions and acceptance criteria are unchanged. Task IDs were renumbered because tasks were split and moved; see the mapping in the correction report. Migration ownership remains **frozen at `057`–`061`** with no `062`.

> **Tooling note**: `.specify/scripts/bash/{setup-plan,check-prerequisites}.sh` reject this branch name (regex `^[0-9]{3}-` does not match `009a-`). Paths resolved manually; the same scripts' `find_feature_dir_by_prefix()` fallback resolves correctly. Pre-existing narrow tooling gap, not an Epic 9A defect.

---

## User Story Map

| Story | Priority | Spec §10 | Delivered in Phase |
|---|---|---|---|
| US-1 Platform Admin views platform overview | P1 | US-1 | 13, 15 |
| US-2 Platform Admin searches/inspects tenants | P1 | US-2 | 7, 13, 15 |
| US-3 Authorized admin changes tenant lifecycle | P1 | US-3 | 7, 15 |
| US-4 Platform Admin manages SaaS plans | P2 | US-4 | 8, 15 |
| US-5 Platform Admin assigns/changes subscriptions | P2 | US-5 | 8, 15 |
| US-6 Platform Admin manages entitlements/limits | P2 | US-6 | 9, 11, 15 |
| US-7 Authorized admin manages Platform RBAC | P2 | US-7 | 3, 5, 15 |
| US-8 Security/Audit Admin reviews privileged actions | P2 | US-8 | 3, 6, 13, 15 |
| US-9 Support Admin obtains controlled tenant access | P3 | US-9 | 12, 15 |
| US-10 Platform Admin reviews usage and quota status | P2 | US-10 | 8, 11, 15 |
| US-11 Platform Admin reviews operational health | P2 | US-11 | 13, 15 |
| US-12 Platform Admin reviews AI usage/credits | P3 | US-12 | 11, 15 |
| US-0 Foundation (no independent user value; blocking) | P0 | — | 1–6 |

---

## Critical Gates (blocking — do not proceed past a failed gate)

| Gate | Proves | Signed off in | Depends only on |
|---|---|---|---|
| **A — Migration Safety** | 057 preflight works on real PostgreSQL; lifecycle restore state never fabricated; up/down/up clean | Phase 2 (T031) | Phase 1–2 |
| **B — Platform Trust Boundary** | Tenant tokens cannot reach Platform APIs and vice versa; Platform auth/session independent; RBAC enforced on the routes that exist by Phase 5; bootstrap authority protected; self-escalation and last-owner rejected | Phase 5 (T077) | Phase 1–5 only |
| **E — Audit Atomicity** | Audit-write failure rolls back the privileged mutation (proved on a real Phase-5 audited mutation) | Phase 6 (T081) | Phase 1–6 only |
| **C — Lifecycle / Auth Freshness** | Suspend/reactivate correct; old access token denied; **old refresh path denied**; genuine login required; Company B survives Company A suspension; **plus** the full 3-way state+audit+outbox atomicity proof | Phase 7 (T102) | Phase 1–7 |
| **D — Entitlement Security** | Plan ceiling enforced at point of use; stale toggle cannot bypass downgrade; all 5 modules | Phase 9 (T137) | Phase 1–9 |
| **F — Support Security Boundary** | Support access cannot reach tenant business records | Phase 12 (T166) | Phase 1–12 |
| **G — Real-Stack Regression** | Epics 1–9 still function on real Docker/PostgreSQL | Phase 17 (T225) | All phases |

**Gate ordering is A → B → E → C → D → F → G.** Gate E precedes Gate C because its foundational proof uses a Phase-5 audited mutation; the tenant-suspension 3-way atomicity proof (T101) lives inside Phase 7 under Gate C.

---

## Phase 1: Preflight / Drift Verification

**Objective**: Confirm repository reality has not drifted from the facts plan.md §3 was built on. Detection only — no implementation.
**Prerequisites**: none.
**Exit condition**: All drift checks pass, or implementation **stops** and the drift is reported.

### Tasks

- [X] T001 Verify Alembic head is still `056` and the revision chain `001→056` is linear
  - **Purpose**: plan.md §33 numbers new migrations from `057`; a different head invalidates the whole migration plan.
  - **Files**: `backend/migrations/versions/` (read-only)
  - **Deps**: none
  - **Acceptance**: Highest file is `056_crm_permission_backfill.py` with `revision = "056"`; no branching `down_revision`. If not → STOP and report.
  - **Result (2026-08-19)**: PASS. Single head `056`, no duplicate `down_revision`, full chain `001→056` walks cleanly (56/56 revisions). 8 Sales-epic migration files (`026`–`033`) embed a descriptive suffix in their `revision` string (e.g. `"030_sales_delivery"`) rather than a bare zero-padded number — a pre-existing naming quirk, not a chain break; the linear walk succeeds regardless.

- [X] T002 [P] Verify `Session` model still has no `company_id` and `Session.created_at` is still inherited/immutable
  - **Purpose**: ADR-6's entire authentication-freshness mechanism depends on this (plan.md §3.1).
  - **Files**: `backend/modules/auth/models/session.py`, `backend/core/database/models/base_model.py` (read-only)
  - **Deps**: none
  - **Acceptance**: `sessions` has `user_id`, `is_revoked`, `revoked_at`, no `company_id`; `created_at` comes from `BaseModel` with `server_default=func.now()`. If drifted → STOP.
  - **Result (2026-08-19)**: PASS. No drift from plan.md §3.1.

- [X] T003 [P] Verify `login()` creates a new `Session` and `refresh()` reuses the existing `session_id`
  - **Purpose**: The single fact that makes `Session.created_at` a valid authentication-freshness value (ADR-6).
  - **Files**: `backend/modules/auth/services/auth_service.py` (read-only)
  - **Deps**: none
  - **Acceptance**: `login()` calls `create_session(...)`; `refresh()` calls `create_access_token(session_id=new_record.session_id)` and never `create_session`. If drifted → STOP; ADR-6 must be re-planned, not patched.
  - **Result (2026-08-19)**: PASS. `refresh()` contains zero calls to `create_session`. No drift.

- [X] T004 [P] Verify `CompanyStatus` enum values and `Company` lifecycle fields are unchanged
  - **Purpose**: §9's suspend/reactivate design reuses the existing 5-state enum exactly.
  - **Files**: `backend/modules/companies/models/enums.py`, `models/company.py` (read-only)
  - **Deps**: none
  - **Acceptance**: Enum still `pending_setup|active|inactive|suspended|deleted`; `subscription_id` still nullable with no FK.
  - **Result (2026-08-19)**: PASS. No drift.

- [X] T005 [P] Verify all five business-module routers still mount `get_current_company_member` and that it still does **not** read `Company.status`
  - **Purpose**: The §3.3 enforcement gap that Phase 7 closes; also the mount point Phase 9 adds entitlement enforcement to.
  - **Files**: `backend/api/v1/router.py`, `backend/modules/users_roles/dependencies.py` (read-only)
  - **Deps**: none
  - **Acceptance**: Inventory/Purchase/Sales/Accounting/CRM all mount `get_current_company_member`; that function checks only `CompanyMember.status`. If a company-status check was added meanwhile → re-scope Phase 7 and report.
  - **Result (2026-08-19)**: PASS. All five mount it via `backend/api/v1/router.py`; the dependency body checks only `CompanyMember.status in ("active", "pending_invitation")`. No drift; Phase 7 scope stands as planned.

- [X] T006 [P] Verify feature-toggle authorization findings still hold: Inventory/Sales/Purchase unguarded; Accounting/CRM already gated
  - **Purpose**: Phase 10 hardens exactly 3 modules; hardening an already-fixed module is wasted/duplicated work.
  - **Files**: `backend/modules/{inventory,sales,purchase,accounting,crm}/router.py` (read-only)
  - **Deps**: none
  - **Acceptance**: Inventory/Sales/Purchase `PUT .../feature-flags/{flag_key}` still only `require_authenticated` + membership; Accounting still calls `user_has_accounting_permission`; CRM still `require_admin_or_above()`.
  - **Result (2026-08-19)**: PASS. No drift; Phase 10's 3-module scope stands as planned.

- [X] T007 [P] Verify the `/platform-admin/...` frontend namespace and `/api/v1/platform/...` API namespace are still collision-free
  - **Purpose**: Epic 9 lost days to a Next.js dynamic-route collision; plan.md §3.14 verified this namespace is clear.
  - **Files**: `frontend/src/app/(protected)/`, `backend/api/v1/router.py` (read-only)
  - **Deps**: none
  - **Acceptance**: No existing route group produces `/platform-admin/*`; no router mounts `/platform`. Confirm `(crm)` still owns bare `/reports` and `/settings` (must not be reused).
  - **Result (2026-08-19)**: PASS. No collision; `(crm)` still owns bare `/reports` and `/settings`.

- [X] T008 [P] Verify `frontend/src/lib/api/client.ts` still hardcodes tenant auth at module scope
  - **Purpose**: ADR-11's `AuthStrategy` refactor is scoped to this exact shape.
  - **Files**: `frontend/src/lib/api/client.ts` (read-only)
  - **Deps**: none
  - **Acceptance**: `buildHeaders()`/`postMultipart()` call `getAccessToken()` directly; 401 branch calls `acquireRefreshLock()` directly; constructor already accepts `baseUrl`.
  - **Result (2026-08-19)**: PASS. No drift; ADR-11's refactor scope stands as planned.

- [X] T009 Establish green baseline: full backend suite + `tsc --noEmit` + `eslint` before any Epic 9A change
  - **Purpose**: Any later failure must be attributable to Epic 9A, not pre-existing breakage.
  - **Files**: `backend/tests/`, `frontend/`
  - **Deps**: T001–T008
  - **Acceptance**: Baseline pass/fail counts recorded in the implementation log. Known-flaky tests noted explicitly, not silently ignored.
  - **Result (2026-08-19, real Docker/PostgreSQL, `erp-system-api-1`/`erp-system-web-1`)**: Backend: **5638 passed, 3 failed, 8 skipped** (5649 collected, 4125.51s). Frontend: `tsc --noEmit` clean (0 errors); `eslint` 0 errors, 55 pre-existing warnings (mostly `no-img-element`). 3 backend failures characterized individually (none touch `platform_admin`, `auth`, `companies`, or any file Epic 9A will modify — zero source files were changed this session, so none are attributable to Epic 9A):
    - `tests/unit/core/test_settings.py::test_settings_default_debug_is_false` — **pre-existing environment artifact**, not flaky: fails deterministically because the container's `.env` sets `DEBUG=true` for local dev and `Settings()` reads it from the environment, overriding the test's assumed default. Reproduces in isolation.
    - `tests/performance/accounting/test_report_performance.py::TestReportPerformance::test_trial_balance_and_balance_sheet_regression_guard` — **Full suite: FAILED. Isolation rerun: PASSED.** Characterized as load/order-sensitive or flaky based on the available evidence — a performance/timing-threshold test contending with 5648 other tests in one process. The full-suite failure is not rewritten as a pass; both results are recorded.
    - `tests/unit/modules/accounting/test_recurring_journal_service.py::TestDueTemplateExecutes::test_due_template_creates_and_posts_journal` — **Full suite: FAILED. Isolation rerun: PASSED.** Same characterization as above; both results recorded.

---

## Phase 2: Database & Migration Foundation — **Gate A**

**Objective**: Create migrations `057`–`061` exactly as owned in plan.md §33 / data-model.md. No migration `062` (bootstrap is deliberately not a migration, ADR-8).
**Prerequisites**: Phase 1 green.
**Exit condition (Gate A)**: T024–T031 pass on real PostgreSQL.

### Tasks

- [X] T010 Create migration `057` upgrade: platform identity/session/audit tables
  - **Purpose**: Platform foundation persistence (data-model.md "Identity & Session").
  - **Files**: `backend/migrations/versions/057_platform_admin_foundation.py`
  - **Deps**: T001
  - **Acceptance**: Creates `platform_administrators`, `platform_roles`, `platform_permissions`, `platform_role_permissions`, `platform_admin_role_assignments`, `platform_sessions`, `platform_refresh_tokens`, `platform_audit_events` with the exact columns/FKs/uniques in data-model.md. `revision="057"`, `down_revision="056"`.
  - **Result (2026-08-19)**: DONE. All 8 tables created; column-by-column audit against data-model.md performed (see T031 sign-off). `grain`/`enforcement_style`-style "enum(...)" fields implemented as VARCHAR+CHECK, not PG ENUM, consistent with `Plan.status`'s explicit convention and this codebase's project-wide anti-native-ENUM pattern — verified on real PostgreSQL via `\d`.

- [X] T011 Add to migration `057`: the two additive `companies` lifecycle columns
  - **Purpose**: `pre_suspension_status` + `access_invalidated_at` (ADR-12, ADR-6 Layer 2).
  - **Files**: `backend/migrations/versions/057_platform_admin_foundation.py`
  - **Deps**: T010
  - **Acceptance**: Both columns added as **nullable** with no backfill; existing rows unaffected.
  - **Result (2026-08-19)**: DONE. Verified via T030's real-PostgreSQL test: pre-existing seeded rows identical after upgrade, both new columns NULL.

- [X] T012 Add to migration `057`: **mandatory suspended-company preflight guard** (runs before any constraint is created)
  - **Purpose**: plan.md §33.1 — a pre-existing `status='suspended'` row has an unrecoverable prior status; fabricating one would make `suspended → pre-suspension status` non-deterministic.
  - **Files**: `backend/migrations/versions/057_platform_admin_foundation.py`
  - **Deps**: T011
  - **Acceptance**: Queries `SELECT id, slug FROM companies WHERE status='suspended'`. Zero rows → proceed. One or more → `raise RuntimeError(...)` naming the affected slugs **and** the remediation options, having created **no** column and **no** constraint. Must never backfill `active`/`inactive`, never weaken/skip the constraint, never infer from audit.
  - **Result (2026-08-19)**: DONE, verified on real PostgreSQL by T025/T026 — refusal message names the affected slug and both remediation options; T026 additionally proves zero partial state (schema snapshot equal, `alembic_version` unchanged at `056`).

- [X] T013 Add to migration `057`: the two CHECK constraints on `companies`
  - **Purpose**: Structurally prevent a suspended company without a restore target, and restrict the restore target's domain (plan.md §26).
  - **Files**: `backend/migrations/versions/057_platform_admin_foundation.py`
  - **Deps**: T012
  - **Acceptance**: `CHECK ((status='suspended' AND pre_suspension_status IS NOT NULL) OR (status<>'suspended' AND pre_suspension_status IS NULL))` and `CHECK (pre_suspension_status IS NULL OR pre_suspension_status IN ('active','inactive'))` both present.
  - **Result (2026-08-19)**: DONE. Both constraints confirmed present via `\d companies` on real PostgreSQL (`ck_companies_pre_suspension_status_presence`, `ck_companies_pre_suspension_status_domain`).

- [X] T014 Add migration `057` indexes on `platform_audit_events`
  - **Purpose**: FR-9A-200's filter set must not table-scan.
  - **Files**: `backend/migrations/versions/057_platform_admin_foundation.py`
  - **Deps**: T010
  - **Acceptance**: Indexes on `actor_platform_administrator_id`, `company_id`, `action`, `created_at`.
  - **Result (2026-08-19)**: DONE. All 4 indexes created (`ix_platform_audit_events_{actor_id,company_id,action,created_at}`).

- [X] T015 Write migration `057` downgrade
  - **Purpose**: Constitution §18 requires reversible migrations.
  - **Files**: `backend/migrations/versions/057_platform_admin_foundation.py`
  - **Deps**: T010–T014
  - **Acceptance**: Drops both `companies` columns + both constraints and all 8 tables in reverse FK order. Preflight has no downgrade counterpart (upgrade-time guard only).
  - **Result (2026-08-19)**: DONE, verified via real-PostgreSQL up→down→up cycle (T027) — all 8 tables and both columns/constraints cleanly absent after downgrade to `056`.

- [X] T016 Create migration `058`: capabilities, plans, plan_capabilities, subscriptions + `companies.subscription_id` FK
  - **Purpose**: Commercial control plane persistence (data-model.md "Entitlement").
  - **Files**: `backend/migrations/versions/058_platform_plans_entitlements.py`
  - **Deps**: T015
  - **Acceptance**: All 4 tables per data-model.md; **partial unique index** `ON subscriptions (company_id) WHERE status='active'`; real FK added to the already-nullable `companies.subscription_id`; `status` columns are VARCHAR+CHECK (not PG ENUM), matching `CompanyStatus`'s convention.
  - **Result (2026-08-19)**: DONE. Verified via `\d+ subscriptions` on real PostgreSQL: `uq_subscriptions_company_active UNIQUE, btree (company_id) WHERE status::text = 'active'::text`, `fk_companies_subscription_id` present. `Subscription.reason` implemented nullable at the DB level — data-model.md states "NOT NULL for **administrative** changes" (a conditional business rule enforced at the service layer in a later phase), not an unconditional DB constraint; a blanket NOT NULL would have wrongly rejected the initial non-administrative assignment path.

- [X] T017 Write migration `058` downgrade
  - **Files**: `backend/migrations/versions/058_platform_plans_entitlements.py`
  - **Deps**: T016
  - **Acceptance**: Drops the FK constraint (leaving the pre-existing nullable column intact — it predates Epic 9A) then the 4 tables in reverse order.
  - **Result (2026-08-19)**: DONE, verified via T027 — after downgrade to `056`, `companies.subscription_id` column still present (only its FK dropped), all 4 tables absent.

- [X] T018 Create migration `059`: quota_definitions, plan_quotas, tenant_quota_overrides, entitlement_overrides
  - **Purpose**: Quota + override persistence (data-model.md "Quotas & Overrides"). Consumed by the Phase 8 quota foundation.
  - **Files**: `backend/migrations/versions/059_platform_quotas_overrides.py`
  - **Deps**: T017
  - **Acceptance**: 4 tables; partial unique indexes `WHERE is_active=true` on both override tables; `limit_value >= 0` CHECK where not null; `expires_at > granted_at` CHECK where not null.
  - **Result (2026-08-19)**: DONE. Both partial unique indexes and all CHECK constraints confirmed via `\d+` on real PostgreSQL. Also added `ck_tenant_quota_overrides_expiry`/`ck_entitlement_overrides_expiry` (`expires_at > granted_at`) per plan.md §26 ("Valid date ranges" — applies to override and support-access tables), sourced from plan.md since data-model.md's compact field table doesn't restate every CHECK per section.

- [X] T019 Write migration `059` downgrade
  - **Files**: `backend/migrations/versions/059_platform_quotas_overrides.py`
  - **Deps**: T018
  - **Acceptance**: Clean reverse drop.
  - **Result (2026-08-19)**: DONE, verified via T027's up→down→up cycle.

- [X] T020 Create migration `060`: usage_records, ai_credit_ledger_entries
  - **Purpose**: Usage metering + provider-neutral AI readiness (data-model.md "Usage & AI Readiness").
  - **Files**: `backend/migrations/versions/060_platform_usage_ai_readiness.py`
  - **Deps**: T019
  - **Acceptance**: Both tables with indexed `company_id`; `ai_credit_ledger_entries.delta` signed numeric; `provider`/`model` free-text nullable (no vendor coupling, BR-9A-026).
  - **Result (2026-08-19)**: DONE. `provider`/`model` are plain nullable VARCHAR (no enum/FK to a provider table) — confirmed provider-neutral. `reason` implemented nullable at the DB level, matching data-model.md's conditional wording ("Required when `actor_platform_administrator_id` is populated" — a service-layer rule, not an unconditional DB constraint).

- [X] T021 Write migration `060` downgrade
  - **Files**: `backend/migrations/versions/060_platform_usage_ai_readiness.py`
  - **Deps**: T020
  - **Acceptance**: Clean reverse drop.
  - **Result (2026-08-19)**: DONE, verified via T027's up→down→up cycle.

- [X] T022 Create migration `061`: support_access_grants + `platform_audit_events.support_access_grant_id` FK
  - **Purpose**: Support-access persistence and its audit linkage (BR-9A-022 — no parallel audit table).
  - **Files**: `backend/migrations/versions/061_platform_support_access.py`
  - **Deps**: T021
  - **Acceptance**: `support_access_grants` per data-model.md; nullable FK column added to `platform_audit_events`; indexed `platform_administrator_id`, `company_id`. **This is the final Epic 9A migration — no `062` exists.**
  - **Result (2026-08-19)**: DONE. Deferred FK (`fk_platform_audit_events_support_access_grant_id`, added in 057 as a bare nullable column, FK closed here — same technique as migration 055's `crm_leads`/`crm_opportunities` cycle) confirmed via `\d platform_audit_events`. No `062` file exists — verified by T029.

- [X] T023 Write migration `061` downgrade
  - **Files**: `backend/migrations/versions/061_platform_support_access.py`
  - **Deps**: T022
  - **Acceptance**: Drops the FK column then the table.
  - **Result (2026-08-19)**: DONE, verified via T027's up→down→up cycle.

- [X] T024 [P] Migration test: clean database with **no** suspended companies → `057` succeeds
  - **Purpose**: Gate A normal path.
  - **Files**: `backend/tests/integration/migrations/test_057_preflight.py`
  - **Deps**: T015
  - **Acceptance**: Both columns and both CHECK constraints exist afterwards.
  - **Result (2026-08-19, real Docker/PostgreSQL, ephemeral per-test database on `erp-system-db-1`)**: PASS — `test_057_succeeds_with_no_suspended_companies`.

- [X] T025 [P] Migration test: database with a pre-existing `status='suspended'` row → `057` **refuses**
  - **Purpose**: Gate A — the core Correction-2 guarantee.
  - **Files**: `backend/tests/integration/migrations/test_057_preflight.py`
  - **Deps**: T015
  - **Acceptance**: Raises with a message naming the affected company and the remediation options; exit is a failure, not a warning.
  - **Result (2026-08-19, real PostgreSQL)**: PASS — `test_057_refuses_with_pre_existing_suspended_row`. Asserts the affected slug, "cannot proceed", "MUST NOT be guessed", and both remediation words ("active"/"inactive") are all present in the raised message.

- [X] T026 [P] Migration test: refused `057` leaves the database **byte-for-byte unchanged**
  - **Purpose**: Proves no partial/fabricated state (no column added, no constraint created, no `pre_suspension_status` backfilled).
  - **Files**: `backend/tests/integration/migrations/test_057_preflight.py`
  - **Deps**: T025
  - **Acceptance**: Post-failure schema snapshot equals pre-run snapshot; `pre_suspension_status` column absent.
  - **Result (2026-08-19, real PostgreSQL)**: PASS — `test_refused_057_leaves_no_partial_state`. Column set, CHECK constraint set, and `alembic_version` all identical before/after the failed attempt (version stays `056`), proving Alembic's own transaction wrapper rolled back every DDL statement the migration had issued before raising.

- [X] T027 **[Gate A]** Real-PostgreSQL migration cycle `056 → 061 → 056 → 061`
  - **Purpose**: Partial unique indexes and CHECK constraints are PostgreSQL-specific; SQLite cannot substitute (plan.md §32).
  - **Files**: Docker Compose `db` service; `backend/tests/integration/migrations/test_migration_cycle_postgres.py`
  - **Deps**: T023, T024–T026
  - **Acceptance**: Clean in both directions; `\dt platform_*`, `\d companies`, `\d subscriptions` verified after each step.
  - **Result (2026-08-19, real Docker/PostgreSQL)**: PASS — `test_full_up_down_up_cycle_on_real_postgres`. All 19 platform/entitlement/quota/usage/support tables present after each upgrade step and absent after downgrade; `companies.subscription_id` column survives downgrade (only its FK is dropped, per T017); the `subscriptions` partial unique index present/absent/present correctly across the cycle.

- [X] T028 **[Gate A]** Real-PostgreSQL test: after remediation of a suspended row, `057` succeeds and the cycle completes
  - **Purpose**: Proves the documented operator remediation path actually works.
  - **Files**: `backend/tests/integration/migrations/test_057_preflight.py`
  - **Deps**: T027
  - **Acceptance**: Operator sets the row's status back to its true prior value → re-run succeeds → up/down/up clean.
  - **Result (2026-08-19, real PostgreSQL)**: PASS — `test_remediation_then_057_succeeds_and_cycle_completes`. Suspended row remediated to `active` → `057` succeeds → full chain to `061` → downgrade to `056` → upgrade to `061` again, all clean.

- [X] T029 [P] **[Gate A]** Verify migrations create **no** Platform Owner and that no `062` exists
  - **Purpose**: ADR-8 — credential provisioning is decoupled from schema versioning; also freezes the migration contract.
  - **Files**: `backend/tests/integration/migrations/test_no_bootstrap_in_migrations.py`
  - **Deps**: T027
  - **Acceptance**: After `upgrade head`, `SELECT count(*) FROM platform_administrators` is `0`. No migration file references bootstrap env vars. **No file named `062_*.py` exists** and head is `061`.
  - **Result (2026-08-19, real PostgreSQL + static filesystem scan)**: PASS — 3 tests: `platform_administrators` count is `0` after `upgrade head`; no migration file references `PLATFORM_OWNER_BOOTSTRAP_EMAIL`/`PLATFORM_OWNER_BOOTSTRAP_PASSWORD_HASH`; no `062_*.py` file exists and the migration DAG's sole head is `061`.

- [X] T030 [P] **[Gate A]** Verify existing tenant data is untouched by `057`–`061`
  - **Purpose**: Backward-compatibility guarantee (plan.md §33).
  - **Files**: `backend/tests/integration/migrations/test_existing_tenant_preservation.py`
  - **Deps**: T027
  - **Acceptance**: Seed companies/members/feature-flag rows before upgrade; all identical afterwards; new columns NULL everywhere.
  - **Result (2026-08-19, real PostgreSQL)**: PASS — `test_pre_epic_9a_rows_survive_057_to_061_unchanged`. Seeded `companies`/`roles`/`company_members`/`inventory_feature_flags` rows at `056`; all fields byte-for-byte identical after upgrade to `061`; both new `companies` columns NULL on the seeded row.

- [X] T031 **[Gate A]** Gate A sign-off — record results in the implementation log
  - **Deps**: T024–T030
  - **Acceptance**: All Gate A tasks green. **Do not start Phase 3 until this passes.**
  - **Result (2026-08-19)**: **GATE A: PASS.** 9/9 real-PostgreSQL tests green (T024, T025, T026, T027, T028, T029×3, T030) on the actual Docker Compose `db` service via ephemeral per-test databases — SQLite never used as proof for any Postgres-specific behaviour. Full migration chain `001→061` verified from empty; up→down→up cycle clean; preflight guard proven both to refuse correctly and to leave zero partial state; no bootstrap credential path exists in any migration; no `062` file exists; pre-existing tenant data (companies/roles/members/feature-flags) proven byte-for-byte unaffected. Phase 3 may now begin.

---

## Phase 3: Platform Domain, Audit Foundation & Administrator Identity

**Objective**: Create `backend/modules/platform_admin/`, the **fail-closed audit foundation** (needed by every audited mutation from here on), and the `PlatformAdministrator` principal (ADR-1). Per plan.md §36 Phase A, audit foundation belongs alongside identity — it is created here so that no later task references an audit service that does not yet exist.
**Prerequisites**: Gate A.
**Exit condition**: `import modules.platform_admin` clean; a trivial audited mutation writes an audit row atomically (T044).

### Tasks

- [X] T032 Create the `platform_admin` module skeleton
  - **Purpose**: Match the most complete existing module shape (accounting/crm, plan.md §4).
  - **Files**: `backend/modules/platform_admin/{__init__,constants,exceptions}.py` + `{models,repositories,services,schemas,events}/__init__.py` + `dependencies.py`, `router.py`
  - **Deps**: T031
  - **Acceptance**: `import modules.platform_admin` succeeds; directory shape matches `modules/accounting/`.
  - **Result (2026-08-20)**: DONE. All files present; `import modules.platform_admin` (+ every submodule) verified inside `erp-system-api-1`. Directory shape matches `modules/accounting/` minus `handlers/`, which T032's own Files list deliberately excludes. `router.py` is an empty, unmounted `APIRouter()` — no route exists yet, consistent with the Architecture Freeze's "do not pre-create future routes."

- [X] T033 Define `PLATFORM_PERMISSION_CODES` and candidate role bundles in `constants.py`
  - **Purpose**: Single source of truth for the permission catalogue (spec §15.1, plan §8).
  - **Files**: `backend/modules/platform_admin/constants.py`
  - **Deps**: T032
  - **Acceptance**: All permission codes from spec §15.1 present as a frozenset; the 6 candidate role bundles from spec §15.2 defined as **data**, not enum members (configurable per FR-9A-140/Constitution §46).
  - **Result (2026-08-20)**: DONE. 29 codes collected verbatim from every literal code in spec.md §15.1's table; cross-checked against all 21 `x-permission` values in `contracts/platform-admin-v1.yaml` — a strict subset, zero drift. 6 role bundles built as `tuple[dict, ...]` (plain data), each `permission_codes` set expanded explicitly from spec.md §15.2's prose (e.g. `platform.plans.*` → `plans.read`+`plans.manage`), with the expansion logic documented inline since these are non-mandatory candidates.

- [X] T034 Define Platform exception types
  - **Purpose**: Consistent error envelope matching the project-wide `ApplicationException` convention.
  - **Files**: `backend/modules/platform_admin/exceptions.py`
  - **Deps**: T032
  - **Acceptance**: `PlatformSessionInvalidError` (401), `InsufficientPlatformPermissionError` (403), `CapabilityNotEntitledError` (403), `SupportAccessExpiredError` (403), `LastPlatformOwnerError` (409), `TenantLifecycleTransitionError` (409) — each with a stable `code`.
  - **Result (2026-08-20)**: DONE. All 6 exceptions defined, each subclassing the matching `core.exceptions.base` typed exception (`UnauthorizedException`/`ForbiddenException`×3/`ConflictException`×2) with an explicit `self.code` override, exactly matching `modules/accounting/exceptions.py`'s convention.

- [X] T035 [US-8] [BR-9A-022] Create `PlatformAuditEvent` model
  - **Purpose**: Audit persistence must exist before any audited mutation is written (moved ahead of identity/RBAC in Revision 2).
  - **Files**: `backend/modules/platform_admin/models/platform_audit_event.py`
  - **Deps**: T032
  - **Acceptance**: Full column set per data-model.md incl. nullable `company_id`, `reason`, `before_state`/`after_state` JSONB, `context` (with `request_id`), and the nullable `support_access_grant_id` FK (populated from Phase 12 onward).
  - **Result (2026-08-20)**: DONE. Full column set matches data-model.md and migration 057 exactly (verified column-by-column, including all 4 indexes). `support_access_grant_id` is a bare nullable UUID column with no `ForeignKey()` object — `support_access_grants` has no ORM model until Phase 12 — mirroring migration 057→061's own deferred-FK technique at the ORM layer. All UUID columns given explicit `Uuid(as_uuid=True)` types (self-review caught that relying on SQLAlchemy's implicit `type_annotation_map` inference for FK-typed columns is import-order-fragile — resolved to `NullType()` when this file was imported standalone without `companies.models` pre-loaded; explicit types make every column's type independent of import order).

- [X] T036 [BR-9A-023] Create `PlatformAuditRepository` — **flush only, never commit**
  - **Purpose**: The mechanical precondition for fail-closed atomicity (ADR-5, plan §3.5).
  - **Files**: `backend/modules/platform_admin/repositories/platform_audit_repository.py`
  - **Deps**: T035
  - **Acceptance**: `record()` does `db.add()` + `db.flush()` and **never** `db.commit()`; there is no update or delete method at all (append-only).
  - **Result (2026-08-20)**: DONE. Mirrors `AccountingAuditLogRepository.create()` exactly. No update/delete method exists. Deliberately does not inherit `BaseRepository` (which mandates `company_id` filtering — wrong for a platform-scoped table). Proven fail-closed by T044.

- [X] T037 [ADR-5] Create the audited-mutation service helper
  - **Purpose**: One reusable pattern so every privileged service commits state + audit (+ outbox) together. Every audited task in Phases 3–12 depends on this.
  - **Files**: `backend/modules/platform_admin/services/platform_audit_service.py`
  - **Deps**: T036
  - **Acceptance**: Callers flush their state change, flush the audit row, then perform a **single** service-level `db.commit()`. Must not use `BaseRepository.create()/.update()`'s auto-commit for audited paths.
  - **Result (2026-08-20)**: DONE. `PlatformAuditService.record()` mirrors `AuditLogService.record()` exactly — stages the audit row (flush-only) and returns it; does **not** commit. The calling domain service (T040) owns the single commit, matching plan.md §3.5's "service layer owns a single `db.commit()`" precedent precisely (not the audit service itself). Proven by T044's two tests (success + forced-failure rollback).

- [X] T038 [US-7] [FR-9A-030] Create `PlatformAdministrator` model
  - **Purpose**: First-class platform principal, 1:1 with `User`, **never** `TenantBaseModel` (no `company_id`).
  - **Files**: `backend/modules/platform_admin/models/platform_administrator.py`
  - **Deps**: T032
  - **Acceptance**: Inherits `BaseModel`; `user_id` FK UNIQUE NOT NULL; `is_active`, `last_login_at`, `deactivated_at`, `deactivated_by` per data-model.md.
  - **Result (2026-08-20)**: DONE. Inherits `BaseModel` only — no `company_id` anywhere. All 5 columns match data-model.md and migration 057 exactly. All UUID columns given explicit `Uuid(as_uuid=True)` types for the same import-order-independence reason as T035. FR-9A-030 (create independent of tenant membership) proven by T042.

- [X] T039 [US-7] Create `PlatformAdministratorRepository`
  - **Purpose**: Platform-scoped data access; must **not** use `BaseRepository` (which mandates `company_id` filtering).
  - **Files**: `backend/modules/platform_admin/repositories/platform_administrator_repository.py`
  - **Deps**: T038
  - **Acceptance**: `get_by_user_id`, `get_by_id`, `list_paginated`, `create`, `set_active`. Audited write paths use `flush()` only, never `commit()` (ADR-5).
  - **Result (2026-08-20)**: DONE. All 5 methods present; does not inherit `BaseRepository`. `create()`/`set_active()` both `flush()` only — verified by T044's atomicity tests (no premature commit anywhere in the write path).

- [X] T040 [US-7] [FR-9A-031] Create `PlatformAdministratorService` — account lifecycle **without** session revocation
  - **Purpose**: Domain foundation for create/activate/deactivate. Session revocation is deliberately **not** here — `PlatformSessionRepository` does not exist until Phase 4 (Revision 2 split).
  - **Files**: `backend/modules/platform_admin/services/platform_administrator_service.py`
  - **Deps**: T039, T037
  - **Acceptance**: Create/activate/deactivate change `is_active` and write an audit row in one transaction via T037's helper. Deactivation is **not yet complete** with respect to BR-9A-011 — T054 adds mandatory session revocation, and the service must expose a seam (e.g. an injected revoker) rather than being rewritten later.
  - **Result (2026-08-20)**: DONE, with the documented Phase-3 gap. `create()`/`activate()`/`deactivate()` each flush their state change, call `PlatformAuditService.record()`, then a single `self.db.commit()` — proven atomic by T044. Exposes a `SessionRevoker` `Protocol` seam, injected via the constructor (`session_revoker: SessionRevoker | None = None`); with none injected (the Phase 3 state), `deactivate()` performs only the account-state change and its audit record. **FR-9A-031/BR-9A-011's "immediately invalidating active platform sessions" clause is intentionally NOT yet satisfied** — that is Phase 4's T054, which will inject a real revoker into this exact seam without rewriting this service.

- [X] T041 [P] [US-7] Create Platform administrator request/response schemas
  - **Files**: `backend/modules/platform_admin/schemas/platform_administrator.py`
  - **Deps**: T032
  - **Acceptance**: Pydantic v2 with explicit field allow-lists (mass-assignment protection, plan §28); no password or token field ever echoed.
  - **Result (2026-08-20)**: DONE. `CreatePlatformAdministratorRequest` carries only `user_id` (no `is_active`/role field — matches Phase 5's T068 constraint exactly). `UpdatePlatformAdministratorRequest` carries only `is_active`+`reason` (activate/deactivate only). `PlatformAdministratorResponse` has no password/token field.

- [X] T042 [P] [US-7] [BR-9A-010] Test: a Platform Administrator with **zero** company memberships is a valid, complete principal
  - **Files**: `backend/tests/integration/services/platform_admin/test_platform_administrator.py`
  - **Deps**: T040
  - **Acceptance**: Account created with no `CompanyMember` row anywhere; no membership check blocks its creation or role assignment. (API-level proof follows in T059.)
  - **Result (2026-08-20, SQLite in-memory, `db_session` fixture)**: PASS — 2 tests. Assertions scoped to the created user's own id (not a table-wide count), since the shared test database persists rows across test functions within one pytest session — a pre-existing property of the project's `db_session` fixture discovered during this phase, not a defect introduced here (see Defects Discovered in the closure report).

- [X] T043 [P] [US-7] [BR-9A-001] Test: tenant `owner`/`admin` role grants **no** Platform authority
  - **Files**: `backend/tests/security/modules/platform_admin/test_identity_boundary.py`
  - **Deps**: T040
  - **Acceptance**: Creating a `CompanyMember` never creates a `PlatformAdministrator`; no tenant role value maps to a platform principal. (API-level proof follows in T055.)
  - **Result (2026-08-20, SQLite in-memory)**: PASS — 2 tests (owner role rank 100, admin role rank 90). Both assert `PlatformAdministratorRepository.get_by_user_id()` returns `None` for the tenant user, scoped to that user's id.

- [X] T044 [ADR-5] Test: the audit foundation writes atomically on a trivial audited action
  - **Purpose**: plan.md §36 Phase A — "audit foundation proven with a trivial first audited action", before any complex mutation depends on it.
  - **Files**: `backend/tests/integration/services/platform_admin/test_audit_foundation.py`
  - **Deps**: T040, T037
  - **Acceptance**: A `PlatformAdministrator` deactivation writes exactly one `PlatformAuditEvent` with correct before/after, committed in the same transaction as the `is_active` change.
  - **Result (2026-08-20, SQLite in-memory)**: PASS — 2 tests, going beyond the literal acceptance text per the master-implementation-prompt's §20 fail-closed standard ("a test that only checks an audit row eventually exists is insufficient"): (1) the literal acceptance — exactly one `platform_administrator.deactivate` event, correct before/after, `target_type`, `reason`; (2) a forced-failure test — `PlatformAuditService.record` patched to raise, proving the `is_active` state change does **not** survive (`db_session.rollback()` restores it to `True`) and zero deactivate-audit rows exist, since `db.commit()` is never reached.

---

## Phase 4: Platform Authentication / Session Boundary

**Objective**: A structurally separate Platform session system (ADR-1), and completion of BR-9A-011 session-revoking deactivation now that `PlatformSessionRepository` exists.
**Prerequisites**: Phase 3.
**Exit condition**: Platform login/refresh/logout work; tenant and platform tokens are mutually unusable; deactivation revokes sessions.

### Tasks

- [X] T045 [FR-9A-036] Create `PlatformSession` model
  - **Files**: `backend/modules/platform_admin/models/platform_session.py`
  - **Deps**: T032
  - **Acceptance**: Mirrors `sessions`' shape (`platform_administrator_id`, `is_revoked`, `revoked_at`, `ip_address`, `user_agent`, `expires_at`); a **separate table**, never reusing tenant `sessions` (BR-9A-003).
  - **Result (2026-08-20)**: DONE. Matches migration 057's `platform_sessions` exactly. `ip_address` uses `INET` — data-model.md's explicit choice for this table, unlike tenant `sessions.ip_address`'s `String(45)`.

- [X] T046 Create `PlatformRefreshToken` model
  - **Files**: `backend/modules/platform_admin/models/platform_refresh_token.py`
  - **Deps**: T045
  - **Acceptance**: SHA-256 `token_hash` (raw token never persisted), FK to `platform_sessions`, rotate-on-use fields, `is_revoked`/`revoked_at`.
  - **Result (2026-08-20)**: DONE. Matches migration 057's `platform_refresh_tokens` exactly (no `unique=True` on `token_hash` at the ORM level, matching the already-committed migration precisely — no model/migration drift).

- [X] T047 Create `PlatformSessionRepository` (incl. bulk revoke-by-administrator)
  - **Purpose**: Ordered before every consumer (Revision 2 fix — previously created after the service that needed it).
  - **Files**: `backend/modules/platform_admin/repositories/platform_session_repository.py`
  - **Deps**: T045
  - **Acceptance**: `create`, `get_by_id`, `revoke`, `revoke_all_for_administrator`. Audited paths flush-only.
  - **Result (2026-08-20)**: DONE. All 5 methods present (plus `get_active_by_administrator`); every write path `flush()`-only, matching every other Platform repository (ADR-5). `revoke_all_for_administrator(platform_administrator_id: UUID) -> None` structurally satisfies T040's `SessionRevoker` `Protocol` — no adapter class needed; the repository is passed directly as `session_revoker` (proved by T054/T059).

- [X] T048 Implement Platform JWT issuance with a distinct `typ`
  - **Purpose**: The structural guarantee that a tenant token can never be a platform token (ADR-1).
  - **Files**: `backend/modules/platform_admin/services/platform_jwt_service.py`
  - **Deps**: T045
  - **Acceptance**: Access tokens carry `typ="platform_access"`, refresh `typ="platform_refresh"`; reuses the existing `PyJWT`/HS256 settings — **no new crypto, no new secret management**.
  - **Result (2026-08-20)**: DONE. Both token kinds are signed JWTs (verified: the tenant system has **no** `typ="refresh"` anywhere — its refresh tokens are opaque `secrets.token_urlsafe()` strings, not JWTs; plan.md's parenthetical comparison to "tenant tokens use typ: access/refresh today" does not match repository reality. T048's own acceptance is unambiguous and self-contained regardless, and data-model.md's `token_hash` field accommodates a JWT-format raw credential exactly as it would an opaque one — documented here as a discovered planning-narrative inaccuracy, not a blocking contradiction). `sub` = `PlatformAdministrator.id` (not `User.id`) — the design choice that makes a Platform token structurally rejected by `get_current_user()` with zero change to that function (see T052/T056).

- [X] T049 Implement `POST /api/v1/platform/auth/login`
  - **Purpose**: Authenticate against the same `User.password_hash`, then require an **active** `PlatformAdministrator` row.
  - **Files**: `backend/modules/platform_admin/services/platform_auth_service.py`, `router.py`
  - **Deps**: T048, T047, T040
  - **Acceptance**: Creates a `PlatformSession` + `PlatformRefreshToken`; a `User` without an active `PlatformAdministrator` gets a **generic** invalid-credentials response that does not reveal whether the email exists as a tenant user.
  - **Result (2026-08-20)**: DONE. Unknown email, wrong password, and a real user with no active `PlatformAdministrator` all raise the identical `AuthenticationException`. Also created `PlatformRefreshTokenRepository` and `schemas/platform_auth.py` (no separate task named these; both are T049's own necessary implementation surface). Live-verified via real HTTP through `test_client`.

- [X] T050 Implement `POST /api/v1/platform/auth/refresh` (rotate-on-use)
  - **Files**: `backend/modules/platform_admin/services/platform_auth_service.py`, `router.py`
  - **Deps**: T049
  - **Acceptance**: Rotates the platform refresh token, reuses the same `PlatformSession`, rejects a revoked session or a deactivated administrator.
  - **Result (2026-08-20)**: DONE. 4 dedicated tests: rotation + new-token-works, replay-of-rotated-token rejected, revoked-session rejected, tenant-typed token rejected.

- [X] T051 Implement `POST /api/v1/platform/auth/logout`
  - **Files**: `backend/modules/platform_admin/services/platform_auth_service.py`, `router.py`
  - **Deps**: T049
  - **Acceptance**: Revokes the `PlatformSession` and all its refresh tokens.
  - **Result (2026-08-20)**: DONE. **Contract audit caught a real discrepancy**: `contracts/platform-admin-v1.yaml`'s `/auth/logout` declares `204 No Content`, not `200` + body (the tenant `/auth/logout` convention) — fixed to `status_code=204`, `response_model=None`, matching the existing `204` pattern used elsewhere in this codebase (e.g. `crm/router.py`'s `DELETE /leads/{id}`); the now-unused `PlatformLogoutResponse` schema was deleted rather than left dead.

- [X] T052 [FR-9A-220] Implement `get_current_platform_admin()` dependency **with revocation check**
  - **Purpose**: Unlike the tenant path, platform sessions check `is_revoked` from day one (plan §10.4).
  - **Files**: `backend/modules/platform_admin/dependencies.py`
  - **Deps**: T048, T047
  - **Acceptance**: Rejects any token whose `typ` is not `platform_access`; rejects revoked `PlatformSession`; rejects inactive `PlatformAdministrator`. **Makes no change to `get_current_user()`.**
  - **Result (2026-08-20)**: DONE. `get_current_user()` verified byte-for-byte untouched (`git diff` confirms zero changes to `core/auth/dependencies.py`). All 3 rejection conditions independently tested.

- [X] T053 Mount the platform router at `/api/v1/platform`
  - **Files**: `backend/api/v1/router.py`
  - **Deps**: T052
  - **Acceptance**: Mounted **without** `get_current_company_member` (platform is never company-scoped); no path collision with existing mounts.
  - **Result (2026-08-20)**: DONE. Verified via the live OpenAPI schema: exactly 3 paths (`/api/v1/platform/auth/{login,refresh,logout}`), 573 total paths app-wide, zero duplicates.

- [X] T054 [BR-9A-011] Complete session-revoking administrator deactivation
  - **Purpose**: The second half of the Revision 2 split — deactivation must revoke all that admin's active platform sessions atomically. **This is where BR-9A-011 becomes fully satisfied.**
  - **Files**: `backend/modules/platform_admin/services/platform_administrator_service.py`
  - **Deps**: T047, T040
  - **Acceptance**: Deactivation revokes every `PlatformSession` for that administrator **in the same transaction** as the `is_active` change and its audit row (single commit via T037's helper). Session invalidation is not weakened or deferred — a deactivated admin's in-flight token stops working immediately (proved by T059).
  - **Result (2026-08-20)**: DONE. No code change to this file was needed — Phase 3's `deactivate()` already called an injected `session_revoker` before the single commit; Phase 4 supplies the real `PlatformSessionRepository` that satisfies that seam. Proved twice: T059 (real revocation happens) and an added forced-audit-failure test (revocation does not survive a failed audit write either — full 3-way atomicity, going beyond T054's literal text per the fail-closed testing standard).

- [X] T055 [P] [BR-9A-002] Test: tenant access token → every Platform API → denied
  - **Files**: `backend/tests/security/modules/platform_admin/test_token_boundary.py`
  - **Deps**: T053
  - **Acceptance**: Every `/api/v1/platform/*` route existing at this point rejects a valid tenant token, regardless of the tenant user's role (including `owner`).
  - **Result (2026-08-20)**: PASS. "Every Platform API existing at this point" scoped correctly to `/auth/logout` — the sole authenticated route; `/auth/login`/`/auth/refresh` are contractually public (`security: []`), so token rejection isn't a meaningful concept for them.

- [X] T056 [P] Test: platform access token is never accepted as a tenant session
  - **Files**: `backend/tests/security/modules/platform_admin/test_token_boundary.py`
  - **Deps**: T053
  - **Acceptance**: A `platform_access` token against `/api/v1/companies/{id}/...` is rejected by `get_current_user()` (wrong `typ`), and does not implicitly unlock any tenant endpoint (spec §11 scenario 4).
  - **Result (2026-08-20)**: PASS, with a documented mechanism correction. `get_current_user()` has **zero** `typ` checking logic (verified: only `"typ": "access"` exists anywhere in tenant auth code) and is explicitly frozen (T052's own acceptance: "makes no change to `get_current_user()`"). Rejection is therefore structural, not a `typ` check: a Platform token's `sub` is a `PlatformAdministrator.id`, which does not correspond to any `users.id` row, so `UserRepository.get_by_id_or_none()` returns `None` and `get_current_user()` raises on its own, unmodified. Tested against both `/api/v1/auth/me` and `/api/v1/auth/logout`.

- [X] T057 [P] Test: revoked platform session is rejected
  - **Files**: `backend/tests/security/modules/platform_admin/test_platform_session.py`
  - **Deps**: T052
  - **Acceptance**: Explicit logout → the still-unexpired access token is rejected on the next request.
  - **Result (2026-08-20)**: PASS. Real end-to-end HTTP: login → logout (204) → same token reused → 401.

- [X] T058 [P] Test: unauthenticated request to every Platform API → denied
  - **Files**: `backend/tests/security/modules/platform_admin/test_token_boundary.py`
  - **Deps**: T053
  - **Acceptance**: No `/api/v1/platform/*` route is reachable without a valid platform token.
  - **Result (2026-08-20)**: PASS. No header and malformed-header cases both rejected against `/auth/logout`.

- [X] T059 [BR-9A-011] Test: deactivated Platform Administrator cannot access Platform APIs, immediately
  - **Purpose**: The API-level proof of T054; moved here from Phase 3 in Revision 2 because it requires Platform APIs to exist.
  - **Files**: `backend/tests/security/modules/platform_admin/test_identity_boundary.py`
  - **Deps**: T054, T053
  - **Acceptance**: Admin logs in → is deactivated → the **same, still-unexpired** access token is rejected on the very next request; the session rows are already revoked in the database.
  - **Result (2026-08-20)**: PASS. Real HTTP login → deactivation via the real service with a real `PlatformSessionRepository` revoker → DB-level confirmation (`is_revoked=True` on every session row) → the still-unexpired token rejected on the very next request (401).

---

## Phase 5: Platform RBAC & Owner Bootstrap — **Gate B**

**Objective**: Genuinely enforced permission-code RBAC (ADR-2) + the out-of-band bootstrap command (ADR-8), then prove the trust boundary on the routes that exist by the end of this phase.
**Prerequisites**: Phase 4.
**Exit condition (Gate B)**: T077 — independently passable using only Phase 1–5 work. The **exhaustive** all-routes permission matrix is deliberately deferred to T206 (Phase 16), after every Platform router exists.

### Tasks

- [X] T060 [US-7] Create `PlatformPermission`, `PlatformRole`, `PlatformRolePermission`, `PlatformAdminRoleAssignment` models
  - **Files**: `backend/modules/platform_admin/models/platform_rbac.py`
  - **Deps**: T032
  - **Acceptance**: Per data-model.md; permission uses code-as-PK (mirroring the tenant `Permission` convention); unique pairs on both join tables.
  - **Result (2026-08-20)**: DONE. All 4 models added, column-by-column verified against migration 057's already-committed `op.create_table(...)` definitions via docker exec introspection — zero drift. `PlatformPermission` uses `code` as PK (no separate `id`); the other 3 inherit `BaseModel`. All FK columns explicitly `Uuid(as_uuid=True)`-typed.

- [X] T061 [US-7] Create the RBAC repositories
  - **Files**: `backend/modules/platform_admin/repositories/platform_rbac_repository.py`
  - **Deps**: T060
  - **Acceptance**: Role CRUD, permission listing, assignment add/remove, and an effective-permission query (union across the admin's roles).
  - **Result (2026-08-20)**: DONE. `PlatformRbacRepository` with permission/role/bundle/assignment CRUD, `has_role`, `count_active_administrators_with_role`, `get_effective_permissions`. All writes flush-only (ADR-5).

- [X] T062 [US-7] Implement permission seeding for codes and candidate role bundles
  - **Purpose**: Roles/permissions are configuration data, addable without code change (FR-9A-140).
  - **Files**: `backend/modules/platform_admin/services/platform_rbac_seed_service.py`
  - **Deps**: T061, T033
  - **Acceptance**: Idempotent; seeds every code in `PLATFORM_PERMISSION_CODES` and the 6 candidate bundles; re-running changes nothing. **Not a migration.**
  - **Result (2026-08-20)**: DONE. `PlatformRbacSeedService.seed_permissions()`/`seed_role_bundles()`/`seed_all()`; check-then-create for permissions, and a `current != target` compare-before-write guard for role bundles so a rerun with no catalogue change performs zero join-table writes — verified via docker exec (29 codes, 6 bundles, reruns are genuine no-ops).

- [X] T063 [FR-9A-142] Implement the effective-permission resolver
  - **Files**: `backend/modules/platform_admin/services/platform_rbac_service.py`
  - **Deps**: T061
  - **Acceptance**: Union of all assigned roles' permissions, resolved **per request** (never cached in the token, FR-9A-221).
  - **Result (2026-08-20)**: DONE. `PlatformRbacService.get_effective_permissions()`/`has_permission()` delegate straight to the repository query — no caching layer anywhere.

- [X] T064 [BR-9A-008] Implement `require_platform_permission(code)` dependency
  - **Purpose**: The single server-side enforcement primitive every sensitive Platform route uses.
  - **Files**: `backend/modules/platform_admin/dependencies.py`
  - **Deps**: T063, T052
  - **Acceptance**: Holding one permission never implies another; raises `InsufficientPlatformPermissionError`; the denial is logged as a security-relevant event (plan §30).
  - **Result (2026-08-20)**: DONE. Dependency factory verified by T076's 33-case parametrized matrix (adjacent-permission denial across all 6 guarded operations) and T074's adjacent-permission test.

- [X] T065 [US-7] [BR-9A-012] Implement role assignment/removal with self-escalation prevention
  - **Purpose**: Also serves as the canonical **audited privileged mutation** available for the Gate E foundation proof (T079).
  - **Files**: `backend/modules/platform_admin/services/platform_rbac_service.py`
  - **Deps**: T063, T037
  - **Acceptance**: Requires `platform.rbac.manage`; assigning `platform_owner` additionally requires the actor to already hold it; every change is audited via T037's helper in a single transaction.
  - **Result (2026-08-20)**: DONE. `assign_role()`/`remove_role_assignment()` implemented; self-escalation denial is now ALSO audited (`platform_rbac.role.assign.denied`) before raising — added during T075 to satisfy "both attempts are audited," which the original success-only audit call did not cover.

- [X] T066 Implement last-Platform-Owner protection
  - **Purpose**: Prevent locking the platform out of itself (plan §8, §26).
  - **Files**: `backend/modules/platform_admin/services/platform_rbac_service.py`
  - **Deps**: T065, T054
  - **Acceptance**: Removing the final active `platform_owner` assignment — or deactivating the last owner account — raises `LastPlatformOwnerError`. Service-level check (not expressible as a single-row CHECK).
  - **Result (2026-08-20)**: DONE. `assert_not_last_owner_removal()` now also audits the denial (`platform_rbac.last_owner_removal.denied`, actor/reason threaded through from both call-sites — `remove_role_assignment()` and the PATCH-deactivate router handler) before raising, for the same T075 reason as T065.

- [X] T067 [FR-9A-036] [ADR-8] Implement the out-of-band bootstrap command
  - **Purpose**: Break the bootstrap circularity without coupling credentials to Alembic versioning.
  - **Files**: `backend/modules/platform_admin/bootstrap.py` (with `if __name__ == "__main__":`)
  - **Deps**: T062, T040, T065
  - **Acceptance**: Reads `PLATFORM_OWNER_BOOTSTRAP_EMAIL` + `PLATFORM_OWNER_BOOTSTRAP_PASSWORD_HASH` (**pre-hashed**, never plaintext in source). Exit `0` on create **or** on "already provisioned"; **non-zero** on missing or invalid config. Never overwrites an existing owner. No HTTP route. **No Alembic migration.** No Click/Typer framework introduced.
  - **Result (2026-08-20)**: DONE. `bootstrap_platform_owner(db)` + `main()`; Argon2 hash-format validation via `PasswordHasher().verify(hash, "dummy")` distinguishing `InvalidHash` from `VerifyMismatchError`; deferred imports so the module stays importable standalone. 7/7 tests (T070-T073) passing.

- [X] T068 [US-7] [FR-9A-030..034] Implement the **Platform Administrator management routes**
  - **Purpose**: The HTTP surface the contract declares and the Phase-15 Administrators page consumes. Revision 3 fix — these routes were implied by services and frontend tasks but never had explicit implementation tasks.
  - **Files**: `backend/modules/platform_admin/router.py`, `backend/modules/platform_admin/schemas/platform_administrator.py`
  - **Deps**: T064, T054, T041, T053, T066
  - **Acceptance**: Implements exactly the three contract operations, no more:
    - `GET /api/v1/platform/administrators` → `require_platform_permission("platform.admins.read")`; paginated + filterable list; response = administrator summary schema (T041); no audit (read).
    - `POST /api/v1/platform/administrators` → `platform.admins.manage`; request = create schema with an explicit field allow-list (no `is_active`/role mass-assignment); delegates to `PlatformAdministratorService` (T040); **fail-closed audited** per ADR-5 (state + audit in one commit); 409 if a `PlatformAdministrator` already exists for that `user_id`.
    - `PATCH /api/v1/platform/administrators/{adminId}` → `platform.admins.manage`; activate/deactivate only; **deactivation MUST call the completed session-revoking path (T054)**, never the Phase-3 domain-only behaviour, so all active `PlatformSession` rows are revoked in the same transaction; returns `LastPlatformOwnerError` (409) when deactivating the final owner (T066).
  - **Router discipline**: routers delegate to the service layer — **no business logic in the router**. Errors use the project-wide `StandardResponse` envelope. Contract traceability: operations 20–22 of `platform-admin-v1.yaml`.
  - **Result (2026-08-20)**: DONE. `admin_router` mounted at `/platform` alongside the existing `/platform/auth` router. `PlatformAdministratorService.create()` extended (self-review finding) with an explicit `User`-existence check (404) before the duplicate-administrator check (409), since the FK/unique-constraint would otherwise surface as a raw `IntegrityError`. PATCH deactivate wires the real `PlatformSessionRepository` as `SessionRevoker` and calls `PlatformRbacService.assert_not_last_owner_removal()` before deactivating. 5 route-level tests (duplicate 409, deactivate-revokes-sessions, last-owner 409, unknown-user 404) + 33 T076 matrix cases, all passing.

- [X] T069 [US-7] [BR-9A-012] Implement the **Platform RBAC management routes**
  - **Purpose**: The role/assignment HTTP surface the contract declares and the Phase-15 Roles page consumes.
  - **Files**: `backend/modules/platform_admin/router.py`, `backend/modules/platform_admin/schemas/platform_rbac.py`
  - **Deps**: T064, T065, T066, T053
  - **Acceptance**: Implements exactly the three contract operations, no more:
    - `GET /api/v1/platform/roles` → `require_platform_permission("platform.rbac.read")`; lists roles with their permission bundles; paginated; no audit (read).
    - `POST /api/v1/platform/roles` → `platform.rbac.manage`; create/update a role's permission bundle; explicit field allow-list; **fail-closed audited**; rejects unknown permission codes against `PLATFORM_PERMISSION_CODES` (T033).
    - `POST /api/v1/platform/administrators/{adminId}/roles` → `platform.rbac.manage`; assigns a role; delegates to `PlatformRbacService` (T065) so **self-escalation prevention** and **last-Platform-Owner protection** (T066) both apply; returns 403 on self-escalation and 409 on last-owner violation; **fail-closed audited**.
  - **Not implemented** (deliberately — the contract does not declare them, and inventing CRUD is forbidden): no `GET /permissions` catalogue route, no `DELETE` role-assignment route. If either is genuinely needed later it requires a contract change first.
  - **Router discipline**: delegates to the service layer; no business logic in the router. Contract traceability: operations 23–25 of `platform-admin-v1.yaml`.
  - **Result (2026-08-20)**: DONE. `rbac_router` mounted at `/platform`. Added `PlatformRbacService.create_or_update_role()` (not itself a T060-T066 task — needed by this route) validating `permission_codes` against `PLATFORM_PERMISSION_CODES` (`UnknownPlatformPermissionError`, 422) and a `PlatformRbacRepository.update_role()` method for the update path. `assign_role` route validates both `adminId` and `role_id` exist (404) before delegating — a self-review finding, since the FK constraints would otherwise surface as raw `IntegrityError`. No `GET /permissions`/`DELETE` route added. 8 route-level tests + 33 T076 matrix cases, all passing.

- [X] T070 [P] Test: first successful bootstrap creates User + PlatformAdministrator + owner role assignment
  - **Files**: `backend/tests/integration/services/platform_admin/test_bootstrap.py`
  - **Deps**: T067
  - **Acceptance**: All three rows created in one transaction; exit `0`; administrator id printed.
  - **Result (2026-08-20)**: DONE — PASSING. Isolates itself as the zero-owner baseline first (`_isolate_as_zero_owners`), since other Phase-5 test files sharing the leaky `db_session` fixture (Phase 3/4/5 documented property) may otherwise leave a `platform_owner` assignment from an earlier-collected file.

- [X] T071 [P] Test: bootstrap with **missing** configuration exits non-zero and writes nothing
  - **Purpose**: The Correction-4 guarantee — a missing config must never look like success.
  - **Files**: `backend/tests/integration/services/platform_admin/test_bootstrap.py`
  - **Deps**: T067
  - **Acceptance**: Non-zero exit; message names the missing variables; zero rows written; re-running after fixing config succeeds.
  - **Result (2026-08-20)**: DONE — PASSING. Uses before/after count deltas rather than absolute-zero assertions (leakage-robust).

- [X] T072 [P] Test: repeated bootstrap with an owner present is a safe no-op
  - **Files**: `backend/tests/integration/services/platform_admin/test_bootstrap.py`
  - **Deps**: T067
  - **Acceptance**: Exit `0`, "already provisioned" message, **no** second owner, existing owner's credentials unchanged.
  - **Result (2026-08-20)**: DONE — PASSING.

- [X] T073 [P] Test: bootstrap with invalid configuration exits non-zero
  - **Files**: `backend/tests/integration/services/platform_admin/test_bootstrap.py`
  - **Deps**: T067
  - **Acceptance**: Malformed email or unusable password hash → specific validation error, non-zero exit, nothing written.
  - **Result (2026-08-20)**: DONE — PASSING. 7/7 tests in this file pass together in the full suite.

- [X] T074 [P] [BR-9A-001] Test: tenant signup cannot create Platform authority
  - **Files**: `backend/tests/security/modules/platform_admin/test_bootstrap_abuse.py`
  - **Deps**: T067
  - **Acceptance**: No code path in `backend/modules/auth/` touches `platform_administrators`; no HTTP route can create one without `platform.admins.manage`.
  - **Result (2026-08-20)**: DONE — PASSING (6/6). Structural proof: greps every `.py` file under `backend/modules/` for `PlatformAdministrator(`/`PlatformAdministratorRepository(` outside `platform_admin` itself (zero hits), and `backend/modules/auth/` specifically for any mention of `platform_administrator` (zero hits). Behavioural proof: `POST /administrators` rejected unauthenticated (401), tenant-token (401), no-role (403), and adjacent-permission (`platform.admins.read` via `security_audit_admin`, 403) — zero rows written in every case. Along the way, fixed a real pre-existing bug this test surfaced: `PlatformRbacSeedService`'s `logger.info(..., extra={"created": ...})` collided with `logging.LogRecord`'s reserved `created` attribute, crashing whenever seeding logged at INFO level (renamed to `created_count`).

- [X] T075 [P] Test: self-escalation and last-owner removal are both rejected
  - **Files**: `backend/tests/security/modules/platform_admin/test_rbac_escalation.py`
  - **Deps**: T066
  - **Acceptance**: Both raise; no state change; both attempts are audited.
  - **Result (2026-08-20)**: DONE — PASSING (4/4), service-layer only (no dependency on T068/T069 routes, per this task's Phase-1-5-service-only scope). This test discovered that neither denial path was actually audited before this phase's own T065/T066 implementation — see those tasks' Result notes for the fix. Both "negative-of-the-negative" cases (an actual owner CAN grant the role; owner-role removal succeeds when a second owner exists) are also covered, proving the guards are precise, not blanket bans.

- [X] T076 **[Gate B]** Permission-enforcement test over the routes that exist at end of Phase 5
  - **Purpose**: Proves RBAC enforcement genuinely works, scoped to the currently-existing surface. Revision 2 split — the exhaustive all-routes matrix is T206, after every router exists.
  - **Files**: `backend/tests/security/modules/platform_admin/test_permission_enforcement_phase5.py`
  - **Deps**: T064, T053, T068, T069
  - **Acceptance**: Covers the **9 operations that genuinely exist at end of Phase 5**, split into two semantically distinct categories — the 3 `/auth/*` operations are **public authentication endpoints and carry no Platform RBAC permission**, so the permission-positive/adjacent-negative test does not apply to them:
    - **3 public authentication operations** (`POST /auth/login`, `/auth/refresh`, `/auth/logout` — no `x-permission` in the contract): verify correct public/auth semantics — login issues a `platform_access`/`platform_refresh` pair only for an **active** `PlatformAdministrator`, and returns a generic invalid-credentials response otherwise; refresh rotates and rejects a revoked session or deactivated administrator; logout revokes the session. Verify the tenant/Platform authentication isolation boundary: a **tenant** token is never accepted as a platform session, and a `platform_access` token is never accepted by `get_current_user()`. **No Platform RBAC permission is required or asserted for these three.**
    - **6 permission-guarded Administrator/RBAC operations** (3 from T068, 3 from T069): holding the required Platform permission succeeds; holding **only** an adjacent/unrelated permission fails; unauthenticated requests are rejected; tenant-token attempts are rejected.
  - The in-scope operation list — and its split into 3 public + 6 guarded — is asserted explicitly in the test, so T206 can later prove completeness against the full 33-operation contract (30 guarded + 3 public). **No route outside this Phase-5 surface is referenced.**
  - **Result (2026-08-20)**: DONE — PASSING (33/33). `IN_SCOPE_OPERATIONS` structure literally asserts the 3+6=9 split and the 4 distinct permission codes involved. Each of the 6 guarded operations parametrized across 4 test functions (unauthenticated, tenant-token, adjacent-permission via a bespoke single-permission role, required-permission success) = 24 cases; the 9 public-auth/boundary tests bring the total to 33.

- [X] T077 **[Gate B]** Gate B sign-off
  - **Deps**: T055–T059, T074, T075, T076
  - **Acceptance**: Tenant tokens cannot reach Platform APIs; Platform tokens cannot act as tenant sessions; Platform auth/session is independent; RBAC enforcement works; bootstrap authority is protected; self-escalation and last-owner removal are rejected. **All dependencies are Phase 1–5 only — no forward reference.** Do not start Phase 6 until this passes.
  - **Result (2026-08-20)**: **GATE B PASSED**. All named dependencies (T055-T059 from Phase 4, T074-T076 from this phase) pass. Combined Phase 1-5 `platform_admin`/`bootstrap` test suite: 77/77 passing in a single combined run; the 3 additional T068/T069 404-path tests added during self-review (unknown-user 404 on create, unknown-admin/unknown-role 404 on role-assign) independently verified passing (8/8 in their file) after being added — 80 Phase 5 tests total, all passing. Scoped shared-file regression (auth, companies, JWT/token security — the modules `api/v1/router.py`/`dependencies.py`/`exceptions.py` changes could plausibly affect): 382/382 passing. No forward reference to Phase 6+ in any of this phase's dependencies.

---

## Phase 6: Platform Audit Query Surface — **Gate E**

**Objective**: The audit read/query surface, and the blocking fail-closed atomicity proof using a **real audited mutation that already exists** (role assignment, T065). The tenant-suspension 3-way proof follows in Phase 7 (T101).
**Prerequisites**: Gate B.
**Exit condition (Gate E)**: T081 — depends only on Phase 1–6 work.

### Tasks

- [X] T078 [US-8] [FR-9A-200] Implement the audit query service (filter + paginate)
  - **Files**: `backend/modules/platform_admin/services/platform_audit_query_service.py`
  - **Deps**: T036
  - **Acceptance**: Filters by administrator, tenant, action, resource, date range, result/status; paginated; uses the T014 indexes (no table scan).
  - **Result (2026-08-20)**: DONE — PASSING (8/8). `PlatformAuditQueryService.query()` is a thin pass-through to a new `PlatformAuditRepository.list_filtered()` (extends T036 — a read-only addition, does not touch its append-only guarantee). `outcome` (the "result/status" dimension) is **derived**, not a stored column — `data-model.md`/`plan.md §20`'s field list for `PlatformAuditEvent` has no status column, so `outcome="denied"`/`"success"` filters on the `action` value's existing `.denied`-suffix convention already established in Phase 5 (T065/T066's denial audits). Every filter that isn't index-covered (`target_type`/`target_id`/`outcome`) is always combined with at least one of the 4 T014-indexed columns in realistic queries; the 4 indexed columns alone are never bypassed for the primary scan. Tests cover each filter dimension individually, combined filters, pagination correctness (offset/limit/total), and explicit newest-first ordering.

- [X] T079 **[Gate E]** Negative test: forced audit-write failure rolls back a privileged mutation
  - **Purpose**: The single most important correctness test in the Epic (plan §32). Revision 2 fix — uses the Phase-5 role-assignment mutation, which legally exists here, instead of forward-referencing a Phase-7 lifecycle task.
  - **Files**: `backend/tests/integration/services/platform_admin/test_audit_fail_closed.py`
  - **Deps**: T037, T065
  - **Acceptance**: Inject a constraint violation on the audit insert during a **platform role assignment** → assert the role-assignment row is **also** rolled back; nothing partial remains committed. quickstart.md §9 explicitly permits "whichever privileged mutation was under test".
  - **Result (2026-08-20)**: DONE — PASSING (2/2). Uses `PlatformRbacService.assign_role()` (T065) as the real privileged mutation. Simulates the constraint violation via `unittest.mock.patch.object(PlatformAuditService, "record", side_effect=IntegrityError(...))` — the exact exception TYPE a real PostgreSQL constraint violation surfaces as — following the same technique T044 (Phase 3) already established and this Epic already accepted as sufficient evidence for this atomicity property. A literal FK-violation-based test was evaluated and rejected: this suite's shared `db_session` fixture is SQLite in-memory with no `PRAGMA foreign_keys` anywhere in `tests/conftest.py`, so a bad foreign key would silently insert rather than raise — not a real test. Positive control (`test_normal_audit_success_still_commits_the_role_assignment`) proves the harness genuinely allows success in the non-forced case.

- [X] T080 [P] [BR-9A-023] Test: platform audit records are append-only through every API surface
  - **Files**: `backend/tests/security/modules/platform_admin/test_audit_immutability.py`
  - **Deps**: T078
  - **Acceptance**: No route updates or deletes an audit row; the repository exposes no such method.
  - **Result (2026-08-20)**: DONE — PASSING (4/4). Structural proof: `PlatformAuditRepository`'s only two public methods are `record` and `list_filtered` (T078) — no update/delete/edit/remove method exists at all. Whole-app proof: the live `/openapi.json` schema (reflecting every FastAPI-registered route regardless of internal router composition) has zero PUT/PATCH/DELETE operations on any `/platform/*` path mentioning "audit", and confirms no `/platform/audit` GET route exists yet either (correctly deferred to T170, Phase 13) — the test is forward-compatible and keeps passing once that GET-only route is added.

- [X] T081 **[Gate E]** Gate E sign-off
  - **Deps**: T079, T080
  - **Acceptance**: Audit atomicity proven against a real privileged mutation using only Phase 1–6 work. The **fuller** state+audit+outbox 3-way proof on tenant suspension is mandatory and blocking in Phase 7 (T101) — Gate E does not substitute for it.
  - **Result (2026-08-20)**: **GATE E PASSED**. T079 (fail-closed atomicity against the real T065 role-assignment mutation) and T080 (append-only through every API surface) both pass. All dependencies are Phase 1-6 work only — T065/T066 (Phase 5), T036/T037 (Phase 3), T078 (this phase). No forward reference to Phase 7's tenant-suspension mutation (T101 remains the mandatory fuller 3-way proof there, not substituted here). Combined Phase 1-6 `platform_admin`/`bootstrap` test suite: 94/94 passing in a single run (80 from Phase 5 + 14 new Phase 6 tests).

---

## Phase 7: Tenant Lifecycle & Company-Scoped Access Invalidation — **Gate C**

**Objective**: Suspend/reactivate with persisted `pre_suspension_status` (ADR-12), company-scoped access invalidation keyed on `Session.created_at` (ADR-6), and the full 3-way audit atomicity proof. **This is the most security-sensitive phase.**
**Prerequisites**: Gate B, Gate E.
**Exit condition (Gate C)**: T102.

### Tasks

- [X] T082 [FR-9A-017] [ADR-6] Implement `assert_company_access_allowed(db, company_id, session_id)`
  - **Purpose**: Layer 1 (company status) + Layer 2 (authentication-freshness watermark) in one shared helper.
  - **Files**: `backend/modules/platform_admin/services/company_access_service.py`
  - **Deps**: T031
  - **Acceptance**: Denies when `Company.status` is `suspended` (raising the existing `CompanySuspendedError`) or `deleted`; **and** denies when `Session.created_at <= Company.access_invalidated_at`. Loads `Session` by the `sid` already surfaced as `CurrentUser.session_id`. **Must not use the token's `iat`.**
  - **Result (2026-08-20)**: DONE. Status-code mapping matches `get_current_company`'s pre-existing behaviour exactly (suspended→403 `CompanySuspendedError`, deleted→404 `CompanyNotFoundError`), so wiring it in is byte-identical for non-suspended companies. `pre_suspension_status`/`access_invalidated_at` columns added to the `Company` ORM model (migration 057 already had them in the DB; the ORM mapping was deliberately deferred to this phase) with their 2 CHECK constraints mirrored into `__table_args__`. 9/9 unit tests (T085) passing.

- [X] T083 Wire `assert_company_access_allowed` into `get_current_company_member`
  - **Purpose**: Closes the §3.3 gap — this is what makes suspension effective on all five business modules.
  - **Files**: `backend/modules/users_roles/dependencies.py`
  - **Deps**: T082
  - **Acceptance**: All five module mounts inherit the check with no per-module change. **`get_current_user()` is not modified** (no new claim, no new query, no new failure mode there).
  - **Result (2026-08-20)**: DONE. Single call inserted at the top of `get_current_company_member`, before the membership lookup. `get_current_user()` untouched — verified via `git diff modules/auth/`. Proven live via T086/T095-T100/T098's real HTTP round trips through all five module mounts.

- [X] T084 Wire `assert_company_access_allowed` into `get_current_company`
  - **Purpose**: The companies module already checks status; it additionally gains the watermark check.
  - **Files**: `backend/modules/companies/dependencies.py`
  - **Deps**: T082
  - **Acceptance**: Behaviour for non-suspended companies is byte-identical to today (regression-checked in T087).
  - **Result (2026-08-20)**: DONE. The manual `suspended`/`deleted` status checks were replaced with a single `assert_company_access_allowed(...)` call — same two exceptions, same status codes, plus the new watermark layer. Byte-identical behaviour for non-suspended companies confirmed by T087's full regression (972 passed, 4 pre-existing skips, 0 failed).

- [X] T085 [P] Unit tests for the freshness comparison
  - **Files**: `backend/tests/unit/modules/platform_admin/test_company_access_rule.py`
  - **Deps**: T082
  - **Acceptance**: Covers `created_at <`, `=`, `>` watermark; NULL watermark denies nothing; `suspended`/`deleted`/`active` status paths.
  - **Result (2026-08-20)**: DONE — PASSING (9/9). Covers all 3 watermark comparisons (including the exact-tie `<=` case), NULL-watermark rollout safety, active/inactive/suspended/deleted status paths, and nonexistent-company no-op.

- [X] T086 [P] Test: a NULL `access_invalidated_at` (every pre-existing company) denies nothing
  - **Purpose**: Proves rollout safety — no existing tenant loses access when Phase 7 ships.
  - **Files**: `backend/tests/integration/api/v1/platform_admin/test_company_access.py`
  - **Deps**: T083, T084
  - **Acceptance**: All five modules behave exactly as before for every existing tenant.
  - **Result (2026-08-20)**: DONE — PASSING (1/1). Real HTTP login + real company/membership with the default NULL watermark; hits a representative endpoint in all 5 business modules (inventory, purchase, sales, accounting `/health`; crm `/status`) — all 200.

- [X] T087 Regression: all five business modules still function for non-suspended tenants
  - **Purpose**: T083 touches a dependency every company-scoped route uses.
  - **Files**: existing `backend/tests/integration/api/v1/{inventory,purchase,sales,accounting,crm}/`
  - **Deps**: T083, T084
  - **Acceptance**: Full existing suite green; any delta explained before proceeding.
  - **Result (2026-08-20)**: DONE. Full existing `inventory`/`purchase`/`sales`/`accounting`/`crm` API test suites run against the T083/T084-modified dependency chain: **972 passed, 4 skipped, 0 failed** (45m57s). The 4 skips are pre-existing (not introduced by this phase). No delta from the pre-Phase-7 baseline.

- [X] T088 [US-3] [FR-9A-011] Implement `TenantLifecycleService.suspend()`
  - **Purpose**: The missing write path for `CompanyStatus.suspended` (spec §3 item 3).
  - **Files**: `backend/modules/platform_admin/services/tenant_lifecycle_service.py`
  - **Deps**: T037, T082
  - **Acceptance**: `SELECT ... FOR UPDATE` on the `Company` row → validate status is `active`/`inactive` → set `pre_suspension_status` → set `status='suspended'` → set `access_invalidated_at=now()` → enqueue `CompanySuspendedEvent` as an `OutboxRecord` → flush → audit row (before/after + mandatory reason) → **single commit**.
  - **Result (2026-08-20)**: DONE. `CompanyRepository` extended with 3 new methods (`get_for_update`, flush-only `suspend()`/`reactivate()`) — deliberately NOT reusing `CompanyRepository.update()`, which auto-commits internally and would break ADR-5 atomicity (a pre-existing property of the tenant-side `CompanyService.deactivate_company()` etc., left untouched, out of Phase 7 scope). Reused the already-defined-but-never-instantiated `CompanySuspendedEvent`/`CompanySuspensionLiftedEvent` (`companies/events.py`). Proven by T091-T094, T101.

- [X] T089 [US-3] [FR-9A-012] Implement `TenantLifecycleService.reactivate()`
  - **Purpose**: Restore the **recorded** pre-suspension status — never hardcoded `active` (ADR-12).
  - **Files**: `backend/modules/platform_admin/services/tenant_lifecycle_service.py`
  - **Deps**: T088
  - **Acceptance**: Locks the row → requires current status `suspended` → reads `pre_suspension_status` → sets `status` to it → sets `pre_suspension_status=NULL` → **retains** `access_invalidated_at` → enqueues `CompanySuspensionLiftedEvent` → audits before/after → single commit. Fails closed with an explicit error if the restore target is somehow NULL.
  - **Result (2026-08-20)**: DONE. Reuses `TenantLifecycleTransitionError` (already defined in Phase 3, never previously raised anywhere — confirmed via full-tree grep before use). Defensive fallback for a NULL `pre_suspension_status` implemented even though the DB CHECK constraint makes it unreachable in practice. Proven by T091/T092 (active/inactive round-trips) and T093 (repeated-reactivation rejection).

- [X] T090 Implement the suspend/reactivate routes with mandatory reason + permission
  - **Files**: `backend/modules/platform_admin/router.py`
  - **Deps**: T088, T089, T064
  - **Acceptance**: `POST /platform/tenants/{companyId}/suspend` requires `platform.tenants.suspend`; `/reactivate` requires `platform.tenants.reactivate` (separate permissions per spec US-3); both validate a non-empty `reason` server-side before any state change.
  - **Result (2026-08-20)**: DONE. New `tenant_router` mounted at `/platform` in `api/v1/router.py`. `TenantLifecycleActionRequest.reason` has both a Pydantic `min_length=1` AND a `field_validator` rejecting whitespace-only strings — validated before the router calls into the service, so no state change is possible with a blank reason. Contract traceability: `/tenants/{companyId}/suspend` and `/reactivate` operations of `platform-admin-v1.yaml`.

- [X] T091 [P] Test: `active → suspended → active`
  - **Files**: `backend/tests/integration/services/platform_admin/test_tenant_lifecycle.py`
  - **Deps**: T090
  - **Acceptance**: Final status is `active`; `pre_suspension_status` is NULL afterwards; both transitions audited with correct before/after.
  - **Result (2026-08-20)**: DONE — PASSING. Also verifies `access_invalidated_at` is set on suspend and deliberately still non-NULL after reactivation (ADR-6), and both `company.suspended`/`company.suspension_lifted` OutboxRecords exist.

- [X] T092 [P] Test: `inactive → suspended → inactive`
  - **Purpose**: The case a hardcoded `active` would silently corrupt.
  - **Files**: `backend/tests/integration/services/platform_admin/test_tenant_lifecycle.py`
  - **Deps**: T090
  - **Acceptance**: Final status is `inactive`, **not** `active`.
  - **Result (2026-08-20)**: DONE — PASSING. Explicit assertion that the restored status is NOT `active`, proving the restore genuinely reads `pre_suspension_status` rather than hardcoding.

- [X] T093 [P] Test: repeated suspension and repeated reactivation are both rejected
  - **Files**: `backend/tests/integration/services/platform_admin/test_tenant_lifecycle.py`
  - **Deps**: T090
  - **Acceptance**: Specific "already suspended" / "not currently suspended" errors (spec Edge Cases #1/#2); no duplicate audit row.
  - **Result (2026-08-20)**: DONE — PASSING (4/4 total in this file, combined with T091/T092). Both rejection paths verified to write zero additional audit rows.

- [X] T094 [P] Test: concurrent suspend attempts — exactly one commits
  - **Files**: `backend/tests/integration/services/platform_admin/test_tenant_lifecycle_concurrency.py`
  - **Deps**: T090
  - **Acceptance**: Two concurrent transactions against one company → one succeeds, the other gets the state-conflict error; exactly one audit row (spec §11 scenario 6). Real PostgreSQL (row locking is not meaningfully testable on SQLite).
  - **Result (2026-08-20)**: DONE — PASSING. Connects directly to the real PostgreSQL dev database (`core.database.session.SessionLocal`, bypassing the SQLite `db_session` fixture entirely) via two threads, each with its own session; `CompanyRepository.get_for_update` briefly holds its lock open (0.4s) after acquiring it so the other thread's concurrent `SELECT ... FOR UPDATE` genuinely blocks on real row-level locking. Exactly one `success`/one `conflict` outcome, exactly one audit row, verified with a fresh third session. All test data (company, user, platform administrator) created and torn down against the real database — verified zero leftover rows via direct `psql` query after the test.

- [X] T095 **[Gate C]** Test A: old **access token** denied after suspend→reactivate
  - **Files**: `backend/tests/security/modules/platform_admin/test_auth_freshness.py`
  - **Deps**: T090
  - **Acceptance**: Login → suspend → reactivate → replay the original access token → **denied** for that company.
  - **Result (2026-08-20)**: DONE — PASSING.

- [X] T096 **[Gate C]** Test B: old **refresh token** cannot restore access — the refresh-bypass regression guard
  - **Purpose**: This test must fail if anyone re-keys the check to the token's `iat` (ADR-6).
  - **Files**: `backend/tests/security/modules/platform_admin/test_auth_freshness.py`
  - **Deps**: T090
  - **Acceptance**: Login → suspend → reactivate → redeem the **pre-suspension refresh token** → a brand-new access token is minted → using it is **still denied**, because it is bound to the same pre-suspension `Session`.
  - **Result (2026-08-20)**: DONE — PASSING. The refreshed token's fresh `iat` does not help — the check compares `Session.created_at`, unchanged by refresh.

- [X] T097 **[Gate C]** Test C: genuine new login restores access
  - **Files**: `backend/tests/security/modules/platform_admin/test_auth_freshness.py`
  - **Deps**: T090
  - **Acceptance**: After reactivation, a real login creates a new `Session` with `created_at > access_invalidated_at` → access allowed if membership is otherwise valid.
  - **Result (2026-08-20)**: DONE — PASSING. Required a 1.1s test-only delay before the second login: SQLite's `CURRENT_TIMESTAMP` (used for `Session.created_at`'s `server_default=func.now()` under the test fixture) has whole-second resolution, unlike `access_invalidated_at`'s Python-side microsecond `datetime.now(UTC)` — without the delay, a same-second tie lands on the `<=` rule's deny side. A real human always takes more than a second to log back in; this is a test-environment precision artifact, not a production behavior gap (documented in the test file).

- [X] T098 **[Gate C]** Test D: multi-tenant user — suspending A does not affect B
  - **Purpose**: The tenant-isolation guarantee that rejected blanket session revocation (ADR-6).
  - **Files**: `backend/tests/security/modules/platform_admin/test_cross_tenant_suspension.py`
  - **Deps**: T090
  - **Acceptance**: User X is an active member of A and B → suspend A → A denied, **B still succeeds on the same token/session**.
  - **Result (2026-08-20)**: DONE — PASSING. Also confirms enforcement is not module-specific by checking both inventory and sales for company A.

- [X] T099 **[Gate C]** Test E: multi-device semantics
  - **Files**: `backend/tests/security/modules/platform_admin/test_auth_freshness.py`
  - **Deps**: T090
  - **Acceptance**: Two devices logged in pre-suspension → both denied for A after reactivation → Device 1 re-logs in and regains A → **Device 2 remains denied** until it re-authenticates → both keep B throughout (plan §10.3.1).
  - **Result (2026-08-20)**: DONE — PASSING. Full matrix proven: both devices denied for A post-reactivation, both keep B throughout, only Device 1's fresh re-login restores A for Device 1, Device 2's original token remains denied for A while still valid for B.

- [X] T100 **[Gate C]** Test F: manipulation cannot fabricate freshness
  - **Files**: `backend/tests/security/modules/platform_admin/test_auth_freshness.py`
  - **Deps**: T090
  - **Acceptance**: Tampering with `iat`, `sid`, `erp_active_company_id`, or the request company id never bypasses the check (signature protects `sid`; `Session.created_at` is server-generated and unwritable via any API).
  - **Result (2026-08-20)**: DONE — PASSING (2 tests). Decoy `X-Erp-Active-Company-Id`/`X-Company-Id` headers proven to have zero effect on the (still-suspended) company A's denial — authorization derives solely from the verified JWT's `sid` and the URL path's `company_id`. Structural proof: no request schema in `modules/auth/` declares a `created_at` field, confirming `Session.created_at` is unwritable via any API. `iat`-tampering specifically is already covered by T096 (a refresh legitimately mints a fresh `iat`, and it still doesn't help).

- [X] T101 **[Gate C]** [ADR-5] Full 3-way atomicity: forced audit failure during tenant suspension
  - **Purpose**: The canonical fail-closed proof the plan intends — state change **+** audit **+** outbox in one transaction. Revision 2 moved this here (rather than forward-referencing from Phase 6), so it runs at the earliest point where suspension actually exists.
  - **Files**: `backend/tests/integration/services/platform_admin/test_audit_fail_closed.py`
  - **Deps**: T088, T037
  - **Acceptance**: Inject a constraint violation on the audit insert during a suspension → assert the `Company.status` change, the `pre_suspension_status` write, the `access_invalidated_at` watermark, **and** the `OutboxRecord` are **all** rolled back; nothing partial remains committed. Blocking — Gate C cannot pass without it.
  - **Result (2026-08-20)**: DONE — PASSING. Added `TestGateCAuditFailClosedOnTenantSuspension` to the same file T079 (Phase 6) created, extending it rather than duplicating — all 4 tests in the file (2 from Phase 6 + 2 new) pass together, confirming no regression to the existing Gate E proof. All 4 pieces (status, `pre_suspension_status`, `access_invalidated_at`, `OutboxRecord`) verified rolled back on forced failure; positive control confirms all 4 genuinely commit together on success.

- [X] T102 **[Gate C]** Gate C sign-off
  - **Deps**: T091–T101
  - **Acceptance**: Lifecycle, authentication-freshness (including the refresh bypass), cross-tenant isolation, multi-device behaviour, and full 3-way audit atomicity all proven.
  - **Result (2026-08-20)**: **GATE C PASSED**. All named dependencies (T091-T101) pass. Combined Phase 1-7 `platform_admin`/`bootstrap` test suite: 118/118 passing in a single run (94 from Phase 1-6 + 24 new). T087's full 5-business-module regression (a Phase-7 task, not a T102 dependency, but required for genuine phase completion per the master prompt's Primary Objective): 972 passed, 4 pre-existing skips, 0 failed. No forward reference to Phase 8+ in any of this phase's dependencies.

---

## Phase 8: Plans, Subscriptions, Capabilities & Quota Foundation

**Objective**: The SaaS commercial control plane (spec §16), the generic capability registry (ADR-3), and the **quota foundation** its downgrade validation and the Phase-9 baseline plan both require. No billing/payment/tax.
**Prerequisites**: Gate C.
**Revision 2 note**: quota models + the effective-quota resolver moved here from Phase 11 so that T113 (downgrade check) and T125 (baseline plan) no longer consume infrastructure that does not yet exist. Phase 11 retains override workflows, usage metering, AI readiness and the admin quota APIs. **There is exactly one quota model set and one resolver** — nothing is duplicated.

### Tasks

- [X] T103 [P] [US-4] Create `Plan` model
  - **Files**: `backend/modules/platform_admin/models/plan.py`
  - **Deps**: T032
  - **Acceptance**: Per data-model.md; `status` VARCHAR+CHECK (`draft|published|retired`); `billing_cycle_metadata`/`pricing_metadata` inert JSONB (Assumption A5); **no hardcoded plan names** (FR-9A-151).
  - **Result (2026-08-21)**: `Plan(BaseModel)` maps 1:1 onto migration 058's `plans` table (verified column-by-column against real PostgreSQL). No "Basic/Pro/Enterprise" anywhere in code — `code`/`name` are always caller-supplied.

- [X] T104 [P] Create `Capability` model + registry
  - **Files**: `backend/modules/platform_admin/models/capability.py`
  - **Deps**: T032
  - **Acceptance**: `key` PK, `module`, `grain` (`module|feature`), `display_name`, `is_active`. Adding a future module needs one row, **no** schema change and **no** per-module boolean column on `Company`.
  - **Result (2026-08-21)**: `Capability(Base)` [string PK, mirrors `PlatformPermission`'s convention]. Not wired to any route in this phase (no capability-registry CRUD task assigned to Phase 8) — read via `PlanRepository.get_capability_map()` only.

- [X] T105 Create `PlanCapability` model (the Plan Entitlement ceiling)
  - **Files**: `backend/modules/platform_admin/models/plan_capability.py`
  - **Deps**: T103, T104
  - **Acceptance**: `(plan_id, capability_key)` unique; `allowed` boolean.
  - **Result (2026-08-21)**: `PlanCapability(BaseModel)`, `plan_id` FK CASCADE, `capability_key` FK RESTRICT, unique(plan_id, capability_key) matching migration 058 exactly.

- [X] T106 [US-5] Create `Subscription` model
  - **Files**: `backend/modules/platform_admin/models/subscription.py`
  - **Deps**: T103
  - **Acceptance**: Per data-model.md; `status` VARCHAR+CHECK limited to `active|ended` (**no `trial`** — resolved OQ-1); partial unique index enforces one active subscription per company.
  - **Result (2026-08-21)**: `Subscription(BaseModel)` maps onto migration 058's `subscriptions` table. The `uq_subscriptions_company_active` partial unique index is proven DB-enforced (not application-only) by T116's real-PostgreSQL test.

- [X] T107 [US-10] Create the quota foundation models + repositories
  - **Purpose**: `QuotaDefinition`, `PlanQuota`, `TenantQuotaOverride` — required by T113's downgrade check and T125's baseline plan. Tables already exist from migration `059`.
  - **Files**: `backend/modules/platform_admin/models/quota.py`, `repositories/quota_repository.py`
  - **Deps**: T103, T018
  - **Acceptance**: Generic key-based registry (`users`, `branches`, `transactions`, `storage`, `api_calls`, `ai_credits`); **no per-quota-type column**; `enforcement_style` (`hard|soft|informational`) declared explicitly per BR-9A-030. `PlanQuota.limit_value` nullable where **NULL means unlimited** (FR-9A-182) — never a large sentinel.
  - **Result (2026-08-21)**: All three models map onto migration 059's tables (verified column-by-column against real PostgreSQL, `count=0` live queries confirmed the ORM mapping is genuinely correct, not just SQLite-compatible). `EntitlementOverride` (also in migration 059) is deliberately **not** mapped — explicit Phase 9 scope, documented in the module docstring.

- [X] T108 [US-10] [FR-9A-181] Implement the effective-quota resolver — the single authoritative resolution path
  - **Files**: `backend/modules/platform_admin/services/quota_service.py`
  - **Deps**: T107
  - **Acceptance**: Override → `PlanQuota` → unlimited; renders the five states `ok|approaching|reached|unlimited|unavailable`. This is the **only** quota resolver in the codebase; Phase 11 consumes it rather than re-implementing it.
  - **Result (2026-08-21)**: `QuotaService.resolve()` implements override-first, then `PlanQuota`, then unlimited (`limit is None`); `current_usage=None` → `unavailable`, never silently zero. 15/15 T109 unit tests pass, including the override-precedence and enforcement-style-independence groups.

- [X] T109 [P] Test: quota states, unlimited semantics and enforcement styles
  - **Files**: `backend/tests/unit/modules/platform_admin/test_quota_resolution.py`
  - **Deps**: T108
  - **Acceptance**: All five states; each enforcement style behaves as declared; entitlement and quota remain independent concepts; NULL limit resolves to unlimited, never to a number.
  - **Result (2026-08-21)**: 15 passed (`TestNoLimitResolvesToUnlimited` x3, `TestOkApproachingReachedStates` x5, `TestUnavailableState` x1, `TestOverrideTakesPrecedenceOverPlanQuota` x3, `TestEnforcementStyleAndEntitlementIndependence` x3).

- [X] T110 Create Plan/Capability/Subscription repositories
  - **Files**: `backend/modules/platform_admin/repositories/{plan,capability,subscription}_repository.py`
  - **Deps**: T103–T106
  - **Acceptance**: Paginated list/filter; audited writes flush-only (ADR-5).
  - **Result (2026-08-21)**: All three repositories `flush()`-only on every write path (no repository-level `commit()`), matching ADR-5; verified by inspection and by every T115-T117 test relying on the calling service's single commit. `PlanRepository.list_paginated()` supports an optional `status` filter.

- [X] T111 [US-4] Implement `PlanService` (create/update/publish/retire)
  - **Files**: `backend/modules/platform_admin/services/plan_service.py`
  - **Deps**: T110, T037
  - **Acceptance**: Retiring blocks **new** assignments only; existing subscriptions keep their entitlements unchanged (BR-9A-018). Every write audited.
  - **Result (2026-08-21)**: `create()` always starts `draft`; `update()` never touches `status`; `publish()`/`retire()` enforce `draft→published→retired` via `PlanTransitionError` on an invalid transition. Every method: repo flush → `PlatformAuditService.record()` → single `db.commit()`. Proven by T115 (`test_retire_does_not_touch_existing_subscription`, `test_cannot_retire_a_draft_plan`, `test_cannot_publish_an_already_published_plan`).

- [X] T112 [US-5] Implement `SubscriptionService.assign_or_change()`
  - **Files**: `backend/modules/platform_admin/services/subscription_service.py`
  - **Deps**: T110, T037
  - **Acceptance**: Keeps `companies.subscription_id` in sync in the same transaction (denormalised pointer; the partial unique index remains authoritative, ADR-9). Every change audited with before/after plan + effective date + reason.
  - **Result (2026-08-21)**: `assign_or_change()` ends the prior active Subscription (if any), creates the new one, and calls the new `CompanyRepository.set_subscription_id()` flush-only method — all inside the same service-level `db.commit()` alongside the audit row. A gap found during implementation (not in the original task list): the target Plan's `status` was never checked, so a `draft`/`retired` Plan could be silently assigned — fixed by adding a `plan.status != "published"` guard raising the new `PlanNotAssignableError` (see T115's Result note); this directly implements BR-9A-018/FR-9A-152's "no longer appears as an assignment option" requirement, which had no other enforcement point in the original task breakdown.

- [X] T113 [US-5] [FR-9A-165] [FR-9A-166] Implement downgrade usage-conflict acknowledgement
  - **Purpose**: Revision 2 fix — previously depended on a non-existent "T132 quota resolver"; now correctly depends on T108, which exists earlier in this same phase.
  - **Files**: `backend/modules/platform_admin/services/subscription_service.py`
  - **Deps**: T112, T108
  - **Acceptance**: If current usage exceeds the target plan's limits, the change is **rejected** unless the request carries an explicit acknowledgement flag; once applied, the tenant is **flagged over-quota** rather than truncated. No tenant data is ever removed or truncated.
  - **Result (2026-08-21)**: `_find_usage_conflicts()` measures only the `users` quota key live (via a `CompanyMember` COUNT — the one key with a genuine real-time source in this phase per spec.md's own US-5 worked example; all other keys have no live source until Phase 11's `UsageRecord` and correctly resolve to `unavailable`, never a false conflict). Rejection raises `SubscriptionUsageConflictError` (409) with zero partial state change (T117 proves the tenant's prior active Subscription is untouched on rejection). With `acknowledged=True` the change applies and no new column/flag was needed — `QuotaService.resolve()` naturally reports `reached` on the next check against the new plan (T117 proves this directly), and the 3 pre-existing `CompanyMember` rows are proven still present/`active` afterward (no truncation).

- [X] T114 Implement plan/subscription routes
  - **Files**: `backend/modules/platform_admin/router.py`
  - **Deps**: T111, T112, T113, T064
  - **Acceptance**: `GET/POST /platform/plans`, `PATCH /platform/plans/{planId}`, `GET/POST /platform/tenants/{companyId}/subscription` — permissions exactly as in `contracts/platform-admin-v1.yaml`.
  - **Result (2026-08-21)**: New `plan_router` (mounted in `api/v1/router.py`) plus two new operations on the existing `tenant_router`. `PATCH /plans/{planId}` is the contract's single combined "Update/publish/retire" operation, dispatched by a request-body `action` field (`update`/`publish`/`retire`) — matches the contract's exactly-one-PATCH-operation shape rather than three separate endpoints. Verified via live OpenAPI schema introspection inside the running container: exactly 5 operations at exactly the 3 contract paths, `platform.plans.read`/`platform.plans.manage`/`platform.subscriptions.read`/`platform.subscriptions.manage` permission codes already existed in the Phase-2 seeded catalogue (`constants.py`) — no new permission code was invented.

- [X] T115 [P] Test: retired plan keeps existing subscriptions intact but is unassignable
  - **Files**: `backend/tests/integration/services/platform_admin/test_plan_lifecycle.py`
  - **Deps**: T114
  - **Acceptance**: 12 subscribed tenants keep entitlements; the plan no longer appears as an assignment option (spec US-4 scenario 2).
  - **Result (2026-08-21)**: 6/6 passed. Covers: retiring a Plan leaves its existing Subscription and capability map byte-for-byte unchanged; a **new** company attempting to subscribe to the now-retired Plan is rejected with `PlanNotAssignableError` (409) and ends up with zero active Subscriptions (no partial state); a retired Plan remains readable via `get_by_id`; `draft`→retire and double-publish both correctly raise `PlanTransitionError`; a `draft` Plan cannot be assigned either (only `published` is assignable).

- [X] T116 [P] Test: one-active-subscription-per-company invariant is DB-enforced
  - **Files**: `backend/tests/integration/repositories/platform_admin/test_subscription_constraints.py`
  - **Deps**: T114
  - **Acceptance**: A second active subscription raises at the database level (partial unique index), not merely in application code. Real PostgreSQL.
  - **Result (2026-08-21)**: 1/1 passed against the real `db` Docker/PostgreSQL container (bypasses the SQLite `db_session` fixture entirely, mirroring T094's pattern) — a second `status='active'` row for the same `company_id` raises `IntegrityError` naming `uq_subscriptions_company_active` specifically (not just any constraint), while a second `status='ended'` row for the same company succeeds, proving the index is genuinely partial. All test rows verified cleaned up afterward (0 leftover rows for every created entity).

- [X] T117 [P] Test: subscription date validation and downgrade acknowledgement
  - **Files**: `backend/tests/integration/services/platform_admin/test_subscription.py`
  - **Deps**: T114
  - **Acceptance**: End date before effective date is rejected (spec Edge Case #16); an over-limit downgrade without acknowledgement is rejected, and with acknowledgement applies and flags over-quota without data loss.
  - **Result (2026-08-21)**: 3/3 passed. `end_date < effective_date` raises `ValidationException` before any row is created (Edge Case #16). Downgrade conflict: 3 active `CompanyMember`s vs. a 2-user-limit target Plan is rejected without `acknowledged=True` with the tenant's original Subscription completely unchanged; with `acknowledged=True` the change applies, all 3 `CompanyMember` rows remain `active` (zero truncation), and `QuotaService.resolve()` against the new plan reports `state=reached` — the over-quota flag required no new persisted column.

**Phase 8 Exit Condition**: T103-T117 all implemented and proven; no Gate assigned to this phase (Gate D belongs to Phase 9) — quota/plan/subscription foundation is ready as a Phase 9/11 dependency. **PASS** — see Phase 8 closure PHR for full evidence.

---

## Phase 9: Entitlement Resolver, Safe Rollout & Point-of-Use Enforcement — **Gate D**

**Objective**: One authoritative entitlement resolver (ADR-3), a staged rollout that cannot break existing tenants (plan §34), then live enforcement on all five modules.
**Prerequisites**: Phase 8 (quota foundation included).
**Ordering rule**: enforcement (T129–T133) must **not** activate before the rollout mapping is verified (T128).

### Tasks

- [X] T118 Define the `ModuleEnablementProvider` protocol
  - **Purpose**: Per-module Tenant Toggle lookup without assuming a uniform master-key convention (ADR-3, plan §40).
  - **Files**: `backend/modules/platform_admin/services/module_enablement.py`
  - **Deps**: T104
  - **Acceptance**: Protocol with one method; documented default rule — **a module with no module-grain master toggle returns `enabled=True`**, so the Plan ceiling alone governs it.
  - **Result (2026-08-21)**: DONE. `ModuleEnablementProvider(Protocol)` with a single `is_enabled(company_id) -> bool` method; the default rule is documented in both the module docstring and `DefaultAlwaysEnabledModuleProvider`'s own docstring.

- [X] T119 [P] Implement the five module enablement providers
  - **Files**: `backend/modules/platform_admin/services/module_enablement.py`
  - **Deps**: T118
  - **Acceptance**: CRM reads `feature.crm.enabled`; Inventory/Sales/Purchase/Accounting apply the documented default rule unless a verified master key exists. Each provider reads its module's existing table **read-only** — never writes a tenant toggle.
  - **Result (2026-08-21)**: DONE. `CrmModuleEnablementProvider` delegates to the existing `CrmFeatureFlagService.is_enabled()` (the same service `require_crm_enabled` itself uses) — read-only. Re-verified directly against each of the other four modules' `*_FEATURE_FLAGS` catalogues (`inventory/constants.py`, `sales/constants.py`, `purchase/constants.py`, `accounting/constants.py`) that none defines a whole-module master key — all entries are fine-grained sub-features — confirming plan.md §40's finding still holds; a single stateless `DefaultAlwaysEnabledModuleProvider` instance is shared by all four (behaviourally identical, not a fabricated per-module distinction) via `get_module_enablement_provider(capability_key, db)`.

- [X] T120 [US-6] [FR-9A-170] Implement `PlatformEntitlementService.resolve_effective_entitlement()`
  - **Purpose**: The single deterministic resolver — no module re-implements this logic (BR-9A-015/016).
  - **Files**: `backend/modules/platform_admin/services/entitlement_service.py`
  - **Deps**: T118, T105, T106
  - **Acceptance**: Implements spec §17.2's table exactly: Plan Entitlement × Tenant Toggle × active Override. Evaluated per request, never cached indefinitely. Also consults tenant lifecycle and current subscription.
  - **Result (2026-08-21)**: DONE, with two documented, deliberate design decisions beyond the literal acceptance text. (1) **Override**: `EntitlementOverride` (spec §17.2's "active Override" row) is Phase 11's model (tasks.md T145) — creating it now would be future-phase leakage. An injectable `OverrideChecker` seam (mirroring `PlatformAdministratorService`'s `SessionRevoker` seam, T040/T054) makes the Override branch unreachable in Phase 9 without restructuring the method later. (2) **"Tenant lifecycle" / no active Subscription**: a real, verified defect was found and fixed here — see Defects Discovered in the closure report. The resolver deliberately does **not** re-check `Company.status` (that is `get_current_company_member`'s concern, Phase 7/Gate C, already gating every caller); "current subscription" is consulted directly, and when none exists the Plan ceiling is treated as **not yet in effect**, deferring entirely to the Tenant Toggle — reproducing exact pre-Epic-9A behaviour rather than a blanket denial. All other rows resolve exactly per §17.2.

- [X] T121 [P] Unit tests: the full entitlement matrix
  - **Files**: `backend/tests/unit/modules/platform_admin/test_entitlement_matrix.py`
  - **Deps**: T120
  - **Acceptance**: Every row of spec §17.2 covered, including "Not Allowed + Enabled → Unavailable" and "moved to a plan lacking a previously-entitled module → Unavailable, toggle preserved".
  - **Result (2026-08-21, SQLite in-memory, `db_session` fixture)**: PASS — 14 tests, going beyond the literal §17.2 rows: Allowed+Enabled, Allowed+Disabled (incl. no-toggle-row-at-all default), Not Allowed+Enabled/Disabled/absent-from-capability-map (all `plan_ceiling`), an injected-`OverrideChecker` proof (`override` wins over a denying plan) plus a no-checker-injected proof (ceiling still governs — Phase 9's documented gap), the no-Subscription defers-to-toggle behaviour (3 tests, added after the regression fix), default-rule-module (`inventory`) toggle-immunity (2 tests), and the full downgrade→re-upgrade cycle with an explicit DB-level assertion that the CRM toggle row is never rewritten at any point.

- [X] T122 Implement `require_capability_entitled(capability_key)` dependency
  - **Purpose**: The **point-of-use** ceiling — mutation-time checks alone are insufficient (ADR-3).
  - **Files**: `backend/modules/platform_admin/dependencies.py`
  - **Deps**: T120, T034
  - **Acceptance**: Raises `CapabilityNotEntitledError` (403) when the effective result is Unavailable; usable as a router-mount dependency.
  - **Result (2026-08-21)**: DONE. Dependency factory matching `require_platform_permission`'s established shape; reads `company_id` from the path (same convention as `get_current_company_member`), resolves via `PlatformEntitlementService`, raises `CapabilityNotEntitledError` with `{"capability_key", "reason"}` details on Unavailable. Proven live by T134-T136 (real HTTP through the actual mount) and indirectly by every Inventory/CRM/Sales/Purchase/Accounting regression re-run (T129-T133's Result notes).

- [X] T123 [US-6] Implement the read-only entitlement endpoint for UX
  - **Files**: `backend/modules/platform_admin/router.py`
  - **Deps**: T120, T064
  - **Acceptance**: `GET /platform/tenants/{companyId}/entitlements` requires `platform.entitlements.read`. Frontend use is **UX only** — never the security boundary.
  - **Result (2026-08-21)**: DONE. Added to the existing `tenant_router` (already mounted under `/platform`, T090/T114) — no new router mount needed. Returns one `{capability_key, available, reason}` entry per active seeded `Capability`, resolved via the same `PlatformEntitlementService` `require_capability_entitled` uses — one resolver, two consumers, never two implementations. `platform.entitlements.read` already existed in the Phase-2 seeded permission catalogue (`constants.py`) — no new permission code invented.

- [X] T124 Seed the five module capability rows
  - **Purpose**: Rollout step 2 (plan §34) — must exist before any plan references them.
  - **Files**: `backend/modules/platform_admin/services/capability_seed_service.py`
  - **Deps**: T104
  - **Acceptance**: Idempotent seed of `inventory`, `purchase`, `sales`, `accounting`, `crm` at module grain. **Not a migration.**
  - **Result (2026-08-21)**: DONE. `CapabilitySeedService.seed_capabilities()` mirrors `PlatformRbacSeedService`'s check-then-create idempotency technique exactly; a rerun with no catalogue change performs zero writes. Verified by T127/T128's tests, which call it directly (SQLite) — not a migration; no Alembic file touched.

- [X] T125 Create the baseline "Legacy/Unlimited" plan
  - **Purpose**: Rollout step 3 — guarantees existing tenants lose nothing. Revision 2 fix — `PlanQuota` now legitimately exists (T107).
  - **Files**: `backend/modules/platform_admin/services/rollout_service.py`
  - **Deps**: T124, T111, T107
  - **Acceptance**: One published plan with `PlanCapability.allowed=true` for all five capabilities and `PlanQuota.limit_value=NULL` (unlimited) for every quota key. Idempotent.
  - **Result (2026-08-21)**: DONE. `RolloutService.create_baseline_plan()` — code `legacy-unlimited`, always `published`, `PlanCapability.allowed=true` for every seeded `Capability`, `PlanQuota.limit_value=NULL` for every quota key. **Necessary implementation surface discovered during this task** (undocumented by any earlier task): `PlanQuota.quota_key` carries a real FK to `quota_definitions.key` (RESTRICT), and no prior task anywhere in tasks.md seeds that catalogue (T107 built only the models/resolver) — `_seed_quota_definitions()` seeds spec.md §17.3's six categories with a documented default `enforcement_style` per category (not fabricated from any spec text — explicitly flagged as a Tasks-phase default, matching `quota_service.py`'s own precedent for `APPROACHING_THRESHOLD_RATIO`). Idempotent: capability/quota ceilings are unconditionally re-applied on every call (create-or-update), so a resumed run after a partial failure still converges correctly — proven by T127/T128.

- [X] T126 Bulk-assign every existing tenant to the baseline plan
  - **Purpose**: Rollout step 4 — the step that makes `companies.subscription_id` non-null for pre-existing tenants.
  - **Files**: `backend/modules/platform_admin/services/rollout_service.py`
  - **Deps**: T125, T112
  - **Acceptance**: One active `Subscription` per existing company, actor = bootstrap Platform Owner, fully audited, idempotent and re-runnable. **Does not touch any tenant feature-toggle row.**
  - **Result (2026-08-21)**: DONE. `RolloutService.bulk_assign_existing_tenants()` calls the existing, already-audited `SubscriptionService.assign_or_change()` per company — no new audit action code invented. Idempotency achieved via a new `CompanyRepository.list_without_subscription()` read method (small, targeted addition, mirroring T112's own precedent of extending `CompanyRepository` for Epic 9A needs): only companies with `subscription_id IS NULL` are ever processed, so a company already assigned in a prior run is never revisited or re-audited. A standalone `main()` entrypoint (mirroring `bootstrap.py`'s established out-of-band, non-HTTP, non-migration convention) locates the bootstrap Platform Owner via a new `PlatformRbacRepository.get_active_administrator_ids_with_role()` method and runs both rollout steps. Proven not to touch any tenant feature-toggle table by T127.

- [X] T127 Verify existing feature-toggle rows are byte-for-byte preserved by the rollout
  - **Purpose**: Rollout step 5 (plan §34, requirement 6).
  - **Files**: `backend/tests/integration/services/platform_admin/test_entitlement_rollout.py`
  - **Deps**: T126
  - **Acceptance**: Snapshot all five modules' feature-flag tables before/after T124–T126 → identical. CRM enabled/disabled state specifically unchanged.
  - **Result (2026-08-21, SQLite in-memory)**: PASS — `test_crm_and_inventory_toggle_rows_unchanged_after_rollout`. Three tenants with distinct CRM toggle states (on/off/no-row) plus an Inventory sub-feature override, snapshotted across all 5 modules' feature-flag tables before/after running capability seeding + baseline plan creation + bulk-assignment: identical (`before == after`), with an explicit additional re-confirmation of each tenant's specific CRM state.

- [X] T128 Verify every existing tenant resolves to "available" for everything it had before
  - **Purpose**: Rollout step 5 verification — the go/no-go for enforcement.
  - **Files**: `backend/tests/integration/services/platform_admin/test_entitlement_rollout.py`
  - **Deps**: T127, T120
  - **Acceptance**: For every existing company × capability, effective entitlement matches pre-rollout effective access exactly. **Enforcement must not be activated until this is green.**
  - **Result (2026-08-21, SQLite in-memory)**: PASS — `test_effective_entitlement_matches_pre_rollout_access_for_every_capability`. Three tenants (CRM-on/CRM-off/CRM-default) × all 5 capabilities, post-rollout resolution compared against explicit pre-Epic-9A expected access (CRM per its own toggle; the other four unconditionally available, since no gate existed for them before this Epic) — exact match on every cell. Gate for T129-T133 satisfied before those tasks were started.

- [X] T129 Mount `require_capability_entitled("inventory")` on the Inventory router
  - **Files**: `backend/api/v1/router.py`
  - **Deps**: T128, T122
  - **Acceptance**: Added alongside the existing `get_current_company_member`; the module's own code is unchanged.
  - **Result (2026-08-21)**: DONE. Mounted on the company-scoped `/companies/{company_id}/inventory` include only (the separate bare `/inventory` health mount, which carries no `company_id`, is untouched — it never had `get_current_company_member` either). Named module-level `inventory_entitlement_gate = require_capability_entitled("inventory")` (not an inline call) so tests can target the exact closure via `app.dependency_overrides`, matching this codebase's own established `require_crm_enabled`-override convention. `git diff modules/inventory/` confirms zero changes to any Inventory source file. **Regression found and fixed** — see Defects Discovered: the full Inventory API suite (246 tests) initially failed 170/246 with `CAPABILITY_NOT_ENTITLED` (every test company has no Subscription); root-caused to the entitlement resolver's original "no Subscription → Unavailable" default (T120), fixed there, then this exact suite re-run clean: **246 passed, 0 failed** (real `test_client`/SQLite, `2356.50s`).

- [X] T130 [P] Mount `require_capability_entitled("purchase")` on the Purchase router
  - **Files**: `backend/api/v1/router.py`
  - **Deps**: T129
  - **Acceptance**: Same pattern.
  - **Result (2026-08-21)**: DONE. `purchase_entitlement_gate`. `git diff modules/purchase/` confirms zero source changes. Regression re-check: `tests/integration/api/v1/purchase/test_reports_isolation.py` — 1 passed (part of the combined 16/16 run below).

- [X] T131 [P] Mount `require_capability_entitled("sales")` on the Sales router
  - **Files**: `backend/api/v1/router.py`
  - **Deps**: T129
  - **Acceptance**: Same pattern.
  - **Result (2026-08-21)**: DONE. `sales_entitlement_gate`. `git diff modules/sales/` confirms zero source changes. Regression re-check: `tests/integration/api/v1/sales/test_phase0_api.py` — part of the combined 16/16 run below.

- [X] T132 [P] Mount `require_capability_entitled("accounting")` on the Accounting router
  - **Files**: `backend/api/v1/router.py`
  - **Deps**: T129
  - **Acceptance**: Same pattern; Accounting's existing permission checks are untouched.
  - **Result (2026-08-21)**: DONE. `accounting_entitlement_gate`. `git diff modules/accounting/` confirms zero source changes; Accounting's own `user_has_accounting_permission` checks are unaffected (different dependency, still runs after this one). Regression re-check (combined with Sales/Purchase): `tests/integration/api/v1/purchase/test_reports_isolation.py` + `tests/integration/api/v1/sales/test_phase0_api.py` + `tests/integration/api/v1/accounting/test_bank_statement_import.py` — **16 passed, 0 failed** (real `test_client`/SQLite, `252.13s`).

- [X] T133 Mount `require_capability_entitled("crm")` **in front of** the preserved `require_crm_enabled`
  - **Purpose**: `require_crm_enabled` alone is explicitly insufficient — it reads only the toggle (plan §35).
  - **Files**: `backend/api/v1/router.py`
  - **Deps**: T129
  - **Acceptance**: Mount order is `get_current_company_member` → `require_capability_entitled("crm")` → `require_crm_enabled`. **No CRM source file is modified.**
  - **Result (2026-08-21)**: DONE. Exact mount order confirmed by reading `api/v1/router.py`; named `crm_entitlement_gate`. `git diff modules/crm/` confirms zero changes to any CRM **source** file (two pre-existing CRM **test** files needed updates — see Defects Discovered: one assertion updated from `FEATURE_DISABLED` to `CAPABILITY_NOT_ENTITLED` with an explanatory docstring, since `require_capability_entitled`'s comprehensive Plan×Toggle resolver now legitimately denies first whenever CRM's toggle is off, per spec §17.2, making that specific pre-existing assertion stale rather than wrong; one test fixture updated to use `app.dependency_overrides[crm_entitlement_gate]` instead of a broken route-stripping attempt, to keep isolating `require_crm_enabled` specifically). Regression re-check: `tests/integration/api/v1/crm/test_production_router_mounting.py` + `tests/integration/api/v1/crm/test_feature_flag_gate.py` — **15 passed, 0 failed** (real `test_client`/SQLite, combined ~4 min).

- [X] T134 **[Gate D]** Test: Plan allows + toggle enabled → allowed; Plan denies + toggle enabled → denied
  - **Files**: `backend/tests/security/modules/platform_admin/test_entitlement_enforcement.py`
  - **Deps**: T129–T133
  - **Acceptance**: Parametrised across **all five** modules.
  - **Result (2026-08-21, real HTTP via `test_client`, SQLite)**: PASS — 10 tests (`TestPlanAllowsAndTogglePermitsIsAllowed` × 5 modules + `TestPlanDeniesIsUnavailableRegardlessOfToggle` × 5 modules), each a genuine login + real access token + real mounted dependency chain. One minimal, low-dependency GET endpoint per module (`.../feature-flags` for the four; `.../my-permissions` for CRM, which has no `feature-flags` endpoint). Denial case additionally asserts `error.code == "CAPABILITY_NOT_ENTITLED"`.

- [X] T135 **[Gate D]** Test: Plan downgrade denies access on the next request without touching the toggle
  - **Purpose**: The Correction-1 bypass regression guard.
  - **Files**: `backend/tests/security/modules/platform_admin/test_entitlement_enforcement.py`
  - **Deps**: T134
  - **Acceptance**: Tenant on an allowing plan with the toggle on → move to a denying plan → next request **denied** → assert the toggle row in the database is **still `true`** (preference preserved, never rewritten).
  - **Result (2026-08-21, real HTTP)**: PASS — `test_downgrade_denies_next_request_and_toggle_row_stays_true`. Real login → CRM endpoint allowed (200) → Platform Admin reassigns the Subscription to a denying plan (service-level, itself covered by Phase 8's own HTTP tests) → same still-valid access token, same endpoint → 403 `CAPABILITY_NOT_ENTITLED` → DB-level assertion the `crm_feature_flags` row is unchanged (`is_enabled=True`).

- [X] T136 **[Gate D]** Test: re-upgrading restores access at the tenant's preserved preference
  - **Files**: `backend/tests/security/modules/platform_admin/test_entitlement_enforcement.py`
  - **Deps**: T135
  - **Acceptance**: Moving back to an allowing plan resumes access automatically, with no toggle mutation at any point.
  - **Result (2026-08-21, real HTTP)**: PASS — `test_re_upgrade_restores_access_without_any_toggle_mutation`. Full downgrade → 403 → re-upgrade → 200 cycle on the same real access token throughout, with a final DB-level assertion the toggle row was never touched at any point in the cycle.

- [X] T137 **[Gate D]** Gate D sign-off
  - **Deps**: T134–T136
  - **Acceptance**: Plan ceiling proven at point of use across all five modules.
  - **Result (2026-08-21)**: **GATE D: PASS.** 12/12 real-HTTP Gate D tests green (T134 ×10, T135, T136) proving Plan-ceiling point-of-use enforcement across all five business modules, plus the downgrade/re-upgrade toggle-preservation guarantee. Combined with T121's 14 resolver unit tests, T127/T128's rollout-safety proofs, and zero-regression re-verification across every phase-affected module (Inventory 246/246, CRM 15/15, Sales+Purchase+Accounting 16/16 spot-checks) — see the Phase 9 closure PHR for full evidence. Phase 10 may now begin.

**Phase 9 Exit Condition**: T118-T137 all implemented and proven; Gate D signed off. **PASS** — see Phase 9 closure PHR (`history/prompts/009a-platform-admin/0022-...`) for full evidence, including the entitlement-resolver "no active Subscription" defect discovered and fixed during implementation (see that PHR's Response snapshot).

---

## Phase 10: Existing Feature-Toggle Mutation Hardening

**Objective**: Close the confirmed authorization gap on exactly the three vulnerable modules (plan §14, §27). Accounting and CRM are **not** rewritten.
**Prerequisites**: Gate D.

### Tasks

- [ ] T138 Add `inventory.settings.manage` permission + check to the Inventory toggle endpoint
  - **Purpose**: Ordinary active members must not be able to flip module feature state (FR-9A-183/184).
  - **Files**: `backend/modules/inventory/router.py`, `backend/modules/inventory/constants.py`
  - **Deps**: T137
  - **Acceptance**: Replicates Accounting's existing `user_has_accounting_permission` pattern exactly; the endpoint additionally consults the entitlement ceiling (secondary guard, FR-9A-185).

- [ ] T139 [P] Add `sales.settings.manage` permission + check to the Sales toggle endpoint
  - **Files**: `backend/modules/sales/router.py`, `backend/modules/sales/constants.py`
  - **Deps**: T138
  - **Acceptance**: Same pattern.

- [ ] T140 [P] Add `purchase.settings.manage` permission + check to the Purchase toggle endpoint
  - **Files**: `backend/modules/purchase/router.py`, `backend/modules/purchase/constants.py`
  - **Deps**: T138
  - **Acceptance**: Same pattern.

- [ ] T141 Seed the three new permissions onto existing tenant `owner`/`admin` roles via `RoleSeedService`
  - **Purpose**: Prevents locking out tenant admins who legitimately relied on the previous (unguarded) behaviour (plan §38 risk mitigation). Revision 2 fix — the previous "migration **or** RoleSeedService" wording was ambiguous and could have produced a forbidden `062`.
  - **Files**: `backend/modules/users_roles/constants.py` (add the 3 codes to `INITIAL_PERMISSIONS` and to `DEFAULT_ROLE_PERMISSIONS` for `owner`/`admin`), `backend/modules/users_roles/services/role_seed_service.py` (existing idempotent seeder — extend only if required, do not rewrite)
  - **Deps**: T138–T140
  - **Acceptance**: The three codes are seeded through the **existing `RoleSeedService`** mechanism, which plan.md §14 names explicitly ("seeded via the existing `RoleSeedService` convention") and which is already idempotent (skips duplicates via unique constraints). Existing owner/admin members can still manage toggles immediately after deploy; ordinary members cannot. **NO NEW MIGRATION `062` MAY BE CREATED** — the Epic 9A migration sequence is frozen at `057`–`061` and T029 asserts this. If a backfill onto already-existing role rows proves impossible through `RoleSeedService` alone, **STOP and report** rather than adding a migration.

- [ ] T142 [P] Security test: ordinary active member cannot mutate feature state on the three hardened modules
  - **Files**: `backend/tests/security/modules/platform_admin/test_feature_toggle_hardening.py`
  - **Deps**: T141
  - **Acceptance**: 403 for a plain member; success for an owner/admin — across Inventory, Sales, Purchase.

- [ ] T143 [P] Regression test: Accounting and CRM toggle behaviour is unchanged
  - **Purpose**: Proves the already-correct modules were not disturbed.
  - **Files**: `backend/tests/security/modules/platform_admin/test_feature_toggle_hardening.py`
  - **Deps**: T141
  - **Acceptance**: Accounting still requires `accounting.approvalworkflow.manage`; CRM still requires `require_admin_or_above()`; behaviour identical to the Phase 1 baseline.

- [ ] T144 [P] Test: a tenant cannot enable a toggle beyond the Plan ceiling
  - **Files**: `backend/tests/security/modules/platform_admin/test_feature_toggle_hardening.py`
  - **Deps**: T141
  - **Acceptance**: With a denying plan, even a tenant owner's enable attempt is rejected with a clear error (no silently-ineffective write).

---

## Phase 11: Overrides, Quota Administration, Usage & AI-Credit Readiness

**Objective**: Administrative overrides (spec §16), quota administration workflows on top of the Phase-8 foundation, PostgreSQL usage metering, and provider-neutral AI readiness.
**Prerequisites**: Gate D.
**Revision 2 note**: quota **models and the resolver** now live in Phase 8; this phase adds the override/administration workflows that consume them. No model or resolver is duplicated.

### Tasks

- [ ] T145 [US-6] Create `EntitlementOverride` model + repository
  - **Files**: `backend/modules/platform_admin/models/entitlement_override.py`, `repositories/override_repository.py`
  - **Deps**: T104
  - **Acceptance**: Per data-model.md; mandatory `reason`; nullable `expires_at` (**NULL = permanent, explicitly distinguishable**); partial unique index on active rows.

- [ ] T146 [US-6] [FR-9A-171] Implement override grant/revoke service
  - **Files**: `backend/modules/platform_admin/services/override_service.py`
  - **Deps**: T145, T037
  - **Acceptance**: Requires `platform.entitlements.override`; records tenant, capability, reason, actor, optional expiry; grant and revoke both audited.

- [ ] T147 [FR-9A-172] Implement expiry-at-read-time semantics + audited automatic reversion
  - **Purpose**: Correctness must not depend on a scheduler (none exists in this repo, plan §40).
  - **Files**: `backend/modules/platform_admin/services/override_service.py`, `entitlement_service.py`
  - **Deps**: T146, T120
  - **Acceptance**: The resolver checks `expires_at > now()` at read time and never trusts a stale `is_active`; reversion writes an audit entry.

- [ ] T148 [P] Test: override precedence and expiry
  - **Files**: `backend/tests/unit/modules/platform_admin/test_override_precedence.py`
  - **Deps**: T147
  - **Acceptance**: Active override beats a denying plan; an **expired** override is never effective even if `is_active` was left stale.

- [ ] T149 [US-10] Implement tenant quota override grant/revoke + quota administration service
  - **Purpose**: The workflow layer over the Phase-8 `TenantQuotaOverride` model (T107) and resolver (T108) — no new model, no second resolver.
  - **Files**: `backend/modules/platform_admin/services/quota_admin_service.py`
  - **Deps**: T107, T108, T037
  - **Acceptance**: Requires `platform.quotas.override`; mandatory reason, actor, optional expiry; grant and revoke audited; expiry handled at read time exactly like entitlement overrides.

- [ ] T150 [US-10] Create `UsageRecord` model + repository
  - **Files**: `backend/modules/platform_admin/models/usage_record.py`, `repositories/usage_repository.py`
  - **Deps**: T032
  - **Acceptance**: Per data-model.md (`company_id`, `metric_key`, `quantity`, `period_start/end`, `source`, `recorded_at`); PostgreSQL only — **no event-streaming infrastructure**.

- [ ] T151 [FR-9A-060] Implement periodic usage computation
  - **Files**: `backend/modules/platform_admin/services/usage_service.py`
  - **Deps**: T150
  - **Acceptance**: Batch computation per company/metric/period (not per-request increments, so no row-locking design is needed); idempotent per period; manually triggerable.

- [ ] T152 [FR-9A-062] Implement the "measurement unavailable" state
  - **Purpose**: A missing period must never render as `0` (spec Edge Case #15).
  - **Files**: `backend/modules/platform_admin/services/quota_service.py`
  - **Deps**: T151, T108
  - **Acceptance**: Absence of a current-period `UsageRecord` is an explicitly-checked `unavailable` state in the existing resolver, never an implicit zero fallback.

- [ ] T153 [P] Test: usage unavailability is distinguishable from genuine zero
  - **Files**: `backend/tests/integration/services/platform_admin/test_usage.py`
  - **Deps**: T152
  - **Acceptance**: No-row → `unavailable`; a real zero-quantity row → `ok` with `0`.

- [ ] T154 [US-12] [BR-9A-026] Create `AiCreditLedgerEntry` model + repository
  - **Files**: `backend/modules/platform_admin/models/ai_credit_ledger.py`, `repositories/ai_credit_repository.py`
  - **Deps**: T032
  - **Acceptance**: Signed `delta`; nullable `actor_platform_administrator_id` (NULL = future automatic debit, populated = manual adjustment); `provider`/`model` free-text — **no vendor named anywhere in the model**.

- [ ] T155 [US-12] [BR-9A-027] Implement manual AI credit adjustment
  - **Files**: `backend/modules/platform_admin/services/ai_credit_service.py`
  - **Deps**: T154, T037
  - **Acceptance**: Requires `platform.ai_credits.adjust`, a mandatory reason, and produces a full audit record linked by `platform_audit_event_id`. Balance is `SUM(delta)`. **No AI provider is integrated.**

- [ ] T156 [P] [FR-9A-235] Test: AI views show "not yet active", never a zero-value table
  - **Files**: `backend/tests/integration/api/v1/platform_admin/test_ai_credits.py`
  - **Deps**: T155
  - **Acceptance**: With an empty ledger the API returns an explicit not-yet-active state; no placeholder zero rows are ever written.

- [ ] T157 Implement override/quota/usage/AI routes
  - **Files**: `backend/modules/platform_admin/router.py`
  - **Deps**: T146, T149, T151, T155, T064
  - **Acceptance**: Exactly the paths in `contracts/platform-admin-v1.yaml` with their declared permissions — no extra CRUD invented.

---

## Phase 12: Support Access — **Gate F**

**Objective**: Time-bounded, reason-required, **inspection-only** cross-tenant access (spec §18, resolved OQ-2). No impersonation.
**Prerequisites**: Gate C (lifecycle), Gate E (audit).

### Tasks

- [ ] T158 [US-9] Create `SupportAccessGrant` model + repository
  - **Files**: `backend/modules/platform_admin/models/support_access_grant.py`, `repositories/support_access_repository.py`
  - **Deps**: T032
  - **Acceptance**: Per data-model.md; mandatory `reason`; mandatory `expires_at` (**no indefinite grant**); `status` `active|expired|terminated`.

- [ ] T159 [US-9] [FR-9A-190..193] Implement grant initiation
  - **Files**: `backend/modules/platform_admin/services/support_access_service.py`
  - **Deps**: T158, T037
  - **Acceptance**: Requires `platform.support_access.initiate`; exactly one target tenant per grant; mandatory reason; explicit expiry; start audited.

- [ ] T160 [US-9] [FR-9A-196/197] Implement termination and lazy expiry
  - **Files**: `backend/modules/platform_admin/services/support_access_service.py`
  - **Deps**: T159
  - **Acceptance**: Expiry checked at request time (`expires_at < now()` → 403, status flipped lazily); explicit termination by the initiator or a sufficiently-privileged admin; end timestamp audited.

- [ ] T161 [US-9] [FR-9A-195] Implement per-action audit within an active grant
  - **Files**: `backend/modules/platform_admin/services/support_access_service.py`
  - **Deps**: T160, T036
  - **Acceptance**: Every read during a grant writes a `PlatformAuditEvent` with `support_access_grant_id` populated — in addition to the grant's own start/end rows (BR-9A-020, no parallel audit table).

- [ ] T162 [US-9] Implement the support-access routes
  - **Files**: `backend/modules/platform_admin/router.py`
  - **Deps**: T159–T161, T064
  - **Acceptance**: `POST /platform/tenants/{companyId}/support-access`, `DELETE /platform/support-access/{grantId}`, `GET /platform/support-access` per contract. The router imports **no** business-record repository from any of the five modules.

- [ ] T163 **[Gate F]** [BR-9A-021] Security test: support access cannot reach tenant business records
  - **Purpose**: The resolved-OQ-2 boundary — read **or** write, inside **or** outside a grant.
  - **Files**: `backend/tests/security/modules/platform_admin/test_support_access_boundary.py`
  - **Deps**: T162
  - **Acceptance**: With an active grant on a tenant holding real invoices/sales orders/journal entries/stock movements/CRM records, no support-access route exposes any of them; a static check asserts the support-access module imports no business-record repository.

- [ ] T164 [P] Test: grant expiry and termination end access
  - **Files**: `backend/tests/security/modules/platform_admin/test_support_access_boundary.py`
  - **Deps**: T162
  - **Acceptance**: Post-expiry and post-termination requests are rejected; both are recorded in the audit trail.

- [ ] T165 [P] Test: support access requires its own permission and a reason
  - **Files**: `backend/tests/security/modules/platform_admin/test_support_access_boundary.py`
  - **Deps**: T162
  - **Acceptance**: Missing permission → 403; missing/empty reason → rejected before the grant is created.

- [ ] T166 **[Gate F]** Gate F sign-off
  - **Deps**: T163–T165
  - **Acceptance**: Support boundary proven; no impersonation exists anywhere in the implementation.

---

## Phase 13: Platform Operational APIs (Dashboard, Tenants, Audit, Health)

**Objective**: The remaining contract endpoints (US-1, US-2, US-8, US-11).
**Prerequisites**: Phases 6–12.

### Tasks

- [ ] T167 [US-2] [FR-9A-010] Implement the tenant directory endpoint
  - **Files**: `backend/modules/platform_admin/services/tenant_directory_service.py`, `router.py`
  - **Deps**: T064
  - **Acceptance**: `GET /platform/tenants` requires `platform.tenants.read`; search/filter/sort/paginate across **all** `CompanyStatus` values; bounded queries only (no "load all").

- [ ] T168 [US-2] [FR-9A-020/021] Implement the tenant 360° detail endpoint
  - **Files**: `backend/modules/platform_admin/services/tenant_directory_service.py`, `router.py`
  - **Deps**: T167, T120, T108
  - **Acceptance**: Returns identity, status, onboarding info, plan, subscription, entitlements, usage-vs-limits, user count, lifecycle history, platform admin actions, audit events. **Exposes no tenant business transaction record** (FR-9A-021).

- [ ] T169 [US-3] [FR-9A-016] Implement the lifecycle-history endpoint
  - **Files**: `backend/modules/platform_admin/router.py`
  - **Deps**: T168, T078
  - **Acceptance**: `GET /platform/tenants/{companyId}/lifecycle-history` shows every transition with actor, timestamp and reason.

- [ ] T170 [US-8] Implement the platform audit endpoint
  - **Files**: `backend/modules/platform_admin/router.py`
  - **Deps**: T078, T064
  - **Acceptance**: `GET /platform/audit` requires `platform.audit.read`; supports the full FR-9A-200 filter set; paginated; append-only (no mutation route exists).

- [ ] T171 [US-1] [FR-9A-001] Implement the dashboard aggregate service
  - **Files**: `backend/modules/platform_admin/services/dashboard_service.py`
  - **Deps**: T167, T108, T078
  - **Acceptance**: Tenant counts by status (`GROUP BY`), recent registrations (indexed `LIMIT`), plan/subscription distribution, quota warnings, recent platform actions, health summary. No unbounded aggregation, no per-tenant N+1.

- [ ] T172 [US-1] [FR-9A-003/004] Implement per-widget state and permission-gated omission
  - **Purpose**: "Data unavailable ≠ zero" (spec §22).
  - **Files**: `backend/modules/platform_admin/services/dashboard_service.py`, `router.py`
  - **Deps**: T171
  - **Acceptance**: Each widget independently reports `loading|populated|empty|unavailable`; a failed sub-query renders `unavailable`, **never `0`**; widgets the caller lacks permission for are **omitted** entirely, not shown empty or erroring.

- [ ] T173 [US-1] [FR-9A-005] Gate the AI widget on real data
  - **Files**: `backend/modules/platform_admin/services/dashboard_service.py`
  - **Deps**: T172, T154
  - **Acceptance**: The AI usage widget appears only once `ai_credit_ledger_entries` has at least one row; otherwise absent (not populated-empty).

- [ ] T174 [US-11] [FR-9A-240/241] Implement the platform health endpoint
  - **Files**: `backend/modules/platform_admin/services/health_service.py`, `router.py`
  - **Deps**: T064
  - **Acceptance**: Surfaces the existing `/health`, `/health/live`, `/health/ready` checks plus outbox pending/published counts, and **explicitly labels the relay as a logging-only stub** rather than implying real message-bus delivery.

- [ ] T175 [P] [FR-9A-243] Test: an unavailable dependency renders as `unavailable` with its check name
  - **Files**: `backend/tests/integration/api/v1/platform_admin/test_dashboard_health.py`
  - **Deps**: T172, T174
  - **Acceptance**: A degraded database check shows `database: degraded`, never a blanket "unknown" and never a fabricated `0`.

- [ ] T176 [P] [FR-9A-120/121] Implement platform export endpoints
  - **Files**: `backend/modules/platform_admin/services/export_service.py`, `router.py`
  - **Deps**: T167, T170
  - **Acceptance**: Tenant directory / subscription / usage / audit export scoped to what the caller's permissions already allow online; **never** includes tenant business transaction records.

- [ ] T177 [P] Contract conformance test against `platform-admin-v1.yaml`
  - **Purpose**: Every declared path exists with the declared method and permission; no undeclared CRUD was invented.
  - **Files**: `backend/tests/integration/api/v1/platform_admin/test_contract_conformance.py`
  - **Deps**: T167–T176, T114, T157, T162, T090, T068, T069
  - **Acceptance**: All **28 contract paths / 33 operations** implemented — including the 6 Administrator/RBAC operations from T068/T069, which are now explicit dependencies. Each operation's declared `x-permission` matches the wired `require_platform_permission` code; every declared HTTP method exists; **no undeclared CRUD was invented** (an endpoint present in code but absent from the contract also fails the test). Any deviation fails.

---

## Phase 14: Platform Frontend Foundation

**Objective**: Separate Platform auth state and a non-crossing HTTP client (ADR-11), plus the canonical tenant-context accessor (ADR-13).
**Prerequisites**: Phase 13 (APIs must exist before pages consume them).

### Tasks

- [ ] T178 [ADR-11] Refactor `ApiClient` to accept an injected `AuthStrategy`
  - **Purpose**: Structural prevention of token crossover; the singleton currently hardcodes tenant auth at module scope.
  - **Files**: `frontend/src/lib/api/client.ts`
  - **Deps**: T008
  - **Acceptance**: `AuthStrategy { getToken, refresh, onAuthFailure }` injected via constructor; `buildHeaders()`, the 401 branch and `postMultipart()` all route through `this.auth`. Shared transport/URL/error/unwrap logic stays in the one class.

- [ ] T179 Export `apiClient` with the tenant strategy — behaviour unchanged
  - **Purpose**: Zero regression for every existing domain file.
  - **Files**: `frontend/src/lib/api/client.ts`, `frontend/src/lib/auth/tenantAuthStrategy.ts`
  - **Deps**: T178
  - **Acceptance**: `accounting.ts`, `crm.ts`, `sales.ts`, etc. are **not modified**; existing behaviour byte-identical.

- [ ] T180 Create the platform token storage and refresh lock
  - **Files**: `frontend/src/lib/platform-auth/platformTokenStorage.ts`, `platformAuthClient.ts`
  - **Deps**: T178
  - **Acceptance**: Platform access token **in-memory only** (mirroring the tenant XSS-mitigation rationale); platform refresh token in its own storage key, never `erp_refresh_token`; `acquirePlatformRefreshLock()` is a **separate** single-flight promise from the tenant lock.

- [ ] T181 Export `platformApiClient` with the platform strategy
  - **Files**: `frontend/src/lib/api/platform.ts`
  - **Deps**: T180, T179
  - **Acceptance**: Own `platformBase()` path helper; imports only the platform strategy; used by every Platform page.

- [ ] T182 [P] Test: zero token crossover in both directions
  - **Files**: `frontend/src/lib/api/__tests__/token-separation.test.ts`
  - **Deps**: T181
  - **Acceptance**: Platform requests carry only the platform token; tenant requests only the tenant token; neither client can read the other's storage.

- [ ] T183 [P] Test: a 401 invokes only its own domain's refresh flow
  - **Files**: `frontend/src/lib/api/__tests__/token-separation.test.ts`
  - **Deps**: T182
  - **Acceptance**: Platform 401 → only `acquirePlatformRefreshLock`; tenant 401 → only `acquireRefreshLock`; a failed platform refresh does **not** clear tenant tokens nor emit the tenant `session-expired` event (and vice versa). Includes a concurrent-401 case proving the locks are independent.

- [ ] T184 [ADR-13] Create the canonical tenant-context accessor
  - **Purpose**: A contract over the existing persistence key — **not** a broad ERP refactor.
  - **Files**: `frontend/src/lib/tenant-context/activeCompany.ts`
  - **Deps**: none
  - **Acceptance**: `getActiveCompanyId()/setActiveCompanyId()/clearActiveCompanyId()` backed by the unchanged `erp_active_company_id` key; 100% compatible with `CompanyContext.tsx`. **Existing modules are not migrated** (out of scope).

- [ ] T185 Create `PlatformAuthContext`
  - **Files**: `frontend/src/contexts/PlatformAuthContext.tsx`
  - **Deps**: T181
  - **Acceptance**: Own login/logout/refresh/session-expiry state; **never nested inside or sharing state with** `AuthContext`; handles deactivated-administrator responses.

- [ ] T186 [BR-9A-035] Create `PlatformSelectedTenantContext`
  - **Purpose**: Platform's tenant selection must never touch tenant context.
  - **Files**: `frontend/src/contexts/PlatformSelectedTenantContext.tsx`
  - **Deps**: T185
  - **Acceptance**: In-memory only; **never reads or writes `erp_active_company_id`**; never grants any permission; cleared on platform logout.

- [ ] T187 [P] Test: platform tenant selection does not disturb tenant context
  - **Files**: `frontend/src/contexts/__tests__/context-isolation.test.tsx`
  - **Deps**: T186, T184
  - **Acceptance**: Selecting a tenant in the Platform context leaves `erp_active_company_id` unchanged; manipulating `erp_active_company_id` grants no platform capability.

---

## Phase 15: Platform Frontend Shell & Pages

**Objective**: A dedicated `/platform-admin/...` area, structurally distinct from tenant admin.
**Prerequisites**: Phase 14.

### Tasks

- [ ] T188 Create the **protected** `(platform-admin)` route group, layout and guard
  - **Purpose**: Its own shell — **not** `AppLayout`, not the tenant `Sidebar` (whose "SuperAdmin" check is an acknowledged placeholder). Revision 3 fix — this layout guards **authenticated pages only**; the login page lives in a *sibling* route group (T190) so it can never be wrapped by this redirecting layout.
  - **Files**: `frontend/src/app/(platform-admin)/platform-admin/layout.tsx`
  - **Deps**: T185
  - **Acceptance**: Wraps only the authenticated `/platform-admin/*` pages (`dashboard`, `tenants`, `plans`, …). Redirects to `/platform-admin/login` when there is no valid platform session; client-side guard matching the existing `(protected)/layout.tsx` convention (**no Next.js middleware introduced** — the repo has none). Structurally cannot wrap `/platform-admin/login`, because that route is defined in the `(platform-auth)` group (T190). Verified against T007's collision check.
  - **Chosen structure** (mirrors the repository's existing `(auth)` vs `(protected)` split exactly — `frontend/src/app/(auth)/login` is already public while `(protected)/layout.tsx` redirects):
    ```
    frontend/src/app/
      (platform-auth)/                      ← PUBLIC, no guard
        platform-admin/login/page.tsx       → /platform-admin/login
      (platform-admin)/                     ← PROTECTED
        platform-admin/layout.tsx           ← guard + shell
        platform-admin/dashboard/page.tsx   → /platform-admin/dashboard
        platform-admin/tenants/…            → /platform-admin/tenants
        …
    ```
    Route groups are stripped from the URL, so both groups contribute to the same `/platform-admin/*` URL space with **no collision** (the complete paths differ), and the guard applies to authenticated pages only.

- [ ] T189 Create permission-aware Platform navigation
  - **Files**: `frontend/src/components/platform-admin/PlatformSidebar.tsx`
  - **Deps**: T188
  - **Acceptance**: Renders only entries the administrator's resolved permission set allows — genuinely permission-driven, unlike the tenant sidebar's placeholder. UX only; the server remains authoritative.

- [ ] T190 [P] Create the Platform login page in the **public** `(platform-auth)` group — `/platform-admin/login`
  - **Purpose**: Revision 3 fix — previously planned inside `(platform-admin)/`, where the redirecting layout would have wrapped it and produced an infinite `login → guard → login` loop.
  - **Files**: `frontend/src/app/(platform-auth)/platform-admin/login/page.tsx` (and a minimal `(platform-auth)/layout.tsx` **only if** the repo's `(auth)` group has one — otherwise none is added)
  - **Deps**: T183
  - **Acceptance**: **Structurally outside** the protected shell — it is a sibling route group, so `(platform-admin)/platform-admin/layout.tsx` provably cannot wrap it. Consumes `PlatformAuthContext` (T183) directly, not the guarded layout. Generic error text that never reveals whether an email exists as a tenant user; loading/error states. On success, redirects to `/platform-admin/dashboard`. **Depends on T183, not T188** — the login page must not depend on the guard it is exempt from.

- [ ] T191 [P] [US-1] Create the Platform Dashboard page — `/platform-admin/dashboard`
  - **Files**: `frontend/src/app/(platform-admin)/platform-admin/dashboard/page.tsx`
  - **Deps**: T189, T172
  - **Acceptance**: Requires `platform.dashboard.view`; each widget renders loading/populated/empty/**unavailable** distinctly; a failed metric never displays `0`; unauthorised widgets are omitted.

- [ ] T192 [P] [US-2] Create the Tenants list page — `/platform-admin/tenants`
  - **Files**: `frontend/src/app/(platform-admin)/platform-admin/tenants/page.tsx`
  - **Deps**: T189, T167
  - **Acceptance**: Requires `platform.tenants.read`; paginated search/filter/sort; explicit empty state (not an error).

- [ ] T193 [P] [US-2] [US-3] Create the Tenant Detail page — `/platform-admin/tenants/[tenantId]`
  - **Files**: `frontend/src/app/(platform-admin)/platform-admin/tenants/[tenantId]/page.tsx`
  - **Deps**: T192, T168, T186, T090
  - **Acceptance**: Uses `PlatformSelectedTenantContext` (never `erp_active_company_id`); shows administrative context only; suspend/reactivate actions require a typed reason and an explicit confirmation dialog; per-section `unavailable` state.

- [ ] T194 [P] [US-4] Create the Plans page — `/platform-admin/plans`
  - **Files**: `frontend/src/app/(platform-admin)/platform-admin/plans/page.tsx`
  - **Deps**: T189, T114
  - **Acceptance**: Requires `platform.plans.read`; management actions gated on `platform.plans.manage`; retire action confirmed.

- [ ] T195 [P] [US-5] Create the Subscriptions page — `/platform-admin/subscriptions`
  - **Files**: `frontend/src/app/(platform-admin)/platform-admin/subscriptions/page.tsx`
  - **Deps**: T194, T113
  - **Acceptance**: Surfaces the downgrade usage-conflict and requires explicit acknowledgement before applying.

- [ ] T196 [P] [US-6] Create the Entitlements page — `/platform-admin/entitlements`
  - **Files**: `frontend/src/app/(platform-admin)/platform-admin/entitlements/page.tsx`
  - **Deps**: T189, T123, T146
  - **Acceptance**: Shows effective entitlement per capability; override grant requires reason + optional expiry; permanent vs temporary visually distinguished.

- [ ] T197 [P] [US-10] Create the Quotas page — `/platform-admin/quotas`
  - **Files**: `frontend/src/app/(platform-admin)/platform-admin/quotas/page.tsx`
  - **Deps**: T189, T149, T157
  - **Acceptance**: Renders all five quota states distinctly; `unavailable` never shown as `0`; unlimited shown as unlimited, not a number.

- [ ] T198 [P] [US-7] Create the Platform Administrators page — `/platform-admin/administrators`
  - **Files**: `frontend/src/app/(platform-admin)/platform-admin/administrators/page.tsx`
  - **Deps**: T189, T068, T179
  - **Acceptance**: Consumes the **Administrator API routes (T068)** exclusively through `platformApiClient` (T179) — the page must never depend conceptually on a Python service. Requires `platform.admins.read` for listing; create/activate/deactivate actions gated on `platform.admins.manage`. Deactivate action is confirmed and warns that active sessions will be invalidated; surfaces the `LastPlatformOwnerError` 409 as a clear, specific message.

- [ ] T199 [P] [US-7] Create the Platform Roles page — `/platform-admin/roles`
  - **Files**: `frontend/src/app/(platform-admin)/platform-admin/roles/page.tsx`
  - **Deps**: T198, T069, T179
  - **Acceptance**: Consumes the **RBAC API routes (T069)** exclusively through `platformApiClient` (T179) — never a direct conceptual dependency on a Python service. Requires `platform.rbac.read` for listing; role create/update and role assignment gated on `platform.rbac.manage`. Surfaces the self-escalation 403 and last-Platform-Owner 409 as clear, specific errors rather than generic failures.

- [ ] T200 [P] [US-8] Create the Audit page — `/platform-admin/audit`
  - **Files**: `frontend/src/app/(platform-admin)/platform-admin/audit/page.tsx`
  - **Deps**: T189, T170
  - **Acceptance**: Full filter set; paginated; read-only (no edit/delete affordance anywhere).

- [ ] T201 [P] [US-10] [US-12] Create the Usage page — `/platform-admin/usage`
  - **Files**: `frontend/src/app/(platform-admin)/platform-admin/usage/page.tsx`
  - **Deps**: T189, T151, T155
  - **Acceptance**: Usage per metric/period; AI section shows the explicit "not yet active" state until the ledger has data; manual credit adjustment requires a reason.

- [ ] T202 [P] [US-9] Create the Support Access page — `/platform-admin/support-access`
  - **Files**: `frontend/src/app/(platform-admin)/platform-admin/support-access/page.tsx`
  - **Deps**: T189, T162
  - **Acceptance**: Grant requires tenant + reason + expiry; an active grant shows a **persistent, unmistakable privileged-mode indicator** (FR-9A-194); terminate action confirmed.

- [ ] T203 [P] [US-11] Create the Health page — `/platform-admin/health`
  - **Files**: `frontend/src/app/(platform-admin)/platform-admin/health/page.tsx`
  - **Deps**: T189, T174
  - **Acceptance**: Names the specific failing check; labels the outbox relay honestly as a stub.

- [ ] T204 [P] Frontend tests: permission-aware nav and UI states
  - **Files**: `frontend/src/app/(platform-admin)/__tests__/platform-shell.test.tsx`
  - **Deps**: T188–T203
  - **Acceptance**: Missing permission → nav entry hidden **and** the route still refused server-side; loading/empty/error/degraded states asserted per page; destructive actions require confirmation. (Route-guard/redirect behaviour is covered separately and explicitly by T205.)

- [ ] T205 [P] Frontend route-guard tests: login is outside the protected shell, with no redirect loop
  - **Purpose**: Revision 3 — proves the `(platform-auth)` / `(platform-admin)` split actually holds at runtime, and that tenant authentication can never satisfy Platform route protection.
  - **Files**: `frontend/src/app/(platform-admin)/__tests__/platform-route-guard.test.tsx`
  - **Deps**: T188, T190, T183
  - **Acceptance**: Five explicit cases, all required:
    - **A — unauthenticated login page**: visit `/platform-admin/login` with no platform session → the login page renders, and **no redirect occurs** (assert zero `router.replace` calls; a loop would fail this).
    - **B — unauthenticated protected route**: visit `/platform-admin/dashboard` with no platform session → redirected to `/platform-admin/login`, exactly once.
    - **C — authenticated Platform Admin**: with a valid platform session → `/platform-admin/dashboard` renders inside the protected Platform shell, no redirect.
    - **D — tenant auth does not count**: with a valid **tenant** session but **no** platform session → `/platform-admin/dashboard` still redirects to `/platform-admin/login`. Proves tenant/Platform auth separation at the routing layer (complements the backend proofs in T055/T056).
    - **E — logout**: Platform logout → platform session cleared → a protected route redirects to `/platform-admin/login` **and** the login page remains reachable and non-looping.
  - **Isolation requirement**: none of these cases may clear tenant tokens, emit the tenant `session-expired` event, or touch `erp_active_company_id`.

---

## Phase 16: Security, Integration & Observability Hardening

**Objective**: The exhaustive route-permission matrix (now that every router exists) plus the remaining security, observability and performance safeguards.
**Prerequisites**: Phases 7–15 — **all Platform routers must exist before T206 runs**.

### Tasks

- [ ] T206 **[Gate B — final coverage]** Exhaustive permission matrix over **every** Platform route
  - **Purpose**: Revision 2 split from the old Gate B task, which illegally depended on Phases 7–13 while blocking Phase 7. Gate B's early proof (T076) covers the Phase-5 surface; this task completes coverage once the full surface exists.
  - **Files**: `backend/tests/security/modules/platform_admin/test_permission_matrix.py`
  - **Deps**: T177, T090, T114, T157, T162, T170, T174, T176, T068, T069
  - **Acceptance**: Parametrised over the **complete** table from `contracts/platform-admin-v1.yaml` — **all 30 permission-guarded operations** (33 total minus the 3 public `/auth/*` operations). For each, holding the required permission succeeds and holding **only** an adjacent permission fails. Every operation in T076's recorded Phase-5 scope is re-covered here, and the test asserts the matrix is **complete** (no contract operation missing, no guarded route absent from the matrix).

- [ ] T207 [P] Security test: cross-tenant IDOR on every tenant-scoped platform route
  - **Files**: `backend/tests/security/modules/platform_admin/test_idor.py`
  - **Deps**: T177
  - **Acceptance**: Substituting another company's id never yields data the caller's permissions don't already allow (FR-9A-212).

- [ ] T208 [P] Security test: mass-assignment protection on every platform write schema
  - **Files**: `backend/tests/security/modules/platform_admin/test_mass_assignment.py`
  - **Deps**: T177
  - **Acceptance**: Extra/unknown fields are rejected or ignored; no privileged field (e.g. `is_active`, role ids) is settable through an unintended endpoint.

- [ ] T209 [P] Security test: lifecycle transition abuse
  - **Files**: `backend/tests/security/modules/platform_admin/test_lifecycle_abuse.py`
  - **Deps**: T102
  - **Acceptance**: Every prohibited transition from spec §23.1 (`suspended→deleted`, `suspended→inactive` direct, `pending_setup→suspended`) is rejected with a **specific** error, not a generic 403.

- [ ] T210 [P] Security test: quota enforcement cannot be bypassed
  - **Files**: `backend/tests/security/modules/platform_admin/test_quota_enforcement.py`
  - **Deps**: T149
  - **Acceptance**: A `hard` quota blocks the action at its declared enforcement point; `soft`/`informational` flag without blocking, exactly as declared.

- [ ] T211 [P] Implement structured operational logging for platform events
  - **Files**: `backend/modules/platform_admin/services/*.py`
  - **Deps**: T177
  - **Acceptance**: Logs platform login, permission denial, suspension/reactivation, entitlement/quota failure, support-access lifecycle, audit-write failure, bootstrap result, degraded measurement — each with correlation/`request_id` and actor id. **Never** logs passwords, hashes, JWTs, refresh tokens, secrets, or tenant business-record contents. Operational logs remain distinct from `PlatformAuditEvent`.

- [ ] T212 [P] Performance: verify pagination and index usage on the heavy list/aggregate paths
  - **Files**: `backend/tests/performance/modules/platform_admin/test_platform_queries.py`
  - **Deps**: T177
  - **Acceptance**: Tenant list, audit filter, usage aggregation and dashboard queries are all paginated/bounded and use the T014/T016/T018 indexes; no N+1 in the tenant-detail or dashboard paths. **No numeric SLA is asserted** (resolved OQ-4) — these are regression guards, not benchmarks.

- [ ] T213 [P] Verify request-scoped memoisation of the company-access and entitlement reads
  - **Purpose**: Both new per-request checks hit the same rows; memoise per request (plan §31) without any cross-request cache.
  - **Files**: `backend/modules/platform_admin/dependencies.py`
  - **Deps**: T122, T083
  - **Acceptance**: One `Company` read and one entitlement resolution per request even when several dependencies need them; **no** process-level cache introduced (no invalidation/consistency concern).

---

## Phase 17: Real-Stack Verification & Epic Closure — **Gate G**

**Objective**: Prove the whole Epic on real PostgreSQL + Docker Compose + a real browser, and prove Epics 1–9 still work.
**Prerequisites**: All previous phases, all gates A–F green.

### Tasks

- [ ] T214 Full real-PostgreSQL migration verification `056 → 061` with rollout applied
  - **Files**: Docker Compose stack
  - **Deps**: T029, T128
  - **Acceptance**: Fresh database → `alembic upgrade head` (ends at `061`, no `062`) → seed capabilities → baseline plan → bulk-assign → verify no tenant lost access; then `downgrade 056` → `upgrade head` clean.

- [ ] T215 Docker Compose live verification: bootstrap → platform login → RBAC
  - **Files**: real stack (`erp-system-api-1`, `erp-system-db-1`, `erp-system-web-1`)
  - **Deps**: T214, T067
  - **Acceptance**: Follows `quickstart.md` §1/§1b/§2/§3 exactly, including the **negative** bootstrap checks (missing config → non-zero exit; repeat → safe no-op) and `platform_administrators` count `0` after migrations alone.

- [ ] T216 Docker Compose live verification: suspension → invalidation → reactivation → refresh-bypass
  - **Files**: real stack
  - **Deps**: T215, T102
  - **Acceptance**: `quickstart.md` §4 end-to-end with a **multi-tenant user**: A denied, B still works on the same token, old access token denied after reactivation, **old refresh token still denied**, genuine login restores, status returns to the pre-suspension value (verified for both `active` and `inactive` origins).

- [ ] T217 Docker Compose live verification: entitlement downgrade bypass check
  - **Files**: real stack
  - **Deps**: T216, T137
  - **Acceptance**: `quickstart.md` §6a–§6d on the real stack, including the direct-`curl` check proving the frontend is not the security boundary and that the stored toggle is never rewritten.

- [ ] T218 Docker Compose live verification: overrides, quotas, usage, audit, support access
  - **Files**: real stack
  - **Deps**: T217, T166, T157
  - **Acceptance**: `quickstart.md` §7 support boundary; override grant/expiry; quota states; audit filtering — all against real Postgres.

- [ ] T219 Playwright: Platform Admin happy path
  - **Purpose**: Follows this project's established live-browser methodology (Epics 7–9).
  - **Files**: verification script under the session scratchpad
  - **Deps**: T218, T204
  - **Acceptance**: bootstrap owner → login → dashboard → tenant list → tenant detail → plan/subscription → entitlement action → audit shows the action. **Zero unexpected browser console errors.**

- [ ] T220 Playwright: suspension flow in the browser
  - **Files**: verification script
  - **Deps**: T219
  - **Acceptance**: tenant user logged in → platform admin suspends → tenant request denied → reactivate → old access token denied → old refresh used → new access token **still denied** → genuine login → access restored. Zero unexpected console errors.

- [ ] T221 Playwright: multi-tenant and support flows
  - **Files**: verification script
  - **Deps**: T220
  - **Acceptance**: user in A and B → suspend A → A denied, B fully functional; support grant → administrative context visible, business records unavailable → revoke → access ends. Zero unexpected console errors.

- [ ] T222 [P] **[Gate G]** Regression: Auth, Companies, Users & Roles
  - **Files**: existing `backend/tests/` suites
  - **Deps**: T214
  - **Acceptance**: Tenant login, refresh, company switching and existing RBAC all unaffected by T083/T084.

- [ ] T223 [P] **[Gate G]** Regression: Inventory, Purchase, Sales
  - **Files**: existing suites + live smoke
  - **Deps**: T214
  - **Acceptance**: Full suites green; feature toggles work for owner/admin; the new entitlement mount denies nothing for baseline-plan tenants.

- [ ] T224 [P] **[Gate G]** Regression: Accounting and CRM
  - **Files**: existing suites + live smoke
  - **Deps**: T214
  - **Acceptance**: Accounting's and CRM's existing gates behave identically to the Phase 1 baseline; the CRM happy path (lead → qualify → convert → customer/opportunity → activity) still passes end-to-end.

- [ ] T225 **[Gate G]** Gate G sign-off and Epic closure audit
  - **Deps**: T214–T224
  - **Acceptance**: All gates A–G green; the Final Completeness Audit below fully ticked; every deviation or deferred item explicitly recorded — never silently closed.

---

## Task Summary

| Phase | Tasks | `[P]` | Focus |
|---|---|---|---|
| 1 | T001–T009 (9) | 7 | Preflight / drift detection |
| 2 | T010–T031 (22) | 5 | Migrations 057–061 + **Gate A** |
| 3 | T032–T044 (13) | 3 | Domain + **audit foundation** + Platform identity |
| 4 | T045–T059 (15) | 4 | Platform auth/session boundary + session-revoking deactivation |
| 5 | T060–T077 (18) | 6 | Platform RBAC + **Administrator/RBAC API routes** + bootstrap + **Gate B** |
| 6 | T078–T081 (4) | 1 | Audit query surface + **Gate E** |
| 7 | T082–T102 (21) | 6 | Tenant lifecycle + access invalidation + 3-way atomicity + **Gate C** |
| 8 | T103–T117 (15) | 6 | Plans / Subscriptions / Capabilities / **quota foundation** |
| 9 | T118–T137 (20) | 5 | Entitlement resolver + rollout + enforcement + **Gate D** |
| 10 | T138–T144 (7) | 5 | Feature-toggle hardening (3 modules) |
| 11 | T145–T157 (13) | 3 | Overrides / quota admin / usage / AI readiness |
| 12 | T158–T166 (9) | 2 | Support access + **Gate F** |
| 13 | T167–T177 (11) | 3 | Platform operational APIs |
| 14 | T178–T187 (10) | 3 | Frontend foundation (clients, contexts) |
| 15 | T188–T205 (18) | 16 | Platform frontend shell + 14 pages + route-guard tests |
| 16 | T206–T213 (8) | 7 | Exhaustive permission matrix + security / observability |
| 17 | T214–T225 (12) | 3 | Real-stack verification + **Gate G** |
| **Total** | **225** | **85** | **17 phases, 7 gates** |

---

## Dependency Graph (phase level)

```
Phase 1 (preflight)
   └─> Phase 2 (migrations) ── Gate A
          └─> Phase 3 (domain + AUDIT FOUNDATION + identity)
                 └─> Phase 4 (auth/session + session-revoking deactivation)
                        └─> Phase 5 (RBAC + bootstrap) ── Gate B  [early scope only]
                               └─> Phase 6 (audit query) ── Gate E  [proof on Phase-5 mutation]
                                      └─> Phase 7 (lifecycle + invalidation + 3-way atomicity) ── Gate C
                                             ├─> Phase 8 (plans/subs/capabilities + QUOTA FOUNDATION)
                                             │      └─> Phase 9 (resolver + rollout + enforcement) ── Gate D
                                             │             ├─> Phase 10 (toggle hardening)
                                             │             └─> Phase 11 (overrides/quota admin/usage/AI)
                                             └─> Phase 12 (support access) ── Gate F
                                                    └─> Phase 13 (operational APIs)
                                                           └─> Phase 14 (frontend foundation)
                                                                  └─> Phase 15 (frontend pages)
                                                                         └─> Phase 16 (exhaustive matrix + security)
                                                                                └─> Phase 17 (real stack) ── Gate G
```

**Hard ordering rules**
- Migrations are strictly sequential — never `[P]` across `057`–`061`. **No `062` may be created** (asserted by T029 and T141).
- Audit foundation (T035–T037) precedes every audited mutation.
- `PlatformSessionRepository` (T047) precedes session-revoking deactivation (T054) and every session consumer.
- Gate B (T077) depends only on Phase 1–5 work; its test (T076) covers the 9 operations that genuinely exist by then (auth + T068 + T069). The exhaustive 30-operation matrix is T206 in Phase 16.
- Administrator/RBAC API routes (T068, T069) precede both Gate B's test and their Phase-15 frontend consumers.
- `/platform-admin/login` lives in the **public `(platform-auth)` group** (T190) and must never be placed inside the protected `(platform-admin)` group, whose layout (T188) redirects — that arrangement would loop.
- Gate E (T081) depends only on Phase 1–6 work; the tenant-suspension 3-way proof is T101 inside Phase 7 under Gate C.
- Quota foundation (T107–T108) precedes both the downgrade check (T113) and the baseline plan (T125).
- Entitlement **enforcement** (T129–T133) must not activate before rollout mapping is verified (T128).
- Frontend pages must not start before their APIs exist (Phase 13 → 14 → 15).
- Gate failures block the next phase entirely.

---

## Parallel Execution Examples

```
Phase 1:  T002, T003, T004, T005, T006, T007, T008 in parallel (all read-only, different files)
Phase 2:  T024, T025, T026 in parallel (independent test cases, same target migration)
Phase 5:  T070, T071, T072, T073, T074 in parallel (independent bootstrap test cases)
Phase 9:  T130, T131, T132 in parallel (three independent router mounts after T129 sets the pattern)
Phase 15: T191–T203 in parallel (13 independent page files, once T189 shell exists)
          T204, T205 in parallel (shell-state tests vs route-guard tests — different files)
Phase 16: T207–T213 in parallel (independent test/observability files, after T177)
Phase 17: T222, T223, T224 in parallel (independent existing suites)
```

---

## Requirement Traceability Matrix

| Requirement | Implementation | Verification |
|---|---|---|
| US-1 platform overview | T171–T174, T191 | T175, T219 |
| US-2 tenant search/inspect | T167, T168, T192, T193 | T177, T207, T219 |
| US-3 tenant lifecycle | T088–T090, T193 | T091–T094, T209, T216, T220 |
| US-4 manage plans | T103, T111, T114, T194 | T115, T177 |
| US-5 subscriptions | T106, T112, T113, T195 | T116, T117, T217 |
| US-6 entitlements/limits | T120, T145–T147, T196 | T121, T148, T134–T136 |
| US-7 Platform Administrator management (API) | T040, T054, **T068** | T059, T076, T177, T206 |
| US-7 Platform RBAC (services + API) | T060–T066, **T069** | T075, T076, T177, T206 |
| US-7 Platform Admin/Roles frontend | T198 (admins), T199 (roles) — both via `platformApiClient` | T204, T205 |
| BR-9A-011 session-revoking deactivation (API path) | T054, **T068** (`PATCH /administrators/{adminId}`) | T059 |
| BR-9A-012 self-escalation (API path) | T065, **T069** (`POST /administrators/{adminId}/roles`) | T075 |
| Platform login / route guard | T183, T188 (protected shell), T190 (public `(platform-auth)` group) | **T205** (tests A–E) |
| Tenant vs Platform auth separation | T048, T052, T176–T179 | T055, T056, T180, T181, **T205 case D** |
| US-8 audit review | T035–T037, T078, T170, T200 | T044, T079, T080, T101, T219 |
| US-9 support access | T158–T162, T202 | T163–T165, T221 |
| US-10 usage/quota | T107, T108, T149–T153, T197, T201 | T109, T153, T210, T212, T218 |
| US-11 operational health | T174, T203 | T175 |
| US-12 AI usage/credits | T154, T155, T201 | T156 |
| FR-9A-017/018/222 auth freshness | T082–T084, T088, T089 | T095–T100, T216, T220 |
| FR-9A-036 bootstrap | T067 | T070–T074, T215 |
| FR-9A-165/166 downgrade conflict | T113 | T117, T217 |
| FR-9A-183–186 toggle hardening | T138–T141 | T142–T144 |
| FR-9A-204 audit fail-closed | T036, T037 | T079 (foundation), **T101 (full 3-way)** |
| BR-9A-001/002/003 trust boundary | T038, T048, T052 | T043, T055, T056 |
| BR-9A-011 session-revoking deactivation | T054 | T059 |
| BR-9A-012 self-escalation | T065 | T075 |
| BR-9A-021 support boundary | T162 | T163 |
| BR-9A-031 bootstrap safety | T067 | T071–T074 |
| BR-9A-032 suspension invalidation | T082, T088 | T095–T100 |
| BR-9A-034/035/036 tenant context | T184, T186 | T187, T100 |
| SC-1 suspend/reactivate audited | T088–T090 | T091–T094 |
| SC-2 least-privilege bundle | T062, T064 | T076, T206 |
| SC-3 deterministic entitlement | T120 | T121, T134–T136 |
| SC-4 attributable privileged actions | T037 | T079, T101, T170 |
| SC-5 no business records in detail view | T168 | T163, T177 |
| SC-6 tenant session cannot reach platform | T052 | T055 (primary), T056, T205 case D |
| SC-7 degraded dependency safety | T172, T174 | T175 |
| SC-8 support requires reason + time bound | T159 | T165 |
| SC-9 no second tenant-context source | T184, T186 | T187 |
| ADR-12 migration preflight | T012, T013 | T024–T028 |

---

## Phase Gate Checklist

- [ ] **Gate A** (T031, Phase 2) — migration safety on real PostgreSQL
- [ ] **Gate B** (T077, Phase 5) — platform trust boundary + RBAC on the Phase-5 route surface
- [ ] **Gate E** (T081, Phase 6) — audit atomicity on a real Phase-5 privileged mutation
- [ ] **Gate C** (T102, Phase 7) — lifecycle, authentication freshness incl. refresh bypass, **and the 3-way state+audit+outbox atomicity proof (T101)**
- [ ] **Gate D** (T137, Phase 9) — entitlement ceiling at point of use, all 5 modules
- [ ] **Gate F** (T166, Phase 12) — support security boundary
- [ ] **Gate G** (T225, Phase 17) — real-stack regression across Epics 1–9
- [ ] **Gate B final coverage** (T206, Phase 16) — exhaustive route-permission matrix once all routers exist

---

## Final Completeness Audit

- [ ] All 12 user stories have implementation + verification coverage
- [ ] Migrations `057`–`061` exist; **no `062`**; bootstrap is not a migration; T029 and T141 both assert this
- [ ] Migration `057` suspended-row preflight is explicit and tested (T012, T025, T026)
- [ ] `PlatformAdministrator`, `PlatformSession`, `PlatformRefreshToken` tasks exist
- [ ] BR-9A-011 session-revoking deactivation is implemented (T054) and proved at API level (T059)
- [ ] Platform RBAC with permission-code enforcement exists; last-owner and self-escalation protected
- [ ] Bootstrap tasks + all 5 negative cases exist
- [ ] Audit foundation precedes every audited mutation; fail-closed proved twice (T079 foundation, T101 full 3-way)
- [ ] Suspension and reactivation are separate tasks; reactivation restores the recorded status
- [ ] Authentication freshness uses `Session.created_at`; **no runtime authorization uses token `iat`**
- [ ] Old-refresh-token bypass test (T096) exists and is a Gate C blocker
- [ ] Multi-tenant A/B test (T098) and multi-device test (T099) exist
- [ ] Plans, Subscriptions, Capability registry, quota foundation and entitlement resolver tasks exist, each exactly once
- [ ] Point-of-use enforcement covers Inventory, Purchase, Sales, Accounting, CRM
- [ ] Feature-toggle hardening covers exactly Inventory, Sales, Purchase; Accounting/CRM not rewritten
- [ ] Canonical tenant-context accessor and `PlatformSelectedTenantContext` tasks exist
- [ ] Override, quota-admin, usage tasks exist; AI readiness remains provider-neutral
- [ ] Support access has negative business-record tests
- [ ] **Platform Administrator backend API routes exist** (T068 — `GET/POST /administrators`, `PATCH /administrators/{adminId}`)
- [ ] **Platform RBAC backend API routes exist** (T069 — `GET/POST /roles`, `POST /administrators/{adminId}/roles`)
- [ ] **Frontend Administrators page consumes the Platform API** via `platformApiClient` (T198 → T068, T179), never a Python service
- [ ] **Frontend Roles page consumes the Platform API** via `platformApiClient` (T199 → T069, T179), never a Python service
- [ ] **Gate B (T076) tests only real, existing Phase-5 routes** — the 9 operations from auth + T068 + T069
- [ ] **T206 covers the complete final route table** — all 30 permission-guarded operations, completeness asserted
- [ ] All **28 contract paths / 33 operations** have explicit implementation coverage (T177) and permission coverage (T206); no undeclared CRUD invented
- [ ] **`/platform-admin/login` is structurally outside the protected layout** — defined in the `(platform-auth)` group (T190), mirroring the repo's existing `(auth)` vs `(protected)` split
- [ ] **Unauthenticated login page has a no-redirect-loop test** (T205 case A)
- [ ] **Protected-route redirect test exists** (T205 case B); authenticated render (case C); logout (case E)
- [ ] **Tenant auth cannot satisfy Platform route protection** (T205 case D, plus backend T055/T056)
- [ ] Tenant/Platform client separation has crossover tests (T182, T183)
- [ ] Platform frontend has a shell + 14 page tasks; dashboard degraded states covered
- [ ] PostgreSQL, Docker Compose and Playwright verification all exist
- [ ] Existing ERP regression verification exists for all 8 completed modules
- [ ] No out-of-scope task introduced (see below)
- [ ] No unresolved architectural decision deferred into `/sp.implement`
- [ ] **Dependency graph is acyclic; every gate depends only on tasks executable before it**

---

## Out of Scope (guardrail — no tasks generated)

CRM business-logic redesign; Installments; Reports; payment gateway; SaaS invoicing; tax; any AI provider integration (OpenAI/Anthropic/Gemini/OpenClaw); unrestricted impersonation; tenant business-record support browsing; mobile apps; microservices; Kubernetes; Redis; broad auth-system rewrite; broad `CompanyContext` refactor; global logout redesign.

**Recorded as notes, not tasks** (plan §41, spec Risks #3/#4):
- `get_current_user()` never checks `Session.is_revoked`, so tenant logout does not invalidate an in-flight access token. Pre-existing; **not** required for Epic 9A correctness under ADR-6; deliberately untouched.
- The dead `/admin/companies` surface (403-always guard + frontend calling `listCompanies()` instead of `listAdminCompanies()`). Epic 9A builds a new surface instead and cannot inherit the bug.
- `SUPER_ADMIN` vs `super_admin` casing inconsistency in `purchase/router.py`.
- `.specify/scripts/bash/{setup-plan,check-prerequisites}.sh` branch regex rejects `009a-`.

---

## Notes on Task Completion

A task is complete only when its **behaviour** is verified — not when the file exists, the route responds once, the migration runs once, or the test file was created. Security-sensitive tasks require their negative tests to pass. Do not proceed past a failed gate.
