/**
 * Platform API client (T181, ADR-11).
 *
 * `platformApiClient` is a second, independent `ApiClient` instance
 * backed by the Platform `AuthStrategy` — imports only the Platform
 * token storage/refresh-lock modules (`lib/platform-auth/*`), never the
 * tenant ones. Every Platform page/domain file (Phase 15+) uses this
 * export, never the tenant `apiClient`.
 *
 * Usage:
 *   import { platformApiClient, platformBase } from '@/lib/api/platform';
 *   const res = await platformApiClient.get(`${platformBase()}/dashboard`);
 */

import { ApiClient } from './client';
import type { AuthStrategy } from './client';
import {
  acquirePlatformRefreshLock,
} from '@/lib/platform-auth/platformAuthClient';
import {
  clearPlatformTokens,
  getPlatformAccessToken,
} from '@/lib/platform-auth/platformTokenStorage';

/**
 * The Platform domain's `AuthStrategy` — deliberately defined inline
 * here rather than as a separate exported module (unlike the tenant
 * domain's `tenantAuthStrategy.ts`); T181's own scope is this file only.
 */
const platformAuthStrategy: AuthStrategy = {
  getToken(): string | null {
    return getPlatformAccessToken();
  },

  async refresh(): Promise<void> {
    await acquirePlatformRefreshLock();
  },

  onAuthFailure(): void {
    // acquirePlatformRefreshLock() already clears Platform tokens and
    // dispatches 'platform-session-expired' on failure — this mirrors
    // that same call, matching tenantAuthStrategy's own shape exactly.
    clearPlatformTokens();
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new Event('platform-session-expired'));
    }
  },
};

/**
 * The path prefix every Platform contract operation lives under
 * (`contracts/platform-admin-v1.yaml`'s `servers[0].url`). Callers
 * compose full paths as `` `${platformBase()}/dashboard` ``, etc.
 */
export function platformBase(): string {
  return '/api/v1/platform';
}

/**
 * Singleton Platform API client instance — backed by the Platform
 * `AuthStrategy`. Structurally cannot read or clear tenant tokens: it
 * never imports `lib/auth/tokenStorage.ts` or `lib/auth/client.ts`.
 */
export const platformApiClient = new ApiClient(platformAuthStrategy);
