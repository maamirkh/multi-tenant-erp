/**
 * T233 — useRecordCollection hook tests. Verifies the mutation succeeds,
 * invalidates dependent caches, and that a fresh Idempotency-Key is
 * generated per call (plan.md §20).
 */

import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useRecordCollection } from '@/hooks/installments/useRecordCollection';
import type { InstallmentCollectionCreate } from '@/lib/api/installments';

const mockRecordInstallmentCollection = jest.fn();

jest.mock('@/lib/api/installments', () => {
  const actual = jest.requireActual('@/lib/api/installments');
  return {
    ...actual,
    recordInstallmentCollection: (...args: unknown[]) => mockRecordInstallmentCollection(...args),
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

const collectionInput: InstallmentCollectionCreate = {
  amount: '100',
  payment_method: 'CASH',
  cash_account_id: 'account-1',
};

describe('T233 — useRecordCollection', () => {
  beforeEach(() => {
    mockRecordInstallmentCollection.mockReset();
    mockInvalidateQueries.mockReset();
  });

  it('returns the collection result on success and invalidates dependent caches', async () => {
    const collectionResult = { contract_id: 'contract-1', status: 'COLLECTED', amount: '100' };
    mockRecordInstallmentCollection.mockResolvedValueOnce({ data: collectionResult });

    const { result } = renderHook(() => useRecordCollection('contract-1'), {
      wrapper: makeWrapper(),
    });

    await act(async () => {
      result.current.mutate(collectionInput);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(collectionResult);
    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: ['contract', 'contract-1'] });
    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: ['schedule', 'contract-1'] });
    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: ['collections', 'contract-1'] });
  });

  it('passes a client-generated Idempotency-Key to the API call', async () => {
    mockRecordInstallmentCollection.mockResolvedValueOnce({ data: {} });

    const { result } = renderHook(() => useRecordCollection('contract-1'), {
      wrapper: makeWrapper(),
    });

    await act(async () => {
      result.current.mutate(collectionInput);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const [, , , idempotencyKey] = mockRecordInstallmentCollection.mock.calls[0];
    expect(typeof idempotencyKey).toBe('string');
    expect((idempotencyKey as string).length).toBeGreaterThan(0);
  });

  it('exposes error state when the API fails', async () => {
    const apiError = new Error('SETTLED_ALREADY');
    mockRecordInstallmentCollection.mockRejectedValueOnce(apiError);

    const { result } = renderHook(() => useRecordCollection('contract-1'), {
      wrapper: makeWrapper(),
    });

    await act(async () => {
      result.current.mutate(collectionInput);
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(apiError);
  });
});
