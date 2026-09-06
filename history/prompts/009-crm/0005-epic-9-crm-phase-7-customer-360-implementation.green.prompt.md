---
id: 0005
title: Epic 9 CRM Phase 7 Customer 360 implementation
stage: green
date: 2026-08-17
surface: agent
model: claude-sonnet-5
feature: 009-crm
branch: 009-crm
user: Muhammad Amir
command: /sp.implement
labels: ["crm", "customer-360", "cross-module-integration", "phase-7"]
links:
  spec: specs/009-crm/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/crm/services/customer_360_service.py
 - backend/modules/crm/schemas/customer_360.py
 - backend/modules/crm/repositories/lead.py
 - backend/modules/crm/exceptions.py
 - backend/modules/crm/dependencies.py
 - backend/modules/crm/router.py
 - backend/modules/crm/schemas/opportunity.py
 - backend/modules/crm/services/opportunity_service.py
 - backend/tests/integration/repositories/crm/test_customer_360.py
 - backend/tests/integration/api/v1/crm/test_customer_360_api.py
 - backend/tests/integration/repositories/crm/test_cross_module_integration.py
 - backend/tests/unit/modules/crm/test_opportunity_service.py
 - specs/009-crm/tasks.md
tests:
 - backend/tests/integration/repositories/crm/test_customer_360.py (6 tests)
 - backend/tests/integration/api/v1/crm/test_customer_360_api.py (4 tests)
 - backend/tests/integration/repositories/crm/test_cross_module_integration.py (5 tests)
 - full CRM regression suite (209 tests, tests/{unit/modules,integration/repositories,integration/api/v1}/crm/)
 - Accounting AR regression (15 tests)
 - Sales customer/quotation unit+repo regression (145 tests)
 - Sales customer/quotation API regression (37 tests)
---

## Prompt

Implement the next phase of Epic 9 — CRM exactly according to the existing approved:

- specs/009-crm/spec.md
- specs/009-crm/plan.md
- specs/009-crm/tasks.md

Current phase:
Phase 7 — "Customer 360 & Cross-Module Integration"

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
Phase 7 — "Customer 360 & Cross-Module Integration"

## Response snapshot

Implemented Phase 7 (T055–T059) of Epic 9 CRM: `Customer360Service` (dedicated read-only query service — 6 bounded queries + 4 Sales COUNT(*) summaries, zero N+1, never writes); `Customer360` Pydantic response schema; `GET /crm/customers/{customer_id}/360` endpoint (dual-permission TODO, wired for Phase 8); `LeadRepository.list_converted_to_customer()`; `CustomerNotFoundError`. Discovered `OpportunityUpdate` had no way to write back `Opportunity.quotation_id` (needed for plan.md §15.2's UI-orchestrated Quotation handoff and required for T059's own test to have something real to verify) — added it with cross-tenant validation via a new `SalesQuotationRepository` dependency on `OpportunityService`, consistent with the existing `customer_id` validation pattern. All 5 tasks completed with tests: T056 (6 tests: graceful degradation, cross-tenant 404, query-count-bounded regression guard via a test-local `before_cursor_execute` counter, AC-16 financial-figures-match-live-service, last_interaction/next_follow_up computation), T058 (4 API tests), T059 (5 boundary tests: structural import check + runtime write-tracking proving LeadConversionService/Customer360Service/Opportunity-quotation-link-back never touch Sales tables outside their sanctioned service calls). Full CRM regression (209 tests), Accounting AR regression (15), Sales customer/quotation regression (145 unit/repo + 37 API) all pass — zero regressions, zero Sales/Accounting/Users&Roles files modified. ruff and mypy clean on every touched CRM file (pre-existing repo-wide mypy debt in transitively-imported modules unrelated to this phase, matching every prior phase's documented convention). Marked T055–T059 and the Phase 7 gate `[x]` in tasks.md.

## Outcome

- ✅ Impact: Customer 360 read-model live at `GET /crm/customers/{customer_id}/360`; CRM↔Sales↔Accounting boundaries verified at runtime, not just on paper; Opportunity→Quotation link-back field now writable.
- 🧪 Tests: 406 total tests run across CRM (209), Accounting AR (15), Sales customer/quotation (182) — 100% pass, 0 regressions.
- 📁 Files: 8 new/modified CRM backend files, 3 new test files, 1 existing CRM unit test file updated for a constructor signature change, tasks.md checkboxes updated.
- 🔁 Next prompts: Phase 8 — RBAC, Audit, Events & Feature Flag Completion (wire real `user_has_crm_permission()` checks, remove Phase 3–7 TODOs, complete audit/event call sites).
- 🧠 Reflection: T059's own task description assumed `Opportunity.quotation_id` was already PATCH-able; it wasn't (a genuine gap from Phase 5) — closing it in-scope, with the same SEC-06-style cross-tenant validation already established for `customer_id`, was the smallest correct fix rather than writing a test for functionality that didn't exist.

## Evaluation notes (flywheel)

- Failure modes observed: One test-only tz-naive/tz-aware datetime comparison mismatch (SQLite round-trips datetimes as naive) — fixed by comparing wall-clock value only, matching the existing precedent in `test_activity_cascade.py`. One missing required field (`sales_rep_id`) when constructing a test-only `SalesQuotation` fixture — fixed by supplying it.
- Graders run and results (PASS/FAIL): ruff (PASS, 0 errors on CRM files), mypy (PASS, 0 errors attributable to CRM files), full CRM/Accounting-AR/Sales regression suites (PASS, 406/406).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
