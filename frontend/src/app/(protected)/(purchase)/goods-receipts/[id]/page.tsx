"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

interface GRLine {
  id: string;
  po_line_id: string;
  product_id: string | null;
  quantity_received: string;
  quantity_rejected: string;
  unit_cost: string;
  po_unit_cost: string;
  ppv_amount: string;
  ppv_percentage: string;
  notes: string | null;
}

interface GoodsReceipt {
  id: string;
  gr_number: string;
  status: string;
  po_id: string;
  supplier_id: string;
  received_by: string | null;
  received_at: string | null;
  delivery_note_number: string | null;
  notes: string | null;
  warehouse_id: string | null;
  landed_cost_ready: boolean;
  lines: GRLine[];
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  CONFIRMED: "bg-green-100 text-green-700",
};

export default function GoodsReceiptDetailPage() {
  const params = useParams();
  const router = useRouter();
  const grId = params.id as string;

  const [gr, setGr] = useState<GoodsReceipt | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function fetchGR() {
    try {
      const companyId = localStorage.getItem("company_id") ?? "";
      const res = await fetch(
        `/api/v1/companies/${companyId}/purchase/goods-receipts/${grId}`
      );
      if (!res.ok) throw new Error("Failed to fetch goods receipt");
      const json = await res.json();
      setGr(json.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchGR();
  }, [grId]);

  async function handleConfirm() {
    if (!confirm("Confirm this Goods Receipt? This action cannot be undone.")) return;
    setConfirming(true);
    setError(null);
    try {
      const companyId = localStorage.getItem("company_id") ?? "";
      const res = await fetch(
        `/api/v1/companies/${companyId}/purchase/goods-receipts/${grId}/confirm`,
        { method: "POST" }
      );
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Failed to confirm receipt");
      }
      await fetchGR();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setConfirming(false);
    }
  }

  if (loading) return <div className="p-6 text-gray-500">Loading...</div>;
  if (!gr) return <div className="p-6 text-red-500">Goods receipt not found.</div>;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{gr.gr_number}</h1>
          <span
            className={`inline-block mt-1 px-2 py-0.5 rounded-full text-xs font-medium ${
              STATUS_COLORS[gr.status] ?? "bg-gray-100 text-gray-600"
            }`}
          >
            {gr.status}
          </span>
        </div>
        <div className="flex gap-2">
          {gr.status === "DRAFT" && (
            <button
              onClick={handleConfirm}
              disabled={confirming}
              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm font-medium disabled:opacity-50"
            >
              {confirming ? "Confirming..." : "Confirm Receipt"}
            </button>
          )}
          <button
            onClick={() => router.back()}
            className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 text-sm"
          >
            Back
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-md text-sm">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
          <h2 className="font-semibold text-gray-700 text-sm">Receipt Information</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">GR Number</dt>
              <dd className="font-medium">{gr.gr_number}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">PO ID</dt>
              <dd className="font-mono text-xs">{gr.po_id}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Delivery Note</dt>
              <dd>{gr.delivery_note_number ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Received At</dt>
              <dd>
                {gr.received_at
                  ? new Date(gr.received_at).toLocaleDateString()
                  : "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Warehouse</dt>
              <dd className="font-mono text-xs">{gr.warehouse_id ?? "—"}</dd>
            </div>
          </dl>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
          <h2 className="font-semibold text-gray-700 text-sm">Notes</h2>
          <p className="text-sm text-gray-600">{gr.notes ?? "No notes."}</p>
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <h2 className="font-semibold text-gray-700 mb-3">Receipt Lines</h2>
        {gr.lines.length === 0 ? (
          <p className="text-sm text-gray-400">No lines.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="pb-2 text-left text-xs font-medium text-gray-500">PO Line</th>
                  <th className="pb-2 text-right text-xs font-medium text-gray-500">Qty Received</th>
                  <th className="pb-2 text-right text-xs font-medium text-gray-500">Qty Rejected</th>
                  <th className="pb-2 text-right text-xs font-medium text-gray-500">Unit Cost</th>
                  <th className="pb-2 text-right text-xs font-medium text-gray-500">PO Cost</th>
                  <th className="pb-2 text-right text-xs font-medium text-gray-500">PPV</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {gr.lines.map((ln) => {
                  const ppv = parseFloat(ln.ppv_amount);
                  const ppvColor = ppv > 0 ? "text-red-600" : ppv < 0 ? "text-green-600" : "text-gray-600";
                  return (
                    <tr key={ln.id}>
                      <td className="py-2 font-mono text-xs text-gray-500">{ln.po_line_id.slice(0, 8)}…</td>
                      <td className="py-2 text-right">{ln.quantity_received}</td>
                      <td className="py-2 text-right">{ln.quantity_rejected}</td>
                      <td className="py-2 text-right">{ln.unit_cost}</td>
                      <td className="py-2 text-right">{ln.po_unit_cost}</td>
                      <td className={`py-2 text-right font-medium ${ppvColor}`}>
                        {ppv >= 0 ? "+" : ""}{ln.ppv_amount} ({ln.ppv_percentage}%)
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
