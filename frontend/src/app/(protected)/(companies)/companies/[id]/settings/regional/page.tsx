/**
 * T093 — /companies/[id]/settings/regional.
 *
 * Regional settings page: timezone, currency, language, fiscal year start.
 * Spec ref: Epic 3, Phase 12 (T093).
 */

'use client';

import { use } from 'react';
import { useCompany } from '@/hooks/companies/useCompany';
import { CompanySettingsTabs } from '@/components/companies/CompanySettingsTabs';
import { CompanyRegionalSettingsForm } from '@/components/companies/CompanyRegionalSettingsForm';

interface Props {
  params: Promise<{ id: string }>;
}

export default function CompanyRegionalSettingsPage({ params }: Props) {
  const { id } = use(params);
  const { data: company, isLoading, isError } = useCompany(id);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <CompanySettingsTabs companyId={id} />
        <div className="mt-6 space-y-3 animate-pulse">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-8 rounded bg-muted" />
          ))}
        </div>
      </div>
    );
  }

  if (isError || !company) {
    return (
      <div className="space-y-4">
        <CompanySettingsTabs companyId={id} />
        <p role="alert" className="mt-6 text-sm text-destructive">
          Failed to load regional settings.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <CompanySettingsTabs companyId={id} />
      <div className="mt-6">
        <h2 className="mb-4 text-base font-semibold text-foreground">Regional Settings</h2>
        <CompanyRegionalSettingsForm company={company} />
      </div>
    </div>
  );
}
