"use client";

/**
 * Inventory KPI Dashboard — Phase 9 Reporting Foundation
 * Displays all 10 inventory KPIs with metric cards.
 */

import { useEffect, useState } from "react";
import { getAccessToken } from "@/lib/auth/tokenStorage";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface KPIData {
  inventory_turnover: string;
  average_inventory_value: string;
  inventory_accuracy: string;
  dead_stock_percentage: string;
  stock_accuracy_percentage: string;
  warehouse_efficiency: string;
  total_inventory_value: string;
  reorder_frequency: string;
  stockout_rate: string;
  overstock_rate: string;
  as_of: string;
  period_days: number;
}

interface KPICard {
  key: keyof KPIData;
  label: string;
  unit: string;
  description: string;
  trend?: "higher-better" | "lower-better";
}

const KPI_CARDS: KPICard[] = [
  {
    key: "total_inventory_value",
    label: "Total Inventory Value",
    unit: "currency",
    description: "Current total value across all warehouses",
    trend: "higher-better",
  },
  {
    key: "inventory_turnover",
    label: "Inventory Turnover",
    unit: "x",
    description: "COGS ÷ Average Inventory in period",
    trend: "higher-better",
  },
  {
    key: "average_inventory_value",
    label: "Average Inventory Value",
    unit: "currency",
    description: "Average value over the lookback period",
  },
  {
    key: "inventory_accuracy",
    label: "Inventory Accuracy",
    unit: "%",
    description: "% of positions with validated cost",
    trend: "higher-better",
  },
  {
    key: "stock_accuracy_percentage",
    label: "Stock Accuracy",
    unit: "%",
    description: "% of positions with stock on hand",
    trend: "higher-better",
  },
  {
    key: "dead_stock_percentage",
    label: "Dead Stock %",
    unit: "%",
    description: "% of inventory value with no movement",
    trend: "lower-better",
  },
  {
    key: "stockout_rate",
    label: "Stockout Rate",
    unit: "%",
    description: "% of positions with zero stock",
    trend: "lower-better",
  },
  {
    key: "overstock_rate",
    label: "Overstock Rate",
    unit: "%",
    description: "% of capped positions exceeding maximum stock",
    trend: "lower-better",
  },
  {
    key: "warehouse_efficiency",
    label: "Warehouse Efficiency",
    unit: "%",
    description: "% of warehouses currently active",
    trend: "higher-better",
  },
  {
    key: "reorder_frequency",
    label: "Reorder Frequency",
    unit: "suggestions",
    description: "Number of reorder suggestions in the period",
  },
];

export default function KPIDashboardPage() {
  const companyId =
    typeof window !== "undefined"
      ? localStorage.getItem("erp_active_company_id") ?? ""
      : "";
  const [periodDays, setPeriodDays] = useState(90);
  const [kpis, setKpis] = useState<KPIData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadKpis();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId, periodDays]);

  async function loadKpis() {
    if (!companyId) return;
    setLoading(true);
    setError(null);
    try {
      const token = getAccessToken();
      const res = await fetch(
        `${API_BASE}/api/v1/companies/${companyId}/inventory/kpis?period_days=${periodDays}`,
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setKpis(json.data ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load KPIs");
    } finally {
      setLoading(false);
    }
  }

  function formatValue(key: keyof KPIData, value: string | number): string {
    if (key === "period_days") return String(value);
    if (key === "as_of") return new Date(value as string).toLocaleString();
    const num = parseFloat(value as string);
    if (isNaN(num)) return String(value);
    const card = KPI_CARDS.find((c) => c.key === key);
    if (card?.unit === "currency") {
      return num.toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
    }
    if (card?.unit === "%" || card?.unit === "x") {
      return num.toFixed(2);
    }
    return num.toString();
  }

  function trendColor(card: KPICard, value: string): string {
    if (!card.trend) return "text-gray-900";
    const num = parseFloat(value);
    if (isNaN(num)) return "text-gray-900";
    if (card.trend === "higher-better") {
      return num >= 80 ? "text-green-700" : num >= 50 ? "text-yellow-700" : "text-red-700";
    }
    return num <= 10 ? "text-green-700" : num <= 30 ? "text-yellow-700" : "text-red-700";
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">KPI Dashboard</h1>
          {kpis && (
            <p className="text-sm text-gray-500 mt-1">
              As of {new Date(kpis.as_of).toLocaleString()} &middot; {kpis.period_days}-day
              lookback
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-600">Period:</label>
          <select
            value={periodDays}
            onChange={(e) => setPeriodDays(Number(e.target.value))}
            className="border rounded px-3 py-2 text-sm"
          >
            <option value={30}>30 days</option>
            <option value={60}>60 days</option>
            <option value={90}>90 days</option>
            <option value={180}>180 days</option>
            <option value={365}>1 year</option>
          </select>
          <button
            onClick={loadKpis}
            disabled={loading}
            className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Loading..." : "Refresh"}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-4 text-red-700 text-sm">
          {error}
        </div>
      )}

      {loading && !kpis && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="border rounded-lg p-4 animate-pulse bg-gray-50 h-28" />
          ))}
        </div>
      )}

      {kpis && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {KPI_CARDS.map((card) => {
            const rawValue = kpis[card.key];
            const displayValue = formatValue(card.key, rawValue as string);
            return (
              <div
                key={card.key}
                className="border rounded-lg p-4 bg-white shadow-sm flex flex-col gap-1"
              >
                <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">
                  {card.label}
                </p>
                <p className={`text-2xl font-bold ${trendColor(card, String(rawValue))}`}>
                  {displayValue}
                  <span className="text-sm font-normal text-gray-400 ml-1">
                    {card.unit !== "currency" ? card.unit : ""}
                  </span>
                </p>
                <p className="text-xs text-gray-400">{card.description}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
