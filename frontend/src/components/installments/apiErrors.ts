import { ApiClientError } from "@/lib/api/client";

export interface InstallmentsErrorState {
  message: string;
  forbidden: boolean;
  featureDisabled: boolean;
}

/**
 * Classifies an error thrown by an `installments.ts` API call into the
 * three states every Installments page needs to render distinctly: a
 * generic error message, permission-denied (403, any code), and
 * feature-disabled (403, FEATURE_DISABLED). Mirrors
 * `crm/apiErrors.ts::classifyCrmError` exactly.
 */
export function classifyInstallmentsError(err: unknown): InstallmentsErrorState {
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

// Matches CompanyContext's STORAGE_KEY (frontend/src/contexts/CompanyContext.tsx) —
// the real platform mechanism for the active company, persisted when a user
// views a company via the Companies module. Read directly from localStorage
// (not via useCompanyContext()) because CompanyProvider only wraps the
// (companies) route group, not Installments' sibling route group. Mirrors
// crm/apiErrors.ts::getCompanyId exactly.
const ACTIVE_COMPANY_STORAGE_KEY = "erp_active_company_id";

export function getCompanyId(): string {
  return typeof window !== "undefined"
    ? (localStorage.getItem(ACTIVE_COMPANY_STORAGE_KEY) ?? "")
    : "";
}
