/**
 * Token storage abstraction.
 *
 * SECURITY TRADEOFF (ADR-0003):
 * - Access token: stored in a module-level variable (in-memory only).
 *   Rationale: in-memory storage prevents XSS attacks from reading the token
 *   via `localStorage`. The token is short-lived (15 min default), so the
 *   risk window on page reload is minimal.
 * - Refresh token: stored in `localStorage` under key `erp_refresh_token`.
 *   Rationale: must survive page reloads to restore sessions without re-login.
 *   XSS risk is acknowledged and documented. HttpOnly cookie migration path
 *   is tracked as a follow-up task once backend coordinated `Set-Cookie` is added.
 */

const REFRESH_TOKEN_KEY = 'erp_refresh_token';

/** In-memory access token — never written to localStorage. */
let _accessToken: string | null = null;

/**
 * Store both tokens. Access token goes into memory only; refresh token goes
 * into localStorage so it survives page reloads.
 */
export function storeTokens(access: string, refresh: string): void {
  _accessToken = access;
  if (typeof window !== 'undefined') {
    localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
  }
}

/** Return the current in-memory access token, or null if not set. */
export function getAccessToken(): string | null {
  return _accessToken;
}

/** Return the refresh token from localStorage, or null if absent. */
export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

/** Clear both tokens — call on logout or session expiry. */
export function clearTokens(): void {
  _accessToken = null;
  if (typeof window !== 'undefined') {
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  }
}
