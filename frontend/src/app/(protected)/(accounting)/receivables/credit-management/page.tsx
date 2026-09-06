"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  CustomerLedgerResponse,
  getCustomerLedger,
  placeCreditHold,
  releaseCreditHold,
  setCreditLimit,
} from "@/lib/api/accounting";

const CREDIT_STATUS_STYLES: Record<string, string> = {
  GOOD: "bg-green-100 text-green-800",
  WARNING: "bg-yellow-100 text-yellow-800",
  EXCEEDED: "bg-orange-100 text-orange-800",
  HOLD: "bg-red-100 text-red-800",
};

/**
 * Credit Management page — look up a customer's credit status and apply
 * hold/release/limit controls.
 *
 * No "list all customers" endpoint exists in T145's fixed API surface, so
 * this page operates on one customer at a time (looked up by ID) — the
 * Customer Ledger and AR Aging pages both link here with `?customer_id=`.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T150
 */
function CreditManagementForm({ companyId }: { companyId: string }) {
  const searchParams = useSearchParams();
  const [customerId, setCustomerId] = useState(searchParams.get("customer_id") ?? "");
  const [ledger, setLedger] = useState<CustomerLedgerResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [holdReason, setHoldReason] = useState("");
  const [newLimit, setNewLimit] = useState("");

  useEffect(() => {
    if (customerId) void load();
  }, []);

  async function load() {
    if (!customerId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getCustomerLedger(companyId, customerId);
      setLedger(res.data);
      setNewLimit(res.data.credit_limit);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load customer ledger");
    } finally {
      setLoading(false);
    }
  }

  async function handlePlaceHold() {
    if (!holdReason) {
      setError("A reason is required to place a credit hold.");
      return;
    }
    setError(null);
    try {
      const res = await placeCreditHold(companyId, customerId, holdReason);
      setLedger(res.data);
      setHoldReason("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to place credit hold");
    }
  }

  async function handleReleaseHold() {
    setError(null);
    try {
      const res = await releaseCreditHold(companyId, customerId);
      setLedger(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to release credit hold");
    }
  }

  async function handleSetLimit() {
    setError(null);
    try {
      const res = await setCreditLimit(companyId, customerId, newLimit);
      setLedger(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update credit limit");
    }
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Credit Management</h1>
        <p className="mt-1 text-sm text-gray-500">
          Place or release credit holds and adjust credit limits for a customer.
        </p>
      </div>

      <div className="mb-6 flex gap-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <input
          type="text"
          value={customerId}
          onChange={(e) => setCustomerId(e.target.value)}
          placeholder="Customer UUID"
          className="flex-1 rounded-md border border-gray-300 px-2 py-1 text-sm"
        />
        <button
          onClick={load}
          disabled={loading}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Loading..." : "Look Up"}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {ledger && (
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <div>
              <p className="text-xs text-gray-500">Total Outstanding</p>
              <p className="text-xl font-semibold text-gray-900">
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

          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <h2 className="mb-2 text-sm font-semibold text-gray-900">Credit Limit</h2>
            <div className="flex gap-3">
              <input
                type="text"
                value={newLimit}
                onChange={(e) => setNewLimit(e.target.value)}
                className="flex-1 rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
              <button
                onClick={handleSetLimit}
                className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Update
              </button>
            </div>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <h2 className="mb-2 text-sm font-semibold text-gray-900">Credit Hold</h2>
            {ledger.credit_status === "HOLD" ? (
              <div>
                <p className="mb-2 text-sm text-gray-600">
                  On hold since{" "}
                  {ledger.credit_hold_at
                    ? new Date(ledger.credit_hold_at).toLocaleString()
                    : "—"}
                  {ledger.credit_hold_reason ? ` — ${ledger.credit_hold_reason}` : ""}
                </p>
                <button
                  onClick={handleReleaseHold}
                  className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
                >
                  Release Hold
                </button>
              </div>
            ) : (
              <div className="flex gap-3">
                <input
                  type="text"
                  value={holdReason}
                  onChange={(e) => setHoldReason(e.target.value)}
                  placeholder="Reason for hold"
                  className="flex-1 rounded-md border border-gray-300 px-2 py-1 text-sm"
                />
                <button
                  onClick={handlePlaceHold}
                  className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
                >
                  Place Hold
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function CreditManagementPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";
  return (
    <Suspense fallback={<div className="py-8 text-center text-gray-500">Loading...</div>}>
      <CreditManagementForm companyId={companyId} />
    </Suspense>
  );
}
