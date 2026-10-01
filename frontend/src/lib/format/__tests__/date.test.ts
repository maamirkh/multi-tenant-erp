/** T224 — timezone-aware period/date display (T223). */

import { formatDate, formatPeriod } from '../date';
import { MISSING_VALUE } from '../money';

describe('formatPeriod', () => {
  it("renders a month in the company's own timezone, end exclusive", () => {
    expect(
      formatPeriod(
        {
          start: '2026-03-01T05:00:00Z',
          end: '2026-04-01T04:00:00Z',
          timezone: 'America/New_York',
          is_partial_current_period: false,
        },
        'en-US'
      )
    ).toBe('Mar 1, 2026 – Mar 31, 2026');
  });

  it('does not shift a zone east of UTC into the previous day', () => {
    expect(
      formatPeriod(
        {
          start: '2026-01-31T19:00:00Z',
          end: '2026-02-28T19:00:00Z',
          timezone: 'Asia/Karachi',
          is_partial_current_period: false,
        },
        'en-US'
      )
    ).toBe('Feb 1, 2026 – Feb 28, 2026');
  });

  it('renders a single-day period as one date', () => {
    expect(
      formatPeriod(
        {
          start: '2026-06-10T00:00:00Z',
          end: '2026-06-11T00:00:00Z',
          timezone: 'UTC',
          is_partial_current_period: false,
        },
        'en-US'
      )
    ).toBe('Jun 10, 2026');
  });

  it('marks a partial current period', () => {
    expect(
      formatPeriod(
        {
          start: '2026-09-01T00:00:00Z',
          end: '2026-10-01T00:00:00Z',
          timezone: 'UTC',
          is_partial_current_period: true,
        },
        'en-US'
      )
    ).toBe('Sep 1, 2026 – Sep 30, 2026 (to date)');
  });

  it('renders a placeholder for a missing or malformed period', () => {
    expect(formatPeriod(null)).toBe(MISSING_VALUE);
    expect(
      formatPeriod({ start: 'nope', end: 'nope', timezone: 'UTC', is_partial_current_period: false })
    ).toBe(MISSING_VALUE);
  });

  it('falls back to UTC for an unknown timezone instead of throwing', () => {
    expect(
      formatPeriod(
        {
          start: '2026-06-10T00:00:00Z',
          end: '2026-06-11T00:00:00Z',
          timezone: 'Not/AZone',
          is_partial_current_period: false,
        },
        'en-US'
      )
    ).toBe('Jun 10, 2026');
  });
});

describe('formatDate', () => {
  it('formats a plain date in UTC by default', () => {
    expect(formatDate('2026-01-15', undefined, 'en-US')).toBe('Jan 15, 2026');
  });

  it('formats an instant in the given timezone', () => {
    expect(formatDate('2026-01-15T02:00:00Z', 'America/Los_Angeles', 'en-US')).toBe(
      'Jan 14, 2026'
    );
  });

  it('renders a placeholder for null or garbage', () => {
    expect(formatDate(null)).toBe(MISSING_VALUE);
    expect(formatDate('garbage')).toBe(MISSING_VALUE);
  });
});
