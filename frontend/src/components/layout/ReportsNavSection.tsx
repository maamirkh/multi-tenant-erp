'use client';

/**
 * ReportsNavSection (T236) — the Reports & Analytics sidebar section.
 *
 * Visibility is driven **entirely** by the discovery endpoint (FR-RPT-320):
 * a domain link renders only when discovery returns at least one report
 * key for that domain, and the whole section renders nothing when
 * discovery returns none or fails (e.g. `reports` not enabled for the
 * company → 403). There is no hardcoded per-module entry and no
 * probe-then-hide-on-403 per report.
 */

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { BarChart3Icon, LayoutGridIcon } from 'lucide-react';
import { useReportDiscovery } from '@/hooks/reports/useReportDiscovery';
import {
  ANALYTICS_BASE_PATH,
  DASHBOARD_REPORT_KEY,
  REPORTS_DOMAIN_SECTIONS,
} from '@/components/reports/domains';
import { cn } from '@/lib/utils';

function ReportsLink({
  href,
  label,
  exact = false,
}: {
  href: string;
  label: string;
  exact?: boolean;
}): React.JSX.Element {
  const pathname = usePathname();
  const isActive = exact ? pathname === href : pathname.startsWith(href);
  return (
    <Link
      href={href}
      aria-current={isActive ? 'page' : undefined}
      className={cn(
        'flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors',
        isActive
          ? 'bg-primary/10 text-primary font-medium'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
      )}
    >
      <span className="size-4 shrink-0" aria-hidden="true">
        {href === ANALYTICS_BASE_PATH ? (
          <LayoutGridIcon className="size-4" />
        ) : (
          <BarChart3Icon className="size-4" />
        )}
      </span>
      {label}
    </Link>
  );
}

export default function ReportsNavSection(): React.JSX.Element | null {
  const { data } = useReportDiscovery();
  const reports = data?.reports ?? [];
  if (reports.length === 0) return null;

  const domains = new Set(reports.map((r) => r.domain));
  const hasDashboard = reports.some((r) => r.key === DASHBOARD_REPORT_KEY);
  const sections = REPORTS_DOMAIN_SECTIONS.filter((s) => domains.has(s.domain));
  if (!hasDashboard && sections.length === 0) return null;

  return (
    <div data-testid="reports-nav">
      <p className="mb-1 px-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Reports &amp; Analytics
      </p>
      <ul className="space-y-0.5" role="list">
        {hasDashboard && (
          <li>
            <ReportsLink href={ANALYTICS_BASE_PATH} label="Overview" exact />
          </li>
        )}
        {sections.map((section) => (
          <li key={section.segment}>
            <ReportsLink
              href={`${ANALYTICS_BASE_PATH}/${section.segment}`}
              label={section.label}
            />
          </li>
        ))}
      </ul>
    </div>
  );
}
