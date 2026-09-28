"use client";

/**
 * `/analytics/customer-360/[customerId]` — Customer 360 shell (Epic 11,
 * T240). Wires the dedicated `GET /reports/customer-360/{id}` call and its
 * loading/error states; the four-section layout lands in Phase 9 (T254).
 */

import { useParams } from "next/navigation";
import { useCustomer360 } from "@/hooks/reports/useCustomer360";
import { ReportsPageHeader } from "@/components/reports/PageHeader";
import { ReportErrorState } from "@/components/reports/states";
import { LoadingState } from "@/components/reports/states/LoadingState";

export default function Customer360Page() {
  const params = useParams<{ customerId: string }>();
  const customerId = params?.customerId ?? "";
  const customer = useCustomer360(customerId);

  if (customer.isLoading) return <LoadingState label="Loading customer…" />;
  if (customer.isError) {
    return <ReportErrorState error={customer.error} onRetry={() => void customer.refetch()} />;
  }
  return (
    <ReportsPageHeader
      title={customer.data?.customer_name ?? "Customer 360"}
      description="Sales, receivables, CRM and installment exposure for this customer."
    />
  );
}
