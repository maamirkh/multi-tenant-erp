"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { APAgingReport, getAPAgingReport } from "@/lib/api/accounting";

const BUCKET_COLUMNS: { key: keyof APAgingReport["totals"]; label: string }[] = [
  { key: "current", label: "Not Yet Due" },
  { key: "days_1_30", label: "1-30 Days" },
  { key: "days_31_60", label: "31-60 Days" },
  { key: "days_61_90", label: "61-90 Days" },
  { key: "days_91_120", label: "91-120 Days" },
  { key: "days_120_plus", label: "120+ Days" },
];

/**
 * AP Aging Report page — summary table by bucket with supplier drill-down.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T171
 */
export default function APAgingReportPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";
  const [report, setReport] = useState<APAgingReport | null>(null);
  const [asOfDate, setAsOfDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId) return;
    load();
  }, [companyId, asOfDate]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getAPAgingReport(companyId, asOfDate);
      setReport(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load aging report");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">AP Aging Report</h1>
          <p className="mt-1 text-sm text-gray-500">
            Outstanding payables bucketed by days overdue (from due date).
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-700">
          As of
          <input
            type="date"
            value={asOfDate}
            onChange={(e) => setAsOfDate(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </label>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : !report || report.rows.length === 0 ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          No open payables as of {asOfDate}.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 text-left text-xs font-medium text-gray-500">
                <th className="px-4 py-2">Supplier</th>
                {BUCKET_COLUMNS.map((col) => (
                  <th key={col.key} className="px-4 py-2 text-right">
                    {col.label}
                  </th>
                ))}
                <th className="px-4 py-2 text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {report.rows.map((row) => (
                <tr key={row.supplier_ledger_id ?? "unknown"} className="border-b border-gray-100">
                  <td className="px-4 py-2">
                    {row.supplier_id ? (
                      <Link
                        href={`/${companyId}/payables/suppliers/${row.supplier_id}`}
                        className="text-blue-600 hover:underline"
                      >
                        {row.supplier_id}
                      </Link>
                    ) : (
                      "—"
                    )}
                  </td>
                  {BUCKET_COLUMNS.map((col) => (
                    <td key={col.key} className="px-4 py-2 text-right">
                      {row[col.key]}
                    </td>
                  ))}
                  <td className="px-4 py-2 text-right font-semibold">{row.total}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-gray-300 bg-gray-50 font-semibold">
                <td className="px-4 py-2">Total</td>
                {BUCKET_COLUMNS.map((col) => (
                  <td key={col.key} className="px-4 py-2 text-right">
                    {report.totals[col.key]}
                  </td>
                ))}
                <td className="px-4 py-2 text-right">{report.totals.total}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}
