"use client";

import { useEffect, useState } from "react";
import {
  createSupplierCategory,
  deleteSupplierCategory,
  getSupplierCategories,
  SupplierCategoryRead,
  updateSupplierCategory,
} from "@/lib/api/purchase";

interface PageProps {
  params: { company_id: string };
}

/**
 * Supplier Category management page.
 * Lists all supplier categories and provides create/edit/delete actions.
 *
 * Spec ref: specs/006-purchase-management/spec.md §14 Supplier Master
 */
export default function SupplierCategoriesPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const [categories, setCategories] = useState<SupplierCategoryRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editTarget, setEditTarget] = useState<SupplierCategoryRead | null>(null);
  const [formData, setFormData] = useState({ code: "", name: "", description: "" });

  async function loadCategories() {
    try {
      setLoading(true);
      const res = await getSupplierCategories(companyId);
      setCategories(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load categories");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (companyId) loadCategories();
  }, [companyId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      if (editTarget) {
        await updateSupplierCategory(companyId, editTarget.id, {
          name: formData.name,
          description: formData.description || null,
        });
      } else {
        await createSupplierCategory(companyId, {
          code: formData.code,
          name: formData.name,
          description: formData.description || null,
        });
      }
      setShowForm(false);
      setEditTarget(null);
      setFormData({ code: "", name: "", description: "" });
      await loadCategories();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save category");
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this category?")) return;
    try {
      await deleteSupplierCategory(companyId, id);
      await loadCategories();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete category");
    }
  }

  function handleEdit(cat: SupplierCategoryRead) {
    setEditTarget(cat);
    setFormData({ code: cat.code, name: cat.name, description: cat.description ?? "" });
    setShowForm(true);
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">
          Supplier Categories
        </h1>
        <button
          onClick={() => { setEditTarget(null); setFormData({ code: "", name: "", description: "" }); setShowForm(true); }}
          className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700"
        >
          + New Category
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">Dismiss</button>
        </div>
      )}

      {showForm && (
        <form onSubmit={handleSubmit} className="mb-6 p-4 border rounded-md bg-gray-50">
          <h2 className="text-lg font-medium mb-4">
            {editTarget ? "Edit Category" : "New Category"}
          </h2>
          <div className="grid grid-cols-2 gap-4">
            {!editTarget && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Code</label>
                <input
                  value={formData.code}
                  onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                  required
                  maxLength={20}
                  className="w-full border rounded px-3 py-2 text-sm"
                  placeholder="e.g. TECH-001"
                />
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
              <input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
                maxLength={200}
                className="w-full border rounded px-3 py-2 text-sm"
                placeholder="Category name"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={2}
                className="w-full border rounded px-3 py-2 text-sm"
                placeholder="Optional description"
              />
            </div>
          </div>
          <div className="flex gap-3 mt-4">
            <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700">
              {editTarget ? "Update" : "Create"}
            </button>
            <button
              type="button"
              onClick={() => { setShowForm(false); setEditTarget(null); }}
              className="px-4 py-2 border rounded text-sm font-medium hover:bg-gray-100"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="text-sm text-gray-500">Loading categories...</p>
      ) : categories.length === 0 ? (
        <p className="text-sm text-gray-500">No supplier categories found. Create one to get started.</p>
      ) : (
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-gray-50 border-b">
              <th className="text-left px-4 py-3 font-medium text-gray-700">Code</th>
              <th className="text-left px-4 py-3 font-medium text-gray-700">Name</th>
              <th className="text-left px-4 py-3 font-medium text-gray-700">Status</th>
              <th className="text-left px-4 py-3 font-medium text-gray-700">Actions</th>
            </tr>
          </thead>
          <tbody>
            {categories.map((cat) => (
              <tr key={cat.id} className="border-b hover:bg-gray-50">
                <td className="px-4 py-3 font-mono text-xs">{cat.code}</td>
                <td className="px-4 py-3">{cat.name}</td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                    cat.status === "active"
                      ? "bg-green-100 text-green-800"
                      : "bg-gray-100 text-gray-600"
                  }`}>
                    {cat.status}
                  </span>
                </td>
                <td className="px-4 py-3 flex gap-2">
                  <button
                    onClick={() => handleEdit(cat)}
                    className="text-blue-600 hover:underline text-xs"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(cat.id)}
                    className="text-red-500 hover:underline text-xs"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
