"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

interface PRLineForm {
  product_description: string;
  quantity: string;
  estimated_unit_cost: string;
  notes: string;
}

const emptyLine = (): PRLineForm => ({
  product_description: "",
  quantity: "1",
  estimated_unit_cost: "0",
  notes: "",
});

export default function NewPurchaseRequestPage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [department, setDepartment] = useState("");
  const [requiredByDate, setRequiredByDate] = useState("");
  const [notes, setNotes] = useState("");
  const [currencyCode, setCurrencyCode] = useState("USD");
  const [lines, setLines] = useState<PRLineForm[]>([emptyLine()]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const totalCost = lines.reduce((sum, ln) => {
    const qty = parseFloat(ln.quantity) || 0;
    const cost = parseFloat(ln.estimated_unit_cost) || 0;
    return sum + qty * cost;
  }, 0);

  const addLine = () => setLines((prev) => [...prev, emptyLine()]);

  const removeLine = (idx: number) =>
    setLines((prev) => prev.filter((_, i) => i !== idx));

  const updateLine = (idx: number, field: keyof PRLineForm, value: string) =>
    setLines((prev) =>
      prev.map((ln, i) => (i === idx ? { ...ln, [field]: value } : ln))
    );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!title.trim()) {
      setError("Title is required.");
      return;
    }

    setSaving(true);
    try {
      // TODO: Call API with company context
      // const result = await createPurchaseRequest({ title, department, ... });
      router.push("../purchase-requests");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create purchase request.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-semibold text-gray-900 mb-6">New Purchase Request</h1>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Header */}
        <div className="rounded-lg border border-gray-200 bg-white p-6 space-y-4">
          <h2 className="text-sm font-medium text-gray-700 uppercase tracking-wide">Details</h2>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Title <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Describe what you need"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
              <input
                type="text"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Required By</label>
              <input
                type="date"
                value={requiredByDate}
                onChange={(e) => setRequiredByDate(e.target.value)}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Lines */}
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-gray-700 uppercase tracking-wide">Line Items</h2>
            <button
              type="button"
              onClick={addLine}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              + Add Line
            </button>
          </div>

          <div className="space-y-3">
            {lines.map((line, idx) => (
              <div key={idx} className="flex gap-3 items-start">
                <div className="flex-1">
                  <input
                    type="text"
                    value={line.product_description}
                    onChange={(e) => updateLine(idx, "product_description", e.target.value)}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                    placeholder="Description"
                    required
                  />
                </div>
                <div className="w-24">
                  <input
                    type="number"
                    value={line.quantity}
                    onChange={(e) => updateLine(idx, "quantity", e.target.value)}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                    placeholder="Qty"
                    min="0.001"
                    step="0.001"
                  />
                </div>
                <div className="w-32">
                  <input
                    type="number"
                    value={line.estimated_unit_cost}
                    onChange={(e) => updateLine(idx, "estimated_unit_cost", e.target.value)}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                    placeholder="Unit Cost"
                    min="0"
                    step="0.01"
                  />
                </div>
                {lines.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeLine(idx)}
                    className="mt-2 text-red-400 hover:text-red-600 text-sm"
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
          </div>

          <div className="mt-4 text-right text-sm font-medium text-gray-700">
            Total: {currencyCode} {totalCost.toFixed(2)}
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => router.back()}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save as Draft"}
          </button>
        </div>
      </form>
    </div>
  );
}
