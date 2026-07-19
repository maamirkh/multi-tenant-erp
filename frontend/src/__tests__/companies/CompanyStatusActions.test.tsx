/**
 * T085 — CompanyStatusActions component tests.
 *
 * Tests:
 * - Activate button shown for inactive company owner.
 * - Deactivate confirmation dialog opens.
 * - Reason field is required (min 10 chars).
 * - Confirmation dialog calls deactivate mutation.
 * - Delete button shown for non-deleted company owner.
 * - Nothing rendered when user is not owner.
 */

import React from 'react';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CompanyStatusActions } from '@/components/companies/CompanyStatusActions';
import type { CompanyDetail } from '@/types/companies';

// ── Mocks ─────────────────────────────────────────────────────────────────────

const mockRouterPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockRouterPush }),
}));

const mockActivateMutate = jest.fn();
const mockDeactivateMutate = jest.fn();
const mockDeleteMutate = jest.fn();

jest.mock('@/hooks/companies/useCompanyStatus', () => ({
  useActivateCompany: () => ({
    mutate: mockActivateMutate,
    isPending: false,
  }),
  useDeactivateCompany: () => ({
    mutate: mockDeactivateMutate,
    isPending: false,
  }),
}));

jest.mock('@/hooks/companies/useDeleteCompany', () => ({
  useDeleteCompany: () => ({
    mutate: mockDeleteMutate,
    isPending: false,
  }),
}));

// ── Helpers ────────────────────────────────────────────────────────────────────

const OWNER_ID = 'user-owner-1';

const makeCompany = (overrides: Partial<CompanyDetail> = {}): CompanyDetail => ({
  id: 'company-1',
  legal_name: 'Acme Inc',
  trade_name: null,
  slug: 'acme-inc',
  status: 'active',
  owner_id: OWNER_ID,
  email: 'acme@example.com',
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
  ...overrides,
});

function makeWrapper(): React.FC<{ children: React.ReactNode }> {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

function renderActions(company: CompanyDetail, userId = OWNER_ID) {
  return render(<CompanyStatusActions company={company} userId={userId} />, {
    wrapper: makeWrapper(),
  });
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('T085 — CompanyStatusActions', () => {
  beforeEach(() => {
    mockActivateMutate.mockReset();
    mockDeactivateMutate.mockReset();
    mockDeleteMutate.mockReset();
    mockRouterPush.mockReset();
  });

  it('renders Activate button for inactive company owner', () => {
    renderActions(makeCompany({ status: 'inactive' }));
    expect(screen.getByRole('button', { name: /Activate Acme Inc/i })).toBeInTheDocument();
  });

  it('renders nothing when user is not the owner', () => {
    const { container } = renderActions(makeCompany({ status: 'active' }), 'other-user');
    expect(container.firstChild).toBeNull();
  });

  it('renders Deactivate button for active company owner', () => {
    renderActions(makeCompany({ status: 'active' }));
    expect(screen.getByRole('button', { name: /Deactivate Acme Inc/i })).toBeInTheDocument();
  });

  it('opens deactivate dialog when Deactivate button is clicked', async () => {
    renderActions(makeCompany({ status: 'active' }));

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Deactivate Acme Inc/i }));
    });

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  it('shows validation error when reason is too short', async () => {
    renderActions(makeCompany({ status: 'active' }));

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Deactivate Acme Inc/i }));
    });

    await waitFor(() => screen.getByRole('dialog'));

    fireEvent.change(screen.getByLabelText(/Reason/i), {
      target: { value: 'Too short' },
    });

    await act(async () => {
      // Click the Deactivate button inside the dialog (not the trigger button)
      const buttons = screen.getAllByRole('button', { name: /Deactivate/i });
      const dialogButton = buttons.at(-1) as HTMLElement;
      fireEvent.click(dialogButton);
    });

    await waitFor(() => {
      expect(screen.getByText(/at least 10 characters/i)).toBeInTheDocument();
    });

    expect(mockDeactivateMutate).not.toHaveBeenCalled();
  });

  it('calls deactivate mutation with reason when form is valid', async () => {
    renderActions(makeCompany({ status: 'active' }));

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Deactivate Acme Inc/i }));
    });

    await waitFor(() => screen.getByRole('dialog'));

    fireEvent.change(screen.getByLabelText(/Reason/i), {
      target: { value: 'Deactivating for maintenance purposes' },
    });

    await act(async () => {
      const buttons = screen.getAllByRole('button', { name: /Deactivate/i });
      const dialogButton = buttons.at(-1) as HTMLElement;
      fireEvent.click(dialogButton);
    });

    await waitFor(() => {
      expect(mockDeactivateMutate).toHaveBeenCalledWith(
        { reason: 'Deactivating for maintenance purposes' },
        expect.objectContaining({ onSuccess: expect.any(Function) })
      );
    });
  });

  it('calls activate mutation when Activate button clicked', async () => {
    renderActions(makeCompany({ status: 'inactive' }));

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Activate Acme Inc/i }));
    });

    expect(mockActivateMutate).toHaveBeenCalledWith();
  });

  it('renders Delete button for non-deleted company owner', () => {
    renderActions(makeCompany({ status: 'active' }));
    expect(screen.getByRole('button', { name: /Delete Acme Inc/i })).toBeInTheDocument();
  });

  it('does not render Delete button for already deleted company', () => {
    renderActions(makeCompany({ status: 'deleted' }));
    expect(screen.queryByRole('button', { name: /Delete Acme Inc/i })).not.toBeInTheDocument();
  });
});
