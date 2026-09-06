"use client";

/**
 * Inventory Alerts Dashboard — Phase 8 Inventory Intelligence
 * Lists LOW_STOCK, OUT_OF_STOCK, SAFETY_STOCK_BREACH, and OVERSTOCK alerts
 * with status filter and inline acknowledge action.
 */

import { useEffect, useState } from "react";
import { getAccessToken } from "@/lib/auth/tokenStorage";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type AlertType = "OUT_OF_STOCK" | "SAFETY_STOCK_BREACH" | "LOW_STOCK" | "OVERSTOCK";
type AlertStatus = "OPEN" | "ACKNOWLEDGED" | "RESOLVED";

interface Alert {
  id: string;
  product_id: string;
  warehouse_id: string;
  alert_type: AlertType;
  status: AlertStatus;
  current_quantity: string;
  threshold_quantity: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  created_at: string;
}

const TYPE_BADGE: Record<AlertType, string> = {
  OUT_OF_STOCK: "bg-red-100 text-red-800",
  SAFETY_STOCK_BREACH: "bg-orange-100 text-orange-800",
  LOW_STOCK: "bg-yellow-100 text-yellow-800",
  OVERSTOCK: "bg-blue-100 text-blue-800",
};

const STATUS_BADGE: Record<AlertStatus, string> = {
  OPEN: "bg-red-100 text-red-700",
  ACKNOWLEDGED: "bg-yellow-100 text-yellow-700",
  RESOLVED: "bg-green-100 text-green-700",
};

export default function AlertsPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";

  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acknowledging, setAcknowledging] = useState<string | null>(null);

  function fetchAlerts() {
    if (!companyId) return;
    setLoading(true);
    const params = new URLSearchParams();
    if (statusFilter) params.set("alert_status", statusFilter);
    if (typeFilter) params.set("alert_type", typeFilter);
    params.set("limit", "100");
    fetch(`${API_BASE}/api/v1/companies/${companyId}/inventory/alerts?${params}`, {
      headers: { Authorization: `Bearer ${getAccessToken()}` },
    })
      .then((r) => r.json())
      .then((body) => {
        setAlerts(body.data ?? []);
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load alerts.");
        setLoading(false);
      });
  }

  useEffect(() => {
    fetchAlerts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId, statusFilter, typeFilter]);

  async function acknowledgeAlert(alertId: string) {
    if (!companyId) return;
    setAcknowledging(alertId);
    try {
      await fetch(
        `${API_BASE}/api/v1/companies/${companyId}/inventory/alerts/${alertId}/acknowledge`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${getAccessToken()}`,
          },
          body: JSON.stringify({ notes: null }),
        }
      );
      fetchAlerts();
    } catch {
      setError("Failed to acknowledge alert.");
    } finally {
      setAcknowledging(null);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Inventory Alerts</h1>
      </div>

      {/* Filters */}
      <div className="flex gap-4 flex-wrap">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border rounded px-3 py-2 text-sm"
        >
          <option value="">All Statuses</option>
          <option value="OPEN">Open</option>
          <option value="ACKNOWLEDGED">Acknowledged</option>
          <option value="RESOLVED">Resolved</option>
        </select>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="border rounded px-3 py-2 text-sm"
        >
          <option value="">All Types</option>
          <option value="OUT_OF_STOCK">Out of Stock</option>
          <option value="SAFETY_STOCK_BREACH">Safety Stock Breach</option>
          <option value="LOW_STOCK">Low Stock</option>
          <option value="OVERSTOCK">Overstock</option>
        </select>
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 p-4 rounded">{error}</div>
      )}

      {loading ? (
        <p className="text-gray-500">Loading alerts…</p>
      ) : alerts.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          No alerts found. Your inventory levels look healthy!
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Type</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Product</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Warehouse</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Qty / Threshold</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Raised</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {alerts.map((a) => (
                <tr key={a.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${TYPE_BADGE[a.alert_type]}`}
                    >
                      {a.alert_type.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">
                    {a.product_id.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">
                    {a.warehouse_id.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-3">
                    {a.current_quantity} / {a.threshold_quantity}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${STATUS_BADGE[a.status]}`}
                    >
                      {a.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(a.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    {a.status === "OPEN" && (
                      <button
                        onClick={() => acknowledgeAlert(a.id)}
                        disabled={acknowledging === a.id}
                        className="text-xs text-indigo-600 hover:text-indigo-800 disabled:opacity-50"
                      >
                        {acknowledging === a.id ? "Acknowledging…" : "Acknowledge"}
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
