"use client";

import { useState } from "react";
import { transitionCustomer } from "@/lib/api/sales";

interface Props {
  companyId: string;
  customerId: string;
  currentStatus: string;
  token: string | undefined;
  onSuccess?: (() => void) | (() => Promise<void>);
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  ACTIVE: "bg-green-100 text-green-700",
  ON_HOLD: "bg-yellow-100 text-yellow-700",
  BLOCKED: "bg-red-100 text-red-700",
  INACTIVE: "bg-slate-100 text-slate-600",
};

// Map status → allowed actions → button config
const ACTIONS: Record<
  string,
  Array<{ action: string; label: string; style: string; needsReason?: boolean }>
> = {
  DRAFT: [
    { action: "activate", label: "Activate", style: "bg-green-600 hover:bg-green-700 text-white" },
  ],
  ACTIVE: [
    { action: "hold", label: "Place on Hold", style: "bg-yellow-500 hover:bg-yellow-600 text-white", needsReason: true },
    { action: "block", label: "Block", style: "bg-red-600 hover:bg-red-700 text-white", needsReason: true },
    { action: "deactivate", label: "Deactivate", style: "bg-slate-500 hover:bg-slate-600 text-white" },
  ],
  ON_HOLD: [
    { action: "release_hold", label: "Release Hold", style: "bg-green-600 hover:bg-green-700 text-white" },
    { action: "block", label: "Block", style: "bg-red-600 hover:bg-red-700 text-white", needsReason: true },
  ],
  BLOCKED: [
    { action: "unblock", label: "Unblock", style: "bg-green-600 hover:bg-green-700 text-white" },
  ],
  INACTIVE: [
    { action: "activate", label: "Reactivate", style: "bg-green-600 hover:bg-green-700 text-white" },
  ],
};

export function CustomerStatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-sm font-medium ${
        STATUS_COLORS[status] ?? "bg-gray-100 text-gray-700"
      }`}
    >
      {status.replace("_", " ")}
    </span>
  );
}

export default function CustomerStatusActions({
  companyId,
  customerId,
  currentStatus,
  token,
  onSuccess,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reasonAction, setReasonAction] = useState<string | null>(null);
  const [reason, setReason] = useState("");

  const actions = ACTIONS[currentStatus] ?? [];

  async function doTransition(action: string, r?: string) {
    setLoading(true);
    setError(null);
    try {
      await transitionCustomer(companyId, customerId, action, r, token);
      setReasonAction(null);
      setReason("");
      onSuccess?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Transition failed");
    } finally {
      setLoading(false);
    }
  }

  function handleClick(
    action: string,
    needsReason: boolean | undefined
  ) {
    if (needsReason) {
      setReasonAction(action);
    } else {
      doTransition(action);
    }
  }

  if (actions.length === 0) return null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {actions.map((a) => (
          <button
            key={a.action}
            onClick={() => handleClick(a.action, a.needsReason)}
            disabled={loading}
            className={`px-3 py-1.5 rounded-md text-sm font-medium disabled:opacity-50 ${a.style}`}
          >
            {a.label}
          </button>
        ))}
      </div>

      {reasonAction && (
        <div className="bg-gray-50 border border-gray-200 rounded-md p-3 space-y-2">
          <label className="text-xs font-medium text-gray-700">
            Reason <span className="text-red-500">*</span>
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={2}
            className="w-full border border-gray-300 rounded-md text-sm px-2 py-1.5"
            placeholder="Enter reason…"
          />
          <div className="flex gap-2">
            <button
              onClick={() => doTransition(reasonAction, reason)}
              disabled={loading || !reason.trim()}
              className="px-3 py-1 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 disabled:opacity-50"
            >
              {loading ? "Processing…" : "Confirm"}
            </button>
            <button
              onClick={() => { setReasonAction(null); setReason(""); }}
              className="px-3 py-1 border border-gray-300 text-sm rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}
    </div>
  );
}
