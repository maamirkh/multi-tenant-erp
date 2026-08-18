/**
 * T079 — CompanyDetailPage.
 *
 * Uses useCompany(id) hook; displays all company profile fields in read-only
 * card layout; shows CompanyStatusBadge; shows CompanyStatusActions for owner.
 *
 * Spec ref: Epic 3, Phase 11 (T079).
 */

'use client';

import { use, useEffect } from 'react';
import Link from 'next/link';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CompanyStatusBadge } from '@/components/companies/CompanyStatusBadge';
import { CompanyStatusActions } from '@/components/companies/CompanyStatusActions';
import { useCompany } from '@/hooks/companies/useCompany';
import { useAuthContext } from '@/contexts/AuthContext';
import { useCompanyContext } from '@/contexts/CompanyContext';
import { cn } from '@/lib/utils';
import { ArrowLeftIcon } from 'lucide-react';

function DetailRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex justify-between py-2 border-b border-border last:border-b-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium text-foreground">{value ?? '—'}</span>
    </div>
  );
}

function CompanyDetailSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading company details">
      <div className="h-8 w-48 animate-pulse rounded bg-muted" />
      <div className="h-64 animate-pulse rounded-xl bg-muted" />
    </div>
  );
}

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function CompanyDetailPage({ params }: PageProps) {
  const { id } = use(params);
  const { data: company, isLoading, isError, error } = useCompany(id);
  const { user } = useAuthContext();
  const { setActiveCompany } = useCompanyContext();

  // Viewing a company's detail page marks it as the active company context
  // for the session — the mechanism every other module (Sales, Purchase,
  // Accounting, CRM) relies on to resolve "which company am I working with"
  // (persisted to localStorage by CompanyContext; consumed directly from
  // there, not via the React context, by modules outside this route group).
  useEffect(() => {
    if (company) {
      setActiveCompany(company);
    }
  }, [company, setActiveCompany]);

  if (isLoading) {
    return <CompanyDetailSkeleton />;
  }

  if (isError || !company) {
    return (
      <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
        {error?.message ?? 'Company not found'}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back navigation */}
      <Link
        href="/companies"
        aria-label="Back to Companies"
        className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'gap-1.5')}
      >
        <ArrowLeftIcon className="size-4" />
        Companies
      </Link>

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-xl font-semibold text-foreground">{company.legal_name}</h1>
          {company.trade_name && (
            <p className="text-sm text-muted-foreground">{company.trade_name}</p>
          )}
          <CompanyStatusBadge status={company.status} />
        </div>

        {user && (
          <CompanyStatusActions company={company} userId={user.user_id} />
        )}
      </div>

      {/* Profile card */}
      <Card>
        <CardHeader>
          <CardTitle>Company Profile</CardTitle>
        </CardHeader>
        <CardContent className="space-y-0">
          <DetailRow label="Legal Name" value={company.legal_name} />
          <DetailRow label="Trade Name" value={company.trade_name} />
          <DetailRow label="Email" value={company.email} />
          <DetailRow label="Slug" value={company.slug} />
          <DetailRow label="Country" value={company.country} />
          <DetailRow label="Currency" value={company.default_currency} />
          <DetailRow label="Timezone" value={company.default_timezone} />
          <DetailRow label="Language" value={company.default_language} />
          <DetailRow label="Business Type" value={company.business_type} />
          <DetailRow label="Phone" value={company.phone_primary} />
          <DetailRow label="Website" value={company.website} />
          <DetailRow label="Tax Number" value={company.tax_number} />
          <DetailRow label="Registration Number" value={company.registration_number} />
          <DetailRow label="Incorporation Date" value={company.incorporation_date} />
        </CardContent>
      </Card>

      {/* Settings navigation hint */}
      <p className="text-xs text-muted-foreground">
        Configure settings, branding, and addresses in the{' '}
        <Link href={`/companies/${id}/settings`} className="underline underline-offset-2 hover:text-foreground">
          Settings
        </Link>{' '}
        section.
      </p>
    </div>
  );
}
