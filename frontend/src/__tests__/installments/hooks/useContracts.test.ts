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

const mockGetCompanyId = jest.fn(() => 'company-1');
jest.mock('@/components/installments/apiErrors', () => ({
  getCompanyId: () => mockGetCompanyId(),
}));

function makeWrapper(queryClient: QueryClient): React.FC<{ children: React.ReactNode }> {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

describe('T233 — useContracts', () => {
  beforeEach(() => {
    mockListInstallmentContracts.mockReset();
    mockGetCompanyId.mockReset();
    mockGetCompanyId.mockReturnValue('company-1');
  });

  it('returns paginated data on successful fetch', async () => {
    const page = { items: [{ id: 'c1' }], total: 1, page: 1, page_size: 20, pages: 1 };
    mockListInstallmentContracts.mockResolvedValueOnce({ data: page });

    const { result } = renderHook(() => useContracts({ page: 1, page_size: 20 }), {
      wrapper: makeWrapper(new QueryClient({ defaultOptions: { queries: { retry: false } } })),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(page);
    expect(mockListInstallmentContracts).toHaveBeenCalledWith('company-1', 1, 20);
  });

  it('exposes error state when the API fails', async () => {
    const apiError = new Error('FORBIDDEN');
    mockListInstallmentContracts.mockRejectedValueOnce(apiError);

    const { result } = renderHook(() => useContracts(), {
      wrapper: makeWrapper(new QueryClient({ defaultOptions: { queries: { retry: false } } })),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(apiError);
  });

  it('SECURITY: never renders Tenant A\'s cached contract list as Tenant B\'s after a company switch, same page/filters, same persistent QueryClient', async () => {
    // One shared QueryClient across both renders, exactly like the real
    // app: `(protected)/layout.tsx` creates a single QueryClient instance
    // that survives client-side navigation between pages/companies.
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = makeWrapper(queryClient);

    const tenantAPage = {
      items: [{ id: 'tenant-a-contract' }],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    };
    const tenantBPage = {
      items: [{ id: 'tenant-b-contract' }],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    };

    // --- Tenant A opens the contracts list ---
    mockGetCompanyId.mockReturnValue('tenant-a');
    mockListInstallmentContracts.mockResolvedValueOnce({ data: tenantAPage });
    const first = renderHook(() => useContracts({ page: 1, page_size: 20 }), { wrapper });
    await waitFor(() => expect(first.result.current.isSuccess).toBe(true));
    expect(first.result.current.data).toEqual(tenantAPage);

    // Simulate navigating away (unmount, cache entry survives — this is
    // exactly the persistence that made the pre-fix bug possible).
    first.unmount();

    // --- Switch active company to Tenant B, same page/filters ---
    mockGetCompanyId.mockReturnValue('tenant-b');
    mockListInstallmentContracts.mockResolvedValueOnce({ data: tenantBPage });
    const second = renderHook(() => useContracts({ page: 1, page_size: 20 }), { wrapper });

    // Tenant A's cached list must NEVER be the value rendered for Tenant
    // B — not even synchronously on the first render before the new
    // fetch resolves. With a tenant-unsafe key this would be `tenantAPage`
    // here (served straight from cache); with the fix it is not.
    expect(second.result.current.data).not.toEqual(tenantAPage);

    await waitFor(() => expect(second.result.current.isSuccess).toBe(true));
    expect(second.result.current.data).toEqual(tenantBPage);
    expect(mockListInstallmentContracts).toHaveBeenLastCalledWith('tenant-b', 1, 20);
  });
});
