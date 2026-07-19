/**
 * T074 — CompanyListPage.
 *
 * Uses useCompanies() hook; renders loading skeleton during fetch; renders
 * CompanyCard for each company; shows "Create Company" button; empty state
 * when no companies exist.
 *
 * Spec ref: Epic 3, Phase 11 (T074).
 */

'use client';

import Link from 'next/link';
import { buttonVariants } from '@/components/ui/button';
import { CompanyCard } from '@/components/companies/CompanyCard';
import { useCompanies } from '@/hooks/companies/useCompanies';
import { cn } from '@/lib/utils';
import { PlusIcon } from 'lucide-react';

function CompanyListSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true" aria-label="Loading companies">
      {Array.from({ length: 3 }).map((_, i) => (
        <div
          key={i}
          className="h-32 animate-pulse rounded-xl bg-muted"
          role="status"
          aria-label="Loading company"
        />
      ))}
    </div>
  );
}

export default function CompanyListPage() {
  const { data: companies, isLoading, isError, error } = useCompanies();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Companies</h1>
          <p className="text-sm text-muted-foreground">Manage your companies</p>
        </div>
        <Link
          href="/companies/new"
          aria-label="Create a new company"
          className={cn(buttonVariants(), 'gap-1.5')}
        >
          <PlusIcon className="size-4" />
          Create Company
        </Link>
      </div>

      {isLoading && <CompanyListSkeleton />}

      {isError && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          Failed to load companies: {error?.message ?? 'Unknown error'}
        </div>
      )}

      {!isLoading && !isError && companies && companies.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border py-16 text-center">
          <p className="text-sm font-medium text-foreground">No companies yet</p>
          <p className="mt-1 text-xs text-muted-foreground">Get started by creating your first company.</p>
          <Link href="/companies/new" className={cn(buttonVariants(), 'mt-4')}>
            Create Company
          </Link>
        </div>
      )}

      {!isLoading && !isError && companies && companies.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {companies.map((company) => (
            <CompanyCard key={company.id} company={company} />
          ))}
        </div>
      )}
    </div>
  );
}
