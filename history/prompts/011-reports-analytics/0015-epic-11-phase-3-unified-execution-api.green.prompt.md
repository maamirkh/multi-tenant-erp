---
id: 0015
title: Epic 11 Phase 3 Unified Execution API
stage: green
date: 2026-09-14
surface: agent
model: claude-sonnet-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: /sp.implement
labels: ["epic-11", "reports-analytics", "phase-3", "execution-api", "gate-3"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/reports/services/execution_service.py
 - backend/modules/reports/services/saved_view_service.py
 - backend/modules/reports/schemas/discovery.py
 - backend/modules/reports/schemas/envelope.py
 - backend/modules/reports/schemas/common.py
 - backend/modules/reports/router.py
 - backend/tests/unit/modules/reports/test_authorize_and_validate.py
 - backend/tests/unit/modules/reports/test_no_direct_adapter_dispatch.py
 - backend/tests/unit/modules/reports/test_deferred_execution_unreachable.py
 - backend/tests/integration/api/v1/reports/conftest.py
 - backend/tests/integration/api/v1/reports/test_discovery_endpoint.py
 - backend/tests/integration/api/v1/reports/test_execute_endpoint_envelopes.py
 - backend/tests/integration/api/v1/reports/test_error_envelope_mapping_phase3.py
 - backend/tests/integration/api/v1/reports/test_drilldown_reauthorization.py
 - backend/tests/integration/api/v1/reports/test_http_trial_balance_equivalence.py
 - backend/tests/integration/api/v1/reports/test_gl_cursor_continuity.py
 - backend/tests/integration/api/v1/reports/test_saved_view_reauthorization.py
 - backend/tests/integration/api/v1/reports/test_router_mount.py
 - backend/tests/integration/api/v1/reports/postgres/conftest.py
 - backend/tests/integration/api/v1/reports/postgres/test_installments_case_a_b_execution.py
 - specs/011-reports-analytics/tasks.md
tests:
 - tests/unit/modules/reports/ + tests/integration/api/v1/reports/ (304 tests, SQLite)
 - tests/integration/api/v1/reports/postgres/ (12 tests, real Postgres)
 - mypy . (1425 files, 0 errors)
 - ruff check . (all checks passed)
---

## Prompt

# DevSphere ERP SaaS

# Epic 11 — Reports & Analytics

## Compact Reusable Implementation Master Prompt

[Full standard /sp.implement master-prompt template, PHASE_TO_IMPLEMENT = 3 — see history/prompts/011-reports-analytics/0012-*.md for the complete verbatim template text, identical across all phase invocations]

## Response snapshot

Implemented Epic 11 Phase 3 (Unified Execution API, T126–T144) in full:

- **T126/T128**: `ReportExecutionService` (`services/execution_service.py`) — `_authorize_and_validate()` (registry lookup incl. COMPOSITE-kind rejection; Installments continuity-gate wiring, the one and only live-request-path integration point; domain entitlement; RBAC permission via a `permission_kind: Literal["view","export"]` discriminator; filter validation; sort validation) and `execute()` (dispatches to `ADAPTER_REGISTRY`, sets `read_only_servicing_continuity`/`drill_down` on the result's meta post-adapter).
- **T130/T132/T136/T140**: new router endpoints — `GET /discovery`, `GET /{report_key}` (isinstance-narrowed into 3 new Reports-owned envelope wrappers, `schemas/envelope.py`), `GET /saved-views/{view_id}` (`SavedViewService.load()`, the only place load() exists — re-runs full `_authorize_and_validate()` against the loading user's current state).
- **T134**: confirmed already structurally satisfied since Phase 0 (global `ApplicationException` handler) — no new router-level registration needed.
- Tests: T127, T129, T131, T133, T135, T137–T143 (11 required + several I split further), all green.

Two genuine defects were discovered and fixed transparently:
1. **Pydantic `SerializeAsAny` bug** in the new envelope schemas — a bare `BaseModel`-bound generic field serializes using its declared (empty) type, not the runtime subclass, silently emitting `{}` for every real payload. Caught by T138 (the first test to inspect a non-empty response body against real fixture data); every other Phase-3 test against a fresh, dataless company never exposed it. Fixed by wrapping every generic payload field in `SerializeAsAny[...]`.
2. **FR-RPT-243 test-setup gap** — discovered the spec explicitly forbids Epic 11 from hardcoding a default role→`reports.*` permission mapping (unlike CRM/Installments' own `_CRM_OWNER`/`_INSTALLMENTS_OWNER` precedent), so a fresh company's owner holds *zero* `reports.*` permissions by default. Not a bug — corrected the test helper (`setup_company()`) to explicitly grant them, simulating the real tenant-admin RBAC action FR-RPT-243 requires.

One pre-existing Phase-0 test was corrected: `test_router_mount.py`'s "unregistered path 404s" assertion was true only while `reports_router` had zero report-key routes — T132's new `GET /{report_key}` catch-all now means an unauthenticated request matches a real route and correctly 401s via `require_authenticated` before any registry lookup (a stricter, more correct default). Renamed/corrected.

One pre-existing, out-of-scope test-isolation issue was found and reported, not fixed: `test_router_mount.py` and `test_entitlement_roundtrip.py` (both unmodified Phase 0/1 files) leak SQLite capability-seed state across each other in one specific combined-run ordering — reproducible with zero Phase 3 files present, passing in isolation and in every other combination.

Real-Postgres testing for T142 required a local `test_client` fixture override (`postgres/conftest.py`) setting a concrete client host — Starlette's default fake `"testclient"` host fails real Postgres's `inet`-typed audit-log column, a pre-existing SQLite/Postgres test-double gap, first surfaced here.

All 145 tasks (T001–T144, Phases 0–3) now marked `[x]` in tasks.md; Phase 4 onward (T145+) correctly remains unmarked.

## Outcome

- ✅ Impact: Epic 11 Phase 3 complete — every registered "Now" report is reachable through a single, fully-typed, gate-chain-enforced HTTP execution path (discovery, execute, saved-view load), with zero direct `ADAPTER_REGISTRY` access anywhere in the router (AST-scan verified).
- 🧪 Tests: 304/304 SQLite tests pass (unit + integration); 12/12 real-Postgres tests pass; `mypy .` clean across 1425 files; `ruff check .` clean.
- 📁 Files: 4 new Reports module files (`execution_service.py`, `schemas/discovery.py`, `schemas/envelope.py`), `saved_view_service.py`/`router.py`/`schemas/common.py` extended, 12 new test files, 1 corrected pre-existing test, `tasks.md` updated (145 tasks now `[x]`).
- 🔁 Next prompts: Await explicit authorization, then `/sp.implement PHASE_TO_IMPLEMENT = 4` (Executive Dashboard).
- 🧠 Reflection: The `SerializeAsAny` bug is a strong argument for always testing against non-empty, realistic response bodies at least once per new response-wrapping layer — every "fresh company, zero data" test in this phase would have silently passed with `data: {}`.

## Evaluation notes (flywheel)

- Failure modes observed: generic Pydantic wrapper types silently drop subclass fields without `SerializeAsAny`; a spec-explicit "no default RBAC mapping" rule (FR-RPT-243) can look identical to a seeding bug until the spec text is checked directly.
- Graders run and results (PASS/FAIL): mypy PASS, ruff PASS, SQLite suite PASS (304/304), Postgres suite PASS (12/12), Gate 3 PASS.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a — awaiting Phase 4 authorization.
