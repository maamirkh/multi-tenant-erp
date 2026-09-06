"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  CashAccountResponse,
  CashBookResponse,
  createCashAccount,
  getCashAccounts,
  getCashBook,
  recordCashPayment,
  recordCashReceipt,
} from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string };
}

const emptyAccountForm = {
  account_name: "",
  currency_code: "USD",
  gl_account_id: "",
  is_petty_cash: false,
  float_amount: "0",
};

const emptyReceiptForm = {
  amount: "",
  contra_account_id: "",
  receipt_date: new Date().toISOString().slice(0, 10),
  reference: "",
  description: "",
};

const emptyPaymentForm = {
  amount: "",
  contra_account_id: "",
  payment_date: new Date().toISOString().slice(0, 10),
  reference: "",
  description: "",
};

/**
 * Cash Accounts list, cash receipt/payment entry, and Cash Book viewer.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T200
 */
export default function CashAccountsPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const [accounts, setAccounts] = useState<CashAccountResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyAccountForm);

  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null);
  const [receiptForm, setReceiptForm] = useState(emptyReceiptForm);
  const [paymentForm, setPaymentForm] = useState(emptyPaymentForm);

  const [fromDate, setFromDate] = useState(
    new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10)
  );
  const [toDate, setToDate] = useState(new Date().toISOString().slice(0, 10));
  const [cashBook, setCashBook] = useState<CashBookResponse | null>(null);

  useEffect(() => {
    if (!companyId) return;
    load();
  }, [companyId]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getCashAccounts(companyId);
      setAccounts(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load cash accounts");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    if (!form.account_name || !form.gl_account_id) {
      setError("Account name and GL account ID are required.");
      return;
    }
    setError(null);
    try {
      await createCashAccount(companyId, form);
      setForm(emptyAccountForm);
      setShowForm(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create cash account");
    }
  }

  async function handleRecordReceipt(cashAccountId: string) {
    if (!receiptForm.amount || !receiptForm.contra_account_id) {
      setError("Amount and contra account are required for a receipt.");
      return;
    }
    setError(null);
    try {
      await recordCashReceipt(companyId, cashAccountId, {
        ...receiptForm,
        reference: receiptForm.reference || null,
        description: receiptForm.description || null,
      });
      setReceiptForm(emptyReceiptForm);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record cash receipt");
    }
  }

  async function handleRecordPayment(cashAccountId: string) {
    if (!paymentForm.amount || !paymentForm.contra_account_id) {
      setError("Amount and contra account are required for a payment.");
      return;
    }
    setError(null);
    try {
      await recordCashPayment(companyId, cashAccountId, {
        ...paymentForm,
        reference: paymentForm.reference || null,
        description: paymentForm.description || null,
      });
      setPaymentForm(emptyPaymentForm);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record cash payment");
    }
  }

  async function handleViewCashBook(cashAccountId: string) {
    setSelectedAccountId(cashAccountId);
    setError(null);
    try {
      const res = await getCashBook(companyId, cashAccountId, fromDate, toDate);
      setCashBook(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load cash book");
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Cash Accounts</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage tills and petty cash boxes, record receipts and payments.
          </p>
        </div>
        <div className="flex gap-3">
          <Link
            href={`/${companyId}/cash/petty-cash`}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Petty Cash
          </Link>
          <button
            onClick={() => setShowForm((v) => !v)}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            New Cash Account
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
            value={form.account_name}
            onChange={(e) => setForm({ ...form, account_name: e.target.value })}
            placeholder="Account name (e.g. Main Till)"
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
            value={form.float_amount}
            onChange={(e) => setForm({ ...form, float_amount: e.target.value })}
            placeholder="Float amount (petty cash only)"
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={form.is_petty_cash}
              onChange={(e) => setForm({ ...form, is_petty_cash: e.target.checked })}
            />
            Petty cash box
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
      ) : accounts.length === 0 ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          No cash accounts yet.
        </div>
      ) : (
        <div className="space-y-3">
          {accounts.map((account) => (
            <div
              key={account.id}
              className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-gray-900">
                    {account.account_name}
                    {account.is_petty_cash ? " (Petty Cash)" : ""}
                  </p>
                  <p className="text-xs text-gray-500">
                    {account.currency_code}
                    {!account.is_active && " · Inactive"}
                  </p>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-sm font-medium text-gray-900">
                    {account.current_balance}
                  </span>
                  <button
                    onClick={() => handleViewCashBook(account.id)}
                    className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                  >
                    Cash Book
                  </button>
                </div>
              </div>

              {selectedAccountId === account.id && (
                <div className="mt-4 space-y-4 border-t border-gray-100 pt-4">
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-5">
                    <input
                      type="number"
                      value={receiptForm.amount}
                      onChange={(e) => setReceiptForm({ ...receiptForm, amount: e.target.value })}
                      placeholder="Receipt amount"
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                    />
                    <input
                      type="text"
                      value={receiptForm.contra_account_id}
                      onChange={(e) =>
                        setReceiptForm({ ...receiptForm, contra_account_id: e.target.value })
                      }
                      placeholder="Contra GL account UUID"
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                    />
                    <input
                      type="date"
                      value={receiptForm.receipt_date}
                      onChange={(e) =>
                        setReceiptForm({ ...receiptForm, receipt_date: e.target.value })
                      }
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                    />
                    <input
                      type="text"
                      value={receiptForm.reference}
                      onChange={(e) => setReceiptForm({ ...receiptForm, reference: e.target.value })}
                      placeholder="Reference"
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                    />
                    <button
                      onClick={() => handleRecordReceipt(account.id)}
                      className="rounded-md bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700"
                    >
                      Record Receipt
                    </button>
                  </div>

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-5">
                    <input
                      type="number"
                      value={paymentForm.amount}
                      onChange={(e) => setPaymentForm({ ...paymentForm, amount: e.target.value })}
                      placeholder="Payment amount"
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                    />
                    <input
                      type="text"
                      value={paymentForm.contra_account_id}
                      onChange={(e) =>
                        setPaymentForm({ ...paymentForm, contra_account_id: e.target.value })
                      }
                      placeholder="Contra GL account UUID"
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                    />
                    <input
                      type="date"
                      value={paymentForm.payment_date}
                      onChange={(e) =>
                        setPaymentForm({ ...paymentForm, payment_date: e.target.value })
                      }
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                    />
                    <input
                      type="text"
                      value={paymentForm.reference}
                      onChange={(e) => setPaymentForm({ ...paymentForm, reference: e.target.value })}
                      placeholder="Reference"
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                    />
                    <button
                      onClick={() => handleRecordPayment(account.id)}
                      className="rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700"
                    >
                      Record Payment
                    </button>
                  </div>

                  <div className="flex items-end gap-3">
                    <div>
                      <label className="block text-xs text-gray-500">From</label>
                      <input
                        type="date"
                        value={fromDate}
                        onChange={(e) => setFromDate(e.target.value)}
                        className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500">To</label>
                      <input
                        type="date"
                        value={toDate}
                        onChange={(e) => setToDate(e.target.value)}
                        className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                      />
                    </div>
                    <button
                      onClick={() => handleViewCashBook(account.id)}
                      className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                    >
                      Refresh Cash Book
                    </button>
                  </div>

                  {cashBook && (
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200 text-sm">
                        <thead>
                          <tr className="text-left text-xs text-gray-500">
                            <th className="py-1 pr-4">Date</th>
                            <th className="py-1 pr-4">Type</th>
                            <th className="py-1 pr-4">Reference</th>
                            <th className="py-1 pr-4">Description</th>
                            <th className="py-1 pr-4 text-right">Amount</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          <tr className="text-gray-500">
                            <td className="py-1 pr-4" colSpan={4}>
                              Opening balance
                            </td>
                            <td className="py-1 pr-4 text-right">{cashBook.opening_balance}</td>
                          </tr>
                          {cashBook.transactions.length === 0 ? (
                            <tr>
                              <td className="py-2 text-center text-gray-400" colSpan={5}>
                                No transactions in this range.
                              </td>
                            </tr>
                          ) : (
                            cashBook.transactions.map((row) => (
                              <tr key={row.id}>
                                <td className="py-1 pr-4">{row.transaction_date}</td>
                                <td className="py-1 pr-4">{row.transaction_type}</td>
                                <td className="py-1 pr-4">{row.reference ?? "—"}</td>
                                <td className="py-1 pr-4">{row.description ?? "—"}</td>
                                <td className="py-1 pr-4 text-right">{row.amount}</td>
                              </tr>
                            ))
                          )}
                          <tr className="font-medium text-gray-900">
                            <td className="py-1 pr-4" colSpan={4}>
                              Closing balance
                            </td>
                            <td className="py-1 pr-4 text-right">{cashBook.closing_balance}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
