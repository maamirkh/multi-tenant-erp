/**
 * useRestoreCompany — mutation to restore a soft-deleted company.
 *
 * T067: On success, invalidates both ['company', id] and ['companies'].
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { restoreCompany } from '@/lib/api/companies';
import type { CompanyDetail } from '@/types/companies';
import type { UseMutationResult } from '@tanstack/react-query';

export function useRestoreCompany(
  id: string
): UseMutationResult<CompanyDetail, Error, void> {
  const queryClient = useQueryClient();

  return useMutation<CompanyDetail, Error, void>({
    mutationFn: () => restoreCompany(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['company', id] });
      void queryClient.invalidateQueries({ queryKey: ['companies'] });
    },
  });
}
