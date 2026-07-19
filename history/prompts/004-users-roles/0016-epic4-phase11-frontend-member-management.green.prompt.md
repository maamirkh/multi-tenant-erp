---
id: "0016"
title: Epic 4 Phase 11 Frontend Member Management
stage: green
date: 2026-07-19
surface: agent
model: claude-sonnet-4-6
feature: 004-users-roles
branch: 004-users-roles
user: shehla83
command: /sp.implement
labels: ["epic4","phase11","frontend","member-management","US1","US2","US5","US6","US7","react-query","zod"]
links:
  spec: specs/004-users-roles/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/types/users-roles.ts
  - frontend/src/lib/api/users-roles.ts
  - frontend/src/schemas/users-roles.ts
  - frontend/src/hooks/users-roles/useMembers.ts
  - frontend/src/hooks/users-roles/useMember.ts
  - frontend/src/hooks/users-roles/useRoles.ts
  - frontend/src/components/users-roles/CompanyMemberProvider.tsx
  - frontend/src/components/users-roles/RequireRank.tsx
  - frontend/src/components/users-roles/MemberStatusBadge.tsx
  - frontend/src/components/users-roles/MemberTable.tsx
  - frontend/src/components/users-roles/AddMemberForm.tsx
  - frontend/src/components/users-roles/EditMemberForm.tsx
  - frontend/src/components/users-roles/MemberStatusActions.tsx
  - frontend/src/app/(protected)/(companies)/companies/[id]/members/page.tsx
  - frontend/src/app/(protected)/(companies)/companies/[id]/members/add/page.tsx
  - frontend/src/app/(protected)/(companies)/companies/[id]/members/[memberId]/page.tsx
  - frontend/src/app/(protected)/(companies)/companies/[id]/members/[memberId]/edit/page.tsx
  - specs/004-users-roles/tasks.md
tests:
  - frontend/src/: TypeScript type check (tsc --noEmit) — 0 errors
---

## Prompt

```text
# DevSphere ERP
# Epic 4 – Phase 11 Implementation
# Phase Name: Frontend — Member Management (US1, US2, US5, US6, US7)

Implement ONLY Phase 11 ("Frontend — Member Management (US1, US2, US5, US6, US7)") from the approved Epic 4 tasks.md.
```

## Response snapshot

Implemented Phase 11 (Frontend — Member Management) in full across 17 new files + tasks.md update:

**TypeScript types** (`frontend/src/types/users-roles.ts`):
- MembershipStatus, MemberSortBy, SortOrder enums
- RoleSummary, RoleListItem, MemberResponse, MemberListItem, MemberDetail
- AddMemberInput, UpdateMemberInput, SuspendMemberInput, ArchiveMemberInput
- MemberListParams

**T087 — API client** (`frontend/src/lib/api/users-roles.ts`):
- listMembers, getMember, addMember, updateMember, deactivateMember, suspendMember, lockMember, reactivateMember, archiveMember, restoreMember, listRoles
- All unwrap StandardResponse<T> / PaginatedResponse<T> envelopes; build URLSearchParams excluding undefined keys

**T088 — Zod schemas** (`frontend/src/schemas/users-roles.ts`):
- AddMemberSchema (email required, role_id required, optional employee fields)
- UpdateMemberSchema (all optional/nullable)
- SuspendSchema, ArchiveSchema (reason required)

**T089 — Hooks** (`frontend/src/hooks/users-roles/useMembers.ts`):
- useMembers (paginated query, staleTime 30s)
- useAddMember, useUpdateMember mutations
- useChangeMemberStatus mutation handling all 6 status transitions via StatusAction discriminated union

**T090 — Hook** (`frontend/src/hooks/users-roles/useMember.ts`):
- useMember (single member query, staleTime 60s)

**Additional hook** (`frontend/src/hooks/users-roles/useRoles.ts`):
- useRoles (role list for Add/Edit dropdowns, staleTime 5min)

**T091 — CompanyMemberProvider** (`frontend/src/components/users-roles/CompanyMemberProvider.tsx`):
- Searches member list by current user's email → locates their member record
- Exposes currentMember, currentMemberRank, currentMemberStatus, isLoading

**T092 — RequireRank** (`frontend/src/components/users-roles/RequireRank.tsx`):
- Hides children when currentMemberRank < minRank; returns null while loading
- Optional fallback prop

**T093 — MemberStatusBadge** (`frontend/src/components/users-roles/MemberStatusBadge.tsx`):
- 6-status color scheme: active=green, inactive=gray, suspended=orange, locked=red, pending=blue, archived=gray+strikethrough

**T094 — MemberTable** (`frontend/src/components/users-roles/MemberTable.tsx`):
- Filter row: search, status select, role select (from useRoles), department input, sort select
- HTML table with clickable sort headers; pagination controls; loading skeleton

**T095 — AddMemberForm** (`frontend/src/components/users-roles/AddMemberForm.tsx`):
- Email + role selector (from useRoles), optional employee info fieldset
- 409 → email field error, 422 → root error, onSuccess → parent navigates

**T096 — EditMemberForm** (`frontend/src/components/users-roles/EditMemberForm.tsx`):
- Pre-populated from MemberDetail; sends only changed fields (partial PATCH)
- 409 EMPLOYEE_ID_CONFLICT → employee_id field error, 422 HIRE_DATE_IN_FUTURE → hire_date field error

**T097 — MemberStatusActions** (`frontend/src/components/users-roles/MemberStatusActions.tsx`):
- Available buttons based on current status and actorRank > member.role.rank guard
- ReasonDialog for suspend/archive; ConfirmDialog for deactivate/lock/reactivate/restore

**T098–T101 — Pages**:
- MemberListPage: CompanyMemberProvider + MemberTable + RequireRank "Add Member" button
- AddMemberPage: RequireRank(minRank=80) wrapper + AddMemberForm card
- MemberDetailPage: profile card + employee info card + MemberStatusActions (admin only) + self-view support
- EditMemberPage: RequireRank(80) + rank collision guard + EditMemberForm card

**TS fix**: `exactOptionalPropertyTypes: true` required `message: string | undefined` (not `message?: string`) in FieldError props and conditional spread for search param in CompanyMemberProvider.

## Outcome

- ✅ Impact: Full frontend member management — list, add, view, edit, lifecycle actions; rank-based UI visibility (RequireRank, notes hidden, action guards); 4 pages, 6 components, 4 hooks, API client, Zod schemas
- 🧪 Tests: TypeScript type check (tsc --noEmit) — 0 errors; Manual testing pending Docker verification
- 📁 Files: 17 files created; 1 tasks.md updated
- 🔁 Next prompts: Phase 12 (Frontend — Role Management: RoleListPage, CreateRolePage, EditRolePage, RoleDetailPage)
- 🧠 Reflection: `exactOptionalPropertyTypes: true` in tsconfig blocks `{ message: string | undefined }` being passed to `{ message?: string }` — use `message: string | undefined` (explicit, not optional) in child component props. Also: never include undefined-valued keys in URLSearchParams — build params object conditionally. CompanyMemberProvider's search-by-email pattern works for finding current user's membership when no dedicated "me" endpoint exists.

## Evaluation notes (flywheel)

- Failure modes observed: exactOptionalPropertyTypes TS errors in FieldError props (8 in AddMemberForm, 7 in EditMemberForm) and CompanyMemberProvider search param — fixed in one round
- Graders run and results (PASS/FAIL): tsc --noEmit PASS (0 errors after fix)
- Prompt variant (if applicable): sp.implement Phase 11
- Next experiment: Phase 12 (Frontend — Role Management)
