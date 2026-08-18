---
id: 0011
title: Epic 9 full closure gap remediation
stage: green
date: 2026-08-18
surface: agent
model: claude-sonnet-5
feature: 009-crm
branch: 009-crm
user: Muhammad Amir
command: none (freeform conversational request)
labels: ["crm", "epic-closure", "gap-remediation", "rbac", "feature-flag", "company-context", "epic-9"]
links:
  spec: specs/009-crm/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/crm/router.py
 - backend/modules/crm/constants.py
 - backend/modules/crm/schemas/base.py
 - backend/api/v1/router.py
 - frontend/src/lib/api/crm.ts
 - frontend/src/hooks/crm/useCrmPermissions.ts (new)
 - frontend/src/app/(protected)/(crm)/leads/page.tsx
 - frontend/src/app/(protected)/(crm)/leads/[leadId]/page.tsx
 - frontend/src/app/(protected)/(crm)/opportunities/[opportunityId]/page.tsx
 - frontend/src/app/(protected)/(crm)/activities/page.tsx
 - frontend/src/app/(protected)/(crm)/settings/page.tsx
 - frontend/src/components/crm/LinkedActivities.tsx
 - frontend/src/app/(protected)/(companies)/companies/[id]/page.tsx
 - specs/009-crm/tasks.md
 - specs/009-crm/plan.md
tests:
 - Fresh full CRM suite (unit+integration+API+security+performance) - 434/434 passed
 - Targeted regression (companies + users_roles, the 2 modules touched) - 636/636 passed
 - ruff/mypy (backend) - clean, zero errors attributable to CRM's own files
 - eslint/tsc --noEmit (frontend) - clean across all changed files
 - Live Playwright E2E against the real Docker/Postgres stack - company creation,
   real company-selection via the Companies module, CRM enable/disable/status round
   trip via real HTTP, all 8 CRM page routes (zero console errors), full Lead ->
   Contacted -> Qualify -> Convert -> Opportunity -> Customer 360 happy path with
   every gated action button correctly visible for the owner role
---

## Prompt

theek hai sab se pehle tum epic 009-crm ke tasks.md ke jo bhi task umark hain unko
complete karke mark karo aur epic 9 complete karke mujhe inform kardo

[Preceded by a status-check exchange establishing that 44 boxes were unchecked, that
most were either stale placeholders already superseded by the T100 live-verification
pass or unticked formality re-statements of independently-`[x]`-confirmed work, and
that the epic was "substantively complete but not formally closed." The user then
asked for genuine completion, not just re-verification.]

[Mid-task, when genuine (not cosmetic) gaps were discovered, two scope-confirmation
questions were asked and answered before implementing:]

1. Confirmed: implement all 3 real gaps found while verifying the checklists — (a) no
   UI/API path exists to enable CRM for a company, (b) CRM's company-id resolution
   reads a localStorage key nothing in the real app ever writes, (c) the frontend
   shows every action button to every user regardless of permission (backend enforces
   correctly; only the UI doesn't hide anything).
2. Confirmed, once gap (b) turned out to be larger than initially described (the
   platform's entire "select an active company" mechanism was never wired to any real
   page anywhere, not just a wrong key name): fix the root cause in the Companies
   module (Epic 3) too, not just work around it inside CRM.

## Response snapshot

Verified every one of the 44 previously-unchecked `tasks.md` boxes individually rather
than bulk-approving them: ran the full CRM test suite fresh (434/434), the DB-level
items already closed by the T100 live-verification pass in the prior session (migration
bidirectional replay, real-Postgres constraint tests, live persistence check — all
`[x]`'d with the T100 citation that had been left unticked), and the 6 "Final
Verification Summary" checklists (API/Frontend/Security-RBAC/Tenant-Isolation/
Audit-Event/Cross-Module) via a mix of fresh test evidence and direct code inspection
(endpoint counts, `grep` for repository imports, `PaginationParams` `le=100` caps,
`CrmAuditLogRepository` lacking update/delete methods, etc.).

That verification pass surfaced 3 genuinely unimplemented gaps (not just unticked
boxes) and, after user confirmation, implemented all 3:

1. **CRM enable/disable path.** `CrmFeatureFlagService.enable()`/`disable()` existed
   but nothing reachable ever called them. Added `GET /crm/status`,
   `POST /crm/enable`, `POST /crm/disable` as a new `admin_router` in
   `modules/crm/router.py`, mounted in `api/v1/router.py` deliberately *without*
   `require_crm_enabled` (a company must reach these while still disabled — otherwise
   no company could ever turn CRM on) and gated instead by `require_admin_or_above()`
   (company-admin authority, not a `crm.*` permission, avoiding a circular
   before-the-module-is-active check). Verified via a full off->on->off->on round trip
   through real HTTP.

2. **Company-selection mechanism.** Investigation found this was not a "wrong
   localStorage key" bug as first described — `CompanyContext.setActiveCompany()`
   (the only place in the entire frontend that ever persists an active company) was
   never called by any real page anywhere in the app; the whole mechanism was
   orphaned scaffolding from Epic 3. Root-fixed by wiring `setActiveCompany()` into
   `(companies)/companies/[id]/page.tsx` (viewing a company's detail page now marks
   it active — the natural, already-existing moment for this), then pointing CRM's
   `getCompanyId()` (`components/crm/apiErrors.ts`) at the correct
   `erp_active_company_id` key `CompanyContext` actually uses. Explicitly did **not**
   fix the identical wrong-key bug independently present in 23 Sales/Purchase files —
   flagged as a separate, much larger, pre-existing cross-epic finding, out of scope
   for closing Epic 9 specifically. Verified live: visiting a company's detail page
   with zero manual localStorage intervention correctly makes every subsequent CRM
   page resolve that exact company.

3. **Permission-gated UI hiding.** Backend RBAC was already fully correct and tested
   (152-cell matrix passing); the frontend simply showed every action to every user
   and only revealed a 403 after a failed click. Added `GET /crm/my-permissions`
   (returns the caller's granted `crm.*` codes for the company, reusing the same
   `CompanyMemberRepository`/`RolePermissionRepository` chain
   `user_has_crm_permission()` itself uses, not a divergent lookup) plus a new
   `useCrmPermissions()`/`useHasCrmPermission()` hook pair
   (`hooks/crm/useCrmPermissions.ts`, fails safe to zero permissions on any error).
   Wired into: Leads list (New Lead, both the header button and the empty-state
   link), Lead detail (Mark Contacted/Qualify/Disqualify/Mark Lost/Reopen gated on
   `crm.leads.update`; Convert gated on `crm.leads.convert`; Reassign Owner gated on
   `crm.leads.assign`), Opportunity detail (Stage change/Link Quotation gated on
   `crm.opportunities.update`; Win/Lose gated on `crm.opportunities.close`; Reassign
   gated on `crm.opportunities.assign`), the shared `LinkedActivities` component used
   by both detail pages (Log Activity gated on `crm.activities.create`, Complete
   gated on `crm.activities.update`), the standalone Activities list's own Complete
   button (same gate), and Settings (all Lead Source/Pipeline/Stage
   add/activate/deactivate controls gated on `crm.pipeline.manage`).

Along the way, fixed a self-inflicted bug in the Playwright verification script
itself (calling `/auth/refresh` repeatedly without persisting the rotated refresh
token back to `localStorage` — the exact same single-use-token race pattern fixed in
`AuthContext.tsx` during the prior session's PHR 0010, this time in the test tooling
rather than the app).

Re-verified everything end-to-end after all 3 fixes: full CRM suite (434/434 fresh),
targeted companies+users_roles regression (636/636 fresh), ruff/mypy/eslint/tsc all
clean, and one continuous live-browser pass covering company creation through real
company-selection, the CRM enable round trip via real HTTP, all 8 page routes with
zero console errors, and the complete Lead->Contacted->Qualify->Convert->Opportunity
->Customer 360 happy path with every permission-gated button correctly visible and
functional for the owner role (which holds all 19 permissions, confirmed via a direct
call to the new endpoint).

Then updated both `specs/009-crm/tasks.md` (all 6 "Final Verification Summary"
checklists, the 3 DB-level items, the Epic Closure Checklist itself, and a new
"Post-Closure Gap Remediation" section documenting all 3 fixes in detail) and
`specs/009-crm/plan.md` §35 (Definition of Done, item-by-item) with evidenced `[x]`
marks — except 2 items left honestly `[ ]`: "zero Accounting files modified" and
"§29.2 modified-files list is exhaustive" are no longer literally true, since the
prior session's routing-collision fix (PHR 0010) touched one Epic 8 file (a pure
rename). Both are explained in place rather than silently marked done.

## Outcome

- ✅ Impact: Epic 9 (CRM) is now genuinely, not just formally, complete — every
  checklist claim in `tasks.md` and `plan.md` §35 is backed by fresh, real evidence
  (either a passing test re-run today or a live-browser observation today), and the 3
  gaps that were silently unimplemented (CRM couldn't be turned on, company context
  didn't work, permissions weren't UI-enforced) are now real, working features, not
  just ticked boxes.
- 🧪 Tests: 434/434 CRM suite (fresh), 636/636 companies+users_roles (fresh), full
  live-browser E2E pass (fresh) — all summarized above. Zero new test files added
  (all verification was via existing suites + live browser observation, matching the
  scope of "close what's incomplete," not "add new test coverage").
- 📁 Files: 3 new backend endpoints + 1 new schema class + 1 new permission-code
  constant list (`modules/crm/`), 1 new frontend hook file
  (`hooks/crm/useCrmPermissions.ts`), 6 existing CRM frontend files updated to use
  it, 1 Companies-module file (Epic 3) gained a `useEffect` to close the root cause
  of the company-context gap, `api/v1/router.py` gained one new router mount.
  `tasks.md` and `plan.md` updated with the full evidence trail.
- 🔁 Next prompts: Two deliberately out-of-scope findings remain for a separate
  decision: (1) the same wrong-localStorage-key bug independently exists in 23
  Sales/Purchase files (Epic 6/7) — CRM's fix did not touch them; (2) client-side
  form validation is thin (no `required` attributes) — backend Pydantic validation is
  authoritative so there's no data-integrity risk, but it's a real, left-unchecked
  gap in the Frontend Checklist, flagged rather than silently claimed done.
- 🧠 Reflection: The pattern that made this pass trustworthy rather than just
  fast was refusing to bulk-tick the 44 boxes — actually running the tests, grepping
  the code, and clicking through the browser for each claim surfaced 3 real product
  gaps a superficial "looks done, check it" pass would have missed entirely, plus 2
  DoD items that are now honestly false rather than quietly re-asserted.

## Evaluation notes (flywheel)

- Failure modes observed: none blocking. The Playwright test script itself hit the
  same refresh-token race the app was fixed for in the prior session — a useful
  confirmation that the underlying bug class (manual `/auth/refresh` calls without
  persisting the rotated token) is easy to reintroduce anywhere it's touched by hand,
  not just in `AuthContext.tsx`.
- Graders run and results (PASS/FAIL): Self-verified via fresh test suite runs and
  the Playwright script's own assertions at each stage (HTTP status codes, exact
  `enabled` boolean through the round trip, exact permission-code list match, final
  happy-path state) — all PASS on the final run.
- Prompt variant (if applicable): n/a.
- Next experiment (smallest change to try): n/a — task complete for the scope agreed
  with the user; the two flagged-but-deferred findings are candidates for a future,
  separately-scoped prompt.
