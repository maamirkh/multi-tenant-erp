"use client";

import { useEffect, useState } from "react";
import {
  AccountingConfigurationRead,
  getAccountingConfiguration,
  updateAccountingConfiguration,
} from "@/lib/api/accounting";

/**
 * Accounting Configuration page.
 * Manages base currency, approval thresholds, and cheque staleness policy.
 * System account assignment (AR/AP/Revenue/Expense/Tax control accounts)
 * is read-only here until the Chart of Accounts (Phase 2) exists to
 * populate an account picker.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T043
 */
export default function AccountingConfigurationPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";
  const [config, setConfig] = useState<AccountingConfigurationRead | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId) return;
    load();
  }, [companyId]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getAccountingConfiguration(companyId);
      setConfig(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load configuration");
    } finally {
      setLoading(false);
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!config) return;
    setSaving(true);
    setError(null);
    try {
      const res = await updateAccountingConfiguration(companyId, {
        base_currency_code: config.base_currency_code,
        journal_approval_threshold: config.journal_approval_threshold,
        payment_approval_threshold: config.payment_approval_threshold,
        credit_warning_threshold_pct: config.credit_warning_threshold_pct,
        cheque_stale_days: config.cheque_stale_days,
      });
      setConfig(res.data);
      setSuccess("Configuration saved");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save configuration");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="p-6 text-center text-gray-500">Loading...</div>;
  }

  if (!config) {
    return (
      <div className="p-6 text-center text-red-600">
        {error ?? "Configuration unavailable."}
      </div>
    );
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="mb-6 text-2xl font-semibold text-gray-900">
        Accounting Configuration
      </h1>

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

      <form onSubmit={handleSave} className="space-y-4 rounded-md border border-gray-200 p-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Base Currency
          </label>
          <input
            required
            maxLength={3}
            value={config.base_currency_code}
            onChange={(e) =>
              setConfig({ ...config, base_currency_code: e.target.value.toUpperCase() })
            }
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Journal Approval Threshold
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={config.journal_approval_threshold ?? ""}
              onChange={(e) =>
                setConfig({
                  ...config,
                  journal_approval_threshold: e.target.value || null,
                })
              }
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              placeholder="No threshold"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Payment Approval Threshold
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={config.payment_approval_threshold ?? ""}
              onChange={(e) =>
                setConfig({
                  ...config,
                  payment_approval_threshold: e.target.value || null,
                })
              }
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              placeholder="No threshold"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Credit Warning Threshold (%)
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              max="100"
              value={config.credit_warning_threshold_pct}
              onChange={(e) =>
                setConfig({ ...config, credit_warning_threshold_pct: e.target.value })
              }
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Cheque Stale Days
            </label>
            <input
              type="number"
              min="1"
              value={config.cheque_stale_days}
              onChange={(e) =>
                setConfig({ ...config, cheque_stale_days: Number(e.target.value) })
              }
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
        </div>

        <div className="rounded-md bg-gray-50 p-3 text-sm text-gray-500">
          System control account assignment (AR, AP, Revenue, Expense, Tax) will
          be configurable here once the Chart of Accounts is available (Phase 2).
        </div>

        <button
          type="submit"
          disabled={saving}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save Configuration"}
        </button>
      </form>
    </div>
  );
}
