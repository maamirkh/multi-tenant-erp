"use client";

import { useParams, useRouter } from "next/navigation";
import { useRef, useState } from "react";

interface ImportJobData {
  id: string;
  status: string;
  file_name: string;
  total_rows: number;
  processed_rows: number;
  failed_rows: number;
  error_rows: Array<{ row_number: number; product_code: string; errors: string[] }> | null;
  error_message: string | null;
}

type ImportPhase = "idle" | "uploading" | "polling" | "done" | "error";

export default function ProductImportPage() {
  const params = useParams<{ company_id: string }>();
  const companyId = params?.company_id;
  const router = useRouter();

  const fileRef = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<ImportPhase>("idle");
  const [job, setJob] = useState<ImportJobData | null>(null);
  const [globalError, setGlobalError] = useState<string | null>(null);

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setPhase("uploading");
    setGlobalError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const resp = await fetch(
        `/api/v1/companies/${companyId}/inventory/products/import`,
        { method: "POST", body: formData }
      );
      if (!resp.ok) throw new Error(await resp.text());
      const result = await resp.json();
      setJob(result.data);
      setPhase("done");
    } catch (err) {
      setGlobalError(err instanceof Error ? err.message : "Upload failed");
      setPhase("error");
    }
  };

  const statusColor = (status: string) => {
    switch (status) {
      case "COMPLETED":
        return "text-green-700 bg-green-50 border-green-200";
      case "FAILED_WITH_ERRORS":
        return "text-yellow-700 bg-yellow-50 border-yellow-200";
      case "FAILED":
        return "text-red-700 bg-red-50 border-red-200";
      case "PROCESSING":
        return "text-blue-700 bg-blue-50 border-blue-200";
      default:
        return "text-gray-600 bg-gray-50 border-gray-200";
    }
  };

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <div className="mb-6 flex items-center gap-3">
        <button
          onClick={() => router.back()}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          ← Back
        </button>
        <h1 className="text-xl font-semibold text-gray-900">Bulk Product Import</h1>
      </div>

      {/* Instructions */}
      <div className="mb-6 rounded-lg border border-blue-100 bg-blue-50 p-4 text-sm text-blue-800">
        <p className="font-medium mb-1">CSV Format Required</p>
        <p className="font-mono text-xs">
          product_code, name, base_uom_code, product_type, description, cost_price, ...
        </p>
        <p className="mt-2 text-xs text-blue-600">
          Required columns: <strong>product_code</strong>, <strong>name</strong>,{" "}
          <strong>base_uom_code</strong>
        </p>
      </div>

      {/* Upload area */}
      {phase === "idle" || phase === "error" ? (
        <div className="space-y-4">
          <div
            className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-gray-300 py-10 hover:border-blue-400"
            onClick={() => fileRef.current?.click()}
          >
            <p className="text-sm text-gray-500">Click to select CSV file</p>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={() => {}}
            />
          </div>

          {globalError && (
            <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {globalError}
            </div>
          )}

          <button
            onClick={handleUpload}
            className="w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            Upload and Import
          </button>
        </div>
      ) : phase === "uploading" ? (
        <div className="flex items-center justify-center py-12 text-sm text-gray-500">
          <span className="animate-pulse">Processing import…</span>
        </div>
      ) : job ? (
        <div className="space-y-4">
          {/* Job summary */}
          <div
            className={`rounded-lg border px-4 py-3 text-sm ${statusColor(job.status)}`}
          >
            <div className="flex items-center justify-between">
              <span className="font-medium">{job.status.replace(/_/g, " ")}</span>
              <span className="text-xs opacity-70">{job.file_name}</span>
            </div>
            <div className="mt-2 flex gap-4 text-xs">
              <span>Total rows: {job.total_rows}</span>
              <span>Imported: {job.processed_rows}</span>
              <span>Failed: {job.failed_rows}</span>
            </div>
          </div>

          {/* Error message */}
          {job.error_message && (
            <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {job.error_message}
            </div>
          )}

          {/* Row-level errors */}
          {job.error_rows && job.error_rows.length > 0 && (
            <div>
              <p className="mb-2 text-sm font-medium text-gray-700">
                Row errors ({job.error_rows.length}):
              </p>
              <div className="max-h-60 overflow-y-auto rounded border border-gray-200">
                <table className="min-w-full text-xs">
                  <thead className="bg-gray-50 text-gray-600">
                    <tr>
                      <th className="px-3 py-2 text-left">Row</th>
                      <th className="px-3 py-2 text-left">Code</th>
                      <th className="px-3 py-2 text-left">Errors</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {job.error_rows.map((row) => (
                      <tr key={row.row_number} className="bg-white">
                        <td className="px-3 py-1.5 text-gray-500">{row.row_number}</td>
                        <td className="px-3 py-1.5 font-mono">{row.product_code || "—"}</td>
                        <td className="px-3 py-1.5 text-red-600">
                          {row.errors.join("; ")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <button
            onClick={() => {
              setPhase("idle");
              setJob(null);
              if (fileRef.current) fileRef.current.value = "";
            }}
            className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
          >
            Import Another File
          </button>
        </div>
      ) : null}
    </div>
  );
}
