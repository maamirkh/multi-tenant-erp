/** useCustomer360 (T221) — one customer's four independently-authorized sections. */

import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { getCustomer360, type Customer360Response } from '@/lib/api/reports';
import { reportsKeys } from './queryKeys';
import { useActiveCompanyId } from './useActiveCompanyId';

export function useCustomer360(customerId: string): UseQueryResult<Customer360Response> {
  const companyId = useActiveCompanyId();
  return useQuery<Customer360Response>({
    queryKey: reportsKeys.customer360(companyId, customerId),
    queryFn: async () => (await getCustomer360(companyId, customerId)).data,
    enabled: companyId !== '' && customerId !== '',
  });
}
