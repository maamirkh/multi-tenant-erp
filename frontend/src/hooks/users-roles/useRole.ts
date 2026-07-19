/**
 * useRole — React Query hook for a single role detail with permissions.
 *
 * Query key: ['role', companyId, roleId]
 * staleTime: 60 seconds
 *
 * Spec reference: Epic 4, Phase 12 (T104).
 */

import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { getRole } from '@/lib/api/users-roles';
import type { RoleDetail } from '@/types/users-roles';

export function useRole(
  companyId: string | undefined,
  roleId: string | undefined
): UseQueryResult<RoleDetail> {
  return useQuery<RoleDetail>({
    queryKey: ['role', companyId, roleId],
    queryFn: () => getRole(companyId!, roleId!),
    enabled:
      companyId !== undefined &&
      companyId !== '' &&
      roleId !== undefined &&
      roleId !== '',
    staleTime: 60_000,
  });
}
