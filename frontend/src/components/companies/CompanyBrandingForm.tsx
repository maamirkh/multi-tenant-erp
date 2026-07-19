/**
 * T091 — CompanyBrandingForm.
 *
 * Logo upload section + primary/secondary hex color inputs +
 * tagline (max 255 chars) + live preview panel.
 * Calls useUpdateCompany() on save.
 *
 * Spec ref: Epic 3, Phase 12 (T091).
 */

'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { CompanyLogoUpload } from '@/components/companies/CompanyLogoUpload';
import { useUpdateCompany } from '@/hooks/companies/useUpdateCompany';
import type { CompanyDetail } from '@/types/companies';

// ── Schema ────────────────────────────────────────────────────────────────────

const HEX_RE = /^#[0-9A-Fa-f]{6}$/;

const brandingSchema = z.object({
  brand_color_primary: z
    .string()
    .optional()
    .refine((v) => !v || HEX_RE.test(v), { message: 'Enter a valid hex color (e.g. #FF5733)' }),
  brand_color_secondary: z
    .string()
    .optional()
    .refine((v) => !v || HEX_RE.test(v), { message: 'Enter a valid hex color (e.g. #336699)' }),
  tagline: z
    .string()
    .max(255, 'Tagline must be 255 characters or fewer')
    .optional(),
});

type BrandingFormData = z.infer<typeof brandingSchema>;

// ── Component ─────────────────────────────────────────────────────────────────

interface CompanyBrandingFormProps {
  company: CompanyDetail;
}

export function CompanyBrandingForm({ company }: CompanyBrandingFormProps) {
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const updateCompany = useUpdateCompany();

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isDirty },
  } = useForm<BrandingFormData>({
    resolver: zodResolver(brandingSchema),
    defaultValues: {
      brand_color_primary: company.brand_color_primary ?? '',
      brand_color_secondary: company.brand_color_secondary ?? '',
      tagline: company.tagline ?? '',
    },
  });

  const watchedPrimary = watch('brand_color_primary') ?? '';
  const watchedSecondary = watch('brand_color_secondary') ?? '';
  const watchedTagline = watch('tagline') ?? '';

  function onSubmit(data: BrandingFormData) {
    setSuccessMessage(null);

    const payload = Object.fromEntries(
      Object.entries(data).filter(([, v]) => v !== '' && v !== undefined)
    );

    updateCompany.mutate(
      { id: company.id, data: payload },
      {
        onSuccess: () => {
          setSuccessMessage('Branding updated successfully.');
        },
      }
    );
  }

  // Whether a string is a valid hex color for the preview swatch
  function isValidHex(color: string): boolean {
    return HEX_RE.test(color);
  }

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
      {/* Form */}
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-6">
        {/* Logo */}
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-foreground">Company Logo</h3>
          <CompanyLogoUpload
            companyId={company.id}
            currentLogoUrl={company.logo_url}
          />
        </div>

        {/* Primary Color */}
        <div className="space-y-1">
          <label htmlFor="brand_color_primary" className="text-sm font-medium text-foreground">
            Primary Brand Color <span className="text-xs text-muted-foreground">(optional)</span>
          </label>
          <div className="flex items-center gap-2">
            <Input
              id="brand_color_primary"
              type="text"
              placeholder="#FF5733"
              maxLength={7}
              aria-invalid={!!errors.brand_color_primary}
              aria-describedby={errors.brand_color_primary ? 'primary_color_err' : undefined}
              {...register('brand_color_primary')}
              className="font-mono"
            />
            {isValidHex(watchedPrimary) && (
              <div
                className="h-8 w-8 flex-shrink-0 rounded border border-border"
                style={{ backgroundColor: watchedPrimary }}
                aria-label={`Primary color preview: ${watchedPrimary}`}
              />
            )}
          </div>
          {errors.brand_color_primary && (
            <p id="primary_color_err" role="alert" className="text-xs text-destructive">
              {errors.brand_color_primary.message}
            </p>
          )}
        </div>

        {/* Secondary Color */}
        <div className="space-y-1">
          <label htmlFor="brand_color_secondary" className="text-sm font-medium text-foreground">
            Secondary Brand Color <span className="text-xs text-muted-foreground">(optional)</span>
          </label>
          <div className="flex items-center gap-2">
            <Input
              id="brand_color_secondary"
              type="text"
              placeholder="#336699"
              maxLength={7}
              aria-invalid={!!errors.brand_color_secondary}
              aria-describedby={errors.brand_color_secondary ? 'secondary_color_err' : undefined}
              {...register('brand_color_secondary')}
              className="font-mono"
            />
            {isValidHex(watchedSecondary) && (
              <div
                className="h-8 w-8 flex-shrink-0 rounded border border-border"
                style={{ backgroundColor: watchedSecondary }}
                aria-label={`Secondary color preview: ${watchedSecondary}`}
              />
            )}
          </div>
          {errors.brand_color_secondary && (
            <p id="secondary_color_err" role="alert" className="text-xs text-destructive">
              {errors.brand_color_secondary.message}
            </p>
          )}
        </div>

        {/* Tagline */}
        <div className="space-y-1">
          <label htmlFor="tagline" className="text-sm font-medium text-foreground">
            Tagline <span className="text-xs text-muted-foreground">(optional)</span>
          </label>
          <Input
            id="tagline"
            type="text"
            placeholder="Your company tagline"
            maxLength={255}
            aria-invalid={!!errors.tagline}
            aria-describedby={errors.tagline ? 'tagline_err' : 'tagline_count'}
            {...register('tagline')}
          />
          <div className="flex justify-between">
            {errors.tagline ? (
              <p id="tagline_err" role="alert" className="text-xs text-destructive">
                {errors.tagline.message}
              </p>
            ) : (
              <span />
            )}
            <p id="tagline_count" className="text-xs text-muted-foreground">
              {watchedTagline.length}/255
            </p>
          </div>
        </div>

        {/* Feedback */}
        {successMessage && (
          <p role="status" className="text-sm text-green-700 dark:text-green-400">
            {successMessage}
          </p>
        )}
        {updateCompany.isError && (
          <p role="alert" className="text-sm text-destructive">
            {updateCompany.error?.message ?? 'Failed to update branding.'}
          </p>
        )}

        <div className="flex justify-end">
          <Button type="submit" disabled={!isDirty || updateCompany.isPending}>
            {updateCompany.isPending ? 'Saving…' : 'Save Changes'}
          </Button>
        </div>
      </form>

      {/* Live Preview Panel */}
      <div className="space-y-2">
        <h3 className="text-sm font-medium text-foreground">Preview</h3>
        <div
          className="rounded-xl border border-border bg-card p-6 space-y-4 shadow-sm"
          aria-label="Branding preview"
        >
          {/* Logo preview */}
          {company.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={company.logo_url}
              alt="Company logo"
              className="h-14 w-14 rounded object-contain bg-muted"
            />
          ) : (
            <div className="flex h-14 w-14 items-center justify-center rounded bg-muted text-xs text-muted-foreground">
              Logo
            </div>
          )}

          {/* Color swatches */}
          <div className="flex gap-3">
            <div className="space-y-1">
              <div
                className="h-8 w-20 rounded border border-border"
                style={{
                  backgroundColor: isValidHex(watchedPrimary) ? watchedPrimary : '#e5e7eb',
                }}
              />
              <p className="text-xs text-muted-foreground">Primary</p>
            </div>
            <div className="space-y-1">
              <div
                className="h-8 w-20 rounded border border-border"
                style={{
                  backgroundColor: isValidHex(watchedSecondary) ? watchedSecondary : '#e5e7eb',
                }}
              />
              <p className="text-xs text-muted-foreground">Secondary</p>
            </div>
          </div>

          {/* Tagline preview */}
          {watchedTagline && (
            <p className="text-sm italic text-muted-foreground">&ldquo;{watchedTagline}&rdquo;</p>
          )}

          {/* Company name */}
          <p className="font-semibold text-foreground">{company.legal_name}</p>
        </div>
      </div>
    </div>
  );
}
