'use client';

/**
 * ReportView (Phase 8, T242–T248) — renders any one registered report:
 * code-defined filters (`reportConfigs.ts`) → the unified
 * `GET /reports/{report_key}` endpoint → the right presentation for its
 * pagination style (offset table, GL cursor "Load more", or aggregate).
 *
 * - Export offers exactly the formats discovery lists for this report, in
 *   the exact filter scope currently applied (never a broader one).
 * - Saved views apply through `loadSavedView()` (re-validated server-side).
 * - Installments reports served under servicing continuity (Case B) show a
 *   read-only banner from `report_meta`.
 * - A required filter that isn't filled yet shows a prompt instead of
 *   sending a request the backend would reject.
 * - Drill-down (`meta.drill_down`): row-level links in the table, and
 *   report-level links (no per-row id) once above it.
 */

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { InfoIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  isCursorPage,
  isPaginatedData,
  type DrillDownRef,
  type JsonValue,
  type ReportDiscoveryItem,
  type ReportRow,
} from '@/lib/api/reports';
import { useCursorReport, useReport } from '@/hooks/reports/useReport';
import { useFilterLookups } from '@/hooks/reports/useFilterLookups';
import { AggregateView } from './AggregateView';
import { DataTable } from './DataTable';
import { splitDrillDowns } from './drillDown';
import { ExportButton } from './ExportButton';
import { FilterBar, toReportFilters, type FilterField, type FilterValues } from './FilterBar';
import { configFor, missingRequiredFilters, type FilterLookup } from './reportConfigs';
import { SavedViewSelector } from './SavedViewSelector';
import { EmptyState, ReportErrorState } from './states';
import { LoadingState } from './states/LoadingState';

export const REPORT_PAGE_SIZE = 20;
const GL_REPORT_KEY = 'accounting.gl';

function ServicingContinuityBanner(): React.JSX.Element {
  return (
    <div
      role="status"
      data-testid="servicing-continuity-banner"
      className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100"
    >
      <InfoIcon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <p>
        <span className="font-medium">Read-only servicing view.</span> Installments is not enabled
        for new contracts, but existing contracts are still shown so they can be serviced.
      </p>
    </div>
  );
}

function Disclaimer({ text }: { text: string }): React.JSX.Element {
  return (
    <p
      data-testid="report-disclaimer"
      className="flex items-start gap-2 rounded-lg border border-border bg-muted/40 p-3 text-sm"
    >
      <InfoIcon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      {text}
    </p>
  );
}

function ReportLinks({ links }: { links: DrillDownRef[] }): React.JSX.Element | null {
  if (links.length === 0) return null;
  return (
    <nav aria-label="Related records" className="flex flex-wrap gap-3 text-sm">
      {links.map((ref) => (
        <Link key={ref.target_route} href={ref.target_route} className="underline underline-offset-4">
          {ref.label}
        </Link>
      ))}
    </nav>
  );
}

function valuesFromSavedView(config: Record<string, JsonValue>): FilterValues {
  const values: FilterValues = {};
  for (const [key, value] of Object.entries(config)) {
    if (value !== null && value !== undefined && typeof value !== 'object') values[key] = String(value);
  }
  return values;
}

function useResolvedFields(fields: ReturnType<typeof configFor>['filters']): FilterField[] {
  const lookups = useMemo(
    () => [...new Set(fields.flatMap((f) => (f.lookup ? [f.lookup] : [])))] as FilterLookup[],
    [fields]
  );
  const options = useFilterLookups(lookups);
  return fields.map(({ lookup, ...field }) => {
    if (!lookup) return field;
    const loaded = options[lookup];
    // Lookup unavailable (e.g. no Accounting permission) → plain ID input.
    return loaded ? { ...field, type: 'select', options: loaded } : { ...field, type: 'text', placeholder: 'UUID' };
  });
}

function OffsetOrAggregate({
  reportKey,
  filters,
  enabled,
  caption,
  columns,
  exportSlot,
  onMeta,
}: {
  reportKey: string;
  filters: FilterValues;
  enabled: boolean;
  caption: string;
  columns: ReturnType<typeof configFor>['columns'];
  exportSlot: React.ReactNode;
  onMeta: (servicingContinuity: boolean) => React.ReactNode;
}): React.JSX.Element {
  const [page, setPage] = useState(1);
  const [lastFilters, setLastFilters] = useState(filters);
  if (lastFilters !== filters) {
    setLastFilters(filters);
    setPage(1);
  }
  const query = useReport(
    reportKey,
    { filters: toReportFilters(filters), page, page_size: REPORT_PAGE_SIZE },
    { enabled }
  );

  if (!enabled) return <></>;
  if (query.isLoading) return <LoadingState />;
  if (query.isError) return <ReportErrorState error={query.error} onRetry={() => void query.refetch()} />;
  if (!query.data) return <></>;

  const { data, report_meta: meta } = query.data;
  const timeZone = meta.period.timezone;
  const banner = onMeta(meta.read_only_servicing_continuity);
  const { rowLinks, reportLinks } = splitDrillDowns(meta.drill_down);

  if (isPaginatedData(data)) {
    return (
      <div className="space-y-3">
        {banner}
        <ReportLinks links={reportLinks} />
        <DataTable
          rowLinks={rowLinks}
          caption={caption}
          rows={data.items}
          columns={columns}
          timeZone={timeZone}
          isFetching={query.isFetching}
          toolbar={exportSlot}
          emptyState={<EmptyState />}
          pagination={{
            kind: 'offset',
            page: data.page,
            pageSize: data.page_size,
            total: data.total,
            onPageChange: setPage,
          }}
        />
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {banner}
      <div className="flex justify-end">{exportSlot}</div>
      <AggregateView data={data as { [key: string]: JsonValue }} timeZone={timeZone} />
    </div>
  );
}

function CursorTable({
  reportKey,
  filters,
  enabled,
  caption,
  columns,
  exportSlot,
}: {
  reportKey: string;
  filters: FilterValues;
  enabled: boolean;
  caption: string;
  columns: ReturnType<typeof configFor>['columns'];
  exportSlot: React.ReactNode;
}): React.JSX.Element {
  const query = useCursorReport(reportKey, { filters: toReportFilters(filters), page_size: 100 }, { enabled });
  if (!enabled) return <></>;
  if (query.isLoading) return <LoadingState />;
  if (query.isError) return <ReportErrorState error={query.error} onRetry={() => void query.refetch()} />;
  const rows: ReportRow[] = (query.data?.pages ?? []).flatMap((p) => (isCursorPage(p.data) ? p.data.items : []));
  const { rowLinks, reportLinks } = splitDrillDowns(query.data?.pages[0]?.report_meta.drill_down);
  return (
    <div className="space-y-3">
      <ReportLinks links={reportLinks} />
      <DataTable
        rowLinks={rowLinks}
        caption={caption}
        rows={rows}
        columns={columns}
        toolbar={exportSlot}
        isFetching={query.isFetching}
        emptyState={<EmptyState />}
      />
      {query.hasNextPage && (
        <div className="flex justify-center">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={query.isFetchingNextPage}
            onClick={() => void query.fetchNextPage()}
          >
            {query.isFetchingNextPage ? 'Loading…' : 'Load more'}
          </Button>
        </div>
      )}
    </div>
  );
}

export function ReportView({ report }: { report: ReportDiscoveryItem }): React.JSX.Element {
  const config = configFor(report.key);
  const [filters, setFilters] = useState<FilterValues>(config.defaults ?? {});
  const fields = useResolvedFields(config.filters);
  const missing = missingRequiredFilters(config, filters);
  const enabled = missing.length === 0;

  const exportSlot = report.exportable ? (
    <ExportButton
      reportKey={report.key}
      formats={report.export_formats}
      filters={toReportFilters(filters)}
    />
  ) : null;

  return (
    <section aria-label={report.name} className="space-y-4">
      <div className="space-y-3 rounded-lg border border-border p-4">
        <FilterBar
          fields={fields}
          values={filters}
          onApply={setFilters}
          onReset={() => setFilters(config.defaults ?? {})}
        />
        <SavedViewSelector
          reportKey={report.key}
          currentFilters={filters}
          onApply={(view) => setFilters(valuesFromSavedView(view.filter_config))}
        />
      </div>
      {config.disclaimer && <Disclaimer text={config.disclaimer} />}
      {!enabled && (
        <p role="status" className="text-sm text-muted-foreground" data-testid="missing-filters">
          Fill in {missing.join(', ')} to run this report.
        </p>
      )}
      {report.key === GL_REPORT_KEY ? (
        <CursorTable
          reportKey={report.key}
          filters={filters}
          enabled={enabled}
          caption={report.name}
          columns={config.columns}
          exportSlot={exportSlot}
        />
      ) : (
        <OffsetOrAggregate
          reportKey={report.key}
          filters={filters}
          enabled={enabled}
          caption={report.name}
          columns={config.columns}
          exportSlot={exportSlot}
          onMeta={(servicing) => (servicing ? <ServicingContinuityBanner /> : null)}
        />
      )}
    </section>
  );
}
