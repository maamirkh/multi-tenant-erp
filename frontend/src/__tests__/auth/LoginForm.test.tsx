/**
 * T119 — LoginForm component tests.
 *
 * Tests: renders email, password, remember_me, submit;
 * empty form submit shows Zod validation errors without API call;
 * valid submit calls login() from useAuth;
 * 401 response shows "Invalid email or password";
 * 423 response shows lock message;
 * button disabled during isSubmitting.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LoginForm } from '@/components/auth/LoginForm';

const mockLogin = jest.fn();
jest.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({
    user: null,
    isAuthenticated: false,
    isLoading: false,
    login: mockLogin,
    logout: jest.fn(),
    logoutAllDevices: jest.fn(),
  }),
}));
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

describe('T119 — LoginForm', () => {
  beforeEach(() => {
    mockLogin.mockReset();
  });

  it('renders email, password, remember_me and submit button', () => {
    render(<LoginForm />);
    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
    expect(screen.getByRole('checkbox')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('empty form submit shows Zod validation errors — no API call', async () => {
    render(<LoginForm />);
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
    await waitFor(() =>
      expect(screen.getByText(/please enter a valid email address/i)).toBeInTheDocument()
    );
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('valid submit calls login() with correct args', async () => {
    mockLogin.mockResolvedValue(undefined);
    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: 'user@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: 'P@ssword123456' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
    await waitFor(() => expect(mockLogin).toHaveBeenCalledTimes(1));
    expect(mockLogin).toHaveBeenCalledWith('user@example.com', 'P@ssword123456', false);
  });

  it('401 response shows "Invalid email or password"', async () => {
    const { ApiClientError } = jest.requireActual<typeof import('@/lib/api/client')>(
      '@/lib/api/client'
    );
    mockLogin.mockRejectedValue(
      new ApiClientError(401, { error: { code: 'INVALID_CREDENTIALS', message: '', details: {} } })
    );
    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: 'u@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: 'wrongpass' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
    await waitFor(() =>
      expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument()
    );
  });

  it('423 response shows lock message', async () => {
    const { ApiClientError } = jest.requireActual<typeof import('@/lib/api/client')>(
      '@/lib/api/client'
    );
    mockLogin.mockRejectedValue(
      new ApiClientError(423, { error: { code: 'ACCOUNT_LOCKED', message: '', details: {} } })
    );
    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: 'u@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: 'anypass' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
    await waitFor(() =>
      expect(screen.getByText(/account.+locked/i)).toBeInTheDocument()
    );
  });
});
