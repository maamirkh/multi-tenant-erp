"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getDeliveryNote,
  cancelDeliveryNote,
  deliverDeliveryNote,
  listDeliveryNoteLines,
  type DeliveryNoteRead,
  type DeliveryNoteLineRead,
} from "@/lib/api/sales";
import { DispatchConfirmation } from "@/components/sales/DispatchConfirmation";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-800",
  DISPATCHED: "bg-blue-100 text-blue-800",
  DELIVERED: "bg-green-100 text-green-800",
  CANCELLED: "bg-red-100 text-red-600",
};

export default function DeliveryNoteDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [dn, setDn] = useState<DeliveryNoteRead | null>(null);
  const [lines, setLines] = useState<DeliveryNoteLineRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [showDispatch, setShowDispatch] = useState(false);

  const companyId =
    typeof window !== "undefined"
      ? (localStorage.getItem("company_id") ?? "")
      : "";
  const token =
    typeof window !== "undefined"
      ? (localStorage.getItem("access_token") ?? undefined)
      : undefined;

  async function loadDn() {
    if (!companyId || !id) return;
    setLoading(true);
    setError(null);
    try {
      const [dnRes, linesRes] = await Promise.all([
        getDeliveryNote(companyId, id, token),
        listDeliveryNoteLines(companyId, id, token),
      ]);
      setDn(dnRes.data);
      setLines(linesRes.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load delivery note.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDn();
  }, [companyId, id]);

  async function handleDeliver() {
    if (!dn) return;
    if (!confirm("Mark this delivery note as delivered?")) return;
    setActionLoading(true);
    setError(null);
    try {
      const res = await deliverDeliveryNote(companyId, dn.id, token);
      setDn(res.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to mark as delivered.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleCancel() {
    if (!dn) return;
    if (!confirm("Cancel this delivery note? This cannot be undone.")) return;
    setActionLoading(true);
    setError(null);
    try {
      const res = await cancelDeliveryNote(companyId, dn.id, token);
      setDn(res.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to cancel delivery note.");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        Loading…
      </div>
    );
  }

  if (!dn) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error ?? "Delivery note not found."}
        </div>
      </div>
    );
  }

  const canDispatch = dn.status === "DRAFT";
  const canDeliver = dn.status === "DISPATCHED";
  const canCancel = dn.status === "DRAFT";

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button
            onClick={() => router.push("/delivery-notes")}
            className="text-sm text-gray-500 hover:text-gray-700 mb-2 flex items-center gap-1"
          >
            ← Back to Delivery Notes
          </button>
          <h1 className="text-2xl font-bold text-gray-900">
            {dn.delivery_number}
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Order: {dn.order_id}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${STATUS_COLORS[dn.status] ?? "bg-gray-100 text-gray-800"}`}
          >
            {dn.status}
          </span>
          {canDispatch && (
            <button
              onClick={() => setShowDispatch(true)}
              disabled={actionLoading}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              Dispatch
            </button>
          )}
          {canDeliver && (
            <button
              onClick={handleDeliver}
              disabled={actionLoading}
              className="px-4 py-2 text-sm bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
            >
              Mark Delivered
            </button>
          )}
          {canCancel && (
            <button
              onClick={handleCancel}
              disabled={actionLoading}
              className="px-4 py-2 text-sm border border-red-300 text-red-600 rounded-md hover:bg-red-50 disabled:opacity-50"
            >
              Cancel
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {/* Details */}
      <div className="bg-white shadow rounded-lg p-6 grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase">Dispatch Date</p>
          <p className="text-sm text-gray-900 mt-1">{dn.dispatch_date ?? "—"}</p>
        </div>
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase">Expected Delivery</p>
          <p className="text-sm text-gray-900 mt-1">{dn.expected_delivery_date ?? "—"}</p>
        </div>
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase">Carrier</p>
          <p className="text-sm text-gray-900 mt-1">{dn.carrier ?? "—"}</p>
        </div>
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase">Tracking Number</p>
          <p className="text-sm text-gray-900 mt-1">{dn.tracking_number ?? "—"}</p>
        </div>
        {dn.internal_notes && (
          <div className="col-span-2">
            <p className="text-xs font-medium text-gray-500 uppercase">Internal Notes</p>
            <p className="text-sm text-gray-900 mt-1">{dn.internal_notes}</p>
          </div>
        )}
      </div>

      {/* Lines */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-sm font-semibold text-gray-700">Line Items</h2>
        </div>
        {lines.length === 0 ? (
          <div className="px-6 py-8 text-center text-gray-500 text-sm">
            No lines on this delivery note.
          </div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Qty Dispatched</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">UOM</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {lines.map((line) => (
                <tr key={line.id}>
                  <td className="px-6 py-4 text-sm text-gray-900">{line.description}</td>
                  <td className="px-6 py-4 text-sm text-gray-900 text-right">{line.quantity_dispatched}</td>
                  <td className="px-6 py-4 text-sm text-gray-500">{line.unit_of_measure}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Dispatch confirmation modal */}
      {showDispatch && (
        <DispatchConfirmation
          companyId={companyId}
          deliveryNoteId={dn.id}
          deliveryNumber={dn.delivery_number}
          {...(token ? { token } : {})}
          onSuccess={() => {
            setShowDispatch(false);
            loadDn();
          }}
          onCancel={() => setShowDispatch(false)}
        />
      )}
    </div>
  );
}
