/**
 * Platform token storage abstraction (T180, ADR-11).
 *
 * Structurally separate from the tenant token storage
 * (`lib/auth/tokenStorage.ts`) — its own module-level in-memory variable
 * and its own localStorage key, so neither domain can read or clear the
 * other's tokens.
 *
 * SECURITY TRADEOFF (mirrors the tenant module's own ADR-0003 rationale):
 * - Platform access token: in-memory only (module-level variable), never
 *   written to localStorage — mitigates XSS token theft.
 * - Platform refresh token: localStorage under `erp_platform_refresh_token`
 *   — deliberately **never** `erp_refresh_token` (the tenant key), so a
 *   Platform session cannot be reconstructed from, or confused with, a
 *   tenant session's persisted state.
 */

const PLATFORM_REFRESH_TOKEN_KEY = 'erp_platform_refresh_token';

/** In-memory Platform access token — never written to localStorage. */
let _platformAccessToken: string | null = null;

/**
 * Store both Platform tokens. Access token goes into memory only;
 * refresh token goes into localStorage so it survives page reloads.
 */
export function storePlatformTokens(access: string, refresh: string): void {
  _platformAccessToken = access;
  if (typeof window !== 'undefined') {
    localStorage.setItem(PLATFORM_REFRESH_TOKEN_KEY, refresh);
  }
}

/** Return the current in-memory Platform access token, or null if not set. */
export function getPlatformAccessToken(): string | null {
  return _platformAccessToken;
}

/** Return the Platform refresh token from localStorage, or null if absent. */
export function getPlatformRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(PLATFORM_REFRESH_TOKEN_KEY);
}

/** Clear both Platform tokens — call on Platform logout or session expiry. */
export function clearPlatformTokens(): void {
  _platformAccessToken = null;
  if (typeof window !== 'undefined') {
    localStorage.removeItem(PLATFORM_REFRESH_TOKEN_KEY);
  }
}
