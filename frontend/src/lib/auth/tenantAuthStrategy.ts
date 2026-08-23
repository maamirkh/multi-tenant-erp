/**
 * tenantAuthStrategy — the tenant domain's `AuthStrategy` implementation
 * (T179, ADR-11).
 *
 * Backed by the existing tenant token storage (`tokenStorage.ts`) and
 * single-flight refresh lock (`auth/client.ts`) — behaviour is
 * byte-identical to what `ApiClient` did inline before T178's refactor;
 * this module only relocates the exact same calls behind the
 * `AuthStrategy` interface. No existing domain file (`accounting.ts`,
 * `crm.ts`, `sales.ts`, etc.) needed to change.
 */

import type { AuthStrategy } from '@/lib/api/client';
import { acquireRefreshLock } from './client';
import { clearTokens, getAccessToken } from './tokenStorage';

export const tenantAuthStrategy: AuthStrategy = {
  getToken(): string | null {
    return getAccessToken();
  },

  async refresh(): Promise<void> {
    await acquireRefreshLock();
  },

  onAuthFailure(): void {
    // acquireRefreshLock() already clears tokens and dispatches
    // 'session-expired' on failure (auth/client.ts) — this mirrors that
    // same call exactly, preserving the pre-T178 double-notification
    // shape rather than "fixing" it, per T179's byte-identical mandate.
    clearTokens();
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new Event('session-expired'));
    }
  },
};
