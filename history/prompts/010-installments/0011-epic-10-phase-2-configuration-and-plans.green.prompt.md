---
id: 0011
title: Epic 10 Phase 2 configuration and plans
stage: green
date: 2026-08-25
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: /sp.implement
labels: [installments, epic-10, phase-2, configuration, plan-templates, feature-flag, entitlement, capability-registration, rbac]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/installments/models/__init__.py
 - backend/modules/installments/models/configuration.py
 - backend/modules/installments/models/plan_template.py
 - backend/modules/installments/models/feature_flag.py
 - backend/modules/installments/models/sequence.py
 - backend/modules/installments/models/audit.py
 - backend/modules/installments/repositories/__init__.py
 - backend/modules/installments/repositories/configuration.py
 - backend/modules/installments/repositories/plan_template.py
 - backend/modules/installments/repositories/feature_flag.py
 - backend/modules/installments/repositories/sequence.py
 - backend/modules/installments/repositories/audit.py
 - backend/modules/installments/services/__init__.py
 - backend/modules/installments/services/configuration_service.py
 - backend/modules/installments/services/plan_template_service.py
 - backend/modules/installments/services/feature_flag_service.py
 - backend/modules/installments/services/audit_service.py
 - backend/modules/installments/services/permission_check.py
 - backend/modules/installments/schemas/configuration.py
 - backend/modules/installments/schemas/plan_template.py
 - backend/modules/installments/schemas/base.py
 - backend/modules/installments/dependencies.py
 - backend/modules/installments/router.py
 - backend/modules/platform_admin/services/module_enablement.py
 - backend/modules/platform_admin/services/capability_seed_service.py
 - backend/tests/integration/repositories/installments/test_configuration_repository.py
 - backend/tests/unit/modules/installments/test_plan_template_service.py
 - backend/tests/integration/api/v1/installments/test_entitlement_registration.py
 - specs/010-installments/tasks.md
tests:
 - backend/tests/integration/repositories/installments/test_configuration_repository.py (real Postgres) — 7 passed
 - backend/tests/unit/modules/installments/test_plan_template_service.py (SQLite) — 5 passed
 - backend/tests/integration/api/v1/installments/test_entitlement_registration.py (SQLite, real PlatformEntitlementService) — 4 passed
 - Full installments + platform_admin regression (unit/integration) — 129 passed
 - CRM regression (module_enablement.py/capability_seed_service.py touched) — 126 passed, 1 environment-flaky (JWT token-expiry race under full-suite load; isolated re-run 5/5 passed)
 - ruff check (all new/modified files) — all checks passed
 - Manual live-HTTP smoke test (throwaway, not committed): full request/response cycle for GET/PUT /config, GET /status, POST/GET/deactivate /plans — all correct status codes and payload shapes
 - Manual Postgres column-drift check (Phase 0 follow-through): zero drift confirmed between all 5 new ORM models and the live migrated schema
---

## Prompt

# Epic 10 — Installments
# MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT

Implement, verify, audit, and close ONLY the following phase of Epic 10.

Phase Number: `2`
Phase Name: `Configuration & Plans`
Task Range: `T021 to T042`

Feature Branch: 010-installments

[Full 47-section master prompt supplied verbatim by the user — identical
structure/rules to the Phase 0/Phase 1 closure prompts (see PHR 0009,
0010): primary objective and no-correction-pass standard; strict phase
scope (implement only T021-T042, no Contract/Schedule/Idempotency
models or Phase 3+ artifacts pre-created); authoritative sources and
authority order; branch/working-tree safety; pre-implementation task
audit; repository-reality check before new abstractions; per-task
IMPLEMENT/TEST/VERIFY/NEGATIVE-PATH/DEPENDENCY-RECHECK discipline;
architecture freeze — N/A at the configuration/plan-template/entitlement-
registration level this phase touches (no financial workflows, no
lifecycle transitions, no idempotency-protected commands exist yet);
financial-transaction/idempotency/Phase-5.5/Phase-6 hard-gate rules —
N/A; database & migration hard rules — N/A, no new migrations this
phase (reuses 062/063 from Phase 0 exactly); API contract lock (explicit
instruction to inspect
`specs/010-installments/contracts/installments-api.yaml` before
implementation and compare OpenAPI↔router↔schema↔service↔permission↔
entitlement↔tests); data-model↔implementation audit; frontend rules —
N/A; full testing pyramid; failure-injection/atomicity proof — N/A;
pre-existing-failure policy; real PostgreSQL/Docker verification
requirement; live HTTP/browser verification; requirement traceability
review; mandatory self-review and adversarial-completeness pass; full
diff review before closure; task-checkbox truthfulness rule; exact
phase Exit Condition proof requirement; hard-gate rule — N/A; regression
verification; no-correction-pass final contradiction search; PHR
requirement; pre-commit check; commit policy; post-commit verification;
the exhaustive Required Final Report template (sections A-S); and the
final stop rule.]

## Response snapshot

Verified branch (`010-installments`) and working tree matched the exact
pre-existing baseline confirmed at Phase 0/1's closures. Confirmed both
prior commits (`2607731`, `70a1736`) present in history. Read tasks.md
T021-T042, plan.md §7.1/§7.2 (table field lists, already used in Phase
0), §15.2/§15.4 (`InstallmentAccessPolicy`/entitlement registration —
confirmed via `grep` that `InstallmentAccessPolicy` itself is created in
**T188 (Phase 11)**, not this phase, so Phase 2's endpoints correctly
omit entitlement gating entirely and only enforce RBAC permissions —
avoiding the "pre-create future lifecycle workflow" trap), §16.1 (16-
permission catalogue, cross-checked against `installments-api.yaml`'s
per-operation `x-permission`/`x-operation-class` annotations), §17
(audit architecture), §30.1 (already-implemented migration 071 grant
table, used again as ground truth).

**Contract-vs-task-text reconciliations (documented, not silent)**:
inspecting `contracts/installments-api.yaml` (Section 25's explicit API
Contract Lock instruction) surfaced two mismatches between the
authoritative OpenAPI contract and tasks.md's looser prose:
1. T036 describes a separate `GET/PUT .../config/branches/{branchId}`
   path; the OpenAPI contract declares only one merged `/config` path
   whose GET/PUT summaries say "(company + branch override)"/"(or
   branch-override)". Resolved by implementing the single `/config`
   endpoint parameterized by an optional `branch_id` query
   parameter (GET) / request-body field (PUT) — same capability, no
   undeclared route invented, matching Section 25's explicit "do not
   invent undeclared CRUD."
2. The OpenAPI contract's `/installments/status`,
   `/installments/enable`, `/installments/disable` paths, taken
   completely literally against the declared server base
   (`/api/v1/companies/{company_id}/installments`), would double the
   module-name segment. Cross-checked against CRM's actual, currently
   *working* `admin_router` mounting
   (`api/v1/router.py`: `include_router(crm_admin_router,
   prefix="/companies/{company_id}/crm", ...)` with routes declared as
   bare `/status`/`/enable`/`/disable`) — confirmed the doubled segment
   is an authoring artifact in the YAML's own self-described
   "Planning-Stage Contract Sketch... Not an implementation artifact"
   status, not an intentional path shape. Implemented `admin_router`
   with bare `/status`/`/enable`/`/disable` routes, exactly mirroring
   CRM's proven, currently-mounted convention — verified end-to-end via
   a temporary FastAPI app + OpenAPI generation, confirming the correct,
   non-doubled resolved paths.
Per T037's OpenAPI table (not tasks.md's one-line summary), implemented
per-operation permission/class exactly as declared: `GET /plans` uses
`installments.contract.view`/READ (not `plan.manage`/ORIGINATION as
tasks.md's prose implies) while POST/PATCH/deactivate correctly use
`installments.plan.manage`/ORIGINATION.

Researched exact repository precedents before writing anything:
`BaseRepository.create()`/`.update()`'s commit-per-call behavior (core
insight carried into T038's audit repository, which must NOT use
`BaseRepository` since it needs flush-only semantics); `CrmFeatureFlag`/
`CrmFeatureFlagRepository`/`CrmFeatureFlagService` as T023/T027/T031's
exact mirror targets; `AccountingAuditLog`/`AccountingAuditLogRepository`/
`AuditLogService` (plain `Base`, flush-only `create()`, "caller MUST
commit" docstring) as T038's exact precedent — confirmed via direct
comparison this is the *same* shape my Phase 0 migration 068 already
committed to; `platform_admin/services/module_enablement.py`'s
`ModuleEnablementProvider` Protocol + `CrmModuleEnablementProvider` +
`get_module_enablement_provider()` factory as T032's exact mirror
target; `CapabilitySeedService.MODULE_CAPABILITY_CATALOGUE` as T033's
one-line addition point; `user_has_accounting_permission()` as T034's
exact mirror target; `SalesSequenceService`'s `SELECT...FOR UPDATE`
locked-increment pattern (already researched in Phase 0) reused
verbatim for T028; `modules.users_roles.dependencies.require_rank` +
`ADMIN_RANK` (not CRM's older, TODO-marked `require_admin_or_above()`)
as the literal mechanism T042 names ("rank-gated (ADMIN_RANK)");
confirmed via `grep` that CRM/Accounting both independently duplicate
their permission catalogues between their own module-local
`constants.py` and `users_roles/constants.py` rather than cross-
importing — not directly needed this phase (T015/T016 already done in
Phase 1) but re-confirmed the module boundary discipline before writing
`platform_admin`'s new cross-module imports for T032.

Implemented all 22 tasks: **T021-T024** (4 SQLAlchemy models, column-
for-column matching migrations 062/063/068 exactly — verified via live
Postgres introspection, zero drift across all 5 tables); **T025-T028**
(4 repositories — `InstallmentConfigurationRepository.get_effective_config()`
resolves branch-override-then-company-fallback; `InstallmentSequenceRepository.generate_next_number()`
uses `SELECT...FOR UPDATE`); **T029-T031** (3 services — configuration
validation for `min_term<=max_term` and the down-payment-field
mutual-exclusivity rule; plan-template create/edit/deactivate with
unique-name-per-company; feature-flag `is_enabled()`/`enable()`/
`disable()`); **T032** (`InstallmentsModuleEnablementProvider` added to
`module_enablement.py`, wired into the factory); **T033** (capability
catalogue entry added — the underlying `capabilities` row already
existed from migration 070, this just adds the idempotent reseed-service
catalogue entry for consistency); **T034** (`user_has_installments_permission()`);
**T035** (Configuration/PlanTemplate Pydantic schemas);
**T036/T037/T042** (all three endpoint groups in `router.py`, per-
operation permission/class exactly matching the OpenAPI contract, none
yet mounted into `api/v1/router.py` — that's T190/Phase 11, mirroring
CRM's own multi-phase router-accumulation-then-mount precedent exactly);
**T038** (`InstallmentAuditLog`/`InstallmentAuditLogRepository`/
`InstallmentAuditService`, flush-only, matching `AuditLogService`
verbatim).

**Defect found and fixed during T040's test-writing** (not merely
worked around): `InstallmentPlanTemplate.is_active`/`requires_approval`
rely purely on `server_default="true"/"false"` (a raw SQL-text
server-side default) with no Python-side default. Diagnosed precisely:
under SQLite, this raw string server_default is stored as the literal
TEXT `'true'`, not integer `1` — so a row created without explicitly
setting `is_active` reads back as Python `True` (the ORM's `Boolean`
type decorator coerces on the way out) but silently fails a subsequent
`.where(is_active == True)` filter (comparing stored TEXT `'true'`
against a bound `1`), returning zero rows despite the row genuinely
being active. Confirmed via a byte-level `typeof()` inspection that this
is a real, reproducible SQLite-specific gap — and confirmed via `grep`
that `CrmPipelineService.create()` already independently discovered and
mitigates the *identical* latent defect class in `Pipeline.is_active`
(same raw-string `server_default="true"` pattern) by *always* passing
`is_active: bool = True` explicitly at the Python/service layer, never
relying on the server_default for anything queried in the same process.
Fixed `InstallmentPlanTemplateService.create()`/
`InstallmentConfigurationService.upsert_config()` to `setdefault()`
every server_default-backed field explicitly, matching this established,
proven mitigation pattern exactly (Postgres would never have exposed
this — the defect is real but SQLite-test-environment-specific; the fix
makes both dialects' behavior identical and explicit rather than
dialect-dependent).

Verified acceptance for every task with runtime evidence: T039's 7
tests ran against a real, freshly-migrated (to head 071) throwaway
Postgres database (reusing Phase 0's `pg_test_db`/`alembic_upgrade`/
`db_engine` fixtures from `tests/integration/migrations/conftest.py`,
rather than duplicating that infrastructure), proving both partial
unique indexes' exact behavior (company-default singleton, branch-
override coexistence, per-branch duplicate rejection) and tenant
isolation for both new tables. T040's 5 tests proved deactivation
excludes a template from `list_active()` while leaving its own row
(name/terms) untouched, and documented the actual invariant that
deactivation ≠ deletion (a deactivated name still blocks reuse — only
soft-delete frees it). T041's 4 tests — the strongest single piece of
Phase 2 evidence — dynamically exercised the **real**,
unmodified `PlatformEntitlementService.resolve_effective_entitlement()`
end-to-end (capability seeding → baseline-plan creation → bulk-assign
→ toggle on/off → re-resolve), proving T032/T033's wiring is genuinely
load-bearing, not inert code: disabled-by-default, enabled-when-toggled,
and immediately reflects a toggle-off (FR-9A-170, never cached).

Beyond the required T039/T040/T041, additionally verified (not required
by tasks.md, but cheap and de-risking): direct Postgres column-drift
comparison for all 5 new ORM models against the live migrated schema
(zero drift); a temporary FastAPI app + `TestClient` end-to-end smoke
run (not committed — throwaway) exercising the actual HTTP request/
response cycle for every Phase 2 endpoint (GET/PUT `/config`, GET
`/status`, POST/GET/deactivate `/plans`) with the real global
`ApplicationException` handler registered, confirming correct status
codes (404 before configuration exists, 200/201 on success) and
response payload shapes; and confirmed the resolved OpenAPI paths for
`admin_router` are correctly non-doubled.

Ran the full pre-existing Installments + `platform_admin` regression
(129 passed) since `module_enablement.py`/`capability_seed_service.py`
are widely-shared platform files, plus a full CRM regression (since
`module_enablement.py`'s factory function is CRM's own dependency too)
— 126 passed, 1 failure (`test_flag_on_passes_through[Pipelines-/pipelines]`,
"Token has expired" → 401) that re-ran clean in isolation (5/5 passed)
immediately after; classified as environment-dependent/flaky (a JWT
short-TTL race under full-suite wall-clock load), confirmed unrelated
to this phase's changes by code inspection (neither touched file has
any relation to JWT/token-expiry logic), and documented per Section 30
rather than silently reported as "all green." `ruff check` clean on
every new/modified file after fixing one F401/F811 false-positive pair
in the T039 test file's cross-directory pytest-fixture-reexport pattern
(resolved via `request.getfixturevalue()` instead of a same-named
parameter, plus a `noqa` comment on the necessary re-export import).

Full diff review (`git status`/`git diff --stat`) confirmed only
Phase-2-scoped files changed: the new `models/`/`repositories/`/
`services/` trees plus 2 new schema files under
`backend/modules/installments/`, the modified `dependencies.py`/
`router.py`/`schemas/base.py` (all populated per this phase's tasks,
previously Phase-1 skeletons), 2 modified shared `platform_admin`
files (the exact 2-line factory registration + 1-line catalogue
addition T032/T033 specify), 3 new test files, and `tasks.md`'s
checkboxes. No `models/contract.py`, `schedule.py`,
`allocation_reference.py`, `late_charge.py`, or `idempotency.py` exist
anywhere in the diff — confirmed no Phase 3+ leakage.

## Outcome

- ✅ Impact: Phase 2 (T021-T042) complete. A test company can have its
  Installments module toggled on/off (proven end-to-end through the
  real, unmodified `PlatformEntitlementService`); effective
  configuration resolves branch-override-then-company-fallback
  correctly (proven against real Postgres); plan templates are
  creatable/deactivatable with unique-name-per-company enforced both at
  the service layer and the DB partial-unique-index backstop; the
  `installments` Capability is registered and resolves correctly
  disabled-by-default, enabled-on-toggle, and immediately reflects
  toggle-off; tenant isolation proven for both new tables against real
  Postgres. A real, SQLite-specific boolean-default defect was found and
  fixed using the codebase's own already-established mitigation pattern
  rather than a novel one.
- 🧪 Tests: T039 — 7 passed (real Postgres). T040 — 5 passed (SQLite).
  T041 — 4 passed (SQLite, real `PlatformEntitlementService`).
  Regression: Installments+platform_admin — 129 passed; CRM — 126
  passed, 1 environment-flaky (documented, unrelated, isolated re-run
  clean). `ruff check` — all checks passed.
- 📁 Files: 23 new files under `backend/modules/installments/`
  (models/repositories/services trees + 2 schema files), 3 populated
  Phase-1-skeleton files, 2 modified shared `platform_admin` files, 3
  new test files, `tasks.md` checkbox update.
- 🔁 Next prompts: Phase 3 (Contract Persistence, T043-T056) —
  `InstallmentContract` aggregate root, tenant-scoped numbering, the
  one-contract-per-obligation invariant — not started, per the master
  prompt's explicit stop rule.
- 🧠 Reflection: The OpenAPI contract, despite self-describing as a
  "planning-stage sketch," was the correct authority to resolve two
  real tasks.md-prose imprecisions (the branch-config path shape and the
  admin-router path segment) — both resolved by cross-checking against
  an *already-proven-working* precedent (CRM's actual mounted routes)
  rather than guessing, which is the right general technique whenever a
  planning artifact's literal text conflicts with another planning
  artifact's more precise structure: find which one already has a
  working, tested analogue elsewhere in the codebase, and match that.
  The SQLite server_default defect is a good example of why "the same
  defect class was already discovered and mitigated elsewhere" is worth
  actively searching for (via `grep` on the suspect pattern) before
  concluding a bug is genuinely novel — CRM's `PipelineService` had
  already paid this exact tax.

## Evaluation notes (flywheel)

- Failure modes observed: `InstallmentPlanTemplate.is_active`/
  `requires_approval` server_default-only booleans silently broke a
  boolean-filtered query under SQLite (text `'true'` vs. bound `1`) —
  root-caused and fixed via the existing `CrmPipelineService`-established
  mitigation (explicit Python-side defaults at the service layer),
  applied to both affected services for consistency.
- Graders run and results (PASS/FAIL): T039/T040/T041 — PASS (16/16);
  full regression — PASS (129/129 Installments+platform_admin, 126/127
  CRM with the 1 failure independently reclassified flaky and
  reverified); ruff — PASS.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): when a new module
  introduces a `server_default`-only boolean column, proactively grep
  sibling modules for the identical raw-string server_default pattern
  and adopt whatever mitigation they already use, rather than
  discovering the gap independently via a failing test each time.
