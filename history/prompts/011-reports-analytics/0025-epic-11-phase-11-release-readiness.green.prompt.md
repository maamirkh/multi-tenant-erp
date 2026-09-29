---
id: 0025
title: Epic 11 Phase 11 Release Readiness
stage: green
date: 2026-09-29
surface: agent
model: claude-opus-5-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: /sp.implement
labels: ["epic-11", "reports-analytics", "release-readiness", "e2e", "docker", "adr", "phase-11"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: history/adr/0005-static-code-defined-report-registry.md, history/adr/0006-section-level-compound-authorization-for-composite-read-models.md
  pr: https://github.com/maamirkh/multi-tenant-erp/pull/9 (draft, CI only)
files:
  - frontend/e2e/reports-smoke.spec.ts
  - frontend/src/components/reports/DashboardWidgets.tsx
  - frontend/src/components/reports/domains.ts
  - frontend/src/__tests__/reports/dashboard.test.tsx
  - frontend/Dockerfile
  - backend/modules/reports/docs/README.md
  - history/adr/0005-static-code-defined-report-registry.md
  - history/adr/0006-section-level-compound-authorization-for-composite-read-models.md
  - specs/011-reports-analytics/release-signoff.md
  - specs/011-reports-analytics/tasks.md
  - CLAUDE.md
tests:
  - T277 ruff check + format --check clean (1494 files)
  - T278 mypy . 0 issues / 1494 files
  - T279 full backend suite + coverage — GitHub CI run 36567160552 (commit 5b7c289; backend code unchanged since)
  - T280 bandit -ll 1 pre-existing HIGH (B324, on main); pip-audit 3 pre-existing advisories (poetry.lock unchanged)
  - T281 alembic upgrade head on empty DB — 78 revisions 001→078, 16 s
  - T282 frontend lint 0 errors / Jest 48 suites 285 tests / next build green
  - T283 Playwright reports-smoke 2/2 runs green
  - T284 docker build --target production backend + frontend green (frontend after Dockerfile fix)
  - T285 consolidated security regression 106 passed, 0 failed
---

## Prompt

# DevSphere ERP SaaS

# Epic 11 — Reports & Analytics

## Compact Reusable Implementation Master Prompt

Implement only the requested Epic 11 phase.

Set:

```text
PHASE_TO_IMPLEMENT = 11
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
PHASE_TO_IMPLEMENT = 11
```

Read the authoritative files, verify prerequisites, implement the full requested phase, run targeted/gate-required checks, produce the required report, and STOP before the next phase.

### Mid-phase user decisions (AskUserQuestion)

- Frontend Dockerfile (pre-existing `@tailwindcss/postcss` build failure): "Fix laga do (Recommended)"
- T288 ADRs: "Dono ADR banao"

## Response snapshot

Phase 11 (T277–T293) complete; Final Gate T293 PASS.

- Static: ruff/format clean; mypy 0 issues in 1494 files.
- Backend regression + coverage: GitHub CI run 36567160552 on `5b7c289`; backend code unchanged since.
- Migration chain: 78 revisions 001→078 on an empty database.
- Security: 106 passed / 0 failed; bandit and pip-audit show no new findings (all pre-existing on `main`).
- Frontend: lint 0 errors, Jest 285/285, build green; Playwright smoke 2/2 green.
- Docker: backend and frontend production images build.
- Defects fixed: dashboard drill-down links never rendered (FR-RPT-180, Phase 9 gap) plus the resulting layout overlap; the pre-existing frontend Dockerfile devDependency failure (user-approved).
- Docs: module README, ADR-0005/0006 (user consent), release-signoff.md, CLAUDE.md (manual; the script output was wrong).
- One local commit, not pushed.

### T283 E2E provenance

Throwaway stack:
- API on `127.0.0.1:8001` against a fresh `devsphere_p11_e2e` database migrated to `078`, with `CORS_ORIGINS=["http://localhost:3001"]`.
- `next dev -p 3001` with `NEXT_PUBLIC_API_URL=http://localhost:8001`.
- Chromium headless shell 1234.
- The database was dropped afterwards.

Seed script (run from `backend/` with `PYTHONPATH=.`; argument = output JSON path, passed to the spec as `REPORTS_E2E_SEED_PATH`):

```python
"""T283 seed — throwaway DB only (devsphere_p11_e2e)."""
import datetime, json, sys, uuid
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tests.fixtures.auth_fixtures import create_test_user
from tests.integration.api.v1.reports.conftest import (
    create_sales_customer, enable_reports, grant_all_reports_permissions, seed_sales_invoice,
)

URL = "postgresql://devsphere:<dev-password>@localhost:5432/devsphere_p11_e2e"
db = sessionmaker(bind=create_engine(URL))()
api = "http://127.0.0.1:8001/api/v1"
today = datetime.date.today().isoformat()
email, password = f"p11-e2e-{uuid.uuid4().hex[:6]}@example.com", "ReportsSmoke123!"
user, _ = create_test_user(db, email=email, password=password)
db.commit()
tok = httpx.post(f"{api}/auth/login", json={"email": email, "password": password}).json()["data"]["access_token"]
r = httpx.post(f"{api}/companies", json={"legal_name": "P11 Reports Smoke Co",
               "email": f"{uuid.uuid4().hex[:6]}@example.com"}, headers={"Authorization": f"Bearer {tok}"})
company_id = uuid.UUID(r.json()["data"]["id"])
enable_reports(db, company_id)
grant_all_reports_permissions(db, company_id, user.id)
customer = create_sales_customer(db, company_id)
for amount in ("1200.50", "300.00"):
    seed_sales_invoice(db, company_id, amount=amount, customer_id=customer.id, invoice_date=today)
db.commit()
json.dump({"email": email, "password": password, "company_id": str(company_id), "today": today},
          open(sys.argv[1], "w"))
```

## Outcome

- ✅ Impact: Epic 11 implementation complete; release sign-off recorded; two ADRs accepted.
- 🧪 Tests: see the `tests:` front-matter; every Phase 11 check green.
- 📁 Files: see the `files:` front-matter.
- 🔁 Next prompts: push/merge authorization for PR #9; product decisions on the open items in release-signoff.md.
- 🧠 Reflection: the E2E smoke test found a real FR-RPT-180 UI gap that the unit tests had missed, because no test asserted that drill-down links were rendered.

## Evaluation notes (flywheel)

- Failure modes observed: `update-agent-context.sh` rewrote `CLAUDE.md` from planning-time plan.md text; WSL `/mnt/d` file watching missed edits until `next dev` was restarted with polling.
- Graders run and results (PASS/FAIL): all Phase 11 checks PASS.
- Prompt variant (if applicable): Compact Reusable Implementation Master Prompt, PHASE_TO_IMPLEMENT = 11.
- Next experiment (smallest change to try): fix the CI Security Scans job so T280 runs in CI instead of locally.
