/**
 * AggregateView (Phase 8) — renders a report's fixed aggregate payload
 * (statements, KPI sets, CRM/Installments dashboards) exactly as the
 * backend returns it, without re-deriving anything:
 * - top-level scalars → KPI cards;
 * - arrays of rows → a DataTable each;
 * - nested objects → a titled sub-section, recursively.
 *
 * Numeric strings are only display-formatted (grouping, ≤2 decimals); no
 * value is ever computed client-side.
 */

import type { JsonValue, ReportRow } from '@/lib/api/reports';
import { MISSING_VALUE } from '@/lib/format/money';
import { DataTable } from './DataTable';
import { KpiCard } from './KpiCard';

const NUMERIC = /^-?\d+(\.\d+)?$/;
const MAX_DEPTH = 4;

export function humanizeKey(key: string): string {
  return key.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
}

export function formatScalar(value: JsonValue): string {
  if (value === null || value === '') return MISSING_VALUE;
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'number') return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value);
  if (typeof value === 'string' && NUMERIC.test(value.trim())) {
    return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(Number(value));
  }
  return typeof value === 'string' ? value : JSON.stringify(value);
}

function isRowArray(value: JsonValue): value is ReportRow[] {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every((v) => v !== null && typeof v === 'object' && !Array.isArray(v))
  );
}

function isObject(value: JsonValue): value is { [key: string]: JsonValue } {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function Section({
  data,
  depth,
  timeZone,
}: {
  data: { [key: string]: JsonValue };
  depth: number;
  timeZone?: string | undefined;
}): React.JSX.Element {
  const entries = Object.entries(data);
  const scalars = entries.filter(([, v]) => !isObject(v) && !Array.isArray(v));
  const lists = entries.filter(([, v]) => Array.isArray(v));
  const nested = entries.filter(([, v]) => isObject(v));
  const Heading = depth === 0 ? 'h2' : 'h3';

  return (
    <div className="space-y-4">
      {scalars.length > 0 && (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" role="list">
          {scalars.map(([key, value]) => (
            <li key={key}>
              <KpiCard label={humanizeKey(key)} value={formatScalar(value)} />
            </li>
          ))}
        </ul>
      )}
      {lists.map(([key, value]) =>
        isRowArray(value) ? (
          <section key={key} className="space-y-2">
            <Heading className="text-sm font-semibold">{humanizeKey(key)}</Heading>
            <DataTable caption={humanizeKey(key)} rows={value} timeZone={timeZone} />
          </section>
        ) : (
          <p key={key} className="text-sm">
            <span className="font-medium">{humanizeKey(key)}: </span>
            {Array.isArray(value) && value.length > 0
              ? value.map((v) => formatScalar(v)).join(', ')
              : MISSING_VALUE}
          </p>
        )
      )}
      {depth < MAX_DEPTH &&
        nested.map(([key, value]) =>
          isObject(value) ? (
            <section key={key} className="space-y-2 rounded-lg border border-border p-4">
              <Heading className="text-sm font-semibold">{humanizeKey(key)}</Heading>
              <Section data={value} depth={depth + 1} timeZone={timeZone} />
            </section>
          ) : null
        )}
    </div>
  );
}

export function AggregateView({
  data,
  timeZone,
}: {
  data: { [key: string]: JsonValue };
  timeZone?: string | undefined;
}): React.JSX.Element {
  return <Section data={data} depth={0} timeZone={timeZone} />;
}
