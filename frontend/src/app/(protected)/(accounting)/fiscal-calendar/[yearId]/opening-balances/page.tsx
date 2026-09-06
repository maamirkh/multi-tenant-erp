"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AccountResponse,
  OpeningBalanceLine,
  OpeningBalanceResponse,
  getAccounts,
  getOpeningBalances,
  setupOpeningBalances,
} from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string; yearId: string };
}

interface DraftLine {
  account_id: string;
  debit_amount: string;
  credit_amount: string;
}

/**
 * Opening Balance entry screen — account list with debit/credit input and
 * a running total showing balance/imbalance.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T082
 */
export default function OpeningBalancesPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const yearId = params?.yearId ?? "";

  const [accounts, setAccounts] = useState<AccountResponse[]>([]);
  const [existing, setExisting] = useState<OpeningBalanceResponse[]>([]);
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId || !yearId) return;
    load();
  }, [companyId, yearId]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [accountsRes, balancesRes] = await Promise.all([
        getAccounts(companyId, false),
        getOpeningBalances(companyId, yearId),
      ]);
      const leafAccounts = (accountsRes.data as AccountResponse[]).filter(
        (a) => a.is_leaf
      );
      setAccounts(leafAccounts);
      setExisting(balancesRes.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load accounts");
    } finally {
      setLoading(false);
    }
  }

  function addLine() {
    setLines([...lines, { account_id: "", debit_amount: "", credit_amount: "" }]);
  }

  function updateLine(index: number, patch: Partial<DraftLine>) {
    setLines(lines.map((l, i) => (i === index ? { ...l, ...patch } : l)));
  }

  function removeLine(index: number) {
    setLines(lines.filter((_, i) => i !== index));
  }

  const totals = useMemo(() => {
    const totalDebit = lines.reduce((sum, l) => sum + (parseFloat(l.debit_amount) || 0), 0);
    const totalCredit = lines.reduce(
      (sum, l) => sum + (parseFloat(l.credit_amount) || 0),
      0
    );
    return { totalDebit, totalCredit, balanced: totalDebit === totalCredit };
  }, [lines]);

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      const payload: OpeningBalanceLine[] = lines
        .filter((l) => l.account_id)
        .map((l) => ({
          account_id: l.account_id,
          debit_amount: l.debit_amount || "0",
          credit_amount: l.credit_amount || "0",
        }));
      await setupOpeningBalances(companyId, yearId, payload);
      setSuccess("Opening balances recorded");
      setLines([]);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record opening balances");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <Link
        href={`/${companyId}/fiscal-calendar/${yearId}/periods`}
        className="text-sm text-blue-600 hover:underline"
      >
        ← Periods
      </Link>
      <h1 className="mt-1 mb-1 text-2xl font-semibold text-gray-900">
        Opening Balances
      </h1>
      <p className="mb-6 text-sm text-gray-500">
        Total opening debits must equal total opening credits before commit.
      </p>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-4 rounded-md bg-green-50 p-3 text-sm text-green-700" role="status">
          {success}
        </div>
      )}

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : (
        <>
          {existing.length > 0 && (
            <div className="mb-6 overflow-x-auto rounded-md border border-gray-200">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left font-medium text-gray-600">
                      Account
                    </th>
                    <th className="px-4 py-2 text-right font-medium text-gray-600">
                      Debit
                    </th>
                    <th className="px-4 py-2 text-right font-medium text-gray-600">
                      Credit
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 bg-white">
                  {existing.map((b) => {
                    const account = accounts.find((a) => a.id === b.account_id);
                    return (
                      <tr key={b.id}>
                        <td className="px-4 py-2 text-gray-900">
                          {account
                            ? `${account.account_code} — ${account.account_name}`
                            : b.account_id}
                        </td>
                        <td className="px-4 py-2 text-right text-gray-600">
                          {b.debit_amount}
                        </td>
                        <td className="px-4 py-2 text-right text-gray-600">
                          {b.credit_amount}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <div className="rounded-md border border-gray-200 bg-white p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-700">New Lines</h2>
              <button
                onClick={addLine}
                className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                + Add Line
              </button>
            </div>

            {lines.length === 0 ? (
              <p className="text-sm text-gray-400">No lines yet. Click &quot;Add Line&quot;.</p>
            ) : (
              <div className="space-y-2">
                {lines.map((line, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <select
                      value={line.account_id}
                      onChange={(e) => updateLine(i, { account_id: e.target.value })}
                      className="flex-1 rounded-md border border-gray-300 px-2 py-1.5 text-sm"
                    >
                      <option value="">Select account…</option>
                      {accounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.account_code} — {a.account_name}
                        </option>
                      ))}
                    </select>
                    <input
                      type="number"
                      step="0.01"
                      placeholder="Debit"
                      value={line.debit_amount}
                      onChange={(e) => updateLine(i, { debit_amount: e.target.value })}
                      className="w-28 rounded-md border border-gray-300 px-2 py-1.5 text-sm text-right"
                    />
                    <input
                      type="number"
                      step="0.01"
                      placeholder="Credit"
                      value={line.credit_amount}
                      onChange={(e) => updateLine(i, { credit_amount: e.target.value })}
                      className="w-28 rounded-md border border-gray-300 px-2 py-1.5 text-sm text-right"
                    />
                    <button
                      onClick={() => removeLine(i)}
                      className="text-xs text-red-600 hover:underline"
                      aria-label="Remove line"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="mt-4 flex items-center justify-between border-t border-gray-100 pt-4">
              <div className="text-sm">
                <span className="text-gray-500">Debit: </span>
                <span className="font-medium text-gray-900">
                  {totals.totalDebit.toFixed(2)}
                </span>
                <span className="ml-4 text-gray-500">Credit: </span>
                <span className="font-medium text-gray-900">
                  {totals.totalCredit.toFixed(2)}
                </span>
                <span
                  className={`ml-3 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                    totals.balanced
                      ? "bg-green-100 text-green-800"
                      : "bg-red-100 text-red-700"
                  }`}
                >
                  {totals.balanced ? "Balanced" : "Imbalanced"}
                </span>
              </div>
              <button
                onClick={handleSubmit}
                disabled={submitting || lines.length === 0 || !totals.balanced}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {submitting ? "Saving..." : "Save Opening Balances"}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
