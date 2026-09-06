"use client";

/**
 * Reorder Rules Management — Phase 8 Inventory Intelligence
 * List, create, and toggle reorder rules per product/warehouse.
 */

import { useEffect, useState } from "react";
import { getAccessToken } from "@/lib/auth/tokenStorage";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface ReorderRule {
  id: string;
  product_id: string;
  variant_id: string | null;
  warehouse_id: string | null;
  reorder_level: string;
  reorder_quantity: string;
  is_active: boolean;
  created_at: string;
}

export default function ReorderRulesPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";

  const [rules, setRules] = useState<ReorderRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  // Form state
  const [productId, setProductId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [reorderLevel, setReorderLevel] = useState("");
  const [reorderQty, setReorderQty] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function fetchRules() {
    if (!companyId) return;
    setLoading(true);
    fetch(`${API_BASE}/api/v1/companies/${companyId}/inventory/reorder-rules?limit=200`, {
      headers: { Authorization: `Bearer ${getAccessToken()}` },
    })
      .then((r) => r.json())
      .then((body) => {
        setRules(body.data ?? []);
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load reorder rules.");
        setLoading(false);
      });
  }

  useEffect(() => {
    fetchRules();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!companyId) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/companies/${companyId}/inventory/reorder-rules`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${getAccessToken()}`,
          },
          body: JSON.stringify({
            product_id: productId,
            warehouse_id: warehouseId || null,
            reorder_level: parseFloat(reorderLevel),
            reorder_quantity: parseFloat(reorderQty),
            is_active: true,
          }),
        }
      );
      if (!res.ok) {
        const body = await res.json();
        setError(body.detail ?? "Failed to create rule.");
      } else {
        setShowForm(false);
        setProductId("");
        setWarehouseId("");
        setReorderLevel("");
        setReorderQty("");
        fetchRules();
      }
    } catch {
      setError("Network error.");
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleRule(rule: ReorderRule) {
    if (!companyId) return;
    await fetch(
      `${API_BASE}/api/v1/companies/${companyId}/inventory/reorder-rules/${rule.id}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${getAccessToken()}`,
        },
        body: JSON.stringify({ is_active: !rule.is_active }),
      }
    );
    fetchRules();
  }

  async function deleteRule(ruleId: string) {
    if (!companyId) return;
    await fetch(
      `${API_BASE}/api/v1/companies/${companyId}/inventory/reorder-rules/${ruleId}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${getAccessToken()}` },
      }
    );
    fetchRules();
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Reorder Rules</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700 text-sm"
        >
          {showForm ? "Cancel" : "+ Add Rule"}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 p-4 rounded">{error}</div>
      )}

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="bg-gray-50 border rounded p-4 space-y-4 max-w-lg"
        >
          <h2 className="font-semibold text-gray-700">New Reorder Rule</h2>
          <div>
            <label className="block text-sm text-gray-600 mb-1">
              Product ID <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              required
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
              placeholder="UUID"
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">
              Warehouse ID (leave blank for global rule)
            </label>
            <input
              type="text"
              value={warehouseId}
              onChange={(e) => setWarehouseId(e.target.value)}
              placeholder="UUID or leave blank"
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">
                Reorder Level <span className="text-red-500">*</span>
              </label>
              <input
                type="number"
                required
                min={0}
                step="0.01"
                value={reorderLevel}
                onChange={(e) => setReorderLevel(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">
                Reorder Quantity <span className="text-red-500">*</span>
              </label>
              <input
                type="number"
                required
                min={0.01}
                step="0.01"
                value={reorderQty}
                onChange={(e) => setReorderQty(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm"
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700 text-sm disabled:opacity-50"
          >
            {submitting ? "Creating…" : "Create Rule"}
          </button>
        </form>
      )}

      {loading ? (
        <p className="text-gray-500">Loading rules…</p>
      ) : rules.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          No reorder rules defined yet.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Product</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Warehouse</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Reorder Level</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Reorder Qty</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {rules.map((r) => (
                <tr key={r.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">
                    {r.product_id.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">
                    {r.warehouse_id ? `${r.warehouse_id.slice(0, 8)}…` : "Global"}
                  </td>
                  <td className="px-4 py-3">{r.reorder_level}</td>
                  <td className="px-4 py-3">{r.reorder_quantity}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        r.is_active
                          ? "bg-green-100 text-green-700"
                          : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {r.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3 space-x-3">
                    <button
                      onClick={() => toggleRule(r)}
                      className="text-xs text-indigo-600 hover:text-indigo-800"
                    >
                      {r.is_active ? "Deactivate" : "Activate"}
                    </button>
                    <button
                      onClick={() => deleteRule(r.id)}
                      className="text-xs text-red-500 hover:text-red-700"
                    >
                      Delete
                    </button>
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
