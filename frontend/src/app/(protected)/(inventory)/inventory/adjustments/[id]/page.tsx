"use client";

/**
 * Inventory Adjustment Detail — view + approve / reject actions.
 * Phase 6 — Stock Operations: Adjustments
 */

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

type AdjustmentStatus = "DRAFT" | "PENDING_APPROVAL" | "APPROVED" | "REJECTED";

interface Adjustment {
  id: string;
  product_id: string;
  warehouse_id: string;
  movement_type: "ADJUSTMENT_IN" | "ADJUSTMENT_OUT";
  quantity: string;
  status: AdjustmentStatus;
  version: number;
  notes: string | null;
  old_quantity: string | null;
  new_quantity: string | null;
  submitted_by: string | null;
  approved_by: string | null;
  rejected_by: string | null;
  rejection_reason: string | null;
  reference_movement_id: string | null;
  created_at: string;
  updated_at: string;
}

const STATUS_BADGE: Record<AdjustmentStatus, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  PENDING_APPROVAL: "bg-yellow-100 text-yellow-800",
  APPROVED: "bg-green-100 text-green-800",
  REJECTED: "bg-red-100 text-red-700",
};

function Field({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">
        {label}
      </p>
      <p className="mt-0.5 text-sm text-gray-900">{value ?? "—"}</p>
    </div>
  );
}

export default function AdjustmentDetailPage() {
  const params = useParams<{ company_id: string; id: string }>();
  const companyId = params?.company_id;
  const adjId = params?.id;
  const router = useRouter();

  const [adj, setAdj] = useState<Adjustment | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");

  const fetchAdj = () => {
    if (!companyId || !adjId) return;
    setLoading(true);
    fetch(`/api/v1/companies/${companyId}/inventory/adjustments/${adjId}`, {
      credentials: "include",
    })
      .then((r) => r.json())
      .then((body) => {
        setAdj(body.data);
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load adjustment.");
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchAdj();
  }, [companyId, adjId]);

  async function callAction(
    action: "submit" | "approve" | "reject",
    body: object = {}
  ) {
    if (!companyId || !adjId) return;
    setActionLoading(true);
    setError(null);
    try {
      const resp = await fetch(
        `/api/v1/companies/${companyId}/inventory/adjustments/${adjId}/${action}`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      );
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.message ?? `Error ${resp.status}`);
      }
      setAdj(data.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) {
    return <p className="p-6 text-sm text-gray-500">Loading…</p>;
  }
  if (!adj) {
    return (
      <p className="p-6 text-sm text-red-600">{error ?? "Adjustment not found."}</p>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">
            Adjustment Detail
          </h1>
          <p className="text-xs text-gray-400 mt-0.5 font-mono">{adj.id}</p>
        </div>
        <span
          className={`inline-flex rounded-full px-3 py-1 text-sm font-semibold ${
            STATUS_BADGE[adj.status]
          }`}
        >
          {adj.status.replace("_", " ")}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 rounded-lg border border-gray-200 p-4">
        <Field label="Movement Type" value={adj.movement_type} />
        <Field label="Quantity" value={Number(adj.quantity).toLocaleString()} />
        <Field
          label="Old Quantity"
          value={
            adj.old_quantity != null
              ? Number(adj.old_quantity).toLocaleString()
              : null
          }
        />
        <Field
          label="New Quantity"
          value={
            adj.new_quantity != null
              ? Number(adj.new_quantity).toLocaleString()
              : null
          }
        />
        <Field label="Product ID" value={adj.product_id} />
        <Field label="Warehouse ID" value={adj.warehouse_id} />
        <Field label="Notes" value={adj.notes} />
        <Field label="Version" value={String(adj.version)} />
        <Field
          label="Created"
          value={new Date(adj.created_at).toLocaleString()}
        />
        <Field
          label="Updated"
          value={new Date(adj.updated_at).toLocaleString()}
        />
        {adj.submitted_by && (
          <Field label="Submitted By" value={adj.submitted_by} />
        )}
        {adj.approved_by && (
          <Field label="Approved By" value={adj.approved_by} />
        )}
        {adj.rejected_by && (
          <Field label="Rejected By" value={adj.rejected_by} />
        )}
        {adj.rejection_reason && (
          <div className="col-span-2">
            <Field label="Rejection Reason" value={adj.rejection_reason} />
          </div>
        )}
        {adj.reference_movement_id && (
          <div className="col-span-2">
            <Field
              label="Stock Movement ID"
              value={adj.reference_movement_id}
            />
          </div>
        )}
      </div>

      {error && (
        <p className="text-sm text-red-600 bg-red-50 rounded p-2">{error}</p>
      )}

      {/* Actions */}
      <div className="flex flex-wrap gap-3">
        {adj.status === "DRAFT" && (
          <button
            disabled={actionLoading}
            onClick={() => callAction("submit")}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {actionLoading ? "Submitting…" : "Submit for Approval"}
          </button>
        )}

        {adj.status === "PENDING_APPROVAL" && (
          <>
            <button
              disabled={actionLoading}
              onClick={() => callAction("approve")}
              className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
            >
              {actionLoading ? "Approving…" : "Approve"}
            </button>

            <div className="flex gap-2 items-center">
              <input
                type="text"
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                placeholder="Rejection reason…"
                className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400 w-56"
              />
              <button
                disabled={actionLoading || !rejectionReason.trim()}
                onClick={() =>
                  callAction("reject", { rejection_reason: rejectionReason })
                }
                className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                {actionLoading ? "Rejecting…" : "Reject"}
              </button>
            </div>
          </>
        )}

        <button
          onClick={() => router.push("/inventory/adjustments")}
          className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Back to List
        </button>
      </div>
    </div>
  );
}
