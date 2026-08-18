---
id: 0001
title: Fix Sales and Purchase company id auth and url bugs
stage: general
date: 2026-08-18
surface: agent
model: claude-sonnet-5
feature: none
branch: 009-crm
user: Muhammad Amir
command: none (freeform conversational request)
labels: ["sales", "purchase", "cross-epic-fix", "auth-bug", "company-context", "epic-6", "epic-7"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - frontend/src/lib/api/sales.ts
 - frontend/src/lib/api/purchase.ts
 - frontend/src/app/(protected)/(sales)/customers/page.tsx
 - frontend/src/app/(protected)/(sales)/customers/import/page.tsx
 - frontend/src/app/(protected)/(sales)/customers/new/page.tsx
 - frontend/src/app/(protected)/(sales)/customers/[id]/page.tsx
 - frontend/src/app/(protected)/(sales)/delivery-notes/page.tsx
 - frontend/src/app/(protected)/(sales)/delivery-notes/[id]/page.tsx
 - frontend/src/app/(protected)/(sales)/invoices/page.tsx
 - frontend/src/app/(protected)/(sales)/invoices/[id]/page.tsx
 - frontend/src/app/(protected)/(sales)/pricing/customer-prices/page.tsx
 - frontend/src/app/(protected)/(sales)/pricing/discounts/page.tsx
 - frontend/src/app/(protected)/(sales)/pricing/price-lists/page.tsx
 - frontend/src/app/(protected)/(sales)/quotations/page.tsx
 - frontend/src/app/(protected)/(sales)/quotations/[id]/page.tsx
 - frontend/src/app/(protected)/(sales)/returns/page.tsx
 - frontend/src/app/(protected)/(sales)/returns/[id]/page.tsx
 - frontend/src/app/(protected)/(sales)/sales-orders/page.tsx
 - frontend/src/app/(protected)/(sales)/sales-orders/[id]/page.tsx
 - frontend/src/app/(protected)/(sales)/sales/settings/approval/page.tsx
 - frontend/src/app/(protected)/(sales)/sales/settings/page.tsx
 - frontend/src/app/(protected)/(sales)/sales/settings/categories/page.tsx
 - frontend/src/app/(protected)/(purchase)/purchase-orders/page.tsx
 - frontend/src/app/(protected)/(purchase)/purchase-orders/new/page.tsx
 - frontend/src/app/(protected)/(purchase)/purchase-orders/[id]/page.tsx
 - frontend/src/app/(protected)/(purchase)/goods-receipts/page.tsx
 - frontend/src/app/(protected)/(purchase)/goods-receipts/new/page.tsx
 - frontend/src/app/(protected)/(purchase)/goods-receipts/[id]/page.tsx
 - frontend/src/app/(protected)/(purchase)/vendor-returns/page.tsx
 - frontend/src/app/(protected)/(purchase)/vendor-returns/new/page.tsx
 - frontend/src/app/(protected)/(purchase)/vendor-returns/[id]/page.tsx
 - frontend/src/app/(protected)/(purchase)/purchase/reports/kpis/page.tsx
 - frontend/src/app/(protected)/(purchase)/purchase/reports/open-purchase-commitments/page.tsx
 - frontend/src/app/(protected)/(purchase)/purchase/reports/purchase-order-summary/page.tsx
 - frontend/src/app/(protected)/(purchase)/purchase/reports/purchase-price-variance/page.tsx
 - frontend/src/app/(protected)/(purchase)/purchase/reports/purchase-trend-analysis/page.tsx
 - frontend/src/app/(protected)/(purchase)/purchase/reports/supplier-performance/page.tsx
 - frontend/src/app/(protected)/(purchase)/purchase/settings/page.tsx
 - frontend/src/app/(protected)/(purchase)/purchase/settings/categories/page.tsx
 - frontend/src/app/(protected)/(purchase)/suppliers/page.tsx
 - frontend/src/app/(protected)/(purchase)/suppliers/[id]/page.tsx
 - frontend/src/app/(protected)/(purchase)/suppliers/import/page.tsx
tests:
 - tsc --noEmit - clean, zero errors
 - eslint across all changed files - 0 errors, 17 pre-existing react-hooks/exhaustive-deps
   warnings unrelated to this change
 - Live Playwright smoke test against the real Docker/Postgres stack - 13 pages sampled
   (7 Sales, 6 Purchase), all 200 with zero console errors and correct real empty-state
   rendering (proving the API calls now genuinely reach and are accepted by the backend)
---

## Prompt

Sales aur Purchase ke 23 files bhi fix kardo

[Preceded by an exchange where the user was informed that the wrong-key bug found while
closing Epic 9 (CRM) also existed in ~23-24 Sales/Purchase files. Investigation before
touching anything found the problem was materially bigger than "same wrong key": Sales'
~18 files also never actually authenticated (token pulled from a localStorage key that
is never populated), and Purchase's 15 files additionally used relative URLs that would
hit the Next.js frontend server itself rather than the backend API, with no auth header
at all. This was surfaced to the user as a 3-bug-class, ~35-40-file, 2-epic problem
before proceeding, and the user confirmed: fix all of it properly, not just the
literally-requested company_id key.]

## Response snapshot

Fixed 3 independent bug classes across Sales (Epic 7) and Purchase (Epic 6):

1. **Wrong company_id localStorage key** — `localStorage.getItem("company_id")`
   (never written by anything) → `localStorage.getItem("erp_active_company_id")`
   (the real key `CompanyContext` writes, per the Epic 9 closure fix). Bulk-fixed via
   `sed` across the 18 Sales files with the uniform pattern, then individually across
   the 15 Purchase raw-fetch files and the remaining route-param variants.

2. **Missing/broken auth token.** Two shared API-client files fixed at the root
   (highest leverage — fixes the ~23 files that use them without touching each
   individually):
   - `lib/api/sales.ts`'s `authHeaders(token)` now falls back to the real
     `getAccessToken()` (from `lib/auth/tokenStorage.ts`, in-memory, the actual
     token store) whenever the caller's passed token (historically read from the
     same nonexistent `access_token` localStorage key) is falsy.
   - `lib/api/purchase.ts`'s `apiFetch()` never even attempted an Authorization
     header before — now calls `getAccessToken()` directly.
   - Also fixed a distinct bug found in `sales.ts`'s `exportSalesReport()`:
     `API_BASE` was being prepended twice (`salesBase()` already includes it),
     which would have produced a malformed URL like
     `http://localhost:8000http://localhost:8000/api/v1/...`.

3. **Wrong/missing base URL + no auth in 15 raw-fetch Purchase pages.** These pages
   (`purchase-orders`, `goods-receipts`, `vendor-returns`, all 6
   `purchase/reports/*`) didn't go through any shared API client at all — hand-rolled
   `fetch()` calls with relative URLs (`/api/v1/...`, resolving against the Next.js
   frontend origin, not the backend) and either `credentials: "include"` (assuming a
   cookie-auth model this app has never used) or no auth attempt whatsoever. Fixed
   each call site individually: added `API_BASE` + `Authorization: Bearer
   ${getAccessToken()}`, matching the pattern already established for the earlier
   9 (purchase-orders/goods-receipts/vendor-returns) files.

Along the way, found and fixed a 4th, related pattern: several Purchase pages
(`suppliers`, `suppliers/[id]`, `purchase/settings`, `purchase/settings/categories`,
`suppliers/import`) derived `companyId` from a `params` prop expected to contain
`company_id`/`id` — but these routes have no such dynamic segment in their file path,
so `params` was always empty; this is a different flavor of the same "never actually
worked" root cause. Fixed by switching to the same `localStorage`-based resolution
(or, for `suppliers/[id]/page.tsx`, the real `useParams()` hook already used correctly
elsewhere for the genuine `[id]` segment) used everywhere else.

Explicitly did **not** expand into Accounting (Epic 8) or Inventory (Epic 5), even
though a grep confirmed the identical `params?.company_id`-prop anti-pattern exists in
roughly 60 more files there — flagged to the user as a separate, much larger,
out-of-scope finding rather than silently continuing into two more epics beyond what
was asked ("Sales aur Purchase").

Verified: `tsc --noEmit` clean, ESLint 0 errors (17 pre-existing unrelated warnings),
and a live Playwright pass logging in, selecting a real company via the (now-working,
from the Epic 9 closure fix) company-detail-page mechanism, then visiting 13 sampled
pages (7 Sales, 6 Purchase) — all 200, zero console errors, and correctly rendering
real (empty, for this test company) data rather than either a stuck loading spinner or
a silent failure — proof the API calls now genuinely reach and are accepted by the
backend, not just that the pages compile.

## Outcome

- ✅ Impact: ~40 Sales and Purchase pages that were silently non-functional (some via
  401 due to no real auth token ever reaching the backend, some via 404 due to
  requests going to the wrong origin entirely) are now genuinely working — not just
  "fixed the literal key requested," but actually reachable and authenticated end to
  end, verified live.
- 🧪 Tests: `tsc`/`eslint` clean; live-browser smoke test across a representative
  sample of both modules, all passing with real (if empty, for the sampled test
  company) data.
- 📁 Files: 40 frontend page files + 2 shared API client files (`sales.ts`,
  `purchase.ts`) changed — see the `files` list above. Zero backend files touched
  (this was purely a frontend connectivity/auth bug).
- 🔁 Next prompts: The same `params?.company_id`-prop pattern (never populated,
  because these routes have no such dynamic segment) exists in ~60 more files across
  Accounting (Epic 8) and Inventory (Epic 5) — flagged, not fixed, pending a separate
  decision from the user on whether/when to address those two epics the same way.
- 🧠 Reflection: What started as a literal "fix the company_id key in 23 files" request
  turned out to require investigating and fixing 3-4 structurally different bug
  classes once the actual behavior was traced end-to-end rather than pattern-matched
  on the surface symptom the user described. Pausing twice to show the user the actual
  discovered scope before proceeding (once for the auth/URL bugs, implicitly again
  when the Accounting/Inventory instance of the same pattern surfaced) kept the fix
  honest and bounded to what was actually asked, rather than either quietly
  under-delivering (a cosmetic key swap that wouldn't have worked) or silently
  over-delivering (rewriting two more epics' frontends without being asked).

## Evaluation notes (flywheel)

- Failure modes observed: none blocking. The double-`API_BASE`-prefix bug in
  `exportSalesReport()` was only caught by actually reading the function's full body
  rather than assuming it followed the same pattern as `apiCall()`/`authHeaders()` in
  the same file — a reminder that "looks like the same file, same fix" doesn't hold
  even within a single module.
- Graders run and results (PASS/FAIL): Self-verified via the live Playwright smoke
  test's own assertions (HTTP status, zero console errors, correct empty-state text
  rather than a stuck spinner or silent failure) — all PASS on the final run.
- Prompt variant (if applicable): n/a.
- Next experiment (smallest change to try): n/a — task complete for the scope agreed
  with the user (Sales + Purchase only).
