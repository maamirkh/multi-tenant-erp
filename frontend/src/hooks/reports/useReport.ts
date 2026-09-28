/** useReport (T221) — executes one registered report by its stable key. */

import { keepPreviousData, useQuery, type UseQueryResult } from '@tanstack/react-query';
import { getReport, type GetReportParams, type ReportResponse } from '@/lib/api/reports';
import { reportsKeys } from './queryKeys';
import { useActiveCompanyId } from './useActiveCompanyId';

export function useReport(
  reportKey: string,
  params: GetReportParams = {},
  options: { enabled?: boolean } = {}
): UseQueryResult<ReportResponse> {
  const companyId = useActiveCompanyId();
  return useQuery<ReportResponse>({
    queryKey: reportsKeys.report(companyId, reportKey, params),
    queryFn: () => getReport(companyId, reportKey, params),
    enabled: companyId !== '' && reportKey !== '' && (options.enabled ?? true),
    // Paging/sorting keeps the previous page on screen while the next loads.
    placeholderData: keepPreviousData,
  });
}
