"use client";

import { useState } from "react";
import { dispatchDeliveryNote } from "@/lib/api/sales";

interface DispatchConfirmationProps {
  companyId: string;
  deliveryNoteId: string;
  deliveryNumber: string;
  token?: string;
  onSuccess: () => void;
  onCancel: () => void;
}

export function DispatchConfirmation({
  companyId,
  deliveryNoteId,
  deliveryNumber,
  token,
  onSuccess,
  onCancel,
}: DispatchConfirmationProps) {
  const today = new Date().toISOString().split("T")[0];
  const [dispatchDate, setDispatchDate] = useState(today);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDispatch() {
    if (!dispatchDate) {
      setError("Dispatch date is required.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await dispatchDeliveryNote(companyId, deliveryNoteId, { dispatch_date: dispatchDate }, token);
      onSuccess();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to dispatch delivery note.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6 space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">
          Dispatch Delivery Note
        </h2>
        <p className="text-sm text-gray-600">
          Confirm dispatch of{" "}
          <span className="font-medium">{deliveryNumber}</span>. This will
          deduct stock and update the sales order status.
        </p>

        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">
            Dispatch Date
          </label>
          <input
            type="date"
            value={dispatchDate}
            onChange={(e) => setDispatchDate(e.target.value)}
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {error && (
          <p className="text-sm text-red-600">{error}</p>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleDispatch}
            disabled={loading}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Dispatching…" : "Confirm Dispatch"}
          </button>
        </div>
      </div>
    </div>
  );
}
