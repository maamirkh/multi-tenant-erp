"use client";

import { useState, useEffect } from "react";
import { getPendingApprovals, type SalesApprovalRecordRead } from "@/lib/api/sales";

interface ApprovalInboxProps {
  companyId: string;
  approverId: string;
  token?: string;
  onApprove?: (recordId: string, orderId: string) => void;
  onReject?: (recordId: string, orderId: string) => void;
}

const DECISION_COLORS: Record<string, string> = {
  PENDING: "bg-yellow-100 text-yellow-800",
  APPROVED: "bg-green-100 text-green-800",
  REJECTED: "bg-red-100 text-red-800",
};

export function ApprovalInbox({
  companyId,
  approverId,
  token,
  onApprove,
  onReject,
}: ApprovalInboxProps) {
  const [records, setRecords] = useState<SalesApprovalRecordRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!companyId || !approverId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getPendingApprovals(companyId, approverId, token);
      setRecords(res.data as SalesApprovalRecordRead[]);
    } catch {
      setError("Failed to load pending approvals.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (approverId && companyId) {
      load();
    }
  }, [approverId, companyId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 text-gray-500 text-sm">
        Loading approvals...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-3 bg-red-50 text-red-700 rounded-md text-sm">{error}</div>
    );
  }

  if (records.length === 0) {
    return (
      <div className="flex flex-col items-center py-8 text-gray-400">
        <p className="text-sm font-medium">No pending approvals</p>
        <p className="text-xs mt-1">You have no items awaiting your approval.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700">Pending Approvals</h3>
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
          {records.length}
        </span>
      </div>

      {records.map((record) => (
        <div
          key={record.id}
          className="bg-white rounded-lg border border-gray-200 p-4"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900">
                {record.document_type.replace(/_/g, " ")}
              </p>
              <p className="text-xs text-gray-500 font-mono mt-0.5">
                {record.document_id}
              </p>
              <p className="text-xs text-gray-400 mt-1">
                Level {record.approval_level} · Version {record.approval_version}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${DECISION_COLORS[record.decision]}`}>
                {record.decision}
              </span>

              {record.decision === "PENDING" && (
                <div className="flex gap-1">
                  {onApprove && (
                    <button
                      onClick={() => onApprove(record.id, record.document_id)}
                      className="px-3 py-1 bg-green-600 text-white rounded text-xs font-medium hover:bg-green-700"
                    >
                      Approve
                    </button>
                  )}
                  {onReject && (
                    <button
                      onClick={() => onReject(record.id, record.document_id)}
                      className="px-3 py-1 bg-red-600 text-white rounded text-xs font-medium hover:bg-red-700"
                    >
                      Reject
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
