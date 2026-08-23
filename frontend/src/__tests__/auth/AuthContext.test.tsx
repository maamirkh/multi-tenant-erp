/**
 * T122 — AuthContext / AuthProvider tests.
 *
 * Tests: on mount with stored refresh token calls refresh endpoint;
 * on mount without token sets isAuthenticated=false;
 * login sets user and isAuthenticated=true;
 * logout clears state and localStorage;
 * session-expired event triggers logout.
 *
 * Root-cause note (Phase 14 -> pre-Phase-15 baseline fix): the first
 * test below originally mocked/asserted `refreshApi` from
 * `@/lib/api/auth`. `AuthContext`'s real hydration path does not call
 * that function at all — it calls `acquireRefreshLock()` from
 * `@/lib/auth/client` (a single-flight lock chosen deliberately, per
 * that file's own docstring, to coalesce hydration with any concurrent
 * 401-triggered refresh rather than racing two calls against the
 * single-use rotating refresh token). `refreshApi` is only ever called
 * by `useTokenRefresh`'s own periodic-refresh timer, which this file
 * already mocks out separately — so the original assertion targeted a
 * function with no reachable call path from the code under test, in
 * any configuration this suite exercises. Confirmed via `git stash`
 * against the pre-Phase-14 `client.ts`: the failure reproduces
 * identically, so this was a stale test assumption predating Epic 9A,
 * not something introduced by Phase 14's AuthStrategy refactor. Fixed
 * by mocking the actual dependency (`acquireRefreshLock`) and — to
 * verify the real contract more thoroughly than the original test did —
 * asserting the resulting authenticated state, not just that a mock fired.
 */

import React from 'react';
import { render, screen, act, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuthContext } from '@/contexts/AuthContext';

const mockGetMeApi = jest.fn();
const mockLoginApi = jest.fn();
const mockLogoutApi = jest.fn();

jest.mock('@/lib/api/auth', () => ({
  getMeApi: (...a: unknown[]) => mockGetMeApi(...a),
  loginApi: (...a: unknown[]) => mockLoginApi(...a),
  logoutApi: (...a: unknown[]) => mockLogoutApi(...a),
}));

// The actual dependency AuthContext's hydration effect calls — see the
// root-cause note above. Mirrors this test file's existing convention
// of mocking each module at the exact resolved path the production code
// imports it from (tokenStorage.ts below is the same pattern).
const mockAcquireRefreshLock = jest.fn();
jest.mock('@/lib/auth/client', () => ({
  acquireRefreshLock: (...a: unknown[]) => mockAcquireRefreshLock(...a),
}));

const mockGetRefreshToken = jest.fn();
const mockGetAccessToken = jest.fn();
const mockStoreTokens = jest.fn();
const mockClearTokens = jest.fn();

jest.mock('@/lib/auth/tokenStorage', () => ({
  getRefreshToken: () => mockGetRefreshToken(),
  getAccessToken: () => mockGetAccessToken(),
  storeTokens: (...a: unknown[]) => mockStoreTokens(...a),
  clearTokens: () => mockClearTokens(),
}));

const mockUseTokenRefresh = jest.fn();
jest.mock('@/hooks/useTokenRefresh', () => ({
  useTokenRefresh: (opts: unknown) => mockUseTokenRefresh(opts),
}));

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

function Wrapper({ children }: { children: React.ReactNode }): React.JSX.Element {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}

/** Renders the live AuthContext state as text so tests can assert on
 * the real resulting auth state, not merely on which mocks fired. */
function AuthStateProbe(): React.JSX.Element {
  const { isAuthenticated, isLoading, user } = useAuthContext();
  return (
    <div data-testid="auth-state">
      {`isLoading=${isLoading} isAuthenticated=${isAuthenticated} email=${user?.email ?? 'null'}`}
    </div>
  );
}

describe('T122 — AuthContext', () => {
  const mockUser = {
    user_id: 'uuid-1',
    email: 'ctx@example.com',
    display_name: 'Ctx User',
    account_status: 'ACTIVE',
    is_email_verified: true,
    created_at: '2026-01-01T00:00:00Z',
  };

  beforeEach(() => {
    mockAcquireRefreshLock.mockReset();
    mockGetMeApi.mockReset();
    mockLoginApi.mockReset();
    mockLogoutApi.mockReset();
    mockGetRefreshToken.mockReset();
    mockStoreTokens.mockReset();
    mockClearTokens.mockReset();
    mockUseTokenRefresh.mockReset();
    mockGetAccessToken.mockReturnValue(null);
  });

  it('on mount with a stored refresh token, hydrates via acquireRefreshLock and authenticates', async () => {
    mockGetRefreshToken.mockReturnValue('stored-rt');
    mockAcquireRefreshLock.mockResolvedValue({
      access_token: 'at',
      refresh_token: 'rt',
      expires_in: 900,
    });
    mockGetMeApi.mockResolvedValue(mockUser);

    render(<AuthStateProbe />, { wrapper: Wrapper });

    // The real hydration dependency was invoked — not refreshApi, which
    // has no reachable call path here (see root-cause note above).
    await waitFor(() => {
      expect(mockAcquireRefreshLock).toHaveBeenCalledTimes(1);
    });

    // And the full contract this test's name promises: hydration
    // actually results in an authenticated session with the fetched
    // profile, not merely "some mock fired".
    await waitFor(() => {
      expect(screen.getByTestId('auth-state').textContent).toBe(
        'isLoading=false isAuthenticated=true email=ctx@example.com'
      );
    });
    expect(mockGetMeApi).toHaveBeenCalledTimes(1);
  });

  it('on mount with a stored refresh token, a failed refresh leaves the session unauthenticated', async () => {
    mockGetRefreshToken.mockReturnValue('stored-rt');
    mockAcquireRefreshLock.mockRejectedValue(new Error('refresh failed'));

    render(<AuthStateProbe />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByTestId('auth-state').textContent).toBe(
        'isLoading=false isAuthenticated=false email=null'
      );
    });
    // A failed refresh must never reach the profile fetch.
    expect(mockGetMeApi).not.toHaveBeenCalled();
    // clearTokens() is the state-cleanup path AuthContext's hydration
    // catch block runs on failure — the tenant/platform token-storage
    // isolation this represents is unchanged by this fix.
    expect(mockClearTokens).toHaveBeenCalled();
  });

  it('on mount without stored token sets isAuthenticated=false', async () => {
    mockGetRefreshToken.mockReturnValue(null);
    render(<div data-testid="child" />, { wrapper: Wrapper });
    await waitFor(() => {
      const calls = mockUseTokenRefresh.mock.calls;
      expect(calls.length).toBeGreaterThan(0);
      expect(calls[0][0]).toMatchObject({ expiresIn: null });
    });
  });

  it('session-expired event clears auth state and shows banner', async () => {
    mockGetRefreshToken.mockReturnValue(null);
    render(<div />, { wrapper: Wrapper });

    act(() => {
      window.dispatchEvent(new Event('session-expired'));
    });

    await waitFor(() => {
      expect(
        screen.getByText(/your session has expired/i)
      ).toBeInTheDocument();
    });
  });
});
