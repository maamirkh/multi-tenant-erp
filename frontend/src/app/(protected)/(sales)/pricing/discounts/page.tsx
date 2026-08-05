"use client";

import { useState, useEffect, useCallback } from "react";
import {
  listDiscountRules,
  createDiscountRule,
  deleteDiscountRule,
  type DiscountRuleRead,
} from "@/lib/api/sales";

const RULE_TYPES = ["PERCENTAGE", "FIXED_AMOUNT", "VOLUME", "PROMOTIONAL"];
const APPLICABILITIES = [
  "ALL_CUSTOMERS",
  "SPECIFIC_CUSTOMER",
  "SPECIFIC_GROUP",
  "SPECIFIC_CATEGORY",
];
const PRODUCT_SCOPES = ["ALL_PRODUCTS", "SPECIFIC_PRODUCT", "SPECIFIC_CATEGORY"];

const PAGE_SIZE = 20;

const RULE_TYPE_LABELS: Record<string, string> = {
  PERCENTAGE: "Percentage %",
  FIXED_AMOUNT: "Fixed Amount",
  VOLUME: "Volume",
  PROMOTIONAL: "Promotional",
};

export default function DiscountsPage() {
  const [rules, setRules] = useState<DiscountRuleRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);

  const [form, setForm] = useState({
    name: "",
    rule_type: "PERCENTAGE",
    discount_value: "",
    effective_from: "",
    effective_to: "",
    applicability: "ALL_CUSTOMERS",
    applicability_id: "",
    product_scope: "ALL_PRODUCTS",
    product_scope_id: "",
    minimum_quantity: "",
    minimum_order_value: "",
    priority: "0",
    is_stackable: false,
    is_active: true,
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
      const res = await listDiscountRules(companyId, { skip, limit: PAGE_SIZE }, token);
      setRules(res.data as DiscountRuleRead[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load discount rules");
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
      await createDiscountRule(
        companyId,
        {
          name: form.name,
          rule_type: form.rule_type,
          discount_value: form.discount_value,
          effective_from: form.effective_from,
          effective_to: form.effective_to || null,
          applicability: form.applicability,
          applicability_id: form.applicability_id || null,
          product_scope: form.product_scope,
          product_scope_id: form.product_scope_id || null,
          minimum_quantity: form.minimum_quantity || null,
          minimum_order_value: form.minimum_order_value || null,
          priority: Number(form.priority),
          is_stackable: form.is_stackable,
          is_active: form.is_active,
        },
        token
      );
      setShowForm(false);
      setForm({
        name: "",
        rule_type: "PERCENTAGE",
        discount_value: "",
        effective_from: "",
        effective_to: "",
        applicability: "ALL_CUSTOMERS",
        applicability_id: "",
        product_scope: "ALL_PRODUCTS",
        product_scope_id: "",
        minimum_quantity: "",
        minimum_order_value: "",
        priority: "0",
        is_stackable: false,
        is_active: true,
      });
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to create discount rule");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this discount rule?")) return;
    try {
      await deleteDiscountRule(companyId, id, token);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    }
  };

  const needsApplicabilityId =
    form.applicability !== "ALL_CUSTOMERS";
  const needsProductScopeId =
    form.product_scope !== "ALL_PRODUCTS";

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Discount Rules</h1>
          <p className="text-sm text-gray-500 mt-1">
            Configure automatic discounts by customer, product, quantity, and order value
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
        >
          + New Discount Rule
        </button>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 overflow-auto">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 my-8">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">New Discount Rule</h2>
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
                  placeholder="e.g. VIP Customer 15% Discount"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Rule Type *
                  </label>
                  <select
                    value={form.rule_type}
                    onChange={(e) => setForm({ ...form, rule_type: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {RULE_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {RULE_TYPE_LABELS[t] ?? t}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Discount Value *
                  </label>
                  <input
                    required
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.discount_value}
                    onChange={(e) => setForm({ ...form, discount_value: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g. 10 for 10%"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Customer Applicability
                </label>
                <select
                  value={form.applicability}
                  onChange={(e) => setForm({ ...form, applicability: e.target.value, applicability_id: "" })}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {APPLICABILITIES.map((a) => (
                    <option key={a} value={a}>
                      {a.replace("_", " ")}
                    </option>
                  ))}
                </select>
              </div>
              {needsApplicabilityId && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Customer / Group / Category ID
                  </label>
                  <input
                    value={form.applicability_id}
                    onChange={(e) => setForm({ ...form, applicability_id: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="UUID"
                  />
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Product Scope
                </label>
                <select
                  value={form.product_scope}
                  onChange={(e) => setForm({ ...form, product_scope: e.target.value, product_scope_id: "" })}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {PRODUCT_SCOPES.map((s) => (
                    <option key={s} value={s}>
                      {s.replace("_", " ")}
                    </option>
                  ))}
                </select>
              </div>
              {needsProductScopeId && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Product / Category ID
                  </label>
                  <input
                    value={form.product_scope_id}
                    onChange={(e) => setForm({ ...form, product_scope_id: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="UUID"
                  />
                </div>
              )}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Min Quantity
                  </label>
                  <input
                    type="number"
                    step="0.001"
                    min="0"
                    value={form.minimum_quantity}
                    onChange={(e) => setForm({ ...form, minimum_quantity: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Min Order Value
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.minimum_order_value}
                    onChange={(e) =>
                      setForm({ ...form, minimum_order_value: e.target.value })
                    }
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
              <div className="flex gap-4">
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={form.is_stackable}
                    onChange={(e) => setForm({ ...form, is_stackable: e.target.checked })}
                    className="rounded"
                  />
                  Stackable
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
                  {submitting ? "Saving…" : "Create Rule"}
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
          Loading discount rules…
        </div>
      ) : error ? (
        <div className="p-4 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
      ) : rules.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-40 text-gray-400">
          <p className="text-lg font-medium">No discount rules</p>
          <p className="text-sm mt-1">Create rules to apply automatic discounts on sales</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Name</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Type</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">Value</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Applicability</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600">Priority</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600">Status</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rules.map((r) => (
                <tr key={r.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {r.name}
                    {r.is_stackable && (
                      <span className="ml-1 text-xs text-blue-600 font-normal">(stackable)</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {RULE_TYPE_LABELS[r.rule_type] ?? r.rule_type}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold text-gray-900">
                    {r.rule_type === "PERCENTAGE" ? `${r.discount_value}%` : r.discount_value}
                  </td>
                  <td className="px-4 py-3 text-gray-600 text-xs">
                    {r.applicability}
                    {r.applicability_id && (
                      <span className="block font-mono text-gray-400">{r.applicability_id}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center text-gray-700">{r.priority}</td>
                  <td className="px-4 py-3 text-center">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        r.is_active
                          ? "bg-green-100 text-green-700"
                          : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {r.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleDelete(r.id)}
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
              Showing {skip + 1}–{skip + rules.length}
            </span>
            <button
              onClick={() => setSkip((s) => s + PAGE_SIZE)}
              disabled={rules.length < PAGE_SIZE}
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
