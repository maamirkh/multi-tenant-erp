---
id: 0024
title: Epic 11 Phase 10 Hardening
stage: green
date: 2026-09-29
surface: agent
model: claude-opus-5-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: /sp.implement
labels: ["epic-11", "reports-analytics", "security", "postgres", "performance", "phase-10"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/tests/security/reports/{phase10_support,test_full_entitlement_matrix,test_full_rbac_matrix,test_tenant_isolation_comprehensive,test_platform_admin_boundary,test_support_access_boundary}.py
  - backend/tests/integration/migrations/test_full_migration_chain.py
  - backend/tests/performance/reports/{test_customer_360_explain,test_no_n_plus_one,test_representative_scale}.py
  - backend/tests/integration/api/v1/reports/postgres/test_decimal_precision_postgres.py
  - backend/tests/unit/modules/reports/test_group_by_cardinality_documented.py
  - backend/tests/unit/modules/sales/test_customer_names_by_ids_seam.py
  - backend/migrations/versions/078_reports_customer_360_index.py
  - backend/modules/installments/models/schedule.py
  - backend/modules/sales/repositories/customer.py
  - backend/modules/reports/services/adapters/sales_adapter.py
  - backend/modules/{sales,purchase,inventory}/services/report_service.py
  - backend/modules/inventory/repositories/alerts_repository.py
  - backend/modules/accounting/repositories/{banking,cash}.py
  - backend/modules/installments/repositories/{contract,schedule,audit,allocation_reference}.py
  - backend/modules/reports/registry/catalog_*.py
  - backend/modules/reports/docs/multi_currency_findings.md
  - backend/tests/integration/api/v1/reports/postgres/conftest.py
  - specs/011-reports-analytics/tasks.md
tests:
  - T261 7, T262 4, T263 4, T264 4, T265 3 passed
  - T266 2 + test_077 migration 2 passed (real PostgreSQL)
  - T267 10 passed (0 discrepancies)
  - T268 EXPLAIN harness 1 passed (Branch B, migration 078)
  - T269 16 passed + Sales seam 4 passed
  - T270 13 passed (real PostgreSQL, tie-heavy data)
  - T271 2 passed; T272 1 passed (real PostgreSQL)
  - mypy . 0 issues / 1494 files; ruff check + format clean
  - Repo-wide pytest --cov-fail-under=80 — NOT completed locally (I/O-bound, est. 5–10+ h); moved to GitHub CI per user decision
---

## Prompt

# DevSphere ERP SaaS

# Epic 11 — Reports & Analytics

## Compact Reusable Implementation Master Prompt

Implement only the requested Epic 11 phase.

Set:

```text
PHASE_TO_IMPLEMENT = 10
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
PHASE_TO_IMPLEMENT = 10
```

Read the authoritative files, verify prerequisites, implement the full requested phase, run targeted/gate-required checks, produce the required report, and STOP before the next phase.



## Response snapshot

Implemented Phase 10 (T261–T273, T275). T274 and the Gate 10 repo-wide coverage run are pending CI.

- Security matrices: the full entitlement matrix across 7 families (real Plan-ceiling toggles), all 16 permission codes each granted alone, comprehensive tenant isolation, and the Platform Admin and support-access boundaries all pass.
- Migration chain 073→078 on real Postgres passes; the financial invariants re-run with zero discrepancies.
- Four genuine defects were found and fixed, each with user approval:
  1. T268 EXPLAIN evidence showed a missing index on `installment_schedule_lines.company_id`, which made Installments reads scan every tenant's rows. Added migration 078 plus the model Index.
  2. T269 found an N+1 in the Sales customer-name lookup. Added the additive Sales seam `get_names_by_ids` and batched the lookup.
  3. T270 found that offset pagination duplicated or skipped rows at scale because source queries had no unique tiebreaker. Added additive ORDER BY tiebreakers across all six domains; 13/13 scale tests now pass.
  4. T273 found that FR-RPT-152 (multi-currency) is not met for Sales/Purchase/Inventory/CRM aggregates. Documented it as an open product decision.
- T275: the Epic 11 range is additive only, with every Phase 10 addition recorded.
- The local full-suite run was I/O-bound on the WSL/Windows-drive Docker Postgres. The user chose GitHub CI; its trigger requires a PR to main.

## Outcome

- ✅ Impact: Epic 11 is hardened. Security is verified; pagination, performance and index defects are fixed with evidence.
- 🧪 Tests: every Phase 10 targeted test is green; mypy and ruff are clean. The repo-wide coverage gate is pending CI.
- 📁 Files: 13 new test/support files, 1 migration, 1 doc; 20 modified backend files, all additive.
- 🔁 Next prompts: get the CI result (draft PR to main needed), then record T274/T276; Phase 11 only once authorized.
- 🧠 Reflection: realistic scale and tie-heavy data exposed defects that small fixtures never would.

## Evaluation notes (flywheel)

- Failure modes observed: nondeterministic ORDER BY across modules; N+1; missing tenant index; FR-RPT-152 gap; xdist aborted because Sales test parameter IDs are random; local Postgres I/O too slow for the full suite.
- Graders run and results (PASS/FAIL): targeted suites PASS; mypy/ruff PASS; repo-wide coverage PENDING (CI).
- Prompt variant (if applicable): compact master prompt, PHASE_TO_IMPLEMENT=10.
- Next experiment (smallest change to try): add a workflow_dispatch trigger to backend CI so feature branches can run the gate without a PR.
