/**
 * T087 — CompanyProfileForm.
 *
 * React Hook Form + Zod form for updating company profile fields.
 * Calls useUpdateCompany() on submit. Maps API error details[] to field
 * errors via setError(). Shows inline success/error messages.
 *
 * Zod mirrors backend validation: legal_name min 2, email RFC, phone optional.
 *
 * Spec ref: Epic 3, Phase 12 (T087).
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

// ── Schema ────────────────────────────────────────────────────────────────────

const BUSINESS_TYPE_VALUES = [
  'sole_proprietor',
  'partnership',
  'llc',
  'corporation',
  'non_profit',
  'other',
] as const;

const BUSINESS_TYPE_LABELS: Record<string, string> = {
  sole_proprietor: 'Sole Proprietor',
  partnership: 'Partnership',
  llc: 'LLC',
  corporation: 'Corporation',
  non_profit: 'Non-Profit',
  other: 'Other',
};

const profileSchema = z.object({
  legal_name: z.string().min(2, 'Company name must be at least 2 characters'),
  trade_name: z.string().optional(),
  email: z.string().email('Enter a valid email address'),
  phone_primary: z
    .string()
    .optional()
    .refine((v) => !v || /^\+[1-9]\d{1,14}$/.test(v), {
      message: 'Enter E.164 phone format (e.g. +12125551234)',
    }),
  phone_secondary: z
    .string()
    .optional()
    .refine((v) => !v || /^\+[1-9]\d{1,14}$/.test(v), {
      message: 'Enter E.164 phone format (e.g. +12125551234)',
    }),
  website: z
    .string()
    .optional()
    .refine((v) => !v || /^https?:\/\//.test(v), {
      message: 'Enter a valid URL (must start with http:// or https://)',
    }),
  tax_number: z.string().optional(),
  registration_number: z.string().optional(),
  business_category: z.string().optional(),
  business_type: z.enum(BUSINESS_TYPE_VALUES).optional(),
  incorporation_date: z.string().optional(),
});

type ProfileFormData = z.infer<typeof profileSchema>;

// ── Component ─────────────────────────────────────────────────────────────────

interface CompanyProfileFormProps {
  company: CompanyDetail;
}

export function CompanyProfileForm({ company }: CompanyProfileFormProps) {
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const updateCompany = useUpdateCompany();

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isDirty },
  } = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      legal_name: company.legal_name,
      trade_name: company.trade_name ?? '',
      email: company.email,
      phone_primary: company.phone_primary ?? '',
      phone_secondary: company.phone_secondary ?? '',
      website: company.website ?? '',
      tax_number: company.tax_number ?? '',
      registration_number: company.registration_number ?? '',
      business_category: company.business_category ?? '',
      business_type: company.business_type ?? undefined,
      incorporation_date: company.incorporation_date ?? '',
    },
  });

  function onSubmit(data: ProfileFormData) {
    setSuccessMessage(null);

    // Strip empty strings to avoid overwriting with blank values
    const payload = Object.fromEntries(
      Object.entries(data).filter(([, v]) => v !== '' && v !== undefined)
    );

    updateCompany.mutate(
      { id: company.id, data: payload },
      {
        onSuccess: () => {
          setSuccessMessage('Profile updated successfully.');
        },
        onError: (err) => {
          // Attempt to map structured API error details to form fields
          try {
            const apiErr = err as { details?: Record<string, string[]> };
            if (apiErr.details) {
              for (const [field, messages] of Object.entries(apiErr.details)) {
                setError(field as keyof ProfileFormData, {
                  type: 'server',
                  message: Array.isArray(messages) ? (messages[0] ?? 'Validation error') : String(messages),
                });
              }
            }
          } catch {
            // Ignore mapping errors — generic error shown below
          }
        },
      }
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
      {/* Legal Name */}
      <div className="space-y-1">
        <label htmlFor="legal_name" className="text-sm font-medium text-foreground">
          Company Name <span aria-hidden="true" className="text-destructive">*</span>
        </label>
        <Input
          id="legal_name"
          type="text"
          aria-invalid={!!errors.legal_name}
          aria-describedby={errors.legal_name ? 'legal_name_err' : undefined}
          {...register('legal_name')}
        />
        {errors.legal_name && (
          <p id="legal_name_err" role="alert" className="text-xs text-destructive">
            {errors.legal_name.message}
          </p>
        )}
      </div>

      {/* Trade Name */}
      <div className="space-y-1">
        <label htmlFor="trade_name" className="text-sm font-medium text-foreground">
          Trade Name <span className="text-xs text-muted-foreground">(optional)</span>
        </label>
        <Input id="trade_name" type="text" {...register('trade_name')} />
      </div>

      {/* Email */}
      <div className="space-y-1">
        <label htmlFor="email" className="text-sm font-medium text-foreground">
          Business Email <span aria-hidden="true" className="text-destructive">*</span>
        </label>
        <Input
          id="email"
          type="email"
          aria-invalid={!!errors.email}
          aria-describedby={errors.email ? 'email_err' : undefined}
          {...register('email')}
        />
        {errors.email && (
          <p id="email_err" role="alert" className="text-xs text-destructive">
            {errors.email.message}
          </p>
        )}
      </div>

      {/* Phone Primary */}
      <div className="space-y-1">
        <label htmlFor="phone_primary" className="text-sm font-medium text-foreground">
          Phone <span className="text-xs text-muted-foreground">(E.164, optional)</span>
        </label>
        <Input
          id="phone_primary"
          type="tel"
          placeholder="+12125551234"
          aria-invalid={!!errors.phone_primary}
          aria-describedby={errors.phone_primary ? 'phone_primary_err' : undefined}
          {...register('phone_primary')}
        />
        {errors.phone_primary && (
          <p id="phone_primary_err" role="alert" className="text-xs text-destructive">
            {errors.phone_primary.message}
          </p>
        )}
      </div>

      {/* Phone Secondary */}
      <div className="space-y-1">
        <label htmlFor="phone_secondary" className="text-sm font-medium text-foreground">
          Secondary Phone <span className="text-xs text-muted-foreground">(optional)</span>
        </label>
        <Input
          id="phone_secondary"
          type="tel"
          placeholder="+12125551234"
          aria-invalid={!!errors.phone_secondary}
          aria-describedby={errors.phone_secondary ? 'phone_secondary_err' : undefined}
          {...register('phone_secondary')}
        />
        {errors.phone_secondary && (
          <p id="phone_secondary_err" role="alert" className="text-xs text-destructive">
            {errors.phone_secondary.message}
          </p>
        )}
      </div>

      {/* Website */}
      <div className="space-y-1">
        <label htmlFor="website" className="text-sm font-medium text-foreground">
          Website <span className="text-xs text-muted-foreground">(optional)</span>
        </label>
        <Input
          id="website"
          type="url"
          placeholder="https://example.com"
          aria-invalid={!!errors.website}
          aria-describedby={errors.website ? 'website_err' : undefined}
          {...register('website')}
        />
        {errors.website && (
          <p id="website_err" role="alert" className="text-xs text-destructive">
            {errors.website.message}
          </p>
        )}
      </div>

      {/* Two-column row: Tax Number + Registration Number */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1">
          <label htmlFor="tax_number" className="text-sm font-medium text-foreground">
            Tax Number <span className="text-xs text-muted-foreground">(optional)</span>
          </label>
          <Input id="tax_number" type="text" {...register('tax_number')} />
        </div>
        <div className="space-y-1">
          <label htmlFor="registration_number" className="text-sm font-medium text-foreground">
            Registration Number <span className="text-xs text-muted-foreground">(optional)</span>
          </label>
          <Input id="registration_number" type="text" {...register('registration_number')} />
        </div>
      </div>

      {/* Business Category */}
      <div className="space-y-1">
        <label htmlFor="business_category" className="text-sm font-medium text-foreground">
          Business Category <span className="text-xs text-muted-foreground">(optional)</span>
        </label>
        <Input id="business_category" type="text" placeholder="e.g. Technology" {...register('business_category')} />
      </div>

      {/* Business Type */}
      <div className="space-y-1">
        <label htmlFor="business_type" className="text-sm font-medium text-foreground">
          Business Type <span className="text-xs text-muted-foreground">(optional)</span>
        </label>
        <select
          id="business_type"
          className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          {...register('business_type', {
            setValueAs: (v: string) => (v === '' ? undefined : v),
          })}
        >
          <option value="">Select type</option>
          {BUSINESS_TYPE_VALUES.map((v) => (
            <option key={v} value={v}>{BUSINESS_TYPE_LABELS[v]}</option>
          ))}
        </select>
      </div>

      {/* Incorporation Date */}
      <div className="space-y-1">
        <label htmlFor="incorporation_date" className="text-sm font-medium text-foreground">
          Incorporation Date <span className="text-xs text-muted-foreground">(optional)</span>
        </label>
        <Input
          id="incorporation_date"
          type="date"
          {...register('incorporation_date')}
        />
      </div>

      {/* Feedback */}
      {successMessage && (
        <p role="status" className="text-sm text-green-700 dark:text-green-400">
          {successMessage}
        </p>
      )}
      {updateCompany.isError && !updateCompany.isPending && (
        <p role="alert" className="text-sm text-destructive">
          {updateCompany.error?.message ?? 'Failed to update profile. Please try again.'}
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
