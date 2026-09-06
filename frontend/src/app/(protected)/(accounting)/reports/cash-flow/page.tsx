"use client";

import { useState } from "react";
import { CashFlowReport, getCashFlowReport } from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string };
}

/**
 * Cash Flow Statement (indirect method): net income + working-capital
 * adjustments reconciled against the actual GL cash/bank balance change.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T265
 */
export default function CashFlowPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";

  const [periodFrom, setPeriodFrom] = useState(
    new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10)
  );
  const [periodTo, setPeriodTo] = useState(new Date().toISOString().slice(0, 10));
  const [report, setReport] = useState<CashFlowReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setLoading(true);
    setError(null);
    try {
      const res = await getCashFlowReport(companyId, periodFrom, periodTo);
      setReport(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load cash flow statement");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Cash Flow Statement</h1>
        <p className="mt-1 text-sm text-gray-500">
          Indirect method: net income adjusted for working-capital movement.
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      <div className="mb-6 flex flex-wrap items-end gap-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div>
          <label className="block text-xs text-gray-500">Period From</label>
          <input
            type="date"
            value={periodFrom}
            onChange={(e) => setPeriodFrom(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500">Period To</label>
          <input
            type="date"
            value={periodTo}
            onChange={(e) => setPeriodTo(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </div>
        <button
          onClick={handleRun}
          disabled={loading}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Loading..." : "Run Report"}
        </button>
      </div>

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : !report ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          Select a period and run the report.
        </div>
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-900">Operating Activities</h2>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                report.reconciles ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
              }`}
            >
              {report.reconciles ? "Reconciled to GL" : "Does not reconcile"}
            </span>
          </div>

          <table className="mb-4 min-w-full text-sm">
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="py-1 pr-4">Net Income</td>
                <td className="py-1 pr-4 text-right">{report.net_income}</td>
              </tr>
              {report.working_capital_adjustments.length === 0 ? (
                <tr>
                  <td className="py-1 pr-4 pl-4 text-gray-400" colSpan={2}>
                    No working-capital adjustments.
                  </td>
                </tr>
              ) : (
                report.working_capital_adjustments.map((line) => (
                  <tr key={line.account_id}>
                    <td className="py-1 pr-4 pl-4 text-gray-600">
                      {line.account_code} ({line.account_type})
                    </td>
                    <td className="py-1 pr-4 text-right">{line.adjustment}</td>
                  </tr>
                ))
              )}
            </tbody>
            <tfoot>
              <tr className="border-t border-gray-200 font-semibold text-gray-900">
                <td className="py-2 pr-4">Net Cash from Operating Activities</td>
                <td className="py-2 pr-4 text-right">
                  {report.net_cash_from_operating_activities}
                </td>
              </tr>
            </tfoot>
          </table>

          <div className="grid grid-cols-3 gap-4 border-t border-gray-200 pt-3 text-sm">
            <div>
              <div className="text-xs text-gray-500">Opening Cash</div>
              <div className="font-medium text-gray-900">{report.opening_cash_balance}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500">Closing Cash</div>
              <div className="font-medium text-gray-900">{report.closing_cash_balance}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500">Net Change</div>
              <div className="font-medium text-gray-900">{report.net_change_in_cash}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
