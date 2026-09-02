/**
 * useContracts — fetch a paginated list of installment contracts.
 *
 * T220: useQuery with key ['contracts', filters]. Mirrors
 * `hooks/companies/useCompany.ts`'s TanStack Query convention.
 */

import { useQuery } from '@tanstack/react-query';
import {
  listInstallmentContracts,
  type InstallmentContractSummary,
} from '@/lib/api/installments';
import { getCompanyId } from '@/components/installments/apiErrors';
import type { PaginatedData } from '@/lib/api/types';
import type { UseQueryResult } from '@tanstack/react-query';

export interface UseContractsFilters {
  page?: number;
  page_size?: number;
}

export function useContracts(
  filters: UseContractsFilters = {}
): UseQueryResult<PaginatedData<InstallmentContractSummary>> {
  const companyId = getCompanyId();
  const page = filters.page ?? 1;
  const pageSize = filters.page_size ?? 20;
  return useQuery<PaginatedData<InstallmentContractSummary>>({
    queryKey: ['contracts', { page, page_size: pageSize }],
    queryFn: async () => (await listInstallmentContracts(companyId, page, pageSize)).data,
    enabled: companyId !== '',
  });
}
