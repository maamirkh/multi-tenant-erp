'use client';

/**
 * useAuth — public authentication hook.
 *
 * Wraps `useAuthContext` and exposes a stable, typed interface for components.
 * Throws a descriptive error if used outside `<AuthProvider>`.
 *
 * Usage:
 *   const { user, isAuthenticated, isLoading, login, logout } = useAuth();
 */

import { useRouter } from 'next/navigation';
import { useCallback } from 'react';
import { useAuthContext } from '@/contexts/AuthContext';
import type { UserProfileResponse } from '@/types/auth';

export interface UseAuthReturn {
  user: UserProfileResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  /** Authenticate and navigate to /dashboard on success. Throws on error. */
  login: (email: string, password: string, rememberMe: boolean) => Promise<void>;
  /** Revoke current session server-side, clear local state, navigate to /login. */
  logout: () => Promise<void>;
  /**
   * T093 — Revoke ALL sessions for this user across every device.
   *
   * The backend's POST /auth/logout already calls `revoke_all_by_user()`,
   * which revokes all active refresh tokens server-side (spec.md §7.2 FR-012).
   * This action clears local tokens and redirects to /login.
   */
  logoutAllDevices: () => Promise<void>;
}

export function useAuth(): UseAuthReturn {
  const ctx = useAuthContext();
  const router = useRouter();

  const login = useCallback(
    async (email: string, password: string, rememberMe: boolean): Promise<void> => {
      await ctx.login(email, password, rememberMe);
      router.push('/dashboard');
    },
    [ctx, router]
  );

  const logout = useCallback(async (): Promise<void> => {
    await ctx.logout();
    router.push('/login');
  }, [ctx, router]);

  // T093: logoutAllDevices — same server call as logout; the backend revokes
  // all active sessions for the user (not just the current one).
  const logoutAllDevices = useCallback(async (): Promise<void> => {
    await ctx.logout();
    router.push('/login');
  }, [ctx, router]);

  return {
    user: ctx.user,
    isAuthenticated: ctx.isAuthenticated,
    isLoading: ctx.isLoading,
    login,
    logout,
    logoutAllDevices,
  };
}
