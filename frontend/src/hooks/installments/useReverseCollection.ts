/**
 * useReverseCollection — reverse a previously recorded collection
 * (idempotency-protected, plan.md §20).
 *
 * T223: useMutation, invalidates contract/schedule/collections queries on
 * success.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  reverseInstallmentCollection,
  newIdempotencyKey,
  type InstallmentCollectionResultRead,
} from '@/lib/api/installments';
import { getCompanyId } from '@/components/installments/apiErrors';

export function useReverseCollection(contractId: string) {
  const queryClient = useQueryClient();
  const companyId = getCompanyId();
  return useMutation<
    InstallmentCollectionResultRead,
    unknown,
    { collectionId: string; reason: string }
  >({
    mutationFn: async ({ collectionId, reason }) =>
      (
        await reverseInstallmentCollection(companyId, collectionId, reason, newIdempotencyKey())
      ).data,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['contract', contractId] });
      void queryClient.invalidateQueries({ queryKey: ['schedule', contractId] });
      void queryClient.invalidateQueries({ queryKey: ['collections', contractId] });
    },
  });
}
