'use client';

/**
 * PlatformAuthContext — Platform Administrator authentication state
 * (T185, ADR-11).
 *
 * Structurally separate from `AuthContext` (tenant): its own login/
 * logout/refresh/session-expiry state, its own token storage
 * (`lib/platform-auth/platformTokenStorage.ts`), its own single-flight
 * refresh lock (`acquirePlatformRefreshLock`), and its own session-expiry
 * event (`platform-session-expired`, never the tenant `session-expired`).
 * `PlatformAuthProvider` is never nested inside `<AuthProvider>` and
 * never reads `AuthContext`'s state.
 *
 * There is no `GET /platform/auth/me` endpoint in the finalized contract
 * (only login/refresh/logout are public Platform auth operations) —
 * this context therefore tracks authentication *status* only, not a
 * fetched administrator profile.
 *
 * **Deactivated-administrator handling**: the backend returns the same
 * generic 401 for invalid credentials and for "no active
 * PlatformAdministrator" at login time (deliberately, to avoid
 * information disclosure) — `login()` simply propagates that error to
 * the caller, same as `AuthContext.login()` does for its own generic
 * 401. For an administrator deactivated *after* a session already
 * exists, deactivation revokes their `PlatformSession` server-side
 * (Phase 5) — the next refresh attempt fails and is handled by the
 * exact same `platform-session-expired` pathway as any other expired
 * session, with no special-casing needed.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { platformApiClient } from '@/lib/api/platform';
import { acquirePlatformRefreshLock } from '@/lib/platform-auth/platformAuthClient';
import {
  clearPlatformTokens,
  getPlatformRefreshToken,
  storePlatformTokens,
} from '@/lib/platform-auth/platformTokenStorage';

interface PlatformLoginResult {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

/** POST /api/v1/platform/auth/login */
async function platformLoginApi(email: string, password: string): Promise<PlatformLoginResult> {
  const res = await platformApiClient.post<PlatformLoginResult>('/api/v1/platform/auth/login', {
    email,
    password,
  });
  return res.data;
}

/** POST /api/v1/platform/auth/logout */
async function platformLogoutApi(): Promise<void> {
  await platformApiClient.post<Record<string, string>>('/api/v1/platform/auth/logout', {});
}

export interface PlatformAuthContextValue {
  isAuthenticated: boolean;
  /** True while the initial session is being hydrated on mount. */
  isLoading: boolean;
  /** Authenticate, store Platform tokens. Throws on failure (invalid
   * credentials or no active PlatformAdministrator — same generic 401). */
  login: (email: string, password: string) => Promise<void>;
  /** Revoke the Platform session server-side, clear local state. */
  logout: () => Promise<void>;
}

const PlatformAuthContext = createContext<PlatformAuthContextValue | null>(null);

export function PlatformAuthProvider({
  children,
}: {
  children: React.ReactNode;
}): React.JSX.Element {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // --- Session hydration on mount ------------------------------------------
  const hydrateStartedRef = useRef(false);

  useEffect(() => {
    // hydrateStartedRef (not a per-invocation `cancelled` closure flag)
    // is the only guard here, and deliberately so: React Strict Mode's
    // dev-only synchronous mount->cleanup->remount double-invocation
    // reuses this same ref, so the guard below ensures hydrate() (and
    // therefore acquirePlatformRefreshLock()) runs at most once per real
    // component lifetime — never twice, which matters because the
    // refresh token is single-use/rotating. A `cancelled` flag set by
    // that synthetic first-invocation's cleanup would incorrectly
    // poison the one-and-only in-flight hydrate() call's eventual state
    // updates (setIsAuthenticated/setIsLoading), permanently stranding
    // the component actually left mounted on its initial isLoading=true
    // — this was a real, reproduced bug (T219 E2E), not a hypothetical.
    // React 18+ already no-ops setState calls after a genuine unmount,
    // so no extra guard is needed for that case either.
    if (hydrateStartedRef.current) return;
    hydrateStartedRef.current = true;

    async function hydrate(): Promise<void> {
      const storedRefreshToken = getPlatformRefreshToken();
      if (!storedRefreshToken) {
        setIsLoading(false);
        return;
      }

      try {
        // Routed through acquirePlatformRefreshLock() (the same
        // single-flight lock the Platform API client's 401-retry
        // interceptor uses) — mirrors AuthContext's own hydration
        // rationale exactly: coalesces hydration onto any concurrent
        // refresh triggered by a data-fetch hitting a 401 in the same
        // window, rather than racing two independent refresh calls
        // against a single-use rotating refresh token.
        await acquirePlatformRefreshLock();
        setIsAuthenticated(true);
      } catch {
        clearPlatformTokens();
        setIsAuthenticated(false);
      } finally {
        setIsLoading(false);
      }
    }

    void hydrate();
  }, []);

  // --- platform-session-expired event (never the tenant session-expired) ---

  useEffect(() => {
    function handlePlatformSessionExpired(): void {
      clearPlatformTokens();
      setIsAuthenticated(false);
    }

    window.addEventListener('platform-session-expired', handlePlatformSessionExpired);
    return () =>
      window.removeEventListener('platform-session-expired', handlePlatformSessionExpired);
  }, []);

  // --- Login ---------------------------------------------------------------

  const login = useCallback(async (email: string, password: string): Promise<void> => {
    const result = await platformLoginApi(email, password);
    storePlatformTokens(result.access_token, result.refresh_token);
    setIsAuthenticated(true);
  }, []);

  // --- Logout --------------------------------------------------------------

  const logout = useCallback(async (): Promise<void> => {
    try {
      await platformLogoutApi();
    } catch {
      // Best-effort — always clear local state even if the server call fails.
    } finally {
      clearPlatformTokens();
      setIsAuthenticated(false);
    }
  }, []);

  // --- Context value -------------------------------------------------------

  const value = useMemo<PlatformAuthContextValue>(
    () => ({ isAuthenticated, isLoading, login, logout }),
    [isAuthenticated, isLoading, login, logout]
  );

  return (
    <PlatformAuthContext.Provider value={value}>{children}</PlatformAuthContext.Provider>
  );
}

/**
 * Internal hook — used only by Platform pages/components.
 * Throws if called outside a `<PlatformAuthProvider>`.
 */
export function usePlatformAuthContext(): PlatformAuthContextValue {
  const ctx = useContext(PlatformAuthContext);
  if (ctx === null) {
    throw new Error('usePlatformAuthContext must be used within a <PlatformAuthProvider>');
  }
  return ctx;
}
