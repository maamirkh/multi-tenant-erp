"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  JournalEntryResponse,
  approveJournal,
  getJournals,
  rejectJournal,
} from "@/lib/api/accounting";

/**
 * Approval Queue page — journals pending approval (status=SUBMITTED),
 * with approve/reject actions.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T105
 */
export default function ApprovalQueuePage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";
  const [journals, setJournals] = useState<JournalEntryResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  useEffect(() => {
    if (!companyId) return;
    load();
  }, [companyId]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getJournals(companyId, { status: "SUBMITTED", limit: 100 });
      setJournals(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load approval queue");
    } finally {
      setLoading(false);
    }
  }

  async function handleApprove(journalId: string) {
    setError(null);
    try {
      await approveJournal(companyId, journalId);
      setSuccess("Journal approved");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to approve journal");
    }
  }

  async function handleReject(journalId: string) {
    if (!rejectReason.trim()) {
      setError("A rejection reason is required.");
      return;
    }
    setError(null);
    try {
      await rejectJournal(companyId, journalId, rejectReason);
      setSuccess("Journal rejected");
      setRejectingId(null);
      setRejectReason("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reject journal");
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <Link href={`/${companyId}/journals`} className="text-sm text-blue-600 hover:underline">
        ← Journal Entries
      </Link>
      <h1 className="mt-1 mb-1 text-2xl font-semibold text-gray-900">Approval Queue</h1>
      <p className="mb-6 text-sm text-gray-500">
        Journal entries awaiting approval before they can be posted.
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
      ) : journals.length === 0 ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          No journals pending approval.
        </div>
      ) : (
        <div className="space-y-3">
          {journals.map((j) => (
            <div key={j.id} className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <div className="mb-2 flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-gray-900">
                    {j.reference || j.description || j.journal_type}
                  </p>
                  <p className="text-xs text-gray-500">
                    {j.posting_date} · {j.journal_type} · Debit {j.total_debit_base} / Credit{" "}
                    {j.total_credit_base}
                  </p>
                </div>
              </div>

              {rejectingId === j.id ? (
                <div className="space-y-2">
                  <input
                    autoFocus
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    placeholder="Rejection reason (required)"
                    className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleReject(j.id)}
                      className="rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700"
                    >
                      Confirm Reject
                    </button>
                    <button
                      onClick={() => {
                        setRejectingId(null);
                        setRejectReason("");
                      }}
                      className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex gap-2">
                  <button
                    onClick={() => handleApprove(j.id)}
                    className="rounded-md bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => setRejectingId(j.id)}
                    className="rounded-md border border-red-300 bg-red-50 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-100"
                  >
                    Reject
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
