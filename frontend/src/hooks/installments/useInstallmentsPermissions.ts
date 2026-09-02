"use client";

import { useEffect, useState } from "react";
import { getMyInstallmentsPermissions } from "@/lib/api/installments";
import { getCompanyId } from "@/components/installments/apiErrors";

export interface InstallmentsPermissionsState {
  /** Granted installments.* permission codes; empty while loading or on error. */
  permissions: string[];
  isLoading: boolean;
  /** True once the initial fetch has resolved (success or failure). */
  isReady: boolean;
}

/**
 * Fetches the current user's installments.* permissions for the active
 * company once per mount, so Installments pages can hide (not just
 * disable) actions the user cannot perform. Fails safe: any error
 * (including feature-disabled) resolves to an empty permission set —
 * every gated action stays hidden rather than risking a false "allowed"
 * on failure. Mirrors `crm/useCrmPermissions.ts` exactly.
 */
export function useInstallmentsPermissions(): InstallmentsPermissionsState {
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
  }, []);

  return { permissions, isLoading, isReady };
}

/** True once permissions are ready and `code` is in the granted set. */
export function useHasInstallmentsPermission(
  state: InstallmentsPermissionsState,
  code: string
): boolean {
  return state.isReady && state.permissions.includes(code);
}
