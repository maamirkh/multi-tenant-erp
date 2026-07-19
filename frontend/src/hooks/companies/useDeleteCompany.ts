/**
 * useDeleteCompany — mutation to soft-delete a company.
 *
 * T067: On success, removes ['company', id] from cache and invalidates ['companies'].
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { deleteCompany } from '@/lib/api/companies';
import type { DeleteCompanyInput, DeleteCompanyResult } from '@/types/companies';
import type { UseMutationResult } from '@tanstack/react-query';

interface DeleteCompanyVariables {
  id: string;
  data: DeleteCompanyInput;
}

export function useDeleteCompany(): UseMutationResult<
  DeleteCompanyResult,
  Error,
  DeleteCompanyVariables
> {
  const queryClient = useQueryClient();

  return useMutation<DeleteCompanyResult, Error, DeleteCompanyVariables>({
    mutationFn: ({ id, data }) => deleteCompany(id, data),
    onSuccess: (_result, { id }) => {
      queryClient.removeQueries({ queryKey: ['company', id] });
      void queryClient.invalidateQueries({ queryKey: ['companies'] });
    },
  });
}
