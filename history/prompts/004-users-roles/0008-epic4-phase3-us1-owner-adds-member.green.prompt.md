---
id: "0008"
title: "Epic 4 Phase 3 US1 Owner Adds Member"
stage: green
date: 2026-07-17
surface: agent
model: claude-opus-4-6
feature: 004-users-roles
branch: 004-users-roles
user: shehla83
command: /sp.implement
labels: ["epic4", "phase3", "us1", "members", "repositories", "services", "schemas"]
links:
  spec: specs/004-users-roles/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/users_roles/repositories/company_member_repository.py
  - backend/modules/users_roles/repositories/role_repository.py
  - backend/modules/users_roles/repositories/permission_repository.py
  - backend/modules/users_roles/repositories/role_permission_repository.py
  - backend/modules/users_roles/repositories/__init__.py
  - backend/modules/users_roles/services/role_seed_service.py
  - backend/modules/users_roles/services/member_service.py
  - backend/modules/users_roles/services/invitation_service.py
  - backend/modules/users_roles/services/__init__.py
  - backend/modules/users_roles/schemas/member.py
  - backend/modules/users_roles/schemas/invitation.py
  - backend/modules/users_roles/schemas/__init__.py
  - backend/modules/users_roles/dependencies.py
  - backend/modules/users_roles/router.py
  - backend/modules/users_roles/models/user_preference.py
  - backend/tests/fixtures/users_roles_fixtures.py
  - backend/tests/unit/modules/users_roles/test_member_service.py
  - backend/tests/unit/modules/users_roles/test_role_seed_service.py
  - backend/tests/integration/api/v1/users_roles/test_add_member.py
  - backend/tests/integration/repositories/users_roles/test_company_member_repository.py
  - backend/tests/conftest.py
  - specs/004-users-roles/tasks.md
tests:
  - "Unit: MemberService.add_member happy path (5 tests) — PASS"
  - "Unit: MemberService duplicate membership (2 tests) — PASS"
  - "Unit: MemberService limit exceeded (1 test) — PASS"
  - "Unit: MemberService archived reactivation (1 test) — PASS"
  - "Unit: MemberService rank enforcement (3 tests) — PASS"
  - "Unit: MemberService role not found (1 test) — PASS"
  - "Unit: RoleSeedService permissions (2 tests) — PASS"
  - "Unit: RoleSeedService roles (4 tests) — PASS"
  - "Unit: RoleSeedService permissions mapping (1 test) — PASS"
  - "Integration: CompanyMemberRepository CRUD (3 tests) — PASS"
  - "Integration: CompanyMemberRepository lookups (4 tests) — PASS"
  - "Integration: CompanyMemberRepository soft-delete (2 tests) — PASS"
  - "Integration: POST /members auth (1 test) — PASS"
  - "Integration: POST /members non-member 403 (1 test) — PASS"
  - "Regression: 395 unit+repo tests — PASS"
  - "Regression: 116 API integration tests — PASS"
---

## Prompt

/sp.implement Phase 3 (US1 — Owner Adds a New Member to the Company) for Epic 4 Users & Roles.

## Response snapshot

Phase 3 completed successfully. All 19 tasks (T021-T039) implemented:

- **T021**: CompanyMemberRepository — extends BaseRepository, company-scoped CRUD, status/role/department filters, archived member lookup, count helpers
- **T022**: RoleRepository — extends BaseRepository, slug/name lookups, system role listing, custom role counting
- **T023**: PermissionRepository — global scope (no company_id), read-only, code/module lookups, bulk code fetch
- **T024**: RolePermissionRepository — CRUD for join table, bulk_set_permissions_for_role, permission code listing
- **T025**: repositories __init__.py exports all 4 repository classes
- **T026**: RoleSeedService — idempotent seeding of 14 permissions, 8 system roles, role-permission matrix; seed_all() method
- **T027**: MemberService — add_member with 8-step flow: limit check, duplicate check, archived reactivation, role validation, rank enforcement, record creation, audit log, domain event
- **T028**: InvitationService — accept_invitation (pending→active), expiry checking, reinvite for expired invitations
- **T029**: services __init__.py exports all 3 service classes
- **T030**: Member Pydantic schemas — AddMemberRequest, MemberResponse, MemberListItem, MemberDetailResponse, RoleSummary
- **T031**: Invitation Pydantic schemas — InvitationResponse
- **T032**: schemas __init__.py exports all schema classes
- **T033**: DI factories — get_member_service, get_invitation_service, get_role_seed_service, get_current_company_member, get_actor_role_rank
- **T034**: POST /members endpoint — auth + membership guard, email→user lookup, delegates to MemberService, returns 201 StandardResponse
- **T035**: Test fixtures — seed_system_roles, create_test_member/role/permission, create_member_with_role
- **T036-T039**: 31 tests total (20 unit + 9 repo integration + 2 API integration)

## Outcome

- Impact: Complete add-member flow from API to database; enables all collaborative features (US2-US8) that depend on members existing
- Tests: 511 passed (395 unit+repo + 116 API), 0 regressions
- Files: 17 created, 4 modified (dependencies.py, router.py, user_preference.py, conftest.py, tasks.md)
- Next prompts: /sp.implement Phase 4 (US2 — Admin Manages User Roles)
- Reflection: Router endpoint path must be "" not "/members" because parent mount already includes /members. UserPreference JSONB server_default needed ::jsonb cast removed for SQLite test compatibility.

## Evaluation notes (flywheel)

- Failure modes observed: (1) Router path doubling — POST /members/members due to mount prefix + endpoint path; fixed by using "" as endpoint path. (2) SQLite incompatibility with PostgreSQL ::jsonb cast in UserPreference server_default; fixed by removing cast.
- Graders run and results (PASS/FAIL): Unit tests PASS (20/20), Repo integration PASS (9/9), API integration PASS (2/2), Full regression PASS (511/511)
- Prompt variant (if applicable): /sp.implement with explicit phase targeting
- Next experiment (smallest change to try): None needed; proceed to Phase 4
