/**
 * T233 — useSchedule hook tests.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useSchedule } from '@/hooks/installments/useSchedule';

const mockGetActiveInstallmentSchedule = jest.fn();

jest.mock('@/lib/api/installments', () => ({
  getActiveInstallmentSchedule: (...args: unknown[]) => mockGetActiveInstallmentSchedule(...args),
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

describe('T233 — useSchedule', () => {
  beforeEach(() => {
    mockGetActiveInstallmentSchedule.mockReset();
  });

  it('returns schedule data on successful fetch', async () => {
    const schedule = { contract_id: 'contract-1', version_number: 1, status: 'ACTIVE', generated_at: '2026-01-01', lines: [] };
    mockGetActiveInstallmentSchedule.mockResolvedValueOnce({ data: schedule });

    const { result } = renderHook(() => useSchedule('contract-1'), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(schedule);
  });

  it('does not fetch when contractId is undefined', () => {
    const { result } = renderHook(() => useSchedule(undefined), { wrapper: makeWrapper() });
    expect(result.current.fetchStatus).toBe('idle');
    expect(mockGetActiveInstallmentSchedule).not.toHaveBeenCalled();
  });
});
