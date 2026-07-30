"use client";

/**
 * SupplierFinancialPanel — Phase 2 Supplier Enrichment (T068)
 *
 * Displays and manages:
 *   - Credit limit with enforcement mode badge
 *   - Bank details list (Finance Manager note: currently open; RBAC enforced in Epic 7)
 *   - Supplier performance rating with manual override indicator
 */

import { useEffect, useState } from "react";
import {
  getCreditLimit,
  setCreditLimit,
  getBankDetails,
  addBankDetails,
  deleteBankDetails,
  getSupplierRating,
  setRatingOverride,
  setPreferredSupplier,
  CreditLimitRead,
  BankDetailsRead,
  BankDetailsCreate,
  SupplierRatingRead,
} from "@/lib/api/purchase";

interface Props {
  companyId: string;
  supplierId: string;
  isPreferred: boolean;
  onPreferredChange?: (val: boolean) => void;
}

const ENFORCEMENT_BADGE: Record<string, string> = {
  BLOCK: "bg-red-100 text-red-700",
  WARN: "bg-yellow-100 text-yellow-700",
  OFF: "bg-gray-100 text-gray-500",
};

export default function SupplierFinancialPanel({
  companyId,
  supplierId,
  isPreferred,
  onPreferredChange,
}: Props) {
  const [creditLimit, setCreditLimitData] = useState<CreditLimitRead | null>(null);
  const [bankDetails, setBankDetails] = useState<BankDetailsRead[]>([]);
  const [rating, setRating] = useState<SupplierRatingRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Credit limit form
  const [clForm, setClForm] = useState({
    amount: "",
    currency: "USD",
    mode: "WARN" as "BLOCK" | "WARN" | "OFF",
  });
  const [showClForm, setShowClForm] = useState(false);

  // Bank detail form
  const [showBdForm, setShowBdForm] = useState(false);
  const [bdForm, setBdForm] = useState<BankDetailsCreate>({
    bank_name: "",
    account_name: "",
    account_number: "",
    bank_country: "",
    currency_code: "USD",
    is_primary: false,
  });

  // Rating override form
  const [showOverrideForm, setShowOverrideForm] = useState(false);
  const [overrideScore, setOverrideScore] = useState("");
  const [overrideReason, setOverrideReason] = useState("");

  useEffect(() => {
    loadAll();
  }, [companyId, supplierId]);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [cl, bd, rt] = await Promise.allSettled([
        getCreditLimit(companyId, supplierId).catch(() => null),
        getBankDetails(companyId, supplierId),
        getSupplierRating(companyId, supplierId).catch(() => null),
      ]);
      if (cl.status === "fulfilled" && cl.value) setCreditLimitData(cl.value.data);
      if (bd.status === "fulfilled") setBankDetails(bd.value.data);
      if (rt.status === "fulfilled" && rt.value) setRating(rt.value.data);
    } catch {
      setError("Failed to load financial data");
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveCreditLimit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await setCreditLimit(companyId, supplierId, {
        credit_limit_amount: parseFloat(clForm.amount),
        currency_code: clForm.currency,
        enforcement_mode: clForm.mode,
      });
      setCreditLimitData(res.data);
      setShowClForm(false);
    } catch {
      setError("Failed to save credit limit");
    } finally {
      setSaving(false);
    }
  }

  async function handleAddBankDetail(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await addBankDetails(companyId, supplierId, bdForm);
      setBankDetails((prev) => [...prev, res.data]);
      setShowBdForm(false);
      setBdForm({ bank_name: "", account_name: "", account_number: "", bank_country: "", currency_code: "USD", is_primary: false });
    } catch {
      setError("Failed to add bank details");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteBd(bdId: string) {
    if (!confirm("Remove this bank account?")) return;
    setSaving(true);
    try {
      await deleteBankDetails(companyId, supplierId, bdId);
      setBankDetails((prev) => prev.filter((b) => b.id !== bdId));
    } catch {
      setError("Failed to remove bank detail");
    } finally {
      setSaving(false);
    }
  }

  async function handleRatingOverride(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await setRatingOverride(companyId, supplierId, {
        manual_override_score: parseFloat(overrideScore),
        manual_override_reason: overrideReason || undefined,
      });
      setRating(res.data);
      setShowOverrideForm(false);
      setOverrideScore("");
      setOverrideReason("");
    } catch {
      setError("Failed to set rating override");
    } finally {
      setSaving(false);
    }
  }

  async function handleTogglePreferred() {
    setSaving(true);
    try {
      const res = await setPreferredSupplier(companyId, supplierId, !isPreferred);
      onPreferredChange?.(res.data.is_preferred);
    } catch {
      setError("Failed to update preferred status");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="p-4 text-sm text-gray-500">Loading financial data...</div>;

  const effectiveScore = rating?.manual_override_score ?? rating?.composite_score ?? null;

  return (
    <div className="space-y-6">
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Preferred Supplier Toggle */}
      <div className="flex items-center justify-between p-4 border rounded-lg bg-gray-50">
        <div>
          <p className="text-sm font-medium text-gray-900">Preferred Supplier</p>
          <p className="text-xs text-gray-500">Mark this supplier as preferred for procurement</p>
        </div>
        <button
          onClick={handleTogglePreferred}
          disabled={saving}
          className={`px-3 py-1.5 text-sm rounded font-medium disabled:opacity-50 ${
            isPreferred
              ? "bg-blue-100 text-blue-700 hover:bg-blue-200"
              : "bg-gray-200 text-gray-600 hover:bg-gray-300"
          }`}
        >
          {isPreferred ? "Preferred" : "Set as Preferred"}
        </button>
      </div>

      {/* Credit Limit */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-900">Credit Limit</h3>
          <button
            onClick={() => {
              setClForm({
                amount: creditLimit ? creditLimit.credit_limit_amount : "",
                currency: creditLimit?.currency_code ?? "USD",
                mode: (creditLimit?.enforcement_mode ?? "WARN") as "BLOCK" | "WARN" | "OFF",
              });
              setShowClForm((v) => !v);
            }}
            className="text-xs text-blue-600 hover:underline"
          >
            {showClForm ? "Cancel" : creditLimit ? "Edit" : "Set Limit"}
          </button>
        </div>

        {creditLimit && !showClForm && (
          <div className="flex items-center gap-3 p-3 border rounded">
            <span className="text-lg font-semibold text-gray-900">
              {creditLimit.currency_code} {parseFloat(creditLimit.credit_limit_amount).toLocaleString()}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded font-medium ${ENFORCEMENT_BADGE[creditLimit.enforcement_mode]}`}>
              {creditLimit.enforcement_mode}
            </span>
          </div>
        )}

        {!creditLimit && !showClForm && (
          <p className="text-sm text-gray-400 italic">No credit limit set — all POs allowed.</p>
        )}

        {showClForm && (
          <form onSubmit={handleSaveCreditLimit} className="border rounded p-4 space-y-3">
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <label className="block text-xs font-medium text-gray-700 mb-1">Limit Amount</label>
                <input
                  type="number" min={0} step="0.01" required
                  value={clForm.amount}
                  onChange={(e) => setClForm({ ...clForm, amount: e.target.value })}
                  className="w-full border rounded px-3 py-1.5 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Currency</label>
                <input
                  maxLength={3} required
                  value={clForm.currency}
                  onChange={(e) => setClForm({ ...clForm, currency: e.target.value.toUpperCase() })}
                  className="w-full border rounded px-3 py-1.5 text-sm"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Enforcement Mode</label>
              <select
                value={clForm.mode}
                onChange={(e) => setClForm({ ...clForm, mode: e.target.value as "BLOCK" | "WARN" | "OFF" })}
                className="w-full border rounded px-3 py-1.5 text-sm"
              >
                <option value="BLOCK">BLOCK — reject PO if exceeded</option>
                <option value="WARN">WARN — alert but allow PO</option>
                <option value="OFF">OFF — skip credit check</option>
              </select>
            </div>
            <button type="submit" disabled={saving}
              className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50">
              Save
            </button>
          </form>
        )}
      </section>

      {/* Supplier Rating */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-900">Performance Rating</h3>
          {rating && (
            <button onClick={() => setShowOverrideForm((v) => !v)} className="text-xs text-blue-600 hover:underline">
              {showOverrideForm ? "Cancel" : "Override"}
            </button>
          )}
        </div>

        {rating ? (
          <div className="border rounded p-4 space-y-2">
            <div className="flex items-center gap-3">
              <span className="text-3xl font-bold text-gray-900">{effectiveScore}</span>
              <span className="text-sm text-gray-500">/ 10</span>
              {rating.manual_override_score && (
                <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded">Manual Override</span>
              )}
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs text-gray-600">
              <div>On-Time: <span className="font-medium">{rating.on_time_rate}%</span></div>
              <div>Fill Rate: <span className="font-medium">{rating.fill_rate}%</span></div>
              <div>Rejection: <span className="font-medium">{rating.rejection_rate}%</span></div>
            </div>
            {rating.manual_override_reason && (
              <p className="text-xs text-gray-400 italic">{rating.manual_override_reason}</p>
            )}
          </div>
        ) : (
          <p className="text-sm text-gray-400 italic">No rating computed yet.</p>
        )}

        {showOverrideForm && (
          <form onSubmit={handleRatingOverride} className="border rounded p-4 mt-3 space-y-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Override Score (0–10)</label>
              <input
                type="number" min={0} max={10} step="0.1" required
                value={overrideScore}
                onChange={(e) => setOverrideScore(e.target.value)}
                className="w-full border rounded px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Reason</label>
              <input
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                className="w-full border rounded px-3 py-1.5 text-sm"
              />
            </div>
            <button type="submit" disabled={saving}
              className="px-3 py-1.5 bg-orange-600 text-white rounded text-sm hover:bg-orange-700 disabled:opacity-50">
              Apply Override
            </button>
          </form>
        )}
      </section>

      {/* Bank Details */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-900">Bank Details</h3>
          <button onClick={() => setShowBdForm((v) => !v)} className="text-xs text-blue-600 hover:underline">
            {showBdForm ? "Cancel" : "+ Add Account"}
          </button>
        </div>

        {bankDetails.length > 0 ? (
          <div className="space-y-2">
            {bankDetails.map((bd) => (
              <div key={bd.id} className="border rounded p-3 text-sm flex justify-between items-start">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{bd.bank_name}</span>
                    {bd.is_primary && (
                      <span className="text-xs bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded">Primary</span>
                    )}
                  </div>
                  <p className="text-gray-500 text-xs">{bd.account_name} — {bd.account_number}</p>
                  <p className="text-gray-400 text-xs">{bd.bank_country} · {bd.currency_code}</p>
                </div>
                <button
                  onClick={() => handleDeleteBd(bd.id)}
                  disabled={saving}
                  className="text-xs text-red-600 hover:underline disabled:opacity-50"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-400 italic">No bank accounts on file.</p>
        )}

        {showBdForm && (
          <form onSubmit={handleAddBankDetail} className="border rounded p-4 mt-3 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Bank Name *</label>
                <input required value={bdForm.bank_name}
                  onChange={(e) => setBdForm({ ...bdForm, bank_name: e.target.value })}
                  className="w-full border rounded px-3 py-1.5 text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Account Name *</label>
                <input required value={bdForm.account_name}
                  onChange={(e) => setBdForm({ ...bdForm, account_name: e.target.value })}
                  className="w-full border rounded px-3 py-1.5 text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Account Number *</label>
                <input required value={bdForm.account_number}
                  onChange={(e) => setBdForm({ ...bdForm, account_number: e.target.value })}
                  className="w-full border rounded px-3 py-1.5 text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Bank Country (ISO) *</label>
                <input required maxLength={2} value={bdForm.bank_country}
                  onChange={(e) => setBdForm({ ...bdForm, bank_country: e.target.value.toUpperCase() })}
                  className="w-full border rounded px-3 py-1.5 text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Currency</label>
                <input maxLength={3} value={bdForm.currency_code}
                  onChange={(e) => setBdForm({ ...bdForm, currency_code: e.target.value.toUpperCase() })}
                  className="w-full border rounded px-3 py-1.5 text-sm" />
              </div>
              <div className="flex items-center gap-2 pt-5">
                <input type="checkbox" id="is_primary" checked={bdForm.is_primary}
                  onChange={(e) => setBdForm({ ...bdForm, is_primary: e.target.checked })} />
                <label htmlFor="is_primary" className="text-xs text-gray-700">Primary account</label>
              </div>
            </div>
            <button type="submit" disabled={saving}
              className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50">
              Add Account
            </button>
          </form>
        )}
      </section>
    </div>
  );
}
