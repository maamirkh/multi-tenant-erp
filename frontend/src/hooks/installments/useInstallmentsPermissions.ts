"use client";

import { useEffect, useState } from "react";
import { getMyInstallmentsPermissions } from "@/lib/api/installments";
import { getCompanyId } from "@/components/installments/apiErrors";
import { ACTIVE_COMPANY_CHANGED_EVENT } from "@/contexts/CompanyContext";
import { useAuthContext } from "@/contexts/AuthContext";

export interface InstallmentsPermissionsState {
  /** Granted installments.* permission codes; empty while loading or on error. */
  permissions: string[];
  isLoading: boolean;
  /** True once the initial fetch has resolved (success or failure). */
  isReady: boolean;
}

/**
 * Fetches the current user's installments.* permissions for the active
 * company, so Installments pages can hide (not just disable) actions the
 * user cannot perform. Fails safe: any error (including feature-disabled)
 * resolves to an empty permission set — every gated action stays hidden
 * rather than risking a false "allowed" on failure. Mirrors
 * `crm/useCrmPermissions.ts`'s fail-safe behavior.
 *
 * Reactive to company switches: `getCompanyId()` reads `localStorage`
 * directly rather than React context (CompanyProvider doesn't wrap the
 * Installments route group), so a switch elsewhere in the app wouldn't
 * otherwise trigger a re-render here. This hook listens for
 * `ACTIVE_COMPANY_CHANGED_EVENT` (dispatched by `CompanyContext` on every
 * set/clear) and, on change, immediately resets to the fail-closed state
 * (`permissions: []`, `isReady: false`) before fetching the new company's
 * permissions — a Tenant-A-only action can never remain visible under
 * Tenant B, even for an instance that was already mounted at switch time.
 *
 * Waits for `AuthContext`'s own session hydration (`isLoading`) before
 * firing: the access token lives only in an in-memory module variable
 * (`lib/auth/tokenStorage.ts`), so on a hard page load it starts out
 * `null` and is repopulated asynchronously from the stored refresh token.
 * Firing the permissions request before that hydration resolves sends it
 * with no Authorization header, and — unlike `useContract`/TanStack
 * Query's automatic retry — this hand-rolled fetch does not retry, so a
 * transient unauthenticated 401 during that window would otherwise
 * permanently fail-close `isReady`/`permissions` for the life of the
 * mount (Phase 15 E2E Scenario A: a different user logs in and hard-
 * navigates straight to a contract needing their approval).
 */
export function useInstallmentsPermissions(): InstallmentsPermissionsState {
  const { isLoading: authIsLoading } = useAuthContext();
  const [companyId, setCompanyId] = useState<string>(() => getCompanyId());
  const [permissions, setPermissions] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    function handleActiveCompanyChanged(): void {
      const next = getCompanyId();
      // Fail-closed immediately, synchronously with the switch — never
      // let the previous company's permissions remain visible/usable
      // while the new company's fetch is still in flight.
      setPermissions([]);
      setIsReady(false);
      setIsLoading(true);
      setCompanyId(next);
    }
    window.addEventListener(ACTIVE_COMPANY_CHANGED_EVENT, handleActiveCompanyChanged);
    return () =>
      window.removeEventListener(ACTIVE_COMPANY_CHANGED_EVENT, handleActiveCompanyChanged);
  }, []);

  useEffect(() => {
    let cancelled = false;

    // Auth session hydration (in-memory access token) is still in
    // flight — wait rather than firing a request with no token.
    if (authIsLoading) {
      return;
    }

    if (!companyId) {
      setPermissions([]);
      setIsLoading(false);
      setIsReady(true);
      return;
    }

    setIsLoading(true);
    getMyInstallmentsPermissions(companyId)
      .then((res) => {
        if (cancelled) return;
        setPermissions(res.data?.permissions ?? []);
      })
      .catch(() => {
        if (!cancelled) setPermissions([]);
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
          setIsReady(true);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [companyId, authIsLoading]);

  return { permissions, isLoading, isReady };
}

/** True once permissions are ready and `code` is in the granted set. */
export function useHasInstallmentsPermission(
  state: InstallmentsPermissionsState,
  code: string
): boolean {
  return state.isReady && state.permissions.includes(code);
}
