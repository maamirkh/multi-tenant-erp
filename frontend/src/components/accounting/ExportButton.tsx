"use client";

import { useState } from "react";
import { downloadReportExport } from "@/lib/api/accounting";

type ExportFormat = "pdf" | "excel" | "csv";

interface ExportFormatOption {
  value: ExportFormat;
  label: string;
}

const DEFAULT_FORMATS: ExportFormatOption[] = [
  { value: "pdf", label: "Export PDF" },
  { value: "excel", label: "Export Excel" },
];

interface ExportButtonProps {
  companyId: string;
  reportPath: string;
  filename: string;
  extraParams?: Record<string, string>;
  disabled?: boolean;
  /** Which formats to offer. Defaults to PDF + Excel (existing /reports/* behavior). */
  formats?: ExportFormatOption[];
}

/**
 * Reusable export trigger for any endpoint that accepts ?format=pdf|excel|csv
 * and streams back a binary attachment (e.g. /reports/*, the audit log export).
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T268, T281
 */
export default function ExportButton({
  companyId,
  reportPath,
  filename,
  extraParams,
  disabled,
  formats = DEFAULT_FORMATS,
}: ExportButtonProps) {
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleExport(format: ExportFormat) {
    setExporting(format);
    setError(null);
    try {
      await downloadReportExport(companyId, reportPath, format, filename, extraParams);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(null);
    }
  }

  return (
    <div className="flex items-center gap-2">
      {formats.map((f) => (
        <button
          key={f.value}
          type="button"
          onClick={() => handleExport(f.value)}
          disabled={disabled || exporting !== null}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {exporting === f.value ? "Exporting..." : f.label}
        </button>
      ))}
      {error && <span className="text-xs text-red-600">{error}</span>}
    </div>
  );
}
