/**
 * T092 — CompanyPreferencesForm.
 *
 * Date format, decimal separator, thousands separator,
 * invoice prefix, and PO prefix settings.
 * Calls useCompanySettings() mutation on submit.
 *
 * Spec ref: Epic 3, Phase 12 (T092).
 */

'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useCompanySettings } from '@/hooks/companies/useCompanySettings';
import type { CompanyDetail } from '@/types/companies';

// ── Data ──────────────────────────────────────────────────────────────────────

const DATE_FORMATS = [
  { value: 'MM/DD/YYYY', label: 'MM/DD/YYYY (US)' },
  { value: 'DD/MM/YYYY', label: 'DD/MM/YYYY (EU)' },
  { value: 'YYYY-MM-DD', label: 'YYYY-MM-DD (ISO)' },
  { value: 'DD.MM.YYYY', label: 'DD.MM.YYYY (DE/RU)' },
  { value: 'DD-MM-YYYY', label: 'DD-MM-YYYY' },
  { value: 'YYYY/MM/DD', label: 'YYYY/MM/DD (JP/CN)' },
];

const DECIMAL_SEPARATORS = [
  { value: '.', label: 'Period (1,234.56)' },
  { value: ',', label: 'Comma (1.234,56)' },
];

const THOUSANDS_SEPARATORS = [
  { value: ',', label: 'Comma (1,234)' },
  { value: '.', label: 'Period (1.234)' },
  { value: ' ', label: 'Space (1 234)' },
];

// ── Schema ────────────────────────────────────────────────name────────────────

const preferencesSchema = z.object({
  date_format: z.string().optional(),
  decimal_separator: z.string().optional(),
  thousands_separator: z.string().optional(),
  invoice_prefix: z.string().max(20, 'Prefix must be 20 characters or fewer').optional(),
  po_prefix: z.string().max(20, 'Prefix must be 20 characters or fewer').optional(),
});

type PreferencesFormData = z.infer<typeof preferencesSchema>;

// ── Helpers ───────────────────────────────────────────────────────────────────

function extractPreferences(company: CompanyDetail): PreferencesFormData {
  const s = company.settings as Record<string, unknown>;
  return {
    date_format: (typeof s.date_format === 'string' ? s.date_format : undefined)
      ?? (typeof company.date_format === 'string' ? company.date_format : undefined)
      ?? '',
    decimal_separator: typeof s.decimal_separator === 'string' ? s.decimal_separator : '',
    thousands_separator: typeof s.thousands_separator === 'string' ? s.thousands_separator : '',
    invoice_prefix: typeof s.invoice_prefix === 'string' ? s.invoice_prefix : '',
    po_prefix: typeof s.po_prefix === 'string' ? s.po_prefix : '',
  };
}

// ── Component ─────────────────────────────────────────────────────────────────

interface CompanyPreferencesFormProps {
  company: CompanyDetail;
}

export function CompanyPreferencesForm({ company }: CompanyPreferencesFormProps) {
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const updateSettings = useCompanySettings();

  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<PreferencesFormData>({
    resolver: zodResolver(preferencesSchema),
    defaultValues: extractPreferences(company),
  });

  function onSubmit(data: PreferencesFormData) {
    setSuccessMessage(null);

    // Only include non-empty values in the settings payload
    const settings: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(data)) {
      if (v !== '' && v !== undefined) {
        settings[k] = v;
      }
    }

    updateSettings.mutate(
      { id: company.id, data: { settings } },
      {
        onSuccess: () => {
          setSuccessMessage('Preferences updated successfully.');
        },
      }
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
      {/* Date Format */}
      <div className="space-y-1">
        <label htmlFor="date_format" className="text-sm font-medium text-foreground">
          Date Format
        </label>
        <select
          id="date_format"
          className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          {...register('date_format')}
        >
          <option value="">Select format</option>
          {DATE_FORMATS.map(({ value, label }) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </div>

      {/* Decimal + Thousands separators in a row */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1">
          <label htmlFor="decimal_separator" className="text-sm font-medium text-foreground">
            Decimal Separator
          </label>
          <select
            id="decimal_separator"
            className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            {...register('decimal_separator')}
          >
            <option value="">Select</option>
            {DECIMAL_SEPARATORS.map(({ value, label }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>

        <div className="space-y-1">
          <label htmlFor="thousands_separator" className="text-sm font-medium text-foreground">
            Thousands Separator
          </label>
          <select
            id="thousands_separator"
            className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            {...register('thousands_separator')}
          >
            <option value="">Select</option>
            {THOUSANDS_SEPARATORS.map(({ value, label }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Invoice Prefix + PO Prefix in a row */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1">
          <label htmlFor="invoice_prefix" className="text-sm font-medium text-foreground">
            Invoice Prefix <span className="text-xs text-muted-foreground">(optional)</span>
          </label>
          <Input
            id="invoice_prefix"
            type="text"
            placeholder="INV-"
            maxLength={20}
            aria-invalid={!!errors.invoice_prefix}
            aria-describedby={errors.invoice_prefix ? 'invoice_prefix_err' : undefined}
            {...register('invoice_prefix')}
          />
          {errors.invoice_prefix && (
            <p id="invoice_prefix_err" role="alert" className="text-xs text-destructive">
              {errors.invoice_prefix.message}
            </p>
          )}
        </div>

        <div className="space-y-1">
          <label htmlFor="po_prefix" className="text-sm font-medium text-foreground">
            PO Prefix <span className="text-xs text-muted-foreground">(optional)</span>
          </label>
          <Input
            id="po_prefix"
            type="text"
            placeholder="PO-"
            maxLength={20}
            aria-invalid={!!errors.po_prefix}
            aria-describedby={errors.po_prefix ? 'po_prefix_err' : undefined}
            {...register('po_prefix')}
          />
          {errors.po_prefix && (
            <p id="po_prefix_err" role="alert" className="text-xs text-destructive">
              {errors.po_prefix.message}
            </p>
          )}
        </div>
      </div>

      {/* Feedback */}
      {successMessage && (
        <p role="status" className="text-sm text-green-700 dark:text-green-400">
          {successMessage}
        </p>
      )}
      {updateSettings.isError && (
        <p role="alert" className="text-sm text-destructive">
          {updateSettings.error?.message ?? 'Failed to update preferences.'}
        </p>
      )}

      <div className="flex justify-end">
        <Button type="submit" disabled={!isDirty || updateSettings.isPending}>
          {updateSettings.isPending ? 'Saving…' : 'Save Changes'}
        </Button>
      </div>
    </form>
  );
}
