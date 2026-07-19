'use client';

/**
 * CompanyContext — active company selection and persistence.
 *
 * Stores the currently selected company (lightweight CompanySummary) in
 * React state and persists the company id in localStorage so that the
 * selection survives page refresh.
 *
 * The active company is cleared whenever the `session-expired` custom event
 * is dispatched by the API client interceptor (same event used by AuthContext).
 *
 * Spec reference: Epic 3, Phase 10 (T061).
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import type { CompanySummary } from '@/types/companies';

const STORAGE_KEY = 'erp_active_company_id';

export interface CompanyContextValue {
  /** Currently selected company, or null if none is selected. */
  activeCompany: CompanySummary | null;
  /** Mark a company as the active context for the session. */
  setActiveCompany: (company: CompanySummary) => void;
  /** Deselect the active company and clear the persisted id. */
  clearActiveCompany: () => void;
  /** True while the initial persisted company is being resolved. */
  isLoading: boolean;
}

const CompanyContext = createContext<CompanyContextValue | null>(null);

export function CompanyProvider({
  children,
}: {
  children: React.ReactNode;
}): React.JSX.Element {
  const [activeCompany, setActiveCompanyState] = useState<CompanySummary | null>(null);

  // Lazy initialiser: isLoading is true only when there is a persisted company
  // id that has not yet been resolved into a full CompanySummary. This avoids
  // calling setState synchronously inside a useEffect.
  const [isLoading, setIsLoading] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return window.localStorage.getItem(STORAGE_KEY) !== null;
  });

  // Clear active company on session expiry (dispatched by API client).
  useEffect(() => {
    if (typeof window === 'undefined') return;

    function handleSessionExpired(): void {
      setActiveCompanyState(null);
      window.localStorage.removeItem(STORAGE_KEY);
    }

    window.addEventListener('session-expired', handleSessionExpired);
    return () => window.removeEventListener('session-expired', handleSessionExpired);
  }, []);

  const setActiveCompany = useCallback((company: CompanySummary): void => {
    setActiveCompanyState(company);
    setIsLoading(false);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, company.id);
    }
  }, []);

  const clearActiveCompany = useCallback((): void => {
    setActiveCompanyState(null);
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  /** Return the persisted company id even before the full summary is loaded. */
  const persistedId =
    typeof window !== 'undefined' ? window.localStorage.getItem(STORAGE_KEY) : null;

  const value = useMemo<CompanyContextValue>(
    () => ({
      activeCompany,
      setActiveCompany,
      clearActiveCompany,
      isLoading: isLoading && persistedId !== null && activeCompany === null,
    }),
    [activeCompany, clearActiveCompany, isLoading, persistedId, setActiveCompany]
  );

  return <CompanyContext.Provider value={value}>{children}</CompanyContext.Provider>;
}

export function useCompanyContext(): CompanyContextValue {
  const ctx = useContext(CompanyContext);
  if (!ctx) {
    throw new Error('useCompanyContext must be used inside <CompanyProvider>');
  }
  return ctx;
}
