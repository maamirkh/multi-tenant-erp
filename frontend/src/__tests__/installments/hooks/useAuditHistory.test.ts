/**
 * T233 — useAuditHistory hook tests.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useAuditHistory } from '@/hooks/installments/useAuditHistory';

const mockGetInstallmentContractAuditHistory = jest.fn();

jest.mock('@/lib/api/installments', () => ({
  getInstallmentContractAuditHistory: (...args: unknown[]) =>
    mockGetInstallmentContractAuditHistory(...args),
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

describe('T233 — useAuditHistory', () => {
  beforeEach(() => {
    mockGetInstallmentContractAuditHistory.mockReset();
  });

  it('returns audit entries on successful fetch', async () => {
    const entries = [{ id: 'a1', action: 'CREATED', occurred_at: '2026-01-01T00:00:00Z' }];
    mockGetInstallmentContractAuditHistory.mockResolvedValueOnce({ data: entries });

    const { result } = renderHook(() => useAuditHistory('contract-1'), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(entries);
  });

  it('does not fetch when contractId is undefined', () => {
    const { result } = renderHook(() => useAuditHistory(undefined), { wrapper: makeWrapper() });
    expect(result.current.fetchStatus).toBe('idle');
    expect(mockGetInstallmentContractAuditHistory).not.toHaveBeenCalled();
  });
});
