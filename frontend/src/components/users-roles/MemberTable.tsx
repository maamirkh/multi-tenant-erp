'use client';

/**
 * MemberTable — paginated, sortable, filterable table of company members.
 *
 * Columns: name/email, role, department, status, actions (view/edit).
 * Supports search, status filter, role filter, department filter, sorting,
 * and page-based pagination.
 *
 * Spec reference: Epic 4, Phase 11 (T094).
 */

import { useState } from 'react';
import Link from 'next/link';
import { useMembers } from '@/hooks/users-roles/useMembers';
import { useRoles } from '@/hooks/users-roles/useRoles';
import { MemberStatusBadge } from '@/components/users-roles/MemberStatusBadge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { MemberListParams, MembershipStatus, MemberSortBy } from '@/types/users-roles';

interface MemberTableProps {
  companyId: string;
  /** Base URL for member links, e.g. /companies/{id}/members */
  basePath: string;
}

const PAGE_SIZE = 20;

const STATUS_OPTIONS: { value: MembershipStatus | ''; label: string }[] = [
  { value: '', label: 'All statuses' },
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'suspended', label: 'Suspended' },
  { value: 'locked', label: 'Locked' },
  { value: 'pending_invitation', label: 'Pending' },
  { value: 'archived', label: 'Archived' },
];

const SORT_OPTIONS: { value: MemberSortBy; label: string }[] = [
  { value: 'name', label: 'Name' },
  { value: 'role_rank', label: 'Role' },
  { value: 'department', label: 'Department' },
  { value: 'created_at', label: 'Date added' },
];

export function MemberTable({ companyId, basePath }: MemberTableProps) {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<MembershipStatus | ''>('');
  const [roleFilter, setRoleFilter] = useState('');
  const [departmentFilter, setDepartmentFilter] = useState('');
  const [sortBy, setSortBy] = useState<MemberSortBy>('name');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [page, setPage] = useState(1);

  // Debouncing not required for Phase 11 — React Query handles duplicate requests.
  const params: MemberListParams = {
    page,
    page_size: PAGE_SIZE,
    sort_by: sortBy,
    sort_order: sortOrder,
    ...(search && { search }),
    ...(statusFilter && { status: statusFilter }),
    ...(roleFilter && { role_id: roleFilter }),
    ...(departmentFilter && { department: departmentFilter }),
  };

  const { data, isLoading, isError, error } = useMembers(companyId, params);
  const { data: roles } = useRoles(companyId);

  function handleSearch(value: string) {
    setSearch(value);
    setPage(1);
  }

  function handleStatusChange(value: string) {
    setStatusFilter(value as MembershipStatus | '');
    setPage(1);
  }

  function handleRoleChange(value: string) {
    setRoleFilter(value);
    setPage(1);
  }

  function handleDepartmentChange(value: string) {
    setDepartmentFilter(value);
    setPage(1);
  }

  function handleSort(column: MemberSortBy) {
    if (sortBy === column) {
      setSortOrder((o) => (o === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(column);
      setSortOrder('asc');
    }
    setPage(1);
  }

  function SortIndicator({ column }: { column: MemberSortBy }) {
    if (sortBy !== column) return <span className="text-muted-foreground/40 ml-1">↕</span>;
    return (
      <span className="ml-1 text-foreground" aria-hidden="true">
        {sortOrder === 'asc' ? '↑' : '↓'}
      </span>
    );
  }

  const totalPages = data ? Math.max(data.pages, 1) : 1;

  return (
    <div className="space-y-4">
      {/* Filters row */}
      <div className="flex flex-wrap gap-3">
        <Input
          type="search"
          placeholder="Search by name, email, or ID…"
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
          className="max-w-xs"
          aria-label="Search members"
        />

        <select
          value={statusFilter}
          onChange={(e) => handleStatusChange(e.target.value)}
          className="rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
          aria-label="Filter by status"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        <select
          value={roleFilter}
          onChange={(e) => handleRoleChange(e.target.value)}
          className="rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
          aria-label="Filter by role"
        >
          <option value="">All roles</option>
          {roles?.map((role) => (
            <option key={role.id} value={role.id}>
              {role.name}
            </option>
          ))}
        </select>

        <Input
          type="text"
          placeholder="Filter by department"
          value={departmentFilter}
          onChange={(e) => handleDepartmentChange(e.target.value)}
          className="max-w-48"
          aria-label="Filter by department"
        />

        <select
          value={`${sortBy}:${sortOrder}`}
          onChange={(e) => {
            const [col, ord] = e.target.value.split(':');
            setSortBy(col as MemberSortBy);
            setSortOrder(ord as 'asc' | 'desc');
            setPage(1);
          }}
          className="rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
          aria-label="Sort members"
        >
          {SORT_OPTIONS.flatMap((opt) => [
            <option key={`${opt.value}:asc`} value={`${opt.value}:asc`}>
              {opt.label} ↑
            </option>,
            <option key={`${opt.value}:desc`} value={`${opt.value}:desc`}>
              {opt.label} ↓
            </option>,
          ])}
        </select>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="space-y-2" aria-busy="true" aria-label="Loading members">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-12 animate-pulse rounded bg-muted" />
          ))}
        </div>
      ) : isError ? (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
        >
          {error?.message ?? 'Failed to load members'}
        </div>
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm" aria-label="Company members">
              <thead className="border-b border-border bg-muted/40">
                <tr>
                  <th
                    scope="col"
                    className="px-4 py-3 text-left font-medium text-muted-foreground cursor-pointer hover:text-foreground select-none"
                    onClick={() => handleSort('name')}
                    aria-sort={
                      sortBy === 'name'
                        ? sortOrder === 'asc'
                          ? 'ascending'
                          : 'descending'
                        : 'none'
                    }
                  >
                    Member <SortIndicator column="name" />
                  </th>
                  <th
                    scope="col"
                    className="px-4 py-3 text-left font-medium text-muted-foreground cursor-pointer hover:text-foreground select-none"
                    onClick={() => handleSort('role_rank')}
                    aria-sort={
                      sortBy === 'role_rank'
                        ? sortOrder === 'asc'
                          ? 'ascending'
                          : 'descending'
                        : 'none'
                    }
                  >
                    Role <SortIndicator column="role_rank" />
                  </th>
                  <th
                    scope="col"
                    className="px-4 py-3 text-left font-medium text-muted-foreground cursor-pointer hover:text-foreground select-none"
                    onClick={() => handleSort('department')}
                    aria-sort={
                      sortBy === 'department'
                        ? sortOrder === 'asc'
                          ? 'ascending'
                          : 'descending'
                        : 'none'
                    }
                  >
                    Department <SortIndicator column="department" />
                  </th>
                  <th
                    scope="col"
                    className="px-4 py-3 text-left font-medium text-muted-foreground"
                  >
                    Status
                  </th>
                  <th
                    scope="col"
                    className="px-4 py-3 text-right font-medium text-muted-foreground"
                  >
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data?.items.length === 0 ? (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-4 py-8 text-center text-muted-foreground"
                    >
                      No members found
                    </td>
                  </tr>
                ) : (
                  data?.items.map((member) => (
                    <tr
                      key={member.id}
                      className="hover:bg-muted/30 transition-colors"
                    >
                      <td className="px-4 py-3">
                        <div className="font-medium text-foreground">
                          {member.display_name}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {member.email}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-foreground">
                        {member.role.name}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {member.department ?? '—'}
                      </td>
                      <td className="px-4 py-3">
                        <MemberStatusBadge status={member.status} />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Link
                            href={`${basePath}/${member.id}`}
                            className="text-xs text-primary underline underline-offset-2 hover:text-primary/80"
                          >
                            View
                          </Link>
                          <Link
                            href={`${basePath}/${member.id}/edit`}
                            className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
                          >
                            Edit
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {data && data.pages > 1 && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                Page {data.page} of {data.pages} — {data.total} members
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => p - 1)}
                  disabled={page <= 1}
                  aria-label="Previous page"
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={page >= totalPages}
                  aria-label="Next page"
                >
                  Next
                </Button>
              </div>
            </div>
          )}

          {data && data.pages <= 1 && (
            <p className="text-sm text-muted-foreground">
              {data.total} member{data.total !== 1 ? 's' : ''}
            </p>
          )}
        </>
      )}
    </div>
  );
}
