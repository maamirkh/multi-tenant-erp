---
id: "0011"
title: Epic4 Phase6 US4 User Updates Profile
stage: green
date: 2026-07-18
surface: agent
model: claude-sonnet-4-6
feature: 004-users-roles
branch: 004-users-roles
user: shehla83
command: /sp.implement
labels: ["phase6","us4","profile","preferences","avatar","green"]
links:
  spec: specs/004-users-roles/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/auth/models/user.py
  - backend/modules/users_roles/repositories/user_preference_repository.py
  - backend/modules/users_roles/services/profile_service.py
  - backend/modules/users_roles/services/preference_service.py
  - backend/modules/users_roles/schemas/profile.py
  - backend/modules/users_roles/schemas/preference.py
  - backend/modules/users_roles/profile_router.py
  - backend/modules/users_roles/preferences_router.py
  - backend/modules/users_roles/dependencies.py
  - backend/api/v1/router.py
  - backend/modules/users_roles/schemas/__init__.py
  - backend/modules/users_roles/services/__init__.py
  - backend/modules/users_roles/repositories/__init__.py
  - backend/tests/unit/modules/users_roles/test_profile_service.py
  - backend/tests/unit/modules/users_roles/test_preference_service.py
  - backend/tests/integration/api/v1/users_roles/test_profile.py
  - backend/tests/integration/api/v1/users_roles/test_preferences.py
  - specs/004-users-roles/tasks.md
tests:
  - backend/tests/unit/modules/users_roles/test_profile_service.py (20 tests)
  - backend/tests/unit/modules/users_roles/test_preference_service.py (14 tests)
  - backend/tests/integration/api/v1/users_roles/test_profile.py (6 tests)
  - backend/tests/integration/api/v1/users_roles/test_preferences.py (9 tests)
---

## Prompt

/sp.implement Phase 6 (US4 — User Updates Their Profile)

Implement ONLY Phase 6 tasks T057-T067 from the approved Epic 4 tasks.md.

Requirements include:
- T057: UserPreferenceRepository (user-scoped, not company-scoped) — get_by_user_id, create_or_update, create_with_defaults
- T058: ProfileService — get_profile, update_profile (display_name, phone), upload_avatar (JPEG/PNG/WebP, magic-byte validation, S3 upload, retention), delete_avatar (retain file for AVATAR_RETENTION_DAYS)
- T059: PreferenceService — get_preferences (creates defaults), update_preferences (validates language, timezone via zoneinfo, date_format enum, theme enum)
- T060: Profile schemas — UpdateProfileRequest, ProfileResponse, AvatarUploadResponse
- T061: Preference schemas — UpdatePreferenceRequest, PreferenceResponse
- T062: DI factories — get_profile_service(), get_preference_service() in dependencies.py
- T063: profile_router.py — GET/PATCH /profile, POST/DELETE /profile/avatar
- T064: preferences_router.py — GET/PUT /preferences
- T065: Unit tests for ProfileService (20 tests)
- T066: Unit tests for PreferenceService (14 tests)
- T067: Integration tests for profile + preferences (15 tests)

## Response snapshot

Implemented all 11 tasks for Phase 6 (US4 — User Updates Their Profile):

**User model update** (`backend/modules/auth/models/user.py`):
- Added `phone`, `avatar_url`, `avatar_previous_url` mapped columns (already in migration 004_users_roles.py)

**T057 — UserPreferenceRepository**:
- Plain repository (not extending BaseRepository — UserPreference has no company_id)
- `get_by_user_id()`, `create_with_defaults()` (with sensible defaults dict), `create_or_update()` (upsert pattern)

**T058 — ProfileService**:
- `_detect_avatar_mime()`: magic-byte MIME detection for JPEG/PNG/WebP (GIF/SVG rejected)
- `get_profile()`, `update_profile()` with sentinel `...` for phone, `upload_avatar()` (size→MIME validation→S3 key as `avatars/{user_id}/{uuid}.ext`→previous URL retention), `delete_avatar()` (S3 file NOT deleted; retained for AVATAR_RETENTION_DAYS)

**T059 — PreferenceService**:
- `get_preferences()` auto-creates defaults if no record exists
- `update_preferences()` validates: language (2-10 chars), timezone (via `zoneinfo.ZoneInfo`), date_format (4 allowed patterns), theme (light/dark/system)
- `InvalidPreferenceValueError` with `http_status=400`

**T060 — profile.py schemas**: `UpdateProfileRequest`, `ProfileResponse`, `AvatarUploadResponse`
**T061 — preference.py schemas**: `UpdatePreferenceRequest` (Literal types for date_format and theme), `PreferenceResponse`

**T062 — DI factories**: `get_profile_service()` (with `_NullStorageClient` stub), `get_preference_service()` in dependencies.py

**T063 — profile_router.py**: Mounted at `/api/v1/profile`; GET/PATCH/POST avatar/DELETE avatar; async upload_avatar reads UploadFile bytes
**T064 — preferences_router.py**: Mounted at `/api/v1/preferences`; GET/PUT

**T065/T066 — Unit tests**: 34 total — 20 profile service + 14 preference service
**T067 — Integration tests**: 15 total — 6 profile + 9 preferences

**api/v1/router.py**: Added profile_router at `/profile` and preferences_router at `/preferences`

## Outcome

- ✅ Impact: US4 fully implemented — users can GET/update their profile (display_name, phone), upload/delete avatar with S3 retention, GET/update preferences with full validation
- 🧪 Tests: 609 total passing — 460 unit+repo (426 previous + 34 new) + 149 API integration (134 previous + 15 new); zero regressions
- 📁 Files: 18 files created/modified — 1 User model update, 1 new repo, 2 new services, 2 new schemas, 2 new routers, 5 updated __init__/dependencies/router files, 4 new test files, 1 tasks.md updated
- 🔁 Next prompts: /sp.implement Phase 7 (US5 — Admin Manages User Lifecycle: T068-T077)
- 🧠 Reflection: UserPreference must be a plain repository (not BaseRepository) since it has no company_id — lesson: not all models are tenant-scoped; zoneinfo standard library is sufficient for IANA timezone validation without external deps; Literal types in Pydantic catch enum violations at schema level (422) before service validation

## Evaluation notes (flywheel)

- Failure modes observed: InvalidPreferenceValueError initially defaulted to http_status=500 (UsersRolesException default) — needed explicit http_status=400; User model lacked phone/avatar_url/avatar_previous_url mapped columns despite migration having them
- Graders run and results (PASS/FAIL): unit tests PASS (34/34), integration tests PASS (15/15), full regression PASS (149/149 API, 460/460 unit+repo)
- Prompt variant (if applicable): /sp.implement phase-by-phase workflow
- Next experiment: Consider extracting magic-byte MIME detection to a shared core utility to avoid duplication between CompanyLogoService and ProfileService
