"use client";

import { useState } from "react";
import { TaxSummaryReport, getTaxSummaryReport } from "@/lib/api/accounting";

/**
 * Tax Summary Report: output tax, input tax, and net payable by tax code.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T241
 */
export default function TaxSummaryReportPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";
  const [periodStart, setPeriodStart] = useState(
    new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10)
  );
  const [periodEnd, setPeriodEnd] = useState(new Date().toISOString().slice(0, 10));
  const [report, setReport] = useState<TaxSummaryReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setLoading(true);
    setError(null);
    try {
      const res = await getTaxSummaryReport(companyId, periodStart, periodEnd);
      setReport(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load tax summary report");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Tax Summary Report</h1>
        <p className="mt-1 text-sm text-gray-500">
          Output tax, input tax, and net payable by tax code for a period.
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      <div className="mb-6 flex items-end gap-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div>
          <label className="block text-xs text-gray-500">Period Start</label>
          <input
            type="date"
            value={periodStart}
            onChange={(e) => setPeriodStart(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500">Period End</label>
          <input
            type="date"
            value={periodEnd}
            onChange={(e) => setPeriodEnd(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </div>
        <button
          onClick={handleRun}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Run Report
        </button>
      </div>

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : !report ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          Select a period and run the report.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500">
                <th className="px-4 py-2">Tax Code</th>
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2 text-right">Output Tax</th>
                <th className="px-4 py-2 text-right">Input Tax</th>
                <th className="px-4 py-2">Recoverable</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {report.rows.length === 0 ? (
                <tr>
                  <td className="px-4 py-3 text-center text-gray-400" colSpan={5}>
                    No tax activity in this period.
                  </td>
                </tr>
              ) : (
                report.rows.map((row) => (
                  <tr key={row.tax_code_id}>
                    <td className="px-4 py-2">{row.tax_code}</td>
                    <td className="px-4 py-2">{row.tax_name}</td>
                    <td className="px-4 py-2 text-right">{row.output_tax}</td>
                    <td className="px-4 py-2 text-right">{row.input_tax}</td>
                    <td className="px-4 py-2">{row.is_input_tax_recoverable ? "Yes" : "No"}</td>
                  </tr>
                ))
              )}
            </tbody>
            <tfoot>
              <tr className="border-t border-gray-200 font-medium text-gray-900">
                <td className="px-4 py-2" colSpan={2}>
                  Totals
                </td>
                <td className="px-4 py-2 text-right">{report.total_output_tax}</td>
                <td className="px-4 py-2 text-right">{report.total_input_tax}</td>
                <td className="px-4 py-2" />
              </tr>
              <tr className="font-semibold text-gray-900">
                <td className="px-4 py-2" colSpan={4}>
                  Net Payable
                </td>
                <td className="px-4 py-2">{report.net_payable}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}
