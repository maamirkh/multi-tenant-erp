"use client";

/**
 * KPI Dashboard — T225
 * Cards for all 10 procurement KPIs with optional date range filter.
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

interface KPIData {
  kpi_01_purchase_cycle_time_days: number | null;
  kpi_02_on_time_delivery_rate_pct: number;
  kpi_03_order_fulfilment_rate_pct: number;
  kpi_04_rejection_rate_pct: number;
  kpi_05_avg_ppv_pct: number | null;
  kpi_06_open_commitments_value: string;
  kpi_07_total_purchase_value: string;
  kpi_08_po_processing_time_days: number | null;
  kpi_09_vendor_return_rate_pct: number;
  kpi_10_preferred_supplier_utilisation_pct: number;
}

const KPI_META = [
  {
    key: "kpi_01_purchase_cycle_time_days",
    label: "Purchase Cycle Time",
    unit: "days",
    description: "Avg days from PR creation to approval",
    isMonetary: false,
  },
  {
    key: "kpi_02_on_time_delivery_rate_pct",
    label: "On-Time Delivery Rate",
    unit: "%",
    description: "% GRs received on or before PO delivery date",
    isMonetary: false,
  },
  {
    key: "kpi_03_order_fulfilment_rate_pct",
    label: "Order Fulfilment Rate",
    unit: "%",
    description: "% GR lines with zero rejections",
    isMonetary: false,
  },
  {
    key: "kpi_04_rejection_rate_pct",
    label: "Rejection Rate",
    unit: "%",
    description: "% of received quantity rejected",
    isMonetary: false,
  },
  {
    key: "kpi_05_avg_ppv_pct",
    label: "Avg PPV %",
    unit: "%",
    description: "Average purchase price variance",
    isMonetary: false,
  },
  {
    key: "kpi_06_open_commitments_value",
    label: "Open Commitments",
    unit: "",
    description: "Total open PO commitment value",
    isMonetary: true,
  },
  {
    key: "kpi_07_total_purchase_value",
    label: "Total Purchase Value",
    unit: "",
    description: "Total confirmed GR spend in period",
    isMonetary: true,
  },
  {
    key: "kpi_08_po_processing_time_days",
    label: "PO Processing Time",
    unit: "days",
    description: "Avg days from PO creation to approval",
    isMonetary: false,
  },
  {
    key: "kpi_09_vendor_return_rate_pct",
    label: "Vendor Return Rate",
    unit: "%",
    description: "% of confirmed GRs with an RMA",
    isMonetary: false,
  },
  {
    key: "kpi_10_preferred_supplier_utilisation_pct",
    label: "Preferred Supplier Utilisation",
    unit: "%",
    description: "% POs placed with preferred suppliers",
    isMonetary: false,
  },
];

export default function KPIDashboardPage() {
  const params = useParams<{ companyId: string }>();
  const companyId = params?.companyId ?? "";

  const [kpis, setKpis] = useState<KPIData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const fetchKpis = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);
      const qs = params.toString() ? `?${params.toString()}` : "";
      const res = await fetch(
        `/api/v1/companies/${companyId}/purchase/reports/kpis${qs}`,
        { credentials: "include" }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = await res.json();
      setKpis(body.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (companyId) fetchKpis();
  }, [companyId]);

  const formatValue = (meta: (typeof KPI_META)[0], raw: number | string | null) => {
    if (raw === null || raw === undefined) return "—";
    if (meta.isMonetary) return `$${parseFloat(String(raw)).toLocaleString("en-US", { minimumFractionDigits: 2 })}`;
    if (meta.unit === "%") return `${raw}%`;
    if (meta.unit === "days") return `${raw} days`;
    return String(raw);
  };

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">KPI Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">10 procurement KPIs</p>
      </div>

      <div className="mb-6 flex flex-wrap gap-3">
        <div>
          <label className="block text-xs text-gray-500">Date From</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="mt-1 rounded border border-gray-300 px-2 py-1 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500">Date To</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="mt-1 rounded border border-gray-300 px-2 py-1 text-sm"
          />
        </div>
        <div className="flex items-end">
          <button
            onClick={fetchKpis}
            className="rounded bg-blue-600 px-4 py-1.5 text-sm text-white hover:bg-blue-700"
          >
            Refresh
          </button>
        </div>
      </div>

      {loading && <div className="text-sm text-gray-400">Loading KPIs…</div>}
      {error && <div className="rounded bg-red-50 p-3 text-sm text-red-600">{error}</div>}

      {kpis && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {KPI_META.map((meta) => {
            const raw = kpis[meta.key as keyof KPIData];
            return (
              <div key={meta.key} className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-gray-500">{meta.label}</div>
                <div className="mt-1 text-xl font-bold text-gray-900">
                  {formatValue(meta, raw)}
                </div>
                <div className="mt-1 text-xs text-gray-400">{meta.description}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
