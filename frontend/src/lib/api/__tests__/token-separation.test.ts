/**
 * [T182, T183] Token separation between the tenant and Platform domains
 * (ADR-11).
 *
 * T182: zero token crossover in either direction — a Platform request
 * carries only the Platform token, a tenant request carries only the
 * tenant token, and neither client can read the other's storage.
 *
 * T183: a 401 invokes only its own domain's refresh flow — the two
 * single-flight locks (`acquireRefreshLock` / `acquirePlatformRefreshLock`)
 * are structurally independent. A failed refresh in one domain never
 * clears the other domain's tokens nor emits the other domain's
 * session-expiry event. Includes a concurrent-401 case proving the locks
 * don't coalesce onto or block each other.
 *
 * Uses a single mocked `global.fetch` keyed by URL — this exercises the
 * real `ApiClient` + real `AuthStrategy` implementations end-to-end
 * (tenant: `tenantAuthStrategy` via `apiClient`; Platform:
 * `platformAuthStrategy` via `platformApiClient`), not mocks of the
 * strategies themselves, since the whole point under test is the
 * structural wiring between them.
 */

import { apiClient } from '../client';
import { platformApiClient } from '../platform';
import { clearTokens, getAccessToken, storeTokens } from '@/lib/auth/tokenStorage';
import {
  clearPlatformTokens,
  getPlatformAccessToken,
  storePlatformTokens,
} from '@/lib/platform-auth/platformTokenStorage';

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function tokenExpiredError(): unknown {
  return { error: { code: 'TOKEN_EXPIRED', message: 'expired', details: {} } };
}

describe('Token separation (T182, T183)', () => {
  let sessionExpiredHandler: jest.Mock;
  let platformSessionExpiredHandler: jest.Mock;

  beforeEach(() => {
    localStorage.clear();
    clearTokens();
    clearPlatformTokens();

    sessionExpiredHandler = jest.fn();
    platformSessionExpiredHandler = jest.fn();
    window.addEventListener('session-expired', sessionExpiredHandler);
    window.addEventListener('platform-session-expired', platformSessionExpiredHandler);
  });

  afterEach(() => {
    window.removeEventListener('session-expired', sessionExpiredHandler);
    window.removeEventListener('platform-session-expired', platformSessionExpiredHandler);
    jest.restoreAllMocks();
  });

  describe('T182 — zero crossover', () => {
    it('a Platform request carries only the Platform token, never the tenant token', async () => {
      storeTokens('tenant-access', 'tenant-refresh');
      storePlatformTokens('platform-access', 'platform-refresh');

      const fetchMock = (global.fetch = jest.fn()).mockResolvedValue(
        jsonResponse(200, { data: {}, message: 'ok', meta: {} })
      );

      await platformApiClient.get('/api/v1/platform/dashboard');

      expect(fetchMock).toHaveBeenCalledTimes(1);
      const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      const headers = init.headers as Record<string, string>;
      expect(headers['Authorization']).toBe('Bearer platform-access');
      expect(headers['Authorization']).not.toContain('tenant-access');
    });

    it('a tenant request carries only the tenant token, never the Platform token', async () => {
      storeTokens('tenant-access', 'tenant-refresh');
      storePlatformTokens('platform-access', 'platform-refresh');

      const fetchMock = (global.fetch = jest.fn()).mockResolvedValue(
        jsonResponse(200, { data: {}, message: 'ok', meta: {} })
      );

      await apiClient.get('/api/v1/some-resource');

      expect(fetchMock).toHaveBeenCalledTimes(1);
      const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      const headers = init.headers as Record<string, string>;
      expect(headers['Authorization']).toBe('Bearer tenant-access');
      expect(headers['Authorization']).not.toContain('platform-access');
    });

    it('neither storage module can read the value the other stored', () => {
      storeTokens('tenant-only-value', 'tenant-refresh');
      storePlatformTokens('platform-only-value', 'platform-refresh');

      expect(getAccessToken()).toBe('tenant-only-value');
      expect(getPlatformAccessToken()).toBe('platform-only-value');

      // Overwriting one must never affect the other.
      storeTokens('tenant-changed', 'tenant-refresh-2');
      expect(getPlatformAccessToken()).toBe('platform-only-value');

      clearTokens();
      expect(getAccessToken()).toBeNull();
      expect(getPlatformAccessToken()).toBe('platform-only-value');
    });
  });

  describe('T183 — independent refresh flows', () => {
    it('a Platform 401 refreshes only via the Platform endpoint, never the tenant one', async () => {
      storePlatformTokens('stale-platform-access', 'platform-refresh-token');

      const fetchMock = (global.fetch = jest.fn()).mockImplementation(async (url) => {
        const u = String(url);
        if (u.endsWith('/api/v1/platform/auth/refresh')) {
          return jsonResponse(200, {
            data: { access_token: 'new-platform-access', refresh_token: 'new-platform-refresh', expires_in: 900 },
          });
        }
        if (u.endsWith('/api/v1/auth/refresh')) {
          throw new Error('tenant refresh endpoint must never be called for a Platform 401');
        }
        if (u.endsWith('/api/v1/platform/dashboard')) {
          const isRetry = getPlatformAccessToken() === 'new-platform-access';
          return isRetry
            ? jsonResponse(200, { data: {}, message: 'ok', meta: {} })
            : jsonResponse(401, tokenExpiredError());
        }
        throw new Error(`unexpected fetch: ${u}`);
      });

      await platformApiClient.get('/api/v1/platform/dashboard');

      const refreshCalls = fetchMock.mock.calls.filter(([u]) =>
        String(u).endsWith('/auth/refresh')
      );
      expect(refreshCalls).toHaveLength(1);
      expect(String(refreshCalls[0]?.[0])).toBe('http://localhost:8000/api/v1/platform/auth/refresh');
    });

    it('a tenant 401 refreshes only via the tenant endpoint, never the Platform one', async () => {
      storeTokens('stale-tenant-access', 'tenant-refresh-token');

      const fetchMock = (global.fetch = jest.fn()).mockImplementation(async (url) => {
        const u = String(url);
        if (u.endsWith('/api/v1/platform/auth/refresh')) {
          throw new Error('platform refresh endpoint must never be called for a tenant 401');
        }
        if (u.endsWith('/api/v1/auth/refresh')) {
          return jsonResponse(200, {
            data: { access_token: 'new-tenant-access', refresh_token: 'new-tenant-refresh', expires_in: 900 },
          });
        }
        if (u.endsWith('/api/v1/some-resource')) {
          const isRetry = getAccessToken() === 'new-tenant-access';
          return isRetry
            ? jsonResponse(200, { data: {}, message: 'ok', meta: {} })
            : jsonResponse(401, tokenExpiredError());
        }
        throw new Error(`unexpected fetch: ${u}`);
      });

      await apiClient.get('/api/v1/some-resource');

      const refreshCalls = fetchMock.mock.calls.filter(([u]) =>
        String(u).endsWith('/auth/refresh')
      );
      expect(refreshCalls).toHaveLength(1);
      expect(String(refreshCalls[0]?.[0])).toBe('http://localhost:8000/api/v1/auth/refresh');
    });

    it('a failed Platform refresh clears only Platform tokens and fires only platform-session-expired', async () => {
      storeTokens('tenant-access', 'tenant-refresh-token');
      storePlatformTokens('stale-platform-access', 'platform-refresh-token');

      (global.fetch = jest.fn()).mockImplementation(async (url) => {
        const u = String(url);
        if (u.endsWith('/api/v1/platform/auth/refresh')) {
          return jsonResponse(401, tokenExpiredError());
        }
        if (u.endsWith('/api/v1/platform/dashboard')) {
          return jsonResponse(401, tokenExpiredError());
        }
        throw new Error(`unexpected fetch: ${u}`);
      });

      await expect(platformApiClient.get('/api/v1/platform/dashboard')).rejects.toThrow();

      // Wait a tick for the 'platform-session-expired' listener (async dispatch chain).
      await new Promise((resolve) => setTimeout(resolve, 0));

      expect(getPlatformAccessToken()).toBeNull();
      expect(localStorage.getItem('erp_platform_refresh_token')).toBeNull();
      // Fires twice by design: once inside acquirePlatformRefreshLock()'s
      // own failure handler, once inside onAuthFailure() — the exact same
      // pre-existing double-dispatch shape the tenant lock already had
      // before T178 (preserved deliberately, not "fixed", per T179's
      // byte-identical mandate). The assertion under test here is really
      // "at least once, and never the *other* domain's event" — see below.
      expect(platformSessionExpiredHandler).toHaveBeenCalledTimes(2);

      // The tenant domain is completely untouched.
      expect(getAccessToken()).toBe('tenant-access');
      expect(localStorage.getItem('erp_refresh_token')).toBe('tenant-refresh-token');
      expect(sessionExpiredHandler).not.toHaveBeenCalled();
    });

    it('a failed tenant refresh clears only tenant tokens and fires only session-expired', async () => {
      storeTokens('stale-tenant-access', 'tenant-refresh-token');
      storePlatformTokens('platform-access', 'platform-refresh-token');

      (global.fetch = jest.fn()).mockImplementation(async (url) => {
        const u = String(url);
        if (u.endsWith('/api/v1/auth/refresh')) {
          return jsonResponse(401, tokenExpiredError());
        }
        if (u.endsWith('/api/v1/some-resource')) {
          return jsonResponse(401, tokenExpiredError());
        }
        throw new Error(`unexpected fetch: ${u}`);
      });

      await expect(apiClient.get('/api/v1/some-resource')).rejects.toThrow();

      await new Promise((resolve) => setTimeout(resolve, 0));

      expect(getAccessToken()).toBeNull();
      expect(localStorage.getItem('erp_refresh_token')).toBeNull();
      // Fires twice by design — see the mirrored Platform test above for
      // the full explanation (pre-existing acquireRefreshLock() shape,
      // deliberately preserved).
      expect(sessionExpiredHandler).toHaveBeenCalledTimes(2);

      // The Platform domain is completely untouched.
      expect(getPlatformAccessToken()).toBe('platform-access');
      expect(localStorage.getItem('erp_platform_refresh_token')).toBe('platform-refresh-token');
      expect(platformSessionExpiredHandler).not.toHaveBeenCalled();
    });

    it('concurrent Platform and tenant 401s refresh independently without blocking each other', async () => {
      storeTokens('stale-tenant-access', 'tenant-refresh-token');
      storePlatformTokens('stale-platform-access', 'platform-refresh-token');

      const fetchMock = (global.fetch = jest.fn()).mockImplementation(async (url) => {
        const u = String(url);
        if (u.endsWith('/api/v1/platform/auth/refresh')) {
          return jsonResponse(200, {
            data: { access_token: 'new-platform-access', refresh_token: 'new-platform-refresh', expires_in: 900 },
          });
        }
        if (u.endsWith('/api/v1/auth/refresh')) {
          return jsonResponse(200, {
            data: { access_token: 'new-tenant-access', refresh_token: 'new-tenant-refresh', expires_in: 900 },
          });
        }
        if (u.endsWith('/api/v1/platform/dashboard')) {
          const isRetry = getPlatformAccessToken() === 'new-platform-access';
          return isRetry
            ? jsonResponse(200, { data: {}, message: 'ok', meta: {} })
            : jsonResponse(401, tokenExpiredError());
        }
        if (u.endsWith('/api/v1/some-resource')) {
          const isRetry = getAccessToken() === 'new-tenant-access';
          return isRetry
            ? jsonResponse(200, { data: {}, message: 'ok', meta: {} })
            : jsonResponse(401, tokenExpiredError());
        }
        throw new Error(`unexpected fetch: ${u}`);
      });

      // Fire both concurrently — neither lock may coalesce with the other.
      const [tenantResult, platformResult] = await Promise.all([
        apiClient.get('/api/v1/some-resource'),
        platformApiClient.get('/api/v1/platform/dashboard'),
      ]);

      expect(tenantResult).toBeDefined();
      expect(platformResult).toBeDefined();

      const tenantRefreshCalls = fetchMock.mock.calls.filter(
        ([u]) => String(u) === 'http://localhost:8000/api/v1/auth/refresh'
      );
      const platformRefreshCalls = fetchMock.mock.calls.filter(
        ([u]) => String(u) === 'http://localhost:8000/api/v1/platform/auth/refresh'
      );
      expect(tenantRefreshCalls).toHaveLength(1);
      expect(platformRefreshCalls).toHaveLength(1);
    });
  });
});
