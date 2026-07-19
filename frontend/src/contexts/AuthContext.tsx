'use client';

/**
 * AuthContext — single source of truth for authentication state.
 *
 * On mount, attempts to hydrate the session from a stored refresh token:
 *   1. Read refresh token from localStorage.
 *   2. If present, call POST /auth/refresh to obtain a new access token.
 *   3. Call GET /auth/me to load the user profile.
 *   4. On any failure: clear tokens, set isAuthenticated=false.
 *
 * Exposes AuthContextValue (user, isAuthenticated, isLoading, login, logout).
 *
 * T084A: All authentication mutations use retry: false to prevent unintended
 * repeated authentication requests (TanStack Query default for mutations is
 * already 0 retries, but this is made explicit here for clarity).
 *
 * T090: useTokenRefresh is wired here and started after successful session
 * hydration or login. The timer is automatically cleared when expiresIn
 * is set to null (on logout or session expiry).
 *
 * T091: A session-expired banner is rendered inside AuthProvider when the
 * `session-expired` custom event is dispatched by the API client interceptor.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { getMeApi, loginApi, logoutApi, refreshApi } from '@/lib/api/auth';
import { clearTokens, getRefreshToken, storeTokens } from '@/lib/auth/tokenStorage';
import { useTokenRefresh } from '@/hooks/useTokenRefresh';
import type { AuthContextValue, UserProfileResponse } from '@/types/auth';

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }): React.JSX.Element {
  const queryClient = useQueryClient();

  const [user, setUser] = useState<UserProfileResponse | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [expiresIn, setExpiresIn] = useState<number | null>(null);
  /** T091: visible when the API client dispatches the `session-expired` event. */
  const [sessionExpiredVisible, setSessionExpiredVisible] = useState(false);

  // --- Session hydration on mount ------------------------------------------

  useEffect(() => {
    let cancelled = false;

    async function hydrate(): Promise<void> {
      const storedRefreshToken = getRefreshToken();
      if (!storedRefreshToken) {
        setIsLoading(false);
        return;
      }

      try {
        // T084A: no retry — mutation-style call, explicit single attempt.
        const refreshResult = await refreshApi(storedRefreshToken);
        if (cancelled) return;

        storeTokens(refreshResult.access_token, refreshResult.refresh_token);
        setExpiresIn(refreshResult.expires_in);

        const profile = await getMeApi();
        if (cancelled) return;

        setUser(profile);
        setIsAuthenticated(true);
      } catch {
        if (!cancelled) {
          clearTokens();
          setUser(null);
          setIsAuthenticated(false);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void hydrate();

    return () => {
      cancelled = true;
    };
  }, []);

  // --- session-expired event (dispatched by API client on refresh failure) ---
  // T091: Clear state and show the session-expired notification banner.

  useEffect(() => {
    function handleSessionExpired(): void {
      clearTokens();
      setUser(null);
      setIsAuthenticated(false);
      setExpiresIn(null);
      queryClient.clear();
      setSessionExpiredVisible(true);
    }

    window.addEventListener('session-expired', handleSessionExpired);
    return () => window.removeEventListener('session-expired', handleSessionExpired);
  }, [queryClient]);

  // --- Login ---------------------------------------------------------------

  const login = useCallback(
    async (email: string, password: string, rememberMe: boolean): Promise<void> => {
      // T084A: no retry — single attempt, errors propagate to the form.
      const loginResult = await loginApi(email, password, rememberMe);
      storeTokens(loginResult.access_token, loginResult.refresh_token);
      setExpiresIn(loginResult.expires_in);

      const profile = await getMeApi();
      setUser(profile);
      setIsAuthenticated(true);
    },
    []
  );

  // --- Logout --------------------------------------------------------------

  const logout = useCallback(async (): Promise<void> => {
    try {
      // T084A: no retry — single attempt; ignore server errors on logout.
      await logoutApi();
    } catch {
      // Best-effort — always clear local state even if the server call fails.
    } finally {
      clearTokens();
      setUser(null);
      setIsAuthenticated(false);
      // Setting expiresIn to null stops the useTokenRefresh timer (T090).
      setExpiresIn(null);
      // T089A: clear TanStack Query cache to prevent authenticated data leaking
      // across user sessions.
      queryClient.clear();
    }
  }, [queryClient]);

  // --- T090: Auto-refresh timer --------------------------------------------
  // Wired after successful hydration/login via expiresIn state.
  // Timer starts when expiresIn > 0 and clears automatically when expiresIn
  // is reset to null (on logout or session expiry — no memory leak).

  useTokenRefresh({
    expiresIn,
    onLogout: logout,
  });

  // --- Context value -------------------------------------------------------

  const value = useMemo<AuthContextValue>(
    () => ({ user, isAuthenticated, isLoading, login, logout }),
    [user, isAuthenticated, isLoading, login, logout]
  );

  // --- T091: Session-expired notification banner ---------------------------

  return (
    <AuthContext.Provider value={value}>
      {sessionExpiredVisible && (
        <div
          role="alert"
          aria-live="assertive"
          className="fixed inset-x-0 top-0 z-50 flex items-center justify-between bg-destructive px-4 py-3 text-sm text-destructive-foreground shadow-md"
        >
          <span>Your session has expired. Please log in again.</span>
          <button
            type="button"
            aria-label="Dismiss"
            onClick={() => setSessionExpiredVisible(false)}
            className="ml-4 rounded px-2 py-0.5 hover:bg-black/10"
          >
            ✕
          </button>
        </div>
      )}
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Internal hook — used only by `useAuth` consumer hook.
 * Throws if called outside an `<AuthProvider>`.
 */
export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error('useAuthContext must be used within an <AuthProvider>');
  }
  return ctx;
}
