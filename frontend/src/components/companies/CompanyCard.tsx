/**
 * T075 — CompanyCard component.
 *
 * Displays legal_name, status badge, country, default_currency, and created_at.
 * Links to /companies/{id}. Accessible with aria-labels on interactive elements.
 *
 * Spec ref: Epic 3, Phase 11 (T075).
 */

'use client';

import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CompanyStatusBadge } from '@/components/companies/CompanyStatusBadge';
import type { Company } from '@/types/companies';

interface CompanyCardProps {
  company: Company;
}

function formatDate(isoString: string): string {
  return new Date(isoString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function CompanyCard({ company }: CompanyCardProps) {
  return (
    <Link
      href={`/companies/${company.id}`}
      aria-label={`View details for ${company.legal_name}`}
      className="block rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      <Card className="transition-shadow hover:shadow-md">
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="truncate">{company.legal_name}</CardTitle>
            <CompanyStatusBadge status={company.status} />
          </div>
          {company.trade_name && (
            <p className="text-xs text-muted-foreground truncate">{company.trade_name}</p>
          )}
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <div>
              <dt className="sr-only">Country</dt>
              <dd>{company.country ?? '—'}</dd>
            </div>
            <div>
              <dt className="sr-only">Currency</dt>
              <dd>{company.default_currency ?? '—'}</dd>
            </div>
            <div className="col-span-2">
              <dt className="sr-only">Created</dt>
              <dd>Created {formatDate(company.created_at)}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>
    </Link>
  );
}
