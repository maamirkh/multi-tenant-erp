---
id: "0015"
title: Epic 4 Phase 10 US8 View Role Details Permissions
stage: green
date: 2026-07-18
surface: agent
model: claude-sonnet-4-6
feature: 004-users-roles
branch: 004-users-roles
user: shehla83
command: /sp.implement
labels: ["epic4","phase10","US8","role-detail","permissions","member-count","fr-074"]
links:
  spec: specs/004-users-roles/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/users_roles/schemas/role.py
  - backend/modules/users_roles/services/role_service.py
  - backend/modules/users_roles/roles_router.py
  - backend/tests/integration/api/v1/users_roles/test_permission_listing.py
  - backend/tests/integration/api/v1/users_roles/test_role_crud.py
  - specs/004-users-roles/tasks.md
tests:
  - backend/tests/integration/api/v1/users_roles/test_permission_listing.py (11 tests, all passing — T086)
  - backend/tests/integration/api/v1/users_roles/test_role_crud.py (11 tests, all passing — regression)
  - backend/tests/unit/ regression (467 passing)
---

## Prompt

```text
# DevSphere ERP
# Epic 4 – Phase 10 Implementation
# Phase Name: US8 — View Role Details and Permissions (Priority: P3)

Implement ONLY Phase 10 ("US8 — View Role Details and Permissions (Priority: P3)") from the approved Epic 4 tasks.md.
```

## Response snapshot

Implemented Phase 10 (US8 — View Role Details and Permissions) in full:

**T085** — Added `get_role_with_permissions` to `RoleService`:
- Calls `get_role(role_id, company_id)` → raises RoleNotFoundError if missing
- Calls `role_permission_repo.get_permission_codes_for_role(role_id)` → set of codes
- Calls `permission_repo.get_by_codes(codes)` → full Permission objects
- Calls `member_repo.count_by_role(company_id, role_id)` → member count
- Returns `(role, permissions_sorted_by_module_code, member_count)`

**T084** — Updated `GET /roles/{role_id}` in `roles_router.py`:
- Changed from `get_role` + `get_permission_codes_for_role` to `get_role_with_permissions`
- Updated `_build_role_detail` to accept `permissions: list[Permission]` and `member_count: int`
- Also updated `create_role` and `update_role` endpoints to use `get_role_with_permissions`
- Added `PermissionResponse` to imports

**Schema changes** (`schemas/role.py`):
- Added `PermissionResponse(id, code, label, module, action, description)`
- Updated `RoleDetailResponse`: replaced `permission_codes: list[str]` with `permissions: list[PermissionResponse]`, added `member_count: int = 0`

**T086** — Created `test_permission_listing.py` with 11 integration tests:
- 200 for valid role, required fields, system role detection
- Permissions are full objects (not strings), have module field, sorted by module+code
- member_count accurate (1 for owner role, 0 for unassigned)
- 404 for unknown role, 401 without auth
- Custom role with specific permissions

**Regression fix**: Updated `test_role_crud.py` line 106 assertion from:
`assert "members.read" in data["permission_codes"]`
to:
`assert any(p["code"] == "members.read" for p in data["permissions"])`

## Outcome

- ✅ Impact: Role detail endpoint now returns full PermissionResponse objects with module/label/action and member_count; matches contracts/roles-api.yaml exactly; backend API for Users & Roles is feature-complete through Phase 10
- 🧪 Tests: 11 integration tests (T086, all passing), role_crud 11/11 regression PASS, unit 467/467 PASS
- 📁 Files: 5 files modified; 1 created; 1 tasks.md updated
- 🔁 Next prompts: Phase 11 (Frontend — Member Management)
- 🧠 Reflection: `permission_codes: list[str]` → `permissions: list[PermissionResponse]` is a breaking schema change — always update existing tests that assert on the old format. Using `get_by_codes` after `get_permission_codes_for_role` is a clean 2-query approach (no N+1), more maintainable than a raw JOIN.

## Evaluation notes (flywheel)

- Failure modes observed: None — clean first-run pass on all 11 new tests, 11 role_crud regression pass
- Graders run and results (PASS/FAIL): integration 11/11 PASS (T086), role_crud 11/11 PASS (regression), unit 467/467 PASS
- Prompt variant (if applicable): sp.implement Phase 10
- Next experiment: Phase 11 (Frontend)
