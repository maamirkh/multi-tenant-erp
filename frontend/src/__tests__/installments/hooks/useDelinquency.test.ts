/**
 * T233 — useDelinquency hook tests. Verifies client-side filtering by
 * contract_id against the "overdue" report rows.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useDelinquency } from '@/hooks/installments/useDelinquency';

const mockGetInstallmentReport = jest.fn();

jest.mock('@/lib/api/installments', () => ({
  getInstallmentReport: (...args: unknown[]) => mockGetInstallmentReport(...args),
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

describe('T233 — useDelinquency', () => {
  beforeEach(() => {
    mockGetInstallmentReport.mockReset();
  });

  it('filters overdue rows to the requested contract_id', async () => {
    mockGetInstallmentReport.mockResolvedValueOnce({
      data: {
        items: [
          { contract_id: 'contract-1', days_overdue: 5 },
          { contract_id: 'contract-2', days_overdue: 10 },
        ],
        total: 2,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    });

    const { result } = renderHook(() => useDelinquency('contract-1'), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([{ contract_id: 'contract-1', days_overdue: 5 }]);
    expect(mockGetInstallmentReport).toHaveBeenCalledWith('company-1', 'overdue', 1, 100);
  });
});
