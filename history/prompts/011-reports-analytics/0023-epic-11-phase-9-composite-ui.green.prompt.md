---
id: 0023
title: Epic 11 Phase 9 Composite UI
stage: green
date: 2026-09-28
surface: agent
model: claude-opus-5-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: /sp.implement
labels: ["epic-11", "reports-analytics", "dashboard", "customer-360", "phase-9"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/components/reports/DashboardWidgets.tsx
  - frontend/src/components/reports/Customer360Sections.tsx
  - frontend/src/app/(protected)/(reports)/analytics/page.tsx
  - frontend/src/app/(protected)/(reports)/analytics/customer-360/[customerId]/page.tsx
  - frontend/src/__tests__/reports/dashboard.test.tsx
  - frontend/src/__tests__/reports/customer-360.test.tsx
  - backend/modules/reports/services/registry_service.py
  - backend/tests/integration/api/v1/reports/postgres/test_discovery_installments_case_b.py
  - specs/011-reports-analytics/tasks.md
tests:
  - npm run test:ci — 48 suites / 284 tests passed
  - npm run build — passed; npx eslint — 0 errors
  - pytest postgres/test_discovery_installments_case_b.py + test_installments_case_a_b_execution.py — 6 passed (real PostgreSQL 16)
  - pytest discovery/registry/installments-gate related tests — 34 passed
  - mypy . — 0 issues / 1479 files; ruff check/format — clean
  - T259 real-browser check (isolated stack, CRM-disabled + Installments Case B tenant) — cross-checked against backend JSON
---

## Prompt

# DevSphere ERP SaaS

# Epic 11 — Reports & Analytics

## Compact Reusable Implementation Master Prompt

Implement only the requested Epic 11 phase.

Set:

```text
PHASE_TO_IMPLEMENT = 9
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
PHASE_TO_IMPLEMENT = 9
```

Read the authoritative files, verify prerequisites, implement the full requested phase, run targeted/gate-required checks, produce the required report, and STOP before the next phase.



## Response snapshot

Implemented Phase 9 (T253–T260); Gate 9 PASS.

- Executive Dashboard: 10 widgets. Omitted widgets are absent, unavailable ones show a neutral card, and present ones show a KpiCard with comparison. The Installments card gets a read-only servicing badge; the WAC disclaimer is always shown.
- Customer 360: 4 sections. Omitted sections render nothing, with no reason text; unavailable ones show "not configured". 404/422 go to the standard `notFound()`, and nothing identifying renders before the backend confirms the customer.
- Tests: dashboard (6) and customer-360 (8), covering the exact card counts, IDOR no-flash, byte-identical 404 pages, and axe.
- T259 real browser against an isolated stack with a CRM-disabled + Case B tenant: the UI matched the backend JSON exactly.
- It also exposed a genuine Phase 3 defect: discovery hid all Installments keys under Case B even though execution serves the 5 allow-listed ones. Fixed with the smallest change: discovery now uses the same continuity gate. Added a real-Postgres regression test, re-verified in the browser, and recorded the correction at T130 and T259.

## Outcome

- ✅ Impact: The composite UIs are complete, and discovery now agrees with execution under Installments Case B.
- 🧪 Tests: 284/284 jest tests, build passing, eslint 0 errors, 6 Postgres + 34 related backend tests passing, mypy/ruff clean.
- 📁 Files: 4 new frontend files and 2 modified pages; 1 backend service fix plus 1 new Postgres test; tasks.md.
- 🔁 Next prompts: Phase 10 (hardening), only once authorized.
- 🧠 Reflection: Discovery and execution applied different rules for the same entitlement state. Only a real end-to-end browser run showed it.

## Evaluation notes (flywheel)

- Failure modes observed: discovery diverged from execution under Case B (fixed); the static Customer 360 description named an omitted domain (fixed).
- Graders run and results (PASS/FAIL): jest PASS, build PASS, eslint PASS, pytest (PG) PASS, mypy/ruff PASS, browser check PASS.
- Prompt variant (if applicable): compact master prompt, PHASE_TO_IMPLEMENT=9.
- Next experiment (smallest change to try): a property test asserting discovery == executable keys across every entitlement state.
