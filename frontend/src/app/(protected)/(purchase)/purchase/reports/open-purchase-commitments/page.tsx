"use client";

/**
 * RPT-11: Open Purchase Commitments — T226
 */

import { useEffect, useState } from "react";
import { getAccessToken } from "@/lib/auth/tokenStorage";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface CommitmentRow {
  po_line_id: string;
  po_id: string;
  po_number: string;
  supplier_id: string;
  currency_code: string;
  product_description: string;
  quantity_ordered: string;
  quantity_received: string;
  open_quantity: string;
  unit_cost: string;
  open_value: string;
  expected_delivery_date: string | null;
}

export default function OpenCommitmentsPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";

  const [rows, setRows] = useState<CommitmentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalOpenValue, setTotalOpenValue] = useState(0);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/companies/${companyId}/purchase/reports/open-purchase-commitments`, { headers: { Authorization: `Bearer ${getAccessToken()}` } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = await res.json();
      setRows(body.data);
      setTotalOpenValue(body.data.reduce((sum: number, r: CommitmentRow) => sum + parseFloat(r.open_value), 0));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (companyId) fetchData(); }, [companyId]);

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Open Purchase Commitments</h1>
          <p className="text-sm text-gray-500">RPT-11 — Outstanding purchase obligations</p>
        </div>
        {!loading && !error && (
          <div className="rounded-lg bg-blue-50 px-4 py-2 text-right">
            <div className="text-xs text-blue-500">Total Open Value</div>
            <div className="text-xl font-bold text-blue-700">${totalOpenValue.toLocaleString("en-US", { minimumFractionDigits: 2 })}</div>
          </div>
        )}
      </div>

      {loading && <div className="text-sm text-gray-400">Loading…</div>}
      {error && <div className="rounded bg-red-50 p-3 text-sm text-red-600">{error}</div>}

      {!loading && !error && (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                {["PO Number","Description","Currency","Ordered","Received","Open Qty","Unit Cost","Open Value","Delivery Date"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {rows.map((r) => (
                <tr key={r.po_line_id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 font-mono text-xs">{r.po_number}</td>
                  <td className="px-4 py-2 max-w-xs truncate">{r.product_description}</td>
                  <td className="px-4 py-2">{r.currency_code}</td>
                  <td className="px-4 py-2 text-right">{r.quantity_ordered}</td>
                  <td className="px-4 py-2 text-right">{r.quantity_received}</td>
                  <td className="px-4 py-2 text-right font-semibold text-orange-600">{r.open_quantity}</td>
                  <td className="px-4 py-2 text-right">{parseFloat(r.unit_cost).toFixed(4)}</td>
                  <td className="px-4 py-2 text-right font-semibold">{parseFloat(r.open_value).toLocaleString("en-US", { minimumFractionDigits: 2 })}</td>
                  <td className="px-4 py-2">{r.expected_delivery_date ?? "—"}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={9} className="py-8 text-center text-gray-400">No open commitments found.</td></tr>
              )}
            </tbody>
          </table>
          <div className="border-t border-gray-200 bg-gray-50 px-4 py-2 text-xs text-gray-500">{rows.length} open lines</div>
        </div>
      )}
    </div>
  );
}
