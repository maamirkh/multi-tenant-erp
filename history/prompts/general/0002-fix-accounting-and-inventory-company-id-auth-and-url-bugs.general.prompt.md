---
id: 0002
title: Fix Accounting and Inventory company_id, auth, and URL bugs
stage: green
date: 2026-08-18
surface: agent
model: claude-sonnet-5
feature: none
branch: 009-crm
user: Muhammad Amir
command: none
labels: ["accounting", "inventory", "frontend", "bugfix", "auth", "routing"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - frontend/src/app/(protected)/(accounting)/**/*.tsx (45 files)
 - frontend/src/app/(protected)/(inventory)/**/*.tsx (21 files)
tests:
 - docker exec erp-system-web-1 npx tsc --noEmit (clean)
 - docker exec erp-system-web-1 npx eslint "src/app/(protected)/(inventory)/**/*.tsx" (0 errors, pre-existing exhaustive-deps warnings only)
 - Playwright live smoke test: 20 pages (13 Inventory + 7 Accounting) via /tmp/.../scratchpad/verify_inv_acct.js — all 200, zero console/API errors
---

## Prompt

Accounting aur Inventory ke files bhi fix kardo

(Continuation of a prior request: "Sales aur Purchase ke 23 files bhi fix kardo", where the user chose "Sab kuch poora fix karo" — fix everything properly. During that investigation, the same bug pattern was found to also exist in Accounting (Epic 8) and Inventory (Epic 5) and was explicitly flagged to the user as out of scope at the time. The user has now explicitly asked to fix these too.)

## Response snapshot

Found and fixed the same 3-bug-class pattern already fixed in Sales/Purchase, now across Accounting (45 files) and Inventory (21 files):

1. **Wrong company_id source** — pages read `useParams().company_id` / `.companyId` from a route segment that doesn't actually exist in these routes (no `[company_id]` folder anywhere in these route trees), so `companyId` was always `undefined`. Replaced with the real source: `localStorage.getItem("erp_active_company_id")`, written by `CompanyContext.setActiveCompany()`.
2. **Broken auth** — several pages either sent `credentials: "include"` (a cookie-based pattern the API never uses) or read the wrong localStorage key `"access_token"` (never populated — the real token lives only in-memory via `getAccessToken()` from `tokenStorage.ts`, by design for XSS mitigation). Replaced with `Authorization: Bearer ${getAccessToken()}` on every raw `fetch()` call.
3. **Wrong/relative URLs** — several raw-fetch calls hit relative paths like `/api/v1/companies/...` with no origin, which only work if the frontend and API share a host (they don't in this dev setup: web on :3000, api on :8000). Added `const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"` and prefixed every fetch URL / `baseUrl` construction with it.

Accounting had zero raw-fetch files (everything already routes through the already-correct `lib/api/accounting.ts`), so only the `company_id` derivation needed fixing across 45 page files — 40 auto-fixed via a Python regex script, 5 files with a genuine extra dynamic segment (`accountId`, `customerId`, `supplierId`, `yearId` ×2) hand-fixed to keep `useParams()` for that real segment while sourcing `companyId` from localStorage.

Inventory needed the full fix in most files: 11 files had raw `fetch()` calls needing all 3 fixes; 3 files had a genuine extra dynamic segment (`id` ×2, `warehouse_id`); 5 files used a camelCase `companyId` param (still fake) routed through the already-token-aware `lib/api/inventory.ts` client, needing only the companyId-source fix; 2 files (`reports/page.tsx`, `reports/kpis/page.tsx`) had the `access_token`-wrong-key variant of the auth bug. Also found and fixed a 4th bug: `products/page.tsx`, `products/[id]/page.tsx`, and `products/[id]/variants/page.tsx` linked to a nonexistent `/companies/{id}/inventory/products/...` route — no such route exists in this app (Inventory routes are flat: `/inventory/...`, no company prefix) — corrected to `/inventory/products/...`, matching every other Inventory page's Link pattern.

Verified via `tsc --noEmit` (clean), `eslint` (0 errors — fixed one resulting unused-prop lint error in `products/page.tsx` after removing the now-unnecessary `companyId` prop from `ProductRow`), and a live Playwright smoke test hitting 13 Inventory pages + 7 Accounting pages after a full `docker restart` of the web container: all 20 returned HTTP 200 with zero console errors and zero API 4xx/5xx responses. The Inventory KPI Dashboard — one of the pages that had the `access_token` wrong-key bug — now shows live fetched data (`As of 8/18/2026, 11:54:12 PM · 90-day lookback`), confirming the auth fix works end-to-end, not just that the page renders.

## Outcome

- ✅ Impact: Accounting (45 files) and Inventory (21 files) frontend pages now correctly resolve the active company, authenticate every API call, and target the real backend origin — completing the same fix already applied to Sales, Purchase, and CRM. All previously "dead" pages (silently failing due to `companyId === undefined`) are now functional.
- 🧪 Tests: tsc clean; eslint clean (pre-existing exhaustive-deps warnings only, not introduced by this change); live Playwright smoke test — 20/20 pages 200 OK, 0 console errors, 0 API errors.
- 📁 Files: 66 frontend page files across `(protected)/(accounting)/` and `(protected)/(inventory)/`.
- 🔁 Next prompts: none requested; user asked only for Accounting + Inventory fix.
- 🧠 Reflection: This closes out the systemic company-context bug across all 5 remaining epics that had it (CRM, Sales, Purchase, Accounting, Inventory) — every epic's frontend now sources the active company the same way.

## Evaluation notes (flywheel)

- Failure modes observed: none during this fix; the pattern from Sales/Purchase generalized cleanly, though Inventory had more variation (camelCase param names, 3 distinct extra-dynamic-segment shapes, a `baseUrl`-variable-reuse pattern, and its own instance of the `access_token`-wrong-key bug) requiring per-file reads rather than a single blind regex pass.
- Graders run and results (PASS/FAIL): tsc PASS, eslint PASS, live smoke test PASS (20/20).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
