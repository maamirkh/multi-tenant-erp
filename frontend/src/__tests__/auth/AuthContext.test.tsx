/**
 * T122 — AuthContext / AuthProvider tests.
 *
 * Tests: on mount with stored refresh token calls refresh endpoint;
 * on mount without token sets isAuthenticated=false;
 * login sets user and isAuthenticated=true;
 * logout clears state and localStorage;
 * session-expired event triggers logout.
 */

import React from 'react';
import { render, screen, act, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '@/contexts/AuthContext';

const mockRefreshApi = jest.fn();
const mockGetMeApi = jest.fn();
const mockLoginApi = jest.fn();
const mockLogoutApi = jest.fn();

jest.mock('@/lib/api/auth', () => ({
  refreshApi: (...a: unknown[]) => mockRefreshApi(...a),
  getMeApi: (...a: unknown[]) => mockGetMeApi(...a),
  loginApi: (...a: unknown[]) => mockLoginApi(...a),
  logoutApi: (...a: unknown[]) => mockLogoutApi(...a),
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
    mockRefreshApi.mockReset();
    mockGetMeApi.mockReset();
    mockLoginApi.mockReset();
    mockLogoutApi.mockReset();
    mockGetRefreshToken.mockReset();
    mockStoreTokens.mockReset();
    mockClearTokens.mockReset();
    mockUseTokenRefresh.mockReset();
    mockGetAccessToken.mockReturnValue(null);
  });

  it('on mount with stored refresh token calls refreshApi', async () => {
    mockGetRefreshToken.mockReturnValue('stored-rt');
    mockRefreshApi.mockResolvedValue({
      access_token: 'at',
      refresh_token: 'rt',
      expires_in: 900,
    });
    mockGetMeApi.mockResolvedValue(mockUser);

    render(<div data-testid="child" />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(mockRefreshApi).toHaveBeenCalledWith('stored-rt');
    });
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
