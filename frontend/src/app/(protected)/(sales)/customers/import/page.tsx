"use client";

import { useState, useRef } from "react";
import Link from "next/link";
import { importCustomers, exportCustomersUrl, type CustomerImportResult } from "@/lib/api/sales";

export default function CustomerImportPage() {
  const companyId =
    typeof window !== "undefined"
      ? (localStorage.getItem("company_id") ?? "")
      : "";
  const token =
    typeof window !== "undefined"
      ? (localStorage.getItem("access_token") ?? undefined)
      : undefined;

  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<CustomerImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload() {
    if (!file || !companyId) return;
    setUploading(true);
    setError(null);
    setResult(null);
    try {
      const res = await importCustomers(companyId, file, token);
      setResult(res.data!);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setUploading(false);
    }
  }

  function downloadTemplate() {
    const csv = [
      "customer_code,legal_name,trading_name,customer_type,category_code,group_code,currency_code,payment_term,tax_number,website,credit_limit,rating,notes",
      "CUST-001,Example Corp,Example,COMPANY,RETAIL,,USD,NET30,,https://example.com,10000,A,Key customer",
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "customers_import_template.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Link href="../customers" className="text-sm text-indigo-600 hover:underline">
          ← Customers
        </Link>
      </div>

      <h1 className="text-2xl font-bold text-gray-900 mb-6">Bulk Import Customers</h1>

      {/* Instructions */}
      <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
        <p className="font-medium mb-2">Instructions</p>
        <ol className="list-decimal list-inside space-y-1">
          <li>Download the CSV template below.</li>
          <li>Fill in your customer data (one row per customer).</li>
          <li>Upload the completed file.</li>
          <li>Required columns: <code className="bg-blue-100 px-1 rounded">customer_code</code>, <code className="bg-blue-100 px-1 rounded">legal_name</code>, <code className="bg-blue-100 px-1 rounded">customer_type</code>.</li>
        </ol>
        <button
          onClick={downloadTemplate}
          className="mt-3 inline-flex items-center gap-1 text-blue-700 font-medium hover:underline"
        >
          ↓ Download template
        </button>
      </div>

      {/* Export existing */}
      <div className="mb-6 p-3 bg-gray-50 border border-gray-200 rounded-lg flex items-center justify-between text-sm">
        <span className="text-gray-700">Export existing customers as CSV</span>
        <a
          href={exportCustomersUrl(companyId)}
          className="text-indigo-600 hover:underline font-medium"
        >
          Export all →
        </a>
      </div>

      {/* File upload */}
      <div className="space-y-4">
        <div
          className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-indigo-400 transition-colors"
          onClick={() => fileRef.current?.click()}
        >
          {file ? (
            <div>
              <p className="text-sm font-medium text-gray-900">{file.name}</p>
              <p className="text-xs text-gray-500 mt-1">{(file.size / 1024).toFixed(1)} KB</p>
            </div>
          ) : (
            <div>
              <p className="text-sm text-gray-500">Click to select a CSV file</p>
              <p className="text-xs text-gray-400 mt-1">or drag and drop</p>
            </div>
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
          className="w-full py-2.5 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
        >
          {uploading ? "Uploading…" : "Upload & Import"}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="mt-6 space-y-3">
          <h3 className="font-medium text-gray-900">Import Complete</h3>
          <div className="grid grid-cols-3 gap-3">
            <div className="p-3 bg-green-50 border border-green-200 rounded-lg text-center">
              <p className="text-2xl font-bold text-green-700">{result.imported}</p>
              <p className="text-xs text-green-600 mt-1">Imported</p>
            </div>
            <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-center">
              <p className="text-2xl font-bold text-yellow-700">{result.skipped}</p>
              <p className="text-xs text-yellow-600 mt-1">Skipped</p>
            </div>
            <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg text-center">
              <p className="text-2xl font-bold text-gray-700">{result.total_rows}</p>
              <p className="text-xs text-gray-500 mt-1">Total Rows</p>
            </div>
          </div>
          {result.errors.length > 0 && (
            <div>
              <p className="text-sm font-medium text-red-700 mb-2">
                {result.errors.length} error(s):
              </p>
              <div className="max-h-48 overflow-y-auto border border-red-200 rounded-lg divide-y divide-red-100">
                {result.errors.map((e, i) => (
                  <div key={i} className="px-3 py-2 text-xs text-red-700">
                    <span className="font-medium">Row {e.row}:</span> {e.message}
                  </div>
                ))}
              </div>
            </div>
          )}
          <Link
            href="../customers"
            className="inline-block mt-2 text-sm text-indigo-600 hover:underline"
          >
            ← Back to Customers
          </Link>
        </div>
      )}
    </div>
  );
}
