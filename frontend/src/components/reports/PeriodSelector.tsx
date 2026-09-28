'use client';

/**
 * PeriodSelector (T227) — the 11 standard presets (FR-RPT-130), emitting
 * the backend's own `PeriodPreset` values. `custom` reveals a start/end
 * date pair; the backend resolves every preset in the company's timezone,
 * so this component never computes date boundaries itself.
 */

import { useId } from 'react';
import { PERIOD_PRESETS, type PeriodPreset } from '@/lib/api/reports';
import { FIELD_CLASS, LABEL_CLASS } from './fieldStyles';

export const PERIOD_LABELS: Record<PeriodPreset, string> = {
  today: 'Today',
  yesterday: 'Yesterday',
  this_week: 'This week',
  last_week: 'Last week',
  this_month: 'This month',
  last_month: 'Last month',
  this_quarter: 'This quarter',
  last_quarter: 'Last quarter',
  this_year: 'This year',
  last_year: 'Last year',
  custom: 'Custom range',
};

export interface PeriodValue {
  period: PeriodPreset;
  customStart?: string;
  customEnd?: string;
}

export function PeriodSelector({
  value,
  onChange,
  label = 'Period',
}: {
  value: PeriodValue;
  onChange: (value: PeriodValue) => void;
  label?: string;
}): React.JSX.Element {
  const id = useId();
  return (
    <div className="flex flex-wrap items-end gap-2">
      <label className={LABEL_CLASS} htmlFor={`${id}-preset`}>
        {label}
        <select
          id={`${id}-preset`}
          className={FIELD_CLASS}
          value={value.period}
          onChange={(event) =>
            onChange({ ...value, period: event.target.value as PeriodPreset })
          }
        >
          {PERIOD_PRESETS.map((preset) => (
            <option key={preset} value={preset}>
              {PERIOD_LABELS[preset]}
            </option>
          ))}
        </select>
      </label>
      {value.period === 'custom' && (
        <>
          <label className={LABEL_CLASS} htmlFor={`${id}-start`}>
            From
            <input
              id={`${id}-start`}
              type="date"
              className={FIELD_CLASS}
              value={value.customStart ?? ''}
              max={value.customEnd || undefined}
              onChange={(event) => onChange({ ...value, customStart: event.target.value })}
            />
          </label>
          <label className={LABEL_CLASS} htmlFor={`${id}-end`}>
            To
            <input
              id={`${id}-end`}
              type="date"
              className={FIELD_CLASS}
              value={value.customEnd ?? ''}
              min={value.customStart || undefined}
              onChange={(event) => onChange({ ...value, customEnd: event.target.value })}
            />
          </label>
        </>
      )}
    </div>
  );
}
