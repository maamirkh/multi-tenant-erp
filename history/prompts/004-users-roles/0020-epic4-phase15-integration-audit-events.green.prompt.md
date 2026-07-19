---
id: 0020
title: "Epic4 Phase 15 Integration Audit Events"
stage: green
date: 2026-07-19
surface: agent
model: claude-sonnet-4-6
feature: 004-users-roles
branch: 004-users-roles
user: shehla83
command: /sp.implement
labels: ["ownership", "audit", "events", "integration", "phase15"]
links:
  spec: specs/004-users-roles/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/users_roles/services/ownership_service.py
  - backend/modules/users_roles/schemas/ownership.py
  - backend/modules/users_roles/ownership_router.py
  - backend/modules/users_roles/services/member_service.py
  - backend/modules/users_roles/router.py
  - backend/modules/users_roles/dependencies.py
  - backend/modules/users_roles/schemas/member.py
  - backend/modules/companies/router.py
  - backend/api/v1/router.py
  - backend/tests/unit/modules/users_roles/test_ownership_service.py
  - backend/tests/integration/api/v1/users_roles/test_ownership_transfer.py
  - backend/tests/integration/api/v1/users_roles/test_audit_events.py
  - backend/tests/integration/api/v1/users_roles/test_domain_events.py
  - backend/tests/fixtures/users_roles_fixtures.py
  - backend/tests/integration/api/v1/companies/test_audit_log.py
tests:
  - tests/unit/modules/users_roles/test_ownership_service.py (8 tests)
  - tests/integration/api/v1/users_roles/test_ownership_transfer.py (6 tests)
  - tests/integration/api/v1/users_roles/test_audit_events.py (12 tests)
  - tests/integration/api/v1/users_roles/test_domain_events.py (11 tests)
---

## Prompt

/sp.implement Phase 15 (Integration — Company Integration, Audit & Events) from Epic 4 tasks.md. Tasks T126–T133: OwnershipService, ownership schemas, transfer-ownership endpoint, RoleSeedService hook into company creation, audit event verification tests, domain event outbox tests, ownership unit tests, ownership integration tests.

## Response snapshot

Implemented Phase 15 (T126–T133) — backend-only integration tasks:

- **T126**: Created `OwnershipService` with atomic ownership transfer (validate actor is Owner, validate target is active member, swap roles Owner↔Admin, update `company.owner_id`, write audit log OWNERSHIP_TRANSFERRED, publish OwnershipTransferredEvent)
- **T127**: Created `TransferOwnershipRequest` schema in `schemas/ownership.py`
- **T128**: Created `ownership_router.py` with `POST /companies/{company_id}/transfer-ownership` (Owner-only via `require_rank(OWNER_RANK)`)
- **T129**: Hooked `RoleSeedService.seed_all()` + `MemberService.create_bootstrap_owner()` into `companies/router.py` create_company handler; added `accept-invitation` endpoint to members router
- **T130**: 12 integration tests verifying audit log entries for lifecycle events (MEMBER_CREATED, ROLE_CHANGED, DEACTIVATED, SUSPENDED, LOCKED, ARCHIVED, RESTORED, ROLE_CREATED/UPDATED/DELETED, INVITATION_ACCEPTED, OWNERSHIP_TRANSFERRED)
- **T131**: 11 domain event outbox verification tests using raw SQL for SQLite compatibility
- **T132**: 8 unit tests for OwnershipService with mocked dependencies
- **T133**: 6 integration tests for ownership transfer API flow

Key fixes during implementation:
- Removed `ConfigDict(strict=True)` from `AddMemberRequest` (prevented JSON string→UUID coercion)
- Made `create_test_member` fixture idempotent (handles bootstrap owner duplication)
- Fixed test references from non-existent `staff` slug to `manager`
- Added missing `accept-invitation` endpoint to members router
- Used raw SQL for outbox queries (SQLite test DB doesn't support JSONB operators)

## Outcome

- ✅ Impact: All 38 Phase 15 tests passing (8 unit + 30 integration)
- 🧪 Tests: 38 new tests added across 4 test files
- 📁 Files: 15 files created/modified
- 🔁 Next prompts: Phase 16 (Security & Performance), commit changes, create PR
- 🧠 Reflection: strict=True on Pydantic models breaks standard JSON API UUID coercion in FastAPI; always test API endpoints with HTTP clients, not just fixtures

## Evaluation notes (flywheel)

- Failure modes observed: strict Pydantic mode incompatible with FastAPI JSON parsing; missing router endpoints discovered only via integration tests; non-existent role slugs in tests
- Graders run and results (PASS/FAIL): pytest 38 PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
