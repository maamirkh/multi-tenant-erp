'use client';

/**
 * ResetPasswordForm — set a new password using a reset token from the URL.
 *
 * Reads `?token=` from the URL search params.
 * On success: redirects to /login with a toast-style message.
 * On 400 (invalid/expired token): shows an error with a link to /forgot-password.
 * Password show/hide toggle included.
 * Accessible: labels, aria-describedby on errors, aria-label on toggle button.
 */

import { useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { resetPasswordApi } from '@/lib/api/auth';
import { ApiClientError } from '@/lib/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const resetSchema = z
  .object({
    new_password: z
      .string()
      .min(12, 'Password must be at least 12 characters.'),
    confirm_password: z.string().min(1, 'Please confirm your password.'),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: 'Passwords do not match.',
    path: ['confirm_password'],
  });

type ResetPasswordFormValues = z.infer<typeof resetSchema>;

export function ResetPasswordForm(): React.JSX.Element {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token') ?? '';

  const [showPassword, setShowPassword] = useState(false);
  const [tokenError, setTokenError] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetSchema),
    defaultValues: { new_password: '', confirm_password: '' },
  });

  async function onSubmit(values: ResetPasswordFormValues): Promise<void> {
    setServerError(null);
    setTokenError(false);

    if (!token) {
      setTokenError(true);
      return;
    }

    try {
      await resetPasswordApi(token, values.new_password);
      // On success: redirect with a success indicator via search param.
      router.push('/login?reset=success');
    } catch (err) {
      if (err instanceof ApiClientError && (err.status === 400 || err.status === 401)) {
        setTokenError(true);
      } else if (err instanceof ApiClientError && err.status === 422) {
        setServerError(err.error.error.message ?? 'Password does not meet requirements.');
      } else {
        setServerError('An unexpected error occurred. Please try again.');
      }
    }
  }

  if (tokenError) {
    return (
      <div role="alert" className="rounded-md bg-destructive/10 p-4 text-sm text-destructive">
        <p className="mb-2 font-medium">This reset link is invalid or has expired.</p>
        <Link href="/forgot-password" className="underline hover:no-underline">
          Request a new reset link
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate aria-label="Reset password form">
      {serverError && (
        <div role="alert" aria-live="polite" className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {serverError}
        </div>
      )}

      {/* New password */}
      <div className="mb-4">
        <label htmlFor="reset-new-password" className="mb-1 block text-sm font-medium">
          New password
        </label>
        <div className="relative">
          <Input
            id="reset-new-password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="new-password"
            aria-describedby={errors.new_password ? 'reset-new-password-error' : undefined}
            aria-invalid={Boolean(errors.new_password)}
            disabled={isSubmitting}
            {...register('new_password')}
          />
          <button
            type="button"
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            onClick={() => setShowPassword((v) => !v)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground hover:text-foreground"
          >
            {showPassword ? 'Hide' : 'Show'}
          </button>
        </div>
        {errors.new_password && (
          <p id="reset-new-password-error" role="alert" className="mt-1 text-xs text-destructive">
            {errors.new_password.message}
          </p>
        )}
      </div>

      {/* Confirm password */}
      <div className="mb-6">
        <label htmlFor="reset-confirm-password" className="mb-1 block text-sm font-medium">
          Confirm new password
        </label>
        <Input
          id="reset-confirm-password"
          type={showPassword ? 'text' : 'password'}
          autoComplete="new-password"
          aria-describedby={errors.confirm_password ? 'reset-confirm-password-error' : undefined}
          aria-invalid={Boolean(errors.confirm_password)}
          disabled={isSubmitting}
          {...register('confirm_password')}
        />
        {errors.confirm_password && (
          <p id="reset-confirm-password-error" role="alert" className="mt-1 text-xs text-destructive">
            {errors.confirm_password.message}
          </p>
        )}
      </div>

      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? 'Resetting…' : 'Reset password'}
      </Button>
    </form>
  );
}
