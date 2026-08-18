"use client";

import { useEffect, useState } from "react";
import ExportButton from "@/components/accounting/ExportButton";
import {
  FiscalPeriodResponse,
  FiscalYearResponse,
  JournalReportResponse,
  getFiscalPeriods,
  getFiscalYears,
  getJournalReport,
} from "@/lib/api/accounting";

/**
 * Journal Report: every POSTED journal entry for a fiscal period.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T267
 */
export default function JournalReportPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";

  const [fiscalYears, setFiscalYears] = useState<FiscalYearResponse[]>([]);
  const [selectedYearId, setSelectedYearId] = useState("");
  const [periods, setPeriods] = useState<FiscalPeriodResponse[]>([]);
  const [periodId, setPeriodId] = useState("");
  const [report, setReport] = useState<JournalReportResponse | null>(null);
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
      const res = await getJournalReport(companyId, periodId);
      setReport(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load journal report");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Journal Report</h1>
          <p className="mt-1 text-sm text-gray-500">Every posted journal entry for a period.</p>
        </div>
        {report && (
          <ExportButton
            companyId={companyId}
            reportPath="/reports/journals"
            filename="journal-report"
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
          <p className="mb-3 text-xs text-gray-500">
            Showing {report.entries.length} of {report.total} entries
          </p>
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500">
                <th className="py-1 pr-4">Journal #</th>
                <th className="py-1 pr-4">Date</th>
                <th className="py-1 pr-4">Type</th>
                <th className="py-1 pr-4">Description</th>
                <th className="py-1 pr-4 text-right">Debit</th>
                <th className="py-1 pr-4 text-right">Credit</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {report.entries.length === 0 ? (
                <tr>
                  <td className="py-1 pr-4 text-gray-400" colSpan={6}>
                    No posted journal entries in this period.
                  </td>
                </tr>
              ) : (
                report.entries.map((e) => (
                  <tr key={e.id}>
                    <td className="py-1 pr-4">{e.journal_number ?? "—"}</td>
                    <td className="py-1 pr-4">{e.posting_date}</td>
                    <td className="py-1 pr-4">{e.journal_type}</td>
                    <td className="py-1 pr-4">{e.description ?? "—"}</td>
                    <td className="py-1 pr-4 text-right">{e.total_debit_base}</td>
                    <td className="py-1 pr-4 text-right">{e.total_credit_base}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
