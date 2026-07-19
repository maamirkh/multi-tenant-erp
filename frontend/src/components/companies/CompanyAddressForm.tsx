/**
 * T088 — CompanyAddressForm.
 *
 * React Hook Form + Zod form for creating/editing a company address.
 * Country is a searchable input using <datalist> for ISO 3166 lookup.
 * Used as a standalone dialog form within profile settings.
 *
 * Spec ref: Epic 3, Phase 12 (T088).
 */

'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { AddressType, CompanyAddress, CreateAddressInput } from '@/types/companies';

// A curated list of ISO 3166-1 alpha-2 codes and country names for the datalist
const COUNTRIES: { code: string; name: string }[] = [
  { code: 'AF', name: 'Afghanistan' }, { code: 'AL', name: 'Albania' },
  { code: 'DZ', name: 'Algeria' }, { code: 'AR', name: 'Argentina' },
  { code: 'AU', name: 'Australia' }, { code: 'AT', name: 'Austria' },
  { code: 'BE', name: 'Belgium' }, { code: 'BR', name: 'Brazil' },
  { code: 'CA', name: 'Canada' }, { code: 'CL', name: 'Chile' },
  { code: 'CN', name: 'China' }, { code: 'CO', name: 'Colombia' },
  { code: 'HR', name: 'Croatia' }, { code: 'CZ', name: 'Czech Republic' },
  { code: 'DK', name: 'Denmark' }, { code: 'EG', name: 'Egypt' },
  { code: 'FI', name: 'Finland' }, { code: 'FR', name: 'France' },
  { code: 'DE', name: 'Germany' }, { code: 'GH', name: 'Ghana' },
  { code: 'GR', name: 'Greece' }, { code: 'HK', name: 'Hong Kong' },
  { code: 'HU', name: 'Hungary' }, { code: 'IN', name: 'India' },
  { code: 'ID', name: 'Indonesia' }, { code: 'IE', name: 'Ireland' },
  { code: 'IL', name: 'Israel' }, { code: 'IT', name: 'Italy' },
  { code: 'JP', name: 'Japan' }, { code: 'JO', name: 'Jordan' },
  { code: 'KE', name: 'Kenya' }, { code: 'KR', name: 'Korea, South' },
  { code: 'MY', name: 'Malaysia' }, { code: 'MX', name: 'Mexico' },
  { code: 'MA', name: 'Morocco' }, { code: 'NL', name: 'Netherlands' },
  { code: 'NZ', name: 'New Zealand' }, { code: 'NG', name: 'Nigeria' },
  { code: 'NO', name: 'Norway' }, { code: 'PK', name: 'Pakistan' },
  { code: 'PH', name: 'Philippines' }, { code: 'PL', name: 'Poland' },
  { code: 'PT', name: 'Portugal' }, { code: 'RO', name: 'Romania' },
  { code: 'RU', name: 'Russia' }, { code: 'SA', name: 'Saudi Arabia' },
  { code: 'SG', name: 'Singapore' }, { code: 'ZA', name: 'South Africa' },
  { code: 'ES', name: 'Spain' }, { code: 'SE', name: 'Sweden' },
  { code: 'CH', name: 'Switzerland' }, { code: 'TW', name: 'Taiwan' },
  { code: 'TH', name: 'Thailand' }, { code: 'TR', name: 'Turkey' },
  { code: 'UA', name: 'Ukraine' }, { code: 'AE', name: 'United Arab Emirates' },
  { code: 'GB', name: 'United Kingdom' }, { code: 'US', name: 'United States' },
  { code: 'VN', name: 'Vietnam' },
];

const ADDRESS_TYPE_VALUES: AddressType[] = ['registered', 'mailing', 'billing', 'shipping'];

// ── Schema ────────────────────────────────────────────────────────────────────

const addressSchema = z.object({
  address_type: z.enum(['registered', 'mailing', 'billing', 'shipping'] as const),
  street_line_1: z.string().min(1, 'Street address is required'),
  street_line_2: z.string().optional(),
  city: z.string().min(1, 'City is required'),
  state_province: z.string().optional(),
  postal_code: z.string().optional(),
  country: z.string().min(2, 'Country is required').max(2, 'Enter 2-letter ISO code'),
  is_primary: z.boolean().optional(),
});

type AddressFormData = z.infer<typeof addressSchema>;

// ── Component ─────────────────────────────────────────────────────────────────

interface CompanyAddressFormProps {
  /** Existing address to edit; omit for create mode. */
  address?: CompanyAddress;
  /** Called when form is submitted with valid data. */
  onSubmit: (data: CreateAddressInput) => void;
  /** Called when user cancels. */
  onCancel: () => void;
  isPending?: boolean;
  error?: string | null;
}

export function CompanyAddressForm({
  address,
  onSubmit,
  onCancel,
  isPending = false,
  error,
}: CompanyAddressFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<AddressFormData>({
    resolver: zodResolver(addressSchema),
    defaultValues: address
      ? {
          address_type: address.address_type,
          street_line_1: address.street_line_1,
          street_line_2: address.street_line_2 ?? '',
          city: address.city,
          state_province: address.state_province ?? '',
          postal_code: address.postal_code ?? '',
          country: address.country,
          is_primary: address.is_primary,
        }
      : { address_type: 'registered', is_primary: false },
  });

  // With exactOptionalPropertyTypes, the Zod-inferred type for optional
  // string fields is `string | undefined`, but CreateAddressInput uses
  // exactOptional semantics. We cast here to satisfy the external contract.
  function handleSubmitCast(data: {
    address_type: 'registered' | 'mailing' | 'billing' | 'shipping';
    street_line_1: string;
    street_line_2?: string | undefined;
    city: string;
    state_province?: string | undefined;
    postal_code?: string | undefined;
    country: string;
    is_primary?: boolean | undefined;
  }) {
    onSubmit(data as Parameters<typeof onSubmit>[0]);
  }

  return (
    <form onSubmit={handleSubmit(handleSubmitCast)} noValidate className="space-y-4">
      {/* Address Type */}
      <div className="space-y-1">
        <label htmlFor="address_type" className="text-sm font-medium text-foreground">
          Address Type <span aria-hidden="true" className="text-destructive">*</span>
        </label>
        <select
          id="address_type"
          className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          aria-invalid={!!errors.address_type}
          {...register('address_type')}
        >
          {ADDRESS_TYPE_VALUES.map((t) => (
            <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
          ))}
        </select>
      </div>

      {/* Street Line 1 */}
      <div className="space-y-1">
        <label htmlFor="street_line_1" className="text-sm font-medium text-foreground">
          Street Address <span aria-hidden="true" className="text-destructive">*</span>
        </label>
        <Input
          id="street_line_1"
          type="text"
          placeholder="123 Main St"
          aria-invalid={!!errors.street_line_1}
          aria-describedby={errors.street_line_1 ? 'street1_err' : undefined}
          {...register('street_line_1')}
        />
        {errors.street_line_1 && (
          <p id="street1_err" role="alert" className="text-xs text-destructive">
            {errors.street_line_1.message}
          </p>
        )}
      </div>

      {/* Street Line 2 */}
      <div className="space-y-1">
        <label htmlFor="street_line_2" className="text-sm font-medium text-foreground">
          Suite/Apt <span className="text-xs text-muted-foreground">(optional)</span>
        </label>
        <Input id="street_line_2" type="text" {...register('street_line_2')} />
      </div>

      {/* City + State in a row */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1">
          <label htmlFor="city" className="text-sm font-medium text-foreground">
            City <span aria-hidden="true" className="text-destructive">*</span>
          </label>
          <Input
            id="city"
            type="text"
            aria-invalid={!!errors.city}
            aria-describedby={errors.city ? 'city_err' : undefined}
            {...register('city')}
          />
          {errors.city && (
            <p id="city_err" role="alert" className="text-xs text-destructive">
              {errors.city.message}
            </p>
          )}
        </div>
        <div className="space-y-1">
          <label htmlFor="state_province" className="text-sm font-medium text-foreground">
            State/Province <span className="text-xs text-muted-foreground">(optional)</span>
          </label>
          <Input id="state_province" type="text" {...register('state_province')} />
        </div>
      </div>

      {/* Postal Code + Country */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1">
          <label htmlFor="postal_code" className="text-sm font-medium text-foreground">
            Postal Code <span className="text-xs text-muted-foreground">(optional)</span>
          </label>
          <Input id="postal_code" type="text" {...register('postal_code')} />
        </div>
        <div className="space-y-1">
          <label htmlFor="country" className="text-sm font-medium text-foreground">
            Country <span aria-hidden="true" className="text-destructive">*</span>
          </label>
          {/* datalist provides searchable native suggestions */}
          <Input
            id="country"
            type="text"
            list="country-list"
            placeholder="US"
            maxLength={2}
            aria-invalid={!!errors.country}
            aria-describedby={errors.country ? 'country_err' : undefined}
            {...register('country')}
          />
          <datalist id="country-list">
            {COUNTRIES.map(({ code, name }) => (
              <option key={code} value={code}>{name}</option>
            ))}
          </datalist>
          {errors.country && (
            <p id="country_err" role="alert" className="text-xs text-destructive">
              {errors.country.message}
            </p>
          )}
        </div>
      </div>

      {/* Primary Address */}
      <div className="flex items-center gap-2">
        <input
          id="is_primary"
          type="checkbox"
          {...register('is_primary')}
        />
        <label htmlFor="is_primary" className="text-sm text-foreground select-none">
          Set as primary address
        </label>
      </div>

      {/* Error */}
      {error && (
        <p role="alert" className="text-sm text-destructive">{error}</p>
      )}

      {/* Actions */}
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onCancel} disabled={isPending}>
          Cancel
        </Button>
        <Button type="submit" disabled={isPending}>
          {isPending ? 'Saving…' : address ? 'Update Address' : 'Add Address'}
        </Button>
      </div>
    </form>
  );
}
