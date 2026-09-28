"use client";

/**
 * `/analytics/customer-360/[customerId]` — Customer 360 (Epic 11, T240
 * shell → T255 full UI), via the dedicated `GET /reports/customer-360/{id}`.
 *
 * IDOR safety (T256/T257): the backend returns the identical `NOT_FOUND`
 * for a customer that doesn't exist and one that belongs to another tenant;
 * this page maps that (and a malformed id) to the app's standard not-found
 * page via `notFound()`. Nothing identifying — not even the id from the URL
 * — is rendered until the backend has confirmed the customer, so there is
 * no transient identity flash for a cross-tenant id.
 */

import { notFound, useParams } from "next/navigation";
import { useCustomer360 } from "@/hooks/reports/useCustomer360";
import {
  Customer360Sections,
  isCustomerNotFound,
} from "@/components/reports/Customer360Sections";
import { ReportsPageHeader } from "@/components/reports/PageHeader";
import { ReportErrorState } from "@/components/reports/states";
import { LoadingState } from "@/components/reports/states/LoadingState";

export default function Customer360Page() {
  const params = useParams<{ customerId: string }>();
  const customerId = params?.customerId ?? "";
  const customer = useCustomer360(customerId);

  if (customer.isError && isCustomerNotFound(customer.error)) notFound();
  if (customer.isLoading || (!customer.data && !customer.isError)) {
    return <LoadingState label="Loading customer…" />;
  }
  if (customer.isError || !customer.data) {
    return <ReportErrorState error={customer.error} onRetry={() => void customer.refetch()} />;
  }
  return (
    <div>
      <ReportsPageHeader
        title={customer.data.customer_name}
        description="This customer's activity across the modules available to you."
      />
      <Customer360Sections data={customer.data} />
    </div>
  );
}
