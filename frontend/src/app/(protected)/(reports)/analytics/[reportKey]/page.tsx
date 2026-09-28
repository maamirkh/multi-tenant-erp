"use client";

/**
 * `/analytics/[reportKey]` — generic detail route for any discoverable
 * report key (Epic 11, T239). Routing scaffold only: it resolves the key
 * against discovery (so an unknown, deferred or unauthorized key never
 * renders anything but a not-available state) and shows the report's
 * identity. Phase 8 renders the report data here.
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useReportDiscovery } from "@/hooks/reports/useReportDiscovery";
import { ReportsPageHeader } from "@/components/reports/PageHeader";
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
  if (!report) {
    return (
      <EmptyState
        title="Report not available"
        message="This report doesn't exist, isn't enabled for this company, or you don't have access to it."
      />
    );
  }
  return (
    <div>
      <ReportsPageHeader title={report.name} description={report.description} />
      <p className="text-sm text-muted-foreground">
        <Link href={ANALYTICS_BASE_PATH} className="underline underline-offset-4">
          Back to Reports &amp; Analytics
        </Link>
      </p>
    </div>
  );
}
