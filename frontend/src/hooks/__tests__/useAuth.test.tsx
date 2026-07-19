/**
 * Unit tests for useAuth hook.
 *
 * T093 — verify logoutAllDevices clears state and navigates to /login.
 * T090 — verify timer is not started without an active session (covered via
 *         the expiresIn=null path already tested in tokenStorage tests).
 */

import { render } from '@testing-library/react';
import React from 'react';

// Mock dependencies before imports.
const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

const mockCtxLogout = jest.fn();
const mockCtxLogin = jest.fn();

jest.mock('@/contexts/AuthContext', () => ({
  useAuthContext: () => ({
    user: null,
    isAuthenticated: false,
    isLoading: false,
    login: mockCtxLogin,
    logout: mockCtxLogout,
  }),
}));

import { useAuth } from '../useAuth';

/** Minimal wrapper to call a hook and expose its return value. */
function HookHarness({
  onMount,
}: {
  onMount: (result: ReturnType<typeof useAuth>) => void;
}): React.JSX.Element {
  const auth = useAuth();
  React.useEffect(() => {
    onMount(auth);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return <div />;
}

describe('useAuth', () => {
  beforeEach(() => {
    mockPush.mockReset();
    mockCtxLogout.mockReset().mockResolvedValue(undefined);
    mockCtxLogin.mockReset().mockResolvedValue(undefined);
  });

  it('exposes user, isAuthenticated, isLoading, login, logout, logoutAllDevices', () => {
    let result!: ReturnType<typeof useAuth>;
    render(<HookHarness onMount={(r) => { result = r; }} />);
    expect(result.user).toBeNull();
    expect(result.isAuthenticated).toBe(false);
    expect(result.isLoading).toBe(false);
    expect(typeof result.login).toBe('function');
    expect(typeof result.logout).toBe('function');
    expect(typeof result.logoutAllDevices).toBe('function');
  });

  it('logout calls ctx.logout and navigates to /login', async () => {
    let result!: ReturnType<typeof useAuth>;
    render(<HookHarness onMount={(r) => { result = r; }} />);
    await result.logout();
    expect(mockCtxLogout).toHaveBeenCalledTimes(1);
    expect(mockPush).toHaveBeenCalledWith('/login');
  });

  it('T093 — logoutAllDevices calls ctx.logout and navigates to /login', async () => {
    let result!: ReturnType<typeof useAuth>;
    render(<HookHarness onMount={(r) => { result = r; }} />);
    await result.logoutAllDevices();
    expect(mockCtxLogout).toHaveBeenCalledTimes(1);
    expect(mockPush).toHaveBeenCalledWith('/login');
  });

  it('login calls ctx.login with correct args and navigates to /dashboard', async () => {
    let result!: ReturnType<typeof useAuth>;
    render(<HookHarness onMount={(r) => { result = r; }} />);
    await result.login('a@b.com', 'pass', true);
    expect(mockCtxLogin).toHaveBeenCalledWith('a@b.com', 'pass', true);
    expect(mockPush).toHaveBeenCalledWith('/dashboard');
  });
});
