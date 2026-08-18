"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CustomerStatementResponse, getCustomerStatement } from "@/lib/api/accounting";

function StatementForm({ companyId }: { companyId: string }) {
  const searchParams = useSearchParams();
  const [customerId, setCustomerId] = useState(searchParams.get("customer_id") ?? "");
  const [fromDate, setFromDate] = useState(
    new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10)
  );
  const [toDate, setToDate] = useState(new Date().toISOString().slice(0, 10));
  const [statement, setStatement] = useState<CustomerStatementResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate() {
    if (!customerId) {
      setError("Customer ID is required.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await getCustomerStatement(companyId, customerId, fromDate, toDate);
      setStatement(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate statement");
    } finally {
      setLoading(false);
    }
  }

  function handlePrint() {
    window.print();
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Customer Statement</h1>
        <p className="mt-1 text-sm text-gray-500">
          Generate an opening-balance-to-closing-balance statement for a customer and period.
        </p>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 rounded-lg border border-gray-200 bg-white p-4 shadow-sm sm:grid-cols-4">
        <label className="text-sm text-gray-700">
          Customer ID
          <input
            type="text"
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            placeholder="Customer UUID"
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </label>
        <label className="text-sm text-gray-700">
          From
          <input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </label>
        <label className="text-sm text-gray-700">
          To
          <input
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </label>
        <div className="flex items-end">
          <button
            onClick={handleGenerate}
            disabled={loading}
            className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Generating..." : "Generate"}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {statement && (
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">
                Statement for {statement.customer_id} · {statement.from_date} to{" "}
                {statement.to_date}
              </p>
            </div>
            <button
              onClick={handlePrint}
              className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
            >
              Download / Print
            </button>
          </div>

          <div className="mb-4 flex justify-between text-sm">
            <span className="text-gray-500">Opening Balance</span>
            <span className="font-medium text-gray-900">{statement.opening_balance}</span>
          </div>

          {statement.transactions.length === 0 ? (
            <p className="py-4 text-center text-sm text-gray-400">
              No transactions in this period.
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs text-gray-500">
                  <th className="py-1">Date</th>
                  <th className="py-1">Type</th>
                  <th className="py-1">Invoice #</th>
                  <th className="py-1 text-right">Amount</th>
                  <th className="py-1 text-right">Outstanding</th>
                </tr>
              </thead>
              <tbody>
                {statement.transactions.map((t) => (
                  <tr key={t.id} className="border-b border-gray-100">
                    <td className="py-1">{t.transaction_date}</td>
                    <td className="py-1">{t.transaction_type}</td>
                    <td className="py-1">{t.invoice_number ?? "—"}</td>
                    <td className="py-1 text-right">{t.amount_base}</td>
                    <td className="py-1 text-right">{t.outstanding_amount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div className="mt-4 flex justify-between border-t border-gray-200 pt-3 text-sm font-semibold">
            <span>Closing Balance</span>
            <span>{statement.closing_balance}</span>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Customer Statement generator page — select customer + period → preview + download.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T149
 */
export default function CustomerStatementPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";
  return (
    <Suspense fallback={<div className="py-8 text-center text-gray-500">Loading...</div>}>
      <StatementForm companyId={companyId} />
    </Suspense>
  );
}
