---
id: "0020"
title: Phase 16 Security Review
stage: green
date: 2026-07-16
surface: agent
model: claude-sonnet-4-6
feature: 003-companies
branch: 003-companies
user: shehla83
command: /sp.implement
labels: ["phase-16","security","backend","python","pytest","companies","rate-limiting","tenant-isolation","permissions","masking","logo"]
links:
  spec: specs/003-companies/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/companies/router.py
  - backend/tests/security/companies/test_tenant_isolation.py
  - backend/tests/security/companies/test_company_permissions.py
  - backend/tests/security/companies/test_sensitive_field_masking.py
  - backend/tests/security/companies/test_logo_upload_security.py
  - backend/tests/security/companies/test_rate_limiting.py
  - specs/003-companies/tasks.md
tests:
  - backend/tests/security/companies/test_tenant_isolation.py (6 tests — all pass)
  - backend/tests/security/companies/test_company_permissions.py (11 tests — all pass)
  - backend/tests/security/companies/test_sensitive_field_masking.py (9 tests — all pass)
  - backend/tests/security/companies/test_logo_upload_security.py (8 tests — all pass)
  - backend/tests/security/companies/test_rate_limiting.py (2 tests — all pass)
  - Full backend suite: 597/598 pass (1 pre-existing failure: test_settings_default_debug_is_false)
---

## Prompt

/sp.implement — Epic 3 Companies, Phase 16: Security Review (T111–T116)

## Response snapshot

**T115 (prerequisite)** — Added `@limiter.limit("10/minute")` to `POST /companies` in `backend/modules/companies/router.py`:
- Imported `limiter` from `modules.auth.router` (singleton shared across all routers)
- Placed decorator between `@router.post(...)` and `async def create_company(...)` (SlowAPI convention)

**T111** — Created `backend/tests/security/companies/test_tenant_isolation.py`:
- 6 tests: cross-tenant GET, PATCH, DELETE, audit-log GET, address POST all return 403
- Key assertion: cross-tenant access returns 403 (not 404) — existence must not leak to outsiders
- Fixture seeds two users each owning a distinct company; user B attempts to access company A

**T112** — Created `backend/tests/security/companies/test_company_permissions.py`:
- 11 tests: owner (GET/PATCH/audit-log), non-owner (GET/PATCH/audit-log/address → 403), unauthenticated (create/admin-list/get → 401), super_admin via dependency override (admin list → 200)
- SuperAdmin test injects via `app.dependency_overrides[require_authenticated]` with MagicMock having `roles=["super_admin"]`
- Phase 3 RBAC simplification noted: Epic 4 roles (admin, manager, accountant, sales, inventory) deferred to company_members table

**T113** — Created `backend/tests/security/companies/test_sensitive_field_masking.py`:
- 9 tests: schema unit tests for roles (owner/accountant/super_admin → unmasked; viewer/manager/sales → "****") + HTTP tests (owner sees real tax_number; super_admin via override sees real tax_number)
- Schema `CompanyDetailResponse.for_role()` tested directly without HTTP layer
- Bug fixed: `CompanyDetailResponse` requires `owner_id` field — added to schema constructor calls

**T114** — Created `backend/tests/security/companies/test_logo_upload_security.py`:
- 8 tests: SVG+script → 400, SVG+onclick → 400, corrupted bytes → 400, PDF-as-.jpg → 400, missing field → 422, PNG-as-.exe → 200, valid PNG → 200, path traversal filename → UUID-based key (no traversal)
- Tests needing successful upload (`png-as-exe`, `valid-png`, `path-traversal`) override `get_company_logo_service` with `_FakeStorage` to bypass `_NullStorageClient.NotImplementedError`
- `_CapturingStorage` captures uploaded key in path traversal test to assert UUID format

**T115** — Created `backend/tests/security/companies/test_rate_limiting.py`:
- 2 tests: 11th POST /companies returns 429; 429 body has `error` field
- `_reset_rate_limiter` autouse fixture in conftest.py resets counter before each test

**T116** — PostgreSQL audit log DB permissions: already documented in `specs/003-companies/quickstart.md §11`. The section documents the SQL verification command and expected permission denial error. This is a manual verification step for the real PostgreSQL container (not pytest-testable in SQLite in-memory test DB).

**Bugs fixed during implementation:**
- `GET /audit-log` → 404: correct URL is `audit-logs` (plural). Fixed in both test_company_permissions.py and test_tenant_isolation.py.
- `CompanyDetailResponse` requires `owner_id`: added to schema constructor in `_make_response()` helper.
- SVG body error code nested under `error.code`: changed `body.get("code")` to `body.get("error", {}).get("code") or body.get("code")`.

## Outcome

- ✅ Impact: Phase 16 complete — all 6 security review tasks done; rate limiting added to POST /companies; 5 new security test files with 36 new tests all pass
- 🧪 Tests: 36 new security tests pass (43 total in security/companies/ including Phase 13's 7); Full backend: 597/598 pass (1 pre-existing env issue)
- 📁 Files: 5 files created, 2 files modified (router.py, tasks.md)
- 🔁 Next prompts: Phase 17 (Epic Finalization)
- 🧠 Reflection: Audit-log endpoint URL is `/audit-logs` (plural) — verify URL spelling before asserting status codes. `CompanyDetailResponse` requires `owner_id` — check all required fields when constructing schema instances in tests. Error response body wraps the code under `error.code`, not at top level — always inspect actual response structure before writing assertions. SVG with `<script>` is correctly caught by `_SVG_DANGEROUS_PATTERNS` and raises `LogoInvalidContentError` (not `LogoInvalidFormatError`). `_NullStorageClient.upload()` raises `NotImplementedError` — logo tests that need a successful upload path must override `get_company_logo_service` with a fake storage.

## Evaluation notes (flywheel)

- Failure modes observed: Wrong audit-log URL (audit-log vs audit-logs); missing required `owner_id` in schema constructor; error code nested under `error` wrapper; SVG body assertion checking wrong key
- Graders run and results (PASS/FAIL): pytest 597/598 PASS (1 pre-existing), security tests 36/36 PASS
- Prompt variant (if applicable): null
- Next experiment: null
