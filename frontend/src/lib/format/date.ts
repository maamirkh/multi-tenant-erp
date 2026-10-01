/**
 * Date/period display formatting for Reports (T223, FR-RPT-322).
 *
 * Report periods come back resolved as half-open UTC intervals
 * `[start, end)` plus the IANA timezone they were computed in
 * (`PeriodResolution`). Displaying them in UTC would shift a company's
 * "March" into Feb 28 / Mar 31 for any zone west of UTC, so every
 * formatter here renders in the period's own timezone. The exclusive
 * `end` is shown as the last included day.
 */

import type { PeriodResolution } from '@/lib/api/reports';
import { MISSING_VALUE } from './money';

function toDate(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

function dayFormatter(timeZone?: string, locale?: string): Intl.DateTimeFormat {
  try {
    return new Intl.DateTimeFormat(locale, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      timeZone,
    });
  } catch {
    // Unknown IANA zone — fall back to UTC rather than throwing mid-render.
    return new Intl.DateTimeFormat(locale, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      timeZone: 'UTC',
    });
  }
}

/** A single date/instant as a calendar day in `timeZone` (default: UTC). */
export function formatDate(
  iso: string | null | undefined,
  timeZone = 'UTC',
  locale?: string
): string {
  const date = toDate(iso);
  return date ? dayFormatter(timeZone, locale).format(date) : MISSING_VALUE;
}

/**
 * `formatPeriod({start:"2026-03-01T05:00:00Z", end:"2026-04-01T04:00:00Z",
 * timezone:"America/New_York"})` → `"Mar 1, 2026 – Mar 31, 2026"`.
 * A single-day period renders one date. Partial current periods get a
 * " (to date)" suffix so a comparison against a full period is never
 * mistaken for like-for-like.
 */
export function formatPeriod(period: PeriodResolution | null | undefined, locale?: string): string {
  if (!period) return MISSING_VALUE;
  const start = toDate(period.start);
  const endExclusive = toDate(period.end);
  if (!start || !endExclusive) return MISSING_VALUE;
  const lastIncluded = new Date(endExclusive.getTime() - 1);
  const formatter = dayFormatter(period.timezone, locale);
  const from = formatter.format(start);
  const to = formatter.format(lastIncluded);
  const range = from === to ? from : `${from} – ${to}`;
  return period.is_partial_current_period ? `${range} (to date)` : range;
}
