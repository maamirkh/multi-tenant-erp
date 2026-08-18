"use client";

/**
 * RPT-01: Purchase Order Summary — T226
 */

import { useEffect, useState } from "react";
import { getAccessToken } from "@/lib/auth/tokenStorage";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface POSummaryRow {
  po_id: string;
  po_number: string;
  status: string;
  supplier_id: string | null;
  currency_code: string;
  subtotal: string;
  total: string;
  expected_delivery_date: string | null;
  created_at: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-600",
  PENDING_APPROVAL: "bg-yellow-100 text-yellow-700",
  APPROVED: "bg-blue-100 text-blue-700",
  PARTIALLY_RECEIVED: "bg-orange-100 text-orange-700",
  FULLY_RECEIVED: "bg-green-100 text-green-700",
  CLOSED: "bg-gray-200 text-gray-700",
  CANCELLED: "bg-red-100 text-red-700",
};

export default function POSummaryPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";

  const [rows, setRows] = useState<POSummaryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const p = new URLSearchParams();
      if (statusFilter) p.set("status", statusFilter);
      if (dateFrom) p.set("date_from", dateFrom);
      if (dateTo) p.set("date_to", dateTo);
      const qs = p.toString() ? `?${p.toString()}` : "";
      const res = await fetch(`${API_BASE}/api/v1/companies/${companyId}/purchase/reports/purchase-order-summary${qs}`, { headers: { Authorization: `Bearer ${getAccessToken()}` } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = await res.json();
      setRows(body.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (companyId) fetchData(); }, [companyId]);

  const handleExport = (fmt: "csv" | "xlsx") => {
    const p = new URLSearchParams();
    if (statusFilter) p.set("status", statusFilter);
    if (dateFrom) p.set("date_from", dateFrom);
    if (dateTo) p.set("date_to", dateTo);
    p.set("fmt", fmt);
    window.open(`/api/v1/companies/${companyId}/purchase/reports/purchase-order-summary?${p.toString()}`, "_blank");
  };

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Purchase Order Summary</h1>
          <p className="text-sm text-gray-500">RPT-01 — All purchase orders</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => handleExport("csv")} className="rounded border border-gray-300 px-3 py-1 text-sm hover:bg-gray-50">Export CSV</button>
          <button onClick={() => handleExport("xlsx")} className="rounded border border-gray-300 px-3 py-1 text-sm hover:bg-gray-50">Export Excel</button>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-3">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded border border-gray-300 px-2 py-1 text-sm">
          <option value="">All Statuses</option>
          {["DRAFT","PENDING_APPROVAL","APPROVED","PARTIALLY_RECEIVED","FULLY_RECEIVED","CLOSED","CANCELLED"].map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="rounded border border-gray-300 px-2 py-1 text-sm" placeholder="From" />
        <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="rounded border border-gray-300 px-2 py-1 text-sm" placeholder="To" />
        <button onClick={fetchData} className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700">Apply</button>
      </div>

      {loading && <div className="text-sm text-gray-400">Loading…</div>}
      {error && <div className="rounded bg-red-50 p-3 text-sm text-red-600">{error}</div>}

      {!loading && !error && (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                {["PO Number","Status","Currency","Subtotal","Total","Delivery Date","Created"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {rows.map((r) => (
                <tr key={r.po_id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 font-mono text-xs">{r.po_number}</td>
                  <td className="px-4 py-2"><span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[r.status] ?? ""}`}>{r.status}</span></td>
                  <td className="px-4 py-2">{r.currency_code}</td>
                  <td className="px-4 py-2 text-right">{parseFloat(r.subtotal).toLocaleString("en-US", { minimumFractionDigits: 2 })}</td>
                  <td className="px-4 py-2 text-right font-semibold">{parseFloat(r.total).toLocaleString("en-US", { minimumFractionDigits: 2 })}</td>
                  <td className="px-4 py-2">{r.expected_delivery_date ?? "—"}</td>
                  <td className="px-4 py-2 text-gray-500">{r.created_at ? r.created_at.substring(0, 10) : "—"}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={7} className="py-8 text-center text-gray-400">No records found.</td></tr>
              )}
            </tbody>
          </table>
          <div className="border-t border-gray-200 bg-gray-50 px-4 py-2 text-xs text-gray-500">{rows.length} records</div>
        </div>
      )}
    </div>
  );
}
