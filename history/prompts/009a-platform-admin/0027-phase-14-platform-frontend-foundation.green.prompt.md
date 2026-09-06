---
id: 0027
title: Phase 14 — Platform Frontend Foundation
stage: green
date: 2026-08-23
surface: agent
model: claude-sonnet-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.implement
labels: ["epic-9a", "phase-14", "frontend", "auth-strategy", "token-separation", "context-isolation", "adr-11", "adr-13"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/lib/api/client.ts
  - frontend/src/lib/auth/tenantAuthStrategy.ts
  - frontend/src/lib/platform-auth/platformTokenStorage.ts
  - frontend/src/lib/platform-auth/platformAuthClient.ts
  - frontend/src/lib/api/platform.ts
  - frontend/src/lib/tenant-context/activeCompany.ts
  - frontend/src/contexts/PlatformAuthContext.tsx
  - frontend/src/contexts/PlatformSelectedTenantContext.tsx
  - frontend/src/lib/api/__tests__/token-separation.test.ts
  - frontend/src/contexts/__tests__/context-isolation.test.tsx
  - specs/009a-platform-admin/tasks.md
tests:
  - frontend/src/lib/api/__tests__/token-separation.test.ts (8 passed)
  - frontend/src/contexts/__tests__/context-isolation.test.tsx (3 passed)
  - full frontend Jest suite (105 passed, 1 pre-existing failure unrelated to this phase, 106 total)
  - tsc --noEmit (0 errors, whole repo)
  - eslint . (0 errors, 55 pre-existing warnings in untouched files, whole repo)
---

## Prompt

```text
# Epic 9A — Platform Administration / Super Admin
# MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT

Implement, verify, audit, and close ONLY the following phase of Epic 9A.

## TARGET PHASE

**Phase Number:** `14`
**Phase Name:** `Platform Frontend Foundation`
**Task Range:** `<T178 to T187>`

[... the full ~700-line master-prompt template, identical in structure to the one embedded verbatim in PHRs 0021-0026 (Phases 8-13), with only Phase Number=14, Phase Name="Platform Frontend Foundation", Task Range=T178 to T187 substituted. Sections 1-37 cover: strict phase scope; branch/working-tree requirements; the pre-implementation task audit; the repository-reality check; the six-step per-task implementation rule; the full Architecture Freeze (including §13 Frontend Auth Isolation and §14 Public Login Route Structure, directly relevant to this phase for the first time); database/migration hard rules (N/A — no backend touched); the API Contract Lock (N/A — no new HTTP operations); the full adversarial security-testing checklist; tenant isolation audit; the seven-level testing pyramid; pre-existing failure policy; real PostgreSQL/Docker verification (N/A this phase); live HTTP/browser verification; the post-implementation self-review checklist; the adversarial completeness pass; the full diff review; the task-checkbox rule; the phase exit condition rule; the Gate rule; regression verification; the no-correction-pass standard; PHR requirements; pre-commit checks; commit policy; post-commit verification; the required final report structure (sections A-P); and the final stop rule. Full text identical to prior phase PHRs' embedded prompts — see PHR 0026 for the complete verbatim template if needed.]
```

## Response snapshot

Implemented Epic 9A Phase 14 (T178-T187) end-to-end — Epic 9A's first frontend phase, and the first phase in this entire session touching `frontend/` rather than `backend/`: the structural token-crossover-prevention refactor (ADR-11) and the canonical tenant-context accessor (ADR-13), completed before any Platform page exists to consume them.

**Repository-reality check**: read the existing `ApiClient`/`tokenStorage.ts`/`auth/client.ts`/`AuthContext.tsx`/`CompanyContext.tsx`/`useTokenRefresh.ts` in full before writing anything, to mirror established conventions exactly rather than inventing new ones — this surfaced the `useTokenRefresh` reuse hazard detailed below (T185) before any code was written against it.

**ApiClient refactor** (T178/T179): `AuthStrategy` interface `{getToken, refresh, onAuthFailure}` now injected via constructor; `buildHeaders()`, the 401-retry branch, and `postMultipart()` all route through `this.auth` exclusively — `client.ts` no longer imports any token-storage module directly. `tenantAuthStrategy.ts` relocates the exact pre-existing calls behind the interface, **deliberately preserving** a pre-existing double-dispatch quirk (the `session-expired` event fires twice on refresh failure — once inside `acquireRefreshLock()`'s own catch, once inside the strategy's `onAuthFailure()`) rather than "fixing" it, since T179 mandates byte-identical behavior, not improved behavior. Verified via `git stash` + isolated test run that this quirk (and one unrelated pre-existing test bug) predates this phase entirely.

**Platform token storage/client/API client** (T180/T181): `platformTokenStorage.ts`/`platformAuthClient.ts` mirror the tenant modules exactly but with `erp_platform_refresh_token` (never `erp_refresh_token`) and a wholly separate `_platformRefreshPromise` singleton lock (`acquirePlatformRefreshLock`), dispatching `platform-session-expired` (never the tenant `session-expired`) on failure. `platform.ts` exports `platformApiClient` (backed by an inline `platformAuthStrategy`, per T181's own file-scope) and `platformBase()`.

**Token-separation tests** (T182/T183): 8 tests exercising the real singleton clients end-to-end against a mocked `global.fetch` — zero crossover in either direction, independent refresh endpoints, a failed refresh in one domain proven to leave the other's tokens/events completely untouched, and a concurrent-401 case proving neither lock coalesces onto the other. Two assertions initially failed for the wrong reason (expected 1 event dispatch, got 2) — root-caused to the deliberately-preserved double-dispatch behavior above, not a defect; fixed the test assertions to expect the real, correct count with an explanation, not the underlying code.

**Canonical tenant-context accessor** (T184): `activeCompany.ts` — three plain functions over the exact `erp_active_company_id` key `CompanyContext.tsx` already uses. `CompanyContext.tsx` itself untouched; no existing module migrated (explicitly out of scope per the task's own purpose statement).

**PlatformAuthContext / PlatformSelectedTenantContext** (T185/T186): `PlatformAuthProvider` is fully self-contained (no import of `AuthContext.tsx`, no shared state, its own `platform-session-expired` listener). **Contract finding**: the finalized contract declares no `GET /platform/auth/me` — confirmed by re-reading the public-operations section — so this context tracks authentication status only, unlike tenant `AuthContext`'s fetched `user` profile. Deliberately does not build an auto-refresh timer hook: `useTokenRefresh` is tenant-specific (hardcodes `/login` and tenant `refreshApi`/`tokenStorage` internally) and reusing it directly would have redirected Platform sessions to the tenant login page — exactly the kind of "ineffective legacy reuse" this phase exists to prevent; no such hook is declared in T185's file list, so it was correctly left out rather than silently built anyway. `PlatformSelectedTenantContext` is pure `useState` (zero localStorage code), nested inside `PlatformAuthProvider`, and clears its selection whenever `isAuthenticated` transitions to `false` — covering both explicit logout and session-expiry with no separate event wiring.

**Context isolation test** (T187): 3 tests proving both directions of BR-9A-035 — selecting a Platform-inspected tenant leaves a pre-existing `erp_active_company_id` value completely untouched; pre-manipulating `erp_active_company_id` grants neither Platform authentication nor a populated tenant selection; and (proving T186's own "cleared on logout" acceptance directly) a genuinely-authenticated-then-logged-out session clears the selection via a real `isAuthenticated` true→false transition.

**Regression**: full frontend Jest suite went from 95 to 106 tests (11 new), with the same single pre-existing failure both before and after this phase's changes (confirmed via `git stash` isolating the exact commit-HEAD `client.ts` against the failing test — reproduces identically). `tsc --noEmit` and `eslint .` both clean (0 errors) across the entire repo — 55 pre-existing ESLint warnings, none in any file this phase touched. `next build` was not runnable in this sandboxed environment (no network, no local binary) — acceptable given this phase creates no App Router pages at all (that is Phase 15's scope) and `tsc`+ESLint+Jest already provide strong static/behavioral verification for the file types this phase actually touches (contexts, lib modules).

**Phase 14 Exit Condition: PASS.** No Gate assigned to Phase 14. No backend files touched, no new migration.

## Outcome

- ✅ Impact: The structural foundation that makes Platform/tenant token crossover *impossible by construction* (not merely by convention) now exists, along with a proven-isolated tenant-selection context for Platform Admin's future inspection UI — both fully tested and zero-regression before a single Platform page has been built, exactly matching this phase's stated purpose of sequencing foundation before consumption.
- 🧪 Tests: 11 new tests passing (8 token-separation + 3 context-isolation); 105/106 full frontend suite passing (1 confirmed pre-existing, unrelated failure); `tsc`/`eslint` both clean repo-wide.
- 📁 Files: 8 new files (2 lib/platform-auth, 1 lib/api/platform.ts, 1 lib/auth/tenantAuthStrategy.ts, 1 lib/tenant-context, 2 contexts) + 2 new test files, 1 modified file (`client.ts`), tasks.md updated.
- 🔁 Next prompts: Phase 15 — Platform Frontend Shell & Pages (T188+, the first Platform pages, `(platform-admin)`/`(platform-auth)` route groups) — not started in this session, per the Final Stop Rule.
- 🧠 Reflection: The most consequential decision this phase wasn't a new pattern but a *restraint* — recognizing that `useTokenRefresh` looked reusable (generic-sounding interface) but was actually tenant-hardcoded internally, and that reusing it would have silently reintroduced the exact crossover bug this phase exists to prevent. Reading the dependency's actual implementation before reusing it, rather than trusting its interface signature, is the same discipline this session has applied consistently to backend services (e.g. Phase 13's `require_super_admin()` finding) — now proven to generalize to frontend code too.

## Evaluation notes (flywheel)

- Failure modes observed: (1) `jest.spyOn(global, 'fetch')` fails in this project's jsdom test environment because `fetch` is not a pre-existing property on `global` (must direct-assign `global.fetch = jest.fn()` instead) — no prior test file in this codebase mocked `fetch` at the global level, so this was a genuinely new pattern requiring discovery through a failing run rather than precedent. (2) Writing a test assertion based on an assumed "clean" behavior (exactly 1 event dispatch) without first tracing the actual pre-existing call graph produced two initially-wrong assertions — the fix was to correct the test's expectation to match the real, intentionally-preserved behavior, not to alter the production code to match the test.
- Graders run and results (PASS/FAIL): tsc --noEmit PASS (0 errors); eslint . PASS (0 errors, pre-existing warnings only); full Jest suite PASS except 1 confirmed-pre-existing failure (verified via git stash isolation).
- Prompt variant (if applicable): n/a — identical master-prompt template as Phases 8-13, Phase Number/Name/Task Range substituted; first frontend-scoped invocation in this session.
- Next experiment (smallest change to try): when reusing an existing hook/utility across a new domain boundary (tenant → Platform here), always read its full implementation for hardcoded domain-specific calls before assuming its generic-looking interface makes it safely reusable — the interface signature alone is not sufficient evidence.
