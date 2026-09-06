"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

interface POLine {
  id: string;
  line_number: number;
  product_description: string;
  quantity_ordered: string;
  quantity_received: string;
  open_quantity: string;
  unit_cost: string;
  line_total: string;
}

interface POCharge {
  id: string;
  charge_type: string;
  description: string;
  amount: string;
}

interface POAmendment {
  id: string;
  amendment_number: number;
  reason: string;
  status: string;
  created_at: string | null;
}

interface PurchaseOrder {
  id: string;
  po_number: string;
  status: string;
  supplier_id: string | null;
  currency_code: string;
  subtotal: string;
  total_charges: string;
  total: string;
  notes: string | null;
  version: number;
  expected_delivery_date: string | null;
  lines: POLine[];
  charges: POCharge[];
  amendments: POAmendment[];
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  PENDING_APPROVAL: "bg-yellow-100 text-yellow-700",
  APPROVED: "bg-blue-100 text-blue-700",
  PARTIALLY_RECEIVED: "bg-purple-100 text-purple-700",
  FULLY_RECEIVED: "bg-green-100 text-green-700",
  CLOSED: "bg-slate-100 text-slate-600",
  CANCELLED: "bg-red-100 text-red-700",
};

export default function PurchaseOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [po, setPo] = useState<PurchaseOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("company_id") ?? ""
      : "";

  async function fetchPO() {
    try {
      const res = await fetch(
        `/api/v1/companies/${companyId}/purchase/purchase-orders/${id}`
      );
      if (!res.ok) throw new Error("Failed to fetch PO");
      const json = await res.json();
      setPo(json.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchPO();
  }, [id]);

  async function performAction(action: string, body?: object) {
    setActionLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/v1/companies/${companyId}/purchase/purchase-orders/${id}/${action}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: body ? JSON.stringify(body) : undefined,
        }
      );
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? `Action ${action} failed`);
      }
      await fetchPO();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) return <div className="p-6 text-gray-500">Loading...</div>;
  if (!po) return <div className="p-6 text-red-500">Purchase order not found.</div>;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{po.po_number}</h1>
          <div className="mt-1 flex items-center gap-2">
            <span
              className={`inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium ${
                STATUS_COLORS[po.status] ?? "bg-gray-100 text-gray-700"
              }`}
            >
              {po.status.replace(/_/g, " ")}
            </span>
            <span className="text-xs text-gray-400">v{po.version}</span>
          </div>
        </div>
        <POStatusActions
          status={po.status}
          loading={actionLoading}
          onAction={performAction}
        />
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-md text-sm">
          {error}
        </div>
      )}

      {/* Info */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 grid grid-cols-3 gap-4 text-sm">
        <div>
          <p className="text-gray-500">Supplier</p>
          <p className="font-medium">{po.supplier_id ?? "—"}</p>
        </div>
        <div>
          <p className="text-gray-500">Expected Delivery</p>
          <p className="font-medium">{po.expected_delivery_date ?? "—"}</p>
        </div>
        <div>
          <p className="text-gray-500">Currency</p>
          <p className="font-medium">{po.currency_code}</p>
        </div>
      </div>

      {/* Lines */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200">
          <h2 className="font-semibold text-gray-700">Line Items</h2>
        </div>
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs text-gray-500">#</th>
              <th className="px-4 py-2 text-left text-xs text-gray-500">Description</th>
              <th className="px-4 py-2 text-right text-xs text-gray-500">Ordered</th>
              <th className="px-4 py-2 text-right text-xs text-gray-500">Received</th>
              <th className="px-4 py-2 text-right text-xs text-gray-500">Open</th>
              <th className="px-4 py-2 text-right text-xs text-gray-500">Unit Cost</th>
              <th className="px-4 py-2 text-right text-xs text-gray-500">Line Total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {po.lines.map((ln) => (
              <tr key={ln.id}>
                <td className="px-4 py-2 text-sm text-gray-500">{ln.line_number}</td>
                <td className="px-4 py-2 text-sm text-gray-900">{ln.product_description}</td>
                <td className="px-4 py-2 text-sm text-gray-900 text-right">{ln.quantity_ordered}</td>
                <td className="px-4 py-2 text-sm text-gray-900 text-right">{ln.quantity_received}</td>
                <td className="px-4 py-2 text-sm text-gray-900 text-right">{ln.open_quantity}</td>
                <td className="px-4 py-2 text-sm text-gray-900 text-right">{ln.unit_cost}</td>
                <td className="px-4 py-2 text-sm font-medium text-gray-900 text-right">
                  {parseFloat(ln.line_total).toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Summary */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <div className="flex flex-col items-end gap-1 text-sm">
          <div className="flex gap-8">
            <span className="text-gray-500">Subtotal</span>
            <span className="w-24 text-right">{parseFloat(po.subtotal).toFixed(2)}</span>
          </div>
          {parseFloat(po.total_charges) > 0 && (
            <div className="flex gap-8">
              <span className="text-gray-500">Charges</span>
              <span className="w-24 text-right">+ {parseFloat(po.total_charges).toFixed(2)}</span>
            </div>
          )}
          <div className="flex gap-8 font-semibold border-t border-gray-200 pt-1 mt-1">
            <span>{po.currency_code} Total</span>
            <span className="w-24 text-right">{parseFloat(po.total).toFixed(2)}</span>
          </div>
        </div>
      </div>

      {/* Amendments */}
      {po.amendments.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200">
            <h2 className="font-semibold text-gray-700">Amendment History</h2>
          </div>
          <div className="divide-y divide-gray-100">
            {po.amendments.map((am) => (
              <div key={am.id} className="px-4 py-3 text-sm">
                <div className="flex justify-between items-center">
                  <span className="font-medium">Amendment #{am.amendment_number}</span>
                  <span className="text-gray-500 text-xs">{am.status}</span>
                </div>
                <p className="text-gray-600 mt-1">{am.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function POStatusActions({
  status,
  loading,
  onAction,
}: {
  status: string;
  loading: boolean;
  onAction: (action: string, body?: object) => void;
}) {
  const btnClass =
    "px-3 py-1.5 text-sm rounded-md font-medium disabled:opacity-50";

  return (
    <div className="flex gap-2">
      {status === "DRAFT" && (
        <button
          className={`${btnClass} bg-indigo-600 text-white hover:bg-indigo-700`}
          disabled={loading}
          onClick={() => onAction("submit")}
        >
          Submit
        </button>
      )}
      {status === "PENDING_APPROVAL" && (
        <>
          <button
            className={`${btnClass} bg-green-600 text-white hover:bg-green-700`}
            disabled={loading}
            onClick={() => onAction("approve")}
          >
            Approve
          </button>
          <button
            className={`${btnClass} bg-red-600 text-white hover:bg-red-700`}
            disabled={loading}
            onClick={() => {
              const reason = prompt("Rejection reason:");
              if (reason) onAction("reject", { reason });
            }}
          >
            Reject
          </button>
        </>
      )}
      {status === "REJECTED" && (
        <button
          className={`${btnClass} bg-gray-600 text-white hover:bg-gray-700`}
          disabled={loading}
          onClick={() => onAction("revert-to-draft")}
        >
          Revise
        </button>
      )}
      {(status === "APPROVED" || status === "PARTIALLY_RECEIVED") && (
        <>
          <button
            className={`${btnClass} bg-yellow-600 text-white hover:bg-yellow-700`}
            disabled={loading}
            onClick={() => {
              const reason = prompt("Amendment reason:");
              if (reason) onAction("amend", { reason, changes: {} });
            }}
          >
            Amend
          </button>
          <button
            className={`${btnClass} bg-slate-600 text-white hover:bg-slate-700`}
            disabled={loading}
            onClick={() => onAction("close")}
          >
            Close
          </button>
        </>
      )}
      {status === "FULLY_RECEIVED" && (
        <button
          className={`${btnClass} bg-slate-600 text-white hover:bg-slate-700`}
          disabled={loading}
          onClick={() => onAction("close")}
        >
          Close
        </button>
      )}
      {["DRAFT", "PENDING_APPROVAL", "APPROVED"].includes(status) && (
        <button
          className={`${btnClass} border border-red-300 text-red-600 hover:bg-red-50`}
          disabled={loading}
          onClick={() => onAction("cancel", {})}
        >
          Cancel
        </button>
      )}
    </div>
  );
}
