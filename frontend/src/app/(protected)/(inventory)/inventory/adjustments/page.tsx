"use client";

/**
 * Inventory Adjustments — list page with status filter and pending-approval queue.
 * Phase 6 — Stock Operations: Adjustments
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

type AdjustmentStatus = "DRAFT" | "PENDING_APPROVAL" | "APPROVED" | "REJECTED";

interface Adjustment {
  id: string;
  product_id: string;
  warehouse_id: string;
  movement_type: "ADJUSTMENT_IN" | "ADJUSTMENT_OUT";
  quantity: string;
  status: AdjustmentStatus;
  notes: string | null;
  old_quantity: string | null;
  new_quantity: string | null;
  created_at: string;
}

const STATUS_BADGE: Record<AdjustmentStatus, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  PENDING_APPROVAL: "bg-yellow-100 text-yellow-800",
  APPROVED: "bg-green-100 text-green-800",
  REJECTED: "bg-red-100 text-red-700",
};

export default function AdjustmentsPage() {
  const params = useParams<{ company_id: string }>();
  const companyId = params?.company_id;

  const [adjustments, setAdjustments] = useState<Adjustment[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId) return;
    setLoading(true);
    const qs = statusFilter ? `?status_filter=${statusFilter}` : "";
    fetch(`/api/v1/companies/${companyId}/inventory/adjustments${qs}`, {
      credentials: "include",
    })
      .then((r) => r.json())
      .then((body) => {
        setAdjustments(body.data ?? []);
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load adjustments.");
        setLoading(false);
      });
  }, [companyId, statusFilter]);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900">
          Inventory Adjustments
        </h1>
        <Link
          href={`/inventory/adjustments/new`}
          className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          + New Adjustment
        </Link>
      </div>

      {/* Status filter */}
      <div className="flex gap-2 flex-wrap">
        {["", "DRAFT", "PENDING_APPROVAL", "APPROVED", "REJECTED"].map(
          (s) => (
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
          )
        )}
      </div>

      {loading && (
        <p className="text-sm text-gray-500">Loading adjustments…</p>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {!loading && !error && adjustments.length === 0 && (
        <div className="rounded-lg border border-dashed border-gray-200 py-16 text-center">
          <p className="text-gray-400 text-sm">No adjustments found.</p>
          <Link
            href={`/inventory/adjustments/new`}
            className="mt-3 inline-block text-sm text-blue-600 hover:underline"
          >
            Create your first adjustment
          </Link>
        </div>
      )}

      {!loading && adjustments.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-500">
                  Type
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">
                  Quantity
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">
                  Status
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">
                  Old Qty
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">
                  New Qty
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">
                  Created
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {adjustments.map((adj) => (
                <tr key={adj.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <span
                      className={`font-medium ${
                        adj.movement_type === "ADJUSTMENT_IN"
                          ? "text-green-700"
                          : "text-red-600"
                      }`}
                    >
                      {adj.movement_type === "ADJUSTMENT_IN" ? "▲ IN" : "▼ OUT"}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-900">
                    {Number(adj.quantity).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${
                        STATUS_BADGE[adj.status] ?? ""
                      }`}
                    >
                      {adj.status.replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600 font-mono">
                    {adj.old_quantity ? Number(adj.old_quantity).toLocaleString() : "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-600 font-mono">
                    {adj.new_quantity ? Number(adj.new_quantity).toLocaleString() : "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(adj.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`/inventory/adjustments/${adj.id}`}
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
