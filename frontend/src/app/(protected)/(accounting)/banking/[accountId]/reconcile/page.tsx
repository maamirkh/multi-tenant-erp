"use client";

import { useState } from "react";
import {
  ReconciliationReportResponse,
  autoMatchBankReconciliation,
  completeBankReconciliation,
  getBankReconciliationReport,
  importBankStatement,
  lockBankReconciliation,
  manualMatchBankReconciliation,
  startBankReconciliation,
  unmatchBankReconciliation,
} from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string; accountId: string };
}

const STATUS_STYLES: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-600",
  IN_PROGRESS: "bg-yellow-100 text-yellow-800",
  COMPLETED: "bg-green-100 text-green-800",
  LOCKED: "bg-blue-100 text-blue-800",
};

/**
 * Bank Reconciliation workspace — split panel: unmatched GL transactions on
 * the left, unmatched statement lines on the right; matched items below;
 * difference indicator; complete/lock controls.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T188
 */
export default function BankReconciliationPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const accountId = params?.accountId ?? "";

  const [statementDate, setStatementDate] = useState(new Date().toISOString().slice(0, 10));
  const [statementClosingBalance, setStatementClosingBalance] = useState("");
  const [reconciliationId, setReconciliationId] = useState<string | null>(null);
  const [report, setReport] = useState<ReconciliationReportResponse | null>(null);
  const [csvText, setCsvText] = useState("");
  const [selectedTransactionId, setSelectedTransactionId] = useState<string | null>(null);
  const [selectedLineId, setSelectedLineId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function refreshReport(rid: string) {
    const res = await getBankReconciliationReport(companyId, accountId, rid);
    setReport(res.data);
  }

  async function handleStart() {
    if (!statementClosingBalance) {
      setError("Statement closing balance is required.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await startBankReconciliation(
        companyId,
        accountId,
        statementDate,
        statementClosingBalance
      );
      setReconciliationId(res.data.id);
      await refreshReport(res.data.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start reconciliation");
    } finally {
      setLoading(false);
    }
  }

  function parseCsv(): {
    statement_date: string;
    amount: string;
    reference: string | null;
    description: string | null;
  }[] {
    return csvText
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [date, amount, reference, description] = line.split(",").map((s) => s.trim());
        return {
          statement_date: date ?? "",
          amount: amount ?? "",
          reference: reference || null,
          description: description || null,
        };
      });
  }

  async function handleImport() {
    if (!reconciliationId) return;
    setError(null);
    try {
      const lines = parseCsv();
      await importBankStatement(companyId, accountId, reconciliationId, lines);
      setCsvText("");
      await refreshReport(reconciliationId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to import statement lines");
    }
  }

  async function handleAutoMatch() {
    if (!reconciliationId) return;
    setError(null);
    try {
      await autoMatchBankReconciliation(companyId, accountId, reconciliationId);
      await refreshReport(reconciliationId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Auto-match failed");
    }
  }

  async function handleManualMatch() {
    if (!reconciliationId || !selectedTransactionId || !selectedLineId) {
      setError("Select one unmatched transaction and one unmatched statement line first.");
      return;
    }
    setError(null);
    try {
      await manualMatchBankReconciliation(
        companyId,
        accountId,
        reconciliationId,
        selectedTransactionId,
        selectedLineId
      );
      setSelectedTransactionId(null);
      setSelectedLineId(null);
      await refreshReport(reconciliationId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Manual match failed");
    }
  }

  async function handleUnmatch(matchId: string) {
    if (!reconciliationId) return;
    setError(null);
    try {
      await unmatchBankReconciliation(companyId, accountId, reconciliationId, matchId);
      await refreshReport(reconciliationId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unmatch failed");
    }
  }

  async function handleComplete() {
    if (!reconciliationId) return;
    setError(null);
    try {
      await completeBankReconciliation(companyId, accountId, reconciliationId);
      await refreshReport(reconciliationId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cannot complete — difference is not zero");
    }
  }

  async function handleLock() {
    if (!reconciliationId) return;
    setError(null);
    try {
      await lockBankReconciliation(companyId, accountId, reconciliationId);
      await refreshReport(reconciliationId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to lock reconciliation");
    }
  }

  const reconciliation = report?.reconciliation;
  const isLocked = reconciliation?.status === "LOCKED";

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Bank Reconciliation</h1>
        <p className="mt-1 text-sm text-gray-500">
          Match GL bank transactions to the imported statement, then complete and lock.
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {!reconciliationId ? (
        <div className="grid grid-cols-1 gap-4 rounded-lg border border-gray-200 bg-white p-4 shadow-sm sm:grid-cols-3">
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
            Statement Closing Balance
            <input
              type="text"
              value={statementClosingBalance}
              onChange={(e) => setStatementClosingBalance(e.target.value)}
              placeholder="0.00"
              className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1 text-sm"
            />
          </label>
          <div className="flex items-end">
            <button
              onClick={handleStart}
              disabled={loading}
              className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Starting..." : "Start Reconciliation"}
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex items-center gap-4">
              <span
                className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  STATUS_STYLES[reconciliation?.status ?? ""] ?? "bg-gray-100 text-gray-500"
                }`}
              >
                {reconciliation?.status}
              </span>
              <span className="text-sm text-gray-700">
                Difference:{" "}
                <span
                  className={
                    reconciliation?.difference === "0.000000"
                      ? "font-semibold text-green-700"
                      : "font-semibold text-red-700"
                  }
                >
                  {reconciliation?.difference}
                </span>
              </span>
            </div>
            <div className="flex gap-3">
              {reconciliation?.status !== "COMPLETED" && !isLocked && (
                <button
                  onClick={handleComplete}
                  className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
                >
                  Complete
                </button>
              )}
              {reconciliation?.status === "COMPLETED" && (
                <button
                  onClick={handleLock}
                  className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                >
                  Lock
                </button>
              )}
            </div>
          </div>

          {!isLocked && (
            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <p className="mb-2 text-sm font-semibold text-gray-900">
                Import Statement Lines (CSV: date,amount,reference,description)
              </p>
              <textarea
                value={csvText}
                onChange={(e) => setCsvText(e.target.value)}
                rows={4}
                placeholder="2026-08-01,1500.00,REF-001,Customer payment"
                className="w-full rounded-md border border-gray-300 px-2 py-1 text-sm font-mono"
              />
              <div className="mt-2 flex gap-3">
                <button
                  onClick={handleImport}
                  className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                >
                  Import Lines
                </button>
                <button
                  onClick={handleAutoMatch}
                  className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                >
                  Run Auto-Match
                </button>
                <button
                  onClick={handleManualMatch}
                  className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
                >
                  Manual Match Selected
                </button>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <p className="mb-2 text-sm font-semibold text-gray-900">
                Unmatched GL Transactions ({report?.unmatched_transactions.length ?? 0})
              </p>
              <ul className="space-y-1 text-sm">
                {report?.unmatched_transactions.map((t) => (
                  <li key={t.id}>
                    <button
                      onClick={() => setSelectedTransactionId(t.id)}
                      className={`w-full rounded-md px-3 py-2 text-left ${
                        selectedTransactionId === t.id
                          ? "bg-blue-100"
                          : "bg-gray-50 hover:bg-gray-100"
                      }`}
                    >
                      {t.transaction_date} · {t.transaction_type} · {t.amount}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <p className="mb-2 text-sm font-semibold text-gray-900">
                Unmatched Statement Lines ({report?.unmatched_statement_lines.length ?? 0})
              </p>
              <ul className="space-y-1 text-sm">
                {report?.unmatched_statement_lines.map((l) => (
                  <li key={l.id}>
                    <button
                      onClick={() => setSelectedLineId(l.id)}
                      className={`w-full rounded-md px-3 py-2 text-left ${
                        selectedLineId === l.id ? "bg-blue-100" : "bg-gray-50 hover:bg-gray-100"
                      }`}
                    >
                      {l.statement_date} · {l.reference ?? "—"} · {l.amount}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <p className="mb-2 text-sm font-semibold text-gray-900">
              Matched Items ({report?.matches.length ?? 0})
            </p>
            <ul className="space-y-1 text-sm">
              {report?.matches.map((m) => (
                <li
                  key={m.id}
                  className="flex items-center justify-between rounded-md bg-green-50 px-3 py-2"
                >
                  <span>
                    {m.match_type} match · matched {new Date(m.matched_at).toLocaleString()}
                  </span>
                  {!isLocked && (
                    <button
                      onClick={() => handleUnmatch(m.id)}
                      className="text-xs text-red-600 hover:underline"
                    >
                      Unmatch
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
