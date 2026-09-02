/**
 * T233 — useContracts hook tests.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useContracts } from '@/hooks/installments/useContracts';

const mockListInstallmentContracts = jest.fn();

jest.mock('@/lib/api/installments', () => ({
  listInstallmentContracts: (...args: unknown[]) => mockListInstallmentContracts(...args),
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

describe('T233 — useContracts', () => {
  beforeEach(() => {
    mockListInstallmentContracts.mockReset();
  });

  it('returns paginated data on successful fetch', async () => {
    const page = { items: [{ id: 'c1' }], total: 1, page: 1, page_size: 20, pages: 1 };
    mockListInstallmentContracts.mockResolvedValueOnce({ data: page });

    const { result } = renderHook(() => useContracts({ page: 1, page_size: 20 }), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(page);
    expect(mockListInstallmentContracts).toHaveBeenCalledWith('company-1', 1, 20);
  });

  it('exposes error state when the API fails', async () => {
    const apiError = new Error('FORBIDDEN');
    mockListInstallmentContracts.mockRejectedValueOnce(apiError);

    const { result } = renderHook(() => useContracts(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(apiError);
  });
});
