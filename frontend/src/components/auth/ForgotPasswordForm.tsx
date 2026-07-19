'use client';

/**
 * ForgotPasswordForm — request a password reset email.
 *
 * Anti-enumeration: transitions to success state regardless of whether the
 * email is registered, so the UI never reveals if an account exists.
 * Accessible: label associated with input; loading state communicated visually.
 */

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { forgotPasswordApi } from '@/lib/api/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const forgotSchema = z.object({
  email: z.string().email('Please enter a valid email address.'),
});

type ForgotPasswordFormValues = z.infer<typeof forgotSchema>;

export function ForgotPasswordForm(): React.JSX.Element {
  const [succeeded, setSucceeded] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotSchema),
    defaultValues: { email: '' },
  });

  async function onSubmit(values: ForgotPasswordFormValues): Promise<void> {
    try {
      await forgotPasswordApi(values.email);
    } catch {
      // Anti-enumeration: swallow errors and show the same success message.
    } finally {
      setSucceeded(true);
    }
  }

  if (succeeded) {
    return (
      <div role="status" aria-live="polite" className="rounded-md bg-green-50 p-4 text-sm text-green-800 dark:bg-green-900/20 dark:text-green-300">
        If this email is registered, you will receive a reset link shortly.
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate aria-label="Forgot password form">
      <div className="mb-4">
        <label htmlFor="forgot-email" className="mb-1 block text-sm font-medium">
          Email address
        </label>
        <Input
          id="forgot-email"
          type="email"
          autoComplete="email"
          aria-describedby={errors.email ? 'forgot-email-error' : undefined}
          aria-invalid={Boolean(errors.email)}
          disabled={isSubmitting}
          {...register('email')}
        />
        {errors.email && (
          <p id="forgot-email-error" role="alert" className="mt-1 text-xs text-destructive">
            {errors.email.message}
          </p>
        )}
      </div>

      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? 'Sending…' : 'Send reset link'}
      </Button>
    </form>
  );
}
