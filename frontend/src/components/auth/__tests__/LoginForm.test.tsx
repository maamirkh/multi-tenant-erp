/**
 * Unit tests for LoginForm component.
 *
 * Phase 10 Checkpoint:
 *   ✓ LoginForm renders without errors.
 *   ✓ Submitting with empty fields shows Zod validation errors without API call.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LoginForm } from '../LoginForm';

// Mock useAuth so the form renders without a real AuthProvider.
const mockLogin = jest.fn();
jest.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({
    user: null,
    isAuthenticated: false,
    isLoading: false,
    login: mockLogin,
    logout: jest.fn(),
  }),
}));

// Mock next/navigation to avoid the router dependency in tests.
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

describe('LoginForm', () => {
  beforeEach(() => {
    mockLogin.mockReset();
  });

  it('renders without throwing', () => {
    expect(() => render(<LoginForm />)).not.toThrow();
  });

  it('renders email and password fields and the submit button', () => {
    render(<LoginForm />);
    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('shows email validation error when submitting with empty email — no API call', async () => {
    render(<LoginForm />);

    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/please enter a valid email address/i)).toBeInTheDocument();
    });

    // The login API must NOT have been called.
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('shows password validation error when submitting with empty password — no API call', async () => {
    render(<LoginForm />);

    // Provide a valid email but leave password empty.
    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: 'user@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/password is required/i)).toBeInTheDocument();
    });

    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('calls login with correct arguments on valid submission', async () => {
    mockLogin.mockResolvedValue(undefined);
    render(<LoginForm />);

    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: 'user@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: 'S3cur3P@ssword!' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => expect(mockLogin).toHaveBeenCalledTimes(1));
    expect(mockLogin).toHaveBeenCalledWith('user@example.com', 'S3cur3P@ssword!', false);
  });

  it('shows "Invalid email or password" on 401 error', async () => {
    const { ApiClientError } = jest.requireActual<typeof import('@/lib/api/client')>(
      '@/lib/api/client'
    );
    mockLogin.mockRejectedValue(
      new ApiClientError(401, {
        error: { code: 'AUTHENTICATION_ERROR', message: 'Bad credentials.', details: {} },
      })
    );

    render(<LoginForm />);

    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: 'user@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: 'wrongpass' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument();
    });
  });

  it('shows rate-limit message on 429 error', async () => {
    const { ApiClientError } = jest.requireActual<typeof import('@/lib/api/client')>(
      '@/lib/api/client'
    );
    mockLogin.mockRejectedValue(
      new ApiClientError(429, {
        error: { code: 'RATE_LIMIT_EXCEEDED', message: 'Too many requests.', details: {} },
      })
    );

    render(<LoginForm />);

    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: 'user@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: 'somepass' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/too many attempts/i)).toBeInTheDocument();
    });
  });
});
