/**
 * useCompanyStatus — mutations for activating and deactivating a company.
 *
 * T066: Optimistic updates with snapshot rollback on error.
 *   - onMutate: snapshots cache and writes optimistic status
 *   - onError: rolls back to the snapshot
 *   - onSettled: invalidates ['company', id] and ['companies']
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { activateCompany, deactivateCompany } from '@/lib/api/companies';
import type { CompanyDetail, DeactivateInput } from '@/types/companies';
import type { UseMutationResult } from '@tanstack/react-query';

export function useActivateCompany(
  id: string
): UseMutationResult<CompanyDetail, Error, void> {
  const queryClient = useQueryClient();

  return useMutation<CompanyDetail, Error, void>({
    mutationFn: () => activateCompany(id),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ['company', id] });
      const snapshot = queryClient.getQueryData<CompanyDetail>(['company', id]);
      if (snapshot) {
        queryClient.setQueryData<CompanyDetail>(['company', id], {
          ...snapshot,
          status: 'active',
        });
      }
      return { snapshot };
    },
    onError: (_err, _vars, context) => {
      const ctx = context as { snapshot?: CompanyDetail } | undefined;
      if (ctx?.snapshot) {
        queryClient.setQueryData(['company', id], ctx.snapshot);
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['company', id] });
      void queryClient.invalidateQueries({ queryKey: ['companies'] });
    },
  });
}

export function useDeactivateCompany(
  id: string
): UseMutationResult<CompanyDetail, Error, DeactivateInput> {
  const queryClient = useQueryClient();

  return useMutation<CompanyDetail, Error, DeactivateInput>({
    mutationFn: (data) => deactivateCompany(id, data),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ['company', id] });
      const snapshot = queryClient.getQueryData<CompanyDetail>(['company', id]);
      if (snapshot) {
        queryClient.setQueryData<CompanyDetail>(['company', id], {
          ...snapshot,
          status: 'inactive',
        });
      }
      return { snapshot };
    },
    onError: (_err, _vars, context) => {
      const ctx = context as { snapshot?: CompanyDetail } | undefined;
      if (ctx?.snapshot) {
        queryClient.setQueryData(['company', id], ctx.snapshot);
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['company', id] });
      void queryClient.invalidateQueries({ queryKey: ['companies'] });
    },
  });
}
