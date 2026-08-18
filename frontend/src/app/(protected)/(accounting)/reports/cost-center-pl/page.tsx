"use client";

import { useEffect, useState } from "react";
import {
  CostCenterPLReport,
  CostCenterResponse,
  getCostCenterPLReport,
  getCostCenters,
} from "@/lib/api/accounting";

/**
 * Cost Center P&L Report: revenue and expenses by cost center.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T243
 */
export default function CostCenterPLReportPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";
  const [costCenters, setCostCenters] = useState<CostCenterResponse[]>([]);
  const [selectedCostCenterId, setSelectedCostCenterId] = useState("");
  const [periodStart, setPeriodStart] = useState(
    new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10)
  );
  const [periodEnd, setPeriodEnd] = useState(new Date().toISOString().slice(0, 10));
  const [report, setReport] = useState<CostCenterPLReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId) return;
    getCostCenters(companyId)
      .then((res) => {
        setCostCenters(res.data);
        if (res.data[0]) setSelectedCostCenterId(res.data[0].id);
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load cost centers")
      );
  }, [companyId]);

  async function handleRun() {
    if (!selectedCostCenterId) {
      setError("Select a cost center.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await getCostCenterPLReport(
        companyId,
        selectedCostCenterId,
        periodStart,
        periodEnd
      );
      setReport(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load cost center P&L report");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Cost Center P&amp;L Report</h1>
        <p className="mt-1 text-sm text-gray-500">
          Revenue and expenses aggregated by cost center for a period.
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      <div className="mb-6 flex flex-wrap items-end gap-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div>
          <label className="block text-xs text-gray-500">Cost Center</label>
          <select
            value={selectedCostCenterId}
            onChange={(e) => setSelectedCostCenterId(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          >
            {costCenters.length === 0 && <option value="">No cost centers</option>}
            {costCenters.map((c) => (
              <option key={c.id} value={c.id}>
                {c.center_code} — {c.center_name}
              </option>
            ))}
          </select>
        </div>
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
          Select a cost center and run the report.
        </div>
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-sm font-semibold text-gray-900">{report.name}</h2>

          <table className="mb-4 min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500">
                <th className="py-1 pr-4">Account</th>
                <th className="py-1 pr-4 text-right">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr className="font-medium text-gray-900">
                <td className="py-1 pr-4" colSpan={2}>
                  Revenue
                </td>
              </tr>
              {report.revenue_lines.length === 0 ? (
                <tr>
                  <td className="py-1 pr-4 text-gray-400" colSpan={2}>
                    No revenue activity.
                  </td>
                </tr>
              ) : (
                report.revenue_lines.map((line) => (
                  <tr key={line.account_id}>
                    <td className="py-1 pr-4">
                      {line.account_code} — {line.account_name}
                    </td>
                    <td className="py-1 pr-4 text-right">{line.amount}</td>
                  </tr>
                ))
              )}
              <tr className="font-medium text-gray-900">
                <td className="py-1 pr-4">Total Revenue</td>
                <td className="py-1 pr-4 text-right">{report.total_revenue}</td>
              </tr>

              <tr className="font-medium text-gray-900">
                <td className="py-1 pr-4 pt-4" colSpan={2}>
                  Expenses
                </td>
              </tr>
              {report.expense_lines.length === 0 ? (
                <tr>
                  <td className="py-1 pr-4 text-gray-400" colSpan={2}>
                    No expense activity.
                  </td>
                </tr>
              ) : (
                report.expense_lines.map((line) => (
                  <tr key={line.account_id}>
                    <td className="py-1 pr-4">
                      {line.account_code} — {line.account_name}
                    </td>
                    <td className="py-1 pr-4 text-right">{line.amount}</td>
                  </tr>
                ))
              )}
              <tr className="font-medium text-gray-900">
                <td className="py-1 pr-4">Total Expense</td>
                <td className="py-1 pr-4 text-right">{report.total_expense}</td>
              </tr>
            </tbody>
            <tfoot>
              <tr className="border-t border-gray-200 font-semibold text-gray-900">
                <td className="py-2 pr-4">Net Income</td>
                <td className="py-2 pr-4 text-right">{report.net_income}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}
