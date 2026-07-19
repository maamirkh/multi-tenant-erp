/**
 * usePermissions — React Query hook for the global permission catalogue.
 *
 * Fetches GET /api/v1/permissions — permissions grouped by module.
 * Not company-scoped; staleTime: 30 minutes (catalogue is static).
 *
 * Query key: ['permissions'] (global singleton)
 *
 * Spec reference: Epic 4, Phase 12 (T105).
 */

import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { listPermissions } from '@/lib/api/users-roles';
import type { PermissionGroup } from '@/types/users-roles';

export function usePermissions(): UseQueryResult<PermissionGroup[]> {
  return useQuery<PermissionGroup[]>({
    queryKey: ['permissions'],
    queryFn: listPermissions,
    staleTime: 30 * 60_000,
  });
}
