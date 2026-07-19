/**
 * T121 — ResetPasswordForm component tests.
 *
 * Tests: password mismatch shows validation error; weak password shows error;
 * valid submit calls resetPasswordApi; success redirects to /login;
 * 400 response shows "link invalid" message with re-request link.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ResetPasswordForm } from '@/components/auth/ResetPasswordForm';

const mockReplace = jest.fn();
const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
  useSearchParams: () => new URLSearchParams('token=valid-reset-token'),
}));

const mockResetPasswordApi = jest.fn();
jest.mock('@/lib/api/auth', () => ({
  resetPasswordApi: (...args: unknown[]) => mockResetPasswordApi(...args),
}));

describe('T121 — ResetPasswordForm', () => {
  beforeEach(() => {
    mockResetPasswordApi.mockReset();
    mockPush.mockReset();
  });

  function fillForm(newPass: string, confirmPass: string): void {
    // Use exact match to avoid ambiguity between "New password" and "Confirm new password".
    fireEvent.change(screen.getByLabelText('New password'), {
      target: { value: newPass },
    });
    fireEvent.change(screen.getByLabelText('Confirm new password'), {
      target: { value: confirmPass },
    });
  }

  it('password mismatch shows validation error', async () => {
    render(<ResetPasswordForm />);
    fillForm('ValidPass@12345', 'DifferentPass@1');
    fireEvent.click(screen.getByRole('button', { name: /reset password/i }));
    await waitFor(() =>
      expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument()
    );
    expect(mockResetPasswordApi).not.toHaveBeenCalled();
  });

  it('password too short shows validation error', async () => {
    render(<ResetPasswordForm />);
    fillForm('short', 'short');
    fireEvent.click(screen.getByRole('button', { name: /reset password/i }));
    await waitFor(() =>
      expect(screen.getByText(/at least 12 characters/i)).toBeInTheDocument()
    );
    expect(mockResetPasswordApi).not.toHaveBeenCalled();
  });

  it('valid submit calls resetPasswordApi with token and new password', async () => {
    mockResetPasswordApi.mockResolvedValue(undefined);
    render(<ResetPasswordForm />);
    const pass = 'NewValid@Password1';
    fillForm(pass, pass);
    fireEvent.click(screen.getByRole('button', { name: /reset password/i }));
    await waitFor(() => expect(mockResetPasswordApi).toHaveBeenCalledTimes(1));
    expect(mockResetPasswordApi).toHaveBeenCalledWith('valid-reset-token', pass);
  });

  it('success redirects to /login', async () => {
    mockResetPasswordApi.mockResolvedValue(undefined);
    render(<ResetPasswordForm />);
    const pass = 'NewValid@Password1';
    fillForm(pass, pass);
    fireEvent.click(screen.getByRole('button', { name: /reset password/i }));
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/login?reset=success'));
  });

  it('400 response shows invalid-link message with re-request link', async () => {
    const { ApiClientError } = jest.requireActual<typeof import('@/lib/api/client')>(
      '@/lib/api/client'
    );
    mockResetPasswordApi.mockRejectedValue(
      new ApiClientError(400, { error: { code: 'INVALID_TOKEN', message: '', details: {} } })
    );
    render(<ResetPasswordForm />);
    const pass = 'NewValid@Password1';
    fillForm(pass, pass);
    fireEvent.click(screen.getByRole('button', { name: /reset password/i }));
    await waitFor(() =>
      expect(screen.getByText(/invalid or has expired/i)).toBeInTheDocument()
    );
    expect(screen.getByRole('link', { name: /request a new reset link/i })).toBeInTheDocument();
  });
});
