"use client";

import { useEffect, useState } from "react";
import {
  createExchangeRate,
  ExchangeRateRead,
  getExchangeRates,
} from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string };
}

/**
 * Exchange Rate Management page.
 * Lists company exchange rates and allows recording a new rate per
 * currency pair per date.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T042
 */
export default function ExchangeRatesPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const [rates, setRates] = useState<ExchangeRateRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    from_currency_code: "",
    to_currency_code: "",
    rate_date: new Date().toISOString().slice(0, 10),
    rate: "",
    rate_type: "SPOT" as "SPOT" | "AVERAGE" | "CLOSING" | "HISTORICAL",
  });

  useEffect(() => {
    if (!companyId) return;
    load();
  }, [companyId]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getExchangeRates(companyId);
      setRates(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load exchange rates");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createExchangeRate(companyId, {
        ...form,
        from_currency_code: form.from_currency_code.toUpperCase(),
        to_currency_code: form.to_currency_code.toUpperCase(),
      });
      setShowForm(false);
      setSuccess("Exchange rate recorded");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record exchange rate");
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Exchange Rates</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          {showForm ? "Cancel" : "Set Rate"}
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
          onSubmit={handleCreate}
          className="mb-6 grid grid-cols-2 gap-4 rounded-md border border-gray-200 p-4"
        >
          <div>
            <label className="block text-sm font-medium text-gray-700">From</label>
            <input
              required
              maxLength={3}
              value={form.from_currency_code}
              onChange={(e) =>
                setForm({ ...form, from_currency_code: e.target.value })
              }
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              placeholder="USD"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">To</label>
            <input
              required
              maxLength={3}
              value={form.to_currency_code}
              onChange={(e) => setForm({ ...form, to_currency_code: e.target.value })}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              placeholder="EUR"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Date</label>
            <input
              type="date"
              required
              value={form.rate_date}
              onChange={(e) => setForm({ ...form, rate_date: e.target.value })}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Rate</label>
            <input
              required
              type="number"
              step="0.0000000001"
              min="0"
              value={form.rate}
              onChange={(e) => setForm({ ...form, rate: e.target.value })}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              placeholder="0.9200"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Rate Type</label>
            <select
              value={form.rate_type}
              onChange={(e) =>
                setForm({
                  ...form,
                  rate_type: e.target.value as typeof form.rate_type,
                })
              }
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="SPOT">Spot</option>
              <option value="AVERAGE">Average</option>
              <option value="CLOSING">Closing</option>
              <option value="HISTORICAL">Historical</option>
            </select>
          </div>
          <div className="col-span-2">
            <button
              type="submit"
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Save
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : rates.length === 0 ? (
        <div className="py-8 text-center text-gray-500">No exchange rates recorded.</div>
      ) : (
        <table className="min-w-full divide-y divide-gray-200 border border-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">
                Pair
              </th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">
                Date
              </th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">
                Rate
              </th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">
                Type
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {rates.map((r) => (
              <tr key={r.id}>
                <td className="px-4 py-2 text-sm font-medium text-gray-900">
                  {r.from_currency_code} / {r.to_currency_code}
                </td>
                <td className="px-4 py-2 text-sm text-gray-700">{r.rate_date}</td>
                <td className="px-4 py-2 text-sm text-gray-700">{r.rate}</td>
                <td className="px-4 py-2 text-sm text-gray-700">{r.rate_type}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
