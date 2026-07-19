/**
 * useCompanies — fetch the list of companies owned by the current user.
 *
 * T062: useQuery with key ['companies'], staleTime: 5 minutes.
 */

import { useQuery } from '@tanstack/react-query';
import { listCompanies } from '@/lib/api/companies';
import type { Company } from '@/types/companies';
import type { UseQueryResult } from '@tanstack/react-query';

export function useCompanies(): UseQueryResult<Company[]> {
  return useQuery<Company[]>({
    queryKey: ['companies'],
    queryFn: listCompanies,
    staleTime: 5 * 60 * 1000,
  });
}
