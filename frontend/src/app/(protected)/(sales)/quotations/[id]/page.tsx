"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getQuotation,
  sendQuotation,
  acceptQuotation,
  rejectQuotation,
  cancelQuotation,
  convertQuotation,
  addQuotationLine,
  deleteQuotationLine,
  type SalesQuotationRead,
  type QuotationLineRead,
} from "@/lib/api/sales";
import QuotationRevisions from "@/components/sales/QuotationRevisions";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-800",
  SENT_TO_CUSTOMER: "bg-blue-100 text-blue-800",
  ACCEPTED: "bg-green-100 text-green-800",
  REJECTED: "bg-red-100 text-red-800",
  CONVERTED: "bg-purple-100 text-purple-800",
  EXPIRED: "bg-orange-100 text-orange-800",
  CANCELLED: "bg-red-50 text-red-600",
};

export default function QuotationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const quotationId = params.id as string;

  const [quotation, setQuotation] = useState<SalesQuotationRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showRevisions, setShowRevisions] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [cancelReason, setCancelReason] = useState("");
  const [showAddLine, setShowAddLine] = useState(false);
  const [lineForm, setLineForm] = useState({
    description: "",
    quantity: "1",
    unit_price: "0",
    unit_of_measure: "EA",
    discount_percentage: "",
    notes: "",
  });

  const companyId =
    typeof window !== "undefined"
      ? (localStorage.getItem("company_id") ?? "")
      : "";
  const token =
    typeof window !== "undefined"
      ? (localStorage.getItem("access_token") ?? undefined)
      : undefined;

  const load = useCallback(async () => {
    if (!companyId || !quotationId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getQuotation(companyId, quotationId, token);
      setQuotation(res.data as SalesQuotationRead);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load quotation");
    } finally {
      setLoading(false);
    }
  }, [companyId, quotationId, token]);

  useEffect(() => {
    load();
  }, [load]);

  const handleAction = async (action: () => Promise<unknown>) => {
    setSubmitting(true);
    setActionError(null);
    try {
      await action();
      await load();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSend = () =>
    handleAction(() =>
      sendQuotation(companyId, quotationId, { notes: "" }, token),
    );

  const handleAccept = () =>
    handleAction(() =>
      acceptQuotation(companyId, quotationId, { notes: "" }, token),
    );

  const handleReject = () => {
    if (!rejectReason.trim()) return;
    handleAction(async () => {
      await rejectQuotation(
        companyId,
        quotationId,
        { reason: rejectReason },
        token,
      );
      setShowRejectModal(false);
      setRejectReason("");
    });
  };

  const handleCancel = () => {
    if (!cancelReason.trim()) return;
    handleAction(async () => {
      await cancelQuotation(
        companyId,
        quotationId,
        { reason: cancelReason },
        token,
      );
      setShowCancelModal(false);
      setCancelReason("");
    });
  };

  const handleConvert = () =>
    handleAction(async () => {
      const res = await convertQuotation(companyId, quotationId, token);
      const data = res.data as { order_number: string };
      alert(`Converted to Sales Order: ${data.order_number}`);
    });

  const handleAddLine = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setActionError(null);
    try {
      await addQuotationLine(
        companyId,
        quotationId,
        {
          description: lineForm.description,
          quantity: Number(lineForm.quantity),
          unit_price: Number(lineForm.unit_price),
          unit_of_measure: lineForm.unit_of_measure,
          discount_percentage: lineForm.discount_percentage
            ? Number(lineForm.discount_percentage)
            : null,
          notes: lineForm.notes || null,
        },
        token,
      );
      setShowAddLine(false);
      setLineForm({
        description: "",
        quantity: "1",
        unit_price: "0",
        unit_of_measure: "EA",
        discount_percentage: "",
        notes: "",
      });
      await load();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to add line");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteLine = async (lineId: string) => {
    if (!confirm("Delete this line?")) return;
    setSubmitting(true);
    setActionError(null);
    try {
      await deleteQuotationLine(companyId, quotationId, lineId, token);
      await load();
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Failed to delete line",
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6 text-center text-gray-500">Loading quotation...</div>
    );
  }

  if (error || !quotation) {
    return (
      <div className="p-6">
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error ?? "Quotation not found"}
        </div>
        <button
          onClick={() => router.back()}
          className="mt-4 text-blue-600 hover:underline text-sm"
        >
          ← Back to Quotations
        </button>
      </div>
    );
  }

  const isDraft = quotation.status === "DRAFT";
  const isSent = quotation.status === "SENT_TO_CUSTOMER";
  const isAccepted = quotation.status === "ACCEPTED";
  const isTerminal = ["REJECTED", "CONVERTED", "EXPIRED", "CANCELLED"].includes(
    quotation.status,
  );

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <button
            onClick={() => router.back()}
            className="text-sm text-blue-600 hover:underline mb-2 block"
          >
            ← Back to Quotations
          </button>
          <h1 className="text-2xl font-bold text-gray-900 font-mono">
            {quotation.quotation_number}
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Revision {quotation.revision_number} · Created{" "}
            {quotation.quotation_date}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`px-3 py-1 rounded-full text-sm font-medium ${
              STATUS_COLORS[quotation.status] ?? "bg-gray-100 text-gray-600"
            }`}
          >
            {quotation.status.replace(/_/g, " ")}
          </span>
          <button
            onClick={() => setShowRevisions(true)}
            className="px-3 py-1 border border-gray-300 text-sm rounded-lg hover:bg-gray-50"
          >
            History
          </button>
        </div>
      </div>

      {actionError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {actionError}
        </div>
      )}

      {/* Action buttons */}
      {!isTerminal && (
        <div className="flex gap-2 mb-6 flex-wrap">
          {isDraft && (
            <button
              onClick={handleSend}
              disabled={submitting}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm transition-colors"
            >
              Send to Customer
            </button>
          )}
          {isSent && (
            <>
              <button
                onClick={handleAccept}
                disabled={submitting}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm transition-colors"
              >
                Accept
              </button>
              <button
                onClick={() => setShowRejectModal(true)}
                disabled={submitting}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 text-sm transition-colors"
              >
                Reject
              </button>
            </>
          )}
          {isAccepted && (
            <button
              onClick={handleConvert}
              disabled={submitting}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 text-sm transition-colors"
            >
              Convert to Order
            </button>
          )}
          {!isTerminal && (
            <button
              onClick={() => setShowCancelModal(true)}
              disabled={submitting}
              className="px-4 py-2 border border-red-300 text-red-600 rounded-lg hover:bg-red-50 disabled:opacity-50 text-sm transition-colors"
            >
              Cancel
            </button>
          )}
        </div>
      )}

      {/* Quotation details */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h3 className="font-semibold text-gray-700 mb-3 text-sm uppercase tracking-wide">
            Quotation Details
          </h3>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Customer ID</dt>
              <dd className="font-mono text-xs text-gray-700 truncate max-w-[180px]">
                {quotation.customer_id}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Quotation Date</dt>
              <dd className="text-gray-700">{quotation.quotation_date}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Valid Until</dt>
              <dd className="text-gray-700">{quotation.validity_date}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Currency</dt>
              <dd className="text-gray-700">{quotation.currency_code}</dd>
            </div>
          </dl>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h3 className="font-semibold text-gray-700 mb-3 text-sm uppercase tracking-wide">
            Totals
          </h3>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Subtotal</dt>
              <dd className="text-gray-700">
                {Number(quotation.subtotal).toFixed(2)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Discount</dt>
              <dd className="text-gray-700">
                -{Number(quotation.discount_amount).toFixed(2)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Tax</dt>
              <dd className="text-gray-700">
                {Number(quotation.tax_amount).toFixed(2)}
              </dd>
            </div>
            <div className="flex justify-between border-t pt-2 font-semibold">
              <dt className="text-gray-900">Total</dt>
              <dd className="text-gray-900">
                {quotation.currency_code}{" "}
                {Number(quotation.total_amount).toFixed(2)}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Lines */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-6">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <h3 className="font-semibold text-gray-700">Line Items</h3>
          {isDraft && (
            <button
              onClick={() => setShowAddLine(true)}
              className="px-3 py-1 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
            >
              + Add Line
            </button>
          )}
        </div>
        {quotation.lines.length === 0 ? (
          <div className="px-4 py-8 text-center text-gray-400 text-sm">
            No lines added yet
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-gray-600">
                  #
                </th>
                <th className="px-4 py-2 text-left font-medium text-gray-600">
                  Description
                </th>
                <th className="px-4 py-2 text-right font-medium text-gray-600">
                  Qty
                </th>
                <th className="px-4 py-2 text-left font-medium text-gray-600">
                  UOM
                </th>
                <th className="px-4 py-2 text-right font-medium text-gray-600">
                  Unit Price
                </th>
                <th className="px-4 py-2 text-right font-medium text-gray-600">
                  Disc %
                </th>
                <th className="px-4 py-2 text-right font-medium text-gray-600">
                  Total
                </th>
                {isDraft && <th className="px-4 py-2" />}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {quotation.lines.map((line: QuotationLineRead) => (
                <tr key={line.id}>
                  <td className="px-4 py-2 text-gray-500">{line.line_number}</td>
                  <td className="px-4 py-2 text-gray-700">{line.description}</td>
                  <td className="px-4 py-2 text-right">{Number(line.quantity)}</td>
                  <td className="px-4 py-2 text-gray-500">{line.unit_of_measure}</td>
                  <td className="px-4 py-2 text-right">
                    {Number(line.unit_price).toFixed(4)}
                  </td>
                  <td className="px-4 py-2 text-right">
                    {line.discount_percentage
                      ? `${Number(line.discount_percentage)}%`
                      : "—"}
                  </td>
                  <td className="px-4 py-2 text-right font-medium">
                    {Number(line.extended_amount).toFixed(2)}
                  </td>
                  {isDraft && (
                    <td className="px-4 py-2">
                      <button
                        onClick={() => handleDeleteLine(line.id)}
                        className="text-red-500 hover:text-red-700 text-xs"
                        disabled={submitting}
                      >
                        Delete
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Notes */}
      {(quotation.internal_notes || quotation.customer_notes) && (
        <div className="grid grid-cols-2 gap-4 mb-6">
          {quotation.internal_notes && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
              <p className="text-xs font-medium text-yellow-700 mb-1">
                Internal Notes
              </p>
              <p className="text-sm text-yellow-800">{quotation.internal_notes}</p>
            </div>
          )}
          {quotation.customer_notes && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <p className="text-xs font-medium text-blue-700 mb-1">
                Customer Notes
              </p>
              <p className="text-sm text-blue-800">{quotation.customer_notes}</p>
            </div>
          )}
        </div>
      )}

      {/* Add Line Modal */}
      {showAddLine && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-2xl">
            <h2 className="text-lg font-semibold mb-4">Add Line Item</h2>
            <form onSubmit={handleAddLine} className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={lineForm.description}
                  onChange={(e) =>
                    setLineForm({ ...lineForm, description: e.target.value })
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Quantity
                  </label>
                  <input
                    type="number"
                    min="0.001"
                    step="0.001"
                    required
                    value={lineForm.quantity}
                    onChange={(e) =>
                      setLineForm({ ...lineForm, quantity: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    UOM
                  </label>
                  <input
                    type="text"
                    value={lineForm.unit_of_measure}
                    onChange={(e) =>
                      setLineForm({
                        ...lineForm,
                        unit_of_measure: e.target.value.toUpperCase(),
                      })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Unit Price
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="0.0001"
                    required
                    value={lineForm.unit_price}
                    onChange={(e) =>
                      setLineForm({ ...lineForm, unit_price: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Discount %
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="0.01"
                    value={lineForm.discount_percentage}
                    onChange={(e) =>
                      setLineForm({
                        ...lineForm,
                        discount_percentage: e.target.value,
                      })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Notes
                </label>
                <input
                  type="text"
                  value={lineForm.notes}
                  onChange={(e) =>
                    setLineForm({ ...lineForm, notes: e.target.value })
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors text-sm"
                >
                  {submitting ? "Adding..." : "Add Line"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowAddLine(false)}
                  className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Reject Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-2xl">
            <h2 className="text-lg font-semibold mb-4">Reject Quotation</h2>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Rejection Reason <span className="text-red-500">*</span>
            </label>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
              placeholder="Enter reason for rejection..."
            />
            <div className="flex gap-3 mt-4">
              <button
                onClick={handleReject}
                disabled={submitting || !rejectReason.trim()}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 text-sm transition-colors"
              >
                Confirm Reject
              </button>
              <button
                onClick={() => setShowRejectModal(false)}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Cancel Modal */}
      {showCancelModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-2xl">
            <h2 className="text-lg font-semibold mb-4">Cancel Quotation</h2>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Cancellation Reason <span className="text-red-500">*</span>
            </label>
            <textarea
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
              placeholder="Enter reason for cancellation..."
            />
            <div className="flex gap-3 mt-4">
              <button
                onClick={handleCancel}
                disabled={submitting || !cancelReason.trim()}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 text-sm transition-colors"
              >
                Confirm Cancel
              </button>
              <button
                onClick={() => setShowCancelModal(false)}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 text-sm"
              >
                Back
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Revision history sidebar */}
      {showRevisions && (
        <QuotationRevisions
          companyId={companyId}
          quotationId={quotationId}
          {...(token ? { token } : {})}
          onClose={() => setShowRevisions(false)}
        />
      )}
    </div>
  );
}
