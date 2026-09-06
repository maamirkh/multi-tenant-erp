"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createCustomer, getCustomerCategories, getCustomerGroups, type CustomerCategoryRead, type CustomerGroupRead } from "@/lib/api/sales";

const CUSTOMER_TYPES = ["COMPANY", "INDIVIDUAL", "GOVERNMENT", "NGO"];
const CURRENCIES = ["USD", "EUR", "GBP", "AED", "SAR", "EGP"];
const PAYMENT_TERMS = ["IMMEDIATE", "NET7", "NET15", "NET30", "NET45", "NET60", "NET90"];

export default function NewCustomerPage() {
  const router = useRouter();
  const companyId = typeof window !== "undefined" ? (localStorage.getItem("company_id") ?? "") : "";
  const token = typeof window !== "undefined" ? (localStorage.getItem("access_token") ?? undefined) : undefined;

  const [categories, setCategories] = useState<CustomerCategoryRead[]>([]);
  const [groups, setGroups] = useState<CustomerGroupRead[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState({
    customer_code: "",
    legal_name: "",
    trading_name: "",
    customer_type: "COMPANY",
    category_id: "",
    group_id: "",
    currency_code: "USD",
    payment_term: "",
    tax_number: "",
    website: "",
    notes: "",
    rating: "",
    credit_limit: 0,
  });

  useEffect(() => {
    if (!companyId) return;
    getCustomerCategories(companyId, token).then((r) => setCategories(r.data ?? []));
    getCustomerGroups(companyId, token).then((r) => setGroups(r.data ?? []));
  }, [companyId, token]);

  function set(key: string, value: string | number) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = { ...form };
      if (!payload.category_id) delete payload.category_id;
      if (!payload.group_id) delete payload.group_id;
      if (!payload.payment_term) delete payload.payment_term;
      if (!payload.trading_name) delete payload.trading_name;
      if (!payload.tax_number) delete payload.tax_number;
      if (!payload.website) delete payload.website;
      if (!payload.notes) delete payload.notes;
      if (!payload.rating) delete payload.rating;
      const res = await createCustomer(companyId, payload, token);
      router.push(`../customers/${res.data?.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create customer");
      setSaving(false);
    }
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Link href="../customers" className="text-sm text-indigo-600 hover:underline">← Customers</Link>
      </div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">New Customer</h1>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">{error}</div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Customer Code <span className="text-red-500">*</span></label>
            <input required value={form.customer_code} onChange={(e) => set("customer_code", e.target.value)} className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm" placeholder="CUST-001" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Legal Name <span className="text-red-500">*</span></label>
            <input required value={form.legal_name} onChange={(e) => set("legal_name", e.target.value)} className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Trading Name</label>
            <input value={form.trading_name} onChange={(e) => set("trading_name", e.target.value)} className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Customer Type <span className="text-red-500">*</span></label>
            <select required value={form.customer_type} onChange={(e) => set("customer_type", e.target.value)} className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm">
              {CUSTOMER_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Category</label>
            <select value={form.category_id} onChange={(e) => set("category_id", e.target.value)} className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm">
              <option value="">— None —</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Group</label>
            <select value={form.group_id} onChange={(e) => set("group_id", e.target.value)} className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm">
              <option value="">— None —</option>
              {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Currency <span className="text-red-500">*</span></label>
            <select required value={form.currency_code} onChange={(e) => set("currency_code", e.target.value)} className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm">
              {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Payment Term</label>
            <select value={form.payment_term} onChange={(e) => set("payment_term", e.target.value)} className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm">
              <option value="">— None —</option>
              {PAYMENT_TERMS.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Tax Number</label>
            <input value={form.tax_number} onChange={(e) => set("tax_number", e.target.value)} className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Credit Limit</label>
            <input type="number" min="0" value={form.credit_limit} onChange={(e) => set("credit_limit", Number(e.target.value))} className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Website</label>
            <input type="url" value={form.website} onChange={(e) => set("website", e.target.value)} className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm" placeholder="https://" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Rating</label>
            <select value={form.rating} onChange={(e) => set("rating", e.target.value)} className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm">
              <option value="">— None —</option>
              <option value="A">A</option>
              <option value="B">B</option>
              <option value="C">C</option>
              <option value="D">D</option>
            </select>
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Notes</label>
          <textarea value={form.notes} onChange={(e) => set("notes", e.target.value)} rows={3} className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm" />
        </div>
        <div className="flex gap-3 pt-2">
          <button type="submit" disabled={saving} className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
            {saving ? "Creating…" : "Create Customer"}
          </button>
          <Link href="../customers" className="px-4 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50">
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
