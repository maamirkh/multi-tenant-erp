"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getInvoice,
  listInvoiceLines,
  listInvoiceCharges,
  type InvoiceRead,
  type InvoiceLineRead,
  type InvoiceChargeRead,
} from "@/lib/api/sales";
import { InvoiceActions } from "@/components/sales/InvoiceActions";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-800",
  ISSUED: "bg-blue-100 text-blue-800",
  PAID: "bg-green-100 text-green-800",
  CANCELLED: "bg-red-100 text-red-600",
  CREDIT_NOTE_ISSUED: "bg-yellow-100 text-yellow-800",
};

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [invoice, setInvoice] = useState<InvoiceRead | null>(null);
  const [lines, setLines] = useState<InvoiceLineRead[]>([]);
  const [charges, setCharges] = useState<InvoiceChargeRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const companyId =
    typeof window !== "undefined"
      ? (localStorage.getItem("erp_active_company_id") ?? "")
      : "";
  const token =
    typeof window !== "undefined"
      ? (localStorage.getItem("access_token") ?? undefined)
      : undefined;

  const load = useCallback(async () => {
    if (!companyId || !id) return;
    setLoading(true);
    setError(null);
    try {
      const [invRes, linesRes, chargesRes] = await Promise.all([
        getInvoice(companyId, id, token),
        listInvoiceLines(companyId, id, token),
        listInvoiceCharges(companyId, id, token),
      ]);
      setInvoice(invRes.data);
      setLines(linesRes.data);
      setCharges(chargesRes.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load invoice");
    } finally {
      setLoading(false);
    }
  }, [companyId, id, token]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-64">
        <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
          {error}
        </div>
      </div>
    );
  }

  if (!invoice) return null;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button
            onClick={() => router.push("/invoices")}
            className="text-sm text-blue-600 hover:underline mb-2 block"
          >
            ← Back to Invoices
          </button>
          <h1 className="text-2xl font-bold text-gray-900">
            Invoice {invoice.invoice_number}
          </h1>
          <div className="flex items-center gap-3 mt-2">
            <span
              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                STATUS_COLORS[invoice.status] ?? "bg-gray-100 text-gray-600"
              }`}
            >
              {invoice.status}
            </span>
            <span className="text-sm text-gray-500">v{invoice.version}</span>
          </div>
        </div>
        <InvoiceActions
          companyId={companyId}
          invoiceId={invoice.id}
          invoiceNumber={invoice.invoice_number}
          status={invoice.status}
          totalAmount={invoice.total_amount}
          token={token}
          onSuccess={load}
        />
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
        {[
          { label: "Invoice Date", value: invoice.invoice_date },
          { label: "Due Date", value: invoice.due_date },
          { label: "Currency", value: invoice.currency_code },
          { label: "Customer ID", value: invoice.customer_id },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white border border-gray-200 rounded-lg p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
            <p className="mt-1 text-sm font-medium text-gray-900 truncate">{value}</p>
          </div>
        ))}
      </div>

      {/* Lines */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Invoice Lines</h2>
        {lines.length === 0 ? (
          <p className="text-sm text-gray-500">No lines.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  {["#", "Description", "Qty", "UoM", "Unit Price", "Discount", "Tax", "Extended"].map(
                    (h) => (
                      <th
                        key={h}
                        className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                      >
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-100">
                {lines.map((ln) => (
                  <tr key={ln.id}>
                    <td className="px-4 py-3 text-gray-700">{ln.line_number}</td>
                    <td className="px-4 py-3 text-gray-900">{ln.description}</td>
                    <td className="px-4 py-3 text-gray-700">{ln.quantity}</td>
                    <td className="px-4 py-3 text-gray-700">{ln.unit_of_measure}</td>
                    <td className="px-4 py-3 text-gray-700">{ln.unit_price}</td>
                    <td className="px-4 py-3 text-gray-700">
                      {ln.discount_amount ?? "-"}
                    </td>
                    <td className="px-4 py-3 text-gray-700">{ln.tax_amount}</td>
                    <td className="px-4 py-3 font-medium text-gray-900">{ln.extended_amount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Charges */}
      {charges.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Additional Charges</h2>
          <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  {["Type", "Description", "Amount", "Tax Applicable"].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-100">
                {charges.map((ch) => (
                  <tr key={ch.id}>
                    <td className="px-4 py-3 text-gray-700">{ch.charge_type}</td>
                    <td className="px-4 py-3 text-gray-900">{ch.description}</td>
                    <td className="px-4 py-3 font-medium text-gray-900">{ch.amount}</td>
                    <td className="px-4 py-3 text-gray-700">
                      {ch.tax_applicable ? "Yes" : "No"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Totals */}
      <div className="flex justify-end">
        <div className="w-64 space-y-2">
          {[
            { label: "Subtotal", value: invoice.subtotal },
            { label: "Discount", value: `-${invoice.discount_amount}` },
            { label: "Tax", value: invoice.tax_amount },
            { label: "Charges", value: invoice.charges_amount },
          ].map(({ label, value }) => (
            <div key={label} className="flex justify-between text-sm text-gray-600">
              <span>{label}</span>
              <span>{Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
            </div>
          ))}
          <div className="border-t border-gray-200 pt-2 flex justify-between text-base font-semibold text-gray-900">
            <span>Total</span>
            <span>
              {invoice.currency_code}{" "}
              {Number(invoice.total_amount).toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </span>
          </div>
          {invoice.amount_in_words && (
            <p className="text-xs text-gray-500 italic">{invoice.amount_in_words}</p>
          )}
          {invoice.credit_note_amount && (
            <div className="text-sm text-yellow-700 font-medium">
              Credit Note: -{invoice.credit_note_amount}
            </div>
          )}
        </div>
      </div>

      {/* Notes */}
      {(invoice.internal_notes || invoice.customer_notes) && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {invoice.internal_notes && (
            <div className="bg-gray-50 rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-700 mb-1">Internal Notes</h3>
              <p className="text-sm text-gray-600 whitespace-pre-line">{invoice.internal_notes}</p>
            </div>
          )}
          {invoice.customer_notes && (
            <div className="bg-blue-50 rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-700 mb-1">Customer Notes</h3>
              <p className="text-sm text-gray-600 whitespace-pre-line">{invoice.customer_notes}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
