"use client";

/**
 * Reusable CFO dashboard KPI card: current value, trend indicator, and a
 * minimal inline-SVG sparkline (no charting dependency — Constitution §26
 * default is to not add one for a two/seven-point line).
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T291
 */

interface KPICardProps {
  label: string;
  /** Already formatted for display (e.g. "$12,345.00", "3.2%", "45 days"). */
  value: string;
  trend: "up" | "down" | "flat";
  /** Already formatted for display (e.g. "+4.2%"), or null if no prior baseline. */
  changePct?: string | null | undefined;
  /** Ordered oldest -> newest. Renders nothing if fewer than 2 points. */
  sparklineData?: number[] | undefined;
}

const TREND_STYLES: Record<KPICardProps["trend"], { icon: string; className: string }> = {
  up: { icon: "▲", className: "text-emerald-600" },
  down: { icon: "▼", className: "text-red-600" },
  flat: { icon: "▬", className: "text-gray-400" },
};

function Sparkline({ data, trend }: { data: number[]; trend: KPICardProps["trend"] }) {
  const width = 100;
  const height = 28;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((v - min) / range) * height;
      return `${x},${y}`;
    })
    .join(" ");

  const strokeColor =
    trend === "up" ? "#059669" : trend === "down" ? "#dc2626" : "#9ca3af";

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="h-7 w-full"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <polyline points={points} fill="none" stroke={strokeColor} strokeWidth={2} />
    </svg>
  );
}

export default function KPICard({ label, value, trend, changePct, sparklineData }: KPICardProps) {
  const trendStyle = TREND_STYLES[trend];

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-gray-900">{value}</div>
      <div className="mt-1 flex items-center gap-1 text-sm">
        <span className={trendStyle.className}>{trendStyle.icon}</span>
        <span className={trendStyle.className}>{changePct ?? "—"}</span>
        <span className="text-gray-400">vs prior period</span>
      </div>
      {sparklineData && sparklineData.length >= 2 && (
        <div className="mt-2">
          <Sparkline data={sparklineData} trend={trend} />
        </div>
      )}
    </div>
  );
}
