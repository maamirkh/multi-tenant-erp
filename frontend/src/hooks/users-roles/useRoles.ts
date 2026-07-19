/**
 * useRoles — React Query hooks for role list, create, update, and delete.
 *
 * Phase 11 added the read-only useRoles query for member-add dropdowns.
 * Phase 12 (T103) extends with full CRUD mutations.
 *
 * Cache strategy:
 *   - List query key: ['roles', companyId] — staleTime: 5 minutes
 *   - Single role key: ['role', companyId, roleId]
 *   - onSettled: invalidate list + single role caches
 *
 * Spec reference: Epic 4, Phase 11 (read) + Phase 12 (T103, mutations).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';
import {
  createRole,
  deleteRole,
  listRoles,
  updateRole,
} from '@/lib/api/users-roles';
import type {
  CreateRoleInput,
  RoleDetail,
  RoleListItem,
  UpdateRoleInput,
} from '@/types/users-roles';

// ── List query ────────────────────────────────────────────────────────────────

export function useRoles(companyId: string | undefined): UseQueryResult<RoleListItem[]> {
  return useQuery<RoleListItem[]>({
    queryKey: ['roles', companyId],
    queryFn: () => listRoles(companyId!),
    enabled: companyId !== undefined && companyId !== '',
    staleTime: 5 * 60_000,
  });
}

// ── Create role mutation ──────────────────────────────────────────────────────

export function useCreateRole(
  companyId: string
): UseMutationResult<RoleDetail, Error, CreateRoleInput> {
  const queryClient = useQueryClient();

  return useMutation<RoleDetail, Error, CreateRoleInput>({
    mutationFn: (data) => createRole(companyId, data),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['roles', companyId] });
    },
  });
}

// ── Update role mutation ──────────────────────────────────────────────────────

export function useUpdateRole(
  companyId: string
): UseMutationResult<RoleDetail, Error, { roleId: string; data: UpdateRoleInput }> {
  const queryClient = useQueryClient();

  return useMutation<RoleDetail, Error, { roleId: string; data: UpdateRoleInput }>({
    mutationFn: ({ roleId, data }) => updateRole(companyId, roleId, data),
    onSettled: (_data, _err, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['roles', companyId] });
      void queryClient.invalidateQueries({ queryKey: ['role', companyId, variables.roleId] });
    },
  });
}

// ── Delete role mutation ──────────────────────────────────────────────────────

export function useDeleteRole(
  companyId: string
): UseMutationResult<void, Error, string> {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: (roleId) => deleteRole(companyId, roleId),
    onSettled: (_data, _err, roleId) => {
      void queryClient.invalidateQueries({ queryKey: ['roles', companyId] });
      void queryClient.removeQueries({ queryKey: ['role', companyId, roleId] });
    },
  });
}
