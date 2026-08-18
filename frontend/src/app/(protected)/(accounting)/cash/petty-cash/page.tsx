"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  CashAccountResponse,
  CashReconciliationResponse,
  PettyCashVoucherResponse,
  createPettyCashVoucher,
  getCashAccounts,
  getPettyCashVouchers,
  reconcileCash,
  replenishPettyCash,
} from "@/lib/api/accounting";

const emptyVoucherForm = {
  voucher_date: new Date().toISOString().slice(0, 10),
  amount: "",
  expense_account_id: "",
  recipient_name: "",
  purpose: "",
  voucher_number: "",
};

const emptyReplenishForm = {
  bank_gl_account_id: "",
  replenishment_date: new Date().toISOString().slice(0, 10),
  reference: "",
};

const emptyReconcileForm = {
  reconciliation_date: new Date().toISOString().slice(0, 10),
  physical_count_amount: "",
  difference_account_id: "",
};

/**
 * Petty Cash management: voucher entry, replenishment, and reconciliation.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T201
 */
export default function PettyCashPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";
  const [accounts, setAccounts] = useState<CashAccountResponse[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<string>("");
  const [vouchers, setVouchers] = useState<PettyCashVoucherResponse[]>([]);
  const [selectedVoucherIds, setSelectedVoucherIds] = useState<string[]>([]);

  const [voucherForm, setVoucherForm] = useState(emptyVoucherForm);
  const [replenishForm, setReplenishForm] = useState(emptyReplenishForm);
  const [reconcileForm, setReconcileForm] = useState(emptyReconcileForm);
  const [lastReconciliation, setLastReconciliation] =
    useState<CashReconciliationResponse | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!companyId) return;
    loadAccounts();
  }, [companyId]);

  useEffect(() => {
    if (selectedAccountId) loadVouchers(selectedAccountId);
  }, [selectedAccountId]);

  async function loadAccounts() {
    setLoading(true);
    setError(null);
    try {
      const res = await getCashAccounts(companyId);
      const pettyCashAccounts = res.data.filter((a) => a.is_petty_cash);
      setAccounts(pettyCashAccounts);
      if (pettyCashAccounts[0]) setSelectedAccountId(pettyCashAccounts[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load petty cash accounts");
    } finally {
      setLoading(false);
    }
  }

  async function loadVouchers(cashAccountId: string) {
    try {
      const res = await getPettyCashVouchers(companyId, cashAccountId);
      setVouchers(res.data);
      setSelectedVoucherIds([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load petty cash vouchers");
    }
  }

  async function handleCreateVoucher() {
    if (
      !voucherForm.amount ||
      !voucherForm.expense_account_id ||
      !voucherForm.recipient_name ||
      !voucherForm.purpose ||
      !voucherForm.voucher_number
    ) {
      setError("All voucher fields except date are required.");
      return;
    }
    setError(null);
    try {
      await createPettyCashVoucher(companyId, selectedAccountId, voucherForm);
      setVoucherForm(emptyVoucherForm);
      await loadVouchers(selectedAccountId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create petty cash voucher");
    }
  }

  function toggleVoucherSelection(voucherId: string) {
    setSelectedVoucherIds((prev) =>
      prev.includes(voucherId) ? prev.filter((id) => id !== voucherId) : [...prev, voucherId]
    );
  }

  async function handleReplenish() {
    if (selectedVoucherIds.length === 0 || !replenishForm.bank_gl_account_id) {
      setError("Select at least one voucher and provide the bank GL account.");
      return;
    }
    setError(null);
    try {
      await replenishPettyCash(companyId, selectedAccountId, {
        voucher_ids: selectedVoucherIds,
        bank_gl_account_id: replenishForm.bank_gl_account_id,
        replenishment_date: replenishForm.replenishment_date,
        reference: replenishForm.reference || null,
      });
      setReplenishForm(emptyReplenishForm);
      await loadVouchers(selectedAccountId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to replenish petty cash");
    }
  }

  async function handleReconcile() {
    if (!reconcileForm.physical_count_amount) {
      setError("Physical count amount is required.");
      return;
    }
    setError(null);
    try {
      const res = await reconcileCash(companyId, selectedAccountId, {
        reconciliation_date: reconcileForm.reconciliation_date,
        physical_count_amount: reconcileForm.physical_count_amount,
        difference_account_id: reconcileForm.difference_account_id || null,
      });
      setLastReconciliation(res.data);
      setReconcileForm(emptyReconcileForm);
      await loadAccounts();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reconcile cash");
    }
  }

  const unreplenishedVouchers = vouchers.filter((v) => v.journal_entry_id === null);
  const replenishedVouchers = vouchers.filter((v) => v.journal_entry_id !== null);
  const selectedTotal = vouchers
    .filter((v) => selectedVoucherIds.includes(v.id))
    .reduce((sum, v) => sum + Number(v.amount), 0);

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Petty Cash</h1>
          <p className="mt-1 text-sm text-gray-500">
            Voucher entry, replenishment, and cash reconciliation.
          </p>
        </div>
        <Link
          href={`/${companyId}/cash`}
          className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Cash Accounts
        </Link>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : accounts.length === 0 ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          No petty cash boxes yet. Create a cash account with &quot;Petty cash box&quot; checked on
          the Cash Accounts page.
        </div>
      ) : (
        <>
          <div className="mb-6">
            <label className="block text-xs text-gray-500">Petty Cash Box</label>
            <select
              value={selectedAccountId}
              onChange={(e) => setSelectedAccountId(e.target.value)}
              className="mt-1 rounded-md border border-gray-300 px-2 py-1 text-sm"
            >
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.account_name} — Balance {a.current_balance}
                </option>
              ))}
            </select>
          </div>

          <section className="mb-8 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold text-gray-900">New Voucher</h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <input
                type="date"
                value={voucherForm.voucher_date}
                onChange={(e) => setVoucherForm({ ...voucherForm, voucher_date: e.target.value })}
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
              <input
                type="number"
                value={voucherForm.amount}
                onChange={(e) => setVoucherForm({ ...voucherForm, amount: e.target.value })}
                placeholder="Amount"
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
              <input
                type="text"
                value={voucherForm.expense_account_id}
                onChange={(e) =>
                  setVoucherForm({ ...voucherForm, expense_account_id: e.target.value })
                }
                placeholder="Expense GL account UUID"
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
              <input
                type="text"
                value={voucherForm.recipient_name}
                onChange={(e) =>
                  setVoucherForm({ ...voucherForm, recipient_name: e.target.value })
                }
                placeholder="Recipient name"
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
              <input
                type="text"
                value={voucherForm.purpose}
                onChange={(e) => setVoucherForm({ ...voucherForm, purpose: e.target.value })}
                placeholder="Purpose"
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
              <input
                type="text"
                value={voucherForm.voucher_number}
                onChange={(e) =>
                  setVoucherForm({ ...voucherForm, voucher_number: e.target.value })
                }
                placeholder="Voucher number (e.g. PCV-0001)"
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
            </div>
            <button
              onClick={handleCreateVoucher}
              className="mt-3 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Create Voucher
            </button>
          </section>

          <section className="mb-8 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold text-gray-900">
              Unreplenished Vouchers — select to replenish
            </h2>
            {unreplenishedVouchers.length === 0 ? (
              <p className="text-sm text-gray-500">No pending vouchers.</p>
            ) : (
              <div className="space-y-2">
                {unreplenishedVouchers.map((v) => (
                  <label
                    key={v.id}
                    className="flex items-center justify-between rounded-md border border-gray-100 p-2 text-sm"
                  >
                    <span className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={selectedVoucherIds.includes(v.id)}
                        onChange={() => toggleVoucherSelection(v.id)}
                      />
                      {v.voucher_number} — {v.recipient_name} — {v.purpose}
                    </span>
                    <span className="font-medium text-gray-900">{v.amount}</span>
                  </label>
                ))}
                <p className="text-xs text-gray-500">Selected total: {selectedTotal.toFixed(2)}</p>
              </div>
            )}

            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
              <input
                type="text"
                value={replenishForm.bank_gl_account_id}
                onChange={(e) =>
                  setReplenishForm({ ...replenishForm, bank_gl_account_id: e.target.value })
                }
                placeholder="Bank GL account UUID"
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
              <input
                type="date"
                value={replenishForm.replenishment_date}
                onChange={(e) =>
                  setReplenishForm({ ...replenishForm, replenishment_date: e.target.value })
                }
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
              <input
                type="text"
                value={replenishForm.reference}
                onChange={(e) => setReplenishForm({ ...replenishForm, reference: e.target.value })}
                placeholder="Reference"
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
            </div>
            <button
              onClick={handleReplenish}
              className="mt-3 rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
            >
              Replenish Selected
            </button>
          </section>

          {replenishedVouchers.length > 0 && (
            <section className="mb-8 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <h2 className="mb-3 text-sm font-semibold text-gray-900">Replenished Vouchers</h2>
              <div className="space-y-2">
                {replenishedVouchers.map((v) => (
                  <div
                    key={v.id}
                    className="flex items-center justify-between rounded-md border border-gray-100 p-2 text-sm text-gray-500"
                  >
                    <span>
                      {v.voucher_number} — {v.recipient_name} — {v.purpose}
                    </span>
                    <span>{v.amount}</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold text-gray-900">Cash Reconciliation</h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <input
                type="date"
                value={reconcileForm.reconciliation_date}
                onChange={(e) =>
                  setReconcileForm({ ...reconcileForm, reconciliation_date: e.target.value })
                }
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
              <input
                type="number"
                value={reconcileForm.physical_count_amount}
                onChange={(e) =>
                  setReconcileForm({ ...reconcileForm, physical_count_amount: e.target.value })
                }
                placeholder="Physical cash count"
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
              <input
                type="text"
                value={reconcileForm.difference_account_id}
                onChange={(e) =>
                  setReconcileForm({ ...reconcileForm, difference_account_id: e.target.value })
                }
                placeholder="Cash Short/Over GL account UUID (if a difference is expected)"
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
            </div>
            <button
              onClick={handleReconcile}
              className="mt-3 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Reconcile
            </button>

            {lastReconciliation && (
              <div className="mt-4 rounded-md bg-gray-50 p-3 text-sm text-gray-700">
                <p>GL balance: {lastReconciliation.gl_balance_amount}</p>
                <p>Physical count: {lastReconciliation.physical_count_amount}</p>
                <p>Difference: {lastReconciliation.difference}</p>
                <p>Status: {lastReconciliation.status}</p>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
