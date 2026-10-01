/** useReport (T221) — executes one registered report by its stable key. */

import {
  keepPreviousData,
  useInfiniteQuery,
  useQuery,
  type InfiniteData,
  type UseInfiniteQueryResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import {
  getReport,
  isCursorPage,
  type GetReportParams,
  type ReportResponse,
} from '@/lib/api/reports';
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

/**
 * useCursorReport — `accounting.gl` only (the one cursor-paginated report,
 * plan.md §19). Each "Load more" follows the backend's opaque
 * `next_cursor` (sent back as `filters[cursor]`), never an offset.
 */
export function useCursorReport(
  reportKey: string,
  params: GetReportParams = {},
  options: { enabled?: boolean } = {}
): UseInfiniteQueryResult<InfiniteData<ReportResponse>, Error> {
  const companyId = useActiveCompanyId();
  return useInfiniteQuery({
    queryKey: [...reportsKeys.report(companyId, reportKey, params), 'cursor'],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      getReport(companyId, reportKey, {
        ...params,
        filters: { ...params.filters, cursor: pageParam },
      }),
    getNextPageParam: (last) =>
      isCursorPage(last.data) && last.data.has_more ? last.data.next_cursor : null,
    enabled: companyId !== '' && reportKey !== '' && (options.enabled ?? true),
  });
}
