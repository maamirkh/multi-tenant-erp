/**
 * useCompany — fetch a single company by id.
 *
 * T063: useQuery with key ['company', id], enabled only when id is defined.
 */

import { useQuery } from '@tanstack/react-query';
import { getCompany } from '@/lib/api/companies';
import type { CompanyDetail } from '@/types/companies';
import type { UseQueryResult } from '@tanstack/react-query';

export function useCompany(id: string | undefined): UseQueryResult<CompanyDetail> {
  return useQuery<CompanyDetail>({
    queryKey: ['company', id],
    queryFn: () => getCompany(id!),
    enabled: id !== undefined && id !== '',
  });
}
