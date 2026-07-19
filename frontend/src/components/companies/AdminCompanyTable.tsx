/**
 * T082 — AdminCompanyTable component.
 *
 * Sortable table of companies with columns: legal_name, slug, status, country,
 * created_at. Row click navigates to company detail. Loading skeleton state.
 *
 * Spec ref: Epic 3, Phase 11 (T082).
 */

'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { CompanyStatusBadge } from '@/components/companies/CompanyStatusBadge';
import type { Company } from '@/types/companies';
import { ChevronUpIcon, ChevronDownIcon } from 'lucide-react';

type SortKey = 'legal_name' | 'slug' | 'status' | 'country' | 'created_at';
type SortDir = 'asc' | 'desc';

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function AdminCompanyTableSkeleton() {
  return (
    <div className="overflow-hidden rounded-xl border border-border" aria-busy="true" aria-label="Loading companies">
      <table className="w-full text-sm">
        <thead className="border-b border-border bg-muted/50">
          <tr>
            {['Company', 'Slug', 'Status', 'Country', 'Created'].map((h) => (
              <th key={h} className="px-4 py-3 text-left font-medium text-muted-foreground">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: 5 }).map((_, i) => (
            <tr key={i} className="border-b border-border last:border-b-0">
              {Array.from({ length: 5 }).map((__, j) => (
                <td key={j} className="px-4 py-3">
                  <div className="h-4 animate-pulse rounded bg-muted" />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface AdminCompanyTableProps {
  companies: Company[];
}

export function AdminCompanyTable({ companies }: AdminCompanyTableProps) {
  const router = useRouter();
  const [sortKey, setSortKey] = useState<SortKey>('created_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  }

  const sorted = [...companies].sort((a, b) => {
    const aVal = (a[sortKey] ?? '') as string;
    const bVal = (b[sortKey] ?? '') as string;
    const cmp = aVal.localeCompare(bVal);
    return sortDir === 'asc' ? cmp : -cmp;
  });

  function SortIcon({ col }: { col: SortKey }) {
    if (sortKey !== col) return <span className="ml-1 opacity-30"><ChevronUpIcon className="inline size-3" /></span>;
    return sortDir === 'asc'
      ? <ChevronUpIcon className="ml-1 inline size-3" />
      : <ChevronDownIcon className="ml-1 inline size-3" />;
  }

  const cols: { key: SortKey; label: string }[] = [
    { key: 'legal_name', label: 'Company' },
    { key: 'slug', label: 'Slug' },
    { key: 'status', label: 'Status' },
    { key: 'country', label: 'Country' },
    { key: 'created_at', label: 'Created' },
  ];

  return (
    <div className="overflow-hidden rounded-xl border border-border">
      <table className="w-full text-sm" aria-label="Companies table">
        <thead className="border-b border-border bg-muted/50">
          <tr>
            {cols.map(({ key, label }) => (
              <th
                key={key}
                scope="col"
                className="px-4 py-3 text-left font-medium text-muted-foreground"
              >
                <button
                  type="button"
                  onClick={() => handleSort(key)}
                  className="inline-flex items-center hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label={`Sort by ${label}`}
                >
                  {label}
                  <SortIcon col={key} />
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((company) => (
            <tr
              key={company.id}
              className="cursor-pointer border-b border-border last:border-b-0 hover:bg-muted/30 focus-within:bg-muted/30"
              onClick={() => router.push(`/companies/${company.id}`)}
              tabIndex={0}
              role="row"
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  router.push(`/companies/${company.id}`);
                }
              }}
              aria-label={`View ${company.legal_name}`}
            >
              <td className="px-4 py-3 font-medium text-foreground">{company.legal_name}</td>
              <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{company.slug}</td>
              <td className="px-4 py-3">
                <CompanyStatusBadge status={company.status} />
              </td>
              <td className="px-4 py-3 text-muted-foreground">{company.country ?? '—'}</td>
              <td className="px-4 py-3 text-muted-foreground">{formatDate(company.created_at)}</td>
            </tr>
          ))}

          {sorted.length === 0 && (
            <tr>
              <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                No companies found.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
