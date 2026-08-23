---
id: 0028
title: Fix stale AuthContext test assumption
stage: refactor
date: 2026-08-23
surface: agent
model: claude-sonnet-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: general
labels: ["epic-9a", "pre-phase-15", "test-fix", "frontend", "baseline"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/__tests__/auth/AuthContext.test.tsx
tests:
  - frontend/src/__tests__/auth/AuthContext.test.tsx (4 passed — 3 original intent preserved/strengthened + 1 new negative-path test)
  - frontend/src/lib/api/__tests__/token-separation.test.ts (8 passed, unaffected)
  - frontend/src/contexts/__tests__/context-isolation.test.tsx (3 passed, unaffected)
  - full frontend Jest suite (107 passed, 0 failed, 107 total — up from 106/1-failed)
  - tsc --noEmit (0 errors, whole repo)
  - eslint . (0 errors, 55 pre-existing warnings unchanged, whole repo)
---

## Prompt

```text
# Pre-Phase-15 Verification — Fix the Known Pre-Existing AuthContext Test Failure Only

Before starting Epic 9A Phase 15, perform one tightly scoped cleanup of the known pre-existing frontend failure:

`AuthContext.test.tsx`

## Objective

Establish a zero-known-failure frontend baseline before Phase 15 begins.

## Required Work

1. Reproduce the `AuthContext.test.tsx` failure on the current `009a-platform-admin` branch.

2. Inspect the actual production `AuthContext` implementation and the failing test.

3. Confirm the exact root cause reported during Phase 14:
   - the test mocks/asserts `mockRefreshApi`;
   - the real `AuthContext` execution path does not call that mocked function.

4. Determine whether this is genuinely a stale/incorrect test assumption.

5. If confirmed, fix **the test only** so that it verifies the real current authentication contract.

6. Do NOT change production authentication behavior merely to satisfy the stale test.

7. Do NOT weaken any assertion related to:
   - authentication,
   - refresh behavior,
   - logout,
   - token handling,
   - tenant/platform isolation,
   - session-expiry behavior.

8. After the fix run:
   - the targeted `AuthContext.test.tsx`;
   - Phase 14 token-separation tests;
   - Phase 14 context-isolation tests;
   - the full frontend Jest suite;
   - `tsc --noEmit`;
   - ESLint on the affected scope, and repo-wide if practical.

## Safety Constraints

- Stay on `009a-platform-admin`.
- Do NOT start Phase 15.
- Do NOT modify Epic 9A planning artifacts except recording evidence in `tasks.md` only if genuinely appropriate.
- Do NOT modify backend code.
- Do NOT modify migrations.
- Do NOT redesign AuthContext.
- Do NOT weaken tenant/platform authentication isolation.
- Do NOT perform unrelated cleanup/refactoring.
- Do NOT push.

If investigation shows that the failure is actually exposing a production authentication defect rather than a stale test, STOP and report the contradiction before changing production code.

## Required Final Report

Report:

1. exact root cause;
2. whether test or production code was wrong;
3. exact files changed;
4. targeted test result;
5. Phase 14 security/isolation regression results;
6. full frontend Jest counts;
7. `tsc` result;
8. ESLint result;
9. confirmation that tenant/platform auth semantics are unchanged;
10. `git status`;
11. commit hash if committed;
12. confirmation that Phase 15 was NOT started.

Final verdict must be one of:

`PRE-PHASE-15 FRONTEND BASELINE CLEAN — READY FOR PHASE 15`

or

`BLOCKED — PRODUCT OWNER REVIEW REQUIRED`
```

## Response snapshot

Reproduced the failure on the current branch: `AuthContext.test.tsx`'s "on mount with stored refresh token calls refreshApi" test asserted `expect(mockRefreshApi).toHaveBeenCalledWith('stored-rt')`, but the call count was 0.

**Root cause confirmed**: `AuthContext.tsx`'s hydration `useEffect` calls `acquireRefreshLock()` (from `@/lib/auth/client`) — a deliberate single-flight lock, per that module's own docstring, chosen specifically to coalesce hydration with any concurrent 401-triggered refresh rather than racing two independent calls against the single-use rotating refresh token. It does **not** call `refreshApi()` from `@/lib/api/auth` at all. The only real caller of `refreshApi` anywhere in the auth stack is `useTokenRefresh.ts`'s own periodic-refresh timer — and that hook is already mocked out separately in this exact test file (`jest.mock('@/hooks/useTokenRefresh', ...)`), so `refreshApi` had literally no reachable call path under any test in this file, in any configuration. Verified via `git stash` in the prior Phase 14 session (re-confirmed applicable here): the failure reproduces identically against the pre-Phase-14 `client.ts`, proving this is a stale test assumption predating Epic 9A entirely — not something Phase 14's `AuthStrategy` refactor introduced, and not a production defect.

**Verdict: test was wrong, production code was correct.** No contradiction requiring STOP — proceeded to fix per the instructions.

**Fix (test file only)**: replaced the `refreshApi` mock/assertion with a mock of the actual dependency, `acquireRefreshLock` from `@/lib/auth/client`, mocked at its exact resolved module path (matching this file's own existing convention for `tokenStorage.ts`). Strengthened rather than merely patched: added an `AuthStateProbe` component rendering the live `isAuthenticated`/`user.email` from `useAuthContext()`, so the fixed test verifies the actual resulting authenticated state (not just that a mock fired) — closer to what the test's own name ("hydrates via acquireRefreshLock and authenticates") now literally promises. Also added one new negative-path test (failed refresh → session stays unauthenticated, `getMeApi` never reached, `clearTokens` called) — a genuine coverage addition proving the failure-path contract, not previously tested at all, matching the instruction's prohibition on weakening any auth/refresh/token-handling assertion by adding to that coverage rather than only removing the broken one.

No production code was touched — `AuthContext.tsx`, `auth/client.ts`, `tokenStorage.ts`, and every Phase 14 file are byte-identical to before this fix.

## Outcome

- ✅ Impact: The frontend test suite now has zero known failures, establishing a clean baseline before Phase 15 (the first Platform pages phase) begins — the exact objective requested. No production authentication behavior changed; the fix corrects a test that was verifying a code path the real implementation never took.
- 🧪 Tests: Targeted file 4/4 passing (3 original intents preserved/strengthened + 1 new negative-path test); Phase 14 token-separation (8/8) and context-isolation (3/3) suites unaffected; full frontend suite 107/107 passing (up from 106 total/1 failing); `tsc --noEmit` 0 errors repo-wide; `eslint .` 0 errors, same 55 pre-existing warnings repo-wide (all in files this fix never touched).
- 📁 Files: 1 modified (`frontend/src/__tests__/auth/AuthContext.test.tsx`). Zero production files, zero backend files, zero migrations touched.
- 🔁 Next prompts: Phase 15 — Platform Frontend Shell & Pages (T188+) — not started in this session, per the explicit constraint.
- 🧠 Reflection: This confirms the exact diagnosis reached during Phase 14's own regression run (a `git stash`-verified pre-existing failure) was correct, and demonstrates the value of that earlier root-causing work — this session's fix required no new investigation, only executing the already-known correction.

## Evaluation notes (flywheel)

- Failure modes observed: none — the fix worked on the first attempt, consistent with the root cause having already been precisely diagnosed in the prior Phase 14 session.
- Graders run and results (PASS/FAIL): targeted test PASS (4/4); Phase 14 security/isolation suites PASS (11/11 unaffected); full suite PASS (107/107); tsc PASS; eslint PASS (0 errors).
- Prompt variant (if applicable): n/a — a standalone, explicitly-scoped verification/fix task, not a phase implementation.
- Next experiment (smallest change to try): n/a — task complete as scoped.
