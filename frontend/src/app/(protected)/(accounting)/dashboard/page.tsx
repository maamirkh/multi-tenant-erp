"use client";

import { useCallback, useEffect, useState } from "react";
import KPICard from "@/components/accounting/KPICard";
import {
  FinancialKPIResponse,
  KPIValue,
  getDashboardKPIs,
} from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string };
}

const REFRESH_INTERVAL_MS = 60_000;

type KPIFormat = "currency" | "percent" | "ratio" | "days";

const KPI_FORMATS: Record<string, KPIFormat> = {
  cash_position: "currency",
  accounts_receivable_total: "currency",
  accounts_payable_total: "currency",
  ar_overdue_pct: "percent",
  ap_overdue_pct: "percent",
  revenue_mtd: "currency",
  gross_profit_margin: "percent",
  net_profit_margin: "percent",
  current_ratio: "ratio",
  quick_ratio: "ratio",
  days_sales_outstanding: "days",
  days_payable_outstanding: "days",
  operating_cash_flow: "currency",
  tax_liability_balance: "currency",
};

const KPI_ORDER = [
  "cash_position",
  "accounts_receivable_total",
  "accounts_payable_total",
  "ar_overdue_pct",
  "ap_overdue_pct",
  "revenue_mtd",
  "gross_profit_margin",
  "net_profit_margin",
  "current_ratio",
  "quick_ratio",
  "days_sales_outstanding",
  "days_payable_outstanding",
  "operating_cash_flow",
  "tax_liability_balance",
];

const numberFormatter = new Intl.NumberFormat(undefined, {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function formatKPIValue(key: string, raw: string): string {
  const n = parseFloat(raw);
  if (Number.isNaN(n)) return raw;
  switch (KPI_FORMATS[key]) {
    case "currency":
      return numberFormatter.format(n);
    case "percent":
      return `${numberFormatter.format(n)}%`;
    case "ratio":
      return `${numberFormatter.format(n)}x`;
    case "days":
      return `${numberFormatter.format(n)} days`;
    default:
      return raw;
  }
}

function formatChangePct(changePct: string | null): string | null {
  if (changePct === null) return null;
  const n = parseFloat(changePct);
  if (Number.isNaN(n)) return null;
  const sign = n > 0 ? "+" : "";
  return `${sign}${numberFormatter.format(n)}%`;
}

const PERIOD_STATUS_STYLES: Record<string, string> = {
  OPEN: "bg-emerald-50 text-emerald-700",
  LOCKED: "bg-amber-50 text-amber-700",
  CLOSED: "bg-gray-100 text-gray-600",
};

/**
 * CFO Financial Intelligence & KPI Dashboard: a single-screen view of all
 * 15 KPIs from spec.md §40, refreshed every 60 seconds.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T290
 */
export default function FinancialDashboardPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";

  const [data, setData] = useState<FinancialKPIResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!companyId) return;
    setError(null);
    try {
      const res = await getDashboardKPIs(companyId);
      setData(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load financial KPIs");
    } finally {
      setLoading(false);
    }
  }, [companyId]);

  useEffect(() => {
    setLoading(true);
    load();
    const interval = setInterval(load, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [load]);

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Financial Dashboard</h1>
          <p className="mt-1 text-sm text-gray-500">
            Real-time financial health — refreshes every 60 seconds.
          </p>
        </div>
        {data && (
          <div className="text-xs text-gray-400">As of {data.as_of_date}</div>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {loading && !data ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : !data ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          No financial data available yet.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {KPI_ORDER.map((key) => {
              const kpi: KPIValue | undefined = data.kpis[key];
              if (!kpi) return null;
              const prior = parseFloat(kpi.prior_value);
              const current = parseFloat(kpi.current_value);
              const sparklineData = [prior, current].every((v) => !Number.isNaN(v))
                ? [prior, current]
                : undefined;
              return (
                <KPICard
                  key={key}
                  label={kpi.label}
                  value={formatKPIValue(key, kpi.current_value)}
                  trend={kpi.trend}
                  changePct={formatChangePct(kpi.change_pct)}
                  sparklineData={sparklineData}
                />
              );
            })}
          </div>

          <div className="mt-6 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold text-gray-900">Period Close Status</h2>
            {data.period_close_status.length === 0 ? (
              <p className="text-sm text-gray-500">No fiscal year is currently active.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {data.period_close_status.map((p) => (
                  <span
                    key={p.period_number}
                    className={`rounded-full px-3 py-1 text-xs font-medium ${
                      PERIOD_STATUS_STYLES[p.status] ?? "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {p.period_name}: {p.status}
                  </span>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
