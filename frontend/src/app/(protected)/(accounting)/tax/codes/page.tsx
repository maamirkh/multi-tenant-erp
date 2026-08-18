"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  TaxCodeResponse,
  TaxRateResponse,
  createTaxCode,
  createTaxRate,
  getTaxCodes,
  getTaxRates,
} from "@/lib/api/accounting";

const emptyForm = {
  tax_code: "",
  tax_name: "",
  tax_type: "VAT",
  applicability: "BOTH",
  gl_account_id: "",
  is_input_tax_recoverable: false,
  country_code: "",
};

const emptyRateForm = {
  effective_from: new Date().toISOString().slice(0, 10),
  effective_to: "",
  rate: "",
  rounding_rule: "HALF_UP",
};

/**
 * Tax Code management: list, create, and rate-history management.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T239
 */
export default function TaxCodesPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";
  const [codes, setCodes] = useState<TaxCodeResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);

  const [selectedCodeId, setSelectedCodeId] = useState<string | null>(null);
  const [rates, setRates] = useState<TaxRateResponse[]>([]);
  const [rateForm, setRateForm] = useState(emptyRateForm);

  useEffect(() => {
    if (!companyId) return;
    load();
  }, [companyId]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getTaxCodes(companyId);
      setCodes(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load tax codes");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    if (!form.tax_code || !form.tax_name || !form.gl_account_id) {
      setError("Tax code, name, and GL account are required.");
      return;
    }
    setError(null);
    try {
      await createTaxCode(companyId, {
        ...form,
        country_code: form.country_code || null,
      });
      setForm(emptyForm);
      setShowForm(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create tax code");
    }
  }

  async function handleViewRates(taxCodeId: string) {
    setSelectedCodeId(taxCodeId === selectedCodeId ? null : taxCodeId);
    setError(null);
    if (taxCodeId === selectedCodeId) return;
    try {
      const res = await getTaxRates(companyId, taxCodeId);
      setRates(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load tax rates");
    }
  }

  async function handleAddRate(taxCodeId: string) {
    if (!rateForm.rate) {
      setError("Rate is required.");
      return;
    }
    setError(null);
    try {
      await createTaxRate(companyId, taxCodeId, {
        effective_from: rateForm.effective_from,
        effective_to: rateForm.effective_to || null,
        rate: rateForm.rate,
        rounding_rule: rateForm.rounding_rule,
      });
      setRateForm(emptyRateForm);
      const res = await getTaxRates(companyId, taxCodeId);
      setRates(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add tax rate");
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Tax Codes</h1>
          <p className="mt-1 text-sm text-gray-500">
            Configure tax codes and their effective-dated rate history.
          </p>
        </div>
        <div className="flex gap-3">
          <Link
            href={`/${companyId}/tax/groups`}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Tax Groups
          </Link>
          <Link
            href={`/${companyId}/reports/tax-summary`}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Tax Summary Report
          </Link>
          <button
            onClick={() => setShowForm((v) => !v)}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            New Tax Code
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {showForm && (
        <div className="mb-6 grid grid-cols-1 gap-4 rounded-lg border border-gray-200 bg-white p-4 shadow-sm sm:grid-cols-3">
          <input
            type="text"
            value={form.tax_code}
            onChange={(e) => setForm({ ...form, tax_code: e.target.value })}
            placeholder="Code (e.g. VAT-15)"
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
          <input
            type="text"
            value={form.tax_name}
            onChange={(e) => setForm({ ...form, tax_name: e.target.value })}
            placeholder="Name"
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
          <select
            value={form.tax_type}
            onChange={(e) => setForm({ ...form, tax_type: e.target.value })}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          >
            <option value="SALES_TAX">Sales Tax</option>
            <option value="VAT">VAT</option>
            <option value="GST">GST</option>
            <option value="WITHHOLDING">Withholding</option>
            <option value="COMPOUND">Compound</option>
            <option value="EXEMPT">Exempt</option>
            <option value="ZERO_RATED">Zero-Rated</option>
            <option value="OUT_OF_SCOPE">Out of Scope</option>
          </select>
          <select
            value={form.applicability}
            onChange={(e) => setForm({ ...form, applicability: e.target.value })}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          >
            <option value="SALES">Sales</option>
            <option value="PURCHASES">Purchases</option>
            <option value="BOTH">Both</option>
          </select>
          <input
            type="text"
            value={form.gl_account_id}
            onChange={(e) => setForm({ ...form, gl_account_id: e.target.value })}
            placeholder="Tax GL account UUID"
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
          <input
            type="text"
            value={form.country_code}
            onChange={(e) => setForm({ ...form, country_code: e.target.value })}
            placeholder="Country code (e.g. GB)"
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={form.is_input_tax_recoverable}
              onChange={(e) => setForm({ ...form, is_input_tax_recoverable: e.target.checked })}
            />
            Input tax recoverable
          </label>
          <div className="sm:col-span-3">
            <button
              onClick={handleCreate}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Create
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : codes.length === 0 ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          No tax codes yet.
        </div>
      ) : (
        <div className="space-y-3">
          {codes.map((code) => (
            <div key={code.id} className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-gray-900">
                    {code.tax_code} — {code.tax_name}
                  </p>
                  <p className="text-xs text-gray-500">
                    {code.tax_type} · {code.applicability}
                    {code.is_input_tax_recoverable && " · Recoverable"}
                    {!code.is_active && " · Inactive"}
                  </p>
                </div>
                <button
                  onClick={() => handleViewRates(code.id)}
                  className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                >
                  Rate History
                </button>
              </div>

              {selectedCodeId === code.id && (
                <div className="mt-4 border-t border-gray-100 pt-4">
                  {rates.length === 0 ? (
                    <p className="mb-3 text-sm text-gray-500">No rates configured yet.</p>
                  ) : (
                    <table className="mb-3 min-w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-gray-500">
                          <th className="py-1 pr-4">From</th>
                          <th className="py-1 pr-4">To</th>
                          <th className="py-1 pr-4">Rate</th>
                          <th className="py-1 pr-4">Rounding</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {rates.map((rate) => (
                          <tr key={rate.id}>
                            <td className="py-1 pr-4">{rate.effective_from}</td>
                            <td className="py-1 pr-4">{rate.effective_to ?? "Ongoing"}</td>
                            <td className="py-1 pr-4">{rate.rate}%</td>
                            <td className="py-1 pr-4">{rate.rounding_rule}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-5">
                    <input
                      type="date"
                      value={rateForm.effective_from}
                      onChange={(e) =>
                        setRateForm({ ...rateForm, effective_from: e.target.value })
                      }
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                    />
                    <input
                      type="date"
                      value={rateForm.effective_to}
                      onChange={(e) => setRateForm({ ...rateForm, effective_to: e.target.value })}
                      placeholder="Effective to (optional)"
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                    />
                    <input
                      type="number"
                      value={rateForm.rate}
                      onChange={(e) => setRateForm({ ...rateForm, rate: e.target.value })}
                      placeholder="Rate %"
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                    />
                    <select
                      value={rateForm.rounding_rule}
                      onChange={(e) =>
                        setRateForm({ ...rateForm, rounding_rule: e.target.value })
                      }
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                    >
                      <option value="HALF_UP">Half Up</option>
                      <option value="HALF_EVEN">Half Even</option>
                      <option value="DOWN">Down</option>
                      <option value="UP">Up</option>
                    </select>
                    <button
                      onClick={() => handleAddRate(code.id)}
                      className="rounded-md bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700"
                    >
                      Add Rate
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
