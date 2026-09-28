'use client';

/** ComparisonSelector (T228) — "no comparison" plus the backend's 5 `ComparisonType`s. */

import { useId } from 'react';
import { COMPARISON_TYPES, type ComparisonType } from '@/lib/api/reports';
import { FIELD_CLASS, LABEL_CLASS } from './fieldStyles';

export const COMPARISON_LABELS: Record<ComparisonType, string> = {
  previous_period: 'Previous period',
  previous_month: 'Previous month',
  previous_quarter: 'Previous quarter',
  previous_year: 'Previous year',
  same_period_last_year: 'Same period last year',
};

export function ComparisonSelector({
  value,
  onChange,
  label = 'Compare with',
}: {
  value: ComparisonType | null;
  onChange: (value: ComparisonType | null) => void;
  label?: string;
}): React.JSX.Element {
  const id = useId();
  return (
    <label className={LABEL_CLASS} htmlFor={id}>
      {label}
      <select
        id={id}
        className={FIELD_CLASS}
        value={value ?? ''}
        onChange={(event) =>
          onChange(event.target.value === '' ? null : (event.target.value as ComparisonType))
        }
      >
        <option value="">No comparison</option>
        {COMPARISON_TYPES.map((type) => (
          <option key={type} value={type}>
            {COMPARISON_LABELS[type]}
          </option>
        ))}
      </select>
    </label>
  );
}
