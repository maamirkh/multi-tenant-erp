---
id: "0012"
title: implement epic2 phase12 protected routing
stage: green
date: 2026-07-14
surface: agent
model: claude-sonnet-4-6
feature: 002-auth-identity
branch: 002-auth-identity
user: shehla83
command: /sp.implement
labels: ["frontend","auth","routing","route-guard","phase12"]
links:
  spec: specs/002-auth-identity/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/app/layout.tsx
  - frontend/src/app/(auth)/layout.tsx
  - frontend/src/app/(auth)/login/page.tsx
  - frontend/src/app/(auth)/forgot-password/page.tsx
  - frontend/src/app/(auth)/reset-password/page.tsx
  - frontend/src/app/(protected)/layout.tsx
  - frontend/src/app/(protected)/dashboard/page.tsx
  - frontend/src/app/(auth)/__tests__/auth-pages.test.tsx
  - frontend/src/app/(protected)/__tests__/protected-pages.test.tsx
  - specs/002-auth-identity/tasks.md
tests:
  - frontend/src/app/(auth)/__tests__/auth-pages.test.tsx (8 tests)
  - frontend/src/app/(protected)/__tests__/protected-pages.test.tsx (6 tests)
  - Full suite: 43 passed
---

## Prompt

EPIC 2 – AUTHENTICATION IMPLEMENTATION PHASE 12. Implement ONLY Phase 12 (T094–T099). Phase 12 boundary strictly enforced — do NOT implement Phase 13+.

## Response snapshot

Implemented all 6 Phase 12 tasks:

**Root layout modified** — Removed `AppLayout` from `app/layout.tsx` (kept only HTML shell + fonts + metadata). Route groups now own their own layout tier.

**T094** — Created `app/(auth)/layout.tsx`: `'use client'` layout with `QueryClientProvider` + `AuthProvider` + `min-h-screen flex items-center justify-center bg-gray-50` centered wrapper. Auth pages get no sidebar, no header.

**T095** — Created `app/(auth)/login/page.tsx`: renders `LoginForm`, includes `<Link href="/forgot-password">Forgot your password?</Link>`, and uses `useEffect` to redirect to `/dashboard` when `isAuthenticated && !isLoading`.

**T096** — Created `app/(auth)/forgot-password/page.tsx`: renders `ForgotPasswordForm` with `<Link href="/login">Back to Sign In</Link>`.

**T097** — Created `app/(auth)/reset-password/page.tsx`: wraps `ResetPasswordForm` in `<Suspense>` (required by Next.js App Router because `ResetPasswordForm` uses `useSearchParams` internally).

**T098** — Created `app/(protected)/layout.tsx`: `ProtectedContent` inner component calls `useAuthContext()` after `AuthProvider` mounts; shows full-screen spinner while `isLoading`; calls `router.replace('/login')` when `!isAuthenticated`; renders `AppLayout` wrapping `{children}` when `isAuthenticated`.

**T099** — Created `app/(protected)/dashboard/page.tsx`: uses TanStack Query `useQuery({ queryKey: ['me'], queryFn: getMeApi })` to fetch the current user profile; displays `display_name`, `email`, and `account_status`; shows spinner while loading and error state on failure.

## Outcome

- ✅ Impact: Route protection fully wired — auth pages have centered card layout, protected pages have route guard + AppLayout; dashboard confirms /me endpoint is reachable
- 🧪 Tests: 43/43 frontend tests pass (14 new + 29 existing, 0 regressions)
- 📁 Files: 9 files created/modified; tasks.md updated (T094–T099 marked [x])
- 🔁 Next prompts: Phase 13 (comprehensive test suite covering all layers)
- 🧠 Reflection: `ProtectedContent` inner component pattern avoids calling `useAuthContext()` before `AuthProvider` mounts; `<Suspense>` required for `useSearchParams` in App Router — ResetPasswordForm already handles the token internally so page only needs the boundary

## Evaluation notes (flywheel)

- Failure modes observed: none — all 43 tests passed first run
- Graders run and results (PASS/FAIL): jest full suite PASS (43/43)
- Prompt variant (if applicable): /sp.implement with strict phase boundary
- Next experiment (smallest change to try): Phase 13 testing — verify backend and frontend integration tests can share fixtures without circular dependencies
