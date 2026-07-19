---
id: "0011"
title: implement epic2 phase11 token lifecycle
stage: green
date: 2026-07-14
surface: agent
model: claude-sonnet-4-6
feature: 002-auth-identity
branch: 002-auth-identity
user: shehla83
command: /sp.implement
labels: ["frontend","auth","token-refresh","session","phase11"]
links:
  spec: specs/002-auth-identity/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/contexts/AuthContext.tsx
  - frontend/src/hooks/useAuth.ts
  - frontend/src/contexts/__tests__/AuthContext.test.tsx
  - frontend/src/hooks/__tests__/useAuth.test.tsx
  - frontend/src/lib/api/__tests__/auth.test.ts
  - specs/002-auth-identity/tasks.md
tests:
  - frontend/src/contexts/__tests__/AuthContext.test.tsx (4 tests)
  - frontend/src/hooks/__tests__/useAuth.test.tsx (4 tests)
  - frontend/src/lib/api/__tests__/auth.test.ts (2 tests)
  - Full suite: 29 passed
---

## Prompt

EPIC 2 – AUTHENTICATION IMPLEMENTATION PHASE 11. Implement ONLY Phase 11 (T090–T093). Phase 11 boundary strictly enforced — do NOT implement Phase 12+.

## Response snapshot

Implemented all 4 Phase 11 tasks:

**T090** — Wired `useTokenRefresh` into `AuthContext.tsx`: imported hook and called it with `{ expiresIn, onLogout: logout }`. Timer starts automatically when `expiresIn > 0` (after successful login/hydration) and clears when `expiresIn` is set to `null` on logout — no memory leak.

**T091** — Added session-expired notification banner in `AuthProvider`: `sessionExpiredVisible` state toggled by the `session-expired` event handler (already registered in Phase 10). Banner renders as a `role="alert"` fixed banner at top of page with "Your session has expired. Please log in again." and a dismiss button. No external toast library needed.

**T092** — Verified `remember_me` flag flows end-to-end: `LoginForm` schema → `useAuth.login(rememberMe)` → `ctx.login(rememberMe)` → `loginApi(email, pass, rememberMe)` → `{ remember_me: rememberMe }` in request body. Test asserts the flag is forwarded and the long `expires_in` is returned.

**T093** — Added `logoutAllDevices()` to `useAuth` hook: calls `ctx.logout()` (which calls `logoutApi()` — backend revokes all sessions via `revoke_all_by_user()` per spec FR-012) then navigates to `/login`. Documented in JSDoc with spec reference.

## Outcome

- ✅ Impact: Token lifecycle fully wired — auto-refresh timer active, session-expired banner visible, remember_me verified, logoutAllDevices added
- 🧪 Tests: 29/29 frontend tests pass (10 new + 19 existing, 0 regressions)
- 📁 Files: 5 files modified/created; tasks.md updated
- 🔁 Next prompts: Phase 12 (protected routing — auth layout, route groups, dashboard page)
- 🧠 Reflection: No toast library available; inline state-based banner in AuthProvider is YAGNI-compliant and avoids a new dependency

## Evaluation notes (flywheel)

- Failure modes observed: none — all tests passed first run
- Graders run and results (PASS/FAIL): jest full suite PASS (29/29)
- Prompt variant (if applicable): /sp.implement with strict phase boundary
- Next experiment (smallest change to try): Phase 12 routing — verify AuthProvider wrapping in protected layout doesn't create double-provider issues
