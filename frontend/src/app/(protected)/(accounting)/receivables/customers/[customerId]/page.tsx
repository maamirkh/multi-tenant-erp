"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  CustomerLedgerResponse,
  getCustomerLedger,
} from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string; customerId: string };
}

const CREDIT_STATUS_STYLES: Record<string, string> = {
  GOOD: "bg-green-100 text-green-800",
  WARNING: "bg-yellow-100 text-yellow-800",
  EXCEEDED: "bg-orange-100 text-orange-800",
  HOLD: "bg-red-100 text-red-800",
};

/**
 * Customer Ledger page — per-customer AR subsidiary ledger summary.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T147
 */
export default function CustomerLedgerPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const customerId = params?.customerId ?? "";
  const [ledger, setLedger] = useState<CustomerLedgerResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId || !customerId) return;
    load();
  }, [companyId, customerId]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getCustomerLedger(companyId, customerId);
      setLedger(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load customer ledger");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <Link
          href={`/${companyId}/receivables/aging`}
          className="text-sm text-blue-600 hover:underline"
        >
          ← AR Aging Report
        </Link>
        <h1 className="mt-1 text-2xl font-semibold text-gray-900">Customer Ledger</h1>
        <p className="mt-1 text-sm text-gray-500">
          Outstanding balance, credit status, and payment history for this customer.
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : !ledger ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          No ledger found for this customer yet.
        </div>
      ) : (
        <div className="space-y-4">
          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-gray-500">Total Outstanding</p>
                <p className="text-2xl font-semibold text-gray-900">
                  {ledger.total_outstanding_base}
                </p>
              </div>
              <span
                className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  CREDIT_STATUS_STYLES[ledger.credit_status] ?? "bg-gray-100 text-gray-500"
                }`}
              >
                {ledger.credit_status}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <p className="text-xs text-gray-500">Credit Limit</p>
              <p className="text-lg font-medium text-gray-900">{ledger.credit_limit}</p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <p className="text-xs text-gray-500">Last Payment Date</p>
              <p className="text-lg font-medium text-gray-900">
                {ledger.last_payment_date ?? "—"}
              </p>
            </div>
          </div>

          {ledger.credit_status === "HOLD" && (
            <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
              On credit hold since{" "}
              {ledger.credit_hold_at ? new Date(ledger.credit_hold_at).toLocaleString() : "—"}.
              {ledger.credit_hold_reason ? ` Reason: ${ledger.credit_hold_reason}` : ""}
            </div>
          )}

          <div className="flex gap-3">
            <Link
              href={`/${companyId}/receivables/statements?customer_id=${customerId}`}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Generate Statement
            </Link>
            <Link
              href={`/${companyId}/receivables/credit-management?customer_id=${customerId}`}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Manage Credit
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
