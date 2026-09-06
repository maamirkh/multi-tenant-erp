/**
 * useCollections — fetch the "collection" report rows filtered to one
 * contract (no dedicated `GET /contracts/{id}/collections` endpoint
 * exists — the collection report is the approved read path for a
 * contract's collection history, per
 * specs/010-installments/contracts/installments-api.yaml
 * `/reports/{reportType}`).
 *
 * T223: useQuery with key ['collections', contractId].
 */

import { useQuery } from '@tanstack/react-query';
import { getInstallmentReport, type InstallmentReportRow } from '@/lib/api/installments';
import { getCompanyId } from '@/components/installments/apiErrors';
import { installmentsKeys } from '@/hooks/installments/queryKeys';
import type { UseQueryResult } from '@tanstack/react-query';

export function useCollections(
  contractId: string | undefined
): UseQueryResult<InstallmentReportRow[]> {
  const companyId = getCompanyId();
  return useQuery<InstallmentReportRow[]>({
    queryKey: installmentsKeys.collections(companyId, contractId ?? ''),
    queryFn: async () => {
      const res = await getInstallmentReport(companyId, 'collection', 1, 100);
      return res.data.items.filter((row) => row['contract_id'] === contractId);
    },
    enabled: contractId !== undefined && contractId !== '' && companyId !== '',
  });
}
