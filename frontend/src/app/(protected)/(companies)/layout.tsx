/**
 * T073 — Companies route group layout.
 *
 * Wraps all routes under (companies)/ with CompanyProvider so that any page
 * in this group can read or set the active company via useCompanyContext().
 *
 * Spec ref: Epic 3, Phase 11 (T073).
 */

import { CompanyProvider } from '@/contexts/CompanyContext';

export default function CompaniesLayout({
  children,
}: {
  children: React.ReactNode;
}): React.JSX.Element {
  return <CompanyProvider>{children}</CompanyProvider>;
}
