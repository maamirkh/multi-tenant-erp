"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  SUBMITTED: "bg-blue-100 text-blue-700",
  APPROVED: "bg-indigo-100 text-indigo-700",
  DISPATCHED: "bg-yellow-100 text-yellow-700",
  COMPLETED: "bg-green-100 text-green-700",
  CANCELLED: "bg-red-100 text-red-700",
};

interface ReturnLine {
  id: string;
  gr_line_id: string;
  product_id: string | null;
  quantity_returned: string;
  reason_id: string | null;
  notes: string | null;
}

interface VendorReturn {
  id: string;
  rma_number: string;
  status: string;
  gr_id: string;
  supplier_id: string;
  initiated_by: string | null;
  notes: string | null;
  replacement_po_id: string | null;
  credit_note_pending: boolean;
  dispatched_at: string | null;
  completed_at: string | null;
  lines: ReturnLine[];
}

export default function VendorReturnDetailPage() {
  const params = useParams();
  const router = useRouter();
  const companyId = params?.companyId as string;
  const rmaId = params?.id as string;

  const [rma, setRma] = useState<VendorReturn | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionLoading, setActionLoading] = useState("");

  const fetchRMA = async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `/api/v1/companies/${companyId}/purchase/vendor-returns/${rmaId}`,
        { credentials: "include" }
      );
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      setRma(json.data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (companyId && rmaId) fetchRMA();
  }, [companyId, rmaId]);

  const doAction = async (action: string) => {
    setActionLoading(action);
    setActionError("");
    try {
      const res = await fetch(
        `/api/v1/companies/${companyId}/purchase/vendor-returns/${rmaId}/${action}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
        }
      );
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? `Failed to ${action}`);
      }
      await fetchRMA();
    } catch (e: any) {
      setActionError(e.message);
    } finally {
      setActionLoading("");
    }
  };

  if (loading) return <div className="p-6 text-gray-500">Loading...</div>;
  if (error) return <div className="p-6 text-red-600">{error}</div>;
  if (!rma) return <div className="p-6 text-gray-500">Not found.</div>;

  const canSubmit = rma.status === "DRAFT";
  const canApprove = rma.status === "SUBMITTED";
  const canDispatch = rma.status === "APPROVED";
  const canComplete = rma.status === "DISPATCHED";
  const canCancel = ["SUBMITTED", "APPROVED"].includes(rma.status);

  return (
    <div className="p-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => router.back()}
          className="text-gray-500 hover:text-gray-700 text-sm"
        >
          ← Back
        </button>
        <h1 className="text-2xl font-bold">{rma.rma_number}</h1>
        <span className={`px-3 py-0.5 rounded-full text-sm font-medium ${STATUS_COLORS[rma.status] ?? ""}`}>
          {rma.status}
        </span>
        {rma.credit_note_pending && (
          <span className="px-2 py-0.5 bg-orange-100 text-orange-700 text-xs rounded-full font-medium">
            Credit Note Pending
          </span>
        )}
      </div>

      {actionError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded text-sm">
          {actionError}
        </div>
      )}

      {/* Info */}
      <div className="grid grid-cols-2 gap-4 mb-6 text-sm">
        <div>
          <span className="text-gray-500">GR Reference:</span>{" "}
          <span className="font-mono text-xs">{rma.gr_id}</span>
        </div>
        <div>
          <span className="text-gray-500">Supplier:</span>{" "}
          <span className="font-mono text-xs">{rma.supplier_id}</span>
        </div>
        {rma.dispatched_at && (
          <div>
            <span className="text-gray-500">Dispatched:</span>{" "}
            {new Date(rma.dispatched_at).toLocaleString()}
          </div>
        )}
        {rma.completed_at && (
          <div>
            <span className="text-gray-500">Completed:</span>{" "}
            {new Date(rma.completed_at).toLocaleString()}
          </div>
        )}
        {rma.replacement_po_id && (
          <div>
            <span className="text-gray-500">Replacement PO:</span>{" "}
            <span className="font-mono text-xs">{rma.replacement_po_id}</span>
          </div>
        )}
        {rma.notes && (
          <div className="col-span-2">
            <span className="text-gray-500">Notes:</span> {rma.notes}
          </div>
        )}
      </div>

      {/* Workflow Actions */}
      <div className="flex flex-wrap gap-2 mb-6">
        {canSubmit && (
          <button
            onClick={() => doAction("submit")}
            disabled={!!actionLoading}
            className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {actionLoading === "submit" ? "Submitting..." : "Submit for Approval"}
          </button>
        )}
        {canApprove && (
          <button
            onClick={() => doAction("approve")}
            disabled={!!actionLoading}
            className="px-4 py-2 bg-indigo-600 text-white rounded text-sm hover:bg-indigo-700 disabled:opacity-50"
          >
            {actionLoading === "approve" ? "Approving..." : "Approve"}
          </button>
        )}
        {canDispatch && (
          <button
            onClick={() => doAction("dispatch")}
            disabled={!!actionLoading}
            className="px-4 py-2 bg-yellow-600 text-white rounded text-sm hover:bg-yellow-700 disabled:opacity-50"
          >
            {actionLoading === "dispatch" ? "Dispatching..." : "Dispatch (Deduct Stock)"}
          </button>
        )}
        {canComplete && (
          <button
            onClick={() => doAction("complete")}
            disabled={!!actionLoading}
            className="px-4 py-2 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50"
          >
            {actionLoading === "complete" ? "Completing..." : "Complete"}
          </button>
        )}
        {canCancel && (
          <button
            onClick={() => doAction("cancel")}
            disabled={!!actionLoading}
            className="px-4 py-2 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50"
          >
            {actionLoading === "cancel" ? "Cancelling..." : "Cancel"}
          </button>
        )}
      </div>

      {/* Return Lines */}
      <h2 className="text-lg font-semibold mb-3">Return Lines</h2>
      {rma.lines.length === 0 ? (
        <p className="text-gray-500 text-sm">No return lines.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full border text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left border-b">GR Line ID</th>
                <th className="px-4 py-2 text-left border-b">Product</th>
                <th className="px-4 py-2 text-right border-b">Qty Returned</th>
                <th className="px-4 py-2 text-left border-b">Notes</th>
              </tr>
            </thead>
            <tbody>
              {rma.lines.map((ln) => (
                <tr key={ln.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 border-b font-mono text-xs">{ln.gr_line_id}</td>
                  <td className="px-4 py-2 border-b font-mono text-xs">
                    {ln.product_id ?? "—"}
                  </td>
                  <td className="px-4 py-2 border-b text-right">{ln.quantity_returned}</td>
                  <td className="px-4 py-2 border-b text-gray-600">{ln.notes ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
