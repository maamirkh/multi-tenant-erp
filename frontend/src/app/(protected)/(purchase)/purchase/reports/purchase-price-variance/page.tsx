"use client";

/**
 * RPT-10: Purchase Price Variance — T226
 */

import { useEffect, useState } from "react";
import { getAccessToken } from "@/lib/auth/tokenStorage";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface PPVRow {
  gr_line_id: string;
  gr_id: string;
  po_line_id: string;
  product_id: string | null;
  quantity_received: string;
  gr_unit_cost: string;
  ppv_amount: string;
  ppv_percentage: string;
  supplier_id: string;
  gr_number: string;
  received_at: string | null;
}

export default function PPVReportPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";

  const [rows, setRows] = useState<PPVRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const p = new URLSearchParams();
      if (dateFrom) p.set("date_from", dateFrom);
      if (dateTo) p.set("date_to", dateTo);
      const qs = p.toString() ? `?${p.toString()}` : "";
      const res = await fetch(`${API_BASE}/api/v1/companies/${companyId}/purchase/reports/purchase-price-variance${qs}`, { headers: { Authorization: `Bearer ${getAccessToken()}` } });
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

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Purchase Price Variance</h1>
        <p className="text-sm text-gray-500">RPT-10 — GR vs PO unit cost variance per line</p>
      </div>

      <div className="mb-4 flex flex-wrap gap-3">
        <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="rounded border border-gray-300 px-2 py-1 text-sm" />
        <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="rounded border border-gray-300 px-2 py-1 text-sm" />
        <button onClick={fetchData} className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700">Apply</button>
      </div>

      {loading && <div className="text-sm text-gray-400">Loading…</div>}
      {error && <div className="rounded bg-red-50 p-3 text-sm text-red-600">{error}</div>}

      {!loading && !error && (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                {["GR Number","Qty Received","GR Unit Cost","PPV Amount","PPV %","Received At"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {rows.map((r) => {
                const ppv = parseFloat(r.ppv_amount);
                const ppvClass = ppv > 0 ? "text-red-600 font-semibold" : ppv < 0 ? "text-green-600 font-semibold" : "text-gray-600";
                return (
                  <tr key={r.gr_line_id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 font-mono text-xs">{r.gr_number}</td>
                    <td className="px-4 py-2 text-right">{r.quantity_received}</td>
                    <td className="px-4 py-2 text-right">{parseFloat(r.gr_unit_cost).toFixed(4)}</td>
                    <td className={`px-4 py-2 text-right ${ppvClass}`}>{ppv >= 0 ? "+" : ""}{parseFloat(r.ppv_amount).toFixed(2)}</td>
                    <td className={`px-4 py-2 text-right ${ppvClass}`}>{r.ppv_percentage}%</td>
                    <td className="px-4 py-2 text-gray-500">{r.received_at ? r.received_at.substring(0, 10) : "—"}</td>
                  </tr>
                );
              })}
              {rows.length === 0 && (
                <tr><td colSpan={6} className="py-8 text-center text-gray-400">No PPV data found.</td></tr>
              )}
            </tbody>
          </table>
          <div className="border-t border-gray-200 bg-gray-50 px-4 py-2 text-xs text-gray-500">{rows.length} lines</div>
        </div>
      )}
    </div>
  );
}
