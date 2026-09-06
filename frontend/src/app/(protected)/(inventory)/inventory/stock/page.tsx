"use client";


import { useEffect, useState } from "react";
import { getAccessToken } from "@/lib/auth/tokenStorage";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface StockPosition {
  id: string;
  product_id: string;
  variant_id: string | null;
  warehouse_id: string;
  qty_on_hand: string;
  qty_reserved: string;
  qty_damaged: string;
  unit_cost: string | null;
  currency_code: string | null;
  safety_stock: string;
  minimum_stock: string;
  reorder_level: string;
}

interface OpeningStockForm {
  product_id: string;
  warehouse_id: string;
  quantity: string;
  unit_cost: string;
  currency_code: string;
  notes: string;
}

export default function StockOverviewPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";

  const [positions, setPositions] = useState<StockPosition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<OpeningStockForm>({
    product_id: "",
    warehouse_id: "",
    quantity: "",
    unit_cost: "",
    currency_code: "",
    notes: "",
  });

  const baseUrl = `${API_BASE}/api/v1/companies/${companyId}/inventory/stock`;

  const fetchPositions = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${baseUrl}/positions`, {
        headers: { Authorization: `Bearer ${getAccessToken()}` },
      });
      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();
      setPositions(data.data ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (companyId) fetchPositions();
  }, [companyId]);

  const handleOpeningStock = async () => {
    if (!form.product_id.trim() || !form.warehouse_id.trim() || !form.quantity) return;
    setSaving(true);
    try {
      const body: Record<string, unknown> = {
        product_id: form.product_id.trim(),
        warehouse_id: form.warehouse_id.trim(),
        quantity: form.quantity,
      };
      if (form.unit_cost) body.unit_cost = form.unit_cost;
      if (form.currency_code) body.currency_code = form.currency_code.toUpperCase();
      if (form.notes) body.notes = form.notes;

      const resp = await fetch(`${baseUrl}/opening`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${getAccessToken()}`,
        },
        body: JSON.stringify(body),
      });
      if (!resp.ok) throw new Error(await resp.text());
      setShowForm(false);
      setForm({ product_id: "", warehouse_id: "", quantity: "", unit_cost: "", currency_code: "", notes: "" });
      await fetchPositions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record opening stock");
    } finally {
      setSaving(false);
    }
  };

  const handleSnapshot = async () => {
    try {
      const resp = await fetch(`${baseUrl}/snapshots`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${getAccessToken()}`,
        },
        body: JSON.stringify({ snapshot_name: `Snapshot ${new Date().toLocaleString()}` }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      alert("Snapshot created successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Snapshot failed");
    }
  };

  const availableQty = (pos: StockPosition) => {
    const onHand = parseFloat(pos.qty_on_hand);
    const reserved = parseFloat(pos.qty_reserved);
    const damaged = parseFloat(pos.qty_damaged);
    return (onHand - reserved - damaged).toFixed(4);
  };

  const isLowStock = (pos: StockPosition) =>
    parseFloat(pos.qty_on_hand) <= parseFloat(pos.reorder_level) &&
    parseFloat(pos.reorder_level) > 0;

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8">
        <div className="h-48 animate-pulse rounded-lg bg-gray-100" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Stock Overview</h1>
          <p className="text-sm text-gray-500 mt-1">{positions.length} position(s)</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleSnapshot}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
          >
            Take Snapshot
          </button>
          <button
            onClick={() => setShowForm(true)}
            className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
          >
            + Opening Stock
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Opening stock form */}
      {showForm && (
        <div className="rounded-lg border border-blue-100 bg-blue-50 p-4 space-y-3">
          <h2 className="text-sm font-semibold text-gray-700">Record Opening Stock</h2>
          <div className="grid grid-cols-2 gap-3">
            {[
              { key: "product_id", label: "Product ID *", placeholder: "UUID" },
              { key: "warehouse_id", label: "Warehouse ID *", placeholder: "UUID" },
              { key: "quantity", label: "Quantity *", placeholder: "100" },
              { key: "unit_cost", label: "Unit Cost", placeholder: "50.00" },
              { key: "currency_code", label: "Currency", placeholder: "AED" },
              { key: "notes", label: "Notes", placeholder: "Initial stock" },
            ].map(({ key, label, placeholder }) => (
              <div key={key}>
                <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
                <input
                  className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
                  placeholder={placeholder}
                  value={form[key as keyof OpeningStockForm]}
                  onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                />
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleOpeningStock}
              disabled={saving}
              className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Record"}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="rounded border border-gray-300 px-3 py-1 text-sm text-gray-600 hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Positions table */}
      {positions.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-gray-200 py-12 text-center text-sm text-gray-400">
          No stock positions yet. Record opening stock to get started.
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500">
              <tr>
                <th className="px-4 py-2 text-left">Product</th>
                <th className="px-4 py-2 text-left">Warehouse</th>
                <th className="px-4 py-2 text-right">On Hand</th>
                <th className="px-4 py-2 text-right">Available</th>
                <th className="px-4 py-2 text-right">Reserved</th>
                <th className="px-4 py-2 text-right">Damaged</th>
                <th className="px-4 py-2 text-right">Unit Cost</th>
                <th className="px-4 py-2 text-left">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {positions.map((pos) => (
                <tr key={pos.id} className="bg-white hover:bg-gray-50">
                  <td className="px-4 py-2 font-mono text-xs text-gray-500">
                    {pos.product_id.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-2 font-mono text-xs text-gray-500">
                    {pos.warehouse_id.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-2 text-right font-medium">{pos.qty_on_hand}</td>
                  <td className="px-4 py-2 text-right text-green-700 font-medium">
                    {availableQty(pos)}
                  </td>
                  <td className="px-4 py-2 text-right text-yellow-600">{pos.qty_reserved}</td>
                  <td className="px-4 py-2 text-right text-red-500">{pos.qty_damaged}</td>
                  <td className="px-4 py-2 text-right text-gray-500">
                    {pos.unit_cost
                      ? `${pos.currency_code ?? ""} ${parseFloat(pos.unit_cost).toFixed(2)}`
                      : "—"}
                  </td>
                  <td className="px-4 py-2">
                    {isLowStock(pos) ? (
                      <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                        Low Stock
                      </span>
                    ) : (
                      <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                        OK
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
