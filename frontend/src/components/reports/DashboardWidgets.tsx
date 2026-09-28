/**
 * DashboardWidgets (Phase 9, T253) — the Executive Dashboard's **10**
 * widgets (FR-RPT-040), bound 1:1 to `GET /reports/dashboard`.
 *
 * Every widget has exactly one of three states, each rendered distinctly:
 * - `present`     → a full KPI card (a real zero is shown as a zero);
 * - `omitted`     → **nothing** — an entitlement/permission gate failed, and
 *                   an absent card never hints at why (FR-RPT-041);
 * - `unavailable` → a neutral "currently unavailable" card — a prerequisite
 *                   isn't set up (e.g. no chart of accounts). Never a zero.
 *
 * Values are backend Decimal strings, display-formatted only. The company's
 * base currency isn't part of this payload, so money renders without a
 * symbol rather than guessing one. `win_rate`/`gross_profit_margin` are
 * already percent units server-side.
 */

import type { ReactNode } from 'react';
import { CircleSlashIcon } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type {
  ComparisonResult,
  ExecutiveDashboardResponse,
  WidgetState,
} from '@/lib/api/reports';
import { formatMoney, formatPercent } from '@/lib/format/money';
import { KpiCard } from './KpiCard';

interface WidgetView {
  key: keyof Omit<ExecutiveDashboardResponse, 'period'>;
  label: string;
  state: WidgetState;
  value: string;
  comparison: ComparisonResult | null;
  footnote?: ReactNode;
  badge?: ReactNode;
}

function ServicingBadge(): React.JSX.Element {
  return (
    <span
      data-testid="installments-servicing-badge"
      className="rounded-full border border-amber-300 px-2 py-0.5 text-[0.7rem] font-medium text-amber-800 dark:border-amber-700 dark:text-amber-200"
    >
      Read-only servicing
    </span>
  );
}

/** The 10 widgets in FR-RPT-040's order. */
export function dashboardWidgetViews(data: ExecutiveDashboardResponse): WidgetView[] {
  const { ar, crm_pipeline: crm, installment_exposure: inst, operational_inventory_value: inv } = data;
  return [
    {
      key: 'net_sales',
      label: 'Net sales',
      state: data.net_sales.state,
      value: formatMoney(data.net_sales.value),
      comparison: data.net_sales.comparison,
    },
    {
      key: 'gross_sales',
      label: 'Gross sales',
      state: data.gross_sales.state,
      value: formatMoney(data.gross_sales.value),
      comparison: data.gross_sales.comparison,
    },
    {
      key: 'purchase_spend',
      label: 'Purchase spend',
      state: data.purchase_spend.state,
      value: formatMoney(data.purchase_spend.value),
      comparison: data.purchase_spend.comparison,
    },
    {
      key: 'ar',
      label: 'Accounts receivable',
      state: ar.state,
      value: formatMoney(ar.balance),
      comparison: ar.comparison,
      footnote: `Overdue: ${formatMoney(ar.overdue)}`,
    },
    {
      key: 'ap',
      label: 'Accounts payable',
      state: data.ap.state,
      value: formatMoney(data.ap.value),
      comparison: data.ap.comparison,
    },
    {
      key: 'cash_position',
      label: 'Cash position',
      state: data.cash_position.state,
      value: formatMoney(data.cash_position.value),
      comparison: data.cash_position.comparison,
    },
    {
      key: 'operational_inventory_value',
      label: 'Inventory value (operational)',
      state: inv.state,
      value: formatMoney(inv.value),
      comparison: inv.comparison,
      footnote: 'Weighted average cost — not a reconciled accounting balance.',
    },
    {
      key: 'crm_pipeline',
      label: 'CRM pipeline',
      state: crm.state,
      value: formatMoney(crm.pipeline_value),
      comparison: crm.comparison,
      footnote: `Win rate: ${formatPercent(crm.win_rate)}`,
    },
    {
      key: 'installment_exposure',
      label: 'Installment exposure',
      state: inst.state,
      value: formatMoney(inst.outstanding_principal),
      comparison: inst.comparison,
      footnote: `Overdue: ${formatMoney(inst.overdue)}`,
      ...(inst.read_only_servicing_continuity ? { badge: <ServicingBadge /> } : {}),
    },
    {
      key: 'gross_profit_margin',
      label: 'Gross profit margin',
      state: data.gross_profit_margin.state,
      value: formatPercent(data.gross_profit_margin.value),
      comparison: data.gross_profit_margin.comparison,
    },
  ];
}

function UnavailableCard({ label }: { label: string }): React.JSX.Element {
  return (
    <Card size="sm" className="h-full border-dashed" data-testid="dashboard-widget-unavailable">
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent className="flex items-center gap-2 text-sm text-muted-foreground">
        <CircleSlashIcon className="size-4" aria-hidden="true" />
        Currently unavailable
      </CardContent>
    </Card>
  );
}

export function DashboardWidgets({ data }: { data: ExecutiveDashboardResponse }): React.JSX.Element {
  const visible = dashboardWidgetViews(data).filter((w) => w.state !== 'omitted');
  return (
    <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" role="list" aria-label="Key figures">
      {visible.map((widget) => (
        <li key={widget.key} data-testid={`dashboard-widget-${widget.key}`} data-state={widget.state}>
          {widget.state === 'unavailable' ? (
            <UnavailableCard label={widget.label} />
          ) : (
            <KpiCard
              label={widget.label}
              value={widget.value}
              comparison={widget.comparison}
              footnote={widget.footnote}
              badge={widget.badge}
            />
          )}
        </li>
      ))}
    </ul>
  );
}
