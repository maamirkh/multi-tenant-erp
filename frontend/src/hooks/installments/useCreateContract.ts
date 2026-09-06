/**
 * useCreateContract — create a DRAFT installment contract.
 *
 * T220: useMutation, invalidates the ['contracts'] list query on success.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  createInstallmentContract,
  type InstallmentContractCreate,
  type InstallmentContractRead,
} from '@/lib/api/installments';
import { getCompanyId } from '@/components/installments/apiErrors';

export function useCreateContract() {
  const queryClient = useQueryClient();
  const companyId = getCompanyId();
  return useMutation<InstallmentContractRead, unknown, InstallmentContractCreate>({
    mutationFn: async (data) => (await createInstallmentContract(companyId, data)).data,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['contracts', companyId] });
    },
  });
}
