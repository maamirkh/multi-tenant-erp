"use client";

import { type SalesApprovalRecordRead } from "@/lib/api/sales";

interface OrderStatusTimelineProps {
  status: string;
  approvalRecords?: SalesApprovalRecordRead[];
  approvalVersion?: number;
}

const STATUS_ORDER = [
  "DRAFT",
  "PENDING_APPROVAL",
  "APPROVED",
  "PARTIALLY_DELIVERED",
  "DELIVERED",
  "INVOICED",
  "CLOSED",
];

const STATUS_LABELS: Record<string, string> = {
  DRAFT: "Draft",
  PENDING_APPROVAL: "Pending Approval",
  APPROVED: "Approved",
  PARTIALLY_DELIVERED: "Partially Delivered",
  DELIVERED: "Delivered",
  INVOICED: "Invoiced",
  CLOSED: "Closed",
  REJECTED: "Rejected",
  CANCELLED: "Cancelled",
};

export function OrderStatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    DRAFT: "bg-gray-100 text-gray-700 border-gray-200",
    PENDING_APPROVAL: "bg-yellow-100 text-yellow-800 border-yellow-200",
    APPROVED: "bg-green-100 text-green-800 border-green-200",
    REJECTED: "bg-red-100 text-red-700 border-red-200",
    PARTIALLY_DELIVERED: "bg-blue-100 text-blue-800 border-blue-200",
    DELIVERED: "bg-teal-100 text-teal-800 border-teal-200",
    INVOICED: "bg-purple-100 text-purple-800 border-purple-200",
    CLOSED: "bg-gray-200 text-gray-700 border-gray-300",
    CANCELLED: "bg-red-50 text-red-600 border-red-100",
  };

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${colors[status] ?? "bg-gray-100 text-gray-600 border-gray-200"}`}
    >
      {STATUS_LABELS[status] ?? status.replace(/_/g, " ")}
    </span>
  );
}

export function OrderStatusTimeline({
  status,
  approvalRecords = [],
  approvalVersion = 1,
}: OrderStatusTimelineProps) {
  const isTerminal = ["REJECTED", "CANCELLED"].includes(status);

  const displayStatuses = isTerminal
    ? [...STATUS_ORDER.slice(0, 2), status]
    : STATUS_ORDER;

  const currentIdx = displayStatuses.indexOf(status);

  return (
    <div className="w-full">
      <div className="flex items-center gap-0">
        {displayStatuses.map((s, idx) => {
          const isCompleted = idx < currentIdx;
          const isCurrent = idx === currentIdx;
          const isTerminalStatus = s === "REJECTED" || s === "CANCELLED";

          return (
            <div key={s} className="flex items-center flex-1 last:flex-none">
              <div className="flex flex-col items-center">
                <div
                  className={`w-5 h-5 rounded-full border-2 flex items-center justify-center text-xs
                    ${isCurrent && isTerminalStatus
                      ? "bg-red-500 border-red-500 text-white"
                      : isCurrent
                      ? "bg-blue-600 border-blue-600 text-white"
                      : isCompleted
                      ? "bg-green-500 border-green-500 text-white"
                      : "bg-white border-gray-300 text-gray-400"
                    }`}
                >
                  {isCompleted ? "✓" : idx + 1}
                </div>
                <span
                  className={`text-xs mt-1 text-center w-16 leading-tight
                    ${isCurrent ? "font-semibold text-gray-900" : "text-gray-400"}`}
                >
                  {STATUS_LABELS[s] ?? s}
                </span>
              </div>
              {idx < displayStatuses.length - 1 && (
                <div
                  className={`flex-1 h-0.5 mx-1 mb-4 ${isCompleted ? "bg-green-400" : "bg-gray-200"}`}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Approval records */}
      {approvalRecords.length > 0 && (
        <div className="mt-4 border-t pt-4">
          <h4 className="text-xs font-medium text-gray-500 mb-2">
            Approval History (version {approvalVersion})
          </h4>
          <div className="space-y-1.5">
            {approvalRecords.map((rec) => (
              <div key={rec.id} className="flex items-center justify-between text-xs">
                <span className="text-gray-600">
                  Level {rec.approval_level} · v{rec.approval_version}
                </span>
                <div className="flex items-center gap-2">
                  {rec.decided_at && (
                    <span className="text-gray-400">{rec.decided_at.slice(0, 10)}</span>
                  )}
                  <span
                    className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                      rec.decision === "APPROVED"
                        ? "bg-green-100 text-green-700"
                        : rec.decision === "REJECTED"
                        ? "bg-red-100 text-red-700"
                        : "bg-yellow-100 text-yellow-700"
                    }`}
                  >
                    {rec.decision}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
