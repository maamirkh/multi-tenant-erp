/**
 * useOwnershipTransfer — React Query mutation for transferring company ownership.
 *
 * POST /api/v1/companies/{company_id}/transfer-ownership
 *
 * On success, invalidates:
 *   - ['members', companyId]   — member list (roles updated)
 *   - ['member', companyId]    — all single-member caches (prefix match)
 *
 * Spec reference: Epic 4, Phase 14 (T123).
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult } from '@tanstack/react-query';
import { transferOwnership } from '@/lib/api/users-roles';

export function useTransferOwnership(
  companyId: string
): UseMutationResult<void, Error, string> {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: (targetMemberId) => transferOwnership(companyId, targetMemberId),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['members', companyId] });
      void queryClient.invalidateQueries({ queryKey: ['member', companyId] });
    },
  });
}
