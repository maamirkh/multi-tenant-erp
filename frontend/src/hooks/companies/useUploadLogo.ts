/**
 * useUploadLogo — mutation to upload a company logo via multipart form.
 *
 * T068: On success, invalidates ['company', id].
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { uploadCompanyLogo } from '@/lib/api/companies';
import type { LogoUploadResponse } from '@/types/companies';
import type { UseMutationResult } from '@tanstack/react-query';

interface UploadLogoVariables {
  id: string;
  file: File;
}

export function useUploadLogo(): UseMutationResult<
  LogoUploadResponse,
  Error,
  UploadLogoVariables
> {
  const queryClient = useQueryClient();

  return useMutation<LogoUploadResponse, Error, UploadLogoVariables>({
    mutationFn: ({ id, file }) => uploadCompanyLogo(id, file),
    onSuccess: (_result, { id }) => {
      void queryClient.invalidateQueries({ queryKey: ['company', id] });
    },
  });
}
