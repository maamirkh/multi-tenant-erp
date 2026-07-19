---
id: "0013"
title: Epic 4 Phase 8 US6 Admin Views Searches Members
stage: green
date: 2026-07-18
surface: agent
model: claude-sonnet-4-6
feature: 004-users-roles
branch: 004-users-roles
user: shehla83
command: /sp.implement
labels: ["epic4","phase8","US6","member-listing","pagination","search","filters"]
links:
  spec: specs/004-users-roles/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/users_roles/repositories/company_member_repository.py
  - backend/modules/users_roles/services/member_service.py
  - backend/modules/users_roles/router.py
  - backend/tests/integration/api/v1/users_roles/test_member_listing.py
  - specs/004-users-roles/tasks.md
tests:
  - backend/tests/integration/api/v1/users_roles/test_member_listing.py (25 tests, all passing)
  - backend/tests/unit/ regression (455 passing)
---

## Prompt

```text
# DevSphere ERP
# Epic 4 – Phase 8 Implementation
# Phase Name: US6 — Admin Views and Searches Company Members (Priority: P2)

Implement ONLY Phase 8 ("US6 — Admin Views and Searches Company Members (Priority: P2)") from the approved Epic 4 tasks.md.
```

## Response snapshot

Implemented Phase 8 (US6 — Admin Views and Searches Company Members) in full:

**T076** — Added `list_by_company_filtered` to `CompanyMemberRepository`:
- JOINs `User` and `Role` tables with `contains_eager()` for N+1-free eager loading
- Filters: `status`, `role_id`, `department` (exact), `search` (ilike on display_name/email/employee_id)
- Sort columns: `name` (User.display_name), `created_at`, `role_rank` (Role.rank), `department`
- Pagination: LIMIT/OFFSET, total count via subquery
- Returns `(items, total)` tuple

**T075** — Added `list_members` to `MemberService`:
- Thin delegation to `list_by_company_filtered` converting `page`/`page_size` to `skip`/`limit`

**T077** — Added `GET ""` endpoint to `router.py`:
- Query params: `status`, `role_id`, `department`, `search` (max_length=100), `page`, `page_size` (1–100), `sort_by` (Literal), `sort_order` (Literal)
- Returns `PaginatedResponse[MemberListItem]` using existing core pagination schema
- Helper `_build_member_list_item()` constructs response from eagerly loaded member

**T078** — Verified GET /roles with `member_count` already fully implemented in Phase 5's `roles_router.py`. No new code needed.

**T079** — Created 25 integration tests in `test_member_listing.py`:
- `TestListMembersAuth` (2): auth guard, non-member 403
- `TestListMembersBasic` (4): paginated response shape, owner included, all members returned, field presence
- `TestListMembersPagination` (4): page_size limit, page 2, total_pages calc, invalid page_size 422
- `TestListMembersFilters` (4): status, role_id, department, combined filters
- `TestListMembersSearch` (4): by display_name, case-insensitive, by employee_id, no-match empty
- `TestListMembersSorting` (4): name asc, name desc, department, invalid sort_by 422
- `TestListRoles` (3): all system roles, member_count present, owner count correct

Fix: `params={"department": None}` serialized as `department=` (empty string) by httpx, matching no members. Removed the None key from params dict.

## Outcome

- ✅ Impact: Complete member listing endpoint (US6) with pagination, multi-filter, text search, and sort — all per spec and contracts
- 🧪 Tests: 25 integration tests (all passing), 455 unit regression (all passing)
- 📁 Files: 4 files modified/created; 1 tasks.md updated
- 🔁 Next prompts: Phase 9 (next Epic 4 phase)
- 🧠 Reflection: `params={"key": None}` in httpx TestClient serializes as `key=` (empty string query param), not omitted — always exclude None-valued keys from params dict. `contains_eager()` requires an explicit JOIN in the query before use; cannot be used with lazy-loaded relationships. T078 was already done in Phase 5 — always check before implementing.

## Evaluation notes (flywheel)

- Failure modes observed: (1) `params={"department": None}` → `department=` empty string filter → 0 results; (2) subquery count with `contains_eager` JOIN requires `.subquery()` wrapping — works correctly
- Graders run and results (PASS/FAIL): integration 25/25 PASS, unit regression 455/455 PASS
- Prompt variant (if applicable): sp.implement Phase 8
- Next experiment: Phase 9
