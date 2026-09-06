"use client";

import { useState, useEffect } from "react";
import {
  AccountCreateRequest,
  AccountResponse,
  AccountType,
} from "@/lib/api/accounting";

interface AccountFormModalProps {
  open: boolean;
  account?: AccountResponse | null;
  onClose: () => void;
  onSubmit: (data: AccountCreateRequest) => Promise<void>;
}

const ACCOUNT_TYPES: AccountType[] = ["ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"];

const EMPTY_FORM: AccountCreateRequest = {
  account_code: "",
  account_name: "",
  account_type: "ASSET",
  is_leaf: true,
  requires_cost_center: false,
  is_bank_account: false,
  is_cash_account: false,
};

/**
 * AccountFormModal — create/edit modal for a Chart of Accounts entry.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T060
 */
export default function AccountFormModal({
  open,
  account,
  onClose,
  onSubmit,
}: AccountFormModalProps) {
  const [form, setForm] = useState<AccountCreateRequest>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (account) {
      setForm({
        account_code: account.account_code,
        account_name: account.account_name,
        account_type: account.account_type,
        is_leaf: account.is_leaf,
        currency_code: account.currency_code,
        requires_cost_center: account.requires_cost_center,
        is_bank_account: account.is_bank_account,
        is_cash_account: account.is_cash_account,
        tax_category: account.tax_category,
        notes: account.notes,
      });
    } else {
      setForm(EMPTY_FORM);
    }
    setError(null);
  }, [account, open]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(form);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save account");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      role="dialog"
      aria-modal="true"
      aria-labelledby="account-form-title"
    >
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <h2 id="account-form-title" className="mb-4 text-lg font-semibold text-gray-900">
          {account ? "Edit Account" : "New Account"}
        </h2>

        {error && (
          <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Account Code
              </label>
              <input
                required
                disabled={!!account}
                value={form.account_code}
                onChange={(e) => setForm({ ...form, account_code: e.target.value })}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-100"
                placeholder="1000"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Account Type
              </label>
              <select
                required
                disabled={!!account}
                value={form.account_type}
                onChange={(e) =>
                  setForm({ ...form, account_type: e.target.value as AccountType })
                }
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-100"
              >
                {ACCOUNT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Account Name
            </label>
            <input
              required
              value={form.account_name}
              onChange={(e) => setForm({ ...form, account_name: e.target.value })}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              placeholder="Cash on Hand"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={form.is_leaf ?? true}
                onChange={(e) => setForm({ ...form, is_leaf: e.target.checked })}
              />
              Leaf account (accepts postings)
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={form.requires_cost_center ?? false}
                onChange={(e) =>
                  setForm({ ...form, requires_cost_center: e.target.checked })
                }
              />
              Requires cost center
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={form.is_bank_account ?? false}
                onChange={(e) => setForm({ ...form, is_bank_account: e.target.checked })}
              />
              Bank account
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={form.is_cash_account ?? false}
                onChange={(e) => setForm({ ...form, is_cash_account: e.target.checked })}
              />
              Cash account
            </label>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Notes</label>
            <textarea
              value={form.notes ?? ""}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              rows={2}
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? "Saving..." : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
