/**
 * T233 — useReverseCollection hook tests.
 */

import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useReverseCollection } from '@/hooks/installments/useReverseCollection';

const mockReverseInstallmentCollection = jest.fn();

jest.mock('@/lib/api/installments', () => {
  const actual = jest.requireActual('@/lib/api/installments');
  return {
    ...actual,
    reverseInstallmentCollection: (...args: unknown[]) => mockReverseInstallmentCollection(...args),
  };
});

jest.mock('@/components/installments/apiErrors', () => ({
  getCompanyId: () => 'company-1',
}));

const mockInvalidateQueries = jest.fn();
jest.mock('@tanstack/react-query', () => {
  const actual = jest.requireActual('@tanstack/react-query') as object;
  return { ...actual, useQueryClient: () => ({ invalidateQueries: mockInvalidateQueries }) };
});

function makeWrapper(): React.FC<{ children: React.ReactNode }> {
  const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

describe('T233 — useReverseCollection', () => {
  beforeEach(() => {
    mockReverseInstallmentCollection.mockReset();
    mockInvalidateQueries.mockReset();
  });

  it('returns the reversal result on success and invalidates dependent caches', async () => {
    const reversalResult = { contract_id: 'contract-1', status: 'REVERSED' };
    mockReverseInstallmentCollection.mockResolvedValueOnce({ data: reversalResult });

    const { result } = renderHook(() => useReverseCollection('contract-1'), {
      wrapper: makeWrapper(),
    });

    await act(async () => {
      result.current.mutate({ collectionId: 'collection-1', reason: 'Duplicate entry' });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(reversalResult);
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ['contract', 'company-1', 'contract-1'],
    });
  });

  it('exposes error state when the API fails', async () => {
    const apiError = new Error('ALREADY_REVERSED');
    mockReverseInstallmentCollection.mockRejectedValueOnce(apiError);

    const { result } = renderHook(() => useReverseCollection('contract-1'), {
      wrapper: makeWrapper(),
    });

    await act(async () => {
      result.current.mutate({ collectionId: 'collection-1', reason: 'Duplicate entry' });
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(apiError);
  });
});
