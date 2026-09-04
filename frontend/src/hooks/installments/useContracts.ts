/**
 * useContracts — fetch a paginated list of installment contracts.
 *
 * T220: useQuery with key ['contracts', companyId, filters]. Mirrors
 * `hooks/companies/useCompany.ts`'s TanStack Query convention.
 *
 * The active company id is part of the key (not just the query function's
 * request URL) so that switching companies without a full page reload never
 * serves one tenant's cached list to another — the QueryClient instance
 * persists across client-side navigation, so an omitted tenant id here would
 * let a stale, wrong-tenant page render before the background refetch
 * resolves. Matches the tenant-scoped-key convention already used elsewhere
 * in the app (e.g. platform-admin's `['platform', 'entitlements',
 * selectedTenant?.id]`).
 */

import { useQuery } from '@tanstack/react-query';
import {
  listInstallmentContracts,
  type InstallmentContractSummary,
} from '@/lib/api/installments';
import { getCompanyId } from '@/components/installments/apiErrors';
import { installmentsKeys } from '@/hooks/installments/queryKeys';
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
    queryKey: installmentsKeys.contracts(companyId, { page, page_size: pageSize }),
    queryFn: async () => (await listInstallmentContracts(companyId, page, pageSize)).data,
    enabled: companyId !== '',
  });
}
