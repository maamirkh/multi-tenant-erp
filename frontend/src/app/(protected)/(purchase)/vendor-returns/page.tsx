"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getAccessToken } from "@/lib/auth/tokenStorage";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  SUBMITTED: "bg-blue-100 text-blue-700",
  APPROVED: "bg-indigo-100 text-indigo-700",
  DISPATCHED: "bg-yellow-100 text-yellow-700",
  COMPLETED: "bg-green-100 text-green-700",
  CANCELLED: "bg-red-100 text-red-700",
};

interface VendorReturn {
  id: string;
  rma_number: string;
  status: string;
  gr_id: string;
  supplier_id: string;
  credit_note_pending: boolean;
  dispatched_at: string | null;
  completed_at: string | null;
}

export default function VendorReturnsPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";
  const [returns, setReturns] = useState<VendorReturn[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchReturns = async () => {
      setLoading(true);
      try {
        const qs = statusFilter ? `?status=${statusFilter}` : "";
        const res = await fetch(
          `${API_BASE}/api/v1/companies/${companyId}/purchase/vendor-returns${qs}`,
          { headers: { Authorization: `Bearer ${getAccessToken()}` } }
        );
        if (!res.ok) throw new Error(await res.text());
        const json = await res.json();
        setReturns(json.data ?? []);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    };
    if (companyId) fetchReturns();
  }, [companyId, statusFilter]);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Vendor Returns (RMA)</h1>
        <Link
          href={`/vendor-returns/new`}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
        >
          + New Return
        </Link>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <select
          className="border rounded px-3 py-1.5 text-sm"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All statuses</option>
          {Object.keys(STATUS_COLORS).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {error && <p className="text-red-600 mb-4">{error}</p>}

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : returns.length === 0 ? (
        <p className="text-gray-500">No vendor returns found.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full border text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left border-b">RMA Number</th>
                <th className="px-4 py-2 text-left border-b">Status</th>
                <th className="px-4 py-2 text-left border-b">GR Reference</th>
                <th className="px-4 py-2 text-left border-b">Credit Note</th>
                <th className="px-4 py-2 text-left border-b">Dispatched</th>
                <th className="px-4 py-2 text-left border-b">Actions</th>
              </tr>
            </thead>
            <tbody>
              {returns.map((r) => (
                <tr key={r.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 border-b font-mono">{r.rma_number}</td>
                  <td className="px-4 py-2 border-b">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[r.status] ?? ""}`}>
                      {r.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 border-b font-mono text-xs">{r.gr_id}</td>
                  <td className="px-4 py-2 border-b">
                    {r.credit_note_pending ? (
                      <span className="text-orange-600 font-medium text-xs">Pending</span>
                    ) : (
                      <span className="text-gray-400 text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2 border-b text-xs text-gray-600">
                    {r.dispatched_at ? new Date(r.dispatched_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-2 border-b">
                    <Link
                      href={`/vendor-returns/${r.id}`}
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
