"use client";

import { useState, useEffect, useCallback } from "react";
import {
  listPriceLists,
  createPriceList,
  deletePriceList,
  type PriceListRead,
} from "@/lib/api/sales";

const PAGE_SIZE = 20;

export default function PriceListsPage() {
  const [priceLists, setPriceLists] = useState<PriceListRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);

  const [form, setForm] = useState({
    name: "",
    currency_code: "USD",
    effective_from: "",
    is_default: false,
    is_active: true,
    priority: "0",
    description: "",
  });

  const companyId =
    typeof window !== "undefined"
      ? (localStorage.getItem("company_id") ?? "")
      : "";
  const token =
    typeof window !== "undefined"
      ? (localStorage.getItem("access_token") ?? undefined)
      : undefined;

  const load = useCallback(async () => {
    if (!companyId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await listPriceLists(companyId, { skip, limit: PAGE_SIZE }, token);
      setPriceLists(res.data as PriceListRead[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load price lists");
    } finally {
      setLoading(false);
    }
  }, [companyId, token, skip]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!companyId) return;
    setSubmitting(true);
    setFormError(null);
    try {
      await createPriceList(
        companyId,
        {
          name: form.name,
          currency_code: form.currency_code,
          effective_from: form.effective_from,
          is_default: form.is_default,
          is_active: form.is_active,
          priority: Number(form.priority),
          description: form.description || null,
        },
        token
      );
      setShowForm(false);
      setForm({
        name: "",
        currency_code: "USD",
        effective_from: "",
        is_default: false,
        is_active: true,
        priority: "0",
        description: "",
      });
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to create price list");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this price list? All entries will also be removed.")) return;
    try {
      await deletePriceList(companyId, id, token);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Price Lists</h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage pricing tiers, quantity breaks, and product prices
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
        >
          + New Price List
        </button>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">New Price List</h2>
            {formError && (
              <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
                {formError}
              </div>
            )}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                <input
                  required
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g. Standard Retail Pricing"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Currency
                  </label>
                  <input
                    value={form.currency_code}
                    onChange={(e) => setForm({ ...form, currency_code: e.target.value })}
                    maxLength={3}
                    className="w-full border rounded-lg px-3 py-2 text-sm uppercase focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Priority
                  </label>
                  <input
                    type="number"
                    min={0}
                    value={form.priority}
                    onChange={(e) => setForm({ ...form, priority: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Effective From *
                </label>
                <input
                  type="date"
                  required
                  value={form.effective_from}
                  onChange={(e) => setForm({ ...form, effective_from: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description
                </label>
                <textarea
                  rows={2}
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Optional description"
                />
              </div>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={form.is_default}
                    onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
                    className="rounded"
                  />
                  Set as default
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={form.is_active}
                    onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                    className="rounded"
                  />
                  Active
                </label>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-1 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50"
                >
                  {submitting ? "Creating…" : "Create Price List"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="flex-1 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 text-sm"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-40 text-gray-500 text-sm">
          Loading price lists…
        </div>
      ) : error ? (
        <div className="p-4 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
      ) : priceLists.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-40 text-gray-400">
          <p className="text-lg font-medium">No price lists yet</p>
          <p className="text-sm mt-1">Create your first price list to get started</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Name</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Currency</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">From</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600">Priority</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600">Status</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600">Default</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {priceLists.map((pl) => (
                <tr key={pl.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {pl.name}
                    {pl.description && (
                      <p className="text-xs text-gray-400 font-normal">{pl.description}</p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-700">{pl.currency_code}</td>
                  <td className="px-4 py-3 text-gray-700">{pl.effective_from}</td>
                  <td className="px-4 py-3 text-center text-gray-700">{pl.priority}</td>
                  <td className="px-4 py-3 text-center">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        pl.is_active
                          ? "bg-green-100 text-green-700"
                          : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {pl.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    {pl.is_default && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
                        Default
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleDelete(pl.id)}
                      className="text-red-500 hover:text-red-700 text-xs font-medium"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between px-4 py-3 border-t bg-gray-50">
            <button
              onClick={() => setSkip((s) => Math.max(0, s - PAGE_SIZE))}
              disabled={skip === 0}
              className="text-sm text-gray-600 hover:text-gray-900 disabled:opacity-40"
            >
              ← Previous
            </button>
            <span className="text-xs text-gray-500">
              Showing {skip + 1}–{skip + priceLists.length}
            </span>
            <button
              onClick={() => setSkip((s) => s + PAGE_SIZE)}
              disabled={priceLists.length < PAGE_SIZE}
              className="text-sm text-gray-600 hover:text-gray-900 disabled:opacity-40"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
