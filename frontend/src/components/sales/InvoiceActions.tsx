"use client";

import { useState } from "react";
import { issueInvoice, cancelInvoice, issueCreditNote } from "@/lib/api/sales";

interface InvoiceActionsProps {
  companyId: string;
  invoiceId: string;
  invoiceNumber: string;
  status: string;
  totalAmount: string;
  token?: string | undefined;
  onSuccess: () => void;
}

export function InvoiceActions({
  companyId,
  invoiceId,
  invoiceNumber,
  status,
  totalAmount,
  token,
  onSuccess,
}: InvoiceActionsProps) {
  const [dialog, setDialog] = useState<"issue" | "cancel" | "credit_note" | null>(null);
  const [creditNoteAmount, setCreditNoteAmount] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleIssue() {
    setLoading(true);
    setError(null);
    try {
      await issueInvoice(companyId, invoiceId, token);
      setDialog(null);
      onSuccess();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to issue invoice");
    } finally {
      setLoading(false);
    }
  }

  async function handleCancel() {
    setLoading(true);
    setError(null);
    try {
      await cancelInvoice(companyId, invoiceId, token);
      setDialog(null);
      onSuccess();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to cancel invoice");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreditNote() {
    if (!creditNoteAmount || Number(creditNoteAmount) <= 0) {
      setError("Credit note amount must be positive.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await issueCreditNote(companyId, invoiceId, creditNoteAmount, token);
      setDialog(null);
      onSuccess();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to issue credit note");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex gap-3">
      {status === "DRAFT" && (
        <>
          <button
            onClick={() => setDialog("issue")}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Issue Invoice
          </button>
          <button
            onClick={() => setDialog("cancel")}
            className="px-4 py-2 bg-white text-red-600 border border-red-300 text-sm font-medium rounded-md hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500"
          >
            Cancel
          </button>
        </>
      )}
      {status === "ISSUED" && (
        <button
          onClick={() => setDialog("credit_note")}
          className="px-4 py-2 bg-yellow-600 text-white text-sm font-medium rounded-md hover:bg-yellow-700 focus:outline-none focus:ring-2 focus:ring-yellow-500"
        >
          Issue Credit Note
        </button>
      )}

      {/* Issue confirmation dialog */}
      {dialog === "issue" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Issue Invoice</h2>
            <p className="text-sm text-gray-600 mb-4">
              Are you sure you want to issue{" "}
              <span className="font-medium">{invoiceNumber}</span>? This action cannot be
              undone.
            </p>
            {error && (
              <div className="text-red-600 text-sm mb-3">{error}</div>
            )}
            <div className="flex justify-end gap-3">
              <button
                onClick={() => { setDialog(null); setError(null); }}
                className="px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
                disabled={loading}
              >
                Cancel
              </button>
              <button
                onClick={handleIssue}
                className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:opacity-50"
                disabled={loading}
              >
                {loading ? "Issuing…" : "Confirm Issue"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Cancel confirmation dialog */}
      {dialog === "cancel" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Cancel Invoice</h2>
            <p className="text-sm text-gray-600 mb-4">
              Cancel <span className="font-medium">{invoiceNumber}</span>? The invoice number
              will be retained but the invoice will be voided.
            </p>
            {error && <div className="text-red-600 text-sm mb-3">{error}</div>}
            <div className="flex justify-end gap-3">
              <button
                onClick={() => { setDialog(null); setError(null); }}
                className="px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
                disabled={loading}
              >
                Back
              </button>
              <button
                onClick={handleCancel}
                className="px-4 py-2 bg-red-600 text-white text-sm rounded-md hover:bg-red-700 disabled:opacity-50"
                disabled={loading}
              >
                {loading ? "Cancelling…" : "Confirm Cancel"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Credit note dialog */}
      {dialog === "credit_note" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Issue Credit Note</h2>
            <p className="text-sm text-gray-600 mb-4">
              Issue a credit note against <span className="font-medium">{invoiceNumber}</span>{" "}
              (total: {totalAmount}).
            </p>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Credit Note Amount
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                value={creditNoteAmount}
                onChange={(e) => setCreditNoteAmount(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-yellow-500"
                placeholder="0.00"
              />
            </div>
            {error && <div className="text-red-600 text-sm mb-3">{error}</div>}
            <div className="flex justify-end gap-3">
              <button
                onClick={() => { setDialog(null); setError(null); setCreditNoteAmount(""); }}
                className="px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
                disabled={loading}
              >
                Cancel
              </button>
              <button
                onClick={handleCreditNote}
                className="px-4 py-2 bg-yellow-600 text-white text-sm rounded-md hover:bg-yellow-700 disabled:opacity-50"
                disabled={loading}
              >
                {loading ? "Submitting…" : "Issue Credit Note"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
