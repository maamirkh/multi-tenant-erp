/**
 * Customer360Sections (Phase 9, T255) — the four independently-authorized
 * sections of one customer's 360 view (FR-RPT-111):
 * - `present`     → the section card with that domain's own figures only
 *                   (never blended across domains, FR-RPT-113);
 * - `omitted`     → **nothing** — no "access denied" text, so an absent
 *                   section never reveals why it is absent;
 * - `unavailable` → a neutral "not configured" note (the backend's `reason`
 *                   stays in the payload for programmatic consumers; it is
 *                   deliberately not surfaced here).
 */

import type { ReactNode } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ApiClientError } from '@/lib/api/client';
import type { Customer360Response } from '@/lib/api/reports';
import { formatMoney, formatMoneyByCurrency } from '@/lib/format/money';

/** 404 NOT_FOUND (missing *or* cross-tenant — indistinguishable by design,
 * IDOR-safe) or 422 for an id that isn't even a UUID → standard not-found. */
export function isCustomerNotFound(error: unknown): boolean {
  return error instanceof ApiClientError && (error.status === 404 || error.status === 422);
}

type SectionKey = 'sales' | 'accounting_ar' | 'crm' | 'installments';

function SectionCard({
  sectionKey,
  title,
  children,
  badge,
}: {
  sectionKey: SectionKey;
  title: string;
  children: ReactNode;
  badge?: ReactNode;
}): React.JSX.Element {
  return (
    <Card data-testid={`c360-section-${sectionKey}`} className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-2 text-sm font-medium">
          <h2>{title}</h2>
          {badge}
        </CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function Figure({ label, value }: { label: string; value: string }): React.JSX.Element {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

function NotConfigured(): React.JSX.Element {
  return (
    <p className="text-sm text-muted-foreground" data-testid="c360-not-configured">
      Not configured for this company yet.
    </p>
  );
}

export function Customer360Sections({ data }: { data: Customer360Response }): React.JSX.Element {
  const cards: ReactNode[] = [];

  if (data.sales.state !== 'omitted') {
    cards.push(
      <SectionCard key="sales" sectionKey="sales" title="Sales">
        {data.sales.state === 'present' ? (
          <dl className="grid grid-cols-2 gap-3">
            <Figure label="Total revenue" value={formatMoneyByCurrency(data.sales.total_revenue, data.sales.total_revenue_by_currency)} />
            <Figure label="Invoices" value={String(data.sales.invoice_count)} />
          </dl>
        ) : (
          <NotConfigured />
        )}
      </SectionCard>
    );
  }

  if (data.accounting_ar.state !== 'omitted') {
    cards.push(
      <SectionCard key="accounting_ar" sectionKey="accounting_ar" title="Receivables (Accounting)">
        {data.accounting_ar.state === 'present' ? (
          <dl>
            <Figure label="Outstanding balance" value={formatMoney(data.accounting_ar.balance)} />
          </dl>
        ) : (
          <NotConfigured />
        )}
      </SectionCard>
    );
  }

  if (data.crm.state !== 'omitted') {
    cards.push(
      <SectionCard key="crm" sectionKey="crm" title="CRM">
        {data.crm.state === 'present' ? (
          <dl className="grid grid-cols-2 gap-3">
            <Figure label="Open opportunities" value={String(data.crm.open_opportunity_count)} />
            <Figure label="Open value" value={formatMoneyByCurrency(data.crm.open_opportunity_value, data.crm.open_opportunity_value_by_currency)} />
          </dl>
        ) : (
          <NotConfigured />
        )}
      </SectionCard>
    );
  }

  if (data.installments.state !== 'omitted') {
    const inst = data.installments;
    cards.push(
      <SectionCard
        key="installments"
        sectionKey="installments"
        title="Installments"
        badge={
          inst.state === 'present' && inst.read_only_servicing_continuity ? (
            <span
              data-testid="c360-servicing-badge"
              className="rounded-full border border-amber-300 px-2 py-0.5 text-[0.7rem] font-medium text-amber-800 dark:border-amber-700 dark:text-amber-200"
            >
              Read-only servicing
            </span>
          ) : undefined
        }
      >
        {inst.state === 'present' ? (
          <dl className="grid grid-cols-2 gap-3">
            <Figure label="Outstanding principal" value={formatMoneyByCurrency(inst.outstanding_principal, inst.outstanding_principal_by_currency)} />
            <Figure label="Contracts" value={String(inst.contract_count)} />
          </dl>
        ) : (
          <NotConfigured />
        )}
      </SectionCard>
    );
  }

  return <div className="grid gap-4 md:grid-cols-2">{cards}</div>;
}
