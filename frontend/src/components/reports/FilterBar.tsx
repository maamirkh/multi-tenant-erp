'use client';

/**
 * FilterBar (T229) — one shared, **props-driven** filter form. It has no
 * knowledge of any report: each report page declares its own filter fields
 * in code and passes them in as `fields` (the discovery contract carries no
 * filter schema, so there is nothing to derive them from). Field names must
 * match the report's backend filter schema exactly — the backend rejects
 * unknown fields (`extra="forbid"`), it never silently ignores them.
 *
 * Edits stay local until "Apply", so typing never fires a query per
 * keystroke.
 */

import { useId, useState } from 'react';
import { Button } from '@/components/ui/button';
import type { ReportFilters } from '@/lib/api/reports';
import { FIELD_CLASS, LABEL_CLASS } from './fieldStyles';

export type FilterFieldType = 'text' | 'date' | 'number' | 'select';

export interface FilterFieldOption {
  value: string;
  label: string;
}

export interface FilterField {
  name: string;
  label: string;
  type: FilterFieldType;
  options?: FilterFieldOption[];
  placeholder?: string;
  required?: boolean;
}

export type FilterValues = Record<string, string>;

export function toReportFilters(values: FilterValues): ReportFilters {
  const filters: ReportFilters = {};
  for (const [name, value] of Object.entries(values)) {
    if (value !== '') filters[name] = value;
  }
  return filters;
}

export function FilterBar({
  fields,
  values,
  onApply,
  onReset,
}: {
  fields: FilterField[];
  values: FilterValues;
  onApply: (values: FilterValues) => void;
  onReset?: () => void;
}): React.JSX.Element | null {
  const id = useId();
  const [draft, setDraft] = useState<FilterValues>(values);
  // Re-sync the draft when the applied values change from outside (e.g. a
  // saved view is loaded) — adjusted during render, not in an effect.
  const [appliedValues, setAppliedValues] = useState<FilterValues>(values);
  if (appliedValues !== values) {
    setAppliedValues(values);
    setDraft(values);
  }

  if (fields.length === 0) return null;

  const setField = (name: string, value: string) => setDraft((prev) => ({ ...prev, [name]: value }));

  return (
    <form
      role="search"
      aria-label="Report filters"
      className="flex flex-wrap items-end gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        onApply(draft);
      }}
    >
      {fields.map((field) => {
        const inputId = `${id}-${field.name}`;
        const value = draft[field.name] ?? '';
        return (
          <label key={field.name} className={LABEL_CLASS} htmlFor={inputId}>
            {field.label}
            {field.type === 'select' ? (
              <select
                id={inputId}
                name={field.name}
                className={FIELD_CLASS}
                value={value}
                required={field.required}
                onChange={(event) => setField(field.name, event.target.value)}
              >
                {!field.required && <option value="">Any</option>}
                {(field.options ?? []).map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id={inputId}
                name={field.name}
                type={field.type}
                className={FIELD_CLASS}
                value={value}
                placeholder={field.placeholder}
                required={field.required}
                onChange={(event) => setField(field.name, event.target.value)}
              />
            )}
          </label>
        );
      })}
      <Button type="submit" size="sm">
        Apply
      </Button>
      {onReset && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => {
            setDraft({});
            onReset();
          }}
        >
          Reset
        </Button>
      )}
    </form>
  );
}
