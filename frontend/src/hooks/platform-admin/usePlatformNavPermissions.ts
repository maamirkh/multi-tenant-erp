'use client';

/**
 * usePlatformNavPermissions — resolves which Platform nav sections the
 * current administrator can actually reach (T189).
 *
 * There is no `GET /platform/auth/me` or permissions-listing endpoint in
 * the finalized contract (`contracts/platform-admin-v1.yaml` fixes
 * exactly 28 paths — plan.md §10 API Contract Lock forbids inventing
 * one). So this hook is "genuinely permission-driven" (unlike the
 * tenant `Sidebar`'s acknowledged placeholder, T189's own purpose
 * statement) by issuing one minimal, real read call per probeable
 * section and hiding the entry only on a definitive 403 from
 * `require_platform_permission` — the same server-side check that would
 * reject the page itself. This is UX only; every Platform route remains
 * independently enforced server-side regardless of what this hook
 * decides (plan.md §7 Architecture Freeze — Platform RBAC).
 *
 * Four nav sections (`subscriptions`, `entitlements`, `quotas`, `usage`)
 * have no tenant-independent list endpoint to probe — every declared
 * operation for them requires a `companyId` path parameter
 * (`contracts/platform-admin-v1.yaml`). They are always shown; the page
 * itself 403s honestly once a tenant is selected and the real call is
 * made, exactly as `platform.entitlements.read`/etc. would reject it.
 * Documented limitation, not a security gap — the property this hook
 * protects is nav-hiding UX, never authorization.
 *
 * Fails open on ambiguity: any outcome other than a confirmed HTTP 403
 * (network error, unrelated failure) leaves that section visible, since
 * hiding a reachable page is worse UX than briefly showing one that the
 * server will still correctly refuse.
 */

import { useEffect, useState } from 'react';
import { platformApiClient, platformBase } from '@/lib/api/platform';
import { isForbidden } from '@/components/platform-admin/DataState';

export type PlatformNavSection =
  | 'dashboard'
  | 'tenants'
  | 'plans'
  | 'administrators'
  | 'roles'
  | 'audit'
  | 'support-access'
  | 'health';

const PROBES: Record<PlatformNavSection, string> = {
  dashboard: `${platformBase()}/dashboard`,
  tenants: `${platformBase()}/tenants?page=1&page_size=1`,
  plans: `${platformBase()}/plans?page=1&page_size=1`,
  administrators: `${platformBase()}/administrators?page=1&page_size=1`,
  roles: `${platformBase()}/roles?page=1&page_size=1`,
  audit: `${platformBase()}/audit?page=1&page_size=1`,
  'support-access': `${platformBase()}/support-access?page=1&page_size=1`,
  health: `${platformBase()}/health`,
};

const ALL_SECTIONS = Object.keys(PROBES) as PlatformNavSection[];

export interface PlatformNavPermissions {
  /** True until every probe has settled. All sections render visible
   * while loading, to avoid a hide-then-show flash for the common case
   * (administrator holds the permission). */
  isLoading: boolean;
  isAllowed: (section: PlatformNavSection) => boolean;
}

export function usePlatformNavPermissions(): PlatformNavPermissions {
  const [denied, setDenied] = useState<Set<PlatformNavSection>>(new Set());
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function probe(): Promise<void> {
      const results = await Promise.allSettled(
        ALL_SECTIONS.map((section) => platformApiClient.get(PROBES[section]))
      );
      if (cancelled) return;
      const next = new Set<PlatformNavSection>();
      results.forEach((result, i) => {
        if (result.status === 'rejected' && isForbidden(result.reason)) {
          next.add(ALL_SECTIONS[i] as PlatformNavSection);
        }
      });
      setDenied(next);
      setIsLoading(false);
    }

    void probe();

    return () => {
      cancelled = true;
    };
  }, []);

  return {
    isLoading,
    isAllowed: (section) => !denied.has(section),
  };
}
