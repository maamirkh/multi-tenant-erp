/**
 * useDelinquency — fetch overdue schedule lines for one contract, from
 * the "overdue" report filtered client-side to `contract_id` (no
 * dedicated per-contract delinquency endpoint exists — the overdue
 * report is the approved read path, same pattern as `useCollections`).
 *
 * Backs the Contract Detail page's Delinquency section (T224).
 */

import { useQuery } from '@tanstack/react-query';
import { getInstallmentReport, type InstallmentReportRow } from '@/lib/api/installments';
import { getCompanyId } from '@/components/installments/apiErrors';
import type { UseQueryResult } from '@tanstack/react-query';

export function useDelinquency(
  contractId: string | undefined
): UseQueryResult<InstallmentReportRow[]> {
  const companyId = getCompanyId();
  return useQuery<InstallmentReportRow[]>({
    queryKey: ['delinquency', contractId],
    queryFn: async () => {
      const res = await getInstallmentReport(companyId, 'overdue', 1, 100);
      return res.data.items.filter((row) => row['contract_id'] === contractId);
    },
    enabled: contractId !== undefined && contractId !== '' && companyId !== '',
  });
}
