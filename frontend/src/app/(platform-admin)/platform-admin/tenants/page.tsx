'use client';

/**
 * T192 — Tenants list page. Requires `platform.tenants.read`.
 * Server-side paginated search/filter/sort; explicit empty state (not
 * an error) when a filtered search finds nothing.
 */

import { useState } from 'react';
import Link from 'next/link';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { listTenants } from '@/lib/api/platform-admin';
import { Input } from '@/components/ui/input';
import {
  LoadingState,
  ErrorState,
  EmptyState,
  PermissionDeniedState,
  PaginationFooter,
  messageFromError,
  isForbidden,
} from '@/components/platform-admin/DataState';

const STATUS_OPTIONS = [
  { value: '', label: 'All Statuses' },
  { value: 'pending_setup', label: 'Pending Setup' },
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'suspended', label: 'Suspended' },
  { value: 'deleted', label: 'Deleted' },
];

const PAGE_SIZE = 20;

export default function PlatformTenantsPage(): React.JSX.Element {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(1);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['platform', 'tenants', { search, status, sortBy, sortOrder, page }],
    queryFn: () =>
      listTenants({
        search: search || undefined,
        status: status || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
        page,
        page_size: PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  });

  function toggleSort(field: string): void {
    if (sortBy === field) {
      setSortOrder((o) => (o === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(field);
      setSortOrder('asc');
    }
    setPage(1);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Tenants</h1>
        <p className="text-sm text-muted-foreground">Search and inspect every tenant on the platform.</p>
      </div>

      <div className="flex flex-wrap gap-3">
        <Input
          type="search"
          placeholder="Search by name or slug…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="max-w-xs"
          aria-label="Search tenants"
        />
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
          aria-label="Filter by status"
          className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {isLoading && <LoadingState />}

      {isError && isForbidden(error) && <PermissionDeniedState />}
      {isError && !isForbidden(error) && (
        <ErrorState message={messageFromError(error)} onRetry={() => void refetch()} />
      )}

      {data && data.items.length === 0 && (
        <EmptyState message="No tenants match your search." />
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="p-3">
                    <button type="button" onClick={() => toggleSort('legal_name')} className="hover:underline">
                      Name {sortBy === 'legal_name' && (sortOrder === 'asc' ? '↑' : '↓')}
                    </button>
                  </th>
                  <th className="p-3">Slug</th>
                  <th className="p-3">
                    <button type="button" onClick={() => toggleSort('status')} className="hover:underline">
                      Status {sortBy === 'status' && (sortOrder === 'asc' ? '↑' : '↓')}
                    </button>
                  </th>
                  <th className="p-3">Country</th>
                  <th className="p-3">
                    <button type="button" onClick={() => toggleSort('created_at')} className="hover:underline">
                      Created {sortBy === 'created_at' && (sortOrder === 'asc' ? '↑' : '↓')}
                    </button>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((tenant) => (
                  <tr key={tenant.id} className="border-t border-border">
                    <td className="p-3">
                      <Link
                        href={`/platform-admin/tenants/${tenant.id}`}
                        className="font-medium text-primary hover:underline"
                      >
                        {tenant.legal_name}
                      </Link>
                    </td>
                    <td className="p-3 text-muted-foreground">{tenant.slug}</td>
                    <td className="p-3">{tenant.status}</td>
                    <td className="p-3 text-muted-foreground">{tenant.country ?? '—'}</td>
                    <td className="p-3 text-muted-foreground">
                      {new Date(tenant.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <PaginationFooter
            page={data.page}
            pages={data.pages}
            total={data.total}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}
