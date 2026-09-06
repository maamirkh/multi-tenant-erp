/**
 * T205 — Route-guard tests: the `(platform-auth)` / `(platform-admin)`
 * split actually holds at runtime, and tenant authentication can never
 * satisfy Platform route protection.
 *
 * Five cases (all required, plan.md §14):
 *   A — unauthenticated login page renders, zero redirects (no loop).
 *   B — unauthenticated protected route redirects to login, exactly once.
 *   C — authenticated Platform Administrator gets the protected shell.
 *   D — a valid tenant session does not count as Platform authentication.
 *   E — logout returns to a reachable, non-looping login.
 *
 * Isolation requirement: none of these cases may clear tenant tokens,
 * emit the tenant `session-expired` event, or touch
 * `erp_active_company_id`.
 */

import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

// --- next/navigation --------------------------------------------------
const mockReplace = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => '/platform-admin/dashboard',
}));

// --- Platform contexts --------------------------------------------------
const mockUsePlatformAuthContext = jest.fn();
jest.mock('@/contexts/PlatformAuthContext', () => ({
  PlatformAuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  usePlatformAuthContext: () => mockUsePlatformAuthContext(),
}));

jest.mock('@/contexts/PlatformSelectedTenantContext', () => ({
  PlatformSelectedTenantProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock('@/components/platform-admin/PlatformSidebar', () => ({
  __esModule: true,
  PlatformSidebar: () => <div data-testid="platform-sidebar" />,
  default: () => <div data-testid="platform-sidebar" />,
}));

// --- Tenant auth (to prove Platform ignores it entirely) -----------------
const mockUseAuthContext = jest.fn();
jest.mock('@/contexts/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuthContext: () => mockUseAuthContext(),
}));

const mockClearTokens = jest.fn();
const mockGetRefreshToken = jest.fn();
jest.mock('@/lib/auth/tokenStorage', () => ({
  clearTokens: () => mockClearTokens(),
  getAccessToken: () => 'tenant-access-token',
  getRefreshToken: () => mockGetRefreshToken(),
  storeTokens: jest.fn(),
}));

// --- Imports after mocks --------------------------------------------------
import PlatformAdminLayout from '../platform-admin/layout';
import PlatformLoginPage from '../../(platform-auth)/platform-admin/login/page';

const ACTIVE_COMPANY_KEY = 'erp_active_company_id';

describe('Platform route guard (T205)', () => {
  let dispatchSpy: jest.SpyInstance;

  beforeEach(() => {
    mockReplace.mockReset();
    mockUsePlatformAuthContext.mockReset();
    mockUseAuthContext.mockReset();
    mockClearTokens.mockReset();
    mockGetRefreshToken.mockReset();
    localStorage.clear();
    dispatchSpy = jest.spyOn(window, 'dispatchEvent');
  });

  afterEach(() => {
    dispatchSpy.mockRestore();
  });

  function assertTenantIsolationUntouched(): void {
    expect(mockClearTokens).not.toHaveBeenCalled();
    expect(localStorage.getItem(ACTIVE_COMPANY_KEY)).toBeNull();
    const tenantSessionExpiredCalls = dispatchSpy.mock.calls.filter(
      ([event]) => (event as Event).type === 'session-expired'
    );
    expect(tenantSessionExpiredCalls).toHaveLength(0);
  }

  it('case A — unauthenticated login page renders with zero redirects', () => {
    mockUsePlatformAuthContext.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      login: jest.fn(),
      logout: jest.fn(),
    });

    render(<PlatformLoginPage />);

    expect(screen.getByRole('heading', { name: /platform administration/i })).toBeInTheDocument();
    expect(mockReplace).not.toHaveBeenCalled();
    assertTenantIsolationUntouched();
  });

  it('case B — unauthenticated protected route redirects to login exactly once', async () => {
    mockUsePlatformAuthContext.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      login: jest.fn(),
      logout: jest.fn(),
    });

    render(
      <PlatformAdminLayout>
        <div data-testid="child" />
      </PlatformAdminLayout>
    );

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith('/platform-admin/login');
    });
    expect(mockReplace).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId('child')).not.toBeInTheDocument();
    assertTenantIsolationUntouched();
  });

  it('case C — authenticated Platform Administrator gets the protected shell, no redirect', () => {
    mockUsePlatformAuthContext.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      login: jest.fn(),
      logout: jest.fn(),
    });

    render(
      <PlatformAdminLayout>
        <div data-testid="child" />
      </PlatformAdminLayout>
    );

    expect(screen.getByTestId('child')).toBeInTheDocument();
    expect(screen.getByTestId('platform-sidebar')).toBeInTheDocument();
    expect(mockReplace).not.toHaveBeenCalled();
    assertTenantIsolationUntouched();
  });

  it('case D — a valid tenant session does not satisfy Platform route protection', async () => {
    // A genuinely authenticated tenant session exists in the same browser...
    mockUseAuthContext.mockReturnValue({ isAuthenticated: true, isLoading: false, user: { email: 'tenant@example.com' } });
    mockGetRefreshToken.mockReturnValue('tenant-refresh-token');
    // ...but no Platform session does. The layout only ever calls
    // usePlatformAuthContext() — it must still redirect.
    mockUsePlatformAuthContext.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      login: jest.fn(),
      logout: jest.fn(),
    });

    render(
      <PlatformAdminLayout>
        <div data-testid="child" />
      </PlatformAdminLayout>
    );

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith('/platform-admin/login');
    });
    expect(screen.queryByTestId('child')).not.toBeInTheDocument();
    assertTenantIsolationUntouched();
  });

  it('case E — logout redirects to login, which remains reachable and non-looping', async () => {
    const mockLogout = jest.fn().mockResolvedValue(undefined);
    mockUsePlatformAuthContext.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      login: jest.fn(),
      logout: mockLogout,
    });

    render(
      <PlatformAdminLayout>
        <div data-testid="child" />
      </PlatformAdminLayout>
    );

    fireEvent.click(screen.getByRole('button', { name: /log out/i }));

    await waitFor(() => {
      expect(mockLogout).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith('/platform-admin/login');
    });

    // The login page itself is then independently reachable/non-looping —
    // proven directly by case A's zero-redirect assertion for the same
    // unauthenticated-login scenario this logout leads into.
    assertTenantIsolationUntouched();
  });
});
