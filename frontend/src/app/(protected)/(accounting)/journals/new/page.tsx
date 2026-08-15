"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  AccountResponse,
  JournalType,
  PostingLineRequest,
  createJournal,
  getAccounts,
  postJournal,
} from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string };
}

interface DraftLine {
  account_id: string;
  debit_amount: string;
  credit_amount: string;
  description: string;
}

const JOURNAL_TYPES: JournalType[] = [
  "STANDARD",
  "ADJUSTING",
  "OPENING_BALANCE",
  "CLOSING",
];

const EMPTY_LINE: DraftLine = {
  account_id: "",
  debit_amount: "",
  credit_amount: "",
  description: "",
};

/**
 * Journal Entry create page — multi-line form with account selector,
 * debit/credit inputs, running balance indicator, and balance status badge.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T104
 */
export default function NewJournalPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const router = useRouter();

  const [accounts, setAccounts] = useState<AccountResponse[]>([]);
  const [journalType, setJournalType] = useState<JournalType>("STANDARD");
  const [postingDate, setPostingDate] = useState(
    new Date().toISOString().slice(0, 10)
  );
  const [reference, setReference] = useState("");
  const [description, setDescription] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([EMPTY_LINE, EMPTY_LINE]);
  const [submitting, setSubmitting] = useState(false);
  const [postImmediately, setPostImmediately] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId) return;
    getAccounts(companyId, false)
      .then((res) => setAccounts((res.data as AccountResponse[]).filter((a) => a.is_leaf)))
      .catch(() => setAccounts([]));
  }, [companyId]);

  function addLine() {
    setLines([...lines, { ...EMPTY_LINE }]);
  }

  function updateLine(index: number, patch: Partial<DraftLine>) {
    setLines(lines.map((l, i) => (i === index ? { ...l, ...patch } : l)));
  }

  function removeLine(index: number) {
    if (lines.length <= 2) return;
    setLines(lines.filter((_, i) => i !== index));
  }

  const totals = useMemo(() => {
    const totalDebit = lines.reduce((sum, l) => sum + (parseFloat(l.debit_amount) || 0), 0);
    const totalCredit = lines.reduce(
      (sum, l) => sum + (parseFloat(l.credit_amount) || 0),
      0
    );
    return { totalDebit, totalCredit, balanced: totalDebit === totalCredit && totalDebit > 0 };
  }, [lines]);

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const payload: PostingLineRequest[] = lines
        .filter((l) => l.account_id)
        .map((l) => ({
          account_id: l.account_id,
          debit_amount: l.debit_amount || "0",
          credit_amount: l.credit_amount || "0",
          description: l.description || null,
        }));
      const created = await createJournal(companyId, {
        journal_type: journalType,
        posting_source: "MANUAL",
        posting_date: postingDate,
        reference: reference || null,
        description: description || null,
        lines: payload,
      });

      if (postImmediately) {
        await postJournal(companyId, created.data.id);
        setSuccess(`Journal ${created.data.journal_number ?? ""} created and posted`);
      } else {
        setSuccess("Journal saved as DRAFT");
      }
      router.push(`/${companyId}/journals`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create journal");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <Link href={`/${companyId}/journals`} className="text-sm text-blue-600 hover:underline">
        ← Journal Entries
      </Link>
      <h1 className="mt-1 mb-6 text-2xl font-semibold text-gray-900">New Journal Entry</h1>

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

      <div className="rounded-md border border-gray-200 bg-white p-5">
        <div className="mb-4 grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Journal Type</label>
            <select
              value={journalType}
              onChange={(e) => setJournalType(e.target.value as JournalType)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            >
              {JOURNAL_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Posting Date</label>
            <input
              type="date"
              value={postingDate}
              onChange={(e) => setPostingDate(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Reference</label>
            <input
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
        </div>

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700">Description</label>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            placeholder="Month-end accrual for..."
          />
        </div>

        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">Lines</h2>
          <button
            onClick={addLine}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
          >
            + Add Line
          </button>
        </div>

        <div className="space-y-2">
          {lines.map((line, i) => (
            <div key={i} className="flex items-center gap-2">
              <select
                value={line.account_id}
                onChange={(e) => updateLine(i, { account_id: e.target.value })}
                className="flex-1 rounded-md border border-gray-300 px-2 py-1.5 text-sm"
              >
                <option value="">Select account…</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.account_code} — {a.account_name}
                  </option>
                ))}
              </select>
              <input
                value={line.description}
                onChange={(e) => updateLine(i, { description: e.target.value })}
                placeholder="Line description"
                className="w-40 rounded-md border border-gray-300 px-2 py-1.5 text-sm"
              />
              <input
                type="number"
                step="0.01"
                placeholder="Debit"
                value={line.debit_amount}
                onChange={(e) => updateLine(i, { debit_amount: e.target.value })}
                className="w-28 rounded-md border border-gray-300 px-2 py-1.5 text-sm text-right"
              />
              <input
                type="number"
                step="0.01"
                placeholder="Credit"
                value={line.credit_amount}
                onChange={(e) => updateLine(i, { credit_amount: e.target.value })}
                className="w-28 rounded-md border border-gray-300 px-2 py-1.5 text-sm text-right"
              />
              <button
                onClick={() => removeLine(i)}
                disabled={lines.length <= 2}
                className="text-xs text-red-600 hover:underline disabled:cursor-not-allowed disabled:text-gray-300"
                aria-label="Remove line"
              >
                Remove
              </button>
            </div>
          ))}
        </div>

        <div className="mt-4 flex items-center justify-between border-t border-gray-100 pt-4">
          <div className="text-sm">
            <span className="text-gray-500">Debit: </span>
            <span className="font-medium text-gray-900">{totals.totalDebit.toFixed(2)}</span>
            <span className="ml-4 text-gray-500">Credit: </span>
            <span className="font-medium text-gray-900">{totals.totalCredit.toFixed(2)}</span>
            <span
              className={`ml-3 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                totals.balanced
                  ? "bg-green-100 text-green-800"
                  : "bg-red-100 text-red-700"
              }`}
            >
              {totals.balanced ? "Balanced" : "Imbalanced"}
            </span>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={postImmediately}
              onChange={(e) => setPostImmediately(e.target.checked)}
            />
            Post immediately
          </label>
        </div>

        <div className="mt-4 flex justify-end">
          <button
            onClick={handleSubmit}
            disabled={submitting || !totals.balanced}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? "Saving..." : postImmediately ? "Save & Post" : "Save as Draft"}
          </button>
        </div>
      </div>
    </div>
  );
}
