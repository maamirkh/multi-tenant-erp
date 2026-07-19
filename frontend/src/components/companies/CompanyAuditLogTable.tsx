/**
 * T095 — CompanyAuditLogTable.
 *
 * Renders a paginated table of audit log entries.
 * Columns: timestamp, actor, action, details (collapsible JSON before/after).
 * Shows loading skeleton and empty state.
 *
 * Spec ref: Epic 3, Phase 12 (T095).
 */

'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import type { AuditLogEntry } from '@/types/companies';

// ── Loading skeleton ───────────────────────────────────────────────────────────

function AuditLogSkeleton() {
  return (
    <div className="space-y-2 animate-pulse" aria-busy="true" aria-label="Loading audit log">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-10 rounded bg-muted" />
      ))}
    </div>
  );
}

// ── JSON Viewer ────────────────────────────────────────────────────────────────

interface JsonViewerProps {
  label: string;
  value: Record<string, unknown> | null;
}

function JsonViewer({ label, value }: JsonViewerProps) {
  const [open, setOpen] = useState(false);

  if (!value) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="text-xs text-primary underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-expanded={open}
      >
        {open ? 'Hide' : 'Show'} {label}
      </button>
      {open && (
        <pre className="mt-1 max-h-48 overflow-auto rounded bg-muted p-2 text-xs">
          {JSON.stringify(value, null, 2)}
        </pre>
      )}
    </div>
  );
}

// ── Row ────────────────────────────────────────────────────────────────────────

function AuditLogRow({ entry }: { entry: AuditLogEntry }) {
  const date = new Date(entry.created_at);
  const formatted = date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <tr className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors">
      <td className="py-2 pr-4 text-xs text-muted-foreground whitespace-nowrap align-top">
        <time dateTime={entry.created_at}>{formatted}</time>
      </td>
      <td className="py-2 pr-4 text-xs align-top">
        {entry.actor_user_id ?? <span className="text-muted-foreground">system</span>}
      </td>
      <td className="py-2 pr-4 align-top">
        <span className="inline-block rounded bg-muted px-1.5 py-0.5 text-xs font-mono font-medium">
          {entry.action}
        </span>
      </td>
      <td className="py-2 align-top space-y-1">
        <JsonViewer label="before" value={entry.before_state} />
        <JsonViewer label="after" value={entry.after_state} />
      </td>
    </tr>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

interface CompanyAuditLogTableProps {
  entries: AuditLogEntry[];
  isLoading?: boolean;
  page: number;
  pages: number;
  total: number;
  onPageChange: (page: number) => void;
}

export function CompanyAuditLogTable({
  entries,
  isLoading = false,
  page,
  pages,
  total,
  onPageChange,
}: CompanyAuditLogTableProps) {
  if (isLoading) {
    return <AuditLogSkeleton />;
  }

  if (entries.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        No audit log entries found.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm" aria-label="Audit log">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th scope="col" className="py-2 pr-4 text-left text-xs font-medium text-muted-foreground">
                Timestamp
              </th>
              <th scope="col" className="py-2 pr-4 text-left text-xs font-medium text-muted-foreground">
                Actor
              </th>
              <th scope="col" className="py-2 pr-4 text-left text-xs font-medium text-muted-foreground">
                Action
              </th>
              <th scope="col" className="py-2 text-left text-xs font-medium text-muted-foreground">
                Details
              </th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <AuditLogRow key={entry.id} entry={entry} />
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <p className="text-muted-foreground">
            Page {page} of {pages} ({total} entries)
          </p>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => onPageChange(page - 1)}
              aria-label="Previous page"
            >
              Previous
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={page >= pages}
              onClick={() => onPageChange(page + 1)}
              aria-label="Next page"
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
