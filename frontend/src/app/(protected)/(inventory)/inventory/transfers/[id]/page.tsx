"use client";

/**
 * Stock Transfer Detail — view + dispatch / receive / cancel actions.
 * Phase 7 — Stock Operations: Transfers & Reservations
 */

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getAccessToken } from "@/lib/auth/tokenStorage";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type TransferStatus = "DRAFT" | "IN_TRANSIT" | "COMPLETED" | "CANCELLED";

interface TransferLine {
  id: string;
  product_id: string;
  variant_id: string | null;
  quantity: string;
  unit_cost: string | null;
  currency_code: string | null;
  source_movement_id: string | null;
  destination_movement_id: string | null;
  reversal_movement_id: string | null;
}

interface Transfer {
  id: string;
  source_warehouse_id: string;
  destination_warehouse_id: string;
  status: TransferStatus;
  version: number;
  reference_no: string | null;
  notes: string | null;
  dispatched_at: string | null;
  received_at: string | null;
  cancelled_at: string | null;
  cancelled_reason: string | null;
  lines: TransferLine[];
  created_at: string;
  updated_at: string;
}

const STATUS_BADGE: Record<TransferStatus, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  IN_TRANSIT: "bg-yellow-100 text-yellow-800",
  COMPLETED: "bg-green-100 text-green-800",
  CANCELLED: "bg-red-100 text-red-700",
};

function Field({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">
        {label}
      </p>
      <p className="mt-0.5 text-sm text-gray-900 font-mono break-all">
        {value ?? "—"}
      </p>
    </div>
  );
}

export default function TransferDetailPage() {
  const params = useParams<{ id: string }>();
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";
  const transferId = params?.id;
  const router = useRouter();

  const [transfer, setTransfer] = useState<Transfer | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cancelReason, setCancelReason] = useState("");

  const fetchTransfer = () => {
    if (!companyId || !transferId) return;
    setLoading(true);
    fetch(
      `${API_BASE}/api/v1/companies/${companyId}/inventory/stock-transfers/${transferId}`,
      { headers: { Authorization: `Bearer ${getAccessToken()}` } }
    )
      .then((r) => r.json())
      .then((body) => {
        setTransfer(body.data);
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load transfer.");
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchTransfer();
  }, [companyId, transferId]);

  async function callAction(
    action: "dispatch" | "receive" | "cancel",
    body: object = {}
  ) {
    if (!companyId || !transferId) return;
    setActionLoading(true);
    setError(null);
    try {
      const resp = await fetch(
        `${API_BASE}/api/v1/companies/${companyId}/inventory/stock-transfers/${transferId}/${action}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${getAccessToken()}`,
          },
          body: JSON.stringify(body),
        }
      );
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.message ?? `Error ${resp.status}`);
      }
      setTransfer(data.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) {
    return <p className="p-6 text-sm text-gray-500">Loading…</p>;
  }
  if (!transfer) {
    return (
      <p className="p-6 text-sm text-red-600">
        {error ?? "Transfer not found."}
      </p>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">
            Transfer Detail
          </h1>
          <p className="text-xs text-gray-400 mt-0.5 font-mono">{transfer.id}</p>
        </div>
        <span
          className={`inline-flex rounded-full px-3 py-1 text-sm font-semibold ${
            STATUS_BADGE[transfer.status]
          }`}
        >
          {transfer.status.replace("_", " ")}
        </span>
      </div>

      {/* Main fields */}
      <div className="grid grid-cols-2 gap-4 rounded-lg border border-gray-200 p-4">
        <Field label="Source Warehouse" value={transfer.source_warehouse_id} />
        <Field
          label="Destination Warehouse"
          value={transfer.destination_warehouse_id}
        />
        <Field label="Reference No" value={transfer.reference_no} />
        <Field label="Version" value={String(transfer.version)} />
        <Field label="Notes" value={transfer.notes} />
        <Field
          label="Created"
          value={new Date(transfer.created_at).toLocaleString()}
        />
        {transfer.dispatched_at && (
          <Field
            label="Dispatched At"
            value={new Date(transfer.dispatched_at).toLocaleString()}
          />
        )}
        {transfer.received_at && (
          <Field
            label="Received At"
            value={new Date(transfer.received_at).toLocaleString()}
          />
        )}
        {transfer.cancelled_at && (
          <Field
            label="Cancelled At"
            value={new Date(transfer.cancelled_at).toLocaleString()}
          />
        )}
        {transfer.cancelled_reason && (
          <div className="col-span-2">
            <Field label="Cancellation Reason" value={transfer.cancelled_reason} />
          </div>
        )}
      </div>

      {/* Lines table */}
      {transfer.lines.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-700 mb-2">
            Transfer Lines ({transfer.lines.length})
          </h2>
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">
                    Product ID
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">
                    Quantity
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">
                    Unit Cost
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">
                    Source Movement
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">
                    Dest Movement
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {transfer.lines.map((line) => (
                  <tr key={line.id}>
                    <td className="px-4 py-2 font-mono text-xs text-gray-700">
                      {line.product_id.slice(0, 8)}…
                    </td>
                    <td className="px-4 py-2 font-mono text-gray-900">
                      {Number(line.quantity).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-gray-600">
                      {line.unit_cost
                        ? `${line.unit_cost} ${line.currency_code ?? ""}`
                        : "—"}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs text-gray-500">
                      {line.source_movement_id
                        ? line.source_movement_id.slice(0, 8) + "…"
                        : "—"}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs text-gray-500">
                      {line.destination_movement_id
                        ? line.destination_movement_id.slice(0, 8) + "…"
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {error && (
        <p className="text-sm text-red-600 bg-red-50 rounded p-2">{error}</p>
      )}

      {/* Actions */}
      <div className="flex flex-wrap gap-3 items-center">
        {transfer.status === "DRAFT" && (
          <button
            disabled={actionLoading}
            onClick={() => callAction("dispatch")}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {actionLoading ? "Dispatching…" : "Dispatch"}
          </button>
        )}

        {transfer.status === "IN_TRANSIT" && (
          <button
            disabled={actionLoading}
            onClick={() => callAction("receive")}
            className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
          >
            {actionLoading ? "Receiving…" : "Mark Received"}
          </button>
        )}

        {(transfer.status === "DRAFT" || transfer.status === "IN_TRANSIT") && (
          <div className="flex gap-2 items-center">
            <input
              type="text"
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              placeholder="Cancellation reason…"
              className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400 w-52"
            />
            <button
              disabled={actionLoading || !cancelReason.trim()}
              onClick={() =>
                callAction("cancel", { cancelled_reason: cancelReason })
              }
              className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              {actionLoading ? "Cancelling…" : "Cancel Transfer"}
            </button>
          </div>
        )}

        <button
          onClick={() => router.push("/inventory/transfers")}
          className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Back to List
        </button>
      </div>
    </div>
  );
}
