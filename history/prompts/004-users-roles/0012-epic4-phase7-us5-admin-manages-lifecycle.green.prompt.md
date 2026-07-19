---
id: "0012"
title: Epic 4 Phase 7 US5 Admin Manages Lifecycle
stage: green
date: 2026-07-18
surface: agent
model: claude-sonnet-4-6
feature: 004-users-roles
branch: 004-users-roles
user: shehla83
command: /sp.implement
labels: ["epic4","phase7","US5","lifecycle","state-machine","session-revocation"]
links:
  spec: specs/004-users-roles/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/users_roles/services/member_service.py
  - backend/modules/users_roles/repositories/company_member_repository.py
  - backend/modules/users_roles/schemas/member_status.py
  - backend/modules/users_roles/router.py
  - backend/modules/users_roles/dependencies.py
  - backend/tests/unit/modules/users_roles/test_member_service.py
  - backend/tests/integration/api/v1/users_roles/test_member_lifecycle.py
  - specs/004-users-roles/tasks.md
tests:
  - backend/tests/unit/modules/users_roles/test_member_service.py (85 tests, all passing)
  - backend/tests/integration/api/v1/users_roles/test_member_lifecycle.py (32 tests, all passing)
  - backend/tests/unit/ regression (455 passing)
  - backend/tests/integration/api/v1/users_roles/test_profile.py + test_preferences.py (15 passing)
---

## Prompt

```text
# DevSphere ERP
# Epic 4 – Phase 7 Implementation
# Phase Name: US5 — Admin Manages User Lifecycle (Priority: P2)

Implement ONLY Phase 7 ("US5 — Admin Manages User Lifecycle (Priority: P2)") from the approved Epic 4 tasks.md.
```

## Response snapshot

Implemented Phase 7 (US5 — Admin Manages User Lifecycle) in full:

**T068** — Added 6 lifecycle methods to `MemberService`:
- `deactivate_member` (active → inactive, revoke sessions, MEMBER_DEACTIVATED)
- `reactivate_member` (inactive/suspended/locked → active, context-sensitive audit: MEMBER_REACTIVATED / MEMBER_UNSUSPENDED / MEMBER_UNLOCKED)
- `suspend_member` (active/locked → suspended, requires reason, MEMBER_SUSPENDED)
- `lock_member` (active → locked, revoke sessions, MEMBER_LOCKED)
- `archive_member` (active/inactive/suspended/locked → archived, requires reason, sets is_deleted+deleted_at, MEMBER_ARCHIVED)
- `restore_member` (archived → active, clears deletion fields, MEMBER_RESTORED)

**T069** — State machine validation via `_validate_transition()` checking `_VALID_TRANSITIONS` dict (BR-020). Raises `InvalidStatusTransitionError` on invalid transitions.

**T070** — Session revocation via `_revoke_sessions()` calling `SessionRepository.revoke_all_by_user()`. Optional injection (backward-compatible); logs warning if not provided.

**T071** — `SuspendRequest` and `ArchiveRequest` Pydantic schemas with mandatory reason (min_length=1, max_length=500).

**T072** — 6 lifecycle endpoints under `/{member_id}/{action}`, all requiring `ADMIN_RANK` via `require_rank(ADMIN_RANK)` dependency.

**T073** — 85 unit tests (15 new lifecycle tests + 11 parametric transition matrix cases).

**T074** — 32 integration tests covering all 6 endpoints: auth guards, rank guards, valid transitions, invalid 409s, reason validation 422s.

Key design decisions:
- `session_repo` as optional kwarg (None default) preserves backward compatibility with existing tests
- `get_deleted_by_id` added to `CompanyMemberRepository` for `restore_member` soft-delete lookup
- `_VALID_TRANSITIONS` frozenset dict at module level (BR-020 state machine)
- `_OWNER_ACTIVE_STATUSES` used for last Owner protection count query
- `reactivate_member` uses `_ACTION_MAP` for context-sensitive audit action selection
- Integration tests use `create_test_member` directly (not API) for reliable status setup

## Outcome

- ✅ Impact: Complete member lifecycle state machine (BR-020) with admin controls, session revocation, audit logging, and domain events
- 🧪 Tests: 85 unit tests (all passing), 32 integration tests (all passing), 455 unit regression (all passing), 15 Phase 6 regression (all passing)
- 📁 Files: 7 files modified/created; 2 test files created
- 🔁 Next prompts: Phase 8 (US6 — Admin Views/Searches Members)
- 🧠 Reflection: The `.test` TLD in email addresses is reserved and rejected by email validator — use `.com` in all test fixtures. `inactive → active` IS a valid BR-020 transition, so `restore_member` on inactive member succeeds (not an error). Pre-existing test isolation flakiness in `test_add_member_non_member_returns_403` — passes when run individually.

## Evaluation notes (flywheel)

- Failure modes observed: (1) Email TLD `.test` rejected by validator — use `.com`; (2) Invalid unit test asserting `inactive → active` would fail via restore_member (wrong — it's a valid transition); (3) Long integration test runs (3-8 min per test class) due to sequential db setup
- Graders run and results (PASS/FAIL): unit 85/85 PASS, integration 32/32 PASS, regression unit 455/455 PASS
- Prompt variant (if applicable): sp.implement Phase 7
- Next experiment: Investigate test isolation issue in test_add_member_non_member_returns_403 (pre-existing, not caused by Phase 7)
