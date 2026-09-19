---
id: 0012
title: Epic 11 Phase 2 Domain Adapters Implementation
stage: green
date: 2026-09-13
surface: agent
model: claude-sonnet-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: /sp.implement
labels: ["epic-11", "reports-analytics", "phase-2", "domain-adapters", "registry", "gate-2"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/accounting/repositories/ar.py
 - backend/modules/accounting/repositories/ap.py
 - backend/modules/accounting/repositories/banking.py
 - backend/modules/accounting/repositories/cash.py
 - backend/modules/accounting/services/ar_service.py
 - backend/modules/accounting/services/ap_service.py
 - backend/modules/accounting/services/bank_service.py
 - backend/modules/accounting/services/cash_service.py
 - backend/modules/purchase/services/report_service.py
 - backend/modules/inventory/services/report_service.py
 - backend/modules/inventory/repositories/alerts_repository.py
 - backend/modules/reports/schemas/accounting.py
 - backend/modules/reports/schemas/sales.py
 - backend/modules/reports/schemas/purchase.py
 - backend/modules/reports/schemas/inventory.py
 - backend/modules/reports/schemas/crm.py
 - backend/modules/reports/schemas/installments.py
 - backend/modules/reports/schemas/pagination.py
 - backend/modules/reports/services/adapters/base.py
 - backend/modules/reports/services/adapters/accounting_adapter.py
 - backend/modules/reports/services/adapters/sales_adapter.py
 - backend/modules/reports/services/adapters/purchase_adapter.py
 - backend/modules/reports/services/adapters/inventory_adapter.py
 - backend/modules/reports/services/adapters/crm_adapter.py
 - backend/modules/reports/services/adapters/installments_adapter.py
 - backend/modules/reports/services/installments_continuity_gate.py
 - backend/modules/reports/registry/catalog_accounting.py
 - backend/modules/reports/registry/catalog_sales.py
 - backend/modules/reports/registry/catalog_purchase.py
 - backend/modules/reports/registry/catalog_inventory.py
 - backend/modules/reports/registry/catalog_crm.py
 - backend/modules/reports/registry/catalog_installments.py
 - backend/modules/reports/registry/catalog_crossmodule.py
 - backend/modules/reports/registry/load_all.py
 - backend/tests/unit/modules/reports/ (35 new test files across all 6 domains)
 - backend/tests/unit/modules/accounting/test_accounting_seam_backward_compat.py
 - backend/tests/unit/modules/accounting/test_accounting_equivalence_ar_ap.py
 - backend/tests/unit/modules/accounting/test_accounting_equivalence_bankcash_kpi.py
 - backend/tests/unit/modules/purchase/test_purchase_service_backward_compat.py
 - backend/tests/unit/modules/inventory/test_inventory_service_backward_compat.py
 - backend/tests/integration/api/v1/installments/test_installments_accounting_reconciliation.py
tests:
 - tests/unit/modules/reports/ (200 tests, all passing)
 - tests/unit/modules/accounting/test_accounting_seam_backward_compat.py
 - tests/unit/modules/purchase/test_purchase_service_backward_compat.py
 - tests/unit/modules/inventory/test_inventory_service_backward_compat.py
 - tests/integration/api/v1/inventory/test_reports_api.py (29, pre-existing regression)
 - tests/integration/api/v1/installments/test_reporting_service.py (16, real Postgres, pre-existing regression)
 - tests/integration/api/v1/installments/test_installments_accounting_reconciliation.py (1, real Postgres)
 - mypy . (1410 files, 0 errors)
 - ruff check . (all checks passed)
---

## Prompt

```text
# DevSphere ERP SaaS

# Epic 11 — Reports & Analytics

## Compact Reusable Implementation Master Prompt

Implement only the requested Epic 11 phase.

Set:

```text
PHASE_TO_IMPLEMENT = 2
```
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

[Full report structure — see tasks.md and CLAUDE.md for the exact template]

---

## 15. Accuracy Rule

Never claim a check passed unless it actually ran.

---

# START

Now implement:

```text
PHASE_TO_IMPLEMENT = 2
```

Read the authoritative files, verify prerequisites, implement the full requested phase, run targeted/gate-required checks, produce the required report, and STOP before the next phase.
```

## Response snapshot

Implemented Epic 11 Phase 2 (Domain Adapters, T047–T125) in full across all 6 sub-phases (Accounting, Sales, Purchase, Inventory, CRM, Installments) plus the Deferred Stubs & Gate 2 close-out. This PHR covers the Inventory/CRM/Installments/Gate-2 tail of the phase completed in this session (Accounting/Sales/Purchase sub-phases were completed in prior turns of the same phase-2 execution, summarized in the conversation history).

Key work this session:
- **Inventory (T087–T099)**: additive `limit`/`offset`+count-sibling seam on `dead_stock`/`movement_velocity`/`stock_aging` plus `count_for_company` on both alert repos; `InventoryAdapter` (8 reports — `stock_position` deliberately backed by the already-bounded `stock_ledger` rather than the unbounded `stock_position_report`, a documented design correction); `valuation_basis="operational_wac"` injected by the adapter; full contract/equivalence/disclaimer/export-seam test coverage; Sub-Gate 2D green.
- **CRM (T100–T107)**: all 4 reports aggregate-shaped, `CrmAdapter` reusing `CrmReportingService`'s existing Pydantic schemas verbatim; `test_crm_disabled_no_exception.py` proves CRM's `require_crm_enabled` gate has no servicing-continuity carve-out (contrasted against Installments); discovered and fixed a genuine pre-existing bug in `test_registry_consistency.py`'s `_resolve_callable` (only resolved bare `module.function` paths, not `module.Class.method`) while building this test; Sub-Gate 2E green.
- **Installments (T108–T121)**: `InstallmentsServicingContinuityGate` (pure, DB-free, fully unit-tested state machine — Case A/B); `InstallmentsAdapter` with an AST-scan-verified zero-entitlement-logic boundary; `due_overdue`/`aging`/`settlement_writeoff` combine two service methods each via bounded-population-then-slice; `branch_id` accepted on the 5 contract-linked filters but transparently documented as inert in Phase 2 (Installments is not one of the 3 sanctioned source-seam modules); real-Postgres cross-module reconciliation test proving Installments' aging and Accounting's AR aging agree on outstanding amount; Sub-Gate 2F green.
- **Deferred Stubs & Gate 2 (T122–T125)**: `accounting.tax`/`accounting.cost_center_pl` (already registered during the Accounting sub-phase) + new `crossmodule.branch_performance` DEFERRED entry; `modules/reports/registry/load_all.py` created as the single explicit entry point that imports all 7 catalogs — deliberately **not** placed in `registry/__init__.py` itself after that approach produced a genuine circular import (`base.py` → `registry.definitions` → package `__init__` → catalogs → adapters → `base.py`), caught by actually running the full test suite; `test_deferred_catalog_unreachable.py`; Gate 2 verified: exactly 43 NOW (8+7+8+9+4+7) all ADAPTER, exactly 3 DEFERRED, all 6 sub-gates green, `mypy . = 0`, `ruff` clean, 200/200 Reports tests passing.

Phase 2 is now complete. Stopped per the master prompt's instruction, awaiting explicit authorization before Phase 3.

## Outcome

- ✅ Impact: Epic 11 Phase 2 (Domain Adapters) fully implemented and gated — all 43 "Now" reports across 6 domains are reachable through typed, stateless `ReportAdapter` implementations; the Report Registry is complete and internally consistent.
- 🧪 Tests: 200/200 Reports unit tests pass; 3 source-domain seam backward-compat suites pass (Accounting/Purchase/Inventory); pre-existing Inventory (29) and Installments (16, real Postgres) regression suites unaffected; 1 real-Postgres cross-module reconciliation test passes; `mypy .` clean across 1410 files; `ruff check .` clean.
- 📁 Files: ~33 new/modified files under `backend/modules/reports/`, 8 domain-service files given additive bounded-read seams (Accounting ×8, Purchase ×1 restructure, Inventory ×2), 35 new Reports test files plus 6 cross-domain regression/reconciliation tests.
- 🔁 Next prompts: Await explicit authorization, then `/sp.implement PHASE_TO_IMPLEMENT = 3` (Unified Execution API).
- 🧠 Reflection: Two genuine, transparently-reported defects were discovered and fixed mid-phase: (1) `test_registry_consistency.py`'s `_resolve_callable` couldn't resolve class-qualified dotted paths — invisible until real entries existed; (2) an eager `registry/__init__.py` catalog import created a circular import with `adapters/base.py` — resolved via a dedicated `load_all.py` module instead.

## Evaluation notes (flywheel)

- Failure modes observed: two structural test/wiring bugs surfaced only once the full 46-entry registry was actually exercised (empty-registry testing throughout the phase had been masking both).
- Graders run and results (PASS/FAIL): mypy PASS, ruff PASS, full Reports unit suite PASS (200/200), all 6 sub-gates PASS, Gate 2 shape assertion PASS.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a — awaiting Phase 3 authorization.
