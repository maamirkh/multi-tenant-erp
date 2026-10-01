---
id: 0021
title: Epic 11 Phase 7 Frontend Foundation
stage: green
date: 2026-09-28
surface: agent
model: claude-opus-5-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: /sp.implement
labels: ["epic-11", "reports-analytics", "frontend", "phase-7"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - frontend/package.json
  - frontend/package-lock.json
  - frontend/src/lib/api/reports.ts
  - frontend/src/lib/format/money.ts
  - frontend/src/lib/format/date.ts
  - frontend/src/lib/format/__tests__/money.test.ts
  - frontend/src/lib/format/__tests__/date.test.ts
  - frontend/src/hooks/reports/useActiveCompanyId.ts
  - frontend/src/hooks/reports/queryKeys.ts
  - frontend/src/hooks/reports/useReportDiscovery.ts
  - frontend/src/hooks/reports/useReport.ts
  - frontend/src/hooks/reports/useDashboard.ts
  - frontend/src/hooks/reports/useCustomer360.ts
  - frontend/src/hooks/reports/useSavedViews.ts
  - frontend/src/components/reports/DataTable.tsx
  - frontend/src/components/reports/PeriodSelector.tsx
  - frontend/src/components/reports/ComparisonSelector.tsx
  - frontend/src/components/reports/FilterBar.tsx
  - frontend/src/components/reports/KpiCard.tsx
  - frontend/src/components/reports/ChartWrapper.tsx
  - frontend/src/components/reports/ExportButton.tsx
  - frontend/src/components/reports/SavedViewSelector.tsx
  - frontend/src/components/reports/DomainReportsShell.tsx
  - frontend/src/components/reports/PageHeader.tsx
  - frontend/src/components/reports/domains.ts
  - frontend/src/components/reports/fieldStyles.ts
  - frontend/src/components/reports/states/ (StateFrame, EmptyState, ErrorState, PermissionDeniedState, ModuleDisabledState, UnavailableState, LoadingState, index)
  - frontend/src/components/layout/ReportsNavSection.tsx
  - frontend/src/components/layout/Sidebar.tsx
  - frontend/src/app/(protected)/(reports)/analytics/ (layout, overview, 6 domain shells, [reportKey], customer-360/[customerId])
  - frontend/src/__tests__/reports/accessibility.test.tsx
  - frontend/src/__tests__/reports/test_nav_discovery.test.tsx
  - specs/011-reports-analytics/tasks.md
tests:
  - npm run test:ci — 45 suites / 241 tests passed
  - npx eslint — 0 errors (0 warnings in Phase 7 files; 55 pre-existing warnings elsewhere)
  - npm run build — passed (plus a temporary code-split probe build, and a clean final rebuild)
  - npx tsc --noEmit — clean
---

## Prompt

# DevSphere ERP SaaS

# Epic 11 — Reports & Analytics

## Compact Reusable Implementation Master Prompt

Implement only the requested Epic 11 phase.

Set:

```text
PHASE_TO_IMPLEMENT = 7
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
PHASE_TO_IMPLEMENT = 7
```

Read the authoritative files, verify prerequisites, implement the full requested phase, run targeted/gate-required checks, produce the required report, and STOP before the next phase.


## Response snapshot

Implemented Phase 7 (T217–T241); Gate 7 PASS.

- Found a genuine conflict with the plan: CRM already owns `/reports` and Accounting owns `/reports/*`, so the planned `(reports)/reports/page.tsx` would collide with an existing route. I stopped and asked; the user chose `/analytics/*`. The route group stays `(reports)`, and the decision is recorded in tasks.md (T225).
- Installed Recharts ^3.10.1 (T217) and jest-axe ^11 + @types/jest-axe (T218) after verifying peer dependencies.
- Added the reports.ts client with the 10 listed methods (the export call returns a binary file), tenant-scoped TanStack hooks that re-key when the active company changes, and display-only money/date formatters.
- Built DataTable, PeriodSelector, ComparisonSelector, the props-driven FilterBar, KpiCard, ChartWrapper (the only Recharts import, with a table alternative), ExportButton, SavedViewSelector, and the five availability states plus an error-to-state classifier.
- Wired a discovery-driven ReportsNavSection into the Sidebar for signed-in users only, and added the Overview, 6 domain, [reportKey] and Customer 360 page shells.
- Bundle evidence: non-Reports pages have 0 Recharts bytes. A temporary probe route proved Recharts is split only into the route that imports ChartWrapper; the probe was then deleted.

## Outcome

- ✅ Impact: The Reports frontend foundation is in place under `/analytics`, and no existing page was modified apart from the one Sidebar insertion.
- 🧪 Tests: 241/241 jest tests, eslint 0 errors, build passing, tsc clean.
- 📁 Files: about 40 new frontend files; package.json, package-lock.json, Sidebar.tsx and tasks.md modified.
- 🔁 Next prompts: Phase 8 (Domain Report Pages), only once authorized.
- 🧠 Reflection: The route collision only surfaced from the real build's route table. The planning docs assumed `/reports` was free.

## Evaluation notes (flywheel)

- Failure modes observed: the plan's frontend route prefix collided with existing CRM/Accounting routes; `exactOptionalPropertyTypes` and `noUncheckedIndexedAccess` needed explicit `| undefined` and indexed-access guards.
- Graders run and results (PASS/FAIL): jest PASS, eslint PASS, build PASS, bundle probe PASS.
- Prompt variant (if applicable): compact master prompt, PHASE_TO_IMPLEMENT=7.
- Next experiment (smallest change to try): Phase 8's gate should re-check Recharts chunk placement now that real pages will import ChartWrapper.
