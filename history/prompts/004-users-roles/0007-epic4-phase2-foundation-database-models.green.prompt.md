---
id: "0007"
title: "Epic 4 Phase 2 Foundation Database Models"
stage: green
date: 2026-07-17
surface: agent
model: claude-opus-4-6
feature: 004-users-roles
branch: 004-users-roles
user: shehla83
command: /sp.implement
labels: ["epic4", "phase2", "foundation", "models", "migration", "database"]
links:
  spec: specs/004-users-roles/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/users_roles/models/enums.py
  - backend/modules/users_roles/models/company_member.py
  - backend/modules/users_roles/models/role.py
  - backend/modules/users_roles/models/permission.py
  - backend/modules/users_roles/models/role_permission.py
  - backend/modules/users_roles/models/user_preference.py
  - backend/modules/users_roles/models/__init__.py
  - backend/modules/users_roles/constants.py
  - backend/modules/users_roles/exceptions.py
  - backend/modules/users_roles/events.py
  - backend/modules/users_roles/validators.py
  - backend/migrations/versions/004_users_roles.py
  - backend/core/config/settings.py
  - specs/004-users-roles/tasks.md
tests:
  - "Import verification: all module imports successful"
  - "Migration upgrade: alembic upgrade head (001->004) succeeds"
  - "Migration downgrade: alembic downgrade -1 (004->003) succeeds"
  - "Migration re-upgrade: alembic upgrade head after downgrade succeeds"
  - "Table verification: 5 new tables with correct column counts"
  - "Index verification: all indexes from data-model.md created"
  - "User extension: 3 new columns (avatar_url, avatar_previous_url, phone)"
  - "Regression: 350 existing tests pass (1 pre-existing unrelated failure)"
---

## Prompt

/sp.implement Phase 2 (Foundation - Database, Models, Enums, Constants, Configuration, Exceptions & Events) for Epic 4 Users & Roles.

## Response snapshot

Phase 2 completed successfully. All 14 tasks (T007-T020) implemented:

- **T007**: MembershipStatus (6 values) and PermissionAction (6 values) enums
- **T008**: Constants with 8 system roles, 14 permissions, role-permission matrix, valid status transitions
- **T009**: 6 new settings in core/config/settings.py (COMPANY_MAX_MEMBERS, USER_AVATAR_MAX_BYTES, AVATAR_RETENTION_DAYS, MEMBER_DELETION_RETENTION_DAYS, MAX_CUSTOM_ROLES_PER_COMPANY, INVITATION_EXPIRY_DAYS)
- **T010-T014**: 5 SQLAlchemy models (CompanyMember 20 cols, Role 13 cols, Permission 7 cols, RolePermission 4 cols, UserPreference 10 cols)
- **T015**: models/__init__.py exports all models for Alembic discovery
- **T016**: Alembic migration 004 with full upgrade/downgrade, 5 tables + users extension, all indexes and constraints
- **T017**: 18 exception classes + UsersRolesException base, matching plan Section 18.1
- **T018**: 12 domain event dataclasses with to_outbox_record() methods
- **T019**: 8 validator functions for email, phone, employee_id, role name, rank, department, date format, theme
- **T020**: Migration verified (upgrade, downgrade, re-upgrade) with table/column/index verification

## Outcome

- Impact: Complete data layer foundation for all 8 user stories; every subsequent phase depends on these definitions
- Tests: 350 passed, 1 pre-existing failure (unrelated), 0 regressions; migration up/down/up verified
- Files: 12 created, 2 modified (settings.py, tasks.md)
- Next prompts: /sp.implement Phase 3 (US1 - Owner Adds New Member)
- Reflection: Permission model uses String PK (code) instead of UUID for simpler lookups. CompanyMember uses partial unique index for employee_id (not UniqueConstraint, which doesn't support postgresql_where in SQLAlchemy ORM).

## Evaluation notes (flywheel)

- Failure modes observed: UniqueConstraint doesn't accept postgresql_where in SQLAlchemy ORM; fixed by using partial unique Index instead
- Graders run and results (PASS/FAIL): Import PASS, Migration up PASS, Migration down PASS, Migration re-up PASS, Table verification PASS, Regression PASS
- Prompt variant (if applicable): /sp.implement with explicit phase targeting
- Next experiment (smallest change to try): None needed; proceed to Phase 3
