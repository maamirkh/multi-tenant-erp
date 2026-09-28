/**
 * Reports UI domain map — URL segment ↔ backend `ReportDomain` value.
 *
 * All Epic 11 pages live under `/analytics` (not `/reports` as plan.md §23
 * sketched): `/reports` is already owned by CRM's reports page and
 * `/reports/*` by Accounting's statement pages, so reusing that prefix
 * would collide with existing routes (decision recorded in tasks.md,
 * Phase 7). The Accounting domain's section is labelled "Finance".
 */

export const ANALYTICS_BASE_PATH = '/analytics';

export interface ReportsDomainSection {
  /** URL segment under `/analytics`. */
  segment: string;
  /** `ReportDiscoveryItem.domain` value. */
  domain: string;
  label: string;
}

export const REPORTS_DOMAIN_SECTIONS: readonly ReportsDomainSection[] = [
  { segment: 'sales', domain: 'sales', label: 'Sales' },
  { segment: 'purchase', domain: 'purchase', label: 'Purchase' },
  { segment: 'inventory', domain: 'inventory', label: 'Inventory' },
  { segment: 'finance', domain: 'accounting', label: 'Finance' },
  { segment: 'crm', domain: 'crm', label: 'CRM' },
  { segment: 'installments', domain: 'installments', label: 'Installments' },
];

/** The Executive Dashboard's registry key — gates the Overview link. */
export const DASHBOARD_REPORT_KEY = 'exec.dashboard';

export function sectionForSegment(segment: string): ReportsDomainSection | undefined {
  return REPORTS_DOMAIN_SECTIONS.find((s) => s.segment === segment);
}

export function reportHref(reportKey: string): string {
  return `${ANALYTICS_BASE_PATH}/${encodeURIComponent(reportKey)}`;
}
