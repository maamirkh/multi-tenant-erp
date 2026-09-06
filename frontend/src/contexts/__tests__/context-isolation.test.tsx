/**
 * [T187] Platform tenant selection does not disturb tenant context —
 * Epic 9A Phase 14 (BR-9A-035).
 *
 * Two directions, both required:
 *   1. Selecting a tenant in PlatformSelectedTenantContext leaves
 *      `erp_active_company_id` (the tenant-side CompanyContext key)
 *      completely unchanged.
 *   2. Manipulating `erp_active_company_id` directly grants no Platform
 *      capability — it neither authenticates PlatformAuthContext nor
 *      populates PlatformSelectedTenantContext's selection.
 *
 * Also proves T186's "cleared on platform logout" acceptance directly,
 * since that is itself a context-isolation property (the selection must
 * not silently outlive the Platform session that scoped it).
 */

import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { PlatformAuthProvider, usePlatformAuthContext } from '../PlatformAuthContext';
import {
  PlatformSelectedTenantProvider,
  usePlatformSelectedTenantContext,
} from '../PlatformSelectedTenantContext';
import { getActiveCompanyId } from '@/lib/tenant-context/activeCompany';
import { clearPlatformTokens, storePlatformTokens } from '@/lib/platform-auth/platformTokenStorage';

function jsonResponse(status: number, body: unknown): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as Response;
}

const ACTIVE_COMPANY_KEY = 'erp_active_company_id';

function Wrapper({ children }: { children: React.ReactNode }): React.JSX.Element {
  return (
    <PlatformAuthProvider>
      <PlatformSelectedTenantProvider>{children}</PlatformSelectedTenantProvider>
    </PlatformAuthProvider>
  );
}

function useCombined() {
  const auth = usePlatformAuthContext();
  const selectedTenant = usePlatformSelectedTenantContext();
  return { auth, selectedTenant };
}

describe('Context isolation (T187)', () => {
  beforeEach(() => {
    localStorage.clear();
    clearPlatformTokens();
  });

  it('selecting a Platform tenant leaves erp_active_company_id unchanged', async () => {
    localStorage.setItem(ACTIVE_COMPANY_KEY, 'tenant-session-company-id');

    const { result } = renderHook(() => useCombined(), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.auth.isLoading).toBe(false));

    act(() => {
      result.current.selectedTenant.selectTenant({
        id: 'platform-inspected-company-id',
        legalName: 'Some Other Tenant Inc.',
      });
    });

    await waitFor(() =>
      expect(result.current.selectedTenant.selectedTenant?.id).toBe(
        'platform-inspected-company-id'
      )
    );

    // The tenant-side key must be exactly what it was before — Platform's
    // own selection state never touches it.
    expect(localStorage.getItem(ACTIVE_COMPANY_KEY)).toBe('tenant-session-company-id');
    expect(getActiveCompanyId()).toBe('tenant-session-company-id');
  });

  it('manipulating erp_active_company_id grants no Platform capability', async () => {
    localStorage.setItem(ACTIVE_COMPANY_KEY, 'attacker-supplied-company-id');

    const { result } = renderHook(() => useCombined(), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.auth.isLoading).toBe(false));

    // No Platform session exists — merely having erp_active_company_id
    // set must never authenticate the Platform context.
    expect(result.current.auth.isAuthenticated).toBe(false);
    // Nor must it populate a tenant selection out of thin air.
    expect(result.current.selectedTenant.selectedTenant).toBeNull();
  });

  it('[T186] the selected tenant is cleared when the Platform session ends (logout)', async () => {
    // Hydrate as genuinely authenticated (isAuthenticated: false -> true)
    // so the later logout produces a real true -> false transition —
    // the PlatformSelectedTenantContext clearing effect only re-runs on
    // an actual isAuthenticated change, not merely "was already false".
    storePlatformTokens('stale-access', 'stored-refresh');
    global.fetch = jest.fn().mockImplementation(async (url) => {
      const u = String(url);
      if (u.endsWith('/api/v1/platform/auth/refresh')) {
        return jsonResponse(200, {
          data: { access_token: 'fresh-access', refresh_token: 'fresh-refresh', expires_in: 900 },
        });
      }
      if (u.endsWith('/api/v1/platform/auth/logout')) {
        return jsonResponse(200, { data: {}, message: 'ok', meta: {} });
      }
      throw new Error(`unexpected fetch: ${u}`);
    });

    const { result } = renderHook(() => useCombined(), { wrapper: Wrapper });

    await waitFor(() => expect(result.current.auth.isLoading).toBe(false));
    await waitFor(() => expect(result.current.auth.isAuthenticated).toBe(true));

    act(() => {
      result.current.selectedTenant.selectTenant({
        id: 'inspected-co',
        legalName: 'Inspected Co',
      });
    });
    await waitFor(() =>
      expect(result.current.selectedTenant.selectedTenant?.id).toBe('inspected-co')
    );

    await act(async () => {
      await result.current.auth.logout();
    });

    await waitFor(() => expect(result.current.auth.isAuthenticated).toBe(false));
    await waitFor(() => expect(result.current.selectedTenant.selectedTenant).toBeNull());
  });
});
