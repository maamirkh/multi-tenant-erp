/**
 * useContract — fetch a single installment contract by id.
 *
 * T220: useQuery with key ['contract', id], enabled only when id is defined.
 * Mirrors `hooks/companies/useCompany.ts` exactly.
 */

import { useQuery } from '@tanstack/react-query';
import { getInstallmentContract, type InstallmentContractRead } from '@/lib/api/installments';
import { getCompanyId } from '@/components/installments/apiErrors';
import { installmentsKeys } from '@/hooks/installments/queryKeys';
import type { UseQueryResult } from '@tanstack/react-query';

export function useContract(id: string | undefined): UseQueryResult<InstallmentContractRead> {
  const companyId = getCompanyId();
  return useQuery<InstallmentContractRead>({
    queryKey: installmentsKeys.contract(companyId, id ?? ''),
    queryFn: async () => (await getInstallmentContract(companyId, id!)).data,
    enabled: id !== undefined && id !== '' && companyId !== '',
  });
}
