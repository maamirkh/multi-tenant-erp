"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface GRLineInput {
  po_line_id: string;
  quantity_received: string;
  quantity_rejected: string;
  unit_cost: string;
  notes: string;
}

export default function NewGoodsReceiptPage() {
  const router = useRouter();
  const [poId, setPoId] = useState("");
  const [deliveryNoteNumber, setDeliveryNoteNumber] = useState("");
  const [notes, setNotes] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [lines, setLines] = useState<GRLineInput[]>([
    { po_line_id: "", quantity_received: "0", quantity_rejected: "0", unit_cost: "0", notes: "" },
  ]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addLine() {
    setLines([
      ...lines,
      { po_line_id: "", quantity_received: "0", quantity_rejected: "0", unit_cost: "0", notes: "" },
    ]);
  }

  function removeLine(index: number) {
    setLines(lines.filter((_, i) => i !== index));
  }

  function updateLine(index: number, field: keyof GRLineInput, value: string) {
    setLines(lines.map((ln, i) => (i === index ? { ...ln, [field]: value } : ln)));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const companyId = localStorage.getItem("company_id") ?? "";
      const payload = {
        po_id: poId,
        delivery_note_number: deliveryNoteNumber || null,
        notes: notes || null,
        warehouse_id: warehouseId || null,
        lines: lines.map((ln) => ({
          po_line_id: ln.po_line_id,
          quantity_received: parseFloat(ln.quantity_received),
          quantity_rejected: parseFloat(ln.quantity_rejected),
          unit_cost: parseFloat(ln.unit_cost),
          notes: ln.notes || null,
        })),
      };

      const res = await fetch(
        `/api/v1/companies/${companyId}/purchase/goods-receipts`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Failed to create goods receipt");
      }

      const json = await res.json();
      router.push(`/goods-receipts/${json.data.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">New Goods Receipt</h1>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-md text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-4">
          <h2 className="font-semibold text-gray-700">Receipt Details</h2>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Purchase Order ID <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={poId}
              onChange={(e) => setPoId(e.target.value)}
              required
              placeholder="UUID of the Purchase Order"
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Delivery Note Number
              </label>
              <input
                type="text"
                value={deliveryNoteNumber}
                onChange={(e) => setDeliveryNoteNumber(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Warehouse ID
              </label>
              <input
                type="text"
                value={warehouseId}
                onChange={(e) => setWarehouseId(e.target.value)}
                placeholder="Optional — for stock movements"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            />
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-gray-700">Receipt Lines</h2>
            <button
              type="button"
              onClick={addLine}
              className="text-sm text-indigo-600 hover:underline"
            >
              + Add Line
            </button>
          </div>

          {lines.map((ln, i) => (
            <div key={i} className="border border-gray-100 rounded-md p-3 space-y-3 bg-gray-50">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-gray-500">Line {i + 1}</span>
                {lines.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeLine(i)}
                    className="text-xs text-red-500 hover:underline"
                  >
                    Remove
                  </button>
                )}
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  PO Line ID <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={ln.po_line_id}
                  onChange={(e) => updateLine(i, "po_line_id", e.target.value)}
                  required
                  placeholder="UUID"
                  className="w-full border border-gray-300 rounded-md px-2 py-1 text-sm"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Qty Received</label>
                  <input
                    type="number"
                    min="0"
                    step="0.001"
                    value={ln.quantity_received}
                    onChange={(e) => updateLine(i, "quantity_received", e.target.value)}
                    className="w-full border border-gray-300 rounded-md px-2 py-1 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Qty Rejected</label>
                  <input
                    type="number"
                    min="0"
                    step="0.001"
                    value={ln.quantity_rejected}
                    onChange={(e) => updateLine(i, "quantity_rejected", e.target.value)}
                    className="w-full border border-gray-300 rounded-md px-2 py-1 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Unit Cost</label>
                  <input
                    type="number"
                    min="0"
                    step="0.0001"
                    value={ln.unit_cost}
                    onChange={(e) => updateLine(i, "unit_cost", e.target.value)}
                    className="w-full border border-gray-300 rounded-md px-2 py-1 text-sm"
                  />
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={submitting}
            className="px-6 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 text-sm font-medium disabled:opacity-50"
          >
            {submitting ? "Creating..." : "Create Receipt"}
          </button>
          <button
            type="button"
            onClick={() => router.back()}
            className="px-6 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 text-sm"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
