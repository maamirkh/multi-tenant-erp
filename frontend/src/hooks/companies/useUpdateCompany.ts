/**
 * useUpdateCompany — mutation to partially update a company profile.
 *
 * T065: useMutation calling updateCompany(), on success invalidates ['company', id].
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateCompany } from '@/lib/api/companies';
import type { CompanyDetail, UpdateCompanyInput } from '@/types/companies';
import type { UseMutationResult } from '@tanstack/react-query';

interface UpdateCompanyVariables {
  id: string;
  data: UpdateCompanyInput;
}

export function useUpdateCompany(): UseMutationResult<
  CompanyDetail,
  Error,
  UpdateCompanyVariables
> {
  const queryClient = useQueryClient();

  return useMutation<CompanyDetail, Error, UpdateCompanyVariables>({
    mutationFn: ({ id, data }) => updateCompany(id, data),
    onSuccess: (_result, { id }) => {
      void queryClient.invalidateQueries({ queryKey: ['company', id] });
    },
  });
}
