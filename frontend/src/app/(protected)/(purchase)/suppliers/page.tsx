"use client";

import { useEffect, useState } from "react";
import {
  getSuppliers,
  SupplierList,
} from "@/lib/api/purchase";

interface PageProps {
  params: { company_id: string };
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  ACTIVE: "bg-green-100 text-green-800",
  INACTIVE: "bg-yellow-100 text-yellow-800",
  BLOCKED: "bg-red-100 text-red-800",
  ARCHIVED: "bg-slate-100 text-slate-600",
};

/**
 * Supplier list page with search, status filter, and pagination.
 * Task: T044
 */
export default function SuppliersPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const [suppliers, setSuppliers] = useState<SupplierList[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [skip, setSkip] = useState(0);
  const limit = 20;

  useEffect(() => {
    if (!companyId) return;
    load();
  }, [companyId, statusFilter, skip]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getSuppliers(companyId, {
        ...(query ? { query } : {}),
        ...(statusFilter ? { status: statusFilter } : {}),
        skip,
        limit,
      });
      setSuppliers(res.data);
      setTotal(res.data.length);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load suppliers");
    } finally {
      setLoading(false);
    }
  }

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setSkip(0);
    load();
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Suppliers</h1>
        <div className="flex gap-2">
          <a
            href={`/companies/${companyId}/purchase/suppliers/import`}
            className="px-3 py-1.5 border rounded text-sm hover:bg-gray-50"
          >
            Import CSV
          </a>
          <a
            href={`/companies/${companyId}/purchase/suppliers/new`}
            className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
          >
            + New Supplier
          </a>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Search & Filters */}
      <form onSubmit={handleSearch} className="flex gap-3 mb-4">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name or code..."
          className="flex-1 border rounded px-3 py-1.5 text-sm"
        />
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setSkip(0); }}
          className="border rounded px-3 py-1.5 text-sm"
        >
          <option value="">All Statuses</option>
          <option value="DRAFT">Draft</option>
          <option value="ACTIVE">Active</option>
          <option value="INACTIVE">Inactive</option>
          <option value="BLOCKED">Blocked</option>
          <option value="ARCHIVED">Archived</option>
        </select>
        <button
          type="submit"
          className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
        >
          Search
        </button>
      </form>

      {/* Table */}
      {loading ? (
        <p className="text-sm text-gray-500">Loading...</p>
      ) : (
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-gray-50 border-b">
              <th className="text-left px-4 py-2 font-medium text-gray-700">Code</th>
              <th className="text-left px-4 py-2 font-medium text-gray-700">Legal Name</th>
              <th className="text-left px-4 py-2 font-medium text-gray-700">Type</th>
              <th className="text-left px-4 py-2 font-medium text-gray-700">Status</th>
              <th className="text-left px-4 py-2 font-medium text-gray-700">Rating</th>
              <th className="text-left px-4 py-2 font-medium text-gray-700">Actions</th>
            </tr>
          </thead>
          <tbody>
            {suppliers.map((s) => (
              <tr key={s.id} className="border-b hover:bg-gray-50">
                <td className="px-4 py-2 font-mono text-xs">
                  {s.supplier_code}
                  {s.is_preferred && (
                    <span className="ml-1 text-yellow-500" title="Preferred">★</span>
                  )}
                </td>
                <td className="px-4 py-2 font-medium">
                  {s.legal_name}
                  {s.trading_name && (
                    <span className="ml-1 text-gray-400 text-xs">({s.trading_name})</span>
                  )}
                </td>
                <td className="px-4 py-2">
                  <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">
                    {s.supplier_type}
                  </span>
                </td>
                <td className="px-4 py-2">
                  <span className={`text-xs px-2 py-0.5 rounded ${STATUS_COLORS[s.status] ?? "bg-gray-100 text-gray-600"}`}>
                    {s.status}
                  </span>
                </td>
                <td className="px-4 py-2 text-gray-600">
                  {s.rating_score != null ? `${s.rating_score}/10` : "-"}
                </td>
                <td className="px-4 py-2">
                  <a
                    href={`/companies/${companyId}/purchase/suppliers/${s.id}`}
                    className="text-blue-600 hover:underline text-xs"
                  >
                    View
                  </a>
                </td>
              </tr>
            ))}
            {suppliers.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-gray-500">
                  No suppliers found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}

      {/* Pagination */}
      {total > limit && (
        <div className="flex items-center justify-between mt-4 text-sm text-gray-600">
          <span>Showing {skip + 1}–{Math.min(skip + limit, total)} of {total}</span>
          <div className="flex gap-2">
            <button
              onClick={() => setSkip(Math.max(0, skip - limit))}
              disabled={skip === 0}
              className="px-3 py-1 border rounded disabled:opacity-50 hover:bg-gray-50"
            >
              Previous
            </button>
            <button
              onClick={() => setSkip(skip + limit)}
              disabled={skip + limit >= total}
              className="px-3 py-1 border rounded disabled:opacity-50 hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
