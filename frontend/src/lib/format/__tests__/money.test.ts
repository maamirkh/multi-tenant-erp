/** T224 — money display formatting (T222). */

import { formatMoney, formatPercent, isNegativeAmount, MISSING_VALUE } from '../money';

describe('formatMoney', () => {
  it('formats a Decimal string with a currency symbol and 2 decimals', () => {
    expect(formatMoney('1234.5', 'USD', 'en-US')).toBe('$1,234.50');
  });

  it('keeps the sign of negative amounts', () => {
    expect(formatMoney('-125.00', 'USD', 'en-US')).toBe('-$125.00');
  });

  it('formats without a symbol when no currency is given', () => {
    expect(formatMoney('1000000', null, 'en-US')).toBe('1,000,000.00');
  });

  it('renders zero as a real zero, not a placeholder', () => {
    expect(formatMoney('0', 'USD', 'en-US')).toBe('$0.00');
  });

  it('rounds long Decimal strings for display only', () => {
    expect(formatMoney('10.005000', 'USD', 'en-US')).toMatch(/^\$10\.0[01]$/);
  });

  it.each([null, undefined, '', 'abc', '1e5', '12,50'])(
    'renders a placeholder for %p instead of NaN',
    (value) => {
      expect(formatMoney(value, 'USD', 'en-US')).toBe(MISSING_VALUE);
    }
  );

  it('falls back to plain formatting for an unknown currency code', () => {
    expect(formatMoney('5', 'NOT_A_CODE', 'en-US')).toBe('5.00');
  });
});

describe('formatPercent', () => {
  it('appends a percent sign to a percent-unit Decimal string', () => {
    expect(formatPercent('12.5', 'en-US')).toBe('12.5%');
  });

  it('renders a placeholder for null', () => {
    expect(formatPercent(null)).toBe(MISSING_VALUE);
  });
});

describe('isNegativeAmount', () => {
  it('detects negatives only', () => {
    expect(isNegativeAmount('-0.01')).toBe(true);
    expect(isNegativeAmount('0')).toBe(false);
    expect(isNegativeAmount('3')).toBe(false);
    expect(isNegativeAmount(null)).toBe(false);
  });
});
