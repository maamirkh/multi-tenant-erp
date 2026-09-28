/** useDashboard (T221) — the Executive Dashboard's 10 widgets. */

import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import {
  getDashboard,
  type ExecutiveDashboardResponse,
  type GetDashboardParams,
} from '@/lib/api/reports';
import { reportsKeys } from './queryKeys';
import { useActiveCompanyId } from './useActiveCompanyId';

export function useDashboard(
  params: GetDashboardParams = {},
  options: { enabled?: boolean } = {}
): UseQueryResult<ExecutiveDashboardResponse> {
  const companyId = useActiveCompanyId();
  return useQuery<ExecutiveDashboardResponse>({
    queryKey: reportsKeys.dashboard(companyId, params),
    queryFn: async () => (await getDashboard(companyId, params)).data,
    enabled: companyId !== '' && (options.enabled ?? true),
  });
}
