'use client';

/**
 * DomainReportsHub (Phase 8, T242–T247) — one domain's report hub
 * (`/analytics/sales`, `/analytics/finance`, …). The report sub-nav lists
 * **only** what discovery returns for this domain — a report the user
 * can't reach (not permitted, not entitled, or excluded under Installments'
 * Case B like `plan_performance`/`dashboard`) is simply absent, never a
 * disabled link that would leak its existence.
 */

import { useState } from 'react';
import { useReportDiscovery } from '@/hooks/reports/useReportDiscovery';
import { cn } from '@/lib/utils';
import type { ReportsDomainSection } from './domains';
import { ReportsPageHeader } from './PageHeader';
import { ReportView } from './ReportView';
import { EmptyState, ReportErrorState } from './states';
import { LoadingState } from './states/LoadingState';

export function DomainReportsHub({ section }: { section: ReportsDomainSection }): React.JSX.Element {
  const discovery = useReportDiscovery();
  const reports = (discovery.data?.reports ?? []).filter((r) => r.domain === section.domain);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const selected = reports.find((r) => r.key === selectedKey) ?? reports[0] ?? null;

  return (
    <div>
      <ReportsPageHeader title={`${section.label} reports`} />
      {discovery.isLoading ? (
        <LoadingState label="Loading reports…" />
      ) : discovery.isError ? (
        <ReportErrorState error={discovery.error} onRetry={() => void discovery.refetch()} />
      ) : !selected ? (
        <EmptyState
          title={`No ${section.label} reports available`}
          message="None are enabled for this company, or you don't have access to them."
        />
      ) : (
        <div className="flex flex-col gap-6 lg:flex-row">
          <nav aria-label={`${section.label} reports`} className="lg:w-56 lg:shrink-0">
            <ul className="space-y-0.5" role="list">
              {reports.map((report) => {
                const active = report.key === selected.key;
                return (
                  <li key={report.key}>
                    <button
                      type="button"
                      aria-current={active ? 'page' : undefined}
                      onClick={() => setSelectedKey(report.key)}
                      className={cn(
                        'w-full rounded-lg px-3 py-2 text-left text-sm transition-colors focus-visible:outline-2 focus-visible:outline-ring',
                        active
                          ? 'bg-primary/10 font-medium text-primary'
                          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                      )}
                    >
                      {report.name}
                    </button>
                  </li>
                );
              })}
            </ul>
          </nav>
          <div className="min-w-0 flex-1">
            <h2 className="mb-1 text-base font-semibold">{selected.name}</h2>
            <p className="mb-4 text-sm text-muted-foreground">{selected.description}</p>
            <ReportView key={selected.key} report={selected} />
          </div>
        </div>
      )}
    </div>
  );
}
