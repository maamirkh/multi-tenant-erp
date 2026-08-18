"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  SupplierLedgerResponse,
  getSupplierLedger,
} from "@/lib/api/accounting";

/**
 * Supplier Ledger page — per-supplier AP subsidiary ledger summary.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T170
 */
export default function SupplierLedgerPage() {
  const params = useParams<{ supplierId: string }>();
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";
  const supplierId = params?.supplierId ?? "";
  const [ledger, setLedger] = useState<SupplierLedgerResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId || !supplierId) return;
    load();
  }, [companyId, supplierId]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getSupplierLedger(companyId, supplierId);
      setLedger(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load supplier ledger");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <Link
          href={`/${companyId}/payables/aging`}
          className="text-sm text-blue-600 hover:underline"
        >
          ← AP Aging Report
        </Link>
        <h1 className="mt-1 text-2xl font-semibold text-gray-900">Supplier Ledger</h1>
        <p className="mt-1 text-sm text-gray-500">
          Outstanding balance and payment history for this supplier.
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
          No ledger found for this supplier yet.
        </div>
      ) : (
        <div className="space-y-4">
          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <p className="text-xs text-gray-500">Total Outstanding</p>
            <p className="text-2xl font-semibold text-gray-900">
              {ledger.total_outstanding_base}
            </p>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <p className="text-xs text-gray-500">Last Payment Date</p>
            <p className="text-lg font-medium text-gray-900">
              {ledger.last_payment_date ?? "—"}
            </p>
          </div>

          <div className="flex gap-3">
            <Link
              href={`/${companyId}/payables/reconcile?supplier_id=${supplierId}`}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Reconcile Statement
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
