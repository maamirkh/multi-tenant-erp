'use client';

/**
 * DataTable (T226) — the one table every Reports list page renders.
 *
 * - **Server-driven sort**: clicking a sortable header calls
 *   `onSortChange(field)`; the page re-queries with `sort=field`. The
 *   backend only accepts fields in the report's `sortable_fields`, so only
 *   columns marked `sortable` get a sort button. The active column carries
 *   `aria-sort`.
 * - **Pagination**: offset (`page`/`pageSize`/`total`) or cursor
 *   (`hasMore`/`onNext`, `accounting.gl` only).
 * - **Formatting**: per-column `money`/`percent`/`date`/`number`/`text`,
 *   display-only via `lib/format` (values stay the backend's strings).
 * - **Export**: `toolbar` is the integration point for `<ExportButton>`.
 *
 * Keyboard: every interactive control is a native `<button>`, so the table
 * is fully operable with Tab/Enter/Space; the `<caption>` names the table
 * for screen readers.
 */

import type { ReactNode } from 'react';
import { ArrowDownIcon, ArrowUpDownIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { formatDate } from '@/lib/format/date';
import { formatMoney, formatPercent, isNegativeAmount, MISSING_VALUE } from '@/lib/format/money';
import type { JsonValue, ReportRow } from '@/lib/api/reports';
import { cn } from '@/lib/utils';

export type ColumnFormat = 'text' | 'number' | 'money' | 'percent' | 'date';

export interface DataTableColumn {
  key: string;
  label: string;
  format?: ColumnFormat;
  /** Row field holding this money column's currency code, if any. */
  currencyKey?: string;
  /** Fixed currency for the whole column, when rows carry none. */
  currency?: string;
  sortable?: boolean;
  align?: 'left' | 'right';
}

export interface OffsetPagination {
  kind: 'offset';
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

export interface CursorPagination {
  kind: 'cursor';
  hasMore: boolean;
  /** True when a previous cursor page exists to return to. */
  hasPrevious: boolean;
  onNext: () => void;
  onPrevious: () => void;
}

export interface DataTableProps {
  caption: string;
  rows: ReportRow[];
  /** Omit to derive text columns from the first row's fields. */
  columns?: DataTableColumn[];
  pagination?: OffsetPagination | CursorPagination;
  sortField?: string | null;
  onSortChange?: (field: string | null) => void;
  toolbar?: ReactNode;
  isFetching?: boolean | undefined;
  timeZone?: string | undefined;
  emptyState?: ReactNode;
}

function humanize(key: string): string {
  return key.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
}

export function deriveColumns(rows: ReportRow[]): DataTableColumn[] {
  const first = rows[0];
  if (!first) return [];
  return Object.keys(first).map((key) => ({ key, label: humanize(key) }));
}

function asText(value: JsonValue | undefined): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function formatCell(
  column: DataTableColumn,
  row: ReportRow,
  timeZone = 'UTC'
): string {
  const raw = asText(row[column.key]);
  if (raw === null || raw === '') return MISSING_VALUE;
  switch (column.format) {
    case 'money': {
      const currency =
        column.currency ?? (column.currencyKey ? asText(row[column.currencyKey]) : null);
      return formatMoney(raw, currency);
    }
    case 'percent':
      return formatPercent(raw);
    case 'date':
      return formatDate(raw, timeZone);
    case 'number': {
      const parsed = Number(raw);
      return Number.isFinite(parsed) ? new Intl.NumberFormat().format(parsed) : raw;
    }
    default:
      return raw;
  }
}

function isNumeric(column: DataTableColumn): boolean {
  return column.format === 'money' || column.format === 'number' || column.format === 'percent';
}

function SortHeader({
  column,
  active,
  onSortChange,
}: {
  column: DataTableColumn;
  active: boolean;
  onSortChange: (field: string | null) => void;
}): React.JSX.Element {
  return (
    <button
      type="button"
      onClick={() => onSortChange(active ? null : column.key)}
      className="inline-flex items-center gap-1 rounded font-medium hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
    >
      {column.label}
      {active ? (
        <ArrowDownIcon className="size-3.5" aria-hidden="true" />
      ) : (
        <ArrowUpDownIcon className="size-3.5 opacity-50" aria-hidden="true" />
      )}
      <span className="sr-only">{active ? '(sorted — activate to clear)' : '(activate to sort)'}</span>
    </button>
  );
}

function PaginationBar({
  pagination,
  isFetching,
}: {
  pagination: OffsetPagination | CursorPagination;
  isFetching?: boolean | undefined;
}): React.JSX.Element {
  if (pagination.kind === 'cursor') {
    return (
      <nav aria-label="Pagination" className="flex items-center justify-end gap-2 pt-3">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!pagination.hasPrevious || isFetching}
          onClick={pagination.onPrevious}
        >
          Previous
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!pagination.hasMore || isFetching}
          onClick={pagination.onNext}
        >
          Next
        </Button>
      </nav>
    );
  }
  const pages = Math.max(1, Math.ceil(pagination.total / pagination.pageSize));
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-2 pt-3">
      <p className="text-xs text-muted-foreground" aria-live="polite">
        Page {pagination.page} of {pages} · {pagination.total} row{pagination.total === 1 ? '' : 's'}
      </p>
      <div className="flex gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={pagination.page <= 1 || isFetching}
          onClick={() => pagination.onPageChange(pagination.page - 1)}
        >
          Previous
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={pagination.page >= pages || isFetching}
          onClick={() => pagination.onPageChange(pagination.page + 1)}
        >
          Next
        </Button>
      </div>
    </nav>
  );
}

export function DataTable({
  caption,
  rows,
  columns,
  pagination,
  sortField = null,
  onSortChange,
  toolbar,
  isFetching,
  timeZone,
  emptyState,
}: DataTableProps): React.JSX.Element {
  const resolvedColumns = columns ?? deriveColumns(rows);

  return (
    <div className="space-y-2" aria-busy={isFetching || undefined}>
      {toolbar && <div className="flex flex-wrap items-center justify-end gap-2">{toolbar}</div>}
      {rows.length === 0 && emptyState ? (
        emptyState
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <caption className="sr-only">{caption}</caption>
            <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
              <tr>
                {resolvedColumns.map((column) => {
                  const active = sortField === column.key;
                  return (
                    <th
                      key={column.key}
                      scope="col"
                      aria-sort={active ? 'descending' : undefined}
                      className={cn('px-3 py-2', isNumeric(column) && 'text-right')}
                    >
                      {column.sortable && onSortChange ? (
                        <SortHeader column={column} active={active} onSortChange={onSortChange} />
                      ) : (
                        column.label
                      )}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={index} className="border-t border-border">
                  {resolvedColumns.map((column) => {
                    const negative =
                      column.format === 'money' && isNegativeAmount(asText(row[column.key]));
                    return (
                      <td
                        key={column.key}
                        className={cn(
                          'px-3 py-2',
                          (column.align === 'right' || isNumeric(column)) && 'text-right tabular-nums',
                          negative && 'text-destructive'
                        )}
                      >
                        {formatCell(column, row, timeZone)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {pagination && <PaginationBar pagination={pagination} isFetching={isFetching} />}
    </div>
  );
}
