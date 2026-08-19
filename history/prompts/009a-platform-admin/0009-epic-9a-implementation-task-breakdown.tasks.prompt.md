---
id: 0009
title: Epic 9A implementation task breakdown
stage: tasks
date: 2026-08-19
surface: agent
model: claude-opus-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.tasks
labels: ["platform-admin", "tasks", "planning"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/009a-platform-admin/tasks.md
 - history/prompts/009a-platform-admin/0009-epic-9a-implementation-task-breakdown.tasks.prompt.md
tests:
 - none (task-generation phase; no code, migrations, or tests written)
---

## Prompt

# Epic 9A — Platform Administration / Super Admin
## `/sp.tasks` — Full & Final Task Generation Prompt

[61-section task-generation brief. Key constraints: `/sp.tasks` phase only; do not reopen approved product decisions, redesign architecture, start implementation, or modify constitution/spec/plan. Mandatory source-of-truth review in authority order Constitution → Spec → Plan/artifacts → repository reality, stopping and reporting on any genuine contradiction rather than silently resolving it. Git baseline verification (branch `009a-platform-admin`, clean tree, HEAD contains `fd3d55e`, Constitution v1.2.1, no pre-existing tasks.md). §4 enumerates 12 finalized architecture decisions that must be preserved verbatim — Platform identity, session boundary, RBAC, suspension/reactivation with `pre_suspension_status`, authentication freshness via `Session.created_at` (explicitly NOT token `iat`), cross-tenant session safety, Plan-entitlement ceiling with point-of-use enforcement, out-of-band bootstrap, tenant-context separation, tenant/platform HTTP client separation, fail-closed audit, and no new infrastructure. §§5–58 specify task format, dependency ordering, per-domain task requirements (migrations 057–061 with the mandatory 057 suspended-row preflight, RBAC, bootstrap, audit, lifecycle, entitlements, quotas, usage, AI readiness, support access, frontend, tests), 7 critical gates A–G, parallelization rules, and a 13+ phase structure. §59 is a 42-item completeness audit; §60 restricts writable files to tasks.md + the PHR; §61 defines a 25-item final report. Full verbatim text in the conversation transcript for this turn.]

## Response snapshot

**Baseline verified first**: branch `009a-platform-admin`, working tree clean, HEAD is `fd3d55e`, `merge-base(009-crm, HEAD)` equals the `009-crm` tip (Epic 9A still descends from completed Epic 9), Constitution v1.2.1, no pre-existing `tasks.md`. `check-prerequisites.sh` failed on the same branch-regex gap as `setup-plan.sh` (`^[0-9]{3}-` rejects `009a-`) — noted in tasks.md as a pre-existing tooling issue and paths resolved manually; the script's own `find_feature_dir_by_prefix()` fallback resolves correctly, so this is cosmetic.

**Convention study**: read `specs/009-crm/tasks.md` (193 tasks, 10 phases) to match the established repo format rather than the generic SpecKit template — per-task Purpose/Files/Deps/Acceptance bullets, a User Story Map, phase objectives, dependency graph, parallel-execution examples, traceability matrix, and a phase-gate checklist.

**Generated `specs/009a-platform-admin/tasks.md`**: 217 tasks (T001–T217, verified sequential and unique via script), 17 phases, 86 `[P]`, 7 critical gates. Structure: preflight/drift detection → migrations 057–061 (Gate A) → domain + Platform identity → auth/session boundary → RBAC + bootstrap (Gate B) → fail-closed audit (Gate E) → tenant lifecycle + company-scoped access invalidation (Gate C) → plans/subscriptions/capabilities → entitlement resolver + staged rollout + point-of-use enforcement (Gate D) → feature-toggle hardening → overrides/quotas/usage/AI → support access (Gate F) → operational APIs → frontend foundation → frontend shell + 14 pages → security/observability → real-stack verification (Gate G).

Decisions preserved exactly as finalized, with tasks written to make regression detectable: T092 is an explicit refresh-bypass guard that fails if anyone re-keys the freshness check to `iat`; T012 encodes the migration-057 suspended-row preflight including the "never backfill, never weaken the constraint" prohibitions; T120 gates enforcement activation on verified rollout mapping so existing tenants cannot lose access; T125 mounts the CRM entitlement check *in front of* the preserved `require_crm_enabled` without modifying any CRM file; T072 specifies flush-only/never-commit for the audit repository; T062 keeps bootstrap out of Alembic with a defined exit-code contract.

**Validation performed**: task-ID sequence (217, no gaps/duplicates), per-phase counts, format compliance, out-of-scope leakage scan across task lines (Redis/K8s/microservices/AI providers/payment/impersonation — none), `iat`-as-authorization scan (only substring false positives in "remediation"/"initiation"), migration-062 scan (only task ID T062 and requirement FR-9A-062). Found and corrected one real error: the summary claimed 78 `[P]` tasks when the actual count is 86.

**No contradictions found** between Constitution, spec, plan, artifacts and repository reality — so no stop-and-report was triggered.

## Outcome

- ✅ Impact: Epic 9A now has an implementation-ready, dependency-aware task breakdown in which every finalized architectural decision is encoded as a concrete task with real file paths, and every security-critical guarantee has a named blocking test. The 7 gates make it impossible to proceed past an unproven trust boundary, migration hazard, entitlement bypass, audit atomicity failure, or support-boundary breach.
- 🧪 Tests: N/A (task-generation phase). The plan mandates 86 test/verification tasks including the Gate C authentication-freshness set (A–F), Gate D entitlement matrix across all five modules, Gate E forced-audit-failure rollback, Gate F support-boundary negative tests, and Gate G regression across all 8 completed modules.
- 📁 Files: `specs/009a-platform-admin/tasks.md` (1529 lines, new) + this PHR. Nothing else created or modified.
- 🔁 Next prompts: `/sp.implement` (not started, per instruction) after review of tasks.md.
- 🧠 Reflection: The highest-value work here was making the previously-corrected design decisions *self-defending* — T092 and T127 exist specifically to fail if a future implementer "simplifies" back to the flawed `iat` comparison or mutation-only entitlement check. A task list that merely restated the plan would have left both regressions undetectable.

## Evaluation notes (flywheel)

- Failure modes observed: one arithmetic error in the summary table (`[P]` count 78 vs actual 86), caught by scripted validation rather than by reading — reinforcing that generated counts should always be machine-verified against the generated document, never hand-tallied.
- Graders run and results (PASS/FAIL): task-ID sequence PASS (217 sequential, unique); per-phase counts PASS (matched summary after correction); format compliance PASS; out-of-scope leakage PASS (zero); `iat`/`062` contradiction scan PASS (false positives only).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
