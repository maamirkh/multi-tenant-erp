/**
 * useReportDiscovery (T220) — the Report Definitions the current user may
 * reach right now, already filtered server-side by entitlement and
 * permission (FR-RPT-320). Navigation visibility is driven entirely by this
 * — never by probing a report and hiding it on 403.
 */

import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { getReportDiscovery, type ReportDiscoveryResponse } from '@/lib/api/reports';
import { reportsKeys } from './queryKeys';
import { useActiveCompanyId } from './useActiveCompanyId';

export function useReportDiscovery(): UseQueryResult<ReportDiscoveryResponse> {
  const companyId = useActiveCompanyId();
  return useQuery<ReportDiscoveryResponse>({
    queryKey: reportsKeys.discovery(companyId),
    queryFn: async () => (await getReportDiscovery(companyId)).data,
    enabled: companyId !== '',
    staleTime: 60_000,
  });
}
