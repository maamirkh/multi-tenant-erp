"use client";

/**
 * Inventory Reports Navigation — Phase 9 Reporting Foundation
 * Lists all 14 inventory reports with date range filter and Export button.
 */

import { useState } from "react";
import { useParams } from "next/navigation";

type ReportType =
  | "inventory-summary"
  | "stock-ledger"
  | "inventory-valuation"
  | "stock-position"
  | "warehouse-utilisation"
  | "category-brand"
  | "dead-stock"
  | "movement-velocity"
  | "stock-aging"
  | "operational"
  | "trend-analysis";

interface ReportConfig {
  type: ReportType;
  label: string;
  description: string;
}

const REPORTS: ReportConfig[] = [
  {
    type: "inventory-summary",
    label: "Inventory Summary",
    description: "Total stock value by warehouse, category, and brand",
  },
  {
    type: "stock-ledger",
    label: "Stock Ledger",
    description: "All stock movements with type, direction, quantity, and cost",
  },
  {
    type: "inventory-valuation",
    label: "Inventory Valuation",
    description: "Per-product WAC valuation and total portfolio value",
  },
  {
    type: "stock-position",
    label: "Stock Position",
    description: "Current, reserved, damaged, and available stock per location",
  },
  {
    type: "warehouse-utilisation",
    label: "Warehouse Utilisation",
    description: "Stock count and value by warehouse with location fill rate",
  },
  {
    type: "category-brand",
    label: "Category & Brand Performance",
    description: "Stock value and movement count grouped by category and brand",
  },
  {
    type: "dead-stock",
    label: "Dead Stock",
    description: "Products with zero movement in the selected period",
  },
  {
    type: "movement-velocity",
    label: "Fast & Slow Moving",
    description: "Products ranked by movement frequency over the selected period",
  },
  {
    type: "stock-aging",
    label: "Stock Aging",
    description: "Age of current stock by first receipt date with aging buckets",
  },
  {
    type: "operational",
    label: "Operational Audit",
    description: "Adjustment and transfer audit history",
  },
  {
    type: "trend-analysis",
    label: "Inventory Trend Analysis",
    description: "Stock level over time for a selected product and warehouse",
  },
];

export default function ReportsPage() {
  const params = useParams();
  const companyId = params?.company_id as string;
  const [selectedReport, setSelectedReport] = useState<ReportType | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(false);
  const [reportData, setReportData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exportLoading, setExportLoading] = useState(false);
  const [exportUrl, setExportUrl] = useState<string | null>(null);

  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("access_token") ?? ""
      : "";

  function authHeader(): HeadersInit {
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async function runReport(type: ReportType) {
    setSelectedReport(type);
    setReportData(null);
    setError(null);
    setExportUrl(null);
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);
      const res = await fetch(
        `/api/v1/companies/${companyId}/inventory/reports/${type}?${params}`,
        { headers: authHeader() }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setReportData(json.data ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load report");
    } finally {
      setLoading(false);
    }
  }

  async function exportReport(fmt: "csv" | "xlsx") {
    if (!selectedReport) return;
    setExportLoading(true);
    setExportUrl(null);
    try {
      const res = await fetch(
        `/api/v1/companies/${companyId}/inventory/reports/${selectedReport}/export`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeader() },
          body: JSON.stringify({ format: fmt }),
        }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setExportUrl(json.data?.download_url ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setExportLoading(false);
    }
  }

  const exportableReports: ReportType[] = [
    "inventory-summary",
    "stock-ledger",
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Inventory Reports</h1>
        <a
          href={`/inventory/${companyId}/reports/kpis`}
          className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700"
        >
          KPI Dashboard
        </a>
      </div>

      {/* Date range filter */}
      <div className="flex gap-4 items-end bg-gray-50 p-4 rounded-lg">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Date From
          </label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="border rounded px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Date To
          </label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="border rounded px-3 py-2 text-sm"
          />
        </div>
      </div>

      {/* Report grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {REPORTS.map((r) => (
          <div
            key={r.type}
            className={`border rounded-lg p-4 cursor-pointer transition-colors ${
              selectedReport === r.type
                ? "border-blue-500 bg-blue-50"
                : "border-gray-200 hover:border-blue-300 hover:bg-gray-50"
            }`}
            onClick={() => runReport(r.type)}
          >
            <h3 className="font-semibold text-gray-900">{r.label}</h3>
            <p className="text-sm text-gray-500 mt-1">{r.description}</p>
          </div>
        ))}
      </div>

      {/* Report output */}
      {selectedReport && (
        <div className="border rounded-lg p-4 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">
              {REPORTS.find((r) => r.type === selectedReport)?.label}
            </h2>
            {exportableReports.includes(selectedReport) && (
              <div className="flex gap-2">
                <button
                  onClick={() => exportReport("csv")}
                  disabled={exportLoading}
                  className="border px-3 py-1 rounded text-sm hover:bg-gray-100"
                >
                  Export CSV
                </button>
                <button
                  onClick={() => exportReport("xlsx")}
                  disabled={exportLoading}
                  className="border px-3 py-1 rounded text-sm hover:bg-gray-100"
                >
                  Export Excel
                </button>
              </div>
            )}
          </div>

          {exportUrl && (
            <div className="bg-green-50 border border-green-200 rounded p-3 text-sm">
              Export ready:{" "}
              <a
                href={exportUrl}
                className="text-green-700 underline"
                target="_blank"
                rel="noreferrer"
              >
                Download
              </a>
            </div>
          )}

          {loading && <p className="text-gray-500 text-sm">Loading report...</p>}
          {error && <p className="text-red-600 text-sm">{error}</p>}

          {reportData && !loading && (
            <div className="overflow-x-auto">
              <ReportViewer data={reportData} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ReportViewer({ data }: { data: Record<string, unknown> }) {
  // Find the first array in the data to render as a table
  const arrayKey = Object.keys(data).find((k) => Array.isArray(data[k]));
  if (!arrayKey) {
    return (
      <pre className="text-xs text-gray-600 bg-gray-50 p-3 rounded overflow-auto">
        {JSON.stringify(data, null, 2)}
      </pre>
    );
  }

  const rows = data[arrayKey] as Record<string, unknown>[];
  if (rows.length === 0) {
    return <p className="text-gray-500 text-sm">No data for this report.</p>;
  }

  const headers = Object.keys(rows[0]);

  return (
    <table className="min-w-full text-sm border-collapse">
      <thead>
        <tr className="bg-gray-100">
          {headers.map((h) => (
            <th
              key={h}
              className="px-3 py-2 text-left text-xs font-semibold text-gray-600 border-b"
            >
              {h.replace(/_/g, " ").toUpperCase()}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
            {headers.map((h) => (
              <td key={h} className="px-3 py-2 border-b text-gray-700 whitespace-nowrap">
                {formatCell(row[h])}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string" && value.match(/^\d{4}-\d{2}-\d{2}T/)) {
    return new Date(value).toLocaleString();
  }
  return String(value);
}
