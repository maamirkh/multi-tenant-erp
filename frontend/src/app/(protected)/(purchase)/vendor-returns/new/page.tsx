"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";

interface ReturnLineInput {
  gr_line_id: string;
  quantity_returned: string;
  notes: string;
}

export default function NewVendorReturnPage() {
  const params = useParams();
  const router = useRouter();
  const companyId = params?.companyId as string;

  const [grId, setGrId] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<ReturnLineInput[]>([
    { gr_line_id: "", quantity_returned: "", notes: "" },
  ]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const addLine = () =>
    setLines([...lines, { gr_line_id: "", quantity_returned: "", notes: "" }]);

  const removeLine = (idx: number) =>
    setLines(lines.filter((_, i) => i !== idx));

  const updateLine = (idx: number, field: keyof ReturnLineInput, value: string) => {
    setLines(lines.map((ln, i) => (i === idx ? { ...ln, [field]: value } : ln)));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");

    const payload = {
      gr_id: grId,
      notes: notes || null,
      lines: lines
        .filter((ln) => ln.gr_line_id)
        .map((ln) => ({
          gr_line_id: ln.gr_line_id,
          quantity_returned: ln.quantity_returned,
          notes: ln.notes || null,
        })),
    };

    try {
      const res = await fetch(
        `/api/v1/companies/${companyId}/purchase/vendor-returns`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify(payload),
        }
      );
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Failed to create vendor return");
      }
      const json = await res.json();
      router.push(`/vendor-returns/${json.data.id}`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="p-6 max-w-3xl">
      <h1 className="text-2xl font-bold mb-6">New Vendor Return (RMA)</h1>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* GR Reference */}
        <div>
          <label className="block text-sm font-medium mb-1">
            Goods Receipt ID <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={grId}
            onChange={(e) => setGrId(e.target.value)}
            required
            placeholder="UUID of the confirmed GR"
            className="w-full border rounded px-3 py-2 text-sm font-mono"
          />
          <p className="text-xs text-gray-500 mt-1">
            Must be a CONFIRMED Goods Receipt.
          </p>
        </div>

        {/* Notes */}
        <div>
          <label className="block text-sm font-medium mb-1">Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            className="w-full border rounded px-3 py-2 text-sm"
          />
        </div>

        {/* Return Lines */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-semibold">Return Lines</h2>
            <button
              type="button"
              onClick={addLine}
              className="text-xs text-blue-600 hover:underline"
            >
              + Add Line
            </button>
          </div>

          <div className="space-y-3">
            {lines.map((ln, idx) => (
              <div key={idx} className="border rounded p-3 bg-gray-50">
                <div className="grid grid-cols-3 gap-2">
                  <div className="col-span-3 sm:col-span-1">
                    <label className="block text-xs font-medium mb-1">
                      GR Line ID <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={ln.gr_line_id}
                      onChange={(e) => updateLine(idx, "gr_line_id", e.target.value)}
                      placeholder="GR Line UUID"
                      className="w-full border rounded px-2 py-1.5 text-xs font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium mb-1">Qty Returned</label>
                    <input
                      type="number"
                      step="0.001"
                      min="0"
                      value={ln.quantity_returned}
                      onChange={(e) => updateLine(idx, "quantity_returned", e.target.value)}
                      className="w-full border rounded px-2 py-1.5 text-xs"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium mb-1">Notes</label>
                    <input
                      type="text"
                      value={ln.notes}
                      onChange={(e) => updateLine(idx, "notes", e.target.value)}
                      className="w-full border rounded px-2 py-1.5 text-xs"
                    />
                  </div>
                </div>
                {lines.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeLine(idx)}
                    className="text-xs text-red-500 hover:underline mt-2"
                  >
                    Remove line
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm disabled:opacity-50"
          >
            {submitting ? "Creating..." : "Create RMA"}
          </button>
          <button
            type="button"
            onClick={() => router.back()}
            className="px-4 py-2 border rounded text-sm hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
