/**
 * Canonical tenant-context accessor (T184, ADR-13).
 *
 * A thin, 100%-compatible contract over the existing persisted key
 * `erp_active_company_id` — the same key `CompanyContext.tsx` already
 * reads/writes via `localStorage.setItem/getItem/removeItem`. This
 * module does **not** replace `CompanyContext`, does not introduce a
 * second source of truth, and does not migrate any existing module —
 * it exists so Platform-side code (which is never wrapped in
 * `<CompanyProvider>`) can read the currently-active tenant id for
 * *display/reference purposes only*, without depending on React context.
 *
 * **Never an authorization source**: per BR-9A-034/035/036, Platform
 * permissions and Platform tenant-selection must never be derived from
 * this value — it is plain client-side state, exactly as
 * `CompanyContext` already treats it. Nothing in this module grants any
 * capability; it only reads/writes a localStorage string.
 */

const STORAGE_KEY = 'erp_active_company_id';

/** Return the persisted active company id, or null if none is set. */
export function getActiveCompanyId(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(STORAGE_KEY);
}

/** Persist the active company id — the same key `CompanyContext` writes. */
export function setActiveCompanyId(companyId: string): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(STORAGE_KEY, companyId);
}

/** Clear the persisted active company id. */
export function clearActiveCompanyId(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(STORAGE_KEY);
}
