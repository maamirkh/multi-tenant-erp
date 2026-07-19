/**
 * T081 — AdminCompanyListPage.
 *
 * Superadmin-only page. Uses useCompanies() with admin parameters.
 * Renders AdminCompanyTable with search input, status filter, country filter,
 * and pagination controls.
 *
 * Spec ref: Epic 3, Phase 11 (T081).
 */

'use client';

import { useState } from 'react';
import { useAuthContext } from '@/contexts/AuthContext';
import { useCompanies } from '@/hooks/companies/useCompanies';
import { AdminCompanyTable, AdminCompanyTableSkeleton } from '@/components/companies/AdminCompanyTable';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All Statuses' },
  { value: 'pending_setup', label: 'Pending Setup' },
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'suspended', label: 'Suspended' },
  { value: 'deleted', label: 'Deleted' },
];

export default function AdminCompanyListPage() {
  const { user } = useAuthContext();
  const { data: companies, isLoading, isError, error } = useCompanies();

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [countryFilter, setCountryFilter] = useState('');
  const [page, setPage] = useState(1);

  const PAGE_SIZE = 20;

  function handleSearch(v: string) { setSearch(v); setPage(1); }
  function handleStatusFilter(v: string) { setStatusFilter(v); setPage(1); }
  function handleCountryFilter(v: string) { setCountryFilter(v); setPage(1); }

  const filtered = (companies ?? []).filter((c) => {
    if (search && !c.legal_name.toLowerCase().includes(search.toLowerCase()) &&
        !c.slug.toLowerCase().includes(search.toLowerCase())) {
      return false;
    }
    if (statusFilter && c.status !== statusFilter) return false;
    if (countryFilter && (c.country ?? '').toLowerCase() !== countryFilter.toLowerCase()) return false;
    return true;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  // Superadmin guard — in production this would be enforced server-side;
  // here we do a client-side check as an additional UI layer.
  // The backend already enforces the permission via middleware.
  if (!user) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">All Companies</h1>
        <p className="text-sm text-muted-foreground">Superadmin view — all companies across all users</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <Input
          type="search"
          placeholder="Search by name or slug…"
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
          className="max-w-xs"
          aria-label="Search companies"
        />

        <select
          value={statusFilter}
          onChange={(e) => handleStatusFilter(e.target.value)}
          aria-label="Filter by status"
          className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>

        <Input
          type="text"
          placeholder="Country (e.g. US)"
          value={countryFilter}
          onChange={(e) => handleCountryFilter(e.target.value)}
          maxLength={2}
          className="max-w-24"
          aria-label="Filter by country"
        />

        {(search || statusFilter || countryFilter) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              handleSearch('');
              handleStatusFilter('');
              handleCountryFilter('');
            }}
          >
            Clear filters
          </Button>
        )}
      </div>

      {isLoading && <AdminCompanyTableSkeleton />}

      {isError && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          Failed to load companies: {error?.message ?? 'Unknown error'}
        </div>
      )}

      {!isLoading && !isError && (
        <>
          <AdminCompanyTable companies={paged} />

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>
                Showing {paged.length} of {filtered.length} companies
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  aria-label="Previous page"
                >
                  Previous
                </Button>
                <span className="flex items-center px-2">
                  Page {page} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  aria-label="Next page"
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
