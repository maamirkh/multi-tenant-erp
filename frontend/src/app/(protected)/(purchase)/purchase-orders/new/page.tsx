"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface POLineInput {
  product_description: string;
  quantity_ordered: string;
  unit_cost: string;
}

export default function NewPurchaseOrderPage() {
  const router = useRouter();
  const [supplierId, setSupplierId] = useState("");
  const [expectedDate, setExpectedDate] = useState("");
  const [currencyCode, setCurrencyCode] = useState("USD");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<POLineInput[]>([
    { product_description: "", quantity_ordered: "1", unit_cost: "0" },
  ]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addLine() {
    setLines((prev) => [
      ...prev,
      { product_description: "", quantity_ordered: "1", unit_cost: "0" },
    ]);
  }

  function removeLine(idx: number) {
    setLines((prev) => prev.filter((_, i) => i !== idx));
  }

  function updateLine(idx: number, field: keyof POLineInput, value: string) {
    setLines((prev) =>
      prev.map((ln, i) => (i === idx ? { ...ln, [field]: value } : ln))
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const companyId = localStorage.getItem("company_id") ?? "";
      const payload = {
        supplier_id: supplierId || null,
        expected_delivery_date: expectedDate || null,
        currency_code: currencyCode,
        notes: notes || null,
        lines: lines.map((ln) => ({
          product_description: ln.product_description,
          quantity_ordered: parseFloat(ln.quantity_ordered),
          unit_cost: parseFloat(ln.unit_cost),
        })),
      };
      const res = await fetch(
        `/api/v1/companies/${companyId}/purchase/purchase-orders`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Failed to create purchase order");
      }
      const json = await res.json();
      router.push(`/purchase-orders/${json.data.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">
        New Purchase Order
      </h1>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-md text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Header */}
        <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-4">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Order Details
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Supplier ID (UUID)
              </label>
              <input
                type="text"
                value={supplierId}
                onChange={(e) => setSupplierId(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                placeholder="Optional — can set before submission"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Currency
              </label>
              <input
                type="text"
                value={currencyCode}
                onChange={(e) => setCurrencyCode(e.target.value.toUpperCase())}
                maxLength={3}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Expected Delivery Date
              </label>
              <input
                type="date"
                value={expectedDate}
                onChange={(e) => setExpectedDate(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Notes
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            />
          </div>
        </div>

        {/* Lines */}
        <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
              Line Items
            </h2>
            <button
              type="button"
              onClick={addLine}
              className="text-indigo-600 hover:text-indigo-700 text-sm font-medium"
            >
              + Add Line
            </button>
          </div>
          {lines.map((ln, idx) => (
            <div key={idx} className="grid grid-cols-12 gap-2 items-end">
              <div className="col-span-6">
                <label className="block text-xs text-gray-500 mb-1">
                  Description *
                </label>
                <input
                  type="text"
                  required
                  value={ln.product_description}
                  onChange={(e) =>
                    updateLine(idx, "product_description", e.target.value)
                  }
                  className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-xs text-gray-500 mb-1">Qty *</label>
                <input
                  type="number"
                  required
                  min="0.001"
                  step="0.001"
                  value={ln.quantity_ordered}
                  onChange={(e) =>
                    updateLine(idx, "quantity_ordered", e.target.value)
                  }
                  className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm"
                />
              </div>
              <div className="col-span-3">
                <label className="block text-xs text-gray-500 mb-1">
                  Unit Cost
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.0001"
                  value={ln.unit_cost}
                  onChange={(e) => updateLine(idx, "unit_cost", e.target.value)}
                  className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm"
                />
              </div>
              <div className="col-span-1 flex justify-end">
                {lines.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeLine(idx)}
                    className="text-red-400 hover:text-red-600 text-lg leading-none"
                    title="Remove line"
                  >
                    ×
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => router.back()}
            className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-2 text-sm text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50"
          >
            {submitting ? "Creating..." : "Create Purchase Order"}
          </button>
        </div>
      </form>
    </div>
  );
}
