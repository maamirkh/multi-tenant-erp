/**
 * T120 — ForgotPasswordForm component tests.
 *
 * Tests: empty email shows validation error; valid email shows success message
 * after submit; success message is identical regardless of API response
 * (anti-enumeration); loading state shows spinner/disabled button.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ForgotPasswordForm } from '@/components/auth/ForgotPasswordForm';

const mockForgotPasswordApi = jest.fn();
jest.mock('@/lib/api/auth', () => ({
  forgotPasswordApi: (...args: unknown[]) => mockForgotPasswordApi(...args),
}));

describe('T120 — ForgotPasswordForm', () => {
  beforeEach(() => {
    mockForgotPasswordApi.mockReset();
  });

  it('empty email shows validation error without API call', async () => {
    render(<ForgotPasswordForm />);
    fireEvent.click(screen.getByRole('button', { name: /send reset link/i }));
    await waitFor(() =>
      expect(screen.getByText(/please enter a valid email address/i)).toBeInTheDocument()
    );
    expect(mockForgotPasswordApi).not.toHaveBeenCalled();
  });

  it('valid email shows success message after submit', async () => {
    mockForgotPasswordApi.mockResolvedValue(undefined);
    render(<ForgotPasswordForm />);
    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: 'user@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: /send reset link/i }));
    await waitFor(() =>
      expect(screen.getByRole('status')).toBeInTheDocument()
    );
    expect(screen.getByText(/if this email is registered/i)).toBeInTheDocument();
  });

  it('success message is identical when API throws (anti-enumeration)', async () => {
    mockForgotPasswordApi.mockRejectedValue(new Error('Not found'));
    render(<ForgotPasswordForm />);
    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: 'nobody@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: /send reset link/i }));
    await waitFor(() =>
      expect(screen.getByText(/if this email is registered/i)).toBeInTheDocument()
    );
  });

  it('button is disabled during submit', async () => {
    let resolve: () => void;
    mockForgotPasswordApi.mockReturnValue(new Promise<void>((res) => { resolve = res; }));
    render(<ForgotPasswordForm />);
    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: 'user@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: /send reset link/i }));
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /sending/i })).toBeDisabled()
    );
    resolve!();
  });
});
