/**
 * Unit tests for AuthContext / AuthProvider.
 *
 * T090 — timer is NOT started without a valid session (no localStorage refresh token).
 * T091 — session-expired banner appears when `session-expired` event fires.
 */

import React from 'react';
import { render, screen, act, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '../AuthContext';

// Mock API functions — no real network calls.
jest.mock('@/lib/api/auth', () => ({
  refreshApi: jest.fn().mockRejectedValue(new Error('no token')),
  getMeApi: jest.fn().mockResolvedValue(null),
  loginApi: jest.fn(),
  logoutApi: jest.fn().mockResolvedValue(undefined),
}));

// Mock tokenStorage — no tokens stored initially.
jest.mock('@/lib/auth/tokenStorage', () => ({
  getRefreshToken: jest.fn().mockReturnValue(null),
  getAccessToken: jest.fn().mockReturnValue(null),
  storeTokens: jest.fn(),
  clearTokens: jest.fn(),
}));

// Mock useTokenRefresh — track calls and options.
const mockUseTokenRefresh = jest.fn();
jest.mock('@/hooks/useTokenRefresh', () => ({
  useTokenRefresh: (opts: { expiresIn: number | null; onLogout: () => void }) => {
    mockUseTokenRefresh(opts);
  },
}));

// Mock next/navigation.
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

function wrapper({ children }: { children: React.ReactNode }): React.JSX.Element {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}

describe('AuthProvider', () => {
  beforeEach(() => {
    mockUseTokenRefresh.mockClear();
  });

  it('renders children without crashing', async () => {
    render(<div data-testid="child" />, { wrapper });
    expect(screen.getByTestId('child')).toBeInTheDocument();
  });

  it('T090 — calls useTokenRefresh with expiresIn=null when no session exists', async () => {
    render(<div />, { wrapper });
    await waitFor(() => {
      // useTokenRefresh should have been called at least once with expiresIn=null
      // (no refresh token → no session → timer does not start).
      const calls = mockUseTokenRefresh.mock.calls;
      expect(calls.length).toBeGreaterThan(0);
      expect(calls[0][0]).toMatchObject({ expiresIn: null });
    });
  });

  it('T091 — shows session-expired banner when session-expired event fires', async () => {
    render(<div />, { wrapper });

    // Dispatch the session-expired custom event (as the API client would).
    act(() => {
      window.dispatchEvent(new Event('session-expired'));
    });

    await waitFor(() => {
      expect(
        screen.getByText(/your session has expired\. please log in again\./i)
      ).toBeInTheDocument();
    });
  });

  it('T091 — session-expired banner can be dismissed', async () => {
    render(<div />, { wrapper });

    act(() => {
      window.dispatchEvent(new Event('session-expired'));
    });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    const dismiss = screen.getByRole('button', { name: /dismiss/i });
    act(() => {
      dismiss.click();
    });

    await waitFor(() => {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  });
});
