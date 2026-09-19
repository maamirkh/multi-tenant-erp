---
id: 0011
title: Epic 11 Phase 1 saved views persistence
stage: green
date: 2026-09-12
surface: agent
model: claude-sonnet-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: /sp.implement
labels: ["epic-11", "reports-analytics", "phase-1", "saved-views"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/migrations/versions/074_reports_capability_seed.py
 - backend/migrations/versions/075_reports_permission_seed.py
 - backend/migrations/versions/076_reports_saved_report_views_table.py
 - backend/modules/reports/models/saved_report_view.py
 - backend/modules/reports/models/__init__.py
 - backend/modules/reports/repositories/saved_report_view.py
 - backend/modules/reports/schemas/saved_view.py
 - backend/modules/reports/services/saved_view_service.py
 - backend/modules/reports/dependencies.py
 - backend/modules/reports/router.py
 - backend/tests/unit/modules/reports/test_reports_permission_migration_matches_constants.py
 - backend/tests/integration/migrations/test_074_075_reports_seed.py
 - backend/tests/integration/api/v1/reports/postgres/__init__.py
 - backend/tests/integration/api/v1/reports/postgres/conftest.py
 - backend/tests/integration/api/v1/reports/postgres/test_saved_views_crud.py
 - backend/tests/security/reports/__init__.py
 - backend/tests/security/reports/test_saved_view_ownership.py
tests:
 - backend/tests/unit/modules/reports/test_reports_permission_migration_matches_constants.py
 - backend/tests/integration/migrations/test_074_075_reports_seed.py
 - backend/tests/integration/api/v1/reports/postgres/test_saved_views_crud.py
 - backend/tests/security/reports/test_saved_view_ownership.py
---

## Prompt

# DevSphere ERP SaaS

# Epic 11 — Reports & Analytics

## Compact Reusable Implementation Master Prompt

Implement only the requested Epic 11 phase.

Set:

```text
PHASE_TO_IMPLEMENT = 1
```

[Full master prompt identical in structure to PHR 0010's Phase 0 invocation
— sections 1-15 on authoritative sources, scope, prerequisite checks,
architecture rules, type/financial safety, contract preservation,
source-domain change limits, implementation method, testing strategy,
Phase 11 exception, failure rules, git rules, completion criteria,
required final report format, and the accuracy rule — preserved verbatim
in the actual command invocation; abbreviated here per PHR convention.]

# START

Now implement:

```text
PHASE_TO_IMPLEMENT = 0
```

Read the authoritative files, verify prerequisites, implement the full requested phase, run targeted/gate-required checks, produce the required report, and STOP before the next phase.

**"Phase 0 introduced migration 073_reports_foundation; inspect the actual Alembic head and renumber Phase 1 migrations accordingly. Do not reuse revision 073."**

(Note: the master prompt body's own `START` section still said `PHASE_TO_IMPLEMENT = 0` — a copy-paste artifact from reusing the Phase 0 template — but the prompt's opening line, its explicit `Set: PHASE_TO_IMPLEMENT = 1`, and the trailing renumbering instruction referencing "Phase 0 introduced migration 073" all unambiguously target Phase 1; treated as Phase 1 per user intent, not the literal stale `0`.)

## Response snapshot

Implemented Epic 11 Phase 1 (Saved Report Views: Persistence Only,
T035–T046) in full, renumbering the phase's three migrations to
`074`/`075`/`076` per the user's explicit instruction (Phase 0's
corrective `073_reports_foundation.py` already claimed that revision).

Created: `074_reports_capability_seed.py` (mirrors `070`),
`075_reports_permission_seed.py` (mirrors `071`'s literal-tuple
convention, but **permissions-catalog-only — zero role_permissions
grants**, per FR-RPT-243's explicit "no default role mapping" decision,
a deliberate deviation from Installments' own precedent), and
`076_reports_saved_report_views_table.py` (creates `saved_report_views`
+ its two indexes). Added the `SavedReportView` ORM model,
`SavedReportViewRepository` (owner-scoped: every method requires both
`company_id` and `user_id`; a nonexistent/other-owner/other-tenant/soft-
deleted row all resolve to the identical `None`), `FilterConfigV1`/
`SavedReportViewCreate/Update/Read` schemas, `saved_view_service`
(`save`/`update`/`delete`/`list_views` — `load()` deliberately deferred
to Phase 3), and the four router endpoints (`GET`/`POST`/`PATCH`/`DELETE
/saved-views[/{id}]`, gated by `reports.saved_view.manage`, checked
inline matching platform convention).

All Gate 1 evidence green: T037 (migration/constants consistency) green;
T045A (dedicated ownership security test, 9 cases) green; a new
real-Postgres CRUD round-trip test (6 cases: create/list/update/delete,
JSONB `filter_config` exact round-trip, ownership/tenant isolation)
green; full migration chain `001→076` up/down/up clean against a fresh
throwaway Postgres database. `mypy . = 0` (1355 files), `ruff` clean.
239-test targeted regression (CRM/Installments/platform_admin/
users_roles) against real Postgres, zero failures.

## Outcome

- ✅ Impact: Epic 11 Phase 1 (Saved Report Views persistence) fully implemented and gated; Gate 1 PASS. Private, user-owned saved view CRUD now exists end-to-end (model → repository → service → schemas → router), validated against a test-fixture Report Registry entry pending Phase 2's real reports.
- 🧪 Tests: 4 new Phase-1 test files (20 tests total) all green; 67-test targeted reports suite green; 239-test related regression green against real Postgres; `mypy . = 0`; `ruff` clean; full migration chain 001→076 verified up/down/up.
- 📁 Files: 3 new migrations (074-076), 1 new model, 1 new repository, 1 new schema module, 1 new service, 4 new router endpoints, 4 new test files (20 tests).
- 🔁 Next prompts: Await explicit authorization to begin Phase 2 (Domain Adapters, T047–T125) — the largest phase (6 domain sub-phases + deferred-stub registration), whose three sanctioned source-domain seam tasks (T047 Accounting, T075 Purchase, T087 Inventory) are the only permitted touches to those modules' own files.
- 🧠 Reflection: The FR-RPT-243 "no default role mapping" decision required a real deviation from the Installments/CRM migration precedent (071 granted default role permissions; 075 deliberately does not) — worth flagging explicitly in the migration's own docstring (done) so a future reader doesn't mistake the omission for a bug when comparing against 071's shape.

## Evaluation notes (flywheel)

- Failure modes observed: none this phase — the PEP 695 `JsonValue` fix from Phase 0 carried forward cleanly into the new `SavedReportView.filter_config: Mapped[dict[str, JsonValue]]` JSONB column with no further schema-generation issues.
- Graders run and results (PASS/FAIL): mypy PASS (0 errors/1355 files); ruff check PASS; ruff format PASS; targeted Phase 1 tests PASS (20/20); targeted reports suite PASS (67/67, 1 expected skip); related regression PASS (239/239); full migration chain PASS (001→076 up/down/up).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
