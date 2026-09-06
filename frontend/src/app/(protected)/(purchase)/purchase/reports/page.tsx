"use client";

/**
 * Purchase Reports Hub — T224
 * Navigation cards for all 14 purchase reports.
 */

import Link from "next/link";
import { useParams } from "next/navigation";

const REPORTS = [
  {
    code: "RPT-01",
    title: "Purchase Order Summary",
    description: "All purchase orders with status, supplier, value, and dates.",
    href: "purchase-order-summary",
  },
  {
    code: "RPT-02",
    title: "Pending Purchase Orders",
    description: "Approved/partially-received POs sorted by expected delivery date.",
    href: "pending-purchase-orders",
  },
  {
    code: "RPT-03",
    title: "Overdue Deliveries",
    description: "POs past expected delivery date with no full receipt.",
    href: "overdue-deliveries",
  },
  {
    code: "RPT-04",
    title: "Goods Receipt Report",
    description: "Confirmed goods receipts in period with quantities and cost.",
    href: "goods-receipt-report",
  },
  {
    code: "RPT-05",
    title: "Purchase Request Status",
    description: "All purchase requests with status, age, and requestor.",
    href: "purchase-request-status",
  },
  {
    code: "RPT-06",
    title: "Supplier Performance",
    description: "On-time rate, fill rate, rejection rate, and composite rating per supplier.",
    href: "supplier-performance",
  },
  {
    code: "RPT-07",
    title: "Vendor Return Report",
    description: "All RMAs in period with status, amounts, and reasons.",
    href: "vendor-return-report",
  },
  {
    code: "RPT-08",
    title: "Purchase by Supplier",
    description: "Total spend per supplier from confirmed goods receipts.",
    href: "purchase-by-supplier",
  },
  {
    code: "RPT-09",
    title: "Purchase by Category",
    description: "Total spend grouped by supplier category.",
    href: "purchase-by-category",
  },
  {
    code: "RPT-10",
    title: "Purchase Price Variance",
    description: "GR vs PO unit cost variance per line, sorted by absolute PPV.",
    href: "purchase-price-variance",
  },
  {
    code: "RPT-11",
    title: "Open Purchase Commitments",
    description: "Open value (ordered − received) per PO line, grouped by supplier.",
    href: "open-purchase-commitments",
  },
  {
    code: "RPT-12",
    title: "Purchase Trend Analysis",
    description: "Monthly/quarterly aggregation of purchase volume and value.",
    href: "purchase-trend-analysis",
  },
  {
    code: "RPT-13",
    title: "Goods Rejection Analysis",
    description: "Rejected GR lines grouped by supplier, reason code, and product.",
    href: "goods-rejection-analysis",
  },
  {
    code: "RPT-14",
    title: "Procurement Audit Trail",
    description: "Full event history per document or supplier.",
    href: "procurement-audit-trail",
  },
];

export default function ReportsHubPage() {
  const params = useParams<{ companyId: string }>();
  const companyId = params?.companyId ?? "";

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Purchase Reports</h1>
          <p className="mt-1 text-sm text-gray-500">
            Procurement intelligence across 14 report categories
          </p>
        </div>
        <Link
          href={`/companies/${companyId}/purchase/reports/kpis`}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          KPI Dashboard
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {REPORTS.map((report) => (
          <Link
            key={report.code}
            href={`/companies/${companyId}/purchase/reports/${report.href}`}
            className="group block rounded-lg border border-gray-200 bg-white p-5 shadow-sm transition hover:border-blue-400 hover:shadow-md"
          >
            <div className="mb-2 flex items-center gap-2">
              <span className="rounded bg-blue-50 px-2 py-0.5 text-xs font-semibold text-blue-700">
                {report.code}
              </span>
            </div>
            <h3 className="font-semibold text-gray-900 group-hover:text-blue-600">
              {report.title}
            </h3>
            <p className="mt-1 text-sm text-gray-500">{report.description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
