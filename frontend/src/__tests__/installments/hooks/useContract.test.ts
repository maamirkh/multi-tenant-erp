/**
 * T233 — useContract hook tests. Mirrors useCompany.test.ts's pattern.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useContract } from '@/hooks/installments/useContract';
import type { InstallmentContractRead } from '@/lib/api/installments';

const mockGetInstallmentContract = jest.fn();

jest.mock('@/lib/api/installments', () => ({
  getInstallmentContract: (...args: unknown[]) => mockGetInstallmentContract(...args),
}));

jest.mock('@/components/installments/apiErrors', () => ({
  getCompanyId: () => 'company-1',
}));

function makeWrapper(): React.FC<{ children: React.ReactNode }> {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

const mockContract = { id: 'contract-1', contract_number: 'INST-0001', status: 'DRAFT' } as InstallmentContractRead;

describe('T233 — useContract', () => {
  beforeEach(() => {
    mockGetInstallmentContract.mockReset();
  });

  it('returns data on successful fetch', async () => {
    mockGetInstallmentContract.mockResolvedValueOnce({ data: mockContract });

    const { result } = renderHook(() => useContract('contract-1'), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockContract);
  });

  it('exposes error state when the API fails', async () => {
    const apiError = new Error('NOT_FOUND');
    mockGetInstallmentContract.mockRejectedValueOnce(apiError);

    const { result } = renderHook(() => useContract('missing'), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(apiError);
  });

  it('does not fetch when id is undefined', () => {
    const { result } = renderHook(() => useContract(undefined), { wrapper: makeWrapper() });
    expect(result.current.fetchStatus).toBe('idle');
    expect(mockGetInstallmentContract).not.toHaveBeenCalled();
  });
});
