/**
 * Platform auth-specific client utilities (T180, ADR-11).
 *
 * Provides `acquirePlatformRefreshLock()` — a single-flight promise lock
 * for the Platform domain, structurally **separate** from the tenant
 * domain's `acquireRefreshLock()` (`lib/auth/client.ts`). Two concurrent
 * 401s, one from a Platform request and one from a tenant request, each
 * trigger their own independent refresh; neither can coalesce onto or
 * block the other's lock.
 *
 * Uses raw `fetch` (not `platformApiClient`) for the same reason the
 * tenant module does: avoids the circular dependency
 * platformApiClient → platformAuthClient → platformApiClient.
 *
 * On failure, clears Platform tokens and dispatches
 * `platform-session-expired` — deliberately a distinct event name from
 * the tenant domain's `session-expired`, so a listener scoped to one
 * domain is never woken by the other's failure (T183).
 */

import { clearPlatformTokens, getPlatformRefreshToken, storePlatformTokens } from './platformTokenStorage';

const DEFAULT_BASE_URL = 'http://localhost:8000';

function getBaseUrl(): string {
  return typeof process !== 'undefined'
    ? (process.env['NEXT_PUBLIC_API_URL'] ?? DEFAULT_BASE_URL)
    : DEFAULT_BASE_URL;
}

interface PlatformRefreshResult {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

/** Active Platform refresh promise — null when no refresh is in flight. */
let _platformRefreshPromise: Promise<PlatformRefreshResult> | null = null;

async function executePlatformRefresh(): Promise<PlatformRefreshResult> {
  const refreshToken = getPlatformRefreshToken();
  if (!refreshToken) {
    throw new Error('No Platform refresh token available');
  }

  const response = await fetch(`${getBaseUrl()}/api/v1/platform/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!response.ok) {
    throw new Error(`Platform token refresh failed with status ${response.status}`);
  }

  // Backend wraps in StandardResponse<PlatformRefreshTokenResponse>
  const envelope = (await response.json()) as { data: PlatformRefreshResult };
  return envelope.data;
}

/**
 * Acquire the Platform refresh lock.
 *
 * If a Platform refresh is already in flight, returns the existing
 * Promise so the caller awaits the same network request. Once the
 * refresh completes, new Platform tokens are stored automatically and
 * the lock is released.
 *
 * On failure, Platform tokens are cleared and the
 * `platform-session-expired` event is dispatched — never the tenant
 * domain's `session-expired`.
 */
export function acquirePlatformRefreshLock(): Promise<PlatformRefreshResult> {
  if (!_platformRefreshPromise) {
    _platformRefreshPromise = executePlatformRefresh()
      .then((result) => {
        storePlatformTokens(result.access_token, result.refresh_token);
        return result;
      })
      .catch((err: unknown) => {
        clearPlatformTokens();
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new Event('platform-session-expired'));
        }
        throw err;
      })
      .finally(() => {
        _platformRefreshPromise = null;
      });
  }
  return _platformRefreshPromise;
}
