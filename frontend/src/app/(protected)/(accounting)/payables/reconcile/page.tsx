"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  ReconcileStatementLine,
  SupplierStatementReconciliationResponse,
  reconcileSupplierStatement,
} from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string };
}

const MATCH_STATUS_STYLES: Record<string, string> = {
  MATCHED: "bg-green-100 text-green-800",
  UNMATCHED_GL: "bg-orange-100 text-orange-800",
  UNMATCHED_STATEMENT: "bg-yellow-100 text-yellow-800",
  DISPUTED: "bg-red-100 text-red-800",
};

function ReconciliationWorkspace({ companyId }: { companyId: string }) {
  const searchParams = useSearchParams();
  const [supplierId, setSupplierId] = useState(searchParams.get("supplier_id") ?? "");
  const [statementDate, setStatementDate] = useState(new Date().toISOString().slice(0, 10));
  const [statementTotal, setStatementTotal] = useState("");
  const [lines, setLines] = useState<ReconcileStatementLine[]>([{ reference: "", amount: "" }]);
  const [result, setResult] = useState<SupplierStatementReconciliationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateLine(index: number, field: keyof ReconcileStatementLine, value: string) {
    setLines((prev) =>
      prev.map((line, i) => (i === index ? { ...line, [field]: value } : line))
    );
  }

  function addLine() {
    setLines((prev) => [...prev, { reference: "", amount: "" }]);
  }

  function removeLine(index: number) {
    setLines((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleReconcile() {
    if (!supplierId) {
      setError("Supplier ID is required.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await reconcileSupplierStatement(
        companyId,
        supplierId,
        statementDate,
        statementTotal || "0",
        lines.filter((l) => l.amount)
      );
      setResult(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reconcile statement");
    } finally {
      setLoading(false);
    }
  }

  const matchedItems = result?.items.filter((i) => i.match_status === "MATCHED") ?? [];
  const unmatchedItems = result?.items.filter((i) => i.match_status !== "MATCHED") ?? [];

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">
          Supplier Statement Reconciliation
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Enter the supplier&apos;s statement lines to match against open AP bills.
        </p>
      </div>

      <div className="mb-6 space-y-4 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <label className="text-sm text-gray-700">
            Supplier ID
            <input
              type="text"
              value={supplierId}
              onChange={(e) => setSupplierId(e.target.value)}
              placeholder="Supplier UUID"
              className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1 text-sm"
            />
          </label>
          <label className="text-sm text-gray-700">
            Statement Date
            <input
              type="date"
              value={statementDate}
              onChange={(e) => setStatementDate(e.target.value)}
              className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1 text-sm"
            />
          </label>
          <label className="text-sm text-gray-700">
            Statement Total
            <input
              type="text"
              value={statementTotal}
              onChange={(e) => setStatementTotal(e.target.value)}
              placeholder="0.00"
              className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1 text-sm"
            />
          </label>
        </div>

        <div>
          <p className="mb-2 text-sm font-semibold text-gray-900">Statement Lines</p>
          <div className="space-y-2">
            {lines.map((line, i) => (
              <div key={i} className="flex gap-2">
                <input
                  type="text"
                  value={line.reference ?? ""}
                  onChange={(e) => updateLine(i, "reference", e.target.value)}
                  placeholder="Reference"
                  className="flex-1 rounded-md border border-gray-300 px-2 py-1 text-sm"
                />
                <input
                  type="text"
                  value={line.amount}
                  onChange={(e) => updateLine(i, "amount", e.target.value)}
                  placeholder="Amount"
                  className="w-32 rounded-md border border-gray-300 px-2 py-1 text-sm"
                />
                <button
                  onClick={() => removeLine(i)}
                  className="rounded-md border border-gray-300 px-2 py-1 text-xs text-gray-500 hover:bg-gray-50"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
          <button
            onClick={addLine}
            className="mt-2 rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
          >
            + Add Line
          </button>
        </div>

        <button
          onClick={handleReconcile}
          disabled={loading}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Reconciling..." : "Reconcile"}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {result && (
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <p className="text-sm text-gray-500">
              Session status:{" "}
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                  result.status === "COMPLETED"
                    ? "bg-green-100 text-green-800"
                    : "bg-yellow-100 text-yellow-800"
                }`}
              >
                {result.status}
              </span>
            </p>
          </div>

          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <div>
              <p className="mb-2 text-sm font-semibold text-gray-900">
                Matched ({matchedItems.length})
              </p>
              {matchedItems.length === 0 ? (
                <p className="text-xs text-gray-400">No matched items.</p>
              ) : (
                <ul className="space-y-1 text-sm">
                  {matchedItems.map((item) => (
                    <li
                      key={item.id}
                      className="flex justify-between rounded-md bg-green-50 px-3 py-2"
                    >
                      <span>{item.statement_line_reference ?? "—"}</span>
                      <span>{item.gl_amount}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <p className="mb-2 text-sm font-semibold text-gray-900">
                Unmatched ({unmatchedItems.length})
              </p>
              {unmatchedItems.length === 0 ? (
                <p className="text-xs text-gray-400">No unmatched items.</p>
              ) : (
                <ul className="space-y-1 text-sm">
                  {unmatchedItems.map((item) => (
                    <li
                      key={item.id}
                      className="flex items-center justify-between rounded-md bg-gray-50 px-3 py-2"
                    >
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                          MATCH_STATUS_STYLES[item.match_status] ?? "bg-gray-100 text-gray-500"
                        }`}
                      >
                        {item.match_status}
                      </span>
                      <span>{item.statement_amount ?? item.gl_amount}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Supplier Statement Reconciliation workspace — side-by-side GL vs statement
 * with match/unmatch display.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T172
 */
export default function ReconcileStatementPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  return (
    <Suspense fallback={<div className="py-8 text-center text-gray-500">Loading...</div>}>
      <ReconciliationWorkspace companyId={companyId} />
    </Suspense>
  );
}
