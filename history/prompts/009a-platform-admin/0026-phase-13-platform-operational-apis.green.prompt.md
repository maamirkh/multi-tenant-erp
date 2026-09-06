---
id: 0026
title: Phase 13 — Platform Operational APIs
stage: green
date: 2026-08-23
surface: agent
model: claude-sonnet-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.implement
labels: ["epic-9a", "phase-13", "dashboard", "tenant-directory", "audit-view", "health", "export", "contract-conformance"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/platform_admin/services/tenant_directory_service.py
  - backend/modules/platform_admin/services/dashboard_service.py
  - backend/modules/platform_admin/services/health_service.py
  - backend/modules/platform_admin/services/export_service.py
  - backend/modules/platform_admin/schemas/tenant_directory.py
  - backend/modules/platform_admin/schemas/dashboard.py
  - backend/modules/platform_admin/schemas/health.py
  - backend/modules/platform_admin/router.py
  - backend/modules/platform_admin/dependencies.py
  - backend/api/v1/router.py
  - backend/core/events/outbox.py
  - backend/modules/companies/repositories/company_repository.py
  - backend/tests/integration/api/v1/platform_admin/test_tenant_operational_apis.py
  - backend/tests/integration/api/v1/platform_admin/test_dashboard_health.py
  - backend/tests/integration/api/v1/platform_admin/test_contract_conformance.py
  - backend/tests/unit/modules/platform_admin/test_export_service.py
  - backend/tests/security/modules/platform_admin/test_audit_immutability.py
  - specs/009a-platform-admin/tasks.md
tests:
  - backend/tests/integration/api/v1/platform_admin/test_tenant_operational_apis.py (9 passed)
  - backend/tests/integration/api/v1/platform_admin/test_dashboard_health.py (8 passed)
  - backend/tests/unit/modules/platform_admin/test_export_service.py (7 passed)
  - backend/tests/integration/api/v1/platform_admin/test_contract_conformance.py (3 passed, run via local venv — needs specs/ outside the Docker mount)
  - backend/tests/security/modules/platform_admin/test_audit_immutability.py (5 passed, 1 updated for T170's planned route addition)
  - full Phase 5-13 platform_admin suite: unit + integration + repositories + security (249 passed, real Postgres)
  - cross-module regression: inventory/test_products_api.py + crm/test_feature_flag_gate.py + companies/test_company_list_performance.py (37 passed)
  - companies regression: test_company_repository.py + test_company_permissions.py + test_company_service.py (68 passed)
---

## Prompt

```text
# Epic 9A — Platform Administration / Super Admin
# MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT

Implement, verify, audit, and close ONLY the following phase of Epic 9A.

## TARGET PHASE

**Phase Number:** `13`
**Phase Name:** `Platform Operational APIs (Dashboard, Tenants, Audit, Health)`
**Task Range:** `<T167 to T177>`

[... the full ~700-line master-prompt template, identical in structure to the one embedded verbatim in PHRs 0021-0025 (Phases 8-12), with only Phase Number=13, Phase Name="Platform Operational APIs (Dashboard, Tenants, Audit, Health)", Task Range=T167 to T177 substituted. Sections 1-37 cover: strict phase scope; branch/working-tree requirements; the pre-implementation task audit; the repository-reality check; the six-step per-task implementation rule; the full Architecture Freeze; database/migration hard rules (frozen range 057-061, no 062); the API Contract Lock (28 paths/33 operations); the full adversarial security-testing checklist; tenant isolation audit; the seven-level testing pyramid; pre-existing failure policy; real PostgreSQL/Docker verification; live HTTP/browser verification; audit fail-closed proof requirement; requirement traceability review; contract↔implementation audit; data-model↔implementation audit; the post-implementation self-review checklist; the adversarial completeness pass; the full diff review; the task-checkbox rule; the phase exit condition rule; the Gate rule; regression verification; the no-correction-pass standard; PHR requirements; pre-commit checks; commit policy; post-commit verification; the required final report structure (sections A-P); and the final stop rule. Full text identical to prior phase PHRs' embedded prompts — see PHR 0025 for the complete verbatim template if needed.]
```

## Response snapshot

Implemented Epic 9A Phase 13 (T167-T177) end-to-end — the final backend implementation phase of Epic 9A: tenant directory/360°-detail/lifecycle-history, the platform audit view, dashboard aggregates with per-widget states and permission-gated omission, platform health, export capability, and the Epic-wide contract conformance test.

**Tenant directory/detail/lifecycle** (T167-T169): `TenantDirectoryService` composes existing Phase 7-11 infrastructure — `CompanyRepository.list_all()` (extended with a whitelisted `sort_by`/`sort_order`, backward-compatible defaults; explicitly NOT reusing the pre-existing tenant-side `require_super_admin()` authorization mechanism it also served, since that legacy tenant-RBAC shortcut is exactly what Epic 9A's `platform.tenants.read` permission-code check supersedes), `PlatformEntitlementService`, `QuotaService`, `OverrideService`, `PlatformAuditRepository`. Zero duplicated resolution logic.

**Platform audit view** (T170): wires `PlatformAuditQueryService` — built in Phase 6 (T78) with a docstring explicitly naming T170 as its future caller. Required updating one pre-existing Phase 6 security test whose own docstring pre-authorized this exact change (see Defects Discovered).

**Dashboard** (T171-T173): `DashboardService` — six independently-bounded widgets, each reporting `populated|empty|unavailable` (never a fabricated `0` on failure). `quota_warnings` resolves via a single JOIN across `usage_records`/`subscriptions`/`plan_quotas` rather than an N+1 per-tenant resolver call — a documented simplification (doesn't apply tenant quota overrides, unlike the authoritative Phase 11 per-tenant endpoint). Widgets are omitted entirely (not shown empty) when the caller lacks the underlying permission. The AI widget is entirely absent until `ai_credit_ledger_entries` has a real row.

**Health** (T174-T175): `HealthService` reuses the exact database/auth-config check logic `/api/v1/health` already computes (not a second implementation) plus new read-only `EventOutboxRepository.count_pending()`/`count_published()` methods, with an explicit `relay.status = "logging_only_stub"` label.

**Export** (T176): **Contract finding** — a full re-read of `platform-admin-v1.yaml` confirms zero `/export` path exists (the file's own "28 paths" count has no room for one), even though `platform.tenants.export`/`platform.export.generate` exist in the Phase 5 permission catalogue. `ExportService` is therefore service-layer only — no router change — mirroring Phase 11's T149 and Phase 12's T161 precedent exactly.

**Contract conformance** (T177): the capstone test. Reads the real YAML contract directly (not a hand-duplicated Python copy) and cross-references every path/method/permission against the live FastAPI app's actual route table, using a new `permission_code` attribute tag on `require_platform_permission()`'s returned dependency specifically to make the *wired* permission introspectable without a second hand-maintained map. Required solving a genuine FastAPI-version-specific routing quirk (`_IncludedRouter` wraps every `include_router()` call recursively, carrying its prefix in `include_context.prefix` rather than flattening eagerly into `route.path`) via a recursive flatten helper. Confirms exactly 28 paths / 33 operations, matching permissions throughout, zero undeclared routes.

**Two genuine defects found and fixed** (not present at task start):
1. A pre-existing Phase 6 security test (`test_audit_immutability.py::test_no_platform_audit_path_declared_at_all_yet`) asserted no `/platform/audit` path existed — its own docstring explicitly said "if this ever starts failing because a route now exists, the failure is expected and this assertion should be updated... not silently left stale." Updated to assert the route now exists and is GET-only, consistent with the durable `test_openapi_schema_has_no_mutating_audit_operation` test alongside it.
2. A newly-written dashboard test asserted the AI widget was globally absent — true in isolation, but flaky under the full suite's shared SQLite session once Phase 11's own `test_ai_credits.py` (alphabetically earlier in the same directory) had already inserted real ledger rows. Fixed by removing the flawed cross-file assumption; the dedicated `TestDashboardAiWidgetGatedOnRealData` test already proves the gating deterministically with its own controlled case.

**Testing**: 27 new Phase-13 tests, all passing (real Postgres for everything except the contract-conformance test, which needs `specs/` — not mounted in the Docker container — and runs via the local venv instead, needing no database at all). Full regression: 249/249 passing across the entire Phase 5-13 `platform_admin` suite (both defects caught and fixed via this exact full-suite run, not the isolated per-file runs which had passed misleadingly). 37 cross-module tests (Inventory/CRM/Companies) plus 68 Companies-specific tests confirm the three shared-file changes (`CompanyRepository.list_all()`, `EventOutboxRepository`, `api/v1/router.py`) caused zero regressions elsewhere. mypy --strict and ruff clean on every new/changed file.

**Phase 13 Exit Condition: PASS.** No Gate assigned to Phase 13. Migration head remains `061`. T177's own test is the definitive Epic-wide proof: all 28 contract paths / 33 operations across Phases 4-13 are implemented, correctly permission-gated, with zero undeclared routes anywhere.

## Outcome

- ✅ Impact: Epic 9A's entire backend API surface is now complete and self-verified — every declared contract operation exists, is correctly permission-gated, and no undeclared route was ever introduced across 13 phases of incremental development. Platform Administrators can search/inspect tenants in full 360° detail, view the platform-wide audit trail, see a permission-aware operational dashboard, check platform health, and export scoped reporting data.
- 🧪 Tests: 27 new tests passing; 249/249 full regression passing (real Postgres); 105 cross-module/companies regression tests passing; mypy --strict and ruff clean.
- 📁 Files: 7 new files (4 services, 3 schemas) + 4 new test files, 6 modified files (router.py, dependencies.py, api/v1/router.py, core/events/outbox.py, company_repository.py, test_audit_immutability.py), tasks.md updated.
- 🔁 Next prompts: Phase 14 — Platform Frontend Foundation (T178+) — not started in this session, per the Final Stop Rule. This is the first frontend phase of Epic 9A.
- 🧠 Reflection: Both defects this phase surfaced were found only by re-running the FULL platform_admin suite after making changes that looked correct in isolation — the isolated per-file test runs for both the dashboard test and (implicitly) the pre-existing audit-immutability test would have looked green in a narrower run, reinforcing this Epic's now well-established pattern: shared-fixture leakage and cross-phase test-assumption staleness are only caught by running the broadest regression scope the phase's risk warrants, never by trusting a narrow slice.

## Evaluation notes (flywheel)

- Failure modes observed: (1) FastAPI's routing internals in this installed version wrap every `include_router()` call in a recursive `_IncludedRouter`, not the flat `route.path`-with-prefix-baked-in model from older FastAPI versions — required writing a small recursive prefix-accumulating helper rather than assuming a simpler API. (2) A test file's global-table assumption ("no rows exist anywhere") that's true in isolation but false under a shared-session full-suite run is a now-recurring failure class in this codebase (SQLite `db_session` fixture is explicitly documented as "shared across test functions within a session" but is easy to forget when writing a new test that only checks itself in isolation first).
- Graders run and results (PASS/FAIL): mypy --strict PASS (zero Phase-13-attributable errors); ruff PASS; full Phase-13 + regression test suite PASS (27 new + 249 regression + 105 cross-module, real Postgres) after both fixes.
- Prompt variant (if applicable): n/a — identical master-prompt template as Phases 8-12, Phase Number/Name/Task Range substituted.
- Next experiment (smallest change to try): when writing a new test against a genuinely global (non-tenant-scoped) table, always run the full containing-directory suite once before declaring the test complete, not just the new file in isolation — would have caught the AI-widget flakiness before the full regression run did.
