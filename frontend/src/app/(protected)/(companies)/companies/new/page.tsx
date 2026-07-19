/**
 * T078 — New Company page.
 *
 * Renders CompanyCreateWizard within a page container.
 * Spec ref: Epic 3, Phase 11 (T078).
 */

'use client';

import { CompanyCreateWizard } from '@/components/companies/CompanyCreateWizard';

export default function NewCompanyPage() {
  return (
    <div className="py-6">
      <CompanyCreateWizard />
    </div>
  );
}
