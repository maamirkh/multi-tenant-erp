/**
 * Money display formatting for Reports (T222, FR-RPT-322).
 *
 * Amounts arrive from the backend as Decimal **strings** and every
 * monetary calculation already happened server-side in `Decimal`. This
 * module never does arithmetic on money: it converts the string to a JS
 * `number` solely to hand it to `Intl.NumberFormat` for display. Display
 * formatting to 2 decimals is well within `Number`'s precision for any
 * realistic amount; the string is validated first so a malformed value
 * renders as a placeholder instead of `NaN`.
 */

export const MISSING_VALUE = '—';

const DECIMAL_PATTERN = /^-?\d+(\.\d+)?$/;

function parseDecimalString(value: string | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  const trimmed = value.trim();
  if (!DECIMAL_PATTERN.test(trimmed)) return null;
  return Number(trimmed);
}

/**
 * `formatMoney("1234.5", "USD")` → `"$1,234.50"`. With no currency code the
 * amount is grouped and fixed to 2 decimals without a symbol — some report
 * rows carry no currency of their own. `null`/malformed → `"—"`.
 */
export function formatMoney(
  amount: string | null | undefined,
  currencyCode?: string | null,
  locale?: string
): string {
  const parsed = parseDecimalString(amount);
  if (parsed === null) return MISSING_VALUE;
  if (currencyCode) {
    try {
      return new Intl.NumberFormat(locale, {
        style: 'currency',
        currency: currencyCode,
      }).format(parsed);
    } catch {
      // Unknown ISO code — fall through to plain formatting, never throw.
    }
  }
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(parsed);
}

/** `formatPercent("12.5")` → `"12.5%"` (the backend already sends percent units). */
export function formatPercent(value: string | null | undefined, locale?: string): string {
  const parsed = parseDecimalString(value);
  if (parsed === null) return MISSING_VALUE;
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(parsed)}%`;
}

/** True for a Decimal string strictly below zero — for sign-aware display
 * (always paired with a text/sign cue, never color alone). */
export function isNegativeAmount(value: string | null | undefined): boolean {
  const parsed = parseDecimalString(value);
  return parsed !== null && parsed < 0;
}
