"use client";

import { useEffect, useState } from "react";
import ExportButton from "@/components/accounting/ExportButton";
import {
  CashAccountResponse,
  LedgerStatementReport,
  getCashAccounts,
  getCashBookReport,
} from "@/lib/api/accounting";

/**
 * Cash Book report: opening balance, transactions, closing balance for a
 * cash account and date range.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T266
 */
export default function CashBookPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";

  const [accounts, setAccounts] = useState<CashAccountResponse[]>([]);
  const [cashAccountId, setCashAccountId] = useState("");
  const [fromDate, setFromDate] = useState(
    new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10)
  );
  const [toDate, setToDate] = useState(new Date().toISOString().slice(0, 10));
  const [report, setReport] = useState<LedgerStatementReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId) return;
    getCashAccounts(companyId)
      .then((res) => {
        setAccounts(res.data);
        if (res.data[0]) setCashAccountId(res.data[0].id);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load cash accounts"));
  }, [companyId]);

  async function handleRun() {
    if (!cashAccountId) {
      setError("Select a cash account.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await getCashBookReport(companyId, cashAccountId, fromDate, toDate);
      setReport(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load cash book");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Cash Book</h1>
          <p className="mt-1 text-sm text-gray-500">Transaction history for a cash account.</p>
        </div>
        {report && cashAccountId && (
          <ExportButton
            companyId={companyId}
            reportPath={`/reports/cash-book/${cashAccountId}`}
            filename="cash-book"
            extraParams={{ from_date: fromDate, to_date: toDate }}
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
          <label className="block text-xs text-gray-500">Cash Account</label>
          <select
            value={cashAccountId}
            onChange={(e) => setCashAccountId(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          >
            {accounts.length === 0 && <option value="">No cash accounts</option>}
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.account_name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500">From Date</label>
          <input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500">To Date</label>
          <input
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </div>
        <button
          onClick={handleRun}
          disabled={loading || !cashAccountId}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Loading..." : "Run Report"}
        </button>
      </div>

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : !report ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          Select a cash account and run the report.
        </div>
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500">
                <th className="py-1 pr-4">Date</th>
                <th className="py-1 pr-4">Description</th>
                <th className="py-1 pr-4 text-right">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr className="font-medium text-gray-900">
                <td className="py-1 pr-4" colSpan={2}>
                  Opening Balance
                </td>
                <td className="py-1 pr-4 text-right">{report.opening_balance}</td>
              </tr>
              {report.transactions.length === 0 ? (
                <tr>
                  <td className="py-1 pr-4 text-gray-400" colSpan={3}>
                    No transactions in this period.
                  </td>
                </tr>
              ) : (
                report.transactions.map((t, idx) => (
                  <tr key={idx}>
                    <td className="py-1 pr-4">{String(t["transaction_date"] ?? "")}</td>
                    <td className="py-1 pr-4">
                      {String(t["description"] ?? t["transaction_type"] ?? "")}
                    </td>
                    <td className="py-1 pr-4 text-right">{String(t["amount"] ?? "")}</td>
                  </tr>
                ))
              )}
              <tr className="font-medium text-gray-900">
                <td className="py-1 pr-4" colSpan={2}>
                  Closing Balance
                </td>
                <td className="py-1 pr-4 text-right">{report.closing_balance}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
