/**
 * T233 — useCreateContract hook tests. Mirrors useCreateCompany.test.ts.
 */

import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useCreateContract } from '@/hooks/installments/useCreateContract';
import type { InstallmentContractCreate, InstallmentContractRead } from '@/lib/api/installments';

const mockCreateInstallmentContract = jest.fn();

jest.mock('@/lib/api/installments', () => ({
  createInstallmentContract: (...args: unknown[]) => mockCreateInstallmentContract(...args),
}));

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

const mockContract = { id: 'contract-1', status: 'DRAFT' } as InstallmentContractRead;
const createInput = {
  sales_invoice_id: 'invoice-1',
  down_payment_amount: '0',
  installment_count: 12,
  frequency: 'MONTHLY',
  first_due_date: '2026-01-01',
  maturity_date: '2027-01-01',
} as InstallmentContractCreate;

describe('T233 — useCreateContract', () => {
  beforeEach(() => {
    mockCreateInstallmentContract.mockReset();
    mockInvalidateQueries.mockReset();
  });

  it('returns the created contract on success', async () => {
    mockCreateInstallmentContract.mockResolvedValueOnce({ data: mockContract });

    const { result } = renderHook(() => useCreateContract(), { wrapper: makeWrapper() });

    await act(async () => {
      result.current.mutate(createInput);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockContract);
  });

  it('invalidates the contracts cache on success', async () => {
    mockCreateInstallmentContract.mockResolvedValueOnce({ data: mockContract });

    const { result } = renderHook(() => useCreateContract(), { wrapper: makeWrapper() });

    await act(async () => {
      result.current.mutate(createInput);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: ['contracts'] });
  });

  it('exposes error state when the API fails', async () => {
    const apiError = new Error('CONFLICT');
    mockCreateInstallmentContract.mockRejectedValueOnce(apiError);

    const { result } = renderHook(() => useCreateContract(), { wrapper: makeWrapper() });

    await act(async () => {
      result.current.mutate(createInput);
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(apiError);
  });
});
