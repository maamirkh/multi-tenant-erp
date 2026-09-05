/**
 * Auth-specific client utilities.
 *
 * Provides a singleton refresh promise lock that ensures multiple simultaneous
 * 401 responses from the API client trigger only one token refresh request.
 * All concurrent callers await the same Promise and receive the updated tokens.
 *
 * This module uses raw `fetch` (not `apiClient`) to avoid the circular dependency:
 *   apiClient → authClient → apiClient
 */

import { clearTokens, getEpoch, getRefreshToken, storeTokens } from './tokenStorage';

const DEFAULT_BASE_URL = 'http://localhost:8000';

function getBaseUrl(): string {
  return typeof process !== 'undefined'
    ? (process.env['NEXT_PUBLIC_API_URL'] ?? DEFAULT_BASE_URL)
    : DEFAULT_BASE_URL;
}

interface RefreshResult {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

/** Active refresh promise — null when no refresh is in flight. */
let _refreshPromise: Promise<RefreshResult> | null = null;

async function executeRefresh(): Promise<RefreshResult> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    throw new Error('No refresh token available');
  }

  const response = await fetch(`${getBaseUrl()}/api/v1/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!response.ok) {
    throw new Error(`Token refresh failed with status ${response.status}`);
  }

  // Backend wraps in StandardResponse<RefreshResponse>
  const envelope = (await response.json()) as { data: RefreshResult };
  return envelope.data;
}

/**
 * Acquire the refresh lock.
 *
 * If a refresh is already in flight, returns the existing Promise so the caller
 * awaits the same network request. Once the refresh completes, new tokens are
 * stored automatically and the lock is released.
 *
 * On failure, tokens are cleared and the `session-expired` event is dispatched.
 */
export function acquireRefreshLock(): Promise<RefreshResult> {
  if (!_refreshPromise) {
    // Captured before the request goes out: if a newer storeTokens()/
    // clearTokens() call (e.g. a fresh login) lands before this refresh
    // resolves, its result is stale and must not overwrite the newer
    // session's tokens.
    const epochAtStart = getEpoch();
    _refreshPromise = executeRefresh()
      .then((result) => {
        if (getEpoch() === epochAtStart) {
          storeTokens(result.access_token, result.refresh_token);
        }
        return result;
      })
      .catch((err: unknown) => {
        if (getEpoch() === epochAtStart) {
          clearTokens();
          if (typeof window !== 'undefined') {
            window.dispatchEvent(new Event('session-expired'));
          }
        }
        throw err;
      })
      .finally(() => {
        _refreshPromise = null;
      });
  }
  return _refreshPromise;
}
