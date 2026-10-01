/**
 * The active company id for Reports hooks — read from the platform's single
 * persisted key (`erp_active_company_id`) and re-read whenever
 * `CompanyContext` announces a switch via `ACTIVE_COMPANY_CHANGED_EVENT`.
 *
 * `CompanyProvider` doesn't wrap the Reports route group (same as
 * Installments/CRM), so React context can't be relied on here; subscribing
 * to the event means a company switch re-keys every Reports query instead
 * of serving the previous tenant's cached data.
 */

import { useSyncExternalStore } from 'react';
import { ACTIVE_COMPANY_CHANGED_EVENT } from '@/contexts/CompanyContext';
import { getActiveCompanyId } from '@/lib/tenant-context/activeCompany';

function subscribe(onChange: () => void): () => void {
  window.addEventListener(ACTIVE_COMPANY_CHANGED_EVENT, onChange);
  window.addEventListener('storage', onChange);
  return () => {
    window.removeEventListener(ACTIVE_COMPANY_CHANGED_EVENT, onChange);
    window.removeEventListener('storage', onChange);
  };
}

function snapshot(): string {
  return getActiveCompanyId() ?? '';
}

function serverSnapshot(): string {
  return '';
}

/** `''` when no company is active — every Reports query is disabled then. */
export function useActiveCompanyId(): string {
  return useSyncExternalStore(subscribe, snapshot, serverSnapshot);
}
