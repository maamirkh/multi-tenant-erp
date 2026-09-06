"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  JournalEntryResponse,
  JournalEntryStatus,
  getJournals,
} from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string };
}

const STATUS_BADGE: Record<JournalEntryStatus, string> = {
  DRAFT: "bg-gray-100 text-gray-600",
  SUBMITTED: "bg-blue-100 text-blue-800",
  APPROVED: "bg-purple-100 text-purple-800",
  POSTED: "bg-green-100 text-green-800",
  REJECTED: "bg-red-100 text-red-700",
  REVERSED: "bg-amber-100 text-amber-800",
};

/**
 * Journal Entry list page — filterable by date/status/source, paginated.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T103
 */
export default function JournalsPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const [journals, setJournals] = useState<JournalEntryResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  useEffect(() => {
    if (!companyId) return;
    load();
  }, [companyId, statusFilter, startDate, endDate]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getJournals(companyId, {
        status: statusFilter || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        limit: 50,
      });
      setJournals(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load journals");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Journal Entries</h1>
          <p className="mt-1 text-sm text-gray-500">
            The General Ledger — manual and automated postings.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href={`/${companyId}/journals/recurring`}
            className="text-sm font-medium text-blue-600 hover:underline"
          >
            Recurring Templates
          </Link>
          <Link
            href={`/${companyId}/journals/approval-queue`}
            className="text-sm font-medium text-blue-600 hover:underline"
          >
            Approval Queue
          </Link>
          <Link
            href={`/${companyId}/reports/gl`}
            className="text-sm font-medium text-blue-600 hover:underline"
          >
            GL Report
          </Link>
          <Link
            href={`/${companyId}/journals/new`}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            New Journal
          </Link>
        </div>
      </div>

      <div className="mb-4 flex items-center gap-3">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm"
        >
          <option value="">All statuses</option>
          {Object.keys(STATUS_BADGE).map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm"
        />
        <span className="text-sm text-gray-400">to</span>
        <input
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm"
        />
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : journals.length === 0 ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          No journal entries found.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-md border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Number</th>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Date</th>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Type</th>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Source</th>
                <th className="px-4 py-2 text-right font-medium text-gray-600">Debit</th>
                <th className="px-4 py-2 text-right font-medium text-gray-600">Credit</th>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {journals.map((j) => (
                <tr key={j.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 font-mono text-xs text-gray-700">
                    {j.journal_number ?? "(unposted)"}
                  </td>
                  <td className="px-4 py-2 text-gray-600">{j.posting_date}</td>
                  <td className="px-4 py-2 text-gray-600">{j.journal_type}</td>
                  <td className="px-4 py-2 text-gray-600">{j.posting_source}</td>
                  <td className="px-4 py-2 text-right text-gray-900">{j.total_debit_base}</td>
                  <td className="px-4 py-2 text-right text-gray-900">{j.total_credit_base}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${STATUS_BADGE[j.status]}`}
                    >
                      {j.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
