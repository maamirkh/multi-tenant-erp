"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  FiscalYearCreateRequest,
  FiscalYearResponse,
  createFiscalYear,
  getFiscalYears,
} from "@/lib/api/accounting";

const EMPTY_FORM: FiscalYearCreateRequest = {
  fiscal_year_name: "",
  start_date: "",
  end_date: "",
  base_currency_code: "USD",
  is_current: false,
};

const STATUS_BADGE: Record<string, string> = {
  SETUP: "bg-gray-100 text-gray-600",
  OPEN: "bg-green-100 text-green-800",
  CLOSED: "bg-red-100 text-red-700",
};

/**
 * Fiscal Year management page — list fiscal years + create new.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T080
 */
export default function FiscalCalendarPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";
  const [years, setYears] = useState<FiscalYearResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState<FiscalYearCreateRequest>(EMPTY_FORM);

  useEffect(() => {
    if (!companyId) return;
    load();
  }, [companyId]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getFiscalYears(companyId);
      setYears(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load fiscal years");
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await createFiscalYear(companyId, form);
      setSuccess(`Fiscal year "${form.fiscal_year_name}" created`);
      setForm(EMPTY_FORM);
      setShowForm(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create fiscal year");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Fiscal Calendar</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage fiscal years, periods, and the accounting calendar.
          </p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          {showForm ? "Cancel" : "New Fiscal Year"}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-4 rounded-md bg-green-50 p-3 text-sm text-green-700" role="status">
          {success}
        </div>
      )}

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="mb-6 rounded-md border border-gray-200 bg-white p-5 space-y-4"
        >
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Fiscal Year Name
              </label>
              <input
                required
                value={form.fiscal_year_name}
                onChange={(e) =>
                  setForm({ ...form, fiscal_year_name: e.target.value })
                }
                placeholder="FY2026"
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Base Currency
              </label>
              <input
                required
                maxLength={3}
                value={form.base_currency_code}
                onChange={(e) =>
                  setForm({
                    ...form,
                    base_currency_code: e.target.value.toUpperCase(),
                  })
                }
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm uppercase"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Start Date
              </label>
              <input
                required
                type="date"
                value={form.start_date}
                onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                End Date
              </label>
              <input
                required
                type="date"
                value={form.end_date}
                onChange={(e) => setForm({ ...form, end_date: e.target.value })}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={form.is_current ?? false}
              onChange={(e) => setForm({ ...form, is_current: e.target.checked })}
            />
            Mark as the current operating year
          </label>
          <p className="text-xs text-gray-500">
            12 monthly accounting periods will be generated automatically for
            this span.
          </p>
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? "Creating..." : "Create Fiscal Year"}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : years.length === 0 ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          No fiscal years yet. Create one to get started.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-md border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Name</th>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Span</th>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Currency</th>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Status</th>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Current</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {years.map((y) => (
                <tr key={y.id}>
                  <td className="px-4 py-2 font-medium text-gray-900">
                    {y.fiscal_year_name}
                  </td>
                  <td className="px-4 py-2 text-gray-600">
                    {y.start_date} – {y.end_date}
                  </td>
                  <td className="px-4 py-2 text-gray-600">{y.base_currency_code}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${STATUS_BADGE[y.status]}`}
                    >
                      {y.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-gray-600">
                    {y.is_current ? "★" : ""}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <Link
                      href={`/${companyId}/fiscal-calendar/${y.id}/periods`}
                      className="text-sm font-medium text-blue-600 hover:underline"
                    >
                      Periods →
                    </Link>
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
