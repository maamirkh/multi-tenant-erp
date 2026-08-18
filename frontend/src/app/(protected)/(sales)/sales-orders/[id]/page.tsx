"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getSalesOrder,
  submitSalesOrder,
  approveSalesOrder,
  rejectSalesOrder,
  cancelSalesOrder,
  closeSalesOrder,
  type SalesOrderRead,
} from "@/lib/api/sales";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  PENDING_APPROVAL: "bg-yellow-100 text-yellow-800",
  APPROVED: "bg-green-100 text-green-800",
  REJECTED: "bg-red-100 text-red-700",
  PARTIALLY_DELIVERED: "bg-blue-100 text-blue-800",
  DELIVERED: "bg-teal-100 text-teal-800",
  INVOICED: "bg-purple-100 text-purple-800",
  CLOSED: "bg-gray-200 text-gray-700",
  CANCELLED: "bg-red-50 text-red-600",
};

export default function SalesOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const companyId =
    typeof window !== "undefined"
      ? (localStorage.getItem("erp_active_company_id") ?? "")
      : "";
  const token =
    typeof window !== "undefined"
      ? (localStorage.getItem("access_token") ?? undefined)
      : undefined;

  const [order, setOrder] = useState<SalesOrderRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Modal state
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [rejectReason, setRejectReason] = useState("");

  const load = useCallback(async () => {
    if (!companyId || !id || id === "new") return;
    setLoading(true);
    setError(null);
    try {
      const res = await getSalesOrder(companyId, id, token);
      setOrder(res.data as SalesOrderRead);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sales order.");
    } finally {
      setLoading(false);
    }
  }, [companyId, id, token]);

  useEffect(() => {
    if (id && id !== "new") {
      load();
    } else {
      setLoading(false);
    }
  }, [id, load]);

  async function handleSubmit() {
    if (!order) return;
    setActionLoading(true);
    setError(null);
    try {
      const res = await submitSalesOrder(companyId, order.id, { submitted_by: order.sales_rep_id }, token);
      setOrder(res.data as SalesOrderRead);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to submit order.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleApprove() {
    if (!order) return;
    setActionLoading(true);
    setError(null);
    try {
      const res = await approveSalesOrder(companyId, order.id, { approver_id: order.sales_rep_id }, token);
      setOrder(res.data as SalesOrderRead);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to approve order.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReject() {
    if (!order || !rejectReason.trim()) return;
    setActionLoading(true);
    setError(null);
    try {
      const res = await rejectSalesOrder(companyId, order.id, {
        approver_id: order.sales_rep_id,
        rejection_reason: rejectReason,
      }, token);
      setOrder(res.data as SalesOrderRead);
      setShowRejectModal(false);
      setRejectReason("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to reject order.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleCancel() {
    if (!order || !cancelReason.trim()) return;
    setActionLoading(true);
    setError(null);
    try {
      const res = await cancelSalesOrder(companyId, order.id, {
        cancellation_reason: cancelReason,
        cancelled_by: order.sales_rep_id,
      }, token);
      setOrder(res.data as SalesOrderRead);
      setShowCancelModal(false);
      setCancelReason("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to cancel order.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleClose() {
    if (!order) return;
    setActionLoading(true);
    setError(null);
    try {
      const res = await closeSalesOrder(companyId, order.id, { closed_by: order.sales_rep_id }, token);
      setOrder(res.data as SalesOrderRead);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to close order.");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-gray-500">
        Loading order...
      </div>
    );
  }

  if (error && !order) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <div className="p-4 bg-red-50 text-red-700 rounded-md">{error}</div>
      </div>
    );
  }

  if (!order) {
    return (
      <div className="p-6 max-w-4xl mx-auto text-gray-500">Order not found.</div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.back()}
            className="text-gray-500 hover:text-gray-700 text-sm"
          >
            ← Back
          </button>
          <h1 className="text-xl font-bold text-gray-900 font-mono">
            {order.order_number}
          </h1>
          <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[order.status] ?? ""}`}>
            {order.status.replace(/_/g, " ")}
          </span>
        </div>

        {/* Action buttons */}
        <div className="flex gap-2">
          {order.status === "DRAFT" && (
            <>
              <button
                onClick={handleSubmit}
                disabled={actionLoading}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium disabled:opacity-50"
              >
                Submit for Approval
              </button>
              <button
                onClick={() => setShowCancelModal(true)}
                disabled={actionLoading}
                className="px-4 py-2 bg-red-50 text-red-600 rounded-md hover:bg-red-100 text-sm font-medium disabled:opacity-50"
              >
                Cancel
              </button>
            </>
          )}
          {order.status === "PENDING_APPROVAL" && (
            <>
              <button
                onClick={handleApprove}
                disabled={actionLoading}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm font-medium disabled:opacity-50"
              >
                Approve
              </button>
              <button
                onClick={() => setShowRejectModal(true)}
                disabled={actionLoading}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm font-medium disabled:opacity-50"
              >
                Reject
              </button>
            </>
          )}
          {["APPROVED", "PARTIALLY_DELIVERED"].includes(order.status) && (
            <button
              onClick={() => setShowCancelModal(true)}
              disabled={actionLoading}
              className="px-4 py-2 bg-red-50 text-red-600 rounded-md hover:bg-red-100 text-sm font-medium disabled:opacity-50"
            >
              Cancel
            </button>
          )}
          {order.status === "INVOICED" && (
            <button
              onClick={handleClose}
              disabled={actionLoading}
              className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 text-sm font-medium disabled:opacity-50"
            >
              Close Order
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-md text-sm">{error}</div>
      )}

      {/* Order details */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-500 mb-3">Order Info</h3>
          <dl className="space-y-1 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Order Date</dt>
              <dd className="font-medium">{order.order_date}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Priority</dt>
              <dd className="font-medium">{order.priority}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Currency</dt>
              <dd className="font-medium">{order.currency_code}</dd>
            </div>
            {order.required_delivery_date && (
              <div className="flex justify-between">
                <dt className="text-gray-500">Required Delivery</dt>
                <dd className="font-medium">{order.required_delivery_date}</dd>
              </div>
            )}
            <div className="flex justify-between">
              <dt className="text-gray-500">Approval Version</dt>
              <dd className="font-medium">v{order.approval_version}</dd>
            </div>
          </dl>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-500 mb-3">Financials</h3>
          <dl className="space-y-1 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Subtotal</dt>
              <dd>{Number(order.subtotal).toFixed(2)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Discount</dt>
              <dd>-{Number(order.discount_amount).toFixed(2)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Tax</dt>
              <dd>{Number(order.tax_amount).toFixed(2)}</dd>
            </div>
            <div className="flex justify-between font-bold border-t pt-1 mt-1">
              <dt>Total</dt>
              <dd>{order.currency_code} {Number(order.total_amount).toFixed(2)}</dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Lines */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden mb-6">
        <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
          <h3 className="text-sm font-medium text-gray-700">Order Lines ({order.lines?.length ?? 0})</h3>
        </div>
        {order.lines && order.lines.length > 0 ? (
          <table className="min-w-full divide-y divide-gray-100">
            <thead>
              <tr>
                <th className="px-4 py-2 text-left text-xs text-gray-500">#</th>
                <th className="px-4 py-2 text-left text-xs text-gray-500">Description</th>
                <th className="px-4 py-2 text-right text-xs text-gray-500">Qty Ordered</th>
                <th className="px-4 py-2 text-right text-xs text-gray-500">Qty Delivered</th>
                <th className="px-4 py-2 text-right text-xs text-gray-500">Unit Price</th>
                <th className="px-4 py-2 text-right text-xs text-gray-500">Extended</th>
                <th className="px-4 py-2 text-center text-xs text-gray-500">Delivery</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {order.lines.map((line) => (
                <tr key={line.id}>
                  <td className="px-4 py-2 text-sm text-gray-500">{line.line_number}</td>
                  <td className="px-4 py-2 text-sm text-gray-900">{line.description}</td>
                  <td className="px-4 py-2 text-sm text-right">{Number(line.quantity_ordered).toFixed(3)} {line.unit_of_measure}</td>
                  <td className="px-4 py-2 text-sm text-right">{Number(line.quantity_delivered).toFixed(3)}</td>
                  <td className="px-4 py-2 text-sm text-right">{Number(line.unit_price).toFixed(4)}</td>
                  <td className="px-4 py-2 text-sm text-right font-medium">{Number(line.extended_amount).toFixed(2)}</td>
                  <td className="px-4 py-2 text-xs text-center text-gray-500">{line.delivery_status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="px-4 py-8 text-center text-gray-400 text-sm">No lines added.</p>
        )}
      </div>

      {/* Cancel Modal */}
      {showCancelModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h2 className="text-lg font-semibold mb-4">Cancel Order</h2>
            <p className="text-sm text-gray-600 mb-4">Please provide a reason for cancellation (required).</p>
            <textarea
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm h-24 resize-none"
              placeholder="Cancellation reason..."
            />
            <div className="flex gap-2 mt-4 justify-end">
              <button
                onClick={() => { setShowCancelModal(false); setCancelReason(""); }}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
              >
                Back
              </button>
              <button
                onClick={handleCancel}
                disabled={!cancelReason.trim() || actionLoading}
                className="px-4 py-2 bg-red-600 text-white rounded-md text-sm font-medium disabled:opacity-50"
              >
                Confirm Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reject Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h2 className="text-lg font-semibold mb-4">Reject Order</h2>
            <p className="text-sm text-gray-600 mb-4">Please provide a reason for rejection.</p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm h-24 resize-none"
              placeholder="Rejection reason..."
            />
            <div className="flex gap-2 mt-4 justify-end">
              <button
                onClick={() => { setShowRejectModal(false); setRejectReason(""); }}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
              >
                Back
              </button>
              <button
                onClick={handleReject}
                disabled={!rejectReason.trim() || actionLoading}
                className="px-4 py-2 bg-red-600 text-white rounded-md text-sm font-medium disabled:opacity-50"
              >
                Confirm Reject
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
