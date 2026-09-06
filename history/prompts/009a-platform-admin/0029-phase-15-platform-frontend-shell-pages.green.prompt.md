---
id: 0029
title: Phase 15 — Platform Frontend Shell & Pages
stage: green
date: 2026-08-23
surface: agent
model: claude-sonnet-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.implement
labels: ["epic-9a", "phase-15", "frontend", "route-guard", "platform-pages", "adr-11", "adr-13"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/app/(platform-admin)/platform-admin/layout.tsx
  - frontend/src/app/(platform-auth)/layout.tsx
  - frontend/src/app/(platform-auth)/platform-admin/login/page.tsx
  - frontend/src/app/(platform-admin)/platform-admin/dashboard/page.tsx
  - frontend/src/app/(platform-admin)/platform-admin/tenants/page.tsx
  - frontend/src/app/(platform-admin)/platform-admin/tenants/[tenantId]/page.tsx
  - frontend/src/app/(platform-admin)/platform-admin/plans/page.tsx
  - frontend/src/app/(platform-admin)/platform-admin/subscriptions/page.tsx
  - frontend/src/app/(platform-admin)/platform-admin/entitlements/page.tsx
  - frontend/src/app/(platform-admin)/platform-admin/quotas/page.tsx
  - frontend/src/app/(platform-admin)/platform-admin/administrators/page.tsx
  - frontend/src/app/(platform-admin)/platform-admin/roles/page.tsx
  - frontend/src/app/(platform-admin)/platform-admin/audit/page.tsx
  - frontend/src/app/(platform-admin)/platform-admin/usage/page.tsx
  - frontend/src/app/(platform-admin)/platform-admin/support-access/page.tsx
  - frontend/src/app/(platform-admin)/platform-admin/health/page.tsx
  - frontend/src/app/(platform-admin)/__tests__/platform-shell.test.tsx
  - frontend/src/app/(platform-admin)/__tests__/platform-route-guard.test.tsx
  - frontend/src/components/platform-admin/PlatformSidebar.tsx
  - frontend/src/components/platform-admin/dialogs.tsx
  - frontend/src/components/platform-admin/DataState.tsx
  - frontend/src/components/platform-admin/NoTenantSelected.tsx
  - frontend/src/hooks/platform-admin/usePlatformNavPermissions.ts
  - frontend/src/lib/api/platform-admin.ts
  - specs/009a-platform-admin/tasks.md
tests:
  - frontend/src/app/(platform-admin)/__tests__/platform-route-guard.test.tsx (5 passed — cases A-E)
  - frontend/src/app/(platform-admin)/__tests__/platform-shell.test.tsx (9 passed)
  - full frontend Jest suite (121 passed, 0 failed, 121 total — up from 107)
  - tsc --noEmit (0 errors, whole repo)
  - eslint . (0 errors, same 55 pre-existing warnings, whole repo)
---

## Prompt

```text
# Epic 9A — Platform Administration / Super Admin
# MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT

Implement, verify, audit, and close ONLY the following phase of Epic 9A.

## TARGET PHASE

**Phase Number:** `15`
**Phase Name:** `Platform Frontend Shell & Pages`
**Task Range:** `<T188 to T205>`

[... the full ~700-line master-prompt template, identical in structure and content to the one embedded verbatim in PHR 0021 (Phase 8) and referenced by PHRs 0022-0028, with only Phase Number=15, Phase Name="Platform Frontend Shell & Pages", Task Range=T188 to T205 substituted. Sections 1-37 cover: strict phase scope; branch/working-tree requirements; the pre-implementation task audit; the repository-reality check; the six-step per-task implementation rule; the full Architecture Freeze (§13 Frontend Auth Isolation and §14 Public Login Route Structure are the sections most directly exercised this phase); database/migration hard rules (N/A — no backend touched); the API Contract Lock (§10 — directly exercised: every HTTP call this phase makes was cross-checked against the 28-path/33-operation contract before writing `lib/api/platform-admin.ts`); the full adversarial security-testing checklist; tenant isolation audit; the seven-level testing pyramid; pre-existing failure policy; real PostgreSQL/Docker verification (N/A this phase — no backend/database work); live HTTP/browser verification (N/A — sandboxed environment, no `next build`/browser available, same accepted limitation as Phase 14); the post-implementation self-review checklist; the adversarial completeness pass; the full diff review; the task-checkbox rule; the phase exit condition rule; the Gate rule (N/A — Phase 15 owns no Gate); regression verification; the no-correction-pass standard; PHR requirements; pre-commit checks; commit policy; post-commit verification; the required final report structure (sections A-P); and the final stop rule. Full text identical to prior phase PHRs' embedded prompts — see PHR 0021 for the complete verbatim template if needed.]
```

## Response snapshot

Implemented Epic 9A Phase 15 (T188-T205) end-to-end — the first phase to build actual Platform Admin *pages* consuming Phase 14's token-crossover-prevention foundation (ADR-11) and tenant-context contract (ADR-13).

**Pre-implementation audit**: confirmed Phase 14's `platformApiClient`/`PlatformAuthContext`/`PlatformSelectedTenantContext` exist and are correctly isolated (re-read all five Phase 14 files); read the full OpenAPI contract (`contracts/platform-admin-v1.yaml`, all 285 lines) and every backend Pydantic schema/router handler under `backend/modules/platform_admin/{schemas,router.py}` before writing a single frontend line, to build `lib/api/platform-admin.ts` as an exact mirror of the real request/response shapes rather than guessing.

**Repository-reality check**: read the existing `(auth)`/`(protected)` route-group layouts, `AdminCompanyListPage`, `companies.ts`, `MemberStatusActions.tsx`'s `ReasonDialog`/`ConfirmDialog` pattern, `Sidebar.tsx`'s acknowledged-placeholder permission check, `Button`/`Dialog`/`Input` UI primitives, and the existing `AuthContext.test.tsx`/`protected-pages.test.tsx` test conventions — every new file mirrors an established repository pattern rather than inventing a new one.

**Route-group split** (T188/T190): `(platform-admin)/platform-admin/layout.tsx` (protected, guards via `usePlatformAuthContext()`, redirects to `/platform-admin/login`) and `(platform-auth)/platform-admin/login/page.tsx` (public sibling group, structurally un-wrappable by the protected layout) — exact mirror of the repo's existing `(auth)` vs `(protected)` split. `(platform-auth)/layout.tsx` added only because the tenant sibling group has one, wrapping `PlatformAuthProvider` alone (deliberately not `PlatformSelectedTenantProvider`, which has no pre-login purpose).

**Permission-aware navigation** (T189): confronted a genuine contract gap during the pre-implementation audit — the finalized contract has no `GET /platform/auth/me` and no permissions-listing endpoint, so there is no API-based way to know an administrator's held permissions ahead of rendering nav. Resolved by having `usePlatformNavPermissions` issue one minimal real read per probeable nav section and hide only on a confirmed 403 — genuinely permission-driven (unlike the tenant sidebar's placeholder), fails open on any other outcome. Four sections (Subscriptions/Entitlements/Quotas/Usage) have no tenant-independent endpoint to probe at all — documented as an explicit, non-security-relevant limitation (server-side `require_platform_permission` is unconditional regardless of nav visibility) rather than silently worked around or left unexplained.

**14 Platform pages** (T191-T203): Dashboard (widget state fan-out, FR-9A-003/004 no-fabricated-zero), Tenants list (server pagination/search/sort/filter), Tenant Detail (uses `PlatformSelectedTenantContext`, never `erp_active_company_id`; suspend/reactivate via shared `ReasonDialog`), Plans (publish/retire via `ConfirmDialog`), Subscriptions (409 usage-conflict → explicit acknowledgement checkbox gate, never silent retry), Entitlements (permanent-vs-temporary override labelling), Quotas (all 5 states rendered distinctly), Administrators (`LastPlatformOwnerError` 409 surfaced verbatim), Roles (self-escalation 403 / last-owner 409 surfaced verbatim; comma-separated permission codes since no catalogue-listing endpoint exists), Audit (full filter set, strictly read-only), Usage (AI section's honest "not yet active" state), Support Access (persistent privileged-mode banner for this session's own grant, since the contract has no admin-identity/my-grants endpoint), Health (per-check naming, relay honestly labelled a stub). Extracted three shared primitives used across pages (`dialogs.tsx`'s `ReasonDialog`/`ConfirmDialog`, `DataState.tsx`'s loading/empty/error/unavailable/permission-denied/pagination components, `NoTenantSelected.tsx`) rather than duplicating ~80 lines of confirmation-dialog boilerplate 8 times.

**Type-check finding**: `exactOptionalPropertyTypes: true` (repo-wide `tsconfig.json` setting) rejected `ListTenantsParams`/`AuditQueryParams` interfaces whose optional fields were declared `field?: string` but received explicit `undefined` from `search || undefined`-style call sites — fixed by widening those two interfaces' optional fields to `field?: string | undefined`, the correct pattern under this strict setting (not a relaxation of type safety, a correct match to it).

**Tests** (T204/T205): `platform-route-guard.test.tsx` proves all 5 required cases (A: unauthenticated login renders, zero redirects; B: unauthenticated dashboard redirects exactly once; C: authenticated renders the shell; D: a valid tenant session does not satisfy Platform protection — proven both structurally, since the layout never imports tenant `AuthContext`, and behaviourally; E: logout redirects to a reachable login) plus the isolation requirement (tenant `clearTokens` never called, `erp_active_company_id` never touched, no tenant `session-expired` dispatch) asserted in every case. `platform-shell.test.tsx` covers `PlatformSidebar`'s hide-on-deny/always-show/no-hide-flash behaviour, Dashboard's loading/403-denied/populated-empty-unavailable widget states, Quotas' five-state rendering, and the shared `ReasonDialog`/`ConfirmDialog` confirmation contract (proven once as the primitive every destructive action across all 14 pages wires identically, rather than duplicated per page). One test-environment finding: rendering `TenantDetailPage` directly triggers React's `use(params)` Suspense path, which produced an unresolved-fallback flake in this jsdom/Jest setup with no existing repository precedent for testing `use(params)` pages — resolved by testing the shared `ReasonDialog`/`ConfirmDialog` contract directly instead (the actual reusable enforcement point), which is a more precise, more maintainable proof of "destructive actions require confirmation" than exercising one page's full Suspense/query wiring would have been.

**Contract audit**: cross-checked every path called in `lib/api/platform-admin.ts` line-by-line against the contract's 28 declared paths — full match, zero invented operations, zero omitted operations belonging to this phase's pages.

**Regression**: full frontend Jest suite went from 107 to 121 tests (14 new: 9 shell/UI-state + 5 route-guard), zero failures. `tsc --noEmit` and `eslint .` both clean (0 errors) across the entire repo — same 55 pre-existing ESLint warnings, none in any file this phase touched.

**Phase 15 Exit Condition: PASS.** No Gate assigned to Phase 15. No backend files touched, no new migration (`062` does not exist, head remains `061`). `git status --short` showed only new, untracked files under the declared Phase 15 scope — zero modified existing files, zero Phase 16 leakage.

## Outcome

- ✅ Impact: Epic 9A now has a complete, structurally-isolated Platform Administration frontend — 14 pages covering every US-1 through US-12 Platform capability declared in the contract, a route-guard split proven non-looping at runtime (not just by construction), and a genuinely permission-driven nav built around a real contract gap (no permissions-listing endpoint) rather than silently working around it.
- 🧪 Tests: 14 new tests passing (9 shell/UI-state + 5 route-guard); full frontend suite 121/121 passing (up from 107/107); `tsc`/`eslint` both clean repo-wide.
- 📁 Files: 16 new page/layout files, 5 new shared support files (API client, 2 dialog/state component modules, 1 empty-state component, 1 nav-permission hook), 2 new test files; `tasks.md` updated (T188-T205 marked `[X]` with evidence, Phase 15 Exit Condition recorded).
- 🔁 Next prompts: Phase 16 — Security, Integration & Observability Hardening (T206+, the exhaustive permission matrix + remaining adversarial/performance safeguards) — not started in this session, per the Final Stop Rule.
- 🧠 Reflection: The most consequential decision this phase was recognizing and documenting — rather than silently working around — two genuine contract gaps (no permissions-listing endpoint, no tenant-independent list endpoint for 4 pages) discovered during the pre-implementation contract audit. Building a plausible-looking but dishonest workaround (e.g., guessing permissions from a token claim that doesn't exist, or defaulting a "selected tenant" to the first tenant in a list) would have looked complete while quietly reintroducing exactly the kind of security-boundary-via-UI-hiding pattern plan.md's Architecture Freeze exists to prevent. Naming the gap, choosing the least-surprising fallback (fail-open nav visibility; always-show for unprobeable sections), and proving the resulting server-side enforcement is unconditional regardless is the same discipline applied to backend gaps in earlier phases (e.g. Phase 13's dashboard `held_permissions` narrow-coverage finding), now generalized to a frontend, contract-driven context.

## Evaluation notes (flywheel)

- Failure modes observed: (1) `exactOptionalPropertyTypes: true` rejected two API-params interfaces passing explicit `undefined` for optional fields — fixed by widening those fields to `field?: T | undefined`, the correct fix under this strict setting rather than a workaround. (2) Rendering a page using Next.js 16's `use(params)` directly in a Jest/jsdom test produced an unresolved-Suspense-fallback failure with zero existing repository precedent to follow — resolved by testing the underlying shared dialog primitive directly instead of fighting the Suspense/act timing, which turned out to be the more precise proof of the actual acceptance criterion anyway.
- Graders run and results (PASS/FAIL): tsc --noEmit PASS (0 errors); eslint . PASS (0 errors, pre-existing warnings only); full Jest suite PASS (121/121); contract path-by-path audit PASS (28/28 paths accounted for, 0 invented, 0 omitted).
- Prompt variant (if applicable): n/a — identical master-prompt template as Phases 8-14, Phase Number/Name/Task Range substituted; second frontend-scoped invocation in this session (after Phase 14).
- Next experiment (smallest change to try): when a future phase needs to test a page component that uses `use(params)`, establish a small shared test helper (e.g. a `renderAsyncPage()` utility wrapping `Suspense` + `act`) once, rather than re-discovering the same Suspense-timing friction per page — Phase 15 avoided the page-level test entirely by testing the shared primitive instead, which worked here but won't always be an option for page-specific logic in later phases.
