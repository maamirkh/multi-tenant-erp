---
id: 0019
title: Epic 11 Phase 6 Exports and Audit
stage: green
date: 2026-09-28
surface: agent
model: claude-opus-5-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: /sp.implement
labels: ["epic-11", "reports-analytics", "exports", "audit", "phase-6"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/migrations/versions/077_reports_audit_log_table.py
  - backend/modules/reports/constants.py
  - backend/modules/reports/models/__init__.py
  - backend/modules/reports/models/reports_audit_log.py
  - backend/modules/reports/registry/catalog_accounting.py
  - backend/modules/reports/repositories/reports_audit_repository.py
  - backend/modules/reports/repositories/saved_report_view.py
  - backend/modules/reports/router.py
  - backend/modules/reports/schemas/export.py
  - backend/modules/reports/services/audit_service.py
  - backend/modules/reports/services/export_service.py
  - backend/modules/reports/services/export_writers.py
  - backend/modules/reports/services/saved_view_service.py
  - backend/modules/reports/services/adapters/base.py
  - backend/modules/reports/services/adapters/accounting_adapter.py
  - backend/modules/reports/services/adapters/crm_adapter.py
  - backend/modules/reports/services/adapters/installments_adapter.py
  - backend/modules/reports/services/adapters/inventory_adapter.py
  - backend/modules/reports/services/adapters/purchase_adapter.py
  - backend/modules/reports/services/adapters/sales_adapter.py
  - backend/tests/integration/api/v1/reports/conftest.py
  - backend/tests/integration/api/v1/reports/postgres/conftest.py
  - backend/tests/integration/api/v1/reports/gl_export_support.py
  - backend/tests/integration/api/v1/reports/postgres/test_category_b_export.py
  - backend/tests/integration/api/v1/reports/test_aggregate_export.py
  - backend/tests/integration/api/v1/reports/test_csv_injection_export.py
  - backend/tests/integration/api/v1/reports/test_export_audit_failure_blocks_delivery.py
  - backend/tests/integration/api/v1/reports/test_export_audit_once.py
  - backend/tests/integration/api/v1/reports/test_export_empty_result.py
  - backend/tests/integration/api/v1/reports/test_export_field_parity.py
  - backend/tests/integration/api/v1/reports/test_export_permission_separation.py
  - backend/tests/integration/api/v1/reports/test_export_row_limit.py
  - backend/tests/integration/api/v1/reports/test_export_scope_matches_online.py
  - backend/tests/integration/api/v1/reports/test_gl_export_cursor_continuity.py
  - backend/tests/integration/api/v1/reports/test_gl_export_limit_plus_one_abort.py
  - backend/tests/integration/api/v1/reports/test_saved_view_audit.py
  - backend/tests/integration/api/v1/reports/test_xlsx_row_limit_independent.py
  - backend/tests/integration/migrations/test_077_reports_audit_log.py
  - backend/tests/unit/modules/reports/test_audit_service_staging.py
  - backend/tests/unit/modules/reports/test_export_bounded_retrieval.py
  - backend/tests/unit/modules/reports/test_export_memory_benchmark.py
  - backend/tests/unit/modules/reports/test_no_direct_dispatch_including_export.py
  - specs/011-reports-analytics/tasks.md
tests:
  - Gate 6 consolidated SQLite run (Phase 6 tests + T215 seam regressions + registry/dispatch/saved-view security) — 110 passed, 6 skipped (opt-in benchmark)
  - Real PostgreSQL 16 — test_077_reports_audit_log.py (2) + postgres/test_category_b_export.py (3) — 5 passed
  - Existing Reports Postgres suite at head 077 — 12 passed
  - T213 benchmark (REPORTS_EXPORT_BENCHMARK=1) — 6 passed, numbers recorded
  - Existing Reports unit/integration/security suites — 340 passed, 1 failed (documented pre-existing T144 ordering flake; passes in isolation)
  - mypy . — 0 issues / 1478 files; ruff check . and ruff format --check . — clean
---

## Prompt

# DevSphere ERP SaaS

# Epic 11 — Reports & Analytics

## Compact Reusable Implementation Master Prompt

Implement only the requested Epic 11 phase.

Set:

```text
PHASE_TO_IMPLEMENT = 6
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

Return:

# Epic 11 Implementation Report — Phase <N>

### A. Phase

* Phase:
* Task range:
* Gate:
* Status: PASS / BLOCKED

### B. Tasks

List each task and status.

### C. Files

* Created:
* Modified:
* Deleted:

### D. Database

* Migrations created/modified:
* Current/down revision:
* Real PostgreSQL used: yes/no

### E. Architecture & Security

Report relevant items only:

* tenant isolation
* RBAC
* entitlements
* service/repository boundaries
* bounded pagination/export
* audit/security behavior

Use `PASS` or `N/A`.

### F. Tests Run

For every command actually run:

```text
command:
result:
passed:
failed:
```

Separate:

* targeted phase tests;
* gate-required static checks;
* targeted PostgreSQL tests;
* targeted frontend tests.

### G. Deferred Final Tests

For Phases 0–10 state explicitly:

```text
Full repository regression was intentionally not run in this phase.
It is reserved for Phase 11 except where an earlier gate explicitly requires a broader check.
```

### H. Type/Lint

Report only what was actually run:

```text
mypy:
ruff:
format:
frontend lint:
```

Use `PASS` or `NOT REQUIRED THIS PHASE`.

### I. Backward Compatibility

* Existing domain behavior unintentionally changed: yes/no
* Unrelated refactors: yes/no

### J. Gate

State exact gate evidence and:

```text
Gate <N>: PASS
```

or:

```text
Gate <N>: BLOCKED
```

### K. Git

* Branch:
* Working tree:
* Unexpected files changed: yes/no

### L. Issues

* Blocking issues:
* Non-blocking observations:

### M. Next Step

If PASS:

```text
Phase <N> is complete.
STOPPED before the next phase.
Waiting for explicit authorization.
```

For Phase 11:

```text
Epic 11 implementation and final regression are complete.
```

---

## 15. Accuracy Rule

Never claim a check passed unless it actually ran.

For Phases 0–10 use precise wording such as:

```text
Targeted phase tests passed.
Full repository regression intentionally deferred to Phase 11.
```

Do not say:

```text
Full regression passed.
```

unless the full regression actually ran.

---

# START

Now implement:

```text
PHASE_TO_IMPLEMENT = 6
```

Read the authoritative files, verify prerequisites, implement the full requested phase, run targeted/gate-required checks, produce the required report, and STOP before the next phase.

## Response snapshot

Implemented Phase 6 (T178–T216) in full; Gate 6 PASS.

- Audit persistence: `ReportsAuditLog` model, migration `077_reports_audit_log_table.py` (renumbered from the task's `076`, which Phase 1 already holds — same precedent as T040), stage-only `ReportsAuditRepository`, `ReportsAuditService.record()`; saved-view create/update/delete now stage write + audit and commit once.
- `ReportExportService.export()`: reuses `_authorize_and_validate(permission_kind="export")`, checks `export_formats`, then per category — A/B count-then-iterate (reject before any batch), GL limit+1 (stops pulling cursor pages the moment limit+1 is seen), D aggregate single `run()` flattened to field/value, PDF delegated to `AccountingAdapter.export_pdf()`. Audit is staged and committed after the bytes are built; a commit failure rolls back and raises `ExportAuditPersistenceError` so no file goes out.
- CSV/XLSX writers (XLSX in `write_only` mode): every text cell is sanitized. Typed numbers are written as numbers so negative amounts stay numeric.
- `GET /{report_key}/export` route, which calls only the export service.
- Two small corrections to earlier phases, both reported: AR/AP aging registry formats changed from (PDF, XLSX) to (CSV, XLSX), because the adapter cannot produce an aging PDF; and a typed `export_row_model()` method added to the adapter Protocol so an empty result can still write its headers.
- Benchmarked and locked the limits: CSV 50K, XLSX 25K, batch 1,000.

## Outcome

- ✅ Impact: Exports ship with no delivery unless the audit row is committed first. All four categories are bounded. CSV/XLSX are protected against formula injection. `.view` and `.export` permissions are enforced separately.
- 🧪 Tests: Gate 6 SQLite 110 passed / 0 failed; real Postgres 5 + 12 passed; T215 12 passed; `mypy .` 0; ruff clean.
- 📁 Files: 7 new production files, 13 modified production files, 20 new test files and helpers, 2 test conftests updated, tasks.md.
- 🔁 Next prompts: Phase 7 (Frontend Foundation), only once authorized.
- 🧠 Reflection: The empty-result header requirement and the PDF-eligibility mismatch only surfaced once the export path actually ran against the registry. Both were fixed where they originated, with the smallest change.

## Evaluation notes (flywheel)

- Failure modes observed: migration number collision in tasks.md (076 taken); registry export formats advertised PDF for keys the adapter cannot render; a pre-existing SQLite seed-ordering flake (T144) recurred.
- Graders run and results (PASS/FAIL): targeted pytest SQLite + real Postgres PASS; mypy . PASS; ruff check/format PASS.
- Prompt variant (if applicable): compact reusable master prompt, PHASE_TO_IMPLEMENT=6.
- Next experiment (smallest change to try): add a registry-consistency assertion that every `ExportFormat.PDF` entry is in the adapter's PDF-eligible set, so this kind of drift is caught statically.
