"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

interface StockMovement {
  id: string;
  product_id: string;
  warehouse_id: string;
  movement_type: string;
  direction: string;
  quantity: string;
  unit_cost: string | null;
  currency_code: string | null;
  total_cost: string | null;
  reference_type: string | null;
  notes: string | null;
  performed_at: string;
  created_at: string;
}

const DIRECTION_COLORS: Record<string, string> = {
  IN: "text-green-700 bg-green-50",
  OUT: "text-red-700 bg-red-50",
};

const TYPE_LABELS: Record<string, string> = {
  OPENING: "Opening",
  PURCHASE_RECEIPT: "Purchase",
  SALES_ISSUE: "Sale",
  ADJUSTMENT_IN: "Adj. In",
  ADJUSTMENT_OUT: "Adj. Out",
  TRANSFER_IN: "Transfer In",
  TRANSFER_OUT: "Transfer Out",
  RETURN_IN: "Return In",
  RETURN_OUT: "Return Out",
  DAMAGE: "Damage",
  WRITE_OFF: "Write Off",
  SNAPSHOT: "Snapshot",
};

export default function StockLedgerPage() {
  const params = useParams<{ company_id: string }>();
  const companyId = params?.company_id;
  const router = useRouter();

  const [movements, setMovements] = useState<StockMovement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [limit] = useState(100);
  const [offset, setOffset] = useState(0);

  const baseUrl = `/api/v1/companies/${companyId}/inventory/stock`;

  const fetchMovements = async (off = offset) => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${baseUrl}/movements?limit=${limit}&offset=${off}`);
      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();
      setMovements(data.data ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (companyId) fetchMovements(0);
  }, [companyId]);

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8">
        <div className="h-48 animate-pulse rounded-lg bg-gray-100" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => router.back()}
            className="mb-2 text-sm text-gray-500 hover:text-gray-700"
          >
            ← Back
          </button>
          <h1 className="text-xl font-semibold text-gray-900">Stock Ledger</h1>
          <p className="text-sm text-gray-500 mt-1">
            Immutable movement history — {movements.length} entries shown
          </p>
        </div>
      </div>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {movements.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-gray-200 py-12 text-center text-sm text-gray-400">
          No movements recorded yet.
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500">
              <tr>
                <th className="px-4 py-2 text-left">Date</th>
                <th className="px-4 py-2 text-left">Type</th>
                <th className="px-4 py-2 text-left">Dir</th>
                <th className="px-4 py-2 text-left">Product</th>
                <th className="px-4 py-2 text-left">Warehouse</th>
                <th className="px-4 py-2 text-right">Qty</th>
                <th className="px-4 py-2 text-right">Unit Cost</th>
                <th className="px-4 py-2 text-right">Total</th>
                <th className="px-4 py-2 text-left">Reference</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {movements.map((mov) => (
                <tr key={mov.id} className="bg-white hover:bg-gray-50">
                  <td className="px-4 py-2 text-xs text-gray-500 whitespace-nowrap">
                    {formatDate(mov.performed_at)}
                  </td>
                  <td className="px-4 py-2">
                    <span className="text-xs font-medium text-gray-700">
                      {TYPE_LABELS[mov.movement_type] ?? mov.movement_type}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                        DIRECTION_COLORS[mov.direction] ?? "text-gray-600"
                      }`}
                    >
                      {mov.direction}
                    </span>
                  </td>
                  <td className="px-4 py-2 font-mono text-xs text-gray-500">
                    {mov.product_id.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-2 font-mono text-xs text-gray-500">
                    {mov.warehouse_id.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-2 text-right font-medium">{mov.quantity}</td>
                  <td className="px-4 py-2 text-right text-gray-500">
                    {mov.unit_cost
                      ? `${mov.currency_code ?? ""} ${parseFloat(mov.unit_cost).toFixed(2)}`
                      : "—"}
                  </td>
                  <td className="px-4 py-2 text-right text-gray-600">
                    {mov.total_cost ? parseFloat(mov.total_cost).toFixed(2) : "—"}
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-400">
                    {mov.reference_type ?? mov.notes ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {movements.length === limit && (
        <div className="text-center">
          <button
            onClick={() => {
              const next = offset + limit;
              setOffset(next);
              fetchMovements(next);
            }}
            className="rounded border border-gray-300 px-4 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
          >
            Load More
          </button>
        </div>
      )}
    </div>
  );
}
