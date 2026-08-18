"use client";

import { useEffect, useState } from "react";
import { getMyCrmPermissions } from "@/lib/api/crm";
import { getCompanyId } from "@/components/crm/apiErrors";

export interface CrmPermissionsState {
  /** Granted crm.* permission codes; empty while loading or on error. */
  permissions: string[];
  isLoading: boolean;
  /** True once the initial fetch has resolved (success or failure). */
  isReady: boolean;
}

/**
 * Fetches the current user's crm.* permissions for the active company once
 * per mount, so CRM pages can hide (not just disable) actions the user
 * cannot perform. Fails safe: any error (including feature-disabled)
 * resolves to an empty permission set — every gated action stays hidden
 * rather than risking a false "allowed" on failure.
 */
export function useCrmPermissions(): CrmPermissionsState {
  const [permissions, setPermissions] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const companyId = getCompanyId();
    if (!companyId) {
      setIsLoading(false);
      setIsReady(true);
      return;
    }

    getMyCrmPermissions(companyId)
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
  }, []);

  return { permissions, isLoading, isReady };
}

/** True once permissions are ready and `code` is in the granted set. */
export function useHasCrmPermission(
  state: CrmPermissionsState,
  code: string
): boolean {
  return state.isReady && state.permissions.includes(code);
}
