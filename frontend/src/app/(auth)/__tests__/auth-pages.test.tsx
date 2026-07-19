/**
 * Phase 12 tests for (auth) route group pages.
 *
 * T094 — AuthLayout renders children in a centered wrapper.
 * T095 — LoginPage renders LoginForm and forgot-password link; redirects if authenticated.
 * T096 — ForgotPasswordPage renders ForgotPasswordForm and back-to-sign-in link.
 * T097 — ResetPasswordPage renders ResetPasswordForm inside Suspense.
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

// --- Mock next/navigation ------------------------------------------------
const mockPush = jest.fn();
const mockReplace = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
  useSearchParams: () => new URLSearchParams('token=test-token'),
}));

// --- Mock AuthContext to control auth state ------------------------------
const mockUseAuthContext = jest.fn();
jest.mock('@/contexts/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuthContext: () => mockUseAuthContext(),
}));

// --- Mock QueryClientProvider (no-op wrapper) ----------------------------
jest.mock('@tanstack/react-query', () => ({
  QueryClient: jest.fn().mockImplementation(() => ({})),
  QueryClientProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useQuery: jest.fn().mockReturnValue({ data: null, isLoading: false, isError: false }),
}));

// --- Mock form components ------------------------------------------------
jest.mock('@/components/auth/LoginForm', () => ({
  LoginForm: () => <div data-testid="login-form" />,
}));
jest.mock('@/components/auth/ForgotPasswordForm', () => ({
  ForgotPasswordForm: () => <div data-testid="forgot-password-form" />,
}));
jest.mock('@/components/auth/ResetPasswordForm', () => ({
  ResetPasswordForm: () => <div data-testid="reset-password-form" />,
}));

// --- Import pages after mocks --------------------------------------------
import AuthLayout from '../layout';
import LoginPage from '../login/page';
import ForgotPasswordPage from '../forgot-password/page';
import ResetPasswordPage from '../reset-password/page';

// -------------------------------------------------------------------------

describe('AuthLayout (T094)', () => {
  it('renders children inside a centered wrapper', () => {
    render(
      <AuthLayout>
        <div data-testid="child" />
      </AuthLayout>
    );
    expect(screen.getByTestId('child')).toBeInTheDocument();
    // Verify centered layout class is applied.
    const wrapper = screen.getByTestId('child').parentElement;
    expect(wrapper?.className).toMatch(/flex/);
    expect(wrapper?.className).toMatch(/min-h-screen/);
  });
});

describe('LoginPage (T095)', () => {
  beforeEach(() => {
    mockReplace.mockReset();
    mockUseAuthContext.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
    });
  });

  it('renders LoginForm and forgot-password link', () => {
    render(<LoginPage />);
    expect(screen.getByTestId('login-form')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /forgot your password/i })).toBeInTheDocument();
  });

  it('forgot-password link points to /forgot-password', () => {
    render(<LoginPage />);
    const link = screen.getByRole('link', { name: /forgot your password/i });
    expect(link).toHaveAttribute('href', '/forgot-password');
  });

  it('redirects to /dashboard when already authenticated', async () => {
    mockUseAuthContext.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
    });
    render(<LoginPage />);
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith('/dashboard');
    });
  });

  it('does not redirect while isLoading', () => {
    mockUseAuthContext.mockReturnValue({
      isAuthenticated: false,
      isLoading: true,
    });
    render(<LoginPage />);
    expect(mockReplace).not.toHaveBeenCalled();
  });
});

describe('ForgotPasswordPage (T096)', () => {
  it('renders ForgotPasswordForm and back-to-sign-in link', () => {
    render(<ForgotPasswordPage />);
    expect(screen.getByTestId('forgot-password-form')).toBeInTheDocument();
    const link = screen.getByRole('link', { name: /back to sign in/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/login');
  });
});

describe('ResetPasswordPage (T097)', () => {
  it('renders ResetPasswordForm inside a Suspense boundary', async () => {
    render(<ResetPasswordPage />);
    await waitFor(() => {
      expect(screen.getByTestId('reset-password-form')).toBeInTheDocument();
    });
  });
});
