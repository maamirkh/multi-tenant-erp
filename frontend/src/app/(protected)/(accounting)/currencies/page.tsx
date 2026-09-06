"use client";

import { useEffect, useState } from "react";
import {
  createCurrency,
  CurrencyRead,
  getCurrencies,
} from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string };
}

/**
 * Currency Management page.
 * Lists the global currency registry and allows creating new currencies.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T041
 */
export default function CurrenciesPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const [currencies, setCurrencies] = useState<CurrencyRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    iso_code: "",
    name: "",
    symbol: "",
    decimal_places: 2,
  });

  useEffect(() => {
    if (!companyId) return;
    load();
  }, [companyId]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getCurrencies(companyId);
      setCurrencies(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load currencies");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createCurrency(companyId, {
        ...form,
        iso_code: form.iso_code.toUpperCase(),
      });
      setShowForm(false);
      setForm({ iso_code: "", name: "", symbol: "", decimal_places: 2 });
      setSuccess("Currency created");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create currency");
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Currencies</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          {showForm ? "Cancel" : "Add Currency"}
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
            <label className="block text-sm font-medium text-gray-700">ISO Code</label>
            <input
              required
              maxLength={3}
              value={form.iso_code}
              onChange={(e) => setForm({ ...form, iso_code: e.target.value })}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              placeholder="USD"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Name</label>
            <input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              placeholder="US Dollar"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Symbol</label>
            <input
              required
              value={form.symbol}
              onChange={(e) => setForm({ ...form, symbol: e.target.value })}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              placeholder="$"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Decimal Places
            </label>
            <input
              type="number"
              min={0}
              value={form.decimal_places}
              onChange={(e) =>
                setForm({ ...form, decimal_places: Number(e.target.value) })
              }
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
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
      ) : currencies.length === 0 ? (
        <div className="py-8 text-center text-gray-500">No currencies found.</div>
      ) : (
        <table className="min-w-full divide-y divide-gray-200 border border-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">
                Code
              </th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">
                Name
              </th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">
                Symbol
              </th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">
                Decimals
              </th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-gray-500">
                Status
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {currencies.map((c) => (
              <tr key={c.id}>
                <td className="px-4 py-2 text-sm font-medium text-gray-900">
                  {c.iso_code}
                </td>
                <td className="px-4 py-2 text-sm text-gray-700">{c.name}</td>
                <td className="px-4 py-2 text-sm text-gray-700">{c.symbol}</td>
                <td className="px-4 py-2 text-sm text-gray-700">{c.decimal_places}</td>
                <td className="px-4 py-2 text-sm">
                  <span
                    className={`inline-flex rounded-full px-2 text-xs font-semibold ${
                      c.is_active
                        ? "bg-green-100 text-green-800"
                        : "bg-gray-100 text-gray-500"
                    }`}
                  >
                    {c.is_active ? "Active" : "Inactive"}
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
