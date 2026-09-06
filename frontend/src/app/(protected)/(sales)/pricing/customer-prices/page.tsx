"use client";

import { useState, useEffect, useCallback } from "react";
import {
  listCustomerSpecificPrices,
  createCustomerSpecificPrice,
  deleteCustomerSpecificPrice,
  type CustomerSpecificPriceRead,
} from "@/lib/api/sales";

const PAGE_SIZE = 20;

export default function CustomerPricesPage() {
  const [prices, setPrices] = useState<CustomerSpecificPriceRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);

  const [form, setForm] = useState({
    customer_id: "",
    product_id: "",
    unit_price: "",
    effective_from: "",
    effective_to: "",
    minimum_quantity: "1",
  });

  const companyId =
    typeof window !== "undefined"
      ? (localStorage.getItem("erp_active_company_id") ?? "")
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
      const res = await listCustomerSpecificPrices(
        companyId,
        { skip, limit: PAGE_SIZE },
        token
      );
      setPrices(res.data as CustomerSpecificPriceRead[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load customer prices");
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
      await createCustomerSpecificPrice(
        companyId,
        {
          customer_id: form.customer_id,
          product_id: form.product_id,
          unit_price: form.unit_price,
          effective_from: form.effective_from,
          effective_to: form.effective_to || null,
          minimum_quantity: form.minimum_quantity,
        },
        token
      );
      setShowForm(false);
      setForm({
        customer_id: "",
        product_id: "",
        unit_price: "",
        effective_from: "",
        effective_to: "",
        minimum_quantity: "1",
      });
      await load();
    } catch (err) {
      setFormError(
        err instanceof Error ? err.message : "Failed to create customer price"
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Remove this customer-specific price?")) return;
    try {
      await deleteCustomerSpecificPrice(companyId, id, token);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Customer-Specific Prices</h1>
          <p className="text-sm text-gray-500 mt-1">
            Override standard pricing for individual customers and products
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
        >
          + Add Price Override
        </button>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              New Customer-Specific Price
            </h2>
            {formError && (
              <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
                {formError}
              </div>
            )}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Customer ID *
                </label>
                <input
                  required
                  value={form.customer_id}
                  onChange={(e) => setForm({ ...form, customer_id: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Customer UUID"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Product ID *
                </label>
                <input
                  required
                  value={form.product_id}
                  onChange={(e) => setForm({ ...form, product_id: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Product UUID"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Unit Price *
                  </label>
                  <input
                    required
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.unit_price}
                    onChange={(e) => setForm({ ...form, unit_price: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Min Quantity
                  </label>
                  <input
                    type="number"
                    step="0.001"
                    min="0.001"
                    value={form.minimum_quantity}
                    onChange={(e) => setForm({ ...form, minimum_quantity: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
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
                    Effective To
                  </label>
                  <input
                    type="date"
                    value={form.effective_to}
                    onChange={(e) => setForm({ ...form, effective_to: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-1 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50"
                >
                  {submitting ? "Saving…" : "Save Price Override"}
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
          Loading customer prices…
        </div>
      ) : error ? (
        <div className="p-4 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
      ) : prices.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-40 text-gray-400">
          <p className="text-lg font-medium">No customer-specific prices</p>
          <p className="text-sm mt-1">Add overrides to apply special rates per customer</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Customer ID</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Product ID</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">Unit Price</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">Min Qty</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600">Effective</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {prices.map((p) => (
                <tr key={p.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-mono text-xs text-gray-600 truncate max-w-[140px]">
                    {p.customer_id}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-600 truncate max-w-[140px]">
                    {p.product_id}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold text-gray-900">
                    {p.unit_price}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-600">{p.minimum_quantity}</td>
                  <td className="px-4 py-3 text-center text-gray-600 text-xs">
                    {p.effective_from}
                    {p.effective_to ? ` – ${p.effective_to}` : " →"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleDelete(p.id)}
                      className="text-red-500 hover:text-red-700 text-xs font-medium"
                    >
                      Remove
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
              Showing {skip + 1}–{skip + prices.length}
            </span>
            <button
              onClick={() => setSkip((s) => s + PAGE_SIZE)}
              disabled={prices.length < PAGE_SIZE}
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
