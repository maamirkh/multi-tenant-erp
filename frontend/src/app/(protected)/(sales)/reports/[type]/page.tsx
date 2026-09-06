"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getSalesReport,
  exportSalesReport,
  ReportResponse,
} from "@/lib/api/sales";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function toTitleCase(str: string): string {
  return str.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// ---------------------------------------------------------------------------
// Report table
// ---------------------------------------------------------------------------

function ReportTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 py-12 text-center text-sm text-gray-400">
        No data for the selected filters.
      </div>
    );
  }
  const firstRow = rows[0];
  if (!firstRow) return null;
  const headers = Object.keys(firstRow);
  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            {headers.map((h) => (
              <th
                key={h}
                className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide"
              >
                {toTitleCase(h)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {rows.map((row, rowIdx) => (
            <tr key={rowIdx} className="hover:bg-gray-50">
              {headers.map((h) => (
                <td key={h} className="px-4 py-2 text-gray-700 whitespace-nowrap">
                  {row[h] === null || row[h] === undefined
                    ? "—"
                    : String(row[h])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ReportDetailPage() {
  const params = useParams();
  const router = useRouter();
  const reportType = (params?.type as string) ?? "";

  const [report, setReport] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [companyId, setCompanyId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(0);
  const limit = 50;

  function load(cId: string, from: string, to: string, pg: number) {
    setLoading(true);
    getSalesReport(cId, reportType, {
      ...(from ? { date_from: from } : {}),
      ...(to ? { date_to: to } : {}),
      limit,
      offset: pg * limit,
    })
      .then((res) => {
        setReport(res.data);
        setError(null);
      })
      .catch((err) => setError(err?.message ?? "Failed to load report"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    const stored = localStorage.getItem("companyId") ?? "";
    setCompanyId(stored);
    if (stored) load(stored, dateFrom, dateTo, 0);
    else {
      setLoading(false);
      setError("No company selected.");
    }
  }, []);

  async function handleExport(fmt: "csv" | "excel") {
    if (!companyId) return;
    try {
      const blob = await exportSalesReport(companyId, reportType, {
        ...(dateFrom ? { date_from: dateFrom } : {}),
        ...(dateTo ? { date_to: dateTo } : {}),
        limit: 1000,
        fmt,
      });
      const ext = fmt === "csv" ? "csv" : "xlsx";
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${reportType}.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert("Export failed");
    }
  }

  function handleFilter(e: React.FormEvent) {
    e.preventDefault();
    setPage(0);
    load(companyId, dateFrom, dateTo, 0);
  }

  const totalPages = report ? Math.ceil(report.total / limit) : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => router.back()}
            className="text-sm text-blue-600 hover:underline mb-1"
          >
            ← Back to Reports
          </button>
          <h1 className="text-2xl font-bold text-gray-900">
            {toTitleCase(reportType)}
          </h1>
          {report && (
            <p className="text-sm text-gray-500 mt-1">
              {report.total} row(s) total
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => handleExport("csv")}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Export CSV
          </button>
          <button
            onClick={() => handleExport("excel")}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Export Excel
          </button>
        </div>
      </div>

      {/* Filters */}
      <form
        onSubmit={handleFilter}
        className="flex flex-wrap gap-4 items-end bg-gray-50 rounded-lg p-4 border border-gray-200"
      >
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Date From
          </label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Date To
          </label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm"
          />
        </div>
        <button
          type="submit"
          className="rounded-md bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        >
          Apply
        </button>
        <button
          type="button"
          onClick={() => {
            setDateFrom("");
            setDateTo("");
            setPage(0);
            load(companyId, "", "", 0);
          }}
          className="rounded-md border border-gray-300 px-4 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-50"
        >
          Clear
        </button>
      </form>

      {/* Content */}
      {loading && (
        <p className="text-sm text-gray-500">Loading…</p>
      )}
      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}
      {report && !loading && <ReportTable rows={report.rows} />}

      {/* Pagination */}
      {report && totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-600">
          <button
            disabled={page === 0}
            onClick={() => {
              const np = page - 1;
              setPage(np);
              load(companyId, dateFrom, dateTo, np);
            }}
            className="rounded-md border border-gray-300 px-3 py-1 disabled:opacity-40"
          >
            Previous
          </button>
          <span>
            Page {page + 1} of {totalPages}
          </span>
          <button
            disabled={page + 1 >= totalPages}
            onClick={() => {
              const np = page + 1;
              setPage(np);
              load(companyId, dateFrom, dateTo, np);
            }}
            className="rounded-md border border-gray-300 px-3 py-1 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
