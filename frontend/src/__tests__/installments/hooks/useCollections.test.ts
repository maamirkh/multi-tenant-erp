/**
 * T233 — useCollections hook tests. Verifies client-side filtering by
 * contract_id against the "collection" report rows.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useCollections } from '@/hooks/installments/useCollections';

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

describe('T233 — useCollections', () => {
  beforeEach(() => {
    mockGetInstallmentReport.mockReset();
  });

  it('filters report rows to the requested contract_id', async () => {
    mockGetInstallmentReport.mockResolvedValueOnce({
      data: {
        items: [
          { contract_id: 'contract-1', amount: '100' },
          { contract_id: 'contract-2', amount: '200' },
        ],
        total: 2,
        page: 1,
        page_size: 100,
        pages: 1,
      },
    });

    const { result } = renderHook(() => useCollections('contract-1'), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([{ contract_id: 'contract-1', amount: '100' }]);
    expect(mockGetInstallmentReport).toHaveBeenCalledWith('company-1', 'collection', 1, 100);
  });
});
