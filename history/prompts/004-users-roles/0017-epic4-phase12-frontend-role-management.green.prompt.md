---
id: "0017"
title: Epic 4 Phase 12 Frontend Role Management
stage: green
date: 2026-07-19
surface: agent
model: claude-sonnet-4-6
feature: 004-users-roles
branch: 004-users-roles
user: shehla83
command: /sp.implement
labels: ["phase-12","roles","frontend","react-query","react-hook-form","zod","next.js"]
links:
  spec: specs/004-users-roles/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/lib/api/users-roles.ts (extended: getRole, createRole, updateRole, deleteRole, listPermissions)
  - frontend/src/types/users-roles.ts (extended: PermissionCatalogItem, PermissionItem, PermissionGroup, RoleDetail, CreateRoleInput, UpdateRoleInput)
  - frontend/src/schemas/users-roles.ts (extended: CreateRoleSchema, UpdateRoleSchema, CreateRoleFormData, UpdateRoleFormData)
  - frontend/src/hooks/users-roles/useRoles.ts (rewritten: useRoles + useCreateRole + useUpdateRole + useDeleteRole)
  - frontend/src/hooks/users-roles/useRole.ts (created)
  - frontend/src/hooks/users-roles/usePermissions.ts (created)
  - frontend/src/components/users-roles/RoleBadge.tsx (created)
  - frontend/src/components/users-roles/RoleTable.tsx (created)
  - frontend/src/components/users-roles/RolePermissionChecklist.tsx (created)
  - frontend/src/components/users-roles/RoleForm.tsx (created)
  - frontend/src/app/(protected)/(companies)/companies/[id]/roles/page.tsx (created)
  - frontend/src/app/(protected)/(companies)/companies/[id]/roles/new/page.tsx (created)
  - frontend/src/app/(protected)/(companies)/companies/[id]/roles/[roleId]/page.tsx (created)
  - frontend/src/app/(protected)/(companies)/companies/[id]/roles/[roleId]/edit/page.tsx (created)
  - specs/004-users-roles/tasks.md (T102-T113 marked [X])
tests:
  - tsc --noEmit (exit 0, no type errors)
---

## Prompt

# DevSphere ERP
# Epic 4 – Phase 12 Implementation
# Phase Name: Frontend — Role Management (US3, US8)

Implement ONLY Phase 12 ("Frontend — Role Management (US3, US8)") from the approved Epic 4 tasks.md.

The following documents are already approved and are the Single Source of Truth (SSOT):
- Engineering Principles, Product Vision, Architecture, Coding Standards, API Guidelines
- Epic 4 spec.md, plan.md, tasks.md

Before writing any code: read the approved specification, plan, tasks; understand Phase 12 scope; implement ONLY Phase 12 tasks.

[Full /sp.implement invocation — see session 00e06a7a-5d14-4664-b9c5-5fdc0724a4c6]

## Response snapshot

Implemented all 12 tasks (T102–T113) for Phase 12 — Frontend Role Management:

**API + Types + Schemas (T102):**
- Extended `lib/api/users-roles.ts` with `getRole`, `createRole`, `updateRole`, `deleteRole`, `listPermissions`
- Extended `types/users-roles.ts` with `PermissionCatalogItem`, `PermissionItem`, `PermissionGroup`, `RoleDetail`, `CreateRoleInput`, `UpdateRoleInput`
- Extended `schemas/users-roles.ts` with `CreateRoleSchema` and `UpdateRoleSchema` (Zod + react-hook-form)

**Hooks (T103–T105):**
- Rewrote `useRoles.ts` with full CRUD mutations (`useCreateRole`, `useUpdateRole`, `useDeleteRole`)
- Created `useRole.ts` — single role query (staleTime: 60s)
- Created `usePermissions.ts` — global permissions catalogue (staleTime: 30min)

**Components (T106–T109):**
- `RoleBadge` — blue for system, purple for custom; shows rank + dot indicator
- `RoleTable` — sorted (system first then custom, by rank desc); delete only for custom with 0 members; inline delete confirmation dialog
- `RolePermissionChecklist` — controlled checklist grouped by module; per-module select-all with indeterminate state; readOnly disables all
- `RoleForm` — shared create/edit via `mode` prop; useController for permission_codes array; readOnly for system roles shows notice + Back button only

**Pages (T110–T113):**
- `RoleListPage` — RoleTable + Admin+ RequireRank guard + "New Role" button
- `CreateRolePage` — RoleForm in create mode; navigates to new role detail on success
- `RoleDetailPage` — role info card + permissions grouped by module (inline grouping logic); Edit link
- `EditRolePage` — RoleForm in edit/readOnly mode based on `role.is_system`; useUpdateRole mutation

**Type fixes applied (exactOptionalPropertyTypes: true):**
- Removed `.default([])` from `CreateRoleSchema.permission_codes` to fix zodResolver generic mismatch
- Changed `RoleFormProps.serverError` from `serverError?: string` to `serverError: string | undefined`
- Used conditional spread `...(data.description ? { description: data.description } : {})` in CreateRolePage to avoid `string | undefined` on `description?: string`

TypeScript: `tsc --noEmit` → exit 0 (no errors).

## Outcome

- ✅ Impact: Full role management UI (list, create, detail, edit) for Epic 4 US3/US8 complete
- 🧪 Tests: `tsc --noEmit` → exit 0
- 📁 Files: 14 files created/modified (10 new, 4 extended)
- 🔁 Next prompts: Phase 13 (next phase in Epic 4)
- 🧠 Reflection: `exactOptionalPropertyTypes: true` requires careful handling of optional props and zodResolver generics with `.default()`. Always use `string | undefined` (not `?: string`) when a value may be explicitly undefined in JSX props or function args.

## Evaluation notes (flywheel)

- Failure modes observed: zodResolver type mismatch with `.default([])` on Zod array fields; `serverError?: string` rejecting `string | undefined` with exactOptionalPropertyTypes; `description?: string` in interfaces rejecting conditional undefined values
- Graders run and results (PASS/FAIL): tsc --noEmit PASS
- Prompt variant (if applicable): /sp.implement continuation after context compaction
- Next experiment: Pre-check for exactOptionalPropertyTypes violations at schema/type definition time before writing components
