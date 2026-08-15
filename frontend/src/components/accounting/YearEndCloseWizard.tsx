"use client";

import { useState } from "react";
import { FiscalPeriodResponse, executeYearEndClose } from "@/lib/api/accounting";

interface YearEndCloseWizardProps {
  open: boolean;
  companyId: string;
  fiscalYearId: string;
  periods: FiscalPeriodResponse[];
  onClose: () => void;
  onCompleted: () => void | Promise<void>;
}

interface ChecklistItem {
  label: string;
  done: boolean;
  note?: string;
}

/**
 * YearEndCloseWizard — multi-step checklist confirming period locks, bank
 * reconciliation, AR/AP confirmation, and a preview before executing the
 * year-end close workflow.
 *
 * NOTE: bank reconciliation and AR/AP confirmation are informational
 * checklist items in this phase — Banking (Phase 7) and AR/AP (Phases 5-6)
 * do not exist yet, so those steps cannot be verified against real data.
 * They are shown as manual-attestation items; only the periods-locked
 * check is enforced server-side (execute_year_end_close raises 422
 * otherwise). Documented gap, consistent with other forward-dependency
 * notes across this phase.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T083
 */
export default function YearEndCloseWizard({
  open,
  fiscalYearId,
  periods,
  companyId,
  onClose,
  onCompleted,
}: YearEndCloseWizardProps) {
  const [attested, setAttested] = useState({ bank: false, arAp: false });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const allPeriodsLocked = periods.length > 0 && periods.every((p) => p.status === "LOCKED");

  const checklist: ChecklistItem[] = [
    {
      label: "All periods in this fiscal year are LOCKED",
      done: allPeriodsLocked,
    },
    {
      label: "Bank accounts reconciled",
      done: attested.bank,
      note: "Manual attestation — Banking module ships in a later phase.",
    },
    {
      label: "AR/AP control accounts confirmed",
      done: attested.arAp,
      note: "Manual attestation — AR/AP modules ship in later phases.",
    },
  ];

  const canProceed = checklist.every((c) => c.done);

  async function handleConfirm() {
    setSubmitting(true);
    setError(null);
    try {
      await executeYearEndClose(companyId, fiscalYearId);
      await onCompleted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Year-end close failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      role="dialog"
      aria-modal="true"
      aria-labelledby="year-end-close-title"
    >
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <h2 id="year-end-close-title" className="mb-1 text-lg font-semibold text-gray-900">
          Year-End Close
        </h2>
        <p className="mb-4 text-sm text-gray-500">
          Review the closing checklist before proceeding. This action locks
          every period permanently and cannot be reversed.
        </p>

        {error && (
          <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
            {error}
          </div>
        )}

        <ul className="mb-4 space-y-3">
          {checklist.map((item, i) => (
            <li key={i} className="flex items-start gap-3">
              {i === 0 ? (
                <span
                  className={`mt-0.5 inline-block h-4 w-4 flex-shrink-0 rounded-full ${
                    item.done ? "bg-green-500" : "bg-gray-300"
                  }`}
                />
              ) : (
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={item.done}
                  onChange={(e) =>
                    setAttested((prev) => ({
                      ...prev,
                      [i === 1 ? "bank" : "arAp"]: e.target.checked,
                    }))
                  }
                />
              )}
              <div>
                <p className="text-sm text-gray-800">{item.label}</p>
                {item.note && <p className="text-xs text-gray-400">{item.note}</p>}
              </div>
            </li>
          ))}
        </ul>

        {!allPeriodsLocked && (
          <p className="mb-4 text-xs text-red-600">
            All periods must be LOCKED before year-end close can proceed.
          </p>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={!canProceed || submitting}
            className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
          >
            {submitting ? "Closing..." : "Confirm Year-End Close"}
          </button>
        </div>
      </div>
    </div>
  );
}
