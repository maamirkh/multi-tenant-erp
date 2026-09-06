"use client";

import { useEffect, useState } from "react";
import {
  createCustomerCategory,
  getCustomerCategories,
  CustomerCategoryRead,
} from "@/lib/api/sales";

interface PageProps {
  params: { company_id: string };
}

/**
 * Customer Category management page.
 * Lists all customer categories and provides create functionality.
 *
 * Spec ref: specs/007-sales-management/spec.md §14.2
 */
export default function CustomerCategoriesPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const [categories, setCategories] = useState<CustomerCategoryRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ code: "", name: "", description: "" });

  useEffect(() => {
    if (!companyId) return;
    loadCategories();
  }, [companyId]);

  async function loadCategories() {
    setLoading(true);
    try {
      const res = await getCustomerCategories(companyId);
      setCategories(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load categories");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await createCustomerCategory(companyId, {
        code: form.code,
        name: form.name,
        description: form.description || null,
      });
      setShowForm(false);
      setForm({ code: "", name: "", description: "" });
      setSuccess("Category created");
      await loadCategories();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create category");
    }
  }

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-semibold">Customer Categories</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          {showForm ? "Cancel" : "New Category"}
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-700 rounded">{error}</div>
      )}
      {success && (
        <div className="mb-4 p-3 bg-green-50 text-green-700 rounded">{success}</div>
      )}

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 p-4 border rounded space-y-3">
          <div>
            <label className="block text-sm font-medium mb-1">Code</label>
            <input
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })}
              className="w-full border rounded px-3 py-2"
              required
              maxLength={20}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Name</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full border rounded px-3 py-2"
              required
              maxLength={200}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Description</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="w-full border rounded px-3 py-2"
              rows={2}
            />
          </div>
          <button
            type="submit"
            className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
          >
            Create
          </button>
        </form>
      )}

      {loading ? (
        <div className="text-center py-8 text-gray-500">Loading...</div>
      ) : categories.length === 0 ? (
        <div className="text-center py-8 text-gray-400">No categories found</div>
      ) : (
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b bg-gray-50">
              <th className="text-left p-3">Code</th>
              <th className="text-left p-3">Name</th>
              <th className="text-left p-3">Description</th>
              <th className="text-left p-3">Credit Limit</th>
              <th className="text-left p-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {categories.map((cat) => (
              <tr key={cat.id} className="border-b hover:bg-gray-50">
                <td className="p-3 font-mono text-sm">{cat.code}</td>
                <td className="p-3">{cat.name}</td>
                <td className="p-3 text-gray-600">{cat.description ?? "-"}</td>
                <td className="p-3">{cat.default_credit_limit}</td>
                <td className="p-3">
                  <span
                    className={`px-2 py-1 rounded text-xs ${
                      cat.is_active
                        ? "bg-green-100 text-green-800"
                        : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {cat.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
