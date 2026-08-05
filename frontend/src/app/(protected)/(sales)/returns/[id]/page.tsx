"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import {
  getSalesReturn,
  submitSalesReturn,
  approveSalesReturn,
  rejectSalesReturn,
  cancelSalesReturn,
  type SalesReturnRead,
  type ReturnLineRead,
} from "@/lib/api/sales";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-800",
  PENDING_APPROVAL: "bg-yellow-100 text-yellow-800",
  APPROVED: "bg-blue-100 text-blue-800",
  REJECTED: "bg-red-100 text-red-700",
  RECEIVED: "bg-purple-100 text-purple-800",
  COMPLETED: "bg-green-100 text-green-800",
  CANCELLED: "bg-red-50 text-red-500",
};

export default function ReturnDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [salesReturn, setSalesReturn] = useState<SalesReturnRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const companyId =
    typeof window !== "undefined"
      ? (localStorage.getItem("company_id") ?? "")
      : "";
  const token =
    typeof window !== "undefined"
      ? (localStorage.getItem("access_token") ?? undefined)
      : undefined;

  const load = useCallback(async () => {
    if (!companyId || !id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getSalesReturn(companyId, id, token);
      setSalesReturn(res.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load return");
    } finally {
      setLoading(false);
    }
  }, [companyId, id, token]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-64">
        <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (error || !salesReturn) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
          {error ?? "Return not found"}
        </div>
      </div>
    );
  }

  const ret = salesReturn;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{ret.return_number}</h1>
          <p className="text-sm text-gray-500 mt-1">
            Created {ret.created_at ? new Date(ret.created_at).toLocaleDateString() : "—"}
          </p>
        </div>
        <span
          className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
            STATUS_COLORS[ret.status] ?? "bg-gray-100 text-gray-600"
          }`}
        >
          {ret.status.replace(/_/g, " ")}
        </span>
      </div>

      {/* Actions */}
      <ReturnActions
        companyId={companyId}
        returnId={ret.id}
        returnNumber={ret.return_number}
        status={ret.status}
        token={token}
        onSuccess={load}
      />

      {/* Detail cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <DetailCard label="Customer" value={ret.customer_id} mono />
        <DetailCard label="Return Date" value={ret.return_date} />
        <DetailCard label="Resolution" value={ret.resolution_type.replace(/_/g, " ")} />
        <DetailCard label="Version" value={String(ret.version)} />
        {ret.order_id && <DetailCard label="Sales Order" value={ret.order_id} mono />}
        {ret.invoice_id && <DetailCard label="Invoice" value={ret.invoice_id} mono />}
        {ret.received_by && <DetailCard label="Received By" value={ret.received_by} mono />}
        {ret.received_at && <DetailCard label="Received At" value={ret.received_at} />}
        {ret.credit_note_amount && (
          <DetailCard label="Credit Note Amount" value={ret.credit_note_amount} />
        )}
      </div>

      {/* Reason / Notes */}
      {ret.reason_description && (
        <section>
          <h2 className="text-base font-semibold text-gray-900 mb-2">Return Reason</h2>
          <p className="text-sm text-gray-700 bg-gray-50 rounded-lg p-4">
            {ret.reason_description}
          </p>
        </section>
      )}

      {/* Lines */}
      <section>
        <h2 className="text-base font-semibold text-gray-900 mb-3">Return Lines</h2>
        {ret.lines.length === 0 ? (
          <p className="text-sm text-gray-500">No lines.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  {[
                    "Description",
                    "Condition",
                    "Qty Returned",
                    "Qty Accepted",
                    "Qty Rejected",
                    "Unit Price",
                    "Extended",
                  ].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-100">
                {ret.lines.map((ln: ReturnLineRead) => (
                  <tr key={ln.id}>
                    <td className="px-4 py-3">{ln.description}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">
                        {ln.condition}
                      </span>
                    </td>
                    <td className="px-4 py-3">{ln.quantity_returned}</td>
                    <td className="px-4 py-3 text-green-700">{ln.quantity_accepted}</td>
                    <td className="px-4 py-3 text-red-600">{ln.quantity_rejected}</td>
                    <td className="px-4 py-3">
                      {Number(ln.unit_price).toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 4,
                      })}
                    </td>
                    <td className="px-4 py-3 font-medium">
                      {Number(ln.extended_amount).toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Internal notes */}
      {ret.internal_notes && (
        <section>
          <h2 className="text-base font-semibold text-gray-900 mb-2">Internal Notes</h2>
          <p className="text-sm text-gray-700 whitespace-pre-wrap bg-gray-50 rounded-lg p-4">
            {ret.internal_notes}
          </p>
        </section>
      )}
    </div>
  );
}

function DetailCard({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-sm font-semibold text-gray-900 truncate ${mono ? "font-mono" : ""}`}>
        {value}
      </p>
    </div>
  );
}

function ReturnActions({
  companyId,
  returnId,
  returnNumber,
  status,
  token,
  onSuccess,
}: {
  companyId: string;
  returnId: string;
  returnNumber: string;
  status: string;
  token?: string | undefined;
  onSuccess: () => void;
}) {
  const [dialog, setDialog] = useState<
    "submit" | "approve" | "reject" | "cancel" | null
  >(null);
  const [rejectionReason, setRejectionReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handle(
    action: () => Promise<unknown>
  ) {
    setLoading(true);
    setError(null);
    try {
      await action();
      setDialog(null);
      onSuccess();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex gap-3 flex-wrap">
      {status === "DRAFT" && (
        <>
          <button
            onClick={() => setDialog("submit")}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700"
          >
            Submit for Approval
          </button>
          <button
            onClick={() => setDialog("cancel")}
            className="px-4 py-2 bg-white text-red-600 border border-red-300 text-sm font-medium rounded-md hover:bg-red-50"
          >
            Cancel
          </button>
        </>
      )}
      {status === "PENDING_APPROVAL" && (
        <>
          <button
            onClick={() => setDialog("approve")}
            className="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-md hover:bg-green-700"
          >
            Approve
          </button>
          <button
            onClick={() => setDialog("reject")}
            className="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-md hover:bg-red-700"
          >
            Reject
          </button>
          <button
            onClick={() => setDialog("cancel")}
            className="px-4 py-2 bg-white text-gray-600 border border-gray-300 text-sm font-medium rounded-md hover:bg-gray-50"
          >
            Cancel
          </button>
        </>
      )}

      {/* Submit confirmation */}
      {dialog === "submit" && (
        <Modal
          title="Submit for Approval"
          message={`Submit ${returnNumber} for approval?`}
          confirmLabel="Confirm Submit"
          confirmClass="bg-blue-600 hover:bg-blue-700"
          loading={loading}
          error={error}
          onClose={() => { setDialog(null); setError(null); }}
          onConfirm={() =>
            handle(() => submitSalesReturn(companyId, returnId, token))
          }
        />
      )}

      {/* Approve confirmation */}
      {dialog === "approve" && (
        <Modal
          title="Approve Return"
          message={`Approve ${returnNumber}?`}
          confirmLabel="Approve"
          confirmClass="bg-green-600 hover:bg-green-700"
          loading={loading}
          error={error}
          onClose={() => { setDialog(null); setError(null); }}
          onConfirm={() =>
            handle(() => approveSalesReturn(companyId, returnId, token))
          }
        />
      )}

      {/* Reject dialog */}
      {dialog === "reject" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Reject Return</h2>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Rejection Reason
              </label>
              <textarea
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                rows={3}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                placeholder="Reason for rejection..."
              />
            </div>
            {error && <div className="text-red-600 text-sm mb-3">{error}</div>}
            <div className="flex justify-end gap-3">
              <button
                onClick={() => { setDialog(null); setError(null); }}
                className="px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
                disabled={loading}
              >
                Back
              </button>
              <button
                onClick={() =>
                  handle(() =>
                    rejectSalesReturn(companyId, returnId, rejectionReason, token)
                  )
                }
                className="px-4 py-2 bg-red-600 text-white text-sm rounded-md hover:bg-red-700 disabled:opacity-50"
                disabled={loading || !rejectionReason.trim()}
              >
                {loading ? "Rejecting…" : "Confirm Reject"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Cancel confirmation */}
      {dialog === "cancel" && (
        <Modal
          title="Cancel Return"
          message={`Cancel ${returnNumber}? This cannot be undone.`}
          confirmLabel="Confirm Cancel"
          confirmClass="bg-red-600 hover:bg-red-700"
          loading={loading}
          error={error}
          onClose={() => { setDialog(null); setError(null); }}
          onConfirm={() =>
            handle(() => cancelSalesReturn(companyId, returnId, token))
          }
        />
      )}
    </div>
  );
}

function Modal({
  title,
  message,
  confirmLabel,
  confirmClass,
  loading,
  error,
  onClose,
  onConfirm,
}: {
  title: string;
  message: string;
  confirmLabel: string;
  confirmClass: string;
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md">
        <h2 className="text-lg font-semibold text-gray-900 mb-2">{title}</h2>
        <p className="text-sm text-gray-600 mb-4">{message}</p>
        {error && <div className="text-red-600 text-sm mb-3">{error}</div>}
        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
            disabled={loading}
          >
            Back
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 text-white text-sm rounded-md disabled:opacity-50 ${confirmClass}`}
            disabled={loading}
          >
            {loading ? "Processing…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
