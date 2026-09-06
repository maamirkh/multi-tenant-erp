"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  listCustomers,
  getCustomerCategories,
  getCustomerGroups,
  type CustomerListItem,
  type CustomerCategoryRead,
  type CustomerGroupRead,
} from "@/lib/api/sales";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  ACTIVE: "bg-green-100 text-green-700",
  ON_HOLD: "bg-yellow-100 text-yellow-700",
  BLOCKED: "bg-red-100 text-red-700",
  INACTIVE: "bg-slate-100 text-slate-600",
};

const CREDIT_COLORS: Record<string, string> = {
  GOOD: "text-green-600",
  WARNING: "text-yellow-600",
  EXCEEDED: "text-red-600",
  HOLD: "text-red-700 font-semibold",
};

const PAGE_SIZE = 20;

export default function CustomersPage() {
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [groupFilter, setGroupFilter] = useState("");
  const [categories, setCategories] = useState<CustomerCategoryRead[]>([]);
  const [groups, setGroups] = useState<CustomerGroupRead[]>([]);

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
      const res = await listCustomers(
        companyId,
        {
          ...(search ? { q: search } : {}),
          ...(statusFilter ? { status: statusFilter } : {}),
          ...(typeFilter ? { customer_type: typeFilter } : {}),
          ...(categoryFilter ? { category_id: categoryFilter } : {}),
          ...(groupFilter ? { group_id: groupFilter } : {}),
          page,
          page_size: PAGE_SIZE,
        },
        token
      );
      setCustomers(res.data?.items ?? []);
      setTotal(res.data?.total ?? 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load customers");
    } finally {
      setLoading(false);
    }
  }, [companyId, token, search, statusFilter, typeFilter, categoryFilter, groupFilter, page]);

  useEffect(() => {
    if (!companyId) return;
    Promise.all([
      getCustomerCategories(companyId, token),
      getCustomerGroups(companyId, token),
    ]).then(([cats, grps]) => {
      setCategories(cats.data ?? []);
      setGroups(grps.data ?? []);
    });
  }, [companyId, token]);

  useEffect(() => {
    load();
  }, [load]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Customers</h1>
          <p className="text-sm text-gray-500 mt-1">{total} total records</p>
        </div>
        <Link
          href="customers/new"
          className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 text-sm font-medium"
        >
          New Customer
        </Link>
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap gap-3">
        <input
          type="search"
          placeholder="Search customers…"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="border border-gray-300 rounded-md px-3 py-1.5 text-sm w-56"
        />
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
        >
          <option value="">All Statuses</option>
          <option value="DRAFT">Draft</option>
          <option value="ACTIVE">Active</option>
          <option value="ON_HOLD">On Hold</option>
          <option value="BLOCKED">Blocked</option>
          <option value="INACTIVE">Inactive</option>
        </select>
        <select
          value={typeFilter}
          onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
          className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
        >
          <option value="">All Types</option>
          <option value="COMPANY">Company</option>
          <option value="INDIVIDUAL">Individual</option>
          <option value="GOVERNMENT">Government</option>
          <option value="NGO">NGO</option>
        </select>
        <select
          value={categoryFilter}
          onChange={(e) => { setCategoryFilter(e.target.value); setPage(1); }}
          className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
        >
          <option value="">All Categories</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        <select
          value={groupFilter}
          onChange={(e) => { setGroupFilter(e.target.value); setPage(1); }}
          className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
        >
          <option value="">All Groups</option>
          {groups.map((g) => (
            <option key={g.id} value={g.id}>{g.name}</option>
          ))}
        </select>
        <Link
          href="customers/import"
          className="px-3 py-1.5 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
        >
          Import
        </Link>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading…</div>
      ) : customers.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          No customers found. <Link href="customers/new" className="text-indigo-600 hover:underline">Create the first one.</Link>
        </div>
      ) : (
        <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 rounded-lg">
          <table className="min-w-full divide-y divide-gray-300">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Code</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Legal Name</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Type</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Credit</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Currency</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {customers.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-mono text-gray-700">{c.customer_code}</td>
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">{c.legal_name}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{c.customer_type}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                        STATUS_COLORS[c.status] ?? "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {c.status.replace("_", " ")}
                    </span>
                  </td>
                  <td className={`px-4 py-3 text-xs font-medium ${CREDIT_COLORS[c.credit_status] ?? "text-gray-500"}`}>
                    {c.credit_status}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">{c.currency_code}</td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`customers/${c.id}`}
                      className="text-indigo-600 hover:text-indigo-700 text-sm font-medium"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between text-sm text-gray-600">
          <span>Page {page} of {totalPages}</span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1 border rounded disabled:opacity-40 hover:bg-gray-50"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1 border rounded disabled:opacity-40 hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
