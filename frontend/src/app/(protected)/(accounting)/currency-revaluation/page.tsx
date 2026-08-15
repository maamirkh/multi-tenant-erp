"use client";

import { useEffect, useState } from "react";
import {
  FiscalPeriodResponse,
  FiscalYearResponse,
  RevaluationReport,
  getCurrencyRevaluationHistory,
  getFiscalPeriods,
  getFiscalYears,
  runCurrencyRevaluation,
} from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string };
}

/**
 * Currency Revaluation: select a fiscal period and revaluation date, preview
 * the unrealized gain/loss report, then confirm to post it to the GL.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T252
 */
export default function CurrencyRevaluationPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";

  const [fiscalYears, setFiscalYears] = useState<FiscalYearResponse[]>([]);
  const [selectedYearId, setSelectedYearId] = useState("");
  const [periods, setPeriods] = useState<FiscalPeriodResponse[]>([]);
  const [selectedPeriodId, setSelectedPeriodId] = useState("");
  const [revaluationDate, setRevaluationDate] = useState(
    new Date().toISOString().slice(0, 10)
  );

  const [history, setHistory] = useState<RevaluationReport[]>([]);
  const [result, setResult] = useState<RevaluationReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId) return;
    getFiscalYears(companyId)
      .then((res) => {
        setFiscalYears(res.data);
        const current = res.data.find((y) => y.is_current) ?? res.data[0];
        if (current) setSelectedYearId(current.id);
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load fiscal years")
      );
    loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId]);

  useEffect(() => {
    if (!companyId || !selectedYearId) return;
    getFiscalPeriods(companyId, selectedYearId)
      .then((res) => {
        setPeriods(res.data);
        if (res.data[0]) setSelectedPeriodId(res.data[0].id);
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load fiscal periods")
      );
  }, [companyId, selectedYearId]);

  function loadHistory() {
    setHistoryLoading(true);
    getCurrencyRevaluationHistory(companyId)
      .then((res) => setHistory(res.data))
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load revaluation history")
      )
      .finally(() => setHistoryLoading(false));
  }

  async function handleRun() {
    if (!selectedPeriodId) {
      setError("Select a fiscal period.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await runCurrencyRevaluation(companyId, {
        fiscal_period_id: selectedPeriodId,
        revaluation_date: revaluationDate,
      });
      setResult(res.data);
      loadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run currency revaluation");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Currency Revaluation</h1>
        <p className="mt-1 text-sm text-gray-500">
          Revalue open foreign-currency AR/AP balances as of a date and post the
          unrealized gain/loss to the General Ledger.
        </p>
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
            {fiscalYears.length === 0 && <option value="">No fiscal years</option>}
            {fiscalYears.map((y) => (
              <option key={y.id} value={y.id}>
                {y.fiscal_year_name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500">Fiscal Period</label>
          <select
            value={selectedPeriodId}
            onChange={(e) => setSelectedPeriodId(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          >
            {periods.length === 0 && <option value="">No periods</option>}
            {periods.map((p) => (
              <option key={p.id} value={p.id}>
                {p.period_name} ({p.start_date} – {p.end_date})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500">Revaluation Date</label>
          <input
            type="date"
            value={revaluationDate}
            onChange={(e) => setRevaluationDate(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </div>
        <button
          onClick={handleRun}
          disabled={loading || !selectedPeriodId}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Running..." : "Run Revaluation"}
        </button>
      </div>

      {result && (
        <div className="mb-6 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-sm font-semibold text-gray-900">
            Revaluation Report — {result.revaluation_date}
          </h2>

          <div className="mb-4 grid grid-cols-3 gap-4 text-sm">
            <div>
              <div className="text-xs text-gray-500">Unrealized Gain</div>
              <div className="font-medium text-green-700">
                {result.total_unrealized_gain_base}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500">Unrealized Loss</div>
              <div className="font-medium text-red-700">{result.total_unrealized_loss_base}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500">Net Gain/(Loss)</div>
              <div className="font-medium text-gray-900">{result.net_gain_loss_base}</div>
            </div>
          </div>

          {result.journal_entry_id === null ? (
            <div className="rounded-md border border-dashed border-gray-300 p-4 text-center text-sm text-gray-500">
              No open foreign-currency exposure as of this date — nothing posted.
            </div>
          ) : (
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500">
                  <th className="py-1 pr-4">Type</th>
                  <th className="py-1 pr-4">Currency</th>
                  <th className="py-1 pr-4 text-right">Booking Rate</th>
                  <th className="py-1 pr-4 text-right">Current Rate</th>
                  <th className="py-1 pr-4 text-right">Outstanding (Foreign)</th>
                  <th className="py-1 pr-4 text-right">Gain/(Loss)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {result.lines.map((line) => (
                  <tr key={`${line.transaction_type}-${line.transaction_id}`}>
                    <td className="py-1 pr-4">{line.transaction_type}</td>
                    <td className="py-1 pr-4">{line.currency_code}</td>
                    <td className="py-1 pr-4 text-right">{line.booking_rate}</td>
                    <td className="py-1 pr-4 text-right">{line.current_rate}</td>
                    <td className="py-1 pr-4 text-right">{line.outstanding_foreign}</td>
                    <td
                      className={`py-1 pr-4 text-right ${
                        Number(line.gain_loss_amount) >= 0 ? "text-green-700" : "text-red-700"
                      }`}
                    >
                      {line.gain_loss_amount}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-gray-900">Revaluation History</h2>
        {historyLoading ? (
          <div className="py-4 text-center text-sm text-gray-500">Loading...</div>
        ) : history.length === 0 ? (
          <div className="rounded-md border border-dashed border-gray-300 p-4 text-center text-sm text-gray-500">
            No revaluation runs yet.
          </div>
        ) : (
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500">
                <th className="py-1 pr-4">Date</th>
                <th className="py-1 pr-4">Currencies</th>
                <th className="py-1 pr-4 text-right">Net Gain/(Loss)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {history.map((run) => (
                <tr key={run.id}>
                  <td className="py-1 pr-4">{run.revaluation_date}</td>
                  <td className="py-1 pr-4">{run.currencies_revalued.join(", ") || "—"}</td>
                  <td className="py-1 pr-4 text-right">{run.net_gain_loss_base}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
