"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  BankAccountResponse,
  createBankAccount,
  getBankAccounts,
} from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string };
}

const emptyForm = {
  bank_name: "",
  branch_name: "",
  account_number: "",
  iban: "",
  currency_code: "USD",
  gl_account_id: "",
  opening_balance: "0",
};

/**
 * Bank Accounts list and management page.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T187
 */
export default function BankAccountsPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const [accounts, setAccounts] = useState<BankAccountResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);

  useEffect(() => {
    if (!companyId) return;
    load();
  }, [companyId]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getBankAccounts(companyId);
      setAccounts(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load bank accounts");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    if (!form.bank_name || !form.account_number || !form.gl_account_id) {
      setError("Bank name, account number, and GL account ID are required.");
      return;
    }
    setError(null);
    try {
      await createBankAccount(companyId, {
        ...form,
        branch_name: form.branch_name || null,
        iban: form.iban || null,
      });
      setForm(emptyForm);
      setShowForm(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create bank account");
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Bank Accounts</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage company bank accounts and their GL account linkage.
          </p>
        </div>
        <div className="flex gap-3">
          <Link
            href={`/${companyId}/banking/cheques`}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cheque Register
          </Link>
          <button
            onClick={() => setShowForm((v) => !v)}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            New Bank Account
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
            value={form.bank_name}
            onChange={(e) => setForm({ ...form, bank_name: e.target.value })}
            placeholder="Bank name"
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
          <input
            type="text"
            value={form.branch_name}
            onChange={(e) => setForm({ ...form, branch_name: e.target.value })}
            placeholder="Branch name"
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
          <input
            type="text"
            value={form.account_number}
            onChange={(e) => setForm({ ...form, account_number: e.target.value })}
            placeholder="Account number"
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
          <input
            type="text"
            value={form.iban}
            onChange={(e) => setForm({ ...form, iban: e.target.value })}
            placeholder="IBAN (optional)"
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
          <input
            type="text"
            value={form.currency_code}
            onChange={(e) => setForm({ ...form, currency_code: e.target.value })}
            placeholder="Currency (e.g. USD)"
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
          <input
            type="text"
            value={form.gl_account_id}
            onChange={(e) => setForm({ ...form, gl_account_id: e.target.value })}
            placeholder="GL Account UUID"
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
          <input
            type="text"
            value={form.opening_balance}
            onChange={(e) => setForm({ ...form, opening_balance: e.target.value })}
            placeholder="Opening balance"
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
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
      ) : accounts.length === 0 ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          No bank accounts yet.
        </div>
      ) : (
        <div className="space-y-3">
          {accounts.map((account) => (
            <div
              key={account.id}
              className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
            >
              <div>
                <p className="text-sm font-semibold text-gray-900">
                  {account.bank_name}
                  {account.branch_name ? ` — ${account.branch_name}` : ""}
                </p>
                <p className="text-xs text-gray-500">
                  {account.account_number} · {account.currency_code}
                  {!account.is_active && " · Inactive"}
                </p>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-sm font-medium text-gray-900">
                  {account.current_gl_balance}
                </span>
                <Link
                  href={`/${companyId}/banking/${account.id}/reconcile`}
                  className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                >
                  Reconcile
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
