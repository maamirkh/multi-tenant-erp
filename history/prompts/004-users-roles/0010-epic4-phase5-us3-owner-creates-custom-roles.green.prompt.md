---
id: "0010"
title: Epic4 Phase5 US3 Owner Creates Custom Roles
stage: green
date: 2026-07-18
surface: agent
model: claude-sonnet-4-6
feature: 004-users-roles
branch: 004-users-roles
user: shehla83
command: /sp.implement
labels: ["phase5","us3","custom-roles","permissions","role-service","green"]
links:
  spec: specs/004-users-roles/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/users_roles/services/role_service.py
  - backend/modules/users_roles/services/permission_service.py
  - backend/modules/users_roles/schemas/permission.py
  - backend/modules/users_roles/roles_router.py
  - backend/modules/users_roles/permissions_router.py
  - backend/api/v1/router.py
  - backend/modules/users_roles/dependencies.py
  - backend/modules/users_roles/schemas/__init__.py
  - backend/modules/users_roles/services/__init__.py
  - backend/modules/users_roles/schemas/role.py
  - backend/tests/unit/modules/users_roles/test_role_service.py
  - backend/tests/integration/api/v1/users_roles/test_role_crud.py
  - specs/004-users-roles/tasks.md
tests:
  - backend/tests/unit/modules/users_roles/test_role_service.py (19 tests)
  - backend/tests/integration/api/v1/users_roles/test_role_crud.py (11 tests)
---

## Prompt

/sp.implement Phase 5 (US3 — Owner Creates Custom Roles)

Implement all tasks T048-T056 from specs/004-users-roles/tasks.md for US3 — Owner Creates Custom Roles.

Requirements include:
- T048: RoleService with create_custom_role (FR-042 rank 1-99, BR-031 name unique, FR-048 max 50, rank != system ranks), update_custom_role (FR-041 immutable system roles), deactivate_role (FR-047), delete_role (FR-046 zero active assignments), list_roles with member counts
- T049: PermissionService with list_all_permissions grouped by module
- T050: PermissionResponse and PermissionGroupResponse Pydantic schemas
- T051: POST /companies/{company_id}/roles — create custom role, 201
- T052: PATCH /companies/{company_id}/roles/{role_id} — update custom role, 403 for system roles
- T053: DELETE /companies/{company_id}/roles/{role_id} — 204 success, 409 active assignments
- T054: GET /permissions — grouped by module, global endpoint
- T055: Unit tests for RoleService (19 tests across 7 test classes)
- T056: Integration tests for role CRUD (11 tests across 5 test classes)

Run full regression (unit + repo + API integration), mark T048-T056 complete, create Phase Completion Report.

## Response snapshot

Implemented all 9 tasks for Phase 5 (US3 — Owner Creates Custom Roles):

**T048 — RoleService** (`backend/modules/users_roles/services/role_service.py`):
- `SYSTEM_ROLE_RANKS` frozenset derived from SYSTEM_ROLES constants
- `create_custom_role()`: 9-step flow — rank range validation, system rank conflict check, name uniqueness (case-insensitive), count limit, permission code validation, Role create, bulk_set permissions, audit log, domain event
- `update_custom_role()`: sentinel `...` pattern for description to distinguish "not provided" vs explicit None; validates not system role (FR-041)
- `deactivate_role()`: soft disable, enforces system role immutability
- `delete_role()`: validates zero active assignments (FR-046), soft-deletes, removes permission mappings
- `list_roles()` with member counts, `get_role()`, `get_permission_codes_for_role()`
- Fixed LogRecord name conflict: `extra={"role_name": name}` instead of `extra={"name": name}`

**T049 — PermissionService** (`backend/modules/users_roles/services/permission_service.py`):
- Read-only wrapper around PermissionRepository
- `list_all_permissions()` grouped by module using defaultdict

**T050 — Permission schemas** (`backend/modules/users_roles/schemas/permission.py`):
- `PermissionResponse`: code, label, module, action, description
- `PermissionGroupResponse`: module + list[PermissionResponse]

**T051-T054 — Routers**:
- `roles_router.py`: mounted at `/api/v1/companies/{company_id}/roles`
  - POST (create, 201), PATCH (update, 200), DELETE (204), GET "" (list), GET /{role_id} (detail)
- `permissions_router.py`: mounted at `/api/v1/permissions` (global)
  - GET "" returns permissions grouped by module
- Both registered in `backend/api/v1/router.py`

**T055 — Unit tests** (19 tests, 7 classes):
- TestCreateCustomRole (4), TestCreateRoleNameConflict (1), TestCreateRoleRankValidation (4), TestCreateRoleLimits (1), TestUpdateCustomRole (3), TestDeactivateRole (2), TestDeleteRole (4)

**T056 — Integration tests** (11 tests, 5 classes):
- TestCreateRoleEndpoint (3), TestUpdateRoleEndpoint (2), TestDeleteRoleEndpoint (3), TestListRolesEndpoint (1), TestPermissionsEndpoint (2)

**Proactive fix**: Removed `strict=True` from `CreateRoleRequest` and `UpdateRoleRequest` ConfigDict to prevent UUID string coercion issues (lesson from Phase 4).

## Outcome

- ✅ Impact: US3 fully implemented — Owner can create/update/deactivate/delete custom roles with permission assignment; custom role constraints enforced (name uniqueness, rank rules, count limit, active assignment guard)
- 🧪 Tests: 560 total passing — 426 unit+repo (pre-existing + 19 new role service tests) + 134 API integration (pre-existing 123 + 11 new role CRUD tests); zero regressions
- 📁 Files: 12 files created/modified — 2 new services, 1 new schema file, 2 new routers, 4 modified (router.py, dependencies.py, schemas/__init__.py, services/__init__.py, role.py), 2 new test files, 1 tasks.md updated
- 🔁 Next prompts: /sp.implement Phase 6 (US4 — User Updates Profile: T057-T065)
- 🧠 Reflection: Sentinel pattern (`...`) for optional description field is clean; LogRecord reserved attribute collision is a subtle Python gotcha to watch for; removing strict=True from Pydantic schemas at route boundary is a recurring pattern worth standardizing

## Evaluation notes (flywheel)

- Failure modes observed: LogRecord 'name' attribute overwrite (KeyError on logger.info with extra={"name": ...}); Pydantic strict=True UUID coercion on JSON boundary
- Graders run and results (PASS/FAIL): unit tests PASS (19/19), integration tests PASS (11/11), full regression PASS (134/134 API, 426/426 unit+repo)
- Prompt variant (if applicable): /sp.implement phase-by-phase workflow
- Next experiment: Standardize Pydantic ConfigDict() (no strict=True) on all router-boundary schemas to prevent UUID coercion issues
