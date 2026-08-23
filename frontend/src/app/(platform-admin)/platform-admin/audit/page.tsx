'use client';

/**
 * T200 — Platform Audit page. Requires `platform.audit.read`. Full
 * filter set over `GET /platform/audit`, paginated, strictly read-only
 * — no edit/delete affordance anywhere on this page (audit events are
 * immutable, plan.md §7 Architecture Freeze — Audit).
 */

import { useState } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { listAuditEvents } from '@/lib/api/platform-admin';
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

const PAGE_SIZE = 50;

export default function PlatformAuditPage(): React.JSX.Element {
  const [companyId, setCompanyId] = useState('');
  const [action, setAction] = useState('');
  const [targetType, setTargetType] = useState('');
  const [outcome, setOutcome] = useState('');
  const [createdAfter, setCreatedAfter] = useState('');
  const [createdBefore, setCreatedBefore] = useState('');
  const [page, setPage] = useState(1);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: [
      'platform',
      'audit',
      { companyId, action, targetType, outcome, createdAfter, createdBefore, page },
    ],
    queryFn: () =>
      listAuditEvents({
        company_id: companyId || undefined,
        action: action || undefined,
        target_type: targetType || undefined,
        outcome: (outcome || undefined) as 'success' | 'denied' | undefined,
        created_after: createdAfter ? new Date(createdAfter).toISOString() : undefined,
        created_before: createdBefore ? new Date(createdBefore).toISOString() : undefined,
        page,
        page_size: PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  });

  function resetPage(): void {
    setPage(1);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Platform Audit</h1>
        <p className="text-sm text-muted-foreground">Read-only. Every privileged Platform action is recorded here.</p>
      </div>

      <div className="flex flex-wrap gap-3">
        <Input
          placeholder="Company ID"
          value={companyId}
          onChange={(e) => { setCompanyId(e.target.value); resetPage(); }}
          className="max-w-48"
          aria-label="Filter by company id"
        />
        <Input
          placeholder="Action"
          value={action}
          onChange={(e) => { setAction(e.target.value); resetPage(); }}
          className="max-w-40"
          aria-label="Filter by action"
        />
        <Input
          placeholder="Target type"
          value={targetType}
          onChange={(e) => { setTargetType(e.target.value); resetPage(); }}
          className="max-w-40"
          aria-label="Filter by target type"
        />
        <select
          value={outcome}
          onChange={(e) => { setOutcome(e.target.value); resetPage(); }}
          aria-label="Filter by outcome"
          className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none"
        >
          <option value="">All Outcomes</option>
          <option value="success">Success</option>
          <option value="denied">Denied</option>
        </select>
        <Input
          type="datetime-local"
          value={createdAfter}
          onChange={(e) => { setCreatedAfter(e.target.value); resetPage(); }}
          aria-label="Created after"
        />
        <Input
          type="datetime-local"
          value={createdBefore}
          onChange={(e) => { setCreatedBefore(e.target.value); resetPage(); }}
          aria-label="Created before"
        />
      </div>

      {isLoading && <LoadingState />}
      {isError && isForbidden(error) && <PermissionDeniedState />}
      {isError && !isForbidden(error) && (
        <ErrorState message={messageFromError(error)} onRetry={() => void refetch()} />
      )}

      {data && data.items.length === 0 && <EmptyState message="No audit events match these filters." />}

      {data && data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="p-3">Action</th>
                  <th className="p-3">Target Type</th>
                  <th className="p-3">Actor</th>
                  <th className="p-3">Reason</th>
                  <th className="p-3">When</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((event) => (
                  <tr key={event.id} className="border-t border-border">
                    <td className="p-3">{event.action}</td>
                    <td className="p-3">{event.target_type}</td>
                    <td className="p-3 font-mono text-xs">
                      {event.actor_platform_administrator_id ?? '—'}
                    </td>
                    <td className="p-3 text-muted-foreground">{event.reason ?? '—'}</td>
                    <td className="p-3 text-muted-foreground">
                      {new Date(event.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <PaginationFooter page={data.page} pages={data.pages} total={data.total} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}
