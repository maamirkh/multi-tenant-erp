"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  listQuotations,
  createQuotation,
  type SalesQuotationListItem,
} from "@/lib/api/sales";

const PAGE_SIZE = 20;

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-800",
  SENT_TO_CUSTOMER: "bg-blue-100 text-blue-800",
  ACCEPTED: "bg-green-100 text-green-800",
  REJECTED: "bg-red-100 text-red-800",
  CONVERTED: "bg-purple-100 text-purple-800",
  EXPIRED: "bg-orange-100 text-orange-800",
  CANCELLED: "bg-red-50 text-red-600",
};

export default function QuotationsPage() {
  const router = useRouter();
  const [quotations, setQuotations] = useState<SalesQuotationListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  const today = new Date().toISOString().split("T")[0] ?? "";
  const thirtyDaysOut = new Date(Date.now() + 30 * 86400000)
    .toISOString()
    .split("T")[0] ?? "";

  const [form, setForm] = useState({
    customer_id: "",
    quotation_date: today,
    validity_date: thirtyDaysOut,
    currency_code: "USD",
    sales_rep_id: "",
    internal_notes: "",
    customer_notes: "",
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
      const res = await listQuotations(
        companyId,
        {
          skip,
          limit: PAGE_SIZE,
          ...(statusFilter ? { status: statusFilter } : {}),
          ...(searchTerm ? { search: searchTerm } : {}),
        },
        token,
      );
      setQuotations(res.data as SalesQuotationListItem[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load quotations");
    } finally {
      setLoading(false);
    }
  }, [companyId, token, skip, statusFilter, searchTerm]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      await createQuotation(
        companyId,
        {
          customer_id: form.customer_id,
          quotation_date: form.quotation_date,
          validity_date: form.validity_date,
          currency_code: form.currency_code,
          sales_rep_id: form.sales_rep_id,
          internal_notes: form.internal_notes || null,
          customer_notes: form.customer_notes || null,
          lines: [],
        },
        token,
      );
      setShowForm(false);
      setForm({
        customer_id: "",
        quotation_date: today,
        validity_date: thirtyDaysOut,
        currency_code: "USD",
        sales_rep_id: "",
        internal_notes: "",
        customer_notes: "",
      });
      load();
    } catch (err) {
      setFormError(
        err instanceof Error ? err.message : "Failed to create quotation",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Sales Quotations</h1>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          + New Quotation
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <input
          type="text"
          placeholder="Search quotation number..."
          value={searchTerm}
          onChange={(e) => {
            setSearchTerm(e.target.value);
            setSkip(0);
          }}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-64"
        />
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setSkip(0);
          }}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Statuses</option>
          <option value="DRAFT">Draft</option>
          <option value="SENT_TO_CUSTOMER">Sent to Customer</option>
          <option value="ACCEPTED">Accepted</option>
          <option value="REJECTED">Rejected</option>
          <option value="CONVERTED">Converted</option>
          <option value="EXPIRED">Expired</option>
          <option value="CANCELLED">Cancelled</option>
        </select>
      </div>

      {/* Create Form Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-lg shadow-2xl">
            <h2 className="text-lg font-semibold mb-4">New Sales Quotation</h2>
            {formError && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                {formError}
              </div>
            )}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Customer ID <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={form.customer_id}
                  onChange={(e) =>
                    setForm({ ...form, customer_id: e.target.value })
                  }
                  placeholder="UUID of customer"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Quotation Date <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    required
                    value={form.quotation_date}
                    onChange={(e) =>
                      setForm({ ...form, quotation_date: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Valid Until <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    required
                    value={form.validity_date}
                    onChange={(e) =>
                      setForm({ ...form, validity_date: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Currency
                  </label>
                  <input
                    type="text"
                    maxLength={3}
                    value={form.currency_code}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        currency_code: e.target.value.toUpperCase(),
                      })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Sales Rep ID <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={form.sales_rep_id}
                    onChange={(e) =>
                      setForm({ ...form, sales_rep_id: e.target.value })
                    }
                    placeholder="UUID of sales rep"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Internal Notes
                </label>
                <textarea
                  value={form.internal_notes}
                  onChange={(e) =>
                    setForm({ ...form, internal_notes: e.target.value })
                  }
                  rows={2}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Customer Notes
                </label>
                <textarea
                  value={form.customer_notes}
                  onChange={(e) =>
                    setForm({ ...form, customer_notes: e.target.value })
                  }
                  rows={2}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  {submitting ? "Creating..." : "Create Quotation"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowForm(false);
                    setFormError(null);
                  }}
                  className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">
          Loading quotations...
        </div>
      ) : error ? (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      ) : quotations.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <p className="text-lg font-medium">No quotations found</p>
          <p className="text-sm mt-1">Create your first quotation to get started</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">
                  Number
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">
                  Date
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">
                  Valid Until
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">
                  Currency
                </th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">
                  Total
                </th>
                <th className="px-4 py-3 text-center font-medium text-gray-600">
                  Status
                </th>
                <th className="px-4 py-3 text-center font-medium text-gray-600">
                  Rev
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {quotations.map((q) => (
                <tr
                  key={q.id}
                  className="hover:bg-gray-50 cursor-pointer transition-colors"
                  onClick={() =>
                    router.push(`/quotations/${q.id}`)
                  }
                >
                  <td className="px-4 py-3 font-mono text-blue-600 font-medium">
                    {q.quotation_number}
                  </td>
                  <td className="px-4 py-3 text-gray-700">{q.quotation_date}</td>
                  <td className="px-4 py-3 text-gray-700">{q.validity_date}</td>
                  <td className="px-4 py-3 text-gray-600">{q.currency_code}</td>
                  <td className="px-4 py-3 text-right font-medium">
                    {Number(q.total_amount).toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                        STATUS_COLORS[q.status] ?? "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {q.status.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center text-gray-500">
                    v{q.revision_number}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 text-sm text-gray-600">
            <button
              onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
              disabled={skip === 0}
              className="px-3 py-1 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-40"
            >
              Previous
            </button>
            <span>
              Showing {skip + 1}–{skip + quotations.length}
            </span>
            <button
              onClick={() => setSkip(skip + PAGE_SIZE)}
              disabled={quotations.length < PAGE_SIZE}
              className="px-3 py-1 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
