"use client";

/**
 * `/analytics` — Reports & Analytics Overview shell (Epic 11, T238).
 * Data-fetching wiring only: period + comparison selection drive the
 * dedicated `GET /reports/dashboard` call with loading/error states. The
 * full 10-widget layout lands in Phase 9 (T256).
 */

import { useState } from "react";
import { useDashboard } from "@/hooks/reports/useDashboard";
import type { ComparisonType, ExecutiveDashboardResponse } from "@/lib/api/reports";
import { ComparisonSelector } from "@/components/reports/ComparisonSelector";
import { PeriodSelector, type PeriodValue } from "@/components/reports/PeriodSelector";
import { ReportsPageHeader } from "@/components/reports/PageHeader";
import { ReportErrorState } from "@/components/reports/states";
import { LoadingState } from "@/components/reports/states/LoadingState";
import { formatPeriod } from "@/lib/format/date";

const WIDGET_KEYS = [
  "net_sales",
  "gross_sales",
  "purchase_spend",
  "ar",
  "ap",
  "cash_position",
  "operational_inventory_value",
  "crm_pipeline",
  "installment_exposure",
  "gross_profit_margin",
] as const satisfies readonly (keyof ExecutiveDashboardResponse)[];

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

  const presentCount = dashboard.data
    ? WIDGET_KEYS.filter((key) => dashboard.data[key].state === "present").length
    : 0;

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
      ) : (
        <p className="text-sm text-muted-foreground" data-testid="overview-widget-count">
          {presentCount} of {WIDGET_KEYS.length} overview figures available for this period.
        </p>
      )}
    </div>
  );
}
