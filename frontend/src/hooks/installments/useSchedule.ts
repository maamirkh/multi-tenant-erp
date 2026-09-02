/**
 * useSchedule — fetch the active schedule version/lines for a contract.
 *
 * T223: useQuery with key ['schedule', contractId].
 */

import { useQuery } from '@tanstack/react-query';
import { getActiveInstallmentSchedule, type InstallmentScheduleRead } from '@/lib/api/installments';
import { getCompanyId } from '@/components/installments/apiErrors';
import type { UseQueryResult } from '@tanstack/react-query';

export function useSchedule(
  contractId: string | undefined
): UseQueryResult<InstallmentScheduleRead> {
  const companyId = getCompanyId();
  return useQuery<InstallmentScheduleRead>({
    queryKey: ['schedule', contractId],
    queryFn: async () => (await getActiveInstallmentSchedule(companyId, contractId!)).data,
    enabled: contractId !== undefined && contractId !== '' && companyId !== '',
  });
}
