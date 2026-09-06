/**
 * T233 — useContractLifecycleActions hook tests. Covers a representative
 * subset (submit, activate w/ idempotency key, writeoff error path) —
 * every sub-mutation shares the same thin wrapper shape.
 */

import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useContractLifecycleActions } from '@/hooks/installments/useContractLifecycleActions';

const mockSubmitInstallmentContract = jest.fn();
const mockActivateInstallmentContract = jest.fn();
const mockWriteoffInstallmentContract = jest.fn();

jest.mock('@/lib/api/installments', () => {
  const actual = jest.requireActual('@/lib/api/installments');
  return {
    ...actual,
    submitInstallmentContract: (...args: unknown[]) => mockSubmitInstallmentContract(...args),
    activateInstallmentContract: (...args: unknown[]) => mockActivateInstallmentContract(...args),
    writeoffInstallmentContract: (...args: unknown[]) => mockWriteoffInstallmentContract(...args),
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

describe('T233 — useContractLifecycleActions', () => {
  beforeEach(() => {
    mockSubmitInstallmentContract.mockReset();
    mockActivateInstallmentContract.mockReset();
    mockWriteoffInstallmentContract.mockReset();
    mockInvalidateQueries.mockReset();
  });

  it('submit() succeeds and invalidates the contract/contracts caches', async () => {
    mockSubmitInstallmentContract.mockResolvedValueOnce({ data: { id: 'contract-1', status: 'PENDING_APPROVAL' } });

    const { result } = renderHook(() => useContractLifecycleActions('contract-1'), {
      wrapper: makeWrapper(),
    });

    await act(async () => {
      result.current.submit.mutate();
    });

    await waitFor(() => expect(result.current.submit.isSuccess).toBe(true));
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ['contract', 'company-1', 'contract-1'],
    });
    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: ['contracts', 'company-1'] });
  });

  it('activate() passes a client-generated Idempotency-Key', async () => {
    mockActivateInstallmentContract.mockResolvedValueOnce({ data: { id: 'contract-1', status: 'ACTIVE' } });

    const { result } = renderHook(() => useContractLifecycleActions('contract-1'), {
      wrapper: makeWrapper(),
    });

    await act(async () => {
      result.current.activate.mutate();
    });

    await waitFor(() => expect(result.current.activate.isSuccess).toBe(true));
    const [, , idempotencyKey] = mockActivateInstallmentContract.mock.calls[0];
    expect(typeof idempotencyKey).toBe('string');
    expect((idempotencyKey as string).length).toBeGreaterThan(0);
  });

  it('writeoff() exposes error state on failure', async () => {
    const apiError = new Error('NOT_DEFAULTED');
    mockWriteoffInstallmentContract.mockRejectedValueOnce(apiError);

    const { result } = renderHook(() => useContractLifecycleActions('contract-1'), {
      wrapper: makeWrapper(),
    });

    await act(async () => {
      result.current.writeoff.mutate('Uncollectible balance');
    });

    await waitFor(() => expect(result.current.writeoff.isError).toBe(true));
    expect(result.current.writeoff.error).toBe(apiError);
  });
});
