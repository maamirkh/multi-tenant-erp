---
id: 0032
title: T219-T221 — Final Browser E2E Closure (real Playwright)
stage: green
date: 2026-08-24
surface: agent
model: claude-sonnet-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: none (direct follow-up instruction)
labels: ["epic-9a", "playwright", "e2e", "real-browser", "bugfix", "epic-closure"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - frontend/playwright.config.ts
  - frontend/e2e/helpers.ts
  - frontend/e2e/t219-platform-admin-happy-path.spec.ts
  - frontend/e2e/t220-suspension-flow.spec.ts
  - frontend/e2e/t221-multi-tenant-support-access.spec.ts
  - frontend/package.json
  - frontend/package-lock.json
  - frontend/.gitignore
  - frontend/src/contexts/AuthContext.tsx
  - frontend/src/contexts/PlatformAuthContext.tsx
  - backend/modules/companies/router.py
  - backend/modules/companies/repositories/company_repository.py
  - backend/tests/integration/api/v1/companies/test_list_my_companies.py
  - specs/009a-platform-admin/tasks.md
tests:
  - frontend/e2e/t219-platform-admin-happy-path.spec.ts (real Chromium via mcr.microsoft.com/playwright docker image, --network host against the live stack — passed)
  - frontend/e2e/t220-suspension-flow.spec.ts (real Chromium, two browser contexts — passed)
  - frontend/e2e/t221-multi-tenant-support-access.spec.ts (real Chromium, two browser contexts — passed)
  - all 3 specs run together in one suite, twice consecutively (passed both times — no cross-spec leftover-state flakiness)
  - backend/tests/integration/api/v1/companies/test_list_my_companies.py (3 passed — new)
  - backend/tests/integration/api/v1/companies/ + unit/modules/companies/ + integration/repositories/companies/ (213 + 57 = 270 passed, zero regressions)
  - backend/tests/ platform_admin + companies sweep (563 passed; 3 contract-conformance tests independently verified 3/3 via a temporary specs/ mount — pre-existing container-mount limitation, not a regression)
  - frontend Jest full suite (121/121 passed — unchanged count, proves no regression from the AuthContext.tsx hydration fix)
  - frontend tsc --noEmit (0 errors)
  - frontend eslint . (0 errors, 55 pre-existing warnings, none in touched files)
  - backend full suite (tests/, excluding the 2 known container-mount-limited files) — 5936 passed, 3 failed, 8 skipped (1:21:08). All 3 failures characterized: 2 (test_report_performance.py regression guard, test_recurring_journal_service.py) FAILED full suite + PASSED isolation (load-sensitive under an 82-minute, ~5900-test concurrent run); 1 (test_settings.py::test_settings_default_debug_is_false) is a deterministic pre-existing environment-config mismatch — this docker-compose dev stack runs with DEBUG=true by design, unrelated to any change in this session. None of the 3 touch companies/, auth/, or platform_admin/.
---

## Prompt

```text
# Epic 9A — Final Browser E2E Closure (T219–T221 Only)

Complete the remaining blocked Epic 9A tasks **T219–T221 only** using real Playwright/browser E2E execution.

## Requirements

1. Stay on branch `009a-platform-admin`.
2. Verify current working tree is clean and commit `64e1fd0` is present.
3. Read the exact T219–T221 acceptance criteria from `tasks.md` before doing anything.
4. Configure/install Playwright only if genuinely required and consistent with the existing frontend architecture.
5. Execute the **actual browser flows** required by T219, T220 and T221 — HTTP/API-equivalent tests are **not substitutes**.
6. Verify especially:
   - Platform login → protected shell/navigation
   - tenant vs Platform auth/storage isolation
   - protected-route redirect behavior with no loops
   - Platform tenant-selection isolation
   - required UI mutation/dialog/acknowledgement flows
   - logout/session behavior
   - all exact acceptance criteria of T219–T221
7. Do not weaken tests or change production behavior merely to make Playwright pass.
8. If a genuine production defect is found, fix only the smallest root cause, add regression proof, and rerun affected tests.
9. Preserve the existing Phase 17 evidence exactly, including the previously documented `971/972` regression result and isolated flaky-test characterization. Do not rewrite historical evidence as a pass.
10. If T219–T221 pass, mark them `[X]`, update the Gate G/final completeness/traceability records so the previous tooling-deviation is explicitly resolved rather than erased.
11. Confirm:
    - T214–T225 are now fully complete;
    - no migration `062`;
    - contract remains `28 paths / 33 operations`;
    - no tenant/Platform security regression;
    - no unrelated scope expansion.
12. Run the appropriate frontend regression, `tsc --noEmit`, and ESLint after the E2E work.
13. Create the final PHR and commit the closure.
14. Do **not** push and do not start any new Epic.

## Final Report

Report:
- T219/T220/T221 results individually;
- Playwright/browser counts;
- defects found/fixed;
- frontend regression + TypeScript + ESLint results;
- security/isolation confirmation;
- files changed;
- commit hash and git status;
- confirmation that all **T001–T225** are complete.

Only declare:

**`EPIC 9A FULLY CLOSED — ALL T001–T225 COMPLETE — NO REMAINING DEVIATIONS`**

if every remaining browser task genuinely passes.

Otherwise STOP and report:

**`EPIC 9A CLOSURE BLOCKED — PRODUCT OWNER REVIEW REQUIRED`**
```

## Response snapshot

Verified branch/tree/commit clean, then confirmed via `ToolSearch` that no dedicated browser-automation tool exists in this session — same gap as Phase 17. Rather than reporting blocked again, tested whether real Playwright could genuinely be installed and run: pulled `mcr.microsoft.com/playwright:v1.62.1-noble` (official image, real Chromium pre-installed), added `@playwright/test` as a real frontend devDependency, and ran the whole suite via `docker run --network host` against the actual running `erp-system-web-1`/`erp-system-api-1` containers — no mocks, no HTTP-equivalent substitutes anywhere.

**Test-data setup**: created fresh Platform Owner (`t221-e2e-owner@example.com`) and tenant (`t221-e2e-tenant@example.com`) users via direct-DB-insert (Argon2id hashes via the real `PasswordService`) plus real `PlatformAdministrator`/role-assignment rows, then Companies A and B via the real `POST /companies` + `/activate` API as that tenant user — mirroring Phase 17's own established real-Postgres verification pattern.

**Real defects found and fixed** (in order of discovery, all via genuine browser navigation — none would have been caught by backend/HTTP-only testing):

1. **React Strict Mode session-hydration race** (`PlatformAuthContext.tsx`, and the identical pre-existing pattern in `AuthContext.tsx`): dev-mode Strict Mode's synchronous mount→cleanup→remount double-invocation set a per-invocation `cancelled` flag from the throwaway first invocation that then permanently poisoned the one genuine in-flight `hydrate()` call's `setIsAuthenticated`/`setIsLoading` updates — the actually-mounted component was permanently stranded on its initial `isLoading=true`, an infinite spinner after every single login. Root-caused via targeted temporary console-log instrumentation of the effect's lifecycle (mount/cleanup/hydrate-start/hydrate-resolve), reproduced deterministically, then fixed in both contexts by relying solely on the existing `hydrateStartedRef` guard (already sufficient — caps `hydrate()` to one real call) and removing the harmful `cancelled` flag entirely (React 18+ already no-ops `setState` after a genuine unmount).

2. **`GET /api/v1/companies` had no route at all** (405 on every call): the frontend's `listCompanies()` and `CompanyService.list_user_companies()` both already existed and were correctly implemented, but nothing ever wired them together — the "My Companies" list page has apparently never worked for any user. Fixed by adding the missing `GET ""` route to `companies/router.py`; 3 new regression tests added.

3. **Platform Tenants page search-by-slug silently broken**: the page's own placeholder text promises "Search by name or slug…", but `CompanyRepository.list_all()`'s `search` filter only ever matched `legal_name` — searching a slug (which contains hyphens where the corresponding legal name has spaces) always returned zero results, for every tenant, in every phase since Phase 13 built the page. Fixed by widening the filter to `legal_name OR slug` (additive, non-narrowing — verified via the existing repository test suite, all 57 unaffected).

**Test-construction findings** (not app defects, fixed within the spec files themselves): (a) Chromium logs its own `console.error` for every non-2xx network response, independent of application code — T220/T221 deliberately trigger 403s as their actual scenario, so this exact, narrow message pattern is excluded from the "unexpected console errors" check (documented in `helpers.ts` — never something app code could "fix", since app code never emits it). (b) The tenant app has no logout button anywhere in its UI (`AuthContext` exposes `logout()`, nothing renders it) — worked around in T220 by clearing the stored refresh token directly before the genuine-re-login step, which also incidentally fixed a real race between silent hydration-refresh (using the still-present old token) and the explicit form login. (c) T220/T221 both suspend Company A as part of their own scenario; added idempotent HTTP "arrange" helpers (`ensureCompanyActive`, `ensureNoActiveOverride`) so repeated/out-of-order runs are deterministic regardless of a prior run's outcome — all three specs verified to pass together, twice consecutively.

**Full regression after all fixes**: frontend Jest 121/121 (unchanged count — proves the hydration fix caused no regression), `tsc --noEmit` 0 errors, `eslint .` 0 errors (same 55 pre-existing warnings, none in touched files). Backend: new test file 3/3, full companies module 213/213 (+57 repository/unit), full `platform_admin`+`companies` sweep 563/563 (+3 contract-conformance tests independently confirmed 3/3 via a temporary `specs/` mount into the container — the same pre-existing container-mount limitation Phase 16 already documented, not a regression). Full backend suite (`tests/`, excluding the 2 known container-mount-limited files) run in background for final confirmation.

`tasks.md` updated: T219/T220/T221 marked `[X]` with full evidence; Gate G checklist, Final Completeness Audit's Playwright line, and the Requirement Traceability Matrix's footnote all updated to record the deviation as **resolved**, not erased — a new dated closure note was appended after Phase 17's own Exit Condition paragraph rather than editing that paragraph's original text, per the explicit instruction to preserve historical evidence exactly.

## Outcome

- ✅ Impact: Epic 9A's real-stack verification requirement (Gate G) is now genuinely complete at every layer specified by tasks.md — Postgres, Docker Compose, HTTP, and now real browser — with zero remaining deviations. Along the way, three real, previously-undiscovered production defects were found and fixed, none introduced by this session, all pre-dating Epic 9A entirely (basic Companies-module and Auth-context bugs that no prior backend-only or component-mocked frontend test could have caught).
- 🧪 Tests: 3 Playwright specs (all passing, individually and combined), 3 new backend tests, 121 frontend Jest tests unchanged, 270+563 backend tests unchanged/passing.
- 📁 Files: 2 new frontend production fixes (AuthContext.tsx, PlatformAuthContext.tsx), 2 new backend production fixes (router.py, company_repository.py), 1 new backend test file, 3 new Playwright spec files + config + helpers, package.json/package-lock.json/.gitignore updated, tasks.md updated.
- 🔁 Next prompts: none — Epic 9A is fully closed, no Phase 18 exists.
- 🧠 Reflection: The single most valuable moment in this session was refusing to accept "still blocked" as the answer a second time — testing whether the tooling gap was actually permanent (it wasn't; Docker + npm access was sufficient) rather than re-reporting the same limitation. The React Strict Mode hydration race is a good example of a defect class that is structurally invisible to every other verification layer this epic has used (real Postgres, real HTTP, component-level Jest tests with mocked timers) — it only exists at the intersection of React's actual render lifecycle and a real network round-trip, which only a genuine browser page load exercises.

## Evaluation notes (flywheel)

- Failure modes observed: (1) initial `docker run -v "$(pwd)":/work` calls silently mounted the wrong directory (`backend/`, not `frontend/`) after an earlier `cd` for an unrelated pytest check changed the persistent shell's cwd — caught via `npx playwright` trying to auto-install a fresh package into a directory with no e2e files, not via an explicit error; fixed by re-`cd`-ing and being more careful about shell state persistence across tool calls in this environment. (2) Assumed the hydration hang was Turbopack cold-compile latency (a real, separately-observed effect in this dev environment) before actually isolating it via temporary console-log instrumentation — cost several wasted retry cycles before the real root cause was identified. (3) Test-data leftover state (suspended companies, already-active entitlement overrides) from earlier partial/failed runs against the same persistent Company A/B repeatedly caused spurious failures on subsequent runs — fixed properly via idempotent arrange-phase helpers rather than by manually resetting state between every retry.
- Graders run and results (PASS/FAIL): all 3 Playwright specs PASS (individually and combined, twice consecutively); new backend test file PASS 3/3; full companies-module regression PASS 270/270; platform_admin+companies sweep PASS 563/563 (+3 via temporary mount); frontend Jest PASS 121/121; tsc PASS 0 errors; eslint PASS 0 errors.
- Prompt variant (if applicable): first invocation in this session explicitly framed as "try again, don't just report blocked" — a meaningfully different instruction from Phase 17's own master-prompt template, which had pre-authorized proceeding without Playwright. This one required actually attempting the tooling installation before concluding anything.
- Next experiment (smallest change to try): if a future session needs to extend this Playwright suite, warm every route via a plain `curl` loop immediately after any web-container restart before running specs — Turbopack's on-demand dev compilation adds real, non-trivial latency to first-visit routes that is easy to mistake for an application bug (as happened here initially).
