"use client";

/**
 * ReportViewer — reusable tabular report component with sorting and export.
 * Phase 9 Reporting Foundation.
 */

import { useState } from "react";

interface ReportViewerProps {
  rows: Record<string, unknown>[];
  onExport?: (format: "csv" | "xlsx") => void;
  exportLoading?: boolean;
  caption?: string;
}

export default function ReportViewer({
  rows,
  onExport,
  exportLoading = false,
  caption,
}: ReportViewerProps) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortAsc, setSortAsc] = useState(true);

  if (rows.length === 0) {
    return <p className="text-sm text-gray-500 py-4">No data available for this report.</p>;
  }

  const firstRow = rows[0];
  if (!firstRow) return null;
  const headers = Object.keys(firstRow);

  function handleSort(key: string) {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
  }

  const sorted = sortKey
    ? [...rows].sort((a, b) => {
        const av = a[sortKey];
        const bv = b[sortKey];
        if (av === null || av === undefined) return 1;
        if (bv === null || bv === undefined) return -1;
        const cmp =
          typeof av === "number" && typeof bv === "number"
            ? av - bv
            : String(av).localeCompare(String(bv));
        return sortAsc ? cmp : -cmp;
      })
    : rows;

  return (
    <div className="space-y-3">
      {(caption || onExport) && (
        <div className="flex items-center justify-between">
          {caption && <h3 className="text-sm font-semibold text-gray-700">{caption}</h3>}
          {onExport && (
            <div className="flex gap-2">
              <button
                onClick={() => onExport("csv")}
                disabled={exportLoading}
                className="border border-gray-300 px-3 py-1 rounded text-sm hover:bg-gray-50 disabled:opacity-50"
              >
                {exportLoading ? "Exporting…" : "CSV"}
              </button>
              <button
                onClick={() => onExport("xlsx")}
                disabled={exportLoading}
                className="border border-gray-300 px-3 py-1 rounded text-sm hover:bg-gray-50 disabled:opacity-50"
              >
                {exportLoading ? "Exporting…" : "Excel"}
              </button>
            </div>
          )}
        </div>
      )}

      <div className="overflow-x-auto rounded border border-gray-200">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              {headers.map((h) => (
                <th
                  key={h}
                  onClick={() => handleSort(h)}
                  className="px-3 py-2 text-left text-xs font-semibold text-gray-600 cursor-pointer hover:bg-gray-100 select-none whitespace-nowrap"
                >
                  {h.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                  {sortKey === h && (
                    <span className="ml-1 text-blue-500">{sortAsc ? "▲" : "▼"}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, i) => (
              <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                {headers.map((h) => (
                  <td key={h} className="px-3 py-2 border-t border-gray-100 text-gray-700 whitespace-nowrap">
                    {formatCell(row[h])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        <div className="px-3 py-2 text-xs text-gray-400 bg-gray-50 border-t">
          {sorted.length} row{sorted.length !== 1 ? "s" : ""}
        </div>
      </div>
    </div>
  );
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}T/.test(value)) {
    return new Date(value).toLocaleString();
  }
  return String(value);
}
