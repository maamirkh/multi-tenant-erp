"use client";

/**
 * `/analytics` — Executive Dashboard (Epic 11, T238 shell → T253 full UI).
 * Period + comparison selection drive the dedicated
 * `GET /reports/dashboard` call (presets resolved server-side in the
 * company's timezone); the 10 widgets render present / omitted (absent) /
 * unavailable distinctly via `DashboardWidgets`.
 */

import { useState } from "react";
import { useDashboard } from "@/hooks/reports/useDashboard";
import type { ComparisonType } from "@/lib/api/reports";
import { ComparisonSelector } from "@/components/reports/ComparisonSelector";
import { PeriodSelector, type PeriodValue } from "@/components/reports/PeriodSelector";
import { ReportsPageHeader } from "@/components/reports/PageHeader";
import { DashboardWidgets, dashboardWidgetViews } from "@/components/reports/DashboardWidgets";
import { EmptyState, ReportErrorState } from "@/components/reports/states";
import { LoadingState } from "@/components/reports/states/LoadingState";
import { formatPeriod } from "@/lib/format/date";

export default function AnalyticsOverviewPage() {
  const [period, setPeriod] = useState<PeriodValue>({ period: "this_month" });
  const [compare, setCompare] = useState<ComparisonType | null>(null);
  const ready = period.period !== "custom" || (!!period.customStart && !!period.customEnd);
  const dashboard = useDashboard({
    period: period.period,
    custom_start: period.customStart ?? null,
    custom_end: period.customEnd ?? null,
    compare,
  }, { enabled: ready });

  const anyVisible = dashboard.data
    ? dashboardWidgetViews(dashboard.data).some((w) => w.state !== "omitted")
    : false;

  return (
    <div>
      <ReportsPageHeader
        title="Reports & Analytics"
        description={dashboard.data ? formatPeriod(dashboard.data.period) : undefined}
        actions={
          <div className="flex flex-wrap items-end gap-2">
            <PeriodSelector value={period} onChange={setPeriod} />
            <ComparisonSelector value={compare} onChange={setCompare} />
          </div>
        }
      />
      {!ready ? (
        <p className="text-sm text-muted-foreground">Choose a start and end date.</p>
      ) : dashboard.isLoading ? (
        <LoadingState label="Loading overview…" />
      ) : dashboard.isError ? (
        <ReportErrorState error={dashboard.error} onRetry={() => void dashboard.refetch()} />
      ) : dashboard.data && anyVisible ? (
        <DashboardWidgets data={dashboard.data} />
      ) : (
        <EmptyState
          title="No overview figures available"
          message="None of the modules behind the overview are available to you for this company."
        />
      )}
    </div>
  );
}
