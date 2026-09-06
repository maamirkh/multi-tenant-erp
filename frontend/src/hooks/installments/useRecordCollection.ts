/**
 * useRecordCollection — record a collection against a contract
 * (idempotency-protected, plan.md §20).
 *
 * T223: useMutation, invalidates contract/schedule/collections queries on
 * success.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  recordInstallmentCollection,
  newIdempotencyKey,
  type InstallmentCollectionCreate,
  type InstallmentCollectionResultRead,
} from '@/lib/api/installments';
import { getCompanyId } from '@/components/installments/apiErrors';
import { installmentsKeys } from '@/hooks/installments/queryKeys';

export function useRecordCollection(contractId: string) {
  const queryClient = useQueryClient();
  const companyId = getCompanyId();
  return useMutation<InstallmentCollectionResultRead, unknown, InstallmentCollectionCreate>({
    mutationFn: async (data) =>
      (
        await recordInstallmentCollection(companyId, contractId, data, newIdempotencyKey())
      ).data,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: installmentsKeys.contract(companyId, contractId),
      });
      void queryClient.invalidateQueries({
        queryKey: installmentsKeys.schedule(companyId, contractId),
      });
      void queryClient.invalidateQueries({
        queryKey: installmentsKeys.collections(companyId, contractId),
      });
    },
  });
}
