/**
 * T089 — CompanyRegionalSettingsForm.
 *
 * Currency, timezone, language, and fiscal year settings.
 * Currency change shows inline warning and requires checkbox confirmation.
 * All selectors use searchable <datalist> or <select> patterns.
 * Submits via useUpdateCompany() mutation.
 *
 * Spec ref: Epic 3, Phase 12 (T089).
 */

'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useUpdateCompany } from '@/hooks/companies/useUpdateCompany';
import type { CompanyDetail } from '@/types/companies';

// ── Data ──────────────────────────────────────────────────────────────────────

const CURRENCIES = [
  'AED', 'AUD', 'BRL', 'CAD', 'CHF', 'CNY', 'COP', 'CZK', 'DKK', 'EGP',
  'EUR', 'GBP', 'GHS', 'HKD', 'HUF', 'IDR', 'ILS', 'INR', 'JPY', 'KES',
  'KRW', 'MAD', 'MXN', 'MYR', 'NGN', 'NOK', 'NZD', 'PHP', 'PKR', 'PLN',
  'RON', 'RUB', 'SAR', 'SEK', 'SGD', 'THB', 'TRY', 'TWD', 'UAH', 'USD',
  'VND', 'ZAR',
];

const TIMEZONES = [
  // Americas
  'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles',
  'America/Anchorage', 'America/Honolulu', 'America/Toronto', 'America/Vancouver',
  'America/Sao_Paulo', 'America/Argentina/Buenos_Aires', 'America/Mexico_City',
  'America/Bogota', 'America/Lima', 'America/Santiago',
  // Europe
  'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'Europe/Madrid',
  'Europe/Rome', 'Europe/Amsterdam', 'Europe/Brussels', 'Europe/Vienna',
  'Europe/Zurich', 'Europe/Stockholm', 'Europe/Oslo', 'Europe/Copenhagen',
  'Europe/Warsaw', 'Europe/Prague', 'Europe/Budapest', 'Europe/Bucharest',
  'Europe/Athens', 'Europe/Helsinki', 'Europe/Kiev',
  // Asia
  'Asia/Dubai', 'Asia/Riyadh', 'Asia/Beirut', 'Asia/Jerusalem', 'Asia/Istanbul',
  'Asia/Karachi', 'Asia/Kolkata', 'Asia/Dhaka', 'Asia/Bangkok', 'Asia/Jakarta',
  'Asia/Singapore', 'Asia/Kuala_Lumpur', 'Asia/Manila', 'Asia/Hong_Kong',
  'Asia/Shanghai', 'Asia/Seoul', 'Asia/Tokyo', 'Asia/Taipei',
  // Africa & Oceania
  'Africa/Cairo', 'Africa/Lagos', 'Africa/Nairobi', 'Africa/Johannesburg',
  'Africa/Casablanca', 'Australia/Sydney', 'Australia/Melbourne',
  'Australia/Brisbane', 'Australia/Perth', 'Pacific/Auckland',
  // UTC
  'UTC',
];

const LANGUAGES = [
  'ar-SA', 'cs-CZ', 'da-DK', 'de-DE', 'el-GR', 'en-AU', 'en-CA', 'en-GB',
  'en-US', 'es-AR', 'es-CO', 'es-ES', 'es-MX', 'fi-FI', 'fr-CA', 'fr-FR',
  'he-IL', 'hi-IN', 'hr-HR', 'hu-HU', 'id-ID', 'it-IT', 'ja-JP', 'ko-KR',
  'ms-MY', 'nl-NL', 'no-NO', 'pl-PL', 'pt-BR', 'pt-PT', 'ro-RO', 'ru-RU',
  'sk-SK', 'sv-SE', 'th-TH', 'tr-TR', 'uk-UA', 'vi-VN', 'zh-CN', 'zh-TW',
];

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

// ── Schema ────────────────────────────────────────────────────────────────────

const regionalSchema = z.object({
  default_currency: z
    .string()
    .optional()
    .refine((v) => !v || v.length === 3, { message: 'Currency must be a 3-letter ISO 4217 code' }),
  default_timezone: z.string().optional(),
  default_language: z.string().optional(),
  fiscal_year_start_month: z
    .number()
    .min(1)
    .max(12)
    .optional()
    .nullable(),
  confirm_currency_change: z.boolean().optional(),
});

type RegionalFormData = z.infer<typeof regionalSchema>;

// ── Component ─────────────────────────────────────────────────────────────────

interface CompanyRegionalSettingsFormProps {
  company: CompanyDetail;
}

export function CompanyRegionalSettingsForm({ company }: CompanyRegionalSettingsFormProps) {
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [showCurrencyWarning, setShowCurrencyWarning] = useState(false);
  const updateCompany = useUpdateCompany();

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isDirty },
  } = useForm<RegionalFormData>({
    resolver: zodResolver(regionalSchema),
    defaultValues: {
      default_currency: company.default_currency ?? '',
      default_timezone: company.default_timezone ?? '',
      default_language: company.default_language ?? '',
      fiscal_year_start_month: company.fiscal_year_start_month ?? null,
      confirm_currency_change: false,
    },
  });

  const watchedCurrency = watch('default_currency');
  const currencyChanged =
    watchedCurrency !== '' && watchedCurrency !== company.default_currency;

  function onSubmit(data: RegionalFormData) {
    setSuccessMessage(null);

    if (currencyChanged && !data.confirm_currency_change) {
      setShowCurrencyWarning(true);
      return;
    }

    const { confirm_currency_change: _omit, ...payload } = data;

    // Strip undefined/null/empty-string values
    const cleaned = Object.fromEntries(
      Object.entries(payload).filter(([, v]) => v !== '' && v !== null && v !== undefined)
    );

    if (currencyChanged) {
      (cleaned as Record<string, unknown>).confirm_currency_change = true;
    }

    updateCompany.mutate(
      { id: company.id, data: cleaned },
      {
        onSuccess: () => {
          setSuccessMessage('Regional settings updated successfully.');
          setShowCurrencyWarning(false);
        },
      }
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
      {/* Currency */}
      <div className="space-y-1">
        <label htmlFor="default_currency" className="text-sm font-medium text-foreground">
          Default Currency
        </label>
        <Input
          id="default_currency"
          type="text"
          list="currency-list"
          placeholder="USD"
          maxLength={3}
          aria-invalid={!!errors.default_currency}
          aria-describedby={errors.default_currency ? 'currency_err' : undefined}
          {...register('default_currency')}
        />
        <datalist id="currency-list">
          {CURRENCIES.map((c) => <option key={c} value={c} />)}
        </datalist>
        {errors.default_currency && (
          <p id="currency_err" role="alert" className="text-xs text-destructive">
            {errors.default_currency.message}
          </p>
        )}
        {currencyChanged && (
          <div className="mt-2 rounded-lg border border-yellow-300 bg-yellow-50 p-3 text-sm text-yellow-800 dark:border-yellow-700 dark:bg-yellow-900/20 dark:text-yellow-300">
            <p className="font-medium">Currency change warning</p>
            <p className="mt-0.5 text-xs">Changing the default currency affects reporting and may impact historical transaction display.</p>
            {showCurrencyWarning && (
              <div className="mt-2 flex items-center gap-2">
                <input
                  id="confirm_currency_change"
                  type="checkbox"
                  {...register('confirm_currency_change')}
                />
                <label htmlFor="confirm_currency_change" className="text-xs select-none">
                  I understand the impact of changing the currency
                </label>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Timezone */}
      <div className="space-y-1">
        <label htmlFor="default_timezone" className="text-sm font-medium text-foreground">
          Timezone
        </label>
        <Input
          id="default_timezone"
          type="text"
          list="timezone-list"
          placeholder="UTC"
          aria-invalid={!!errors.default_timezone}
          {...register('default_timezone')}
        />
        <datalist id="timezone-list">
          {TIMEZONES.map((tz) => <option key={tz} value={tz} />)}
        </datalist>
      </div>

      {/* Language */}
      <div className="space-y-1">
        <label htmlFor="default_language" className="text-sm font-medium text-foreground">
          Language
        </label>
        <Input
          id="default_language"
          type="text"
          list="language-list"
          placeholder="en-US"
          aria-invalid={!!errors.default_language}
          {...register('default_language')}
        />
        <datalist id="language-list">
          {LANGUAGES.map((l) => <option key={l} value={l} />)}
        </datalist>
      </div>

      {/* Fiscal Year Start Month */}
      <div className="space-y-1">
        <label htmlFor="fiscal_year_start_month" className="text-sm font-medium text-foreground">
          Fiscal Year Start Month
        </label>
        <select
          id="fiscal_year_start_month"
          className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          {...register('fiscal_year_start_month', {
            setValueAs: (v: string) => (v === '' ? null : parseInt(v, 10)),
          })}
        >
          <option value="">Select month</option>
          {MONTHS.map((name, i) => (
            <option key={i + 1} value={i + 1}>{name}</option>
          ))}
        </select>
      </div>

      {/* Feedback */}
      {successMessage && (
        <p role="status" className="text-sm text-green-700 dark:text-green-400">
          {successMessage}
        </p>
      )}
      {updateCompany.isError && (
        <p role="alert" className="text-sm text-destructive">
          {updateCompany.error?.message ?? 'Failed to update settings.'}
        </p>
      )}

      <div className="flex justify-end">
        <Button type="submit" disabled={!isDirty || updateCompany.isPending}>
          {updateCompany.isPending ? 'Saving…' : 'Save Changes'}
        </Button>
      </div>
    </form>
  );
}
