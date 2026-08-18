"use client";

/**
 * Stock Transfers — list page with status filter.
 * Phase 7 — Stock Operations: Transfers & Reservations
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { getAccessToken } from "@/lib/auth/tokenStorage";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type TransferStatus = "DRAFT" | "IN_TRANSIT" | "COMPLETED" | "CANCELLED";

interface Transfer {
  id: string;
  source_warehouse_id: string;
  destination_warehouse_id: string;
  status: TransferStatus;
  reference_no: string | null;
  notes: string | null;
  version: number;
  created_at: string;
}

const STATUS_BADGE: Record<TransferStatus, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  IN_TRANSIT: "bg-yellow-100 text-yellow-800",
  COMPLETED: "bg-green-100 text-green-800",
  CANCELLED: "bg-red-100 text-red-700",
};

export default function TransfersPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";

  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId) return;
    setLoading(true);
    const qs = statusFilter ? `?status_filter=${statusFilter}` : "";
    fetch(`${API_BASE}/api/v1/companies/${companyId}/inventory/stock-transfers${qs}`, {
      headers: { Authorization: `Bearer ${getAccessToken()}` },
    })
      .then((r) => r.json())
      .then((body) => {
        setTransfers(body.data ?? []);
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load transfers.");
        setLoading(false);
      });
  }, [companyId, statusFilter]);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900">
          Stock Transfers
        </h1>
        <Link
          href={`/inventory/transfers/new`}
          className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          + New Transfer
        </Link>
      </div>

      {/* Status filter */}
      <div className="flex gap-2 flex-wrap">
        {["", "DRAFT", "IN_TRANSIT", "COMPLETED", "CANCELLED"].map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`rounded-full px-3 py-1 text-xs font-medium border transition-colors ${
              statusFilter === s
                ? "bg-blue-600 text-white border-blue-600"
                : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
            }`}
          >
            {s || "All"}
          </button>
        ))}
      </div>

      {loading && <p className="text-sm text-gray-500">Loading transfers…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {!loading && !error && transfers.length === 0 && (
        <div className="rounded-lg border border-dashed border-gray-200 py-16 text-center">
          <p className="text-gray-400 text-sm">No transfers found.</p>
          <Link
            href={`/inventory/transfers/new`}
            className="mt-3 inline-block text-sm text-blue-600 hover:underline"
          >
            Create your first transfer
          </Link>
        </div>
      )}

      {!loading && transfers.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-500">
                  Reference
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">
                  Source Warehouse
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">
                  Destination Warehouse
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">
                  Status
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">
                  Created
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {transfers.map((t) => (
                <tr key={t.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs text-gray-700">
                    {t.reference_no ?? t.id.slice(0, 8) + "…"}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-600">
                    {t.source_warehouse_id.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-600">
                    {t.destination_warehouse_id.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${
                        STATUS_BADGE[t.status] ?? ""
                      }`}
                    >
                      {t.status.replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(t.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`/inventory/transfers/${t.id}`}
                      className="text-blue-600 hover:underline text-xs"
                    >
                      View
                    </Link>
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
