---
id: 0016
title: Epic 11 Phase 4 Executive Dashboard
stage: green
date: 2026-09-18
surface: agent
model: claude-sonnet-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: /sp.implement
labels: ["epic-11", "reports-analytics", "executive-dashboard", "phase-4"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/reports/schemas/dashboard.py
  - backend/modules/reports/metrics/definitions.py
  - backend/modules/reports/services/dashboard_service.py
  - backend/modules/reports/services/date_range_service.py
  - backend/modules/reports/services/adapters/accounting_adapter.py
  - backend/modules/reports/registry/catalog_executive.py
  - backend/modules/reports/registry/load_all.py
  - backend/modules/reports/router.py
  - backend/tests/unit/modules/reports/test_metric_catalog_distinct_names.py
  - backend/tests/unit/modules/reports/test_registry_consistency.py
  - backend/tests/integration/api/v1/reports/conftest.py
  - backend/tests/integration/api/v1/reports/test_dashboard_graceful_degradation.py
  - backend/tests/integration/api/v1/reports/test_dashboard_installments_exception.py
  - backend/tests/integration/api/v1/reports/postgres/test_dashboard_installments_case_b.py
  - backend/tests/integration/api/v1/reports/test_dashboard_zero_and_single_module.py
  - backend/tests/integration/api/v1/reports/test_dashboard_known_prerequisite_unavailable.py
  - backend/tests/integration/api/v1/reports/test_dashboard_unexpected_error_propagates.py
  - backend/tests/integration/api/v1/reports/test_dashboard_no_leak.py
  - backend/tests/integration/api/v1/reports/test_dashboard_comparison.py
  - backend/tests/integration/api/v1/reports/test_execute_endpoint_envelopes.py
  - specs/011-reports-analytics/tasks.md
tests:
  - pytest tests/unit/modules/reports/ (53 passed)
  - pytest tests/integration/api/v1/reports/ --ignore=postgres (317 passed, 1 pre-existing documented flake)
  - mypy modules/reports/ (0 errors, 57 files)
  - mypy tests/unit/modules/reports/ tests/integration/api/v1/reports/ (0 errors, 25 files)
  - ruff check / ruff format --check (clean on all touched files)
---

## Prompt

# DevSphere ERP SaaS

# Epic 11 — Reports & Analytics

## Compact Reusable Implementation Master Prompt

Implement only the requested Epic 11 phase.

Set:

```text
PHASE_TO_IMPLEMENT = 4
```

[Full compact reusable master prompt as supplied by the user via /sp.implement,
covering: authoritative sources to read, scope (implement only the requested
phase, stop before the next), prerequisite-check requirements, architecture
rules (tenant isolation, RBAC, entitlements, router→service→repository
boundaries, no cross-tenant fallback, no Branch authorization, no Deferred
reports, no AI/LLM work), type/financial safety (mypy=0, no Any/unsafe casts,
Decimal-only arithmetic), the sanctioned source-domain seams (T047 Accounting,
T075 Purchase, T087 Inventory — no others), the 8-step implementation method,
the Phase 0–10 testing strategy (targeted tests only, full regression deferred
to Phase 11), failure rules (stop on tenant/security failure), git rules, the
required Phase N final report format (sections A–M), and the accuracy rule
never to claim an unrun check passed. Ends with: "Now implement:
PHASE_TO_IMPLEMENT = 0. Read the authoritative files, verify prerequisites,
implement the full requested phase, run targeted/gate-required checks, produce
the required report, and STOP before the next phase."]

## Outline

[/sp.implement's standard 9-step workflow: run check-prerequisites.sh,
check checklist status, load spec/plan/tasks/data-model/contracts/quickstart,
verify ignore files, parse tasks.md phases/dependencies, execute
phase-by-phase respecting [P] markers and TDD ordering, mark completed tasks
[X], validate final coverage against the spec.]

## User Input

(verbatim, matches the "Prompt" section content above in full — the compact
reusable Epic 11 Phase 4 implementation master prompt.)

## Response snapshot

Verified prerequisites: Phases 0–3 (T001–T144) all marked `[x]` in tasks.md
and independently confirmed present on disk (`backend/modules/reports/`
fully populated through the execution API). Checklist `requirements.md`
39/39 complete. Read spec.md §10/§13, plan.md §7/§8/§33, and every existing
Phase 2/3 adapter/service file needed to source each of the 10 dashboard
widgets from an already-authoritative domain call (never a locally
re-derived formula).

Implemented Phase 4 (T145–T159):
- `schemas/dashboard.py` — `WidgetState` (3 values, defined once) + 10
  typed widget schemas + `ExecutiveDashboardResponse` + `DashboardFilter`
  registry placeholder.
- `metrics/definitions.py` — `MetricDefinition` + 16-entry `METRIC_CATALOG`
  mirroring spec §10 verbatim.
- `services/dashboard_service.py` — `ExecutiveDashboardService.get()`:
  each widget independently gates on domain entitlement + `reports.<domain>
  .view`, then calls its metric's existing adapter method via
  `ADAPTER_REGISTRY`; per-widget `except UnavailablePrerequisiteError` only
  (T156's non-contradictory rule verified); comparison computed by calling
  the same adapter method twice (current + `resolve_comparison_period()`)
  through T024's `compute_comparison` — never a domain's own internal
  trend field, per T158.
- Extended `date_range_service.py` with `resolve_comparison_period()`.
- `registry/catalog_executive.py` registers `exec.dashboard`
  (`execution_kind=COMPOSITE`) and wires `COMPOSITE_REPORT_HANDLERS`.
- `GET /reports/dashboard` route (registered before the `/{report_key}`
  catch-all), gated by `reports.executive.view`.
- 8 new integration tests (T152–T158) + 1 unit test (T147).

Two genuine implementation-time defects were found and fixed with the
smallest necessary correction, both documented inline in tasks.md and in
code comments:
1. A bound-method identity gotcha (`instance.method is instance.method`
   is `False` in Python) would have broken T032's registry-consistency
   identity check for the new `COMPOSITE` entry — fixed by pinning the
   bound method to a stable module-level name (`get_dashboard`).
2. `AccountingAdapter`'s `accounting.kpis` branch let Accounting's own
   "not configured" `PostingValidationError` propagate uncaught; since 4
   of the 10 widgets now share that one call, an unconfigured company
   would 5xx the whole dashboard instead of rendering a defined
   `UNAVAILABLE` state (violating FR-RPT-044) — fixed by catching it and
   re-raising `UnavailablePrerequisiteError`, exactly the translation that
   exception's own pre-existing docstring already named as its purpose.

Two pre-existing Phase 3 tests needed scope corrections once a 44th,
`COMPOSITE`-kind registry entry existed for the first time (`exec.dashboard`
correctly 404s via the generic execution path, which older tests didn't
anticipate): `test_execute_endpoint_envelopes.py`'s `_now_definitions()`
scoped to `execution_kind == ADAPTER`; `test_registry_consistency.py`'s
`test_gate_2_registry_shape` renamed/extended to `test_gate_4_registry_shape`
(43 ADAPTER + 1 COMPOSITE = 44 NOW), Gate 2's own per-domain counts
preserved verbatim inside it.

Installments' Case B fixture (`build_active_contract_with_schedule`) relies
on Postgres-only `server_default=text("now()")` columns — split T153 into
a SQLite Case A test (this session) and a real-Postgres Case B test
(`postgres/test_dashboard_installments_case_b.py`), matching the identical,
already-established precedent for this same fixture in
`test_installments_case_a_b_execution.py` (T142). No local Postgres was
available in this sandbox, so the Postgres-tagged test could not be
executed — reported as deferred, not claimed as passing.

Targeted evidence: 53/53 new/Phase-0-3 unit tests pass; 317/318
non-Postgres integration tests pass (the one failure,
`test_entitlement_roundtrip.py::test_reports_capability_is_seeded`, is the
identical cross-test SQLite state-leak flake T144 already documented as
pre-existing and out of scope — independently reconfirmed passing in
isolation, twice). `mypy modules/reports/` and `mypy` on every touched test
file: 0 errors. `ruff check`/`ruff format --check`: clean on every file
touched this phase. Full repository regression intentionally not run
(reserved for Phase 11 per the master prompt's testing strategy).

Marked T145–T159 `[x]` in tasks.md with implementation notes; Gate 4
declared PASS. Stopped before Phase 5 pending explicit authorization.

## Outcome

- ✅ Impact: Executive Dashboard (`GET /reports/dashboard`) implemented end
  to end — 10 independently-gated widgets composing the 16-entry metric
  catalog, all sourced from existing Phase 2 domain adapters with zero
  re-derived formulas; `exec.dashboard` registered as the epic's first
  `COMPOSITE`-kind report. Registry: 44 NOW (43 ADAPTER + 1 COMPOSITE) + 3
  DEFERRED.
- 🧪 Tests: 53 unit + 317/318 integration passing (1 pre-existing documented
  flake, reconfirmed non-regression); 1 real-Postgres test written but not
  runnable in this sandbox. mypy/ruff clean.
- 📁 Files: 3 new service/schema modules, 1 new registry catalog, 2 existing
  Phase 0–3 files extended (date_range_service.py, accounting_adapter.py),
  1 pre-existing router extended, 9 new test files, 2 pre-existing Phase 3
  test files corrected for the new registry shape, tasks.md updated.
- 🔁 Next prompts: Phase 5 (Customer 360) on explicit authorization.
- 🧠 Reflection: The two "genuine defect" fixes (bound-method identity,
  PostingValidationError translation) were both foreseeable only by
  actually tracing call graphs into already-implemented Phase 2 code
  rather than trusting the compact task summary's literal wording —
  consistent with every earlier phase's own documented pattern of
  discovering real gaps only once a later phase's composition actually
  exercises an earlier phase's code path for the first time.

## Evaluation notes (flywheel)

- Failure modes observed: a naive reading of T151 ("`COMPOSITE_REPORT_HANDLERS
  ["exec.dashboard"] = dashboard_service.get`") would have shipped a
  registry-consistency test failure at Gate 4, since Python bound-method
  access does not preserve object identity across separate evaluations.
- Graders run and results (PASS/FAIL): targeted pytest + mypy + ruff — PASS
  (see files/tests above); full regression deliberately deferred to Phase 11.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): when Phase 5 registers
  `crossmodule.customer_360` as a second `COMPOSITE` entry, apply the same
  pinned-module-level-name pattern established here for `get_dashboard`.
