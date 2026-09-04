/**
 * T233 — useRescheduleContract hook tests.
 */

import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useRescheduleContract } from '@/hooks/installments/useRescheduleContract';

const mockRescheduleInstallmentContract = jest.fn();

jest.mock('@/lib/api/installments', () => {
  const actual = jest.requireActual('@/lib/api/installments');
  return {
    ...actual,
    rescheduleInstallmentContract: (...args: unknown[]) =>
      mockRescheduleInstallmentContract(...args),
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

describe('T233 — useRescheduleContract', () => {
  beforeEach(() => {
    mockRescheduleInstallmentContract.mockReset();
    mockInvalidateQueries.mockReset();
  });

  it('returns the rescheduled contract on success and invalidates schedule cache', async () => {
    const contract = { id: 'contract-1', status: 'ACTIVE' };
    mockRescheduleInstallmentContract.mockResolvedValueOnce({ data: contract });

    const { result } = renderHook(() => useRescheduleContract('contract-1'), {
      wrapper: makeWrapper(),
    });

    await act(async () => {
      result.current.mutate({
        first_due_date: '2026-02-01',
        reason: 'Customer requested',
        requested_by: 'user-2',
      });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(contract);
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ['schedule', 'company-1', 'contract-1'],
    });
  });

  it('exposes error state when maker-checker is violated', async () => {
    const apiError = new Error('MAKER_CHECKER_VIOLATION');
    mockRescheduleInstallmentContract.mockRejectedValueOnce(apiError);

    const { result } = renderHook(() => useRescheduleContract('contract-1'), {
      wrapper: makeWrapper(),
    });

    await act(async () => {
      result.current.mutate({
        first_due_date: '2026-02-01',
        reason: 'Customer requested',
        requested_by: 'user-1',
      });
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(apiError);
  });
});
