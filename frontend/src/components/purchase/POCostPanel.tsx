"use client";

import { useEffect, useState } from "react";

interface POCostSummary {
  po_id: string;
  po_number: string;
  supplier_id: string | null;
  status: string;
  currency_code: string;
  subtotal: string;
  total_charges: string;
  total_discounts: string;
  tax_amount: string;
  total: string;
}

interface POCostPanelProps {
  companyId: string;
  poId: string;
}

export default function POCostPanel({ companyId, poId }: POCostPanelProps) {
  const [summary, setSummary] = useState<POCostSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchSummary = async () => {
      setLoading(true);
      try {
        const res = await fetch(
          `/api/v1/companies/${companyId}/purchase/purchase-orders/${poId}/cost-summary`,
          { credentials: "include" }
        );
        if (!res.ok) throw new Error(await res.text());
        const json = await res.json();
        setSummary(json.data);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    };
    if (companyId && poId) fetchSummary();
  }, [companyId, poId]);

  if (loading) return <div className="text-gray-500 text-sm">Loading cost summary...</div>;
  if (error) return <div className="text-red-600 text-sm">{error}</div>;
  if (!summary) return null;

  const rows: { label: string; value: string; bold?: boolean; sign?: "+" | "-" }[] = [
    { label: "Subtotal", value: summary.subtotal },
    { label: "Additional Charges", value: summary.total_charges, sign: "+" },
    { label: "Discounts", value: `(${summary.total_discounts})`, sign: "-" },
    { label: "Tax Amount", value: summary.tax_amount, sign: "+" },
    { label: "Total", value: summary.total, bold: true },
  ];

  return (
    <div className="border rounded p-4 bg-white">
      <h3 className="text-sm font-semibold mb-3 text-gray-700">Cost Breakdown</h3>
      <div className="text-xs text-gray-500 mb-3">Currency: {summary.currency_code}</div>
      <dl className="divide-y">
        {rows.map((row) => (
          <div
            key={row.label}
            className={`flex justify-between py-1.5 text-sm ${row.bold ? "font-semibold border-t-2 border-gray-300 mt-1 pt-2" : ""}`}
          >
            <dt className="text-gray-600">{row.label}</dt>
            <dd className={`font-mono ${row.bold ? "text-gray-900" : "text-gray-700"}`}>
              {summary.currency_code} {row.value}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
