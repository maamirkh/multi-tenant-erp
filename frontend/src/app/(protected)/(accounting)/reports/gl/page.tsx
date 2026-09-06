"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AccountResponse,
  GLReportRow,
  getAccounts,
  getGLReport,
} from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string };
}

/**
 * GL Report page — searchable/filterable General Ledger with account and
 * date filters; drill-down to the source document on row click.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T106
 */
export default function GLReportPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const [accounts, setAccounts] = useState<AccountResponse[]>([]);
  const [rows, setRows] = useState<GLReportRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [accountId, setAccountId] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  useEffect(() => {
    if (!companyId) return;
    getAccounts(companyId, false)
      .then((res) => setAccounts(res.data as AccountResponse[]))
      .catch(() => setAccounts([]));
  }, [companyId]);

  useEffect(() => {
    if (!companyId) return;
    load();
  }, [companyId, accountId, startDate, endDate]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await getGLReport(companyId, {
        account_id: accountId || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        limit: 200,
      });
      setRows(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load GL report");
    } finally {
      setLoading(false);
    }
  }

  const totals = rows.reduce(
    (acc, r) => ({
      debit: acc.debit + parseFloat(r.debit_amount),
      credit: acc.credit + parseFloat(r.credit_amount),
    }),
    { debit: 0, credit: 0 }
  );

  function sourceDocHref(row: GLReportRow): string | null {
    if (!row.source_document_type || !row.source_document_id) return null;
    if (row.source_document_type === "SalesInvoice") {
      return `/${companyId}/invoices/${row.source_document_id}`;
    }
    return null;
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <Link href={`/${companyId}/journals`} className="text-sm text-blue-600 hover:underline">
        ← Journal Entries
      </Link>
      <h1 className="mt-1 mb-1 text-2xl font-semibold text-gray-900">General Ledger Report</h1>
      <p className="mb-6 text-sm text-gray-500">
        Posted GL lines only — drafts and rejected entries are excluded.
      </p>

      <div className="mb-4 flex items-center gap-3">
        <select
          value={accountId}
          onChange={(e) => setAccountId(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm"
        >
          <option value="">All accounts</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.account_code} — {a.account_name}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm"
        />
        <span className="text-sm text-gray-400">to</span>
        <input
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm"
        />
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : rows.length === 0 ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          No posted GL lines match these filters.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-md border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Date</th>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Journal #</th>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Account</th>
                <th className="px-4 py-2 text-left font-medium text-gray-600">Description</th>
                <th className="px-4 py-2 text-right font-medium text-gray-600">Debit</th>
                <th className="px-4 py-2 text-right font-medium text-gray-600">Credit</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {rows.map((r, i) => {
                const href = sourceDocHref(r);
                return (
                  <tr key={i} className={href ? "cursor-pointer hover:bg-gray-50" : ""}>
                    <td className="px-4 py-2 text-gray-600">{r.posting_date}</td>
                    <td className="px-4 py-2 font-mono text-xs text-gray-700">
                      {href ? (
                        <Link href={href} className="text-blue-600 hover:underline">
                          {r.journal_number}
                        </Link>
                      ) : (
                        r.journal_number
                      )}
                    </td>
                    <td className="px-4 py-2 text-gray-900">{r.account_code}</td>
                    <td className="px-4 py-2 text-gray-600">{r.description ?? r.reference ?? ""}</td>
                    <td className="px-4 py-2 text-right text-gray-900">
                      {parseFloat(r.debit_amount) > 0 ? r.debit_amount : ""}
                    </td>
                    <td className="px-4 py-2 text-right text-gray-900">
                      {parseFloat(r.credit_amount) > 0 ? r.credit_amount : ""}
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot className="bg-gray-50 font-medium">
              <tr>
                <td colSpan={4} className="px-4 py-2 text-right text-gray-600">
                  Totals
                </td>
                <td className="px-4 py-2 text-right text-gray-900">{totals.debit.toFixed(2)}</td>
                <td className="px-4 py-2 text-right text-gray-900">{totals.credit.toFixed(2)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}
