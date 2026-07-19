/**
 * Phase 12 tests for (protected) route group.
 *
 * T098 — ProtectedLayout shows spinner while loading; redirects to /login
 *        when unauthenticated; renders AppLayout + children when authenticated.
 * T099 — DashboardPage calls getMeApi and renders user data.
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

// --- Mock next/navigation ------------------------------------------------
const mockReplace = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace }),
}));

// --- Mock AuthContext -----------------------------------------------------
const mockUseAuthContext = jest.fn();
jest.mock('@/contexts/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuthContext: () => mockUseAuthContext(),
}));

// --- Mock QueryClientProvider / useQuery ---------------------------------
const mockUseQuery = jest.fn();
jest.mock('@tanstack/react-query', () => ({
  QueryClient: jest.fn().mockImplementation(() => ({})),
  QueryClientProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useQuery: (...args: unknown[]) => mockUseQuery(...args),
}));

// --- Mock AppLayout ------------------------------------------------------
jest.mock('@/components/layout/AppLayout', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="app-layout">{children}</div>
  ),
}));

// --- Import pages after mocks --------------------------------------------
import ProtectedLayout from '../layout';
import DashboardPage from '../dashboard/page';

// -------------------------------------------------------------------------

describe('ProtectedLayout (T098)', () => {
  beforeEach(() => {
    mockReplace.mockReset();
  });

  it('shows loading spinner while hydrating', () => {
    mockUseAuthContext.mockReturnValue({ isAuthenticated: false, isLoading: true });
    render(
      <ProtectedLayout>
        <div data-testid="child" />
      </ProtectedLayout>
    );
    expect(screen.getByRole('status', { name: /loading/i })).toBeInTheDocument();
    expect(screen.queryByTestId('child')).not.toBeInTheDocument();
  });

  it('redirects to /login when unauthenticated after hydration', async () => {
    mockUseAuthContext.mockReturnValue({ isAuthenticated: false, isLoading: false });
    render(
      <ProtectedLayout>
        <div data-testid="child" />
      </ProtectedLayout>
    );
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith('/login');
    });
    expect(screen.queryByTestId('child')).not.toBeInTheDocument();
  });

  it('renders AppLayout with children when authenticated', () => {
    mockUseAuthContext.mockReturnValue({ isAuthenticated: true, isLoading: false });
    render(
      <ProtectedLayout>
        <div data-testid="child" />
      </ProtectedLayout>
    );
    expect(screen.getByTestId('app-layout')).toBeInTheDocument();
    expect(screen.getByTestId('child')).toBeInTheDocument();
  });
});

describe('DashboardPage (T099)', () => {
  const mockUser = {
    user_id: 'uuid-123',
    email: 'alice@example.com',
    display_name: 'Alice Smith',
    account_status: 'ACTIVE',
    is_email_verified: true,
    created_at: '2026-01-01T00:00:00Z',
  };

  it('shows loading spinner while fetching', () => {
    mockUseQuery.mockReturnValue({ data: undefined, isLoading: true, isError: false });
    render(<DashboardPage />);
    expect(screen.getByRole('status', { name: /loading/i })).toBeInTheDocument();
  });

  it('shows error message on query failure', () => {
    mockUseQuery.mockReturnValue({ data: undefined, isLoading: false, isError: true });
    render(<DashboardPage />);
    expect(screen.getByText(/failed to load user profile/i)).toBeInTheDocument();
  });

  it('renders display_name and email from /me response', () => {
    mockUseQuery.mockReturnValue({ data: mockUser, isLoading: false, isError: false });
    render(<DashboardPage />);
    expect(screen.getByText('Alice Smith')).toBeInTheDocument();
    expect(screen.getByText('alice@example.com')).toBeInTheDocument();
  });

  it('calls getMeApi via useQuery with key ["me"]', () => {
    mockUseQuery.mockReturnValue({ data: mockUser, isLoading: false, isError: false });
    render(<DashboardPage />);
    expect(mockUseQuery).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['me'] })
    );
  });
});
