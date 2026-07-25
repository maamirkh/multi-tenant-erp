"use client";

/**
 * Reorder Suggestions — Phase 8 Inventory Intelligence
 * Displays auto-generated reorder suggestions triggered by LOW_STOCK alerts.
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

type SuggestionStatus = "PENDING" | "ACKNOWLEDGED" | "CONVERTED";

interface ReorderSuggestion {
  id: string;
  product_id: string;
  warehouse_id: string;
  suggested_quantity: string;
  triggered_by_alert_id: string | null;
  status: SuggestionStatus;
  created_at: string;
}

const STATUS_BADGE: Record<SuggestionStatus, string> = {
  PENDING: "bg-yellow-100 text-yellow-800",
  ACKNOWLEDGED: "bg-blue-100 text-blue-700",
  CONVERTED: "bg-green-100 text-green-700",
};

export default function SuggestionsPage() {
  const params = useParams<{ company_id: string }>();
  const companyId = params?.company_id;

  const [suggestions, setSuggestions] = useState<ReorderSuggestion[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acknowledging, setAcknowledging] = useState<string | null>(null);

  function fetchSuggestions() {
    if (!companyId) return;
    setLoading(true);
    const qp = new URLSearchParams({ limit: "100" });
    if (statusFilter) qp.set("suggestion_status", statusFilter);
    fetch(`/api/v1/companies/${companyId}/inventory/suggestions?${qp}`, {
      credentials: "include",
    })
      .then((r) => r.json())
      .then((body) => {
        setSuggestions(body.data ?? []);
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load suggestions.");
        setLoading(false);
      });
  }

  useEffect(() => {
    fetchSuggestions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId, statusFilter]);

  async function acknowledgeSuggestion(id: string) {
    if (!companyId) return;
    setAcknowledging(id);
    try {
      await fetch(
        `/api/v1/companies/${companyId}/inventory/suggestions/${id}/acknowledge`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ notes: null }),
        }
      );
      fetchSuggestions();
    } catch {
      setError("Failed to acknowledge suggestion.");
    } finally {
      setAcknowledging(null);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Reorder Suggestions</h1>
      </div>

      <div className="flex gap-4">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border rounded px-3 py-2 text-sm"
        >
          <option value="">All Statuses</option>
          <option value="PENDING">Pending</option>
          <option value="ACKNOWLEDGED">Acknowledged</option>
          <option value="CONVERTED">Converted</option>
        </select>
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 p-4 rounded">{error}</div>
      )}

      {loading ? (
        <p className="text-gray-500">Loading suggestions…</p>
      ) : suggestions.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          No reorder suggestions at this time.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Product</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Warehouse</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Suggested Qty</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Generated</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {suggestions.map((s) => (
                <tr key={s.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">
                    {s.product_id.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">
                    {s.warehouse_id.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-3 font-semibold">{s.suggested_quantity}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${STATUS_BADGE[s.status]}`}
                    >
                      {s.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(s.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    {s.status === "PENDING" && (
                      <button
                        onClick={() => acknowledgeSuggestion(s.id)}
                        disabled={acknowledging === s.id}
                        className="text-xs text-indigo-600 hover:text-indigo-800 disabled:opacity-50"
                      >
                        {acknowledging === s.id ? "Acknowledging…" : "Acknowledge"}
                      </button>
                    )}
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
