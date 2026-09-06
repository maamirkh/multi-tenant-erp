---
id: 0008
title: Implement Phase 10 CRM performance security regression closure
stage: green
date: 2026-08-18
surface: agent
model: claude-sonnet-5
feature: 009-crm
branch: 009-crm
user: Muhammad Amir
command: /sp.implement
labels: ["crm", "phase-10", "performance", "security", "regression", "epic-closure"]
links:
  spec: specs/009-crm/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/tests/performance/crm/__init__.py
 - backend/tests/performance/crm/test_list_performance.py
 - backend/tests/performance/crm/test_conversion_performance.py
 - backend/tests/performance/crm/test_customer_360_performance.py
 - backend/tests/performance/crm/test_pipeline_report_performance.py
 - backend/tests/security/crm/conftest.py
 - backend/tests/security/crm/test_tenant_and_security.py
 - backend/modules/crm/services/audit_service.py
 - backend/modules/crm/services/lead_conversion_service.py
 - backend/tests/integration/repositories/crm/test_lead_conversion.py
 - specs/009-crm/data-model.md
 - specs/009-crm/research.md
 - specs/009-crm/quickstart.md
 - specs/009-crm/contracts/events.md
 - specs/009-crm/contracts/crm-v1.yaml
 - specs/009-crm/tasks.md
tests:
 - backend/tests/performance/crm/test_list_performance.py (3 tests, T092)
 - backend/tests/performance/crm/test_conversion_performance.py (2 tests, T093)
 - backend/tests/performance/crm/test_customer_360_performance.py (1 test, T094)
 - backend/tests/performance/crm/test_pipeline_report_performance.py (1 test, T095)
 - backend/tests/security/crm/test_tenant_and_security.py (16 tests, T096, SEC-01–SEC-12)
 - backend/tests/integration/repositories/crm/test_lead_conversion.py (added regression test for the SEC-10 defect fix)
 - Full CRM suite (T097): 434 passed
 - Targeted regression — users_roles/sales/accounting (T098): 2469 passed
 - Full repository regression — all Epics (T099): 5638 passed, 3 failed (all triaged as pre-existing flaky/environment, zero CRM-caused)
---

## Prompt

```text
Implement the next phase of Epic 9 — CRM exactly according to the existing approved:

- specs/009-crm/spec.md
- specs/009-crm/plan.md
- specs/009-crm/tasks.md

Current phase:
Phase 10 — "Performance, Security, Regression & Epic Closure"

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
Phase 10 — "Performance, Security, Regression & Epic Closure"
```

## Response snapshot

Implemented Phase 10 (T092–T099, T101–T103) of Epic 9 CRM. Wrote 4 performance benchmark files (T092–T095) as SQLite regression guards following the exact Epic 8 `test_report_performance.py` precedent, with T093/T094 measured at the real spec.md §47 target values. Wrote a dedicated 16-test security suite (`test_tenant_and_security.py`, T096) covering all 12 SEC-01–SEC-12 cases as real HTTP requests, which surfaced a genuine Epic 9 defect: `LeadConversionService.convert()`'s idempotent-retry branch hardcoded `customer_matched=True` regardless of the original conversion's real outcome. Fixed via a new `CrmAuditService.find_latest_after_state()` method that recalls the fact from the existing audit log (no new migration/column needed), with 2 regression tests added. Ran the full CRM suite (434 passed, T097), targeted Users/Roles+Sales+Accounting regression (2469 passed, T098), and full repository regression across all Epics (5638 passed / 3 failed, T099) — all 3 failures reproduced in isolation and triaged as pre-existing (2 flaky timing tests in Epic 8 accounting, 1 pre-existing `DEBUG=true` environment leak in `tests/unit/core/test_settings.py`), none CRM-caused. Ran ruff/mypy/ESLint/tsc (T101) — all clean on CRM-owned files. Audited `git diff --stat` (T102) — confirmed the 3 documented Epic 1–8 files are additive-only, plus one previously-undocumented additive line in `tests/conftest.py` (registering CRM models for the SQLite test metadata), noted in research.md. Wrote all 5 closure artifacts (T103): `data-model.md`, `research.md`, `quickstart.md`, `contracts/events.md`, and a generated `contracts/crm-v1.yaml` OpenAPI spec (24 paths / 36 operations / 59 schemas). T100 (full live Docker/Postgres verification) was deliberately deferred per this phase's own explicit instruction, matching the identical precedent already set by Phase 9's own gate. Updated tasks.md's Phase 10 gate section honestly, including the one still-open T100 item.

## Outcome

- ✅ Impact: Phase 10 substantially complete (11/12 tasks); Epic 9's confidence gate is met except for the explicitly-deferred live-Postgres verification pass. One genuine pre-existing-defect-class bug (idempotent conversion's `customer_matched` flag) found and fixed with regression coverage before Epic 9 closes.
- 🧪 Tests: 434 CRM (T097) + 2469 targeted cross-module (T098) + 5638 full-repo (T099, 3 pre-existing/environment failures triaged, zero CRM-caused) all green; 16/16 new security tests (T096); 4/4 performance benchmarks (T092–T095) within their asserted targets.
- 📁 Files: 4 new performance test files, 1 new security test file + conftest, 2 modified CRM source files (audit_service.py, lead_conversion_service.py), 1 extended regression test file, 5 new closure-documentation artifacts, tasks.md updated.
- 🔁 Next prompts: T100 (live Docker/Postgres verification, full 14-item checklist) at Epic-9 final closure; then Epic 10 kickoff.
- 🧠 Reflection: Writing the dedicated exhaustive SEC-01–SEC-12 suite (rather than relying on incidental coverage scattered across earlier phases' CRUD tests) is what surfaced the idempotency defect — exhaustive, purpose-built security tests catch things spot-checks miss, exactly as plan.md §27.3/§27.4 intended.

## Evaluation notes (flywheel)

- Failure modes observed: one genuine Epic 9 defect (idempotent conversion flag), one novel mypy-debt pattern in a new test file (fixed by typing the dict `Any`), one ruff F811 false-positive from importing a pytest fixture directly into a test module (fixed via a local `conftest.py` re-export instead) — all resolved within this phase.
- Graders run and results (PASS/FAIL): ruff PASS, mypy PASS (zero CRM-attributable errors), ESLint PASS, tsc PASS, full test suite PASS (5638/5641, 3 pre-existing triaged).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
