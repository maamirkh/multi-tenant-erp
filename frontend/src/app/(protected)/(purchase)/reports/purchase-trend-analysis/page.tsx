"use client";

/**
 * RPT-12: Purchase Trend Analysis — T226
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

interface TrendRow {
  period: string;
  gr_count: number;
  total_spend: string;
  avg_spend: string;
}

export default function PurchaseTrendPage() {
  const params = useParams<{ companyId: string }>();
  const companyId = params?.companyId ?? "";

  const [rows, setRows] = useState<TrendRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [granularity, setGranularity] = useState<"monthly" | "quarterly">("monthly");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const p = new URLSearchParams({ granularity });
      if (dateFrom) p.set("date_from", dateFrom);
      if (dateTo) p.set("date_to", dateTo);
      const res = await fetch(`/api/v1/companies/${companyId}/purchase/reports/purchase-trend-analysis?${p.toString()}`, { credentials: "include" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = await res.json();
      setRows(body.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (companyId) fetchData(); }, [companyId, granularity]);

  const maxSpend = Math.max(...rows.map((r) => parseFloat(r.total_spend)), 1);

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Purchase Trend Analysis</h1>
        <p className="text-sm text-gray-500">RPT-12 — Purchase volume and value over time</p>
      </div>

      <div className="mb-4 flex flex-wrap gap-3">
        <select value={granularity} onChange={(e) => setGranularity(e.target.value as "monthly" | "quarterly")} className="rounded border border-gray-300 px-2 py-1 text-sm">
          <option value="monthly">Monthly</option>
          <option value="quarterly">Quarterly</option>
        </select>
        <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="rounded border border-gray-300 px-2 py-1 text-sm" />
        <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="rounded border border-gray-300 px-2 py-1 text-sm" />
        <button onClick={fetchData} className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700">Apply</button>
      </div>

      {loading && <div className="text-sm text-gray-400">Loading…</div>}
      {error && <div className="rounded bg-red-50 p-3 text-sm text-red-600">{error}</div>}

      {!loading && !error && rows.length > 0 && (
        <>
          {/* Simple bar chart */}
          <div className="mb-6 rounded-lg border border-gray-200 bg-white p-4">
            <div className="mb-2 text-xs font-semibold text-gray-500 uppercase">Total Spend by Period</div>
            <div className="flex items-end gap-2 overflow-x-auto pb-2" style={{ minHeight: "120px" }}>
              {rows.map((r) => {
                const height = Math.max((parseFloat(r.total_spend) / maxSpend) * 100, 2);
                return (
                  <div key={r.period} className="flex flex-col items-center gap-1" style={{ minWidth: "48px" }}>
                    <div className="text-xs font-semibold text-gray-600">${(parseFloat(r.total_spend) / 1000).toFixed(1)}k</div>
                    <div className="w-10 rounded-t bg-blue-500" style={{ height: `${height}px` }} title={`$${parseFloat(r.total_spend).toLocaleString()}`} />
                    <div className="text-xs text-gray-400 whitespace-nowrap">{r.period}</div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  {["Period","GR Count","Total Spend","Avg Spend per GR"].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {rows.map((r) => (
                  <tr key={r.period} className="hover:bg-gray-50">
                    <td className="px-4 py-2 font-semibold">{r.period}</td>
                    <td className="px-4 py-2">{r.gr_count}</td>
                    <td className="px-4 py-2 text-right">${parseFloat(r.total_spend).toLocaleString("en-US", { minimumFractionDigits: 2 })}</td>
                    <td className="px-4 py-2 text-right">${parseFloat(r.avg_spend).toLocaleString("en-US", { minimumFractionDigits: 2 })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="border-t border-gray-200 bg-gray-50 px-4 py-2 text-xs text-gray-500">{rows.length} periods</div>
          </div>
        </>
      )}

      {!loading && !error && rows.length === 0 && (
        <div className="py-12 text-center text-gray-400">No trend data available. Confirm goods receipts to generate trend data.</div>
      )}
    </div>
  );
}
