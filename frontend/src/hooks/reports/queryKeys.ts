/**
 * Reports React Query key factory (plan.md §23). Every key carries the
 * active `companyId` as its second element — tenant context is part of this
 * data's caching semantics, never just a URL detail (mirrors
 * `hooks/installments/queryKeys.ts`).
 */

import type {
  GetDashboardParams,
  GetReportParams,
} from '@/lib/api/reports';

export const reportsKeys = {
  all: (companyId: string) => ['reports', companyId] as const,
  discovery: (companyId: string) => ['reports', 'discovery', companyId] as const,
  report: (companyId: string, reportKey: string, params: GetReportParams) =>
    ['reports', companyId, reportKey, params] as const,
  dashboard: (companyId: string, params: GetDashboardParams) =>
    ['reports', companyId, 'dashboard', params] as const,
  customer360: (companyId: string, customerId: string) =>
    ['reports', companyId, 'customer-360', customerId] as const,
  savedViews: (companyId: string) => ['reports', companyId, 'saved-views'] as const,
};
