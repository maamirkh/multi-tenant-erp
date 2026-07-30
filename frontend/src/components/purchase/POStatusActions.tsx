"use client";

/**
 * POStatusActions — reusable status badge + lifecycle action buttons for
 * PurchaseOrder documents.
 *
 * Task: T141
 */

import React from "react";

export type POStatus =
  | "DRAFT"
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "PARTIALLY_RECEIVED"
  | "FULLY_RECEIVED"
  | "CLOSED"
  | "CANCELLED"
  | "REJECTED";

const STATUS_COLORS: Record<POStatus, string> = {
  DRAFT: "bg-gray-100 text-gray-700 border-gray-200",
  PENDING_APPROVAL: "bg-yellow-100 text-yellow-700 border-yellow-200",
  APPROVED: "bg-blue-100 text-blue-700 border-blue-200",
  PARTIALLY_RECEIVED: "bg-purple-100 text-purple-700 border-purple-200",
  FULLY_RECEIVED: "bg-green-100 text-green-700 border-green-200",
  CLOSED: "bg-slate-100 text-slate-600 border-slate-200",
  CANCELLED: "bg-red-100 text-red-700 border-red-200",
  REJECTED: "bg-orange-100 text-orange-700 border-orange-200",
};

const STATUS_LABELS: Record<POStatus, string> = {
  DRAFT: "Draft",
  PENDING_APPROVAL: "Pending Approval",
  APPROVED: "Approved",
  PARTIALLY_RECEIVED: "Partially Received",
  FULLY_RECEIVED: "Fully Received",
  CLOSED: "Closed",
  CANCELLED: "Cancelled",
  REJECTED: "Rejected",
};

export interface POStatusActionsProps {
  poId: string;
  status: POStatus;
  loading?: boolean;
  onSubmit?: () => void;
  onApprove?: () => void;
  onReject?: (reason: string) => void;
  onAmend?: (reason: string) => void;
  onCancel?: (reason?: string) => void;
  onClose?: () => void;
  onRevertToDraft?: () => void;
}

export function POStatusBadge({ status }: { status: POStatus }) {
  const colorClass = STATUS_COLORS[status] ?? "bg-gray-100 text-gray-700 border-gray-200";
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${colorClass}`}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

export function POStatusActions({
  status,
  loading = false,
  onSubmit,
  onApprove,
  onReject,
  onAmend,
  onCancel,
  onClose,
  onRevertToDraft,
}: POStatusActionsProps) {
  const base =
    "inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md disabled:opacity-50 disabled:cursor-not-allowed transition-colors";

  return (
    <div className="flex flex-wrap gap-2 items-center">
      <POStatusBadge status={status} />

      {status === "DRAFT" && onSubmit && (
        <button
          className={`${base} bg-indigo-600 text-white hover:bg-indigo-700`}
          disabled={loading}
          onClick={onSubmit}
        >
          Submit for Approval
        </button>
      )}

      {status === "PENDING_APPROVAL" && onApprove && (
        <button
          className={`${base} bg-green-600 text-white hover:bg-green-700`}
          disabled={loading}
          onClick={onApprove}
        >
          Approve
        </button>
      )}

      {status === "PENDING_APPROVAL" && onReject && (
        <button
          className={`${base} bg-red-600 text-white hover:bg-red-700`}
          disabled={loading}
          onClick={() => {
            const reason = prompt("Enter rejection reason (required):");
            if (reason?.trim()) onReject(reason.trim());
          }}
        >
          Reject
        </button>
      )}

      {status === "REJECTED" && onRevertToDraft && (
        <button
          className={`${base} bg-gray-600 text-white hover:bg-gray-700`}
          disabled={loading}
          onClick={onRevertToDraft}
        >
          Revise (Back to Draft)
        </button>
      )}

      {(status === "APPROVED" || status === "PARTIALLY_RECEIVED") && onAmend && (
        <button
          className={`${base} bg-amber-600 text-white hover:bg-amber-700`}
          disabled={loading}
          onClick={() => {
            const reason = prompt("Enter amendment reason (required):");
            if (reason?.trim()) onAmend(reason.trim());
          }}
        >
          Amend
        </button>
      )}

      {["APPROVED", "PARTIALLY_RECEIVED", "FULLY_RECEIVED"].includes(status) &&
        onClose && (
          <button
            className={`${base} bg-slate-600 text-white hover:bg-slate-700`}
            disabled={loading}
            onClick={onClose}
          >
            Close PO
          </button>
        )}

      {["DRAFT", "PENDING_APPROVAL", "APPROVED"].includes(status) && onCancel && (
        <button
          className={`${base} border border-red-300 text-red-600 hover:bg-red-50`}
          disabled={loading}
          onClick={() => {
            const reason = prompt("Cancel reason (optional):");
            onCancel(reason ?? undefined);
          }}
        >
          Cancel
        </button>
      )}
    </div>
  );
}
