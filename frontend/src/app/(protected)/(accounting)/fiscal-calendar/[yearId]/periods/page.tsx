"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  FiscalPeriodResponse,
  FiscalYearResponse,
  getFiscalPeriods,
  getFiscalYear,
  lockFiscalPeriod,
  unlockFiscalPeriod,
} from "@/lib/api/accounting";
import YearEndCloseWizard from "@/components/accounting/YearEndCloseWizard";

interface PageProps {
  params: { company_id: string; yearId: string };
}

const STATUS_BADGE: Record<string, string> = {
  OPEN: "bg-green-100 text-green-800",
  LOCKED: "bg-amber-100 text-amber-800",
  CLOSED: "bg-red-100 text-red-700",
};

/**
 * Period Dashboard — grid of all periods for a fiscal year with
 * OPEN/LOCKED/CLOSED status badges and lock/unlock controls.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T081
 */
export default function FiscalPeriodsPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const yearId = params?.yearId ?? "";

  const [year, setYear] = useState<FiscalYearResponse | null>(null);
  const [periods, setPeriods] = useState<FiscalPeriodResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [actionPeriodId, setActionPeriodId] = useState<string | null>(null);
  const [reasonDraft, setReasonDraft] = useState("");
  const [showWizard, setShowWizard] = useState(false);

  useEffect(() => {
    if (!companyId || !yearId) return;
    load();
  }, [companyId, yearId]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [yearRes, periodsRes] = await Promise.all([
        getFiscalYear(companyId, yearId),
        getFiscalPeriods(companyId, yearId),
      ]);
      setYear(yearRes.data);
      setPeriods(periodsRes.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load periods");
    } finally {
      setLoading(false);
    }
  }

  async function handleLock(periodId: string) {
    if (!reasonDraft.trim()) {
      setError("A lock reason is required.");
      return;
    }
    setError(null);
    try {
      await lockFiscalPeriod(companyId, yearId, periodId, reasonDraft);
      setSuccess("Period locked");
      setActionPeriodId(null);
      setReasonDraft("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to lock period");
    }
  }

  async function handleUnlock(periodId: string) {
    if (!reasonDraft.trim()) {
      setError("A reason is required to unlock a period.");
      return;
    }
    setError(null);
    try {
      await unlockFiscalPeriod(companyId, yearId, periodId, reasonDraft);
      setSuccess("Period unlocked");
      setActionPeriodId(null);
      setReasonDraft("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to unlock period");
    }
  }

  const allLocked = periods.length > 0 && periods.every((p) => p.status === "LOCKED");

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Link
            href={`/${companyId}/fiscal-calendar`}
            className="text-sm text-blue-600 hover:underline"
          >
            ← Fiscal Calendar
          </Link>
          <h1 className="mt-1 text-2xl font-semibold text-gray-900">
            {year ? year.fiscal_year_name : "Periods"}
          </h1>
          {year && (
            <p className="mt-1 text-sm text-gray-500">
              {year.start_date} – {year.end_date} · {year.status}
            </p>
          )}
        </div>
        {year && year.status !== "CLOSED" && (
          <button
            onClick={() => setShowWizard(true)}
            disabled={!allLocked}
            title={
              allLocked
                ? "Run the year-end close workflow"
                : "All periods must be LOCKED before year-end close"
            }
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            Year-End Close
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-4 rounded-md bg-green-50 p-3 text-sm text-green-700" role="status">
          {success}
        </div>
      )}

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : periods.length === 0 ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          No periods found for this fiscal year.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
          {periods.map((p) => (
            <div
              key={p.id}
              className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
            >
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-semibold text-gray-900">
                  {p.period_name}
                </span>
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${STATUS_BADGE[p.status]}`}
                >
                  {p.status}
                </span>
              </div>
              <p className="mb-3 text-xs text-gray-500">
                {p.start_date} – {p.end_date}
              </p>
              {p.lock_reason && (
                <p className="mb-3 text-xs text-gray-500">
                  Reason: {p.lock_reason}
                </p>
              )}

              {actionPeriodId === p.id ? (
                <div className="space-y-2">
                  <input
                    autoFocus
                    value={reasonDraft}
                    onChange={(e) => setReasonDraft(e.target.value)}
                    placeholder="Reason (required)"
                    className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-xs"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() =>
                        p.status === "OPEN" ? handleLock(p.id) : handleUnlock(p.id)
                      }
                      className="flex-1 rounded-md bg-blue-600 px-2 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
                    >
                      Confirm
                    </button>
                    <button
                      onClick={() => {
                        setActionPeriodId(null);
                        setReasonDraft("");
                      }}
                      className="flex-1 rounded-md border border-gray-300 px-2 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex gap-2">
                  {p.status === "OPEN" && (
                    <button
                      onClick={() => setActionPeriodId(p.id)}
                      className="flex-1 rounded-md border border-amber-300 bg-amber-50 px-2 py-1.5 text-xs font-medium text-amber-800 hover:bg-amber-100"
                    >
                      Lock
                    </button>
                  )}
                  {p.status === "LOCKED" && (
                    <button
                      onClick={() => setActionPeriodId(p.id)}
                      className="flex-1 rounded-md border border-green-300 bg-green-50 px-2 py-1.5 text-xs font-medium text-green-800 hover:bg-green-100"
                    >
                      Unlock
                    </button>
                  )}
                  {p.status === "CLOSED" && (
                    <span className="flex-1 text-center text-xs text-gray-400">
                      Permanently closed
                    </span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <YearEndCloseWizard
        open={showWizard}
        companyId={companyId}
        fiscalYearId={yearId}
        periods={periods}
        onClose={() => setShowWizard(false)}
        onCompleted={async () => {
          setShowWizard(false);
          setSuccess("Year-end close completed");
          await load();
        }}
      />
    </div>
  );
}
