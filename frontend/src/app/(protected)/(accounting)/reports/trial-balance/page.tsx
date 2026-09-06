"use client";

import { useEffect, useState } from "react";
import ExportButton from "@/components/accounting/ExportButton";
import {
  FiscalPeriodResponse,
  FiscalYearResponse,
  TrialBalanceReport,
  getFiscalPeriods,
  getFiscalYears,
  getTrialBalanceReport,
} from "@/lib/api/accounting";

/**
 * Trial Balance report: account list with debit/credit totals, a balance
 * check indicator, and an optional comparative period column.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T264
 */
export default function TrialBalancePage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";

  const [fiscalYears, setFiscalYears] = useState<FiscalYearResponse[]>([]);
  const [selectedYearId, setSelectedYearId] = useState("");
  const [periods, setPeriods] = useState<FiscalPeriodResponse[]>([]);
  const [periodId, setPeriodId] = useState("");
  const [comparativePeriodId, setComparativePeriodId] = useState("");

  const [report, setReport] = useState<TrialBalanceReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId) return;
    getFiscalYears(companyId)
      .then((res) => {
        setFiscalYears(res.data);
        const current = res.data.find((y) => y.is_current) ?? res.data[0];
        if (current) setSelectedYearId(current.id);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load fiscal years"));
  }, [companyId]);

  useEffect(() => {
    if (!companyId || !selectedYearId) return;
    getFiscalPeriods(companyId, selectedYearId)
      .then((res) => {
        setPeriods(res.data);
        if (res.data[0]) setPeriodId(res.data[0].id);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load fiscal periods"));
  }, [companyId, selectedYearId]);

  async function handleRun() {
    if (!periodId) {
      setError("Select a fiscal period.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await getTrialBalanceReport(
        companyId,
        periodId,
        comparativePeriodId || undefined
      );
      setReport(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load trial balance");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Trial Balance</h1>
          <p className="mt-1 text-sm text-gray-500">
            Total debits and credits by account for a fiscal period.
          </p>
        </div>
        {report && (
          <ExportButton
            companyId={companyId}
            reportPath="/reports/trial-balance"
            filename="trial-balance"
            extraParams={{ period_id: periodId }}
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
          <label className="block text-xs text-gray-500">Fiscal Year</label>
          <select
            value={selectedYearId}
            onChange={(e) => setSelectedYearId(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          >
            {fiscalYears.map((y) => (
              <option key={y.id} value={y.id}>
                {y.fiscal_year_name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500">Period</label>
          <select
            value={periodId}
            onChange={(e) => setPeriodId(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          >
            {periods.map((p) => (
              <option key={p.id} value={p.id}>
                {p.period_name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500">Comparative Period (optional)</label>
          <select
            value={comparativePeriodId}
            onChange={(e) => setComparativePeriodId(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          >
            <option value="">None</option>
            {periods.map((p) => (
              <option key={p.id} value={p.id}>
                {p.period_name}
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={handleRun}
          disabled={loading || !periodId}
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
            <h2 className="text-sm font-semibold text-gray-900">Trial Balance</h2>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                report.is_balanced
                  ? "bg-green-100 text-green-800"
                  : "bg-red-100 text-red-800"
              }`}
            >
              {report.is_balanced ? "Balanced" : "Out of Balance"}
            </span>
          </div>
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500">
                <th className="py-1 pr-4">Account Code</th>
                <th className="py-1 pr-4 text-right">Debit</th>
                <th className="py-1 pr-4 text-right">Credit</th>
                {report.comparative && (
                  <>
                    <th className="py-1 pr-4 text-right">Comp. Debit</th>
                    <th className="py-1 pr-4 text-right">Comp. Credit</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {report.rows.map((row) => {
                const compRow = report.comparative?.rows.find(
                  (r) => r.account_code === row.account_code
                );
                return (
                  <tr key={row.account_id}>
                    <td className="py-1 pr-4">{row.account_code}</td>
                    <td className="py-1 pr-4 text-right">{row.total_debit}</td>
                    <td className="py-1 pr-4 text-right">{row.total_credit}</td>
                    {report.comparative && (
                      <>
                        <td className="py-1 pr-4 text-right text-gray-500">
                          {compRow?.total_debit ?? "—"}
                        </td>
                        <td className="py-1 pr-4 text-right text-gray-500">
                          {compRow?.total_credit ?? "—"}
                        </td>
                      </>
                    )}
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr className="border-t border-gray-200 font-semibold text-gray-900">
                <td className="py-2 pr-4">Total</td>
                <td className="py-2 pr-4 text-right">{report.total_debit}</td>
                <td className="py-2 pr-4 text-right">{report.total_credit}</td>
                {report.comparative && (
                  <>
                    <td className="py-2 pr-4 text-right">{report.comparative.total_debit}</td>
                    <td className="py-2 pr-4 text-right">{report.comparative.total_credit}</td>
                  </>
                )}
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}
