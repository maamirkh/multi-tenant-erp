/**
 * T077 — CompanyCreateWizard.
 *
 * 4-step wizard using React Hook Form + Zod:
 *   Step 1: legal_name, trade_name, email, business_type
 *   Step 2: country, default_currency, default_timezone, default_language
 *   Step 3: branding (optional, skip button)
 *   Step 4: review and submit
 *
 * On submit calls useCreateCompany() mutation.
 * On success redirects to /companies/{id}.
 * Zod schemas validate each step independently before allowing Next.
 *
 * Spec ref: Epic 3, Phase 11 (T077).
 */

'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useRouter } from 'next/navigation';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { CompanyStatusBadge } from '@/components/companies/CompanyStatusBadge';
import { useCreateCompany } from '@/hooks/companies/useCreateCompany';
import type { CreateCompanyInput, BusinessType } from '@/types/companies';

// ── Zod schemas per step ──────────────────────────────────────────────────────

const BUSINESS_TYPE_VALUES = [
  'sole_proprietor',
  'partnership',
  'llc',
  'corporation',
  'non_profit',
  'other',
] as const;

const step1Schema = z.object({
  legal_name: z.string().min(2, 'Company name must be at least 2 characters'),
  trade_name: z.string().optional(),
  email: z.string().email('Please enter a valid email address'),
  business_type: z.enum(BUSINESS_TYPE_VALUES).optional(),
});

const step2Schema = z.object({
  country: z
    .string()
    .optional()
    .refine((v) => !v || v.length === 2, { message: 'Country must be a 2-letter ISO code' }),
  default_currency: z
    .string()
    .optional()
    .refine((v) => !v || v.length === 3, { message: 'Currency must be a 3-letter code' }),
  default_timezone: z.string().optional(),
  default_language: z.string().optional(),
});


type Step1Data = z.infer<typeof step1Schema>;
type Step2Data = z.infer<typeof step2Schema>;

const BUSINESS_TYPE_LABELS: Record<string, string> = {
  sole_proprietor: 'Sole Proprietor',
  partnership: 'Partnership',
  llc: 'LLC',
  corporation: 'Corporation',
  non_profit: 'Non-Profit',
  other: 'Other',
};

const STEPS = ['Basic Info', 'Regional', 'Branding', 'Review'] as const;

// ── Subform components ────────────────────────────────────────────────────────

interface Step1FormProps {
  defaultValues?: Partial<Step1Data>;
  onNext: (data: Step1Data) => void;
}

function Step1Form({ defaultValues, onNext }: Step1FormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Step1Data>({
    resolver: zodResolver(step1Schema),
    defaultValues: defaultValues ?? {},
  });

  return (
    <form onSubmit={handleSubmit(onNext)} noValidate className="space-y-4">
      <div className="space-y-1">
        <label htmlFor="legal_name" className="text-sm font-medium text-foreground">
          Company Name <span aria-hidden="true" className="text-destructive">*</span>
        </label>
        <Input
          id="legal_name"
          type="text"
          placeholder="Acme Inc."
          aria-invalid={!!errors.legal_name}
          aria-describedby={errors.legal_name ? 'legal_name_error' : undefined}
          {...register('legal_name')}
        />
        {errors.legal_name && (
          <p id="legal_name_error" className="text-xs text-destructive" role="alert">
            {errors.legal_name.message}
          </p>
        )}
      </div>

      <div className="space-y-1">
        <label htmlFor="trade_name" className="text-sm font-medium text-foreground">
          Trade Name <span className="text-xs text-muted-foreground">(optional)</span>
        </label>
        <Input id="trade_name" type="text" placeholder="Acme" {...register('trade_name')} />
      </div>

      <div className="space-y-1">
        <label htmlFor="email" className="text-sm font-medium text-foreground">
          Business Email <span aria-hidden="true" className="text-destructive">*</span>
        </label>
        <Input
          id="email"
          type="email"
          placeholder="contact@acme.com"
          aria-invalid={!!errors.email}
          aria-describedby={errors.email ? 'email_error' : undefined}
          {...register('email')}
        />
        {errors.email && (
          <p id="email_error" className="text-xs text-destructive" role="alert">
            {errors.email.message}
          </p>
        )}
      </div>

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
          {Object.entries(BUSINESS_TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </div>

      <div className="flex justify-end pt-2">
        <Button type="submit">Next</Button>
      </div>
    </form>
  );
}

interface Step2FormProps {
  defaultValues?: Partial<Step2Data>;
  onNext: (data: Step2Data) => void;
  onBack: () => void;
}

function Step2Form({ defaultValues, onNext, onBack }: Step2FormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Step2Data>({
    resolver: zodResolver(step2Schema),
    defaultValues: defaultValues ?? {},
  });

  return (
    <form onSubmit={handleSubmit(onNext)} noValidate className="space-y-4">
      <div className="space-y-1">
        <label htmlFor="country" className="text-sm font-medium text-foreground">
          Country <span className="text-xs text-muted-foreground">(ISO 2-letter, e.g. US)</span>
        </label>
        <Input
          id="country"
          type="text"
          placeholder="US"
          maxLength={2}
          aria-invalid={!!errors.country}
          aria-describedby={errors.country ? 'country_error' : undefined}
          {...register('country')}
        />
        {errors.country && (
          <p id="country_error" className="text-xs text-destructive" role="alert">
            {errors.country.message}
          </p>
        )}
      </div>

      <div className="space-y-1">
        <label htmlFor="default_currency" className="text-sm font-medium text-foreground">
          Default Currency <span className="text-xs text-muted-foreground">(ISO 3-letter, e.g. USD)</span>
        </label>
        <Input
          id="default_currency"
          type="text"
          placeholder="USD"
          maxLength={3}
          aria-invalid={!!errors.default_currency}
          aria-describedby={errors.default_currency ? 'currency_error' : undefined}
          {...register('default_currency')}
        />
        {errors.default_currency && (
          <p id="currency_error" className="text-xs text-destructive" role="alert">
            {errors.default_currency.message}
          </p>
        )}
      </div>

      <div className="space-y-1">
        <label htmlFor="default_timezone" className="text-sm font-medium text-foreground">
          Timezone <span className="text-xs text-muted-foreground">(e.g. America/New_York)</span>
        </label>
        <Input
          id="default_timezone"
          type="text"
          placeholder="UTC"
          {...register('default_timezone')}
        />
      </div>

      <div className="space-y-1">
        <label htmlFor="default_language" className="text-sm font-medium text-foreground">
          Language <span className="text-xs text-muted-foreground">(e.g. en-US)</span>
        </label>
        <Input
          id="default_language"
          type="text"
          placeholder="en-US"
          {...register('default_language')}
        />
      </div>

      <div className="flex justify-between pt-2">
        <Button type="button" variant="outline" onClick={onBack}>Back</Button>
        <Button type="submit">Next</Button>
      </div>
    </form>
  );
}

interface Step3FormProps {
  onNext: () => void;
  onBack: () => void;
  onSkip: () => void;
}

function Step3Form({ onNext, onBack, onSkip }: Step3FormProps) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Branding settings (logo, colors) can be configured after company creation.
        You can skip this step for now.
      </p>
      <div className="flex justify-between pt-2">
        <Button type="button" variant="outline" onClick={onBack}>Back</Button>
        <div className="flex gap-2">
          <Button type="button" variant="ghost" onClick={onSkip}>Skip</Button>
          <Button type="button" onClick={onNext}>Next</Button>
        </div>
      </div>
    </div>
  );
}

// ── Wizard state ──────────────────────────────────────────────────────────────

interface WizardData {
  step1: Step1Data;
  step2: Partial<Step2Data>;
}

interface ReviewStepProps {
  data: WizardData;
  onSubmit: () => void;
  onBack: () => void;
  isSubmitting: boolean;
  error: string | null;
}

function ReviewStep({ data, onSubmit, onBack, isSubmitting, error }: ReviewStepProps) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-border p-4 space-y-3 text-sm">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Company Name</span>
          <span className="font-medium">{data.step1.legal_name}</span>
        </div>
        {data.step1.trade_name && (
          <div className="flex justify-between">
            <span className="text-muted-foreground">Trade Name</span>
            <span>{data.step1.trade_name}</span>
          </div>
        )}
        <div className="flex justify-between">
          <span className="text-muted-foreground">Email</span>
          <span>{data.step1.email}</span>
        </div>
        {data.step1.business_type && (
          <div className="flex justify-between">
            <span className="text-muted-foreground">Business Type</span>
            <span>{BUSINESS_TYPE_LABELS[data.step1.business_type] ?? data.step1.business_type}</span>
          </div>
        )}
        {data.step2.country && (
          <div className="flex justify-between">
            <span className="text-muted-foreground">Country</span>
            <span>{data.step2.country}</span>
          </div>
        )}
        {data.step2.default_currency && (
          <div className="flex justify-between">
            <span className="text-muted-foreground">Currency</span>
            <span>{data.step2.default_currency}</span>
          </div>
        )}
        <div className="flex justify-between items-center">
          <span className="text-muted-foreground">Status after creation</span>
          <CompanyStatusBadge status="pending_setup" />
        </div>
      </div>

      {error && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="flex justify-between pt-2">
        <Button type="button" variant="outline" onClick={onBack} disabled={isSubmitting}>
          Back
        </Button>
        <Button type="button" onClick={onSubmit} disabled={isSubmitting}>
          {isSubmitting ? 'Creating…' : 'Create Company'}
        </Button>
      </div>
    </div>
  );
}

// ── Main wizard component ─────────────────────────────────────────────────────

export function CompanyCreateWizard() {
  const router = useRouter();
  const createCompany = useCreateCompany();

  const [step, setStep] = useState(0);
  const [step1Data, setStep1Data] = useState<Step1Data | null>(null);
  const [step2Data, setStep2Data] = useState<Partial<Step2Data>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  function handleStep1Next(data: Step1Data) {
    setStep1Data(data);
    setStep(1);
  }

  function handleStep2Next(data: Step2Data) {
    setStep2Data(data);
    setStep(2);
  }

  function handleStep3Next() {
    setStep(3);
  }

  function handleStep3Skip() {
    setStep(3);
  }

  function handleSubmit() {
    if (!step1Data) return;

    setSubmitError(null);

    const input: CreateCompanyInput = {
      legal_name: step1Data.legal_name,
      email: step1Data.email,
      ...(step1Data.trade_name ? { trade_name: step1Data.trade_name } : {}),
      ...(step1Data.business_type ? { business_type: step1Data.business_type as BusinessType } : {}),
      ...(step2Data.country ? { country: step2Data.country } : {}),
      ...(step2Data.default_currency ? { default_currency: step2Data.default_currency } : {}),
      ...(step2Data.default_timezone ? { default_timezone: step2Data.default_timezone } : {}),
      ...(step2Data.default_language ? { default_language: step2Data.default_language } : {}),
    };

    createCompany.mutate(input, {
      onSuccess: (company) => {
        router.push(`/companies/${company.id}`);
      },
      onError: (err) => {
        setSubmitError(err.message ?? 'Failed to create company. Please try again.');
      },
    });
  }

  return (
    <Card className="mx-auto max-w-lg">
      <CardHeader>
        <CardTitle>Create Company</CardTitle>
        <CardDescription>
          Step {step + 1} of {STEPS.length}: {STEPS[step]}
        </CardDescription>
        {/* Step indicator */}
        <div className="flex gap-1 pt-1" role="list" aria-label="Wizard steps">
          {STEPS.map((label, i) => (
            <div
              key={label}
              role="listitem"
              aria-current={i === step ? 'step' : undefined}
              className={`h-1 flex-1 rounded-full transition-colors ${
                i <= step ? 'bg-primary' : 'bg-muted'
              }`}
            />
          ))}
        </div>
      </CardHeader>

      <CardContent>
        {step === 0 && (
          <Step1Form
            {...(step1Data ? { defaultValues: step1Data } : {})}
            onNext={handleStep1Next}
          />
        )}
        {step === 1 && (
          <Step2Form
            defaultValues={step2Data}
            onNext={handleStep2Next}
            onBack={() => setStep(0)}
          />
        )}
        {step === 2 && (
          <Step3Form
            onNext={handleStep3Next}
            onBack={() => setStep(1)}
            onSkip={handleStep3Skip}
          />
        )}
        {step === 3 && step1Data && (
          <ReviewStep
            data={{ step1: step1Data, step2: step2Data }}
            onSubmit={handleSubmit}
            onBack={() => setStep(2)}
            isSubmitting={createCompany.isPending}
            error={submitError}
          />
        )}
      </CardContent>
    </Card>
  );
}
