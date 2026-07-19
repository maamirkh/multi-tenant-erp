/**
 * useCompanyAuditLog — paginated query for a company's audit log.
 *
 * T071: Query with key ['company-audit-log', id, filters], staleTime: 60s.
 * Accepts page, page_size, action, actor_id, date_from, date_to params.
 */

import { useQuery } from '@tanstack/react-query';
import { getCompanyAuditLog } from '@/lib/api/companies';
import type { AuditLogEntry, AuditLogParams, PaginatedResponse } from '@/types/companies';
import type { UseQueryResult } from '@tanstack/react-query';

export function useCompanyAuditLog(
  id: string,
  params: AuditLogParams = {}
): UseQueryResult<PaginatedResponse<AuditLogEntry>> {
  return useQuery<PaginatedResponse<AuditLogEntry>>({
    queryKey: ['company-audit-log', id, params],
    queryFn: () => getCompanyAuditLog(id, params),
    enabled: id !== '',
    staleTime: 60 * 1000,
  });
}
