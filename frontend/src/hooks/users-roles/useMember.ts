/**
 * useMember — React Query hook for a single member detail.
 *
 * Query key: ['member', companyId, memberId]
 * staleTime: 60 seconds (detail data changes less frequently than list)
 *
 * Spec reference: Epic 4, Phase 11 (T090).
 */

import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { getMember } from '@/lib/api/users-roles';
import type { MemberDetail } from '@/types/users-roles';

export function useMember(
  companyId: string | undefined,
  memberId: string | undefined
): UseQueryResult<MemberDetail> {
  return useQuery<MemberDetail>({
    queryKey: ['member', companyId, memberId],
    queryFn: () => getMember(companyId!, memberId!),
    enabled:
      companyId !== undefined &&
      companyId !== '' &&
      memberId !== undefined &&
      memberId !== '',
    staleTime: 60_000,
  });
}
