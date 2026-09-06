"use client";

import { useState } from "react";

interface PageProps {
  params: { company_id: string };
}

interface ImportResult {
  total_rows: number;
  created: number;
  skipped: number;
  failed: number;
  errors: Array<{
    row_number: number;
    supplier_code: string | null;
    errors: string[];
  }>;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Supplier bulk import page — CSV upload with progress and error report.
 * Task: T047
 */
export default function SupplierImportPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";
  const [file, setFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const TEMPLATE_COLUMNS = [
    "supplier_code",
    "legal_name",
    "trading_name",
    "supplier_type",
    "currency_code",
    "website",
    "notes",
    "lead_time_days",
    "tax_registration_number",
  ];

  function downloadTemplate() {
    const csv = TEMPLATE_COLUMNS.join(",") + "\n" +
      "SUP-001,Acme Corp,Acme,GOODS,USD,https://acme.com,,30,VAT123\n";
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "supplier_import_template.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleImport(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;

    setImporting(true);
    setError(null);
    setResult(null);

    try {
      const token = typeof window !== "undefined"
        ? localStorage.getItem("access_token")
        : null;

      const formData = new FormData();
      formData.append("file", file);

      const resp = await fetch(
        `${API_BASE}/api/v1/companies/${companyId}/purchase/suppliers/import`,
        {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: formData,
        }
      );

      if (!resp.ok) {
        const body = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(body.detail ?? "Import failed");
      }

      const body = await resp.json();
      setResult(body.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-4 mb-6">
        <a href={`/companies/${companyId}/purchase/suppliers`} className="text-blue-600 hover:underline text-sm">
          &larr; Suppliers
        </a>
        <h1 className="text-2xl font-semibold text-gray-900">Import Suppliers</h1>
      </div>

      {/* Template download */}
      <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded">
        <p className="text-sm text-blue-800 mb-2">
          Download the CSV template with the required columns before importing.
        </p>
        <button
          onClick={downloadTemplate}
          className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
        >
          Download Template
        </button>
        <p className="text-xs text-blue-600 mt-2">
          Required: <strong>supplier_code</strong>, <strong>legal_name</strong>
        </p>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Upload form */}
      <form onSubmit={handleImport} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Select CSV File
          </label>
          <input
            type="file"
            accept=".csv"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            required
            className="block w-full text-sm text-gray-500 file:mr-4 file:py-1.5 file:px-4 file:rounded file:border-0 file:text-sm file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
          />
        </div>
        <button
          type="submit"
          disabled={!file || importing}
          className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {importing ? "Importing..." : "Start Import"}
        </button>
      </form>

      {/* Import result */}
      {result && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold mb-3">Import Result</h2>
          <div className="grid grid-cols-4 gap-3 mb-4">
            <div className="border rounded p-3 text-center">
              <p className="text-2xl font-bold text-gray-900">{result.total_rows}</p>
              <p className="text-xs text-gray-500">Total Rows</p>
            </div>
            <div className="border rounded p-3 text-center bg-green-50">
              <p className="text-2xl font-bold text-green-700">{result.created}</p>
              <p className="text-xs text-green-600">Created</p>
            </div>
            <div className="border rounded p-3 text-center bg-yellow-50">
              <p className="text-2xl font-bold text-yellow-700">{result.skipped}</p>
              <p className="text-xs text-yellow-600">Skipped</p>
            </div>
            <div className="border rounded p-3 text-center bg-red-50">
              <p className="text-2xl font-bold text-red-700">{result.failed}</p>
              <p className="text-xs text-red-600">Failed</p>
            </div>
          </div>

          {result.errors.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">
                Row Errors ({result.errors.length})
              </h3>
              <div className="border rounded overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b">
                      <th className="text-left px-4 py-2 text-gray-600">Row</th>
                      <th className="text-left px-4 py-2 text-gray-600">Code</th>
                      <th className="text-left px-4 py-2 text-gray-600">Errors</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.errors.map((err) => (
                      <tr key={err.row_number} className="border-b">
                        <td className="px-4 py-2 text-gray-500">{err.row_number}</td>
                        <td className="px-4 py-2 font-mono text-xs">{err.supplier_code ?? "-"}</td>
                        <td className="px-4 py-2 text-red-700">{err.errors.join("; ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
