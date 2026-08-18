---
id: 0006
title: Epic 9 CRM Phase 8 RBAC audit events
stage: green
date: 2026-08-17
surface: agent
model: claude-sonnet-5
feature: 009-crm
branch: 009-crm
user: Muhammad Amir
command: /sp.implement
labels: ["crm", "rbac", "audit", "domain-events", "feature-flag", "phase-8"]
links:
  spec: specs/009-crm/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/users_roles/constants.py
 - backend/main.py
 - backend/migrations/versions/056_crm_permission_backfill.py
 - backend/modules/crm/services/permission_check.py
 - backend/modules/crm/repositories/audit_log.py
 - backend/modules/crm/services/audit_service.py
 - backend/modules/crm/events/__init__.py
 - backend/modules/crm/events/lead_events.py
 - backend/modules/crm/events/opportunity_events.py
 - backend/modules/crm/events/activity_events.py
 - backend/modules/crm/handlers/integration_handlers.py
 - backend/modules/crm/router.py
 - backend/modules/crm/dependencies.py
 - backend/modules/crm/services/lead_service.py
 - backend/modules/crm/services/lead_conversion_service.py
 - backend/modules/crm/services/opportunity_service.py
 - backend/modules/crm/services/activity_service.py
 - backend/tests/security/crm/test_rbac.py
 - backend/tests/integration/api/v1/crm/test_permission_enforcement.py
 - backend/tests/integration/repositories/crm/test_audit_coverage.py
 - backend/tests/integration/repositories/crm/test_event_coverage.py
 - backend/tests/integration/repositories/crm/test_sales_integration_handlers.py
 - backend/tests/integration/api/v1/crm/test_feature_flag_gate.py
 - specs/009-crm/tasks.md
tests:
 - backend/tests/security/crm/test_rbac.py (154 tests: 152 matrix assertions + 2 completeness)
 - backend/tests/integration/api/v1/crm/test_permission_enforcement.py (12 tests)
 - backend/tests/integration/repositories/crm/test_audit_coverage.py (9 tests)
 - backend/tests/integration/repositories/crm/test_event_coverage.py (2 tests)
 - backend/tests/integration/repositories/crm/test_sales_integration_handlers.py (4 tests)
 - backend/tests/integration/api/v1/crm/test_feature_flag_gate.py (12 tests)
 - full CRM regression suite (402 tests, all Phases 1-8 combined)
 - users_roles regression (354 tests)
 - Accounting RBAC regression (35 tests)
 - alembic upgrade/downgrade --sql offline verification for migration 056
---

## Prompt

Implement the next phase of Epic 9 — CRM exactly according to the existing approved:

- specs/009-crm/spec.md
- specs/009-crm/plan.md
- specs/009-crm/tasks.md

Current phase:
Phase 8 — "RBAC, Audit, Events & Feature Flag Completion"

IMPORTANT:
This is an implementation task, NOT a planning task.

Before writing code:

1. Read the complete Epic 9 spec.md, plan.md, and tasks.md.
2. Read the existing project constitution/CLAUDE.md and relevant completed Epic 1–8 implementations.
3. Identify the exact tasks belonging to the current phase.
4. Do NOT implement tasks belonging to future phases.
5. Do NOT redesign the architecture or introduce speculative features.
6. Reuse existing ERP patterns, services, repositories, permissions, tenant isolation, audit conventions, API patterns, validation, error handling, and frontend conventions wherever applicable.
7. Maintain backward compatibility with all completed Epics.

Implementation requirements:

- Implement every task assigned to the current phase completely.
- Follow spec.md and plan.md as the source of truth.
- Keep the existing modular-monolith architecture.
- Maintain strict company_id / tenant isolation everywhere.
- Apply RBAC/permissions according to the specification.
- Preserve financial/accounting integrity where CRM interacts with Sales, AR/AP, Inventory, or Accounting.
- Use proper repository/service/router/schema/model separation consistent with the existing codebase.
- Add database migrations only when actually required.
- Add/update API endpoints and frontend UI where the current phase requires them.
- Add appropriate unit, integration, API, security, and regression tests.
- Do not modify or weaken existing tests just to make them pass.
- Do not skip existing functionality.
- Do not start the next phase.

Testing:

After implementation:

1. Run all tests relevant to the current phase.
2. Run the relevant existing CRM regression tests.
3. Run directly affected cross-module regression tests from previous Epics.
4. Run Ruff.
5. Run mypy according to the project's existing convention.
6. Run TypeScript check.
7. Run ESLint.
8. Verify migration integrity if a migration was added.
9. Verify API routes and permissions.
10. Verify tenant isolation and authorization for new functionality.

If any failure occurs:

- Investigate the root cause.
- Fix genuine defects introduced by this phase.
- Do NOT hide, skip, delete, weaken, or rewrite tests merely to obtain a passing result.
- Clearly distinguish new defects from pre-existing/flaky/environmental issues.
- Re-run the affected tests after every fix.

Task tracking:

- Mark only the completed tasks of the CURRENT phase as [X] in tasks.md.
- Do not mark future-phase tasks as complete.
- Keep task descriptions and phase boundaries intact.

Documentation:

At the end, provide a concise implementation report containing:

1. Phase implemented
2. Tasks completed
3. Files created
4. Files modified
5. Database/migration changes
6. APIs added/changed
7. Frontend changes
8. Tests executed and results
9. Code-quality results
10. Security/tenant-isolation verification
11. Any defects found and fixed
12. Any pre-existing issues discovered
13. Remaining tasks for the next phase

STOP CONDITION:

When the current phase is fully implemented and validated, STOP.

Do NOT automatically start the next phase.

Do NOT perform the full expensive live verification protocol unless explicitly requested. Phase-level implementation testing is sufficient at this stage; comprehensive live verification will be performed after Epic 9 is complete.

Current phase to implement:
Phase 8 — "RBAC, Audit, Events & Feature Flag Completion"

## Response snapshot

Implemented Phase 8 (T060–T078) of Epic 9 CRM, closing out every TODO stub left by Phases 1/3–7:

**RBAC (T060–T066)**: appended 19 `crm.*` `PermissionDefinition` tuples + role grants to `modules/users_roles/constants.py` (additive-only, 244 insertions/0 deletions); built `user_has_crm_permission()` mirroring Accounting's exact wrapper shape; wired inline permission checks into all 31 router endpoints (30 single-permission + Customer 360's dual-permission check); RBAC matrix test (152/152, all 19 codes × 8 roles verbatim against spec §31.2) plus a self-check cross-verifying the matrix against the real `DEFAULT_ROLE_PERMISSIONS` seed data; 12 HTTP-level permission-enforcement tests (denied+granted pairs across all 6 resource groups).

**Audit (T067–T070)**: `CrmAuditLogRepository` (create/list_for_entity only, no update/delete, matching `AccountingAuditLogRepository`'s precedent exactly); `CrmAuditService.record()` with `CompanyAuditService`'s keyword-only signature shape; wired into 8 auditable actions across `LeadService`/`LeadConversionService`/`OpportunityService` per spec §44's exact scoping (Activity create/update deliberately NOT audited — only status transitions); 9-test coverage file proving all 8 categories produce correct before/after-state rows.

**Events (T071–T075)**: CRM's own `InProcessEventBus` singleton (independent from every other module's); 12 event dataclasses across 3 files matching spec §36's payload tables exactly (qualify fires both `status_changed` AND `qualified`); wired `get_event_bus().publish()` after every commit across all 4 mutating services (11 call sites); event-coverage test exercising a full Lead→Opportunity lifecycle and asserting all 12 event types fire with correct payloads.

**Sales integration handlers (T074/T076/T077)**: discovered and corrected a spec inaccuracy before implementing — the real Sales event is `"quotation.accepted"`, not `"sales.quotation.accepted"` as spec.md's prose states (verified directly against `modules.sales.events.quotation_events.QuotationAccepted`); both handlers write a single NOTE Activity for salesperson visibility (owner resolved via the customer's most recent Opportunity; no-op if none exists) with zero CRM aggregate state mutation; wired into `main.py`'s lifespan (11 insertions, 0 deletions, confirmed via full app lifespan smoke test).

**Feature flag gate (T078)**: built a test-local `flag_gated_client` fixture applying `require_crm_enabled` at include-time (Phase 9's real production shape) without touching the shared `crm_client` fixture every other Phase 3–7 test depends on; 12 tests (6 resource groups × flag-off-403/flag-on-200).

**Migration (T062)**: created `056_crm_permission_backfill.py` as a new additive migration (not amending already-created `055`) — idempotent `ON CONFLICT DO NOTHING` backfill of the 19 permissions + per-role grants for pre-existing companies, verified via offline `alembic upgrade/downgrade --sql` emission (no Docker/Postgres this session, consistent with every earlier phase's documented deviation).

All touched TODO markers in `router.py`/4 services are now zero. Full CRM regression (402 tests), users_roles regression (354), Accounting RBAC regression (35) — 791/791 pass, zero regressions. ruff clean on every touched file; mypy zero errors attributable to any Phase 8 file (pre-existing unrelated debt in transitively-imported modules only). Marked T060–T078 and the Phase 8 gate `[x]` in tasks.md.

## Outcome

- ✅ Impact: Every CRM endpoint now genuinely access-controlled and auditable, not merely functional; CRM's domain events are live and consumable; Customer 360's timeline auto-updates from real Sales activity; the module-wide feature flag gate is proven end-to-end.
- 🧪 Tests: 791 total across CRM + users_roles + Accounting RBAC regression — 100% pass, 0 regressions. 6 new CRM test files added this phase.
- 📁 Files: 2 of the epic's exactly-3 permitted Epic 1–8 file modifications now used (`constants.py`, `main.py`), both purely additive; 1 new migration; 12 new/modified CRM backend files; 6 new test files.
- 🔁 Next prompts: Phase 9 — API, Frontend, Dashboard & Reporting (mount `crm_router` into `api/v1/router.py` — the epic's 3rd and final permitted Epic 1–8 file edit — build the Next.js `(crm)` route group, and CRM reporting/KPI endpoints).
- 🧠 Reflection: T074's own task description flagged the exact risk that materialized — spec.md's documented event name (`sales.quotation.accepted`) didn't match the real, already-published event type (`quotation.accepted`). Verifying against the actual producer code before subscribing, rather than trusting the spec's prose, avoided a silently-dead subscription that would have looked correct in every unit test but never fired in practice.

## Evaluation notes (flywheel)

- Failure modes observed: `SessionLocal()`-based handler tests initially hit a real Postgres connection attempt (handlers use the production session factory, not the test fixture) — fixed via `monkeypatch.setattr(handlers, "SessionLocal", lambda: db_session)`, matching the established precedent in `tests/integration/repositories/accounting/test_integration_handlers.py`. A related `DetachedInstanceError` surfaced because the handler's own `db.close()` expires all ORM attributes on the shared test session after a commit — fixed by capturing plain-value IDs before invoking the handler rather than re-touching ORM instance attributes afterward. One BR-008 partial-unique-index violation in the event-coverage test (tried to create a second default Pipeline after Lead conversion had already auto-provisioned one) — fixed by reusing `PipelineRepository.get_default_for_company()` instead of unconditionally creating a new one.
- Graders run and results (PASS/FAIL): ruff (PASS, 0 errors on all touched files), mypy (PASS, 0 errors attributable to any Phase 8 file), full regression suite (PASS, 791/791), offline alembic SQL-emission for migration 056 (PASS, both directions clean).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
