'use client';

/**
 * ChartWrapper (T231) — the **one** Recharts boundary in the app. Nothing
 * outside `components/reports/` imports `recharts`, and only `(reports)`
 * route pages import this file, so Next.js code-splits Recharts into those
 * routes only (verified at Gate 7 by comparing non-Reports page bundles
 * before/after installing it).
 *
 * Every chart ships with an accessible alternative (FR-RPT-331): the SVG
 * itself is hidden from assistive technology, and the same data is always
 * rendered as a labelled `<table>` beneath it, inside a disclosure so
 * sighted users can open it too. Series are told apart by legend text and
 * dash pattern, not by color alone.
 *
 * Values arrive as Decimal strings. They are converted to numbers here only
 * to position marks on the chart; every value a person reads (tooltip,
 * table) is the formatted original string.
 */

import { useId } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { JsonValue, ReportRow } from '@/lib/api/reports';
import { MISSING_VALUE } from '@/lib/format/money';

export interface ChartSeries {
  key: string;
  label: string;
}

export interface ChartWrapperProps {
  title: string;
  type: 'bar' | 'line';
  data: ReportRow[];
  xKey: string;
  xLabel?: string;
  series: ChartSeries[];
  /** Display formatter for series values (tooltip + table). */
  formatValue?: (value: string) => string;
  formatX?: (value: string) => string;
  height?: number;
}

const SERIES_COLORS = ['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)', 'var(--chart-5)'];
const SERIES_DASHES = ['', '6 3', '2 2', '8 3 2 3', '1 3'];

/** Series color from the theme's chart tokens. */
function colorFor(index: number): string {
  return SERIES_COLORS[index % SERIES_COLORS.length] ?? 'var(--chart-1)';
}

/** Distinguishes line series by dash pattern as well as color. */
function dashFor(index: number): { strokeDasharray?: string } {
  const dash = SERIES_DASHES[index % SERIES_DASHES.length];
  return dash ? { strokeDasharray: dash } : {};
}

function text(value: JsonValue | undefined): string {
  if (value === null || value === undefined || value === '') return MISSING_VALUE;
  return typeof value === 'object' ? JSON.stringify(value) : String(value);
}

type PlotPoint = Record<string, string | number | null>;

/** Numeric copies of each series value, for mark positioning only. */
function toPlotData(data: ReportRow[], xKey: string, series: ChartSeries[]): PlotPoint[] {
  return data.map((row) => {
    const point: PlotPoint = { [xKey]: text(row[xKey]) };
    for (const s of series) {
      const parsed = Number(row[s.key]);
      point[s.key] = Number.isFinite(parsed) ? parsed : null;
    }
    return point;
  });
}

export function ChartWrapper({
  title,
  type,
  data,
  xKey,
  xLabel,
  series,
  formatValue = (value) => value,
  formatX = (value) => value,
  height = 280,
}: ChartWrapperProps): React.JSX.Element {
  const titleId = useId();
  const plotData = toPlotData(data, xKey, series);
  const tooltipFormatter = (value: unknown) =>
    typeof value === 'number' ? formatValue(String(value)) : MISSING_VALUE;

  const chart =
    type === 'line' ? (
      <LineChart data={plotData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey={xKey} tickFormatter={(v) => formatX(String(v))} />
        <YAxis />
        <Tooltip formatter={tooltipFormatter} labelFormatter={(v) => formatX(String(v))} />
        <Legend />
        {series.map((s, index) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.label}
            stroke={colorFor(index)}
            {...dashFor(index)}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    ) : (
      <BarChart data={plotData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey={xKey} tickFormatter={(v) => formatX(String(v))} />
        <YAxis />
        <Tooltip formatter={tooltipFormatter} labelFormatter={(v) => formatX(String(v))} />
        <Legend />
        {series.map((s, index) => (
          <Bar
            key={s.key}
            dataKey={s.key}
            name={s.label}
            fill={colorFor(index)}
            isAnimationActive={false}
          />
        ))}
      </BarChart>
    );

  return (
    <figure aria-labelledby={titleId} className="space-y-2">
      <figcaption id={titleId} className="text-sm font-medium">
        {title}
      </figcaption>
      <div aria-hidden="true" style={{ width: '100%', height }}>
        <ResponsiveContainer width="100%" height="100%">
          {chart}
        </ResponsiveContainer>
      </div>
      <details className="text-sm">
        <summary className="cursor-pointer text-xs text-muted-foreground">
          View data as table
        </summary>
        <table className="mt-2 w-full text-sm" aria-labelledby={titleId}>
          <thead className="text-left text-xs text-muted-foreground">
            <tr>
              <th scope="col" className="px-2 py-1">
                {xLabel ?? xKey}
              </th>
              {series.map((s) => (
                <th key={s.key} scope="col" className="px-2 py-1 text-right">
                  {s.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, index) => (
              <tr key={index} className="border-t border-border">
                <th scope="row" className="px-2 py-1 text-left font-normal">
                  {formatX(text(row[xKey]))}
                </th>
                {series.map((s) => {
                  const raw = text(row[s.key]);
                  return (
                    <td key={s.key} className="px-2 py-1 text-right tabular-nums">
                      {raw === MISSING_VALUE ? raw : formatValue(raw)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
