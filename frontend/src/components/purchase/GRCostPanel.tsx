"use client";

import { useEffect, useState } from "react";

interface PPVLine {
  gr_line_id: string;
  po_line_id: string;
  product_id: string | null;
  quantity_received: string;
  unit_cost: string;
  po_unit_cost: string;
  ppv_amount: string;
  ppv_percentage: string;
}

interface GRCostSummary {
  gr_id: string;
  gr_number: string;
  po_id: string;
  supplier_id: string;
  status: string;
  subtotal: string;
  ppv_lines: PPVLine[];
  total_ppv_amount: string;
}

interface GRCostPanelProps {
  companyId: string;
  grId: string;
}

function ppvColor(ppvPct: string): string {
  const val = parseFloat(ppvPct);
  if (isNaN(val) || val === 0) return "text-gray-600";
  return val > 0 ? "text-red-600" : "text-green-600";
}

export default function GRCostPanel({ companyId, grId }: GRCostPanelProps) {
  const [summary, setSummary] = useState<GRCostSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchSummary = async () => {
      setLoading(true);
      try {
        const res = await fetch(
          `/api/v1/companies/${companyId}/purchase/goods-receipts/${grId}/cost-summary`,
          { credentials: "include" }
        );
        if (!res.ok) throw new Error(await res.text());
        const json = await res.json();
        setSummary(json.data);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    if (companyId && grId) fetchSummary();
  }, [companyId, grId]);

  if (loading) return <div className="text-gray-500 text-sm">Loading GR cost summary...</div>;
  if (error) return <div className="text-red-600 text-sm">{error}</div>;
  if (!summary) return null;

  const totalPPV = parseFloat(summary.total_ppv_amount);

  return (
    <div className="border rounded p-4 bg-white">
      <h3 className="text-sm font-semibold mb-1 text-gray-700">GR Cost &amp; PPV Analysis</h3>
      <div className="text-xs text-gray-500 mb-3">
        GR: {summary.gr_number} &bull; Status: {summary.status}
      </div>

      {/* Header metrics */}
      <div className="grid grid-cols-2 gap-3 mb-4 text-sm">
        <div className="bg-gray-50 rounded p-2">
          <div className="text-gray-500 text-xs">GR Subtotal</div>
          <div className="font-semibold font-mono">{summary.subtotal}</div>
        </div>
        <div className={`rounded p-2 ${totalPPV === 0 ? "bg-gray-50" : totalPPV > 0 ? "bg-red-50" : "bg-green-50"}`}>
          <div className="text-gray-500 text-xs">Total PPV</div>
          <div className={`font-semibold font-mono ${ppvColor(summary.total_ppv_amount)}`}>
            {totalPPV >= 0 ? "+" : ""}{summary.total_ppv_amount}
          </div>
        </div>
      </div>

      {/* PPV per line */}
      {summary.ppv_lines.length === 0 ? (
        <p className="text-gray-500 text-xs">No PPV lines.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-xs border">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-1.5 text-left border-b">Product</th>
                <th className="px-3 py-1.5 text-right border-b">Qty Received</th>
                <th className="px-3 py-1.5 text-right border-b">GR Unit Cost</th>
                <th className="px-3 py-1.5 text-right border-b">PO Unit Cost</th>
                <th className="px-3 py-1.5 text-right border-b">PPV Amount</th>
                <th className="px-3 py-1.5 text-right border-b">PPV %</th>
              </tr>
            </thead>
            <tbody>
              {summary.ppv_lines.map((ln) => (
                <tr key={ln.gr_line_id} className="hover:bg-gray-50">
                  <td className="px-3 py-1.5 border-b font-mono text-xs">
                    {ln.product_id ?? "—"}
                  </td>
                  <td className="px-3 py-1.5 border-b text-right">{ln.quantity_received}</td>
                  <td className="px-3 py-1.5 border-b text-right">{ln.unit_cost}</td>
                  <td className="px-3 py-1.5 border-b text-right">{ln.po_unit_cost}</td>
                  <td className={`px-3 py-1.5 border-b text-right font-mono ${ppvColor(ln.ppv_percentage)}`}>
                    {parseFloat(ln.ppv_amount) >= 0 ? "+" : ""}{ln.ppv_amount}
                  </td>
                  <td className={`px-3 py-1.5 border-b text-right font-mono ${ppvColor(ln.ppv_percentage)}`}>
                    {parseFloat(ln.ppv_percentage) >= 0 ? "+" : ""}{parseFloat(ln.ppv_percentage).toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
