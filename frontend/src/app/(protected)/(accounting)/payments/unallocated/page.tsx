"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PaymentResponse, getUnallocatedPayments } from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string };
}

/**
 * Unallocated Payments report: list of payments not yet fully allocated,
 * with a link through to the customer/supplier allocation screen.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T219
 */
export default function UnallocatedPaymentsPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const [payments, setPayments] = useState<PaymentResponse[]>([]);
  const [partyType, setPartyType] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId, partyType]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getUnallocatedPayments(companyId, partyType || undefined);
      setPayments(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load unallocated payments");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Unallocated Payments</h1>
          <p className="mt-1 text-sm text-gray-500">
            Payments not yet fully allocated to an invoice or bill.
          </p>
        </div>
        <div className="flex gap-3">
          <Link
            href={`/${companyId}/payments/customer`}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Customer Payments
          </Link>
          <Link
            href={`/${companyId}/payments/supplier`}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Supplier Payments
          </Link>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      <div className="mb-4 flex gap-3">
        {["", "CUSTOMER", "SUPPLIER"].map((option) => (
          <button
            key={option || "all"}
            onClick={() => setPartyType(option)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium ${
              partyType === option
                ? "bg-blue-600 text-white"
                : "border border-gray-300 text-gray-700 hover:bg-gray-50"
            }`}
          >
            {option === "" ? "All" : option === "CUSTOMER" ? "Customers" : "Suppliers"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : payments.length === 0 ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          No unallocated payments.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500">
                <th className="px-4 py-2">Date</th>
                <th className="px-4 py-2">Party</th>
                <th className="px-4 py-2">Method</th>
                <th className="px-4 py-2 text-right">Amount</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Reference</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {payments.map((payment) => (
                <tr key={payment.id}>
                  <td className="px-4 py-2">{payment.payment_date}</td>
                  <td className="px-4 py-2">{payment.party_type}</td>
                  <td className="px-4 py-2">{payment.payment_method}</td>
                  <td className="px-4 py-2 text-right">
                    {payment.amount_base} {payment.currency_code}
                  </td>
                  <td className="px-4 py-2">{payment.status}</td>
                  <td className="px-4 py-2">{payment.reference ?? "—"}</td>
                  <td className="px-4 py-2 text-right">
                    <Link
                      href={
                        payment.party_type === "CUSTOMER"
                          ? `/${companyId}/payments/customer`
                          : `/${companyId}/payments/supplier`
                      }
                      className="text-xs font-medium text-blue-600 hover:underline"
                    >
                      Allocate →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
