/**
 * T072 — useCompany hook tests.
 *
 * Tests:
 * - Successful data fetch returns the correct CompanyDetail type.
 * - Error state is exposed correctly when the API fails.
 * - Hook is disabled when id is undefined.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useCompany } from '@/hooks/companies/useCompany';
import type { CompanyDetail } from '@/types/companies';

const mockGetCompany = jest.fn<Promise<CompanyDetail>, [string]>();

jest.mock('@/lib/api/companies', () => ({
  getCompany: (...args: [string]) => mockGetCompany(...args),
}));

function makeWrapper(): React.FC<{ children: React.ReactNode }> {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      QueryClientProvider,
      { client: queryClient },
      children
    );
  };
}

const mockCompany: CompanyDetail = {
  id: 'uuid-company-1',
  legal_name: 'Test Corp',
  trade_name: null,
  slug: 'test-corp',
  status: 'active',
  owner_id: 'uuid-owner-1',
  email: 'test@corp.com',
  country: 'US',
  default_currency: 'USD',
  default_language: 'en-US',
  default_timezone: 'UTC',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  primary_admin_id: null,
  phone_primary: null,
  phone_secondary: null,
  website: null,
  tax_number: null,
  registration_number: null,
  business_category: null,
  business_type: null,
  incorporation_date: null,
  fiscal_year_start_month: null,
  date_format: null,
  number_format: {},
  logo_url: null,
  brand_color_primary: null,
  brand_color_secondary: null,
  tagline: null,
  settings: {},
  addresses: [],
};

describe('T072 — useCompany', () => {
  beforeEach(() => {
    mockGetCompany.mockReset();
  });

  it('returns data on successful fetch', async () => {
    mockGetCompany.mockResolvedValueOnce(mockCompany);

    const { result } = renderHook(() => useCompany('uuid-company-1'), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockCompany);
    expect(result.current.data?.id).toBe('uuid-company-1');
    expect(result.current.data?.legal_name).toBe('Test Corp');
  });

  it('exposes error state when the API fails', async () => {
    const apiError = new Error('NOT_FOUND');
    mockGetCompany.mockRejectedValueOnce(apiError);

    const { result } = renderHook(() => useCompany('uuid-missing'), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBe(apiError);
    expect(result.current.data).toBeUndefined();
  });

  it('does not fetch when id is undefined', () => {
    const { result } = renderHook(() => useCompany(undefined), {
      wrapper: makeWrapper(),
    });

    expect(result.current.fetchStatus).toBe('idle');
    expect(mockGetCompany).not.toHaveBeenCalled();
  });

  it('does not fetch when id is an empty string', () => {
    const { result } = renderHook(() => useCompany(''), {
      wrapper: makeWrapper(),
    });

    expect(result.current.fetchStatus).toBe('idle');
    expect(mockGetCompany).not.toHaveBeenCalled();
  });
});
