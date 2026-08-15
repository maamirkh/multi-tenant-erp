"use client";

import { useEffect, useState } from "react";
import ExportButton from "@/components/accounting/ExportButton";
import {
  CostCenterResponse,
  PLReport,
  getCostCenters,
  getProfitLossReport,
} from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string };
}

/**
 * Profit & Loss report: revenue/expense sections, gross margin, net
 * profit, comparative column, cost center filter.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T263
 */
export default function ProfitLossPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";

  const [periodFrom, setPeriodFrom] = useState(
    new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10)
  );
  const [periodTo, setPeriodTo] = useState(new Date().toISOString().slice(0, 10));
  const [comparativeFrom, setComparativeFrom] = useState("");
  const [comparativeTo, setComparativeTo] = useState("");
  const [costCenters, setCostCenters] = useState<CostCenterResponse[]>([]);
  const [costCenterId, setCostCenterId] = useState("");
  const [report, setReport] = useState<PLReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId) return;
    getCostCenters(companyId).then((res) => setCostCenters(res.data)).catch(() => undefined);
  }, [companyId]);

  async function handleRun() {
    setLoading(true);
    setError(null);
    try {
      const res = await getProfitLossReport(companyId, periodFrom, periodTo, {
        comparativeFrom: comparativeFrom || undefined,
        comparativeTo: comparativeTo || undefined,
        costCenterId: costCenterId || undefined,
      });
      setReport(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load profit & loss statement");
    } finally {
      setLoading(false);
    }
  }

  const grossMarginPct =
    report && parseFloat(report.total_revenue) !== 0
      ? ((parseFloat(report.net_income) / parseFloat(report.total_revenue)) * 100).toFixed(1)
      : null;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Profit &amp; Loss</h1>
          <p className="mt-1 text-sm text-gray-500">Revenue and expenses for a period.</p>
        </div>
        {report && (
          <ExportButton
            companyId={companyId}
            reportPath="/reports/profit-loss"
            filename="profit-loss"
            extraParams={{ period_from: periodFrom, period_to: periodTo }}
          />
        )}
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
        <div>
          <label className="block text-xs text-gray-500">Comparative From (optional)</label>
          <input
            type="date"
            value={comparativeFrom}
            onChange={(e) => setComparativeFrom(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500">Comparative To (optional)</label>
          <input
            type="date"
            value={comparativeTo}
            onChange={(e) => setComparativeTo(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500">Cost Center</label>
          <select
            value={costCenterId}
            onChange={(e) => setCostCenterId(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          >
            <option value="">All</option>
            {costCenters.map((c) => (
              <option key={c.id} value={c.id}>
                {c.center_code} — {c.center_name}
              </option>
            ))}
          </select>
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
          <table className="mb-4 min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500">
                <th className="py-1 pr-4">Account</th>
                <th className="py-1 pr-4 text-right">Amount</th>
                {report.comparative && <th className="py-1 pr-4 text-right">Comparative</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr className="font-medium text-gray-900">
                <td className="py-1 pr-4" colSpan={report.comparative ? 3 : 2}>
                  Revenue
                </td>
              </tr>
              {report.revenue.lines.map((line) => {
                const compLine = report.comparative?.revenue.lines.find(
                  (l) => l.account_code === line.account_code
                );
                return (
                  <tr key={line.account_id}>
                    <td className="py-1 pr-4 pl-4">
                      {line.account_code} — {line.account_name}
                    </td>
                    <td className="py-1 pr-4 text-right">{line.amount}</td>
                    {report.comparative && (
                      <td className="py-1 pr-4 text-right text-gray-500">
                        {compLine?.amount ?? "—"}
                      </td>
                    )}
                  </tr>
                );
              })}
              <tr className="font-medium text-gray-900">
                <td className="py-1 pr-4">Total Revenue</td>
                <td className="py-1 pr-4 text-right">{report.total_revenue}</td>
                {report.comparative && (
                  <td className="py-1 pr-4 text-right">{report.comparative.total_revenue}</td>
                )}
              </tr>

              <tr className="font-medium text-gray-900">
                <td className="py-1 pr-4 pt-4" colSpan={report.comparative ? 3 : 2}>
                  Expenses
                </td>
              </tr>
              {report.expense.lines.map((line) => {
                const compLine = report.comparative?.expense.lines.find(
                  (l) => l.account_code === line.account_code
                );
                return (
                  <tr key={line.account_id}>
                    <td className="py-1 pr-4 pl-4">
                      {line.account_code} — {line.account_name}
                    </td>
                    <td className="py-1 pr-4 text-right">{line.amount}</td>
                    {report.comparative && (
                      <td className="py-1 pr-4 text-right text-gray-500">
                        {compLine?.amount ?? "—"}
                      </td>
                    )}
                  </tr>
                );
              })}
              <tr className="font-medium text-gray-900">
                <td className="py-1 pr-4">Total Expense</td>
                <td className="py-1 pr-4 text-right">{report.total_expense}</td>
                {report.comparative && (
                  <td className="py-1 pr-4 text-right">{report.comparative.total_expense}</td>
                )}
              </tr>
            </tbody>
            <tfoot>
              <tr className="border-t border-gray-200 font-semibold text-gray-900">
                <td className="py-2 pr-4">
                  Net Income {grossMarginPct !== null && `(${grossMarginPct}% margin)`}
                </td>
                <td className="py-2 pr-4 text-right">{report.net_income}</td>
                {report.comparative && (
                  <td className="py-2 pr-4 text-right">{report.comparative.net_income}</td>
                )}
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}
