"use client";

import { useState } from "react";
import Link from "next/link";
import {
  PaymentResponse,
  allocatePayment,
  cancelPayment,
  createCustomerPayment,
  getCustomerPayments,
} from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string };
}

const emptyForm = {
  customer_id: "",
  payment_method: "BANK_TRANSFER",
  payment_date: new Date().toISOString().slice(0, 10),
  amount: "",
  currency_code: "USD",
  bank_account_id: "",
  cash_account_id: "",
  reference: "",
};

const emptyAllocationForm = {
  transaction_id: "",
  amount_foreign: "",
  discount_amount: "",
  discount_account_id: "",
};

/**
 * Customer Payment screen: payment form + allocation table with invoice selection.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T217
 */
export default function CustomerPaymentPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const [searchCustomerId, setSearchCustomerId] = useState("");
  const [payments, setPayments] = useState<PaymentResponse[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [selectedPaymentId, setSelectedPaymentId] = useState<string | null>(null);
  const [allocationForm, setAllocationForm] = useState(emptyAllocationForm);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadPayments() {
    if (!searchCustomerId) {
      setError("Enter a customer ID to search.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await getCustomerPayments(companyId, searchCustomerId);
      setPayments(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load payments");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    if (!form.customer_id || !form.amount || (!form.bank_account_id && !form.cash_account_id)) {
      setError("Customer, amount, and a bank or cash account are required.");
      return;
    }
    setError(null);
    try {
      await createCustomerPayment(companyId, {
        ...form,
        bank_account_id: form.bank_account_id || null,
        cash_account_id: form.cash_account_id || null,
        reference: form.reference || null,
      });
      setForm({ ...emptyForm, customer_id: form.customer_id });
      setSearchCustomerId(form.customer_id);
      await loadPayments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create payment");
    }
  }

  async function handleAllocate(paymentId: string) {
    if (!allocationForm.transaction_id || !allocationForm.amount_foreign) {
      setError("Transaction ID and amount are required to allocate.");
      return;
    }
    setError(null);
    try {
      await allocatePayment(companyId, paymentId, [
        {
          transaction_id: allocationForm.transaction_id,
          amount_foreign: allocationForm.amount_foreign,
          discount_amount: allocationForm.discount_amount || "0",
          discount_account_id: allocationForm.discount_account_id || null,
        },
      ]);
      setAllocationForm(emptyAllocationForm);
      await loadPayments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to allocate payment");
    }
  }

  async function handleCancel(paymentId: string) {
    setError(null);
    try {
      await cancelPayment(companyId, paymentId, "Cancelled from Customer Payment screen");
      await loadPayments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel payment");
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Customer Payments</h1>
          <p className="mt-1 text-sm text-gray-500">
            Record customer receipts and allocate them to open invoices.
          </p>
        </div>
        <Link
          href={`/${companyId}/payments/unallocated`}
          className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Unallocated Payments
        </Link>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      <section className="mb-8 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-gray-900">New Payment</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <input
            type="text"
            value={form.customer_id}
            onChange={(e) => setForm({ ...form, customer_id: e.target.value })}
            placeholder="Customer UUID"
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
          <select
            value={form.payment_method}
            onChange={(e) => setForm({ ...form, payment_method: e.target.value })}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          >
            <option value="BANK_TRANSFER">Bank Transfer</option>
            <option value="CASH">Cash</option>
            <option value="CHEQUE">Cheque</option>
            <option value="CARD">Card</option>
            <option value="ONLINE">Online</option>
          </select>
          <input
            type="date"
            value={form.payment_date}
            onChange={(e) => setForm({ ...form, payment_date: e.target.value })}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
          <input
            type="number"
            value={form.amount}
            onChange={(e) => setForm({ ...form, amount: e.target.value })}
            placeholder="Amount"
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
            value={form.bank_account_id}
            onChange={(e) => setForm({ ...form, bank_account_id: e.target.value })}
            placeholder="Bank account UUID"
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
          <input
            type="text"
            value={form.cash_account_id}
            onChange={(e) => setForm({ ...form, cash_account_id: e.target.value })}
            placeholder="Cash account UUID (alternative to bank)"
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
          <input
            type="text"
            value={form.reference}
            onChange={(e) => setForm({ ...form, reference: e.target.value })}
            placeholder="Reference"
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </div>
        <button
          onClick={handleCreate}
          className="mt-3 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Record Payment
        </button>
      </section>

      <section className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-gray-900">Payment History</h2>
        <div className="mb-3 flex gap-3">
          <input
            type="text"
            value={searchCustomerId}
            onChange={(e) => setSearchCustomerId(e.target.value)}
            placeholder="Customer UUID"
            className="flex-1 rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
          <button
            onClick={loadPayments}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
          >
            Search
          </button>
        </div>

        {loading ? (
          <div className="py-8 text-center text-gray-500">Loading...</div>
        ) : payments.length === 0 ? (
          <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
            No payments found. Search by customer ID.
          </div>
        ) : (
          <div className="space-y-3">
            {payments.map((payment) => (
              <div
                key={payment.id}
                className="rounded-lg border border-gray-200 p-3"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-gray-900">
                      {payment.amount_base} {payment.currency_code} — {payment.payment_method}
                    </p>
                    <p className="text-xs text-gray-500">
                      {payment.payment_date} · Status: {payment.status}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() =>
                        setSelectedPaymentId(selectedPaymentId === payment.id ? null : payment.id)
                      }
                      className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                    >
                      Allocate
                    </button>
                    {payment.status !== "CANCELLED" && (
                      <button
                        onClick={() => handleCancel(payment.id)}
                        className="rounded-md border border-red-300 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-50"
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                </div>

                {selectedPaymentId === payment.id && (
                  <div className="mt-3 grid grid-cols-1 gap-3 border-t border-gray-100 pt-3 sm:grid-cols-5">
                    <input
                      type="text"
                      value={allocationForm.transaction_id}
                      onChange={(e) =>
                        setAllocationForm({ ...allocationForm, transaction_id: e.target.value })
                      }
                      placeholder="Invoice (AR transaction) UUID"
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                    />
                    <input
                      type="number"
                      value={allocationForm.amount_foreign}
                      onChange={(e) =>
                        setAllocationForm({ ...allocationForm, amount_foreign: e.target.value })
                      }
                      placeholder="Amount to allocate"
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                    />
                    <input
                      type="number"
                      value={allocationForm.discount_amount}
                      onChange={(e) =>
                        setAllocationForm({ ...allocationForm, discount_amount: e.target.value })
                      }
                      placeholder="Discount (optional)"
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                    />
                    <input
                      type="text"
                      value={allocationForm.discount_account_id}
                      onChange={(e) =>
                        setAllocationForm({
                          ...allocationForm,
                          discount_account_id: e.target.value,
                        })
                      }
                      placeholder="Discount GL account (if discount)"
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                    />
                    <button
                      onClick={() => handleAllocate(payment.id)}
                      className="rounded-md bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700"
                    >
                      Apply Allocation
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
