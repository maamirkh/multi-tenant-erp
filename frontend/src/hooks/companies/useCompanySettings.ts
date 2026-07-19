/**
 * useCompanySettings — mutation to update company settings.
 *
 * T069: On success, invalidates ['company', id].
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateCompanySettings } from '@/lib/api/companies';
import type { CompanySettings, UpdateSettingsInput } from '@/types/companies';
import type { UseMutationResult } from '@tanstack/react-query';

interface UpdateSettingsVariables {
  id: string;
  data: UpdateSettingsInput;
}

export function useCompanySettings(): UseMutationResult<
  CompanySettings,
  Error,
  UpdateSettingsVariables
> {
  const queryClient = useQueryClient();

  return useMutation<CompanySettings, Error, UpdateSettingsVariables>({
    mutationFn: ({ id, data }) => updateCompanySettings(id, data),
    onSuccess: (_result, { id }) => {
      void queryClient.invalidateQueries({ queryKey: ['company', id] });
    },
  });
}
