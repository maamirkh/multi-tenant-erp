"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { bulkImportAccounts, COAImportResultRow } from "@/lib/api/accounting";

const TEMPLATE_HEADER = "account_code,account_name,account_type,account_group_code,is_leaf";
const TEMPLATE_EXAMPLE =
  "1005,Petty Cash Box,ASSET,CUR-AST,true";

/** Minimal CSV line parser — sufficient for the flat, comma-only COA import format. */
function parseCsv(text: string): Record<string, string>[] {
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
  const headerLine = lines[0];
  if (lines.length < 2 || !headerLine) return [];
  const headers = headerLine.split(",").map((h) => h.trim());
  return lines.slice(1).map((line) => {
    const cells = line.split(",").map((c) => c.trim());
    const row: Record<string, string> = {};
    headers.forEach((h, i) => {
      row[h] = cells[i] ?? "";
    });
    return row;
  });
}

/**
 * Chart of Accounts Bulk Import page.
 * Downloads a CSV template, accepts an uploaded CSV, and reports
 * row-level success/failure after posting to the bulk-import endpoint.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T062
 */
export default function COABulkImportPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState<COAImportResultRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function downloadTemplate() {
    const csv = [TEMPLATE_HEADER, TEMPLATE_EXAMPLE].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "coa_import_template.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleUpload() {
    if (!file || !companyId) return;
    setUploading(true);
    setError(null);
    setResults(null);
    try {
      const text = await file.text();
      const rows = parseCsv(text).map((r) => ({
        ...r,
        is_leaf: r.is_leaf ? r.is_leaf.toLowerCase() !== "false" : true,
      }));
      const res = await bulkImportAccounts(companyId, rows);
      setResults(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setUploading(false);
    }
  }

  const successCount = results?.filter((r) => r.success).length ?? 0;
  const failureCount = results ? results.length - successCount : 0;

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="mb-4">
        <Link
          href={`/${companyId}/chart-of-accounts`}
          className="text-sm text-blue-600 hover:underline"
        >
          ← Chart of Accounts
        </Link>
      </div>

      <h1 className="mb-6 text-2xl font-semibold text-gray-900">Bulk Import Accounts</h1>

      <div className="mb-6 rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">
        <p className="mb-2 font-medium">Instructions</p>
        <ol className="list-inside list-decimal space-y-1">
          <li>Download the CSV template below.</li>
          <li>Fill in one row per account.</li>
          <li>Upload the completed file.</li>
          <li>
            Required columns:{" "}
            <code className="rounded bg-blue-100 px-1">account_code</code>,{" "}
            <code className="rounded bg-blue-100 px-1">account_name</code>,{" "}
            <code className="rounded bg-blue-100 px-1">account_type</code>.
          </li>
        </ol>
        <button
          onClick={downloadTemplate}
          className="mt-3 font-medium text-blue-700 hover:underline"
        >
          ↓ Download template
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      <div
        onClick={() => fileRef.current?.click()}
        className="cursor-pointer rounded-lg border-2 border-dashed border-gray-300 p-8 text-center transition-colors hover:border-blue-400"
      >
        {file ? (
          <div>
            <p className="text-sm font-medium text-gray-900">{file.name}</p>
            <p className="mt-1 text-xs text-gray-500">{(file.size / 1024).toFixed(1)} KB</p>
          </div>
        ) : (
          <p className="text-sm text-gray-500">Click to select a CSV file</p>
        )}
        <input
          ref={fileRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
      </div>

      <button
        onClick={handleUpload}
        disabled={!file || uploading}
        className="mt-4 w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {uploading ? "Importing..." : "Upload and Import"}
      </button>

      {results && (
        <div className="mt-6">
          <p className="mb-2 text-sm font-medium text-gray-700">
            {successCount} succeeded, {failureCount} failed (of {results.length} rows)
          </p>
          <table className="min-w-full divide-y divide-gray-200 border border-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                  Row
                </th>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                  Code
                </th>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                  Status
                </th>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                  Error
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {results.map((r) => (
                <tr key={r.row} className={r.success ? "" : "bg-red-50"}>
                  <td className="px-3 py-1.5">{r.row}</td>
                  <td className="px-3 py-1.5 font-mono">{r.account_code}</td>
                  <td className="px-3 py-1.5">
                    {r.success ? (
                      <span className="text-green-700">✓ Created</span>
                    ) : (
                      <span className="text-red-700">✗ Failed</span>
                    )}
                  </td>
                  <td className="px-3 py-1.5 text-gray-500">{r.error ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
