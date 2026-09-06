'use client';

/**
 * PlatformSelectedTenantContext — the tenant a Platform Administrator has
 * selected for inspection/support-access, structurally separate from the
 * tenant-side `CompanyContext` (T186, BR-9A-035).
 *
 * **In-memory only** — no localStorage persistence at all, and in
 * particular this module never reads or writes `erp_active_company_id`
 * (`CompanyContext.tsx`'s key, also exposed read-only via T184's
 * `activeCompany.ts` accessor). Selecting a tenant here has zero effect
 * on what any tenant-side tab in the same browser sees as its active
 * company, and vice versa.
 *
 * **Never an authorization source** (BR-9A-034/036): this context only
 * carries a display-purposes tenant summary for the Platform UI — no
 * code anywhere derives a permission or capability from it. Every
 * Platform API call remains gated server-side by the actor's actual
 * `platform.*` permissions, never by which tenant happens to be
 * selected here.
 *
 * Nested inside `<PlatformAuthProvider>` (T185) so the selection clears
 * automatically whenever the Platform session ends — explicit logout
 * and session-expiry both flow through `isAuthenticated` becoming
 * `false`, so no separate event wiring is needed here.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { usePlatformAuthContext } from './PlatformAuthContext';

/** Minimal display-purposes tenant summary — never used for authorization. */
export interface PlatformSelectedTenantSummary {
  id: string;
  legalName: string;
}

export interface PlatformSelectedTenantContextValue {
  selectedTenant: PlatformSelectedTenantSummary | null;
  selectTenant: (tenant: PlatformSelectedTenantSummary) => void;
  clearSelectedTenant: () => void;
}

const PlatformSelectedTenantContext =
  createContext<PlatformSelectedTenantContextValue | null>(null);

export function PlatformSelectedTenantProvider({
  children,
}: {
  children: React.ReactNode;
}): React.JSX.Element {
  const { isAuthenticated } = usePlatformAuthContext();
  const [selectedTenant, setSelectedTenantState] =
    useState<PlatformSelectedTenantSummary | null>(null);

  // Cleared whenever the Platform session ends — covers both explicit
  // logout() and session-expiry, since both set isAuthenticated=false.
  useEffect(() => {
    if (!isAuthenticated) {
      setSelectedTenantState(null);
    }
  }, [isAuthenticated]);

  const selectTenant = useCallback((tenant: PlatformSelectedTenantSummary): void => {
    setSelectedTenantState(tenant);
  }, []);

  const clearSelectedTenant = useCallback((): void => {
    setSelectedTenantState(null);
  }, []);

  const value = useMemo<PlatformSelectedTenantContextValue>(
    () => ({ selectedTenant, selectTenant, clearSelectedTenant }),
    [selectedTenant, selectTenant, clearSelectedTenant]
  );

  return (
    <PlatformSelectedTenantContext.Provider value={value}>
      {children}
    </PlatformSelectedTenantContext.Provider>
  );
}

/**
 * Internal hook — used only by Platform pages/components.
 * Throws if called outside a `<PlatformSelectedTenantProvider>`.
 */
export function usePlatformSelectedTenantContext(): PlatformSelectedTenantContextValue {
  const ctx = useContext(PlatformSelectedTenantContext);
  if (ctx === null) {
    throw new Error(
      'usePlatformSelectedTenantContext must be used within a <PlatformSelectedTenantProvider>'
    );
  }
  return ctx;
}
