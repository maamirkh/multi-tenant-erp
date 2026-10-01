/**
 * KpiCard (T230) — the one KPI card Epic 11's own pages use (existing
 * per-module KPI tiles are untouched). The comparison delta is always
 * spelled out with a sign, an arrow glyph and screen-reader text — never
 * color alone (FR-RPT-331). A non-comparable period says so instead of
 * showing a misleading percentage.
 */

import type { ReactNode } from 'react';
import { ArrowDownRightIcon, ArrowUpRightIcon, MinusIcon } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { ComparisonResult } from '@/lib/api/reports';
import { formatPercent, isNegativeAmount } from '@/lib/format/money';
import { cn } from '@/lib/utils';

export interface KpiCardProps {
  label: string;
  /** Already display-formatted (e.g. via `formatMoney`). */
  value: string;
  comparison?: ComparisonResult | null;
  /** e.g. "Operational valuation (WAC) — not an accounting balance". */
  footnote?: ReactNode;
  badge?: ReactNode;
}

function ComparisonLine({ comparison }: { comparison: ComparisonResult }): React.JSX.Element {
  if (comparison.comparability === 'not_comparable' || comparison.percentage_change === null) {
    return <p className="text-xs text-muted-foreground">Not comparable with the prior period</p>;
  }
  const change = comparison.percentage_change;
  const negative = isNegativeAmount(change);
  const flat = Number(change) === 0;
  const Icon = flat ? MinusIcon : negative ? ArrowDownRightIcon : ArrowUpRightIcon;
  const direction = flat ? 'No change' : negative ? 'Decrease' : 'Increase';
  const signed = !negative && !flat ? `+${formatPercent(change)}` : formatPercent(change);
  return (
    <p
      className={cn(
        'flex items-center gap-1 text-xs',
        flat ? 'text-muted-foreground' : negative ? 'text-destructive' : 'text-emerald-700 dark:text-emerald-400'
      )}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      <span className="sr-only">{direction}:</span>
      <span>{signed}</span>
      {comparison.comparability === 'partial_current_period' && (
        <span className="text-muted-foreground">(period to date)</span>
      )}
    </p>
  );
}

export function KpiCard({ label, value, comparison, footnote, badge }: KpiCardProps): React.JSX.Element {
  return (
    <Card size="sm" className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-2 text-sm font-medium text-muted-foreground">
          <span>{label}</span>
          {badge}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-1">
        <p className="text-2xl font-semibold tabular-nums">{value}</p>
        {comparison && <ComparisonLine comparison={comparison} />}
        {footnote && <p className="text-xs text-muted-foreground">{footnote}</p>}
      </CardContent>
    </Card>
  );
}
