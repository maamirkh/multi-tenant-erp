"use client";

import { useEffect, useState } from "react";
import {
  AccountResponse,
  AccountingConfigurationRead,
  getAccounts,
  getSystemAccounts,
  setSystemAccount,
  SYSTEM_ACCOUNT_ROLES,
} from "@/lib/api/accounting";

/**
 * System Accounts configuration page.
 * Designates AR, AP, Bank, Cash, Tax, Retained Earnings, and Exchange
 * control accounts. Each role only accepts an account of the matching
 * account type (validated server-side).
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T061
 */
export default function SystemAccountsPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";
  const [config, setConfig] = useState<AccountingConfigurationRead | null>(null);
  const [accounts, setAccounts] = useState<AccountResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [savingRole, setSavingRole] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId) return;
    load();
  }, [companyId]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [configRes, accountsRes] = await Promise.all([
        getSystemAccounts(companyId),
        getAccounts(companyId),
      ]);
      setConfig(configRes.data);
      setAccounts(accountsRes.data as AccountResponse[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load system accounts");
    } finally {
      setLoading(false);
    }
  }

  async function handleAssign(role: string, accountId: string) {
    if (!accountId) return;
    setSavingRole(role);
    setError(null);
    try {
      const res = await setSystemAccount(companyId, role, accountId);
      setConfig(res.data);
      setSuccess("System account updated");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update system account");
    } finally {
      setSavingRole(null);
    }
  }

  if (loading) {
    return <div className="p-6 text-center text-gray-500">Loading...</div>;
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="mb-2 text-2xl font-semibold text-gray-900">System Accounts</h1>
      <p className="mb-6 text-sm text-gray-500">
        Designate the control accounts used by the accounting engine for automated
        postings. Each role only accepts an account of the compatible type.
      </p>

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

      {accounts.length === 0 ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          No accounts exist yet — create accounts in the Chart of Accounts first.
        </div>
      ) : (
        <div className="space-y-3 rounded-md border border-gray-200 p-4">
          {SYSTEM_ACCOUNT_ROLES.map(({ role, label }) => {
            const currentId = config
              ? (config as unknown as Record<string, string | null>)[role]
              : null;
            return (
              <div key={role} className="flex items-center justify-between gap-4">
                <label className="w-56 text-sm font-medium text-gray-700">{label}</label>
                <select
                  value={currentId ?? ""}
                  disabled={savingRole === role}
                  onChange={(e) => handleAssign(role, e.target.value)}
                  className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-100"
                >
                  <option value="">Not set</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.account_code} — {a.account_name} ({a.account_type})
                    </option>
                  ))}
                </select>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
