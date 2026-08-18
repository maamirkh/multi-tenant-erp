import { ApiClientError } from "@/lib/api/client";

export interface CrmErrorState {
  message: string;
  forbidden: boolean;
  featureDisabled: boolean;
}

/**
 * Classifies an error thrown by a `crm.ts` API call into the three states
 * every CRM page needs to render distinctly: a generic error message,
 * permission-denied (403, any code), and feature-disabled (403,
 * FEATURE_DISABLED — thrown by `require_crm_enabled` at the router-mount
 * level). Mirrors the `ApiClientError` + `.status === 403` convention
 * already established in `(accounting)/audit-trail/page.tsx`.
 */
export function classifyCrmError(err: unknown): CrmErrorState {
  if (err instanceof ApiClientError) {
    const code = err.error.error.code;
    return {
      message: err.error.error.message,
      forbidden: err.status === 403,
      featureDisabled: err.status === 403 && code === "FEATURE_DISABLED",
    };
  }
  return {
    message: err instanceof Error ? err.message : "Something went wrong.",
    forbidden: false,
    featureDisabled: false,
  };
}

export function getCompanyId(): string {
  return typeof window !== "undefined" ? (localStorage.getItem("company_id") ?? "") : "";
}
