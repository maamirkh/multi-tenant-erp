/**
 * useCompanyAddresses — query and mutations for company addresses.
 *
 * T070: All mutations invalidate ['company', id] on success.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createCompanyAddress,
  deleteCompanyAddress,
  getCompanyAddresses,
  updateCompanyAddress,
} from '@/lib/api/companies';
import type {
  CompanyAddress,
  CreateAddressInput,
  UpdateAddressInput,
} from '@/types/companies';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

export function useCompanyAddresses(id: string): UseQueryResult<CompanyAddress[]> {
  return useQuery<CompanyAddress[]>({
    queryKey: ['company-addresses', id],
    queryFn: () => getCompanyAddresses(id),
    enabled: id !== '',
  });
}

export function useCreateAddress(
  companyId: string
): UseMutationResult<CompanyAddress, Error, CreateAddressInput> {
  const queryClient = useQueryClient();

  return useMutation<CompanyAddress, Error, CreateAddressInput>({
    mutationFn: (data) => createCompanyAddress(companyId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['company', companyId] });
      void queryClient.invalidateQueries({ queryKey: ['company-addresses', companyId] });
    },
  });
}

interface UpdateAddressVariables {
  addressId: string;
  data: UpdateAddressInput;
}

export function useUpdateAddress(
  companyId: string
): UseMutationResult<CompanyAddress, Error, UpdateAddressVariables> {
  const queryClient = useQueryClient();

  return useMutation<CompanyAddress, Error, UpdateAddressVariables>({
    mutationFn: ({ addressId, data }) => updateCompanyAddress(companyId, addressId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['company', companyId] });
      void queryClient.invalidateQueries({ queryKey: ['company-addresses', companyId] });
    },
  });
}

export function useDeleteAddress(
  companyId: string
): UseMutationResult<void, Error, string> {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: (addressId) => deleteCompanyAddress(companyId, addressId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['company', companyId] });
      void queryClient.invalidateQueries({ queryKey: ['company-addresses', companyId] });
    },
  });
}
