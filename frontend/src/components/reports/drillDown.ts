/**
 * Report drill-down links (FR-RPT-180/182). A report's `meta.drill_down`
 * refs come in two shapes:
 *
 * - **Row-level**: the route has `{field}` placeholders
 *   (`/contracts/{contract_id}`), filled from each row. A row missing a
 *   placeholder's value gets no link — never a half-built URL.
 * - **Report-level**: no placeholders (`/invoices?date_from=…`), so every
 *   row would get the same link; it is shown once, next to the table.
 *
 * The backend already appended the preserved filter scope as query params
 * (T136). Authorization is re-checked by the target page (FR-RPT-181).
 */

import type { DrillDownRef, ReportRow } from '@/lib/api/reports';
import { drillDownHref } from './domains';

const PLACEHOLDER = /\{(\w+)\}/g;

export function isRowLevel(ref: DrillDownRef): boolean {
  return /\{\w+\}/.test(ref.target_route);
}

/** The row's link for a row-level ref, or `null` if a value is missing. */
export function rowDrillDownHref(ref: DrillDownRef, row: ReportRow): string | null {
  let missing = false;
  const route = ref.target_route.replace(PLACEHOLDER, (_, field: string) => {
    const value = row[field];
    if (value === null || value === undefined || value === '' || typeof value === 'object') {
      missing = true;
      return '';
    }
    return encodeURIComponent(String(value));
  });
  return missing ? null : drillDownHref(route);
}

export function splitDrillDowns(refs: DrillDownRef[] | undefined): {
  rowLinks: DrillDownRef[];
  reportLinks: DrillDownRef[];
} {
  const all = refs ?? [];
  return {
    rowLinks: all.filter(isRowLevel),
    reportLinks: all.filter((ref) => !isRowLevel(ref)),
  };
}
