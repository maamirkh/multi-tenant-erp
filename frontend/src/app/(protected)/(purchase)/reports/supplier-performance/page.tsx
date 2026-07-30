"use client";

/**
 * RPT-06: Supplier Performance — T226
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

interface SupplierPerfRow {
  supplier_id: string;
  total_grs: number;
  on_time_rate: number;
  fill_rate: number;
  rejection_rate: number;
  composite_rating: number;
}

function RatingBar({ value }: { value: number }) {
  const color = value >= 80 ? "bg-green-500" : value >= 60 ? "bg-yellow-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 rounded-full bg-gray-100 h-2">
        <div className={`${color} h-2 rounded-full`} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
      <span className="text-xs">{value}%</span>
    </div>
  );
}

export default function SupplierPerformancePage() {
  const params = useParams<{ companyId: string }>();
  const companyId = params?.companyId ?? "";

  const [rows, setRows] = useState<SupplierPerfRow[]>([]);
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
      const res = await fetch(`/api/v1/companies/${companyId}/purchase/reports/supplier-performance${qs}`, { credentials: "include" });
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
        <h1 className="text-2xl font-bold text-gray-900">Supplier Performance</h1>
        <p className="text-sm text-gray-500">RPT-06 — On-time, fill rate, and rejection analysis</p>
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
                {["Supplier ID","Total GRs","On-Time Rate","Fill Rate","Rejection Rate","Composite Rating"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {rows.map((r) => (
                <tr key={r.supplier_id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 font-mono text-xs text-gray-500">{r.supplier_id}</td>
                  <td className="px-4 py-2">{r.total_grs}</td>
                  <td className="px-4 py-2"><RatingBar value={r.on_time_rate} /></td>
                  <td className="px-4 py-2"><RatingBar value={r.fill_rate} /></td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-2">
                      <div className="w-20 rounded-full bg-gray-100 h-2">
                        <div className={`${r.rejection_rate > 10 ? "bg-red-400" : "bg-green-500"} h-2 rounded-full`} style={{ width: `${Math.min(r.rejection_rate, 100)}%` }} />
                      </div>
                      <span className="text-xs">{r.rejection_rate}%</span>
                    </div>
                  </td>
                  <td className="px-4 py-2"><RatingBar value={r.composite_rating} /></td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={6} className="py-8 text-center text-gray-400">No data available.</td></tr>
              )}
            </tbody>
          </table>
          <div className="border-t border-gray-200 bg-gray-50 px-4 py-2 text-xs text-gray-500">{rows.length} suppliers</div>
        </div>
      )}
    </div>
  );
}
