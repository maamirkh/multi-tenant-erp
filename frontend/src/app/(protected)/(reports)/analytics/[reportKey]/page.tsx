"use client";

/**
 * `/analytics/[reportKey]` — generic detail view for any discoverable
 * report key (Epic 11, T248), e.g. a drill-down target outside the six
 * domain hubs. The key is resolved against discovery first, so an unknown,
 * deferred or unauthorized key only ever renders a not-available state —
 * never a request for a report the user can't see. Filters come from the
 * report's own code-defined config (`reportConfigs.ts`).
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useReportDiscovery } from "@/hooks/reports/useReportDiscovery";
import { ReportsPageHeader } from "@/components/reports/PageHeader";
import { ReportView } from "@/components/reports/ReportView";
import { EmptyState, ReportErrorState } from "@/components/reports/states";
import { LoadingState } from "@/components/reports/states/LoadingState";
import { ANALYTICS_BASE_PATH } from "@/components/reports/domains";

export default function ReportDetailPage() {
  const params = useParams<{ reportKey: string }>();
  const reportKey = decodeURIComponent(params?.reportKey ?? "");
  const discovery = useReportDiscovery();
  const report = discovery.data?.reports.find((r) => r.key === reportKey);

  if (discovery.isLoading) return <LoadingState />;
  if (discovery.isError) {
    return <ReportErrorState error={discovery.error} onRetry={() => void discovery.refetch()} />;
  }
  if (!report || report.domain === "executive" || report.domain === "crossmodule") {
    // Composite reports have their own dedicated pages (Overview, Customer 360).
    return (
      <EmptyState
        title="Report not available"
        message="This report doesn't exist, isn't enabled for this company, or you don't have access to it."
      />
    );
  }
  return (
    <div>
      <ReportsPageHeader
        title={report.name}
        description={report.description}
        actions={
          <Link href={ANALYTICS_BASE_PATH} className="text-sm underline underline-offset-4">
            Back to Reports &amp; Analytics
          </Link>
        }
      />
      <ReportView report={report} />
    </div>
  );
}
