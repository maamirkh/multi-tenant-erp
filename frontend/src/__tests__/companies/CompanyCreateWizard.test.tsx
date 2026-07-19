/**
 * T084 — CompanyCreateWizard component tests.
 *
 * Tests:
 * - Step 1 validation prevents progression with empty legal_name.
 * - Step 2 validates currency code (must be 3 letters if provided).
 * - Submit calls the createCompany mutation.
 * - Failed submit shows error message.
 */

import React from 'react';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CompanyCreateWizard } from '@/components/companies/CompanyCreateWizard';

// ── Mocks ─────────────────────────────────────────────────────────────────────

const mockPush = jest.fn();

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

const mockMutate = jest.fn();

jest.mock('@/hooks/companies/useCreateCompany', () => ({
  useCreateCompany: () => ({
    mutate: mockMutate,
    isPending: false,
    isError: false,
    error: null,
  }),
}));

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeWrapper(): React.FC<{ children: React.ReactNode }> {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

function renderWizard() {
  return render(<CompanyCreateWizard />, { wrapper: makeWrapper() });
}

async function fillStep1(legalName: string, email: string) {
  fireEvent.change(screen.getByLabelText(/Company Name/i), {
    target: { value: legalName },
  });
  fireEvent.change(screen.getByLabelText(/Business Email/i), {
    target: { value: email },
  });
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /next/i }));
  });
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('T084 — CompanyCreateWizard', () => {
  beforeEach(() => {
    mockPush.mockReset();
    mockMutate.mockReset();
  });

  it('prevents progression from step 1 with empty legal_name', async () => {
    renderWizard();

    expect(screen.getByLabelText(/Company Name/i)).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /next/i }));
    });

    await waitFor(() => {
      expect(screen.getByText(/at least 2 characters/i)).toBeInTheDocument();
    });

    // Still on step 1
    expect(screen.getByLabelText(/Company Name/i)).toBeInTheDocument();
    expect(mockMutate).not.toHaveBeenCalled();
  });

  it('prevents progression from step 1 with invalid email', async () => {
    renderWizard();

    fireEvent.change(screen.getByLabelText(/Company Name/i), {
      target: { value: 'Test Corp' },
    });
    fireEvent.change(screen.getByLabelText(/Business Email/i), {
      target: { value: 'not-an-email' },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /next/i }));
    });

    await waitFor(() => {
      expect(screen.getByText(/valid email/i)).toBeInTheDocument();
    });
  });

  it('advances to step 2 after valid step 1 data', async () => {
    renderWizard();

    await fillStep1('Acme Inc', 'test@acme.com');

    await waitFor(() => {
      expect(screen.getByLabelText(/Default Currency/i)).toBeInTheDocument();
    });
  });

  it('validates currency code on step 2 (must be 3 letters)', async () => {
    renderWizard();

    await fillStep1('Acme Inc', 'test@acme.com');

    await waitFor(() => screen.getByLabelText(/Default Currency/i));

    fireEvent.change(screen.getByLabelText(/Default Currency/i), {
      target: { value: 'US' }, // only 2 chars — invalid
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /next/i }));
    });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Currency must be a 3-letter code')).toBeInTheDocument();
    });
  });

  it('calls mutation on submit at review step', async () => {
    renderWizard();

    await fillStep1('Acme Inc', 'test@acme.com');

    // Step 2 — next with no optional fields
    await waitFor(() => screen.getByRole('button', { name: /next/i }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /next/i }));
    });

    // Step 3 — skip branding
    await waitFor(() => screen.getByRole('button', { name: /skip/i }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /skip/i }));
    });

    // Review step
    await waitFor(() => screen.getByRole('button', { name: /Create Company/i }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Create Company/i }));
    });

    expect(mockMutate).toHaveBeenCalledWith(
      expect.objectContaining({ legal_name: 'Acme Inc', email: 'test@acme.com' }),
      expect.objectContaining({ onSuccess: expect.any(Function), onError: expect.any(Function) })
    );
  });

  it('shows error message when submit fails', async () => {
    mockMutate.mockImplementation((_data: unknown, handlers: { onError: (e: Error) => void }) => {
      handlers.onError(new Error('COMPANY_NAME_CONFLICT'));
    });

    renderWizard();

    await fillStep1('Acme Inc', 'test@acme.com');

    await waitFor(() => screen.getByRole('button', { name: /next/i }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /next/i }));
    });

    await waitFor(() => screen.getByRole('button', { name: /skip/i }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /skip/i }));
    });

    await waitFor(() => screen.getByRole('button', { name: /Create Company/i }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Create Company/i }));
    });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/COMPANY_NAME_CONFLICT/i)).toBeInTheDocument();
    });

    expect(mockPush).not.toHaveBeenCalled();
  });
});
