---
id: 0010
title: Epic 11 Phase 0 foundation implementation
stage: green
date: 2026-09-12
surface: agent
model: claude-sonnet-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: /sp.implement
labels: ["epic-11", "reports-analytics", "phase-0", "foundation"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/reports/__init__.py
 - backend/modules/reports/constants.py
 - backend/modules/reports/exceptions.py
 - backend/modules/reports/router.py
 - backend/modules/reports/dependencies.py
 - backend/modules/reports/models/__init__.py
 - backend/modules/reports/models/feature_flag.py
 - backend/modules/reports/repositories/__init__.py
 - backend/modules/reports/repositories/feature_flag.py
 - backend/modules/reports/services/__init__.py
 - backend/modules/reports/services/feature_flag_service.py
 - backend/modules/reports/services/permission_check.py
 - backend/modules/reports/services/date_range_service.py
 - backend/modules/reports/services/comparison_service.py
 - backend/modules/reports/services/money_normalization.py
 - backend/modules/reports/services/csv_sanitizer.py
 - backend/modules/reports/services/registry_service.py
 - backend/modules/reports/services/adapters/__init__.py
 - backend/modules/reports/services/adapters/base.py
 - backend/modules/reports/registry/__init__.py
 - backend/modules/reports/registry/definitions.py
 - backend/modules/reports/schemas/__init__.py
 - backend/modules/reports/schemas/common.py
 - backend/modules/reports/metrics/__init__.py
 - backend/migrations/versions/073_reports_foundation.py
 - backend/modules/platform_admin/services/capability_seed_service.py
 - backend/modules/platform_admin/services/module_enablement.py
 - backend/api/v1/router.py
 - backend/modules/users_roles/constants.py
 - backend/tests/unit/modules/reports/ (10 test files)
 - backend/tests/integration/api/v1/reports/test_entitlement_roundtrip.py
 - backend/tests/integration/api/v1/reports/test_router_mount.py
 - backend/tests/unit/modules/users_roles/test_reports_permissions_seed.py
tests:
 - backend/tests/unit/modules/reports/test_date_range_service.py
 - backend/tests/unit/modules/reports/test_comparison_service.py
 - backend/tests/unit/modules/reports/test_money_normalization.py
 - backend/tests/unit/modules/reports/test_csv_sanitizer.py
 - backend/tests/unit/modules/reports/test_base_report_result.py
 - backend/tests/unit/modules/reports/test_registry_service.py
 - backend/tests/unit/modules/reports/test_registry_consistency.py
 - backend/tests/integration/api/v1/reports/test_entitlement_roundtrip.py
 - backend/tests/integration/api/v1/reports/test_router_mount.py
 - backend/tests/unit/modules/users_roles/test_reports_permissions_seed.py
---

## Prompt

# DevSphere ERP SaaS

# Epic 11 — Reports & Analytics

## Compact Reusable Implementation Master Prompt

Implement only the requested Epic 11 phase.

Set:

```text
PHASE_TO_IMPLEMENT = 0
```

Example:

```text
PHASE_TO_IMPLEMENT = 0
```

---

## 1. Authoritative Sources

Before implementation, read:

```text
CLAUDE.md
specs/011-reports-analytics/spec.md
specs/011-reports-analytics/plan.md
specs/011-reports-analytics/tasks.md
specs/011-reports-analytics/research.md
specs/011-reports-analytics/data-model.md
specs/011-reports-analytics/quickstart.md
specs/011-reports-analytics/contracts/reports-api.yaml
```

Treat the final corrected `tasks.md` as the execution contract.

Do not redesign the Epic.

Do not regenerate spec/plan/tasks.

Do not change settled architecture unless a genuine repository contradiction is discovered.

---

## 2. Scope

Implement:

```text
PHASE_TO_IMPLEMENT = <provided phase>
```

Determine the exact task range and gate from the current `tasks.md`.

Implement every task assigned to that phase.

Do not start the next phase.

After the phase gate passes:

```text
STOP.
```

Wait for explicit authorization before continuing.

---

## 3. Prerequisite Check

Before coding:

* inspect `git status`;
* identify current branch;
* verify prerequisite phase gates are complete;
* inspect the actual repository patterns relevant to this phase.

If a prerequisite is incomplete or the approved documents contain a genuine contradiction:

```text
STOP and report it.
```

Do not bypass gates.

---

## 4. Architecture Rules

Preserve all approved DevSphere architecture and Constitution rules.

In particular:

* strict `company_id` tenant isolation;
* RBAC and entitlement checks;
* router → service → repository/domain-service boundaries;
* no business SQL in API handlers;
* no duplication of formulas owned by another module;
* no cross-tenant fallback;
* no Branch authorization invented by Epic 11;
* no implementation of Deferred reports;
* no AI/OpenClaw/LLM/vector/NL-to-SQL work in Epic 11.

Rule:

```text
One Metric → One Authoritative Definition → Many Consumers
```

---

## 5. Type and Financial Safety

Preserve:

```text
mypy . = 0
```

Do not introduce `Any`, unsafe casts, `# type: ignore`, or dynamic dispatch into Reports public/service/adapter contracts unless explicitly approved.

Financial arithmetic stays server-side using `Decimal`.

Do not introduce floating-point financial calculations.

---

## 6. Important Epic 11 Contracts

Do not regress any final approved decisions in `spec.md`, `plan.md`, or `tasks.md`, including:

* `ADAPTER` vs `COMPOSITE` execution;
* Dashboard and Customer 360 dedicated routes;
* Saved View soft-delete and load-time reauthorization;
* Installments servicing-continuity Case A/B rules;
* Purchase 6/6 list reports as real bounded Category A;
* bounded Accounting AR/AP and bank/cash reads;
* GL cursor + limit+1 export handling;
* CSV formula-injection protection;
* XLSX bounded/write-only behavior;
* audit commit must succeed before export file delivery;
* Deferred reports remain unimplemented.

If this prompt and the approved Epic documents differ, follow the approved Epic documents.

---

## 7. Source-Domain Changes

The sanctioned source-domain bounded-read seams are:

```text
T047 — Accounting
T075 — Purchase
T087 — Inventory
```

Keep them additive and narrowly scoped.

Do not refactor unrelated code.

Existing callers must remain backward-compatible.

---

## 8. Implementation Method

For the selected phase:

1. read all tasks in that phase;
2. inspect required existing code before editing;
3. implement in dependency order;
4. use `[P]` only where genuinely safe;
5. run required targeted evidence;
6. mark tasks complete only after implementation and required evidence pass;
7. pass the phase gate;
8. STOP before the next phase.

Do not mark partially-complete tasks as complete.

---

## 9. Testing Strategy — Important

For **Phases 0–10**, do NOT run the entire repository regression suite after every phase.

Run only:

* tests created/changed by the current phase;
* directly related regression/security tests;
* required real-Postgres tests where the task genuinely needs PostgreSQL;
* static/type/lint checks explicitly required by that phase gate.

Do not automatically run after every phase:

```text
full pytest regression
full historical migration chain
full frontend E2E
Docker production build
repo-wide security scan
all-module regression
```

unless the approved phase gate explicitly requires one.

This is deliberate:

```text
fast targeted validation per phase
+
complete regression at the end
```

Never skip a check that the approved phase gate explicitly requires.

---

## 10. Phase 11 Is Different

When:

```text
PHASE_TO_IMPLEMENT = 11
```

run the full final release-readiness verification required by `tasks.md`.

This is where the expensive checks belong, including as applicable:

* full backend regression and coverage;
* full `mypy .`;
* Ruff/format;
* final security regression;
* full historical PostgreSQL migration chain;
* frontend lint/test/build;
* Playwright smoke E2E;
* Docker production build;
* security tooling;
* backward-compatibility rechecks;
* git hygiene and final evidence.

Do not weaken Phase 11 for speed.

---

## 11. Failure Rules

If a tenant/security test fails:

```text
STOP immediately.
```

If a current-phase targeted test fails:

fix the current phase before proceeding.

If an earlier Epic 11 phase contains a genuine defect exposed by the current phase, make only the smallest necessary correction and clearly report it.

Do not hide or relabel failures.

Do not use blind bulk transformations.

---

## 12. Git Rules

Do not discard existing user changes.

Do not reset unrelated files.

Do not push or merge unless explicitly authorized.

Do not begin the next phase automatically.

---

## 13. Completion Criteria

The phase is PASS only if:

```text
all assigned tasks complete
+
required targeted tests pass
+
gate-required checks pass
+
no known tenant/security defect remains
+
tasks.md accurately reflects completion
```

Otherwise:

```text
STATUS = BLOCKED
```

---

## 14. Required Final Report

[full report structure specified — see command output]

---

## 15. Accuracy Rule

Never claim a check passed unless it actually ran.

---

# START

Now implement:

```text
PHASE_TO_IMPLEMENT = 0
```

Read the authoritative files, verify prerequisites, implement the full requested phase, run targeted/gate-required checks, produce the required report, and STOP before the next phase.

(Full verbatim prompt, including the complete required-report template and `/sp.implement` skill instructions, is preserved in the conversation's command invocation; abbreviated here per PHR convention for a very long structured master-prompt — no instruction content was altered or omitted from actual execution.)

## Response snapshot

Implemented Epic 11 Phase 0 (Foundation, T001–T034) in full. Created the
`backend/modules/reports/` package skeleton, constants, 10 typed
exceptions, empty router, feature-flag gate chain (model + repository +
service + `ReportsModuleEnablementProvider` + `require_reports_enabled`),
`reports` Capability registration, 16 `reports.*` permission codes unioned
into `INITIAL_PERMISSIONS`, shared schemas (`JsonValue`, `PeriodPreset`,
`PeriodResolution`, `FreshnessClassification`, `ComparisonRequest/Result`,
`DrillDownRef`, `ReportEnvelopeMeta`), the `BaseReportResult` hierarchy +
`ReportAdapter` Protocol + both empty registries (`ADAPTER_REGISTRY`,
`COMPOSITE_REPORT_HANDLERS`), the Report Registry types
(`ReportDefinition`, `ReportExecutionKind`, etc.), and five supporting
services (permission check, date-range resolution, comparison,
money normalization, CSV sanitizer) plus registry discovery filtering.

**Genuine repository contradiction found and corrected (smallest-diff
fix, clearly flagged)**: `tasks.md`/`plan.md` require a row-backed
`ReportsFeatureFlagService` identical in shape to CRM's/Installments' own
per-module `*_feature_flags` tables, but no migration for this table
exists anywhere in the 12-phase task list. Added migration `073_reports_
foundation.py` (creating `reports_feature_flags`, mirroring
`055_crm_foundation.py`/`062_installments_foundation.py` exactly) — the
smallest possible fix, verified upgrade/downgrade/re-upgrade clean against
real Postgres from a fresh `001` baseline. **Downstream effect for
whoever implements Phase 1**: its four migrations (capability seed,
permission seed, saved views table, audit log table) must be renumbered
`074-077` instead of the doc's stated `073-076`.

All Gate 0 evidence green: 10/10 required unit/integration tests pass,
`mypy . = 0` (1341 files), `ruff check .` clean, `ruff format --check .`
clean, and a 284-test regression across CRM/Installments/platform_admin/
users_roles/reports passes against real Postgres with zero regressions.
Working tree contains only the intended files.

## Outcome

- ✅ Impact: Epic 11 Phase 0 (Foundation) fully implemented and gated; Gate 0 PASS. Reports module scaffold, entitlement/RBAC wiring, and shared contracts now exist as a green-field base for Phase 2's domain adapters.
- 🧪 Tests: 10 new Phase-0 test files (48 tests) all green; 284-test related regression (CRM/Installments/platform_admin/users_roles/reports) green against real Postgres; `mypy . = 0`; `ruff` clean.
- 📁 Files: 24 new backend/modules/reports/* files, 1 new migration (073), 10 new test files, 4 modified files (capability_seed_service.py, module_enablement.py, api/v1/router.py, users_roles/constants.py).
- 🔁 Next prompts: Await explicit authorization to begin Phase 1 (Saved Report Views: Persistence Only, T035–T046) — Phase 1's migration numbers must shift to 074–077 per this phase's corrective addition.
- 🧠 Reflection: The missing feature-flag-table migration was a real cross-document gap (plan.md's row-backed service design vs. tasks.md's migration list never including it) — worth flagging in future spec/tasks reviews that every "mirrors CRM/Installments" service claim should be cross-checked against an actual migration task, not just a service-file task.

## Evaluation notes (flywheel)

- Failure modes observed: A recursive Pydantic type alias (`JsonValue = ... | list["JsonValue"] | ...`) written with implicit string-forward-ref unions caused infinite recursion in Pydantic v2's schema builder; fixed via PEP 695 `type JsonValue = ...` syntax (Python 3.12), which Pydantic v2 explicitly supports for self-referential aliases.
- Graders run and results (PASS/FAIL): mypy PASS (0 errors/1341 files); ruff check PASS; ruff format PASS; targeted Phase 0 tests PASS (48/48); related regression PASS (284/284, 1 expected skip).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
