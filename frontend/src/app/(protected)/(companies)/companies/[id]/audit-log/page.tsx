/**
 * T094 — /companies/[id]/audit-log.
 *
 * Company audit log page.
 * Filters: date range (date_from, date_to), action type.
 * Pagination via useCompanyAuditLog().
 * Renders CompanyAuditLogTable.
 *
 * Spec ref: Epic 3, Phase 12 (T094).
 */

'use client';

import { use, useState } from 'react';
import Link from 'next/link';
import { useCompanyAuditLog } from '@/hooks/companies/useCompanyAuditLog';
import { CompanyAuditLogTable } from '@/components/companies/CompanyAuditLogTable';
import { Input } from '@/components/ui/input';
import type { AuditLogParams } from '@/types/companies';

// ── Known action types ─────────────────────────────────────────────────────────

const ACTION_OPTIONS = [
  'company.created',
  'company.updated',
  'company.activated',
  'company.deactivated',
  'company.deleted',
  'company.restored',
  'company.logo_uploaded',
  'company.settings_updated',
  'company.address_created',
  'company.address_updated',
  'company.address_deleted',
];

// ── Component ─────────────────────────────────────────────────────────────────

interface Props {
  params: Promise<{ id: string }>;
}

export default function CompanyAuditLogPage({ params }: Props) {
  const { id } = use(params);

  const [page, setPage] = useState(1);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [action, setAction] = useState('');

  const filters: AuditLogParams = {
    page,
    page_size: 20,
    ...(dateFrom ? { date_from: dateFrom } : {}),
    ...(dateTo ? { date_to: dateTo } : {}),
    ...(action ? { action } : {}),
  };

  const { data: result, isLoading, isError } = useCompanyAuditLog(id, filters);

  function handleDateFrom(e: React.ChangeEvent<HTMLInputElement>) {
    setDateFrom(e.target.value);
    setPage(1);
  }

  function handleDateTo(e: React.ChangeEvent<HTMLInputElement>) {
    setDateTo(e.target.value);
    setPage(1);
  }

  function handleAction(e: React.ChangeEvent<HTMLSelectElement>) {
    setAction(e.target.value);
    setPage(1);
  }

  const entries = result?.data?.items ?? [];
  const pages = result?.data?.pages ?? 1;
  const total = result?.data?.total ?? 0;

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link href={`/companies/${id}`} className="hover:text-foreground">
          Company
        </Link>
        <span>/</span>
        <span className="text-foreground font-medium">Audit Log</span>
      </div>

      <h1 className="text-xl font-semibold text-foreground">Audit Log</h1>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="space-y-1">
          <label htmlFor="date_from" className="text-xs font-medium text-muted-foreground">
            From
          </label>
          <Input
            id="date_from"
            type="date"
            value={dateFrom}
            onChange={handleDateFrom}
            className="h-8 w-40 text-xs"
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="date_to" className="text-xs font-medium text-muted-foreground">
            To
          </label>
          <Input
            id="date_to"
            type="date"
            value={dateTo}
            onChange={handleDateTo}
            className="h-8 w-40 text-xs"
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="action_filter" className="text-xs font-medium text-muted-foreground">
            Action
          </label>
          <select
            id="action_filter"
            value={action}
            onChange={handleAction}
            className="h-8 rounded-lg border border-input bg-transparent px-2.5 py-1 text-xs outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            <option value="">All actions</option>
            {ACTION_OPTIONS.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Error state */}
      {isError && (
        <p role="alert" className="text-sm text-destructive">
          Failed to load audit log.
        </p>
      )}

      {/* Table */}
      <CompanyAuditLogTable
        entries={entries}
        isLoading={isLoading}
        page={page}
        pages={pages}
        total={total}
        onPageChange={setPage}
      />
    </div>
  );
}
