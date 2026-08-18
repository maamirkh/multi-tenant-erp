"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { getAccessToken } from "@/lib/auth/tokenStorage";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface GoodsReceiptListItem {
  id: string;
  gr_number: string;
  status: string;
  po_id: string;
  supplier_id: string;
  received_at: string | null;
  delivery_note_number: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  CONFIRMED: "bg-green-100 text-green-700",
};

export default function GoodsReceiptsPage() {
  const [receipts, setReceipts] = useState<GoodsReceiptListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("");

  useEffect(() => {
    async function fetchReceipts() {
      try {
        const companyId = localStorage.getItem("erp_active_company_id") ?? "";
        const params = new URLSearchParams();
        if (statusFilter) params.set("status", statusFilter);
        const res = await fetch(
          `${API_BASE}/api/v1/companies/${companyId}/purchase/goods-receipts?${params}`,
          { headers: { Authorization: `Bearer ${getAccessToken()}` } }
        );
        if (!res.ok) throw new Error("Failed to fetch goods receipts");
        const json = await res.json();
        setReceipts(json.data ?? []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    fetchReceipts();
  }, [statusFilter]);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Goods Receipts</h1>
        <Link
          href="goods-receipts/new"
          className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 text-sm font-medium"
        >
          New Receipt
        </Link>
      </div>

      <div className="mb-4">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border border-gray-300 rounded-md px-3 py-2 text-sm"
        >
          <option value="">All Statuses</option>
          <option value="DRAFT">Draft</option>
          <option value="CONFIRMED">Confirmed</option>
        </select>
      </div>

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : receipts.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <p className="text-lg">No goods receipts found.</p>
          <p className="text-sm mt-1">Create a receipt against an approved purchase order.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-500">GR Number</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">Status</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">Delivery Note</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">Received At</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {receipts.map((gr) => (
                <tr key={gr.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-indigo-700">
                    {gr.gr_number}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                        STATUS_COLORS[gr.status] ?? "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {gr.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {gr.delivery_note_number ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {gr.received_at
                      ? new Date(gr.received_at).toLocaleDateString()
                      : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`goods-receipts/${gr.id}`}
                      className="text-indigo-600 hover:underline text-sm"
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
