---
id: 0010
title: Live browser verification and 3 routing auth fixes
stage: green
date: 2026-08-18
surface: agent
model: claude-sonnet-5
feature: 009-crm
branch: 009-crm
user: Muhammad Amir
command: none (freeform conversational request)
labels: ["crm", "live-verification", "routing-bug", "auth-bug", "epic-9", "cross-epic-fix"]
links:
  spec: specs/009-crm/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - frontend/src/app/(protected)/(accounting)/accounting-dashboard/page.tsx (renamed from dashboard/page.tsx)
 - frontend/src/app/(protected)/(crm)/crm-dashboard/page.tsx (renamed from dashboard/page.tsx)
 - frontend/src/app/(protected)/(crm)/crm-customers/[customerId]/page.tsx (renamed from customers/[customerId]/page.tsx)
 - frontend/src/app/(protected)/(crm)/leads/[leadId]/page.tsx
 - frontend/src/app/(protected)/(crm)/opportunities/[opportunityId]/page.tsx
 - frontend/src/contexts/AuthContext.tsx
 - specs/009-crm/tasks.md
tests:
 - Live browser verification (Playwright, headless Chromium, manually installed
   due to no root access on host — deb packages for libnspr4/libnss3/libasound2t64
   extracted to a local prefix + LD_LIBRARY_PATH, no system package manager used)
 - Verified all 8 distinct CRM page routes return 200 with zero console errors
 - Verified full Lead -> Contacted -> Qualify -> Convert -> Opportunity ->
   Customer 360 happy path end-to-end through the real UI against the live
   Docker Compose stack (api/web/db/minio containers, real Postgres)
---

## Prompt

009-crm ki tasks.md check karo complete hogayi thi tu abhi kiya baqi rehta hai

[Follow-up, after being shown that 45 tasks.md checkboxes were unchecked but
that all except one (frontend live-browser verification) were either stale
placeholders already superseded by later evidence, or unticked formality
re-statements of work already independently confirmed complete elsewhere in
the document:]

to jo test baqi hai woh bhi complete karo

[Two follow-up confirmations given mid-task, via AskUserQuestion, when scope
threatened to expand beyond the original request:]

1. Confirmed OK to fix the 3-way /dashboard route collision (Epic 8's
   accounting dashboard + CRM's new dashboard + the pre-existing global
   dashboard) that was 500-ing the entire app and blocking any verification
   at all.
2. Confirmed OK to investigate and fix the app-wide dynamic-route 404 bug
   (every /{module}/[id]-style detail page across every epic, not just CRM)
   after the AuthContext.tsx double-refresh race fix was applied but a new,
   much larger-blast-radius bug was found blocking the Lead qualify/convert
   steps of the happy path.

## Response snapshot

Investigated `specs/009-crm/tasks.md`'s 45 unchecked boxes and reported that
44 were either stale (already satisfied by the later T100 live-Docker-Postgres
verification pass, never retroactively ticked) or unticked formality
re-statements of work already independently `[x]`-confirmed elsewhere in the
file — genuinely leaving exactly one real gap: the frontend's 12 pages had
never been clicked through in an actual running browser (deliberately
deferred per the task's own instructions).

To perform that verification: installed Playwright + a locally-extracted
Chromium (no root/sudo available on the WSL host; downloaded the missing
`.deb` packages via `apt-get download` — which doesn't require root — and
extracted them into a scratch prefix, pointed at via `LD_LIBRARY_PATH`,
rather than modifying any system state). Created a throwaway test user via
`backend/scripts/create_admin.py`, drove the real login form, created a real
company through the real 4-step onboarding wizard, and — since no HTTP
endpoint or UI exists anywhere to enable a tenant's CRM feature flag — called
`CrmFeatureFlagService.enable()` directly via a `docker exec ... python -c`
one-liner (documented as a genuine product gap, not fixed).

Hit and diagnosed, in order:
1. **App-wide 500** on every route: three separate pages (`(protected)/dashboard`,
   `(protected)/(accounting)/dashboard`, `(protected)/(crm)/dashboard`) all
   resolved to the literal `/dashboard` URL since Next.js route groups don't
   add path segments — a 2-way collision already present in Epic 8's own
   committed code (verified via `git show b1ce764:...`, i.e. predates this
   session and predates CRM entirely) that CRM's own new dashboard turned
   into a 3-way collision. Fixed (with explicit user sign-off) by renaming
   both module dashboards to unique paths.
2. **Silent random logout on every hard navigation**: `AuthContext.tsx`'s
   session-hydration effect called `refreshApi()` directly instead of the
   existing `acquireRefreshLock()` single-flight lock the API client's own
   401-retry interceptor already uses elsewhere — any hard page load while
   authenticated could race two concurrent `/auth/refresh` calls against the
   same single-use, rotating refresh token; the first succeeded and rotated
   it, the second failed `TOKEN_REVOKED` and immediately cleared the session
   the first call had just established. Diagnosed via full request/response
   network logging in the Playwright driver script. Platform-wide, predates
   CRM, not fixed by an initial `useRef` StrictMode-guard attempt (kept as
   belt-and-braces) — the actual fix was routing hydration through
   `acquireRefreshLock()`.
3. **App-wide 404** on every dynamic-segment detail route (`/leads/{id}`,
   `/companies/{id}`, `/customers/{id}`, confirmed identically broken across
   Epic 3, Epic 7, and Epic 9): root-caused via web-container logs surfaced
   only after properly clearing the `/app/.next` Docker **anonymous volume**
   (a `docker restart` alone does *not* clear it — the volume survives
   process restarts; had to `docker stop`, mount the named volume into a
   throwaway `alpine` container to `rm -rf` its contents, then `docker start`)
   to a genuinely fresh compile: `Error: You cannot use different slug names
   for the same dynamic path ('customerId' !== 'id')`. CRM's own new
   `(crm)/customers/[customerId]` collided with the pre-existing
   `(sales)/customers/[id]` at the literal path `/customers/{x}` — Turbopack
   rejects the whole dynamic-route manifest reload on any such conflict
   anywhere in the app, which is why *every* unrelated dynamic route 404'd,
   not just the two colliding pages. This one is CRM's own defect (Sales owns
   `/customers`; CRM should never have claimed the same literal path for its
   own Customer 360 page). Fixed by renaming to `/crm-customers/[customerId]`
   and updating its 2 internal `Link` references (the "View Customer" links
   on the lead-detail and opportunity-detail pages).

With all three fixed, re-verified via the same Playwright script: all 8
distinct CRM page routes load with zero console errors, and the complete
Lead -> Mark Contacted -> Qualify (with required qualification notes,
correctly enforced server-side) -> Convert -> auto-created Opportunity
(confirmed in the Opportunities list) -> Customer 360 (confirmed showing the
converted Lead, the new Opportunity, and live cross-module Sales/Accounting
data — credit status, sales history) happy path was executed end-to-end
through the real UI against the live Docker/Postgres stack, with zero console
errors throughout.

Also surfaced (documented, deliberately *not* fixed, out of the scope
explicitly agreed with the user for this task) two further real gaps: (a) no
sidebar navigation link anywhere reaches any of CRM's pages — they're only
reachable by typing the URL directly; (b) CRM's `apiErrors.ts::getCompanyId()`
reads the active company from `localStorage.getItem("company_id")`, a key
nothing in the real app ever writes — the platform's actual mechanism is
`CompanyContext` writing `erp_active_company_id`, and Sales' own `customers`
page has the identical wrong-key bug, so this is a pre-existing, cross-epic
pattern, not something to silently rewrite under this task's scope.

Updated `specs/009-crm/tasks.md`'s Phase 9 gate: ticked the previously-`[ ]`
"All 12 CRM frontend pages functional against the live backend" item with the
verification evidence and a full account of the 3 defects found/fixed, and
amended the adjacent "3 Epic 1-8 files" line to honestly note the 2
additional cross-epic files this pass required touching (both are bug fixes
to the infrastructure the defects were found in, not feature changes).

Committed as `fcfef7b` on the `009-crm` branch (commit `feat(009)` for the
CRM implementation itself was already committed earlier in the session as
`aa353aa`).

## Outcome

- ✅ Impact: The one genuine remaining gap identified in Epic 9's task
  checklist (live frontend verification) is now actually complete, with real
  evidence, not just marked done. Three real defects that were silently
  breaking large parts of the *entire application* (not just CRM) were found
  and fixed with explicit user approval at each escalation in scope size.
- 🧪 Tests: No automated test suite was added or run (out of scope for this
  request — it was specifically about live-browser verification, not new
  pytest/vitest coverage); verification was manual-but-scripted via
  Playwright against the real Docker/Postgres stack, screenshots retained in
  the session scratchpad.
- 📁 Files: 3 files renamed (2 dashboard collisions + 1 customers collision),
  2 files got a 1-line internal-link update each, 1 shared auth file
  (`AuthContext.tsx`) got its hydration call rerouted through the existing
  refresh lock, `tasks.md` updated with evidence. All committed as `fcfef7b`.
- 🔁 Next prompts: Two real, still-open, deliberately-out-of-scope gaps to
  decide on separately: (1) no way to enable CRM for a tenant except direct
  backend/DB access — no UI, no API endpoint; (2) CRM's (and Sales
  `customers` page's) `localStorage["company_id"]` company-resolution is
  disconnected from the platform's real `CompanyContext`/`erp_active_company_id`
  mechanism. Also: the 3 defects found here were all *cross-epic*
  pre-existing issues that CRM's arrival exposed rather than solely
  caused — worth a broader audit of other modules' dynamic routes for the
  same literal-path-collision pattern before Epic 10 adds more pages.
- 🧠 Reflection: The most consequential single fact discovered was that
  `docker restart` does **not** clear an anonymous-volume-backed `.next`
  cache — two of the three bugs looked cache-related at first glance and
  survived a restart, which nearly led to concluding they were unfixable
  cache staleness rather than real code defects. Explicitly stopping to
  clear the actual Docker volume (not just the process) before declaring a
  restart "didn't help" was what surfaced the real, actionable error message.
  Also notable: escalating scope was handled by pausing and asking at each
  new order-of-magnitude jump (2-file fix -> 1-file fix -> app-wide unknown
  root cause) rather than either silently ploughing ahead or refusing outright.

## Evaluation notes (flywheel)

- Failure modes observed: Initial attempt at the auth race used a `useRef`
  StrictMode-double-invoke guard, which did not fix the bug (the real
  duplicate came from a *different* code path — the API client's own
  401-retry lock — not from StrictMode re-invoking the same effect); had to
  add full request/response network logging to the Playwright driver to see
  the actual duplicate `/auth/refresh` call before finding the true cause.
  `docker restart` was tried twice under the (wrong) assumption it would
  clear Next's dev cache; it does not, for anonymous-volume-backed paths.
- Graders run and results (PASS/FAIL): Self-verified via the Playwright
  script's own assertions (HTTP status per page, zero-console-errors check,
  and the happy-path's final state — CONVERTED status, Opportunity created,
  Customer 360 populated) — all PASS on the final run.
- Prompt variant (if applicable): n/a.
- Next experiment (smallest change to try): n/a — task complete for the
  scope agreed with the user.
