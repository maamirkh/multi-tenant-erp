"use client";

/**
 * New Inventory Adjustment — create form.
 * Phase 6 — Stock Operations: Adjustments
 */

import { useState } from "react";
import { useRouter, useParams } from "next/navigation";

export default function NewAdjustmentPage() {
  const params = useParams<{ company_id: string }>();
  const companyId = params?.company_id;
  const router = useRouter();

  const [productId, setProductId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [movementType, setMovementType] = useState<
    "ADJUSTMENT_IN" | "ADJUSTMENT_OUT"
  >("ADJUSTMENT_IN");
  const [quantity, setQuantity] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!companyId) return;
    setSubmitting(true);
    setError(null);

    try {
      const resp = await fetch(
        `/api/v1/companies/${companyId}/inventory/adjustments`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            product_id: productId,
            warehouse_id: warehouseId,
            movement_type: movementType,
            quantity,
            notes: notes || undefined,
          }),
        }
      );

      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.message ?? `Error ${resp.status}`);
      }

      const body = await resp.json();
      const adjId = body.data?.id;
      router.push(`/inventory/adjustments/${adjId}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="p-6 max-w-xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">
          New Inventory Adjustment
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Creates a DRAFT adjustment. Submit to apply to stock.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Product ID
          </label>
          <input
            type="text"
            required
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
            placeholder="UUID of the product"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Warehouse ID
          </label>
          <input
            type="text"
            required
            value={warehouseId}
            onChange={(e) => setWarehouseId(e.target.value)}
            placeholder="UUID of the warehouse"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Adjustment Type
          </label>
          <select
            value={movementType}
            onChange={(e) =>
              setMovementType(
                e.target.value as "ADJUSTMENT_IN" | "ADJUSTMENT_OUT"
              )
            }
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="ADJUSTMENT_IN">Adjustment IN (increase stock)</option>
            <option value="ADJUSTMENT_OUT">
              Adjustment OUT (decrease stock)
            </option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Quantity
          </label>
          <input
            type="number"
            required
            min="0.0001"
            step="any"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            placeholder="e.g. 25"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Notes
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            placeholder="Reason / justification for this adjustment"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 rounded p-2">{error}</p>
        )}

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? "Creating…" : "Create Adjustment"}
          </button>
          <button
            type="button"
            onClick={() => router.push("/inventory/adjustments")}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
