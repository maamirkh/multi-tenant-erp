"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getKPIDashboard, KPIResult, KPIDashboard } from "@/lib/api/sales";

// ---------------------------------------------------------------------------
// KPI card component
// ---------------------------------------------------------------------------

function KPICard({ kpi }: { kpi: KPIResult }) {
  const trendColor =
    kpi.trend === "UP"
      ? "text-green-600"
      : kpi.trend === "DOWN"
      ? "text-red-600"
      : "text-gray-500";
  const trendIcon =
    kpi.trend === "UP" ? "↑" : kpi.trend === "DOWN" ? "↓" : "→";

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
        {kpi.kpi_id}
      </p>
      <p className="mt-1 text-sm font-semibold text-gray-700">{kpi.name}</p>
      <div className="mt-3 flex items-end justify-between">
        <span className="text-2xl font-bold text-gray-900">
          {kpi.value !== null && kpi.value !== undefined
            ? `${kpi.value} ${kpi.unit}`
            : "N/A"}
        </span>
        {kpi.trend && (
          <span className={`text-sm font-medium ${trendColor}`}>
            {trendIcon}{" "}
            {kpi.change_pct !== null && kpi.change_pct !== undefined
              ? `${kpi.change_pct}%`
              : ""}
          </span>
        )}
      </div>
      <p className="mt-1 text-xs text-gray-400">{kpi.period_label}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Report navigation links
// ---------------------------------------------------------------------------

const REPORT_LINKS = [
  { label: "Sales Summary", type: "sales_summary" },
  { label: "Sales by Customer", type: "sales_by_customer" },
  { label: "Sales by Product", type: "sales_by_product" },
  { label: "Sales by Representative", type: "sales_by_representative" },
  { label: "Order Pipeline", type: "sales_order_pipeline" },
  { label: "Top Customers", type: "top_customers" },
  { label: "Sales Trend", type: "sales_trend" },
  { label: "Customer List", type: "customer_list" },
  { label: "Customer Ageing", type: "customer_ageing" },
  { label: "Customer Activity", type: "customer_activity" },
  { label: "New Customers", type: "new_customers" },
  { label: "Customer Credit Report", type: "customer_credit_report" },
  { label: "Quotation Conversion Rate", type: "quotation_conversion_rate" },
  { label: "Quotation Pipeline", type: "quotation_pipeline" },
  { label: "Expired Quotations", type: "expired_quotations" },
  { label: "Pending Deliveries", type: "pending_deliveries" },
  { label: "Delivery Performance", type: "delivery_performance" },
  { label: "Backorder Report", type: "backorder_report" },
  { label: "Gross Margin by Product", type: "gross_margin_by_product" },
  { label: "Gross Margin by Customer", type: "gross_margin_by_customer" },
  { label: "Discount Analysis", type: "discount_analysis" },
  { label: "Sales Audit Trail", type: "sales_audit_trail" },
  { label: "Price Override Report", type: "price_override_report" },
  { label: "Credit Limit Changes", type: "credit_limit_change_report" },
  { label: "Approval History", type: "approval_history" },
] as const;

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function SalesReportsPage() {
  const [dashboard, setDashboard] = useState<KPIDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [_companyId, setCompanyId] = useState<string>("");

  useEffect(() => {
    // Retrieve companyId from session/local storage or URL
    const stored = localStorage.getItem("companyId") ?? "";
    setCompanyId(stored);
    if (!stored) {
      setLoading(false);
      setError("No company selected.");
      return;
    }
    getKPIDashboard(stored)
      .then((res) => {
        setDashboard(res.data);
      })
      .catch((err) => {
        setError(err?.message ?? "Failed to load KPIs");
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Sales Intelligence</h1>
        <p className="mt-1 text-sm text-gray-500">
          KPI dashboard and report library
        </p>
      </div>

      {/* KPI Dashboard */}
      <section>
        <h2 className="text-lg font-semibold text-gray-700 mb-4">
          Key Performance Indicators
        </h2>
        {loading && (
          <p className="text-sm text-gray-500">Loading KPIs…</p>
        )}
        {error && (
          <p className="text-sm text-red-600">{error}</p>
        )}
        {dashboard && !loading && (
          <>
            <p className="text-xs text-gray-400 mb-3">
              Period: {dashboard.period_label}
            </p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
              {dashboard.kpis.map((kpi) => (
                <KPICard key={kpi.kpi_id} kpi={kpi} />
              ))}
            </div>
          </>
        )}
      </section>

      {/* Report Library */}
      <section>
        <h2 className="text-lg font-semibold text-gray-700 mb-4">
          Report Library
        </h2>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {REPORT_LINKS.map((r) => (
            <Link
              key={r.type}
              href={`/reports/${r.type}`}
              className="flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3 shadow-sm hover:border-blue-400 hover:shadow-md transition-all"
            >
              <span className="text-sm font-medium text-gray-700">
                {r.label}
              </span>
              <span className="text-gray-400">→</span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
