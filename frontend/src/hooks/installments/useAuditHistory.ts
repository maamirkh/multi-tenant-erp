/**
 * useAuditHistory — fetch the chronological audit trail for a contract.
 *
 * Backs the Contract Detail page's Audit-History section (T224).
 */

import { useQuery } from '@tanstack/react-query';
import {
  getInstallmentContractAuditHistory,
  type InstallmentAuditLogRead,
} from '@/lib/api/installments';
import { getCompanyId } from '@/components/installments/apiErrors';
import { installmentsKeys } from '@/hooks/installments/queryKeys';
import type { UseQueryResult } from '@tanstack/react-query';

export function useAuditHistory(
  contractId: string | undefined
): UseQueryResult<InstallmentAuditLogRead[]> {
  const companyId = getCompanyId();
  return useQuery<InstallmentAuditLogRead[]>({
    queryKey: installmentsKeys.auditHistory(companyId, contractId ?? ''),
    queryFn: async () => (await getInstallmentContractAuditHistory(companyId, contractId!)).data,
    enabled: contractId !== undefined && contractId !== '' && companyId !== '',
  });
}
