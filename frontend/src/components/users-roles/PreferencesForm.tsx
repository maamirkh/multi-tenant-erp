'use client';

/**
 * PreferencesForm — language, timezone, date format, number format, and theme.
 *
 * Uses React Hook Form + Zod (UpdatePreferencesSchema).
 * Theme changes apply immediately to document.documentElement via the `dark`
 * class (Tailwind v4 @custom-variant dark) and are persisted to localStorage
 * so the preference survives page reload before the API response is available.
 *
 * Props:
 *   preferences: current UserPreferences to pre-fill defaults.
 *   onSuccess:   called after a successful PUT /preferences submission.
 *
 * Spec reference: Epic 4, Phase 13 (T119).
 */

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useUpdatePreferences } from '@/hooks/users-roles/usePreferences';
import {
  DATE_FORMATS,
  THEMES,
  UpdatePreferencesSchema,
} from '@/schemas/users-roles';
import type { UpdatePreferencesFormData } from '@/schemas/users-roles';
import { ApiClientError } from '@/lib/api/client';
import type { ThemePreference, UserPreferences } from '@/types/users-roles';

// ── Common timezones ──────────────────────────────────────────────────────────

const COMMON_TIMEZONES = [
  'UTC',
  'Africa/Cairo',
  'Africa/Johannesburg',
  'Africa/Lagos',
  'Africa/Nairobi',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/New_York',
  'America/Sao_Paulo',
  'America/Toronto',
  'Asia/Dhaka',
  'Asia/Dubai',
  'Asia/Jakarta',
  'Asia/Karachi',
  'Asia/Kolkata',
  'Asia/Seoul',
  'Asia/Shanghai',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Australia/Melbourne',
  'Australia/Sydney',
  'Europe/Amsterdam',
  'Europe/Berlin',
  'Europe/Istanbul',
  'Europe/London',
  'Europe/Madrid',
  'Europe/Moscow',
  'Europe/Paris',
  'Pacific/Auckland',
] as const;

// ── Common number format locales ──────────────────────────────────────────────

const NUMBER_FORMATS = [
  { value: 'en-US', label: 'English (US) — 1,234.56' },
  { value: 'en-GB', label: 'English (UK) — 1,234.56' },
  { value: 'fr-FR', label: 'French — 1 234,56' },
  { value: 'de-DE', label: 'German — 1.234,56' },
  { value: 'es-ES', label: 'Spanish — 1.234,56' },
  { value: 'ar-SA', label: 'Arabic — ١٬٢٣٤٫٥٦' },
] as const;

// ── Theme helpers ─────────────────────────────────────────────────────────────

function applyTheme(theme: ThemePreference) {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  if (theme === 'dark') {
    root.classList.add('dark');
  } else if (theme === 'light') {
    root.classList.remove('dark');
  } else {
    // system
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    root.classList.toggle('dark', prefersDark);
  }
  try {
    localStorage.setItem('erp-theme', theme);
  } catch {
    // localStorage unavailable — ignore
  }
}

// ── Component ─────────────────────────────────────────────────────────────────

interface PreferencesFormProps {
  preferences: UserPreferences;
  onSuccess: () => void;
}

function FieldError({ message }: { message: string | undefined }) {
  if (!message) return null;
  return (
    <p className="text-xs text-destructive mt-1" role="alert">
      {message}
    </p>
  );
}

const DATE_FORMAT_LABELS: Record<string, string> = {
  'YYYY-MM-DD': 'ISO — 2026-07-19',
  'DD/MM/YYYY': 'EU — 19/07/2026',
  'MM/DD/YYYY': 'US — 07/19/2026',
  'DD-MM-YYYY': 'Dash — 19-07-2026',
};

const THEME_LABELS: Record<string, string> = {
  light: 'Light',
  dark: 'Dark',
  system: 'System',
};

export function PreferencesForm({ preferences, onSuccess }: PreferencesFormProps) {
  const [serverError, setServerError] = useState<string | undefined>(undefined);
  const [successMessage, setSuccessMessage] = useState<string | undefined>(undefined);

  const updatePreferences = useUpdatePreferences();

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isDirty },
  } = useForm<UpdatePreferencesFormData>({
    resolver: zodResolver(UpdatePreferencesSchema),
    defaultValues: {
      language: preferences.language,
      timezone: preferences.timezone,
      date_format: (preferences.date_format as UpdatePreferencesFormData['date_format']) ?? 'YYYY-MM-DD',
      number_format: preferences.number_format,
      theme: (preferences.theme as UpdatePreferencesFormData['theme']) ?? 'system',
    },
  });

  const currentTheme = watch('theme');

  function handleThemeChange(theme: ThemePreference) {
    setValue('theme', theme, { shouldDirty: true });
    applyTheme(theme);
  }

  function handleSubmitForm(data: UpdatePreferencesFormData) {
    setServerError(undefined);
    setSuccessMessage(undefined);

    updatePreferences.mutate(data, {
      onSuccess: () => {
        setSuccessMessage('Preferences saved.');
        onSuccess();
      },
      onError: (err) => {
        if (err instanceof ApiClientError) {
          setServerError(err.error.error.message);
        } else {
          setServerError(err.message ?? 'Failed to save preferences');
        }
      },
    });
  }

  return (
    <form onSubmit={handleSubmit(handleSubmitForm)} noValidate className="space-y-6">
      {/* Server error */}
      {serverError && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
        >
          {serverError}
        </div>
      )}

      {/* Success message */}
      {successMessage && (
        <div
          role="status"
          className="rounded-lg border border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950/30 p-3 text-sm text-green-700 dark:text-green-400"
        >
          {successMessage}
        </div>
      )}

      {/* Language */}
      <div>
        <label htmlFor="language" className="block text-sm font-medium text-foreground mb-1">
          Language
        </label>
        <Input
          id="language"
          type="text"
          placeholder="e.g. en, fr, pt-BR"
          aria-invalid={!!errors.language}
          {...register('language')}
        />
        <p className="text-xs text-muted-foreground mt-1">BCP-47 language tag.</p>
        <FieldError message={errors.language?.message} />
      </div>

      {/* Timezone */}
      <div>
        <label htmlFor="timezone" className="block text-sm font-medium text-foreground mb-1">
          Timezone
        </label>
        <select
          id="timezone"
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
          aria-invalid={!!errors.timezone}
          {...register('timezone')}
        >
          {COMMON_TIMEZONES.map((tz) => (
            <option key={tz} value={tz}>
              {tz}
            </option>
          ))}
        </select>
        <FieldError message={errors.timezone?.message} />
      </div>

      {/* Date format */}
      <div>
        <label htmlFor="date_format" className="block text-sm font-medium text-foreground mb-1">
          Date Format
        </label>
        <select
          id="date_format"
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
          aria-invalid={!!errors.date_format}
          {...register('date_format')}
        >
          {DATE_FORMATS.map((fmt) => (
            <option key={fmt} value={fmt}>
              {DATE_FORMAT_LABELS[fmt] ?? fmt}
            </option>
          ))}
        </select>
        <FieldError message={errors.date_format?.message} />
      </div>

      {/* Number format */}
      <div>
        <label htmlFor="number_format" className="block text-sm font-medium text-foreground mb-1">
          Number Format
        </label>
        <select
          id="number_format"
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
          aria-invalid={!!errors.number_format}
          {...register('number_format')}
        >
          {NUMBER_FORMATS.map((nf) => (
            <option key={nf.value} value={nf.value}>
              {nf.label}
            </option>
          ))}
        </select>
        <FieldError message={errors.number_format?.message} />
      </div>

      {/* Theme */}
      <div>
        <p className="text-sm font-medium text-foreground mb-2">Theme</p>
        <div className="flex gap-2" role="radiogroup" aria-label="Theme">
          {THEMES.map((t) => (
            <button
              key={t}
              type="button"
              role="radio"
              aria-checked={currentTheme === t}
              onClick={() => handleThemeChange(t)}
              className={`flex-1 rounded-md border px-3 py-2 text-sm font-medium transition-colors ${
                currentTheme === t
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-border bg-background text-foreground hover:bg-muted'
              }`}
            >
              {THEME_LABELS[t]}
            </button>
          ))}
        </div>
        <FieldError message={errors.theme?.message} />
      </div>

      {/* Actions */}
      <div className="flex justify-end pt-2">
        <Button type="submit" disabled={updatePreferences.isPending || !isDirty}>
          {updatePreferences.isPending ? 'Saving…' : 'Save Preferences'}
        </Button>
      </div>
    </form>
  );
}
