/**
 * useCreateCompany — mutation to create a new company.
 *
 * T064: useMutation calling createCompany(), on success invalidates ['companies'].
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createCompany } from '@/lib/api/companies';
import type { Company, CreateCompanyInput } from '@/types/companies';
import type { UseMutationResult } from '@tanstack/react-query';

export function useCreateCompany(): UseMutationResult<Company, Error, CreateCompanyInput> {
  const queryClient = useQueryClient();

  return useMutation<Company, Error, CreateCompanyInput>({
    mutationFn: createCompany,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['companies'] });
    },
  });
}
