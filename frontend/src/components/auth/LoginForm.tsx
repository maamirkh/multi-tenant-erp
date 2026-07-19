'use client';

/**
 * LoginForm — authentication form component.
 *
 * Uses React Hook Form + Zod for client-side validation.
 * Calls useAuth().login() on submit; handles 401, 423, and 429 error codes.
 * Form is disabled during submission to prevent duplicate requests.
 * Accessible: all fields have associated <label> elements and aria-describedby
 * on error messages.
 */

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useAuth } from '@/hooks/useAuth';
import { ApiClientError } from '@/lib/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const loginSchema = z.object({
  email: z.string().email('Please enter a valid email address.'),
  password: z.string().min(1, 'Password is required.'),
  remember_me: z.boolean(),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export function LoginForm(): React.JSX.Element {
  const { login } = useAuth();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '', remember_me: false },
  });

  async function onSubmit(values: LoginFormValues): Promise<void> {
    setServerError(null);
    try {
      await login(values.email, values.password, values.remember_me);
    } catch (err) {
      if (err instanceof ApiClientError) {
        const code = err.error.error.code;
        if (err.status === 401) {
          setServerError('Invalid email or password.');
        } else if (err.status === 423) {
          const details = err.error.error.details as Record<string, string | null>;
          const lockedUntil = details['unlocks_at'] ?? null;
          setServerError(
            lockedUntil
              ? `Account locked until ${new Date(lockedUntil).toLocaleString()}.`
              : 'Account is temporarily locked. Please try again later.'
          );
        } else if (err.status === 429 || code === 'RATE_LIMIT_EXCEEDED') {
          setServerError('Too many attempts. Please wait before trying again.');
        } else {
          setServerError('An unexpected error occurred. Please try again.');
        }
      } else {
        setServerError('An unexpected error occurred. Please try again.');
      }
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate aria-label="Sign in form">
      {/* Server-level error */}
      {serverError && (
        <div role="alert" aria-live="polite" className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {serverError}
        </div>
      )}

      {/* Email */}
      <div className="mb-4">
        <label htmlFor="login-email" className="mb-1 block text-sm font-medium">
          Email address
        </label>
        <Input
          id="login-email"
          type="email"
          autoComplete="email"
          aria-describedby={errors.email ? 'login-email-error' : undefined}
          aria-invalid={Boolean(errors.email)}
          disabled={isSubmitting}
          {...register('email')}
        />
        {errors.email && (
          <p id="login-email-error" role="alert" className="mt-1 text-xs text-destructive">
            {errors.email.message}
          </p>
        )}
      </div>

      {/* Password */}
      <div className="mb-4">
        <label htmlFor="login-password" className="mb-1 block text-sm font-medium">
          Password
        </label>
        <Input
          id="login-password"
          type="password"
          autoComplete="current-password"
          aria-describedby={errors.password ? 'login-password-error' : undefined}
          aria-invalid={Boolean(errors.password)}
          disabled={isSubmitting}
          {...register('password')}
        />
        {errors.password && (
          <p id="login-password-error" role="alert" className="mt-1 text-xs text-destructive">
            {errors.password.message}
          </p>
        )}
      </div>

      {/* Remember me */}
      <div className="mb-6 flex items-center gap-2">
        <input
          id="login-remember-me"
          type="checkbox"
          className="h-4 w-4 rounded border-border"
          disabled={isSubmitting}
          {...register('remember_me')}
        />
        <label htmlFor="login-remember-me" className="text-sm">
          Remember me
        </label>
      </div>

      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? 'Signing in…' : 'Sign in'}
      </Button>
    </form>
  );
}
