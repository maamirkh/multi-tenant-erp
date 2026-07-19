---
id: "0018"
title: Epic 4 Phase 13 Frontend Profile Preferences
stage: green
date: 2026-07-19
surface: agent
model: claude-sonnet-4-6
feature: 004-users-roles
branch: 004-users-roles
user: shehla83
command: /sp.implement
labels: ["phase-13","profile","preferences","avatar-upload","theme","react-query","react-hook-form","zod","next.js"]
links:
  spec: specs/004-users-roles/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/lib/api/client.ts (fixed: 204 No Content handling in request())
  - frontend/src/types/users-roles.ts (extended: UserProfile, AvatarUploadResult, UpdateProfileInput, UserPreferences, UpdatePreferencesInput, ThemePreference, DateFormatOption)
  - frontend/src/schemas/users-roles.ts (extended: UpdateProfileSchema, UpdatePreferencesSchema, DATE_FORMATS, THEMES)
  - frontend/src/lib/api/users-roles.ts (extended: getProfile, updateProfile, uploadAvatar, deleteAvatar, getPreferences, updatePreferences)
  - frontend/src/hooks/users-roles/useProfile.ts (created)
  - frontend/src/hooks/users-roles/usePreferences.ts (created)
  - frontend/src/components/users-roles/AvatarUpload.tsx (created)
  - frontend/src/components/users-roles/ProfileForm.tsx (created)
  - frontend/src/components/users-roles/PreferencesForm.tsx (created)
  - frontend/src/app/(protected)/profile/page.tsx (created)
  - frontend/src/app/(protected)/preferences/page.tsx (created)
  - specs/004-users-roles/tasks.md (T114-T121 marked [X])
tests:
  - tsc --noEmit (exit 0, no type errors)
---

## Prompt

Frontend — Profile & Preferences (US4)

[/sp.implement invocation for Phase 13]

## Response snapshot

Implemented all 8 tasks (T114–T121) for Phase 13 — Frontend Profile & Preferences:

**Bug fix first**: Fixed `ApiClient.request()` to handle 204 No Content responses by returning `{}` before calling `.json()`. This was silently broken for both `deleteRole` and the new `deleteAvatar`.

**Types + Schemas + API (T114)**:
- Added `UserProfile`, `AvatarUploadResult`, `UpdateProfileInput`, `UserPreferences`, `UpdatePreferencesInput`, `ThemePreference`, `DateFormatOption` to `types/users-roles.ts`
- Added `UpdateProfileSchema`, `UpdatePreferencesSchema`, `DATE_FORMATS`, `THEMES` to `schemas/users-roles.ts`
- Added `getProfile`, `updateProfile`, `uploadAvatar` (multipart), `deleteAvatar`, `getPreferences`, `updatePreferences` to `lib/api/users-roles.ts`

**Hooks (T115, T116)**:
- `useProfile` — query `['profile']` staleTime 60s; mutations: useUpdateProfile, useUploadAvatar, useDeleteAvatar
- `usePreferences` — query `['preferences']` staleTime 5min; mutation: useUpdatePreferences

**Components (T117–T119)**:
- `AvatarUpload` — file input validates JPEG/PNG/WebP + ≤2 MiB client-side; initials placeholder; upload overlay on hover; Remove button
- `ProfileForm` — display_name + phone fields + AvatarUpload; avatar mutations fire immediately; read-only email field
- `PreferencesForm` — language text input, timezone `<select>` (30 common TZs), date_format `<select>`, number_format `<select>`, theme radio-button group; `applyTheme()` sets `document.documentElement.dark` class + localStorage on change

**Pages (T120, T121)**:
- `MyProfilePage` — useProfile + ProfileForm; no rank guard (all authenticated users)
- `MyPreferencesPage` — usePreferences + PreferencesForm; applies stored theme from localStorage on mount; syncs from API on load

TypeScript: `tsc --noEmit` → exit 0.

## Outcome

- ✅ Impact: Full profile + preferences self-service UI complete for Epic 4 US4
- 🧪 Tests: `tsc --noEmit` PASS
- 📁 Files: 12 files created/modified (9 new, 3 extended)
- 🔁 Next prompts: Phase 14 (Ownership Transfer)
- 🧠 Reflection: 204 No Content bug in `ApiClient.request()` was latent from Phase 12 deleteRole. Always check response body assumptions for delete endpoints. Theme toggle without next-themes requires manual class + localStorage management.

## Evaluation notes (flywheel)

- Failure modes observed: None (tsc clean first pass)
- Graders run and results (PASS/FAIL): tsc --noEmit PASS
- Prompt variant (if applicable): /sp.implement for Phase 13
- Next experiment: Add a lightweight theme script tag to layout.tsx for FOUC prevention
