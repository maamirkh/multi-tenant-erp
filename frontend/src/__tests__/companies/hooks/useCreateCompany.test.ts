/**
 * T072 — useCreateCompany hook tests.
 *
 * Tests:
 * - Mutation returns the correct Company type on success.
 * - Error state is exposed correctly when the API fails.
 * - On success, the ['companies'] query cache is invalidated.
 */

import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useCreateCompany } from '@/hooks/companies/useCreateCompany';
import type { Company, CreateCompanyInput } from '@/types/companies';

const mockCreateCompany = jest.fn<Promise<Company>, [CreateCompanyInput]>();

jest.mock('@/lib/api/companies', () => ({
  createCompany: (data: CreateCompanyInput) => mockCreateCompany(data),
}));

const mockInvalidateQueries = jest.fn();

jest.mock('@tanstack/react-query', () => {
  const actual = jest.requireActual('@tanstack/react-query') as object;
  return {
    ...actual,
    useQueryClient: () => ({
      invalidateQueries: mockInvalidateQueries,
    }),
  };
});

function makeWrapper(): React.FC<{ children: React.ReactNode }> {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      QueryClientProvider,
      { client: queryClient },
      children
    );
  };
}

const mockCompany: Company = {
  id: 'uuid-new-1',
  legal_name: 'New Corp',
  trade_name: null,
  slug: 'new-corp',
  status: 'pending_setup',
  owner_id: 'uuid-owner-1',
  email: 'new@corp.com',
  country: null,
  default_currency: 'USD',
  default_language: 'en-US',
  default_timezone: 'UTC',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const createInput: CreateCompanyInput = {
  legal_name: 'New Corp',
  email: 'new@corp.com',
};

describe('T072 — useCreateCompany', () => {
  beforeEach(() => {
    mockCreateCompany.mockReset();
    mockInvalidateQueries.mockReset();
  });

  it('returns correct Company type on successful mutation', async () => {
    mockCreateCompany.mockResolvedValueOnce(mockCompany);

    const { result } = renderHook(() => useCreateCompany(), {
      wrapper: makeWrapper(),
    });

    await act(async () => {
      result.current.mutate(createInput);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockCompany);
    expect(result.current.data?.id).toBe('uuid-new-1');
    expect(result.current.data?.status).toBe('pending_setup');
  });

  it('exposes error state when the API fails', async () => {
    const apiError = new Error('COMPANY_NAME_CONFLICT');
    mockCreateCompany.mockRejectedValueOnce(apiError);

    const { result } = renderHook(() => useCreateCompany(), {
      wrapper: makeWrapper(),
    });

    await act(async () => {
      result.current.mutate(createInput);
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBe(apiError);
    expect(result.current.data).toBeUndefined();
  });

  it('invalidates the companies cache on success', async () => {
    mockCreateCompany.mockResolvedValueOnce(mockCompany);

    const { result } = renderHook(() => useCreateCompany(), {
      wrapper: makeWrapper(),
    });

    await act(async () => {
      result.current.mutate(createInput);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ['companies'],
    });
  });
});
