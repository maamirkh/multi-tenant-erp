"use client";

import { useEffect, useState } from "react";
import { ChequeResponse, getCheques, updateChequeStatus } from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string };
}

const STATUS_STYLES: Record<string, string> = {
  ISSUED: "bg-blue-100 text-blue-800",
  PRESENTED: "bg-yellow-100 text-yellow-800",
  CLEARED: "bg-green-100 text-green-800",
  CANCELLED: "bg-gray-100 text-gray-500",
  STALE: "bg-orange-100 text-orange-800",
};

const NEXT_STATUS: Record<string, string[]> = {
  ISSUED: ["PRESENTED", "CLEARED", "CANCELLED", "STALE"],
  PRESENTED: ["CLEARED"],
  CLEARED: [],
  CANCELLED: [],
  STALE: [],
};

/**
 * Cheque Register page — list with status filter, status update controls.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T189
 */
export default function ChequeRegisterPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const [cheques, setCheques] = useState<ChequeResponse[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId) return;
    load();
  }, [companyId, statusFilter]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getCheques(companyId, statusFilter || undefined);
      setCheques(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load cheques");
    } finally {
      setLoading(false);
    }
  }

  async function handleStatusChange(chequeId: string, newStatus: string) {
    setError(null);
    try {
      await updateChequeStatus(
        companyId,
        chequeId,
        newStatus as "PRESENTED" | "CLEARED" | "CANCELLED" | "STALE"
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update cheque status");
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Cheque Register</h1>
          <p className="mt-1 text-sm text-gray-500">
            Track issued cheques through their clearing lifecycle.
          </p>
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-md border border-gray-300 px-2 py-1 text-sm"
        >
          <option value="">All statuses</option>
          <option value="ISSUED">Issued</option>
          <option value="PRESENTED">Presented</option>
          <option value="CLEARED">Cleared</option>
          <option value="CANCELLED">Cancelled</option>
          <option value="STALE">Stale</option>
        </select>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : cheques.length === 0 ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          No cheques found.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 text-left text-xs font-medium text-gray-500">
                <th className="px-4 py-2">Cheque #</th>
                <th className="px-4 py-2">Payee</th>
                <th className="px-4 py-2">Date</th>
                <th className="px-4 py-2 text-right">Amount</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {cheques.map((cheque) => (
                <tr key={cheque.id} className="border-b border-gray-100">
                  <td className="px-4 py-2">{cheque.cheque_number}</td>
                  <td className="px-4 py-2">{cheque.payee_name}</td>
                  <td className="px-4 py-2">{cheque.cheque_date}</td>
                  <td className="px-4 py-2 text-right">{cheque.amount}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                        STATUS_STYLES[cheque.status] ?? "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {cheque.status}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex gap-1">
                      {NEXT_STATUS[cheque.status]?.map((next) => (
                        <button
                          key={next}
                          onClick={() => handleStatusChange(cheque.id, next)}
                          className="rounded-md border border-gray-300 px-2 py-1 text-[10px] font-medium text-gray-700 hover:bg-gray-50"
                        >
                          {next}
                        </button>
                      ))}
                    </div>
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
