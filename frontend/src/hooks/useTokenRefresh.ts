'use client';

/**
 * useTokenRefresh — automatic access token refresh timer.
 *
 * Called once inside the AuthContext provider after a successful login or
 * session hydration. Schedules a refresh at 80% of the token lifetime (e.g.
 * 12 minutes for a 15-minute access token). On each successful refresh the
 * timer reschedules itself. On failure, logout() is called and the user is
 * redirected to /login.
 *
 * The timer is cleared automatically on unmount (or when logout() is called,
 * which causes re-render with expiresIn=null).
 */

import { useCallback, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { refreshApi } from '@/lib/api/auth';
import { getRefreshToken, storeTokens } from '@/lib/auth/tokenStorage';

interface UseTokenRefreshOptions {
  /** Access token lifetime in seconds from the last login/refresh response. */
  expiresIn: number | null;
  /** Called when refresh fails — should clear auth state. */
  onLogout: () => void;
}

export function useTokenRefresh({ expiresIn, onLogout }: UseTokenRefreshOptions): void {
  const router = useRouter();
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onLogoutRef = useRef(onLogout);
  // Ref for the schedule function to allow safe recursive rescheduling
  // without creating a circular dependency on the useCallback.
  const scheduleRefreshRef = useRef<((s: number) => void) | null>(null);

  // Keep callback refs in sync after each render (not during render, to satisfy
  // the react-compiler rule that forbids ref mutation in the render phase).
  useEffect(() => {
    onLogoutRef.current = onLogout;
  });

  const scheduleRefresh = useCallback(
    (lifetimeSeconds: number) => {
      // Fire at 80% of the token lifetime.
      const delayMs = Math.max(lifetimeSeconds * 0.8 * 1000, 30_000);

      timerRef.current = setTimeout(async () => {
        const refreshToken = getRefreshToken();
        if (!refreshToken) {
          onLogoutRef.current();
          router.push('/login');
          return;
        }

        try {
          const result = await refreshApi(refreshToken);
          storeTokens(result.access_token, result.refresh_token);
          // Reschedule using the new token's lifetime via ref to avoid
          // referencing scheduleRefresh before its const binding is complete.
          scheduleRefreshRef.current?.(result.expires_in);
        } catch {
          onLogoutRef.current();
          router.push('/login');
        }
      }, delayMs);
    },
    [router]
  );

  // Keep scheduleRefreshRef in sync after each render.
  useEffect(() => {
    scheduleRefreshRef.current = scheduleRefresh;
  });

  useEffect(() => {
    if (expiresIn == null || expiresIn <= 0) return;

    scheduleRefresh(expiresIn);

    return () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [expiresIn, scheduleRefresh]);
}
