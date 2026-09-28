'use client';

/**
 * DomainReportsShell (T239) — routing scaffold for one domain section
 * (`/analytics/sales`, `/analytics/finance`, …). Lists the reports the
 * user can reach in that domain, straight from discovery; each links to
 * the generic `/analytics/[reportKey]` view. Phase 8 builds the real
 * per-domain pages on top of this.
 */

import Link from 'next/link';
import { useReportDiscovery } from '@/hooks/reports/useReportDiscovery';
import { reportHref, type ReportsDomainSection } from './domains';
import { ReportsPageHeader } from './PageHeader';
import { EmptyState, ReportErrorState } from './states';
import { LoadingState } from './states/LoadingState';

export function DomainReportsShell({
  section,
}: {
  section: ReportsDomainSection;
}): React.JSX.Element {
  const discovery = useReportDiscovery();
  const reports = (discovery.data?.reports ?? []).filter((r) => r.domain === section.domain);

  return (
    <div>
      <ReportsPageHeader title={`${section.label} reports`} />
      {discovery.isLoading ? (
        <LoadingState label="Loading reports…" />
      ) : discovery.isError ? (
        <ReportErrorState error={discovery.error} onRetry={() => void discovery.refetch()} />
      ) : reports.length === 0 ? (
        <EmptyState
          title={`No ${section.label} reports available`}
          message="None are enabled for this company, or you don't have access to them."
        />
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" role="list">
          {reports.map((report) => (
            <li key={report.key}>
              <Link
                href={reportHref(report.key)}
                className="block h-full rounded-lg border border-border p-4 transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
              >
                <p className="text-sm font-medium">{report.name}</p>
                <p className="mt-1 text-xs text-muted-foreground">{report.description}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
