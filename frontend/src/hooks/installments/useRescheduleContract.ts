/**
 * useRescheduleContract — controlled due-date-only schedule amendment
 * (idempotency-protected, plan.md §20). Backs the Reschedule page (T226).
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  rescheduleInstallmentContract,
  newIdempotencyKey,
  type InstallmentRescheduleRequest,
  type InstallmentContractRead,
} from '@/lib/api/installments';
import { getCompanyId } from '@/components/installments/apiErrors';

export function useRescheduleContract(contractId: string) {
  const queryClient = useQueryClient();
  const companyId = getCompanyId();
  return useMutation<InstallmentContractRead, unknown, InstallmentRescheduleRequest>({
    mutationFn: async (data) =>
      (
        await rescheduleInstallmentContract(companyId, contractId, data, newIdempotencyKey())
      ).data,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['contract', contractId] });
      void queryClient.invalidateQueries({ queryKey: ['schedule', contractId] });
    },
  });
}
