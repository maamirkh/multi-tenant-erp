'use client';

/**
 * T190 — Platform login page, public `(platform-auth)` group.
 *
 * Structurally outside the protected shell: this route lives in a
 * sibling route group from `(platform-admin)/platform-admin/layout.tsx`
 * (T188), so that redirecting layout provably cannot wrap it — no
 * `login → guard → login` loop (plan.md §14). Consumes
 * `PlatformAuthContext` (T183) directly, never the guarded layout.
 *
 * Generic error text on failure — never reveals whether an email exists
 * as a tenant user (the backend itself returns the same 401 for invalid
 * credentials and for "no active PlatformAdministrator", deliberately,
 * per `PlatformAuthContext`'s own docstring).
 */

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { usePlatformAuthContext } from '@/contexts/PlatformAuthContext';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

export default function PlatformLoginPage(): React.JSX.Element {
  const { isAuthenticated, isLoading, login } = usePlatformAuthContext();
  const router = useRouter();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace('/platform-admin/dashboard');
    }
  }, [isAuthenticated, isLoading, router]);

  async function handleSubmit(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
      router.replace('/platform-admin/dashboard');
    } catch {
      // Deliberately generic — never reveals whether this email exists
      // as a tenant user or a Platform Administrator (see docstring).
      setError('Invalid email or password.');
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading || isAuthenticated) {
    return (
      <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
        <div
          className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent"
          role="status"
          aria-label="Loading"
        />
        Loading…
      </div>
    );
  }

  return (
    <div className="w-full max-w-md px-4">
      <title>Platform Administration Sign In — DevSphere ERP</title>
      <div className="rounded-lg border border-gray-200 bg-white p-8 shadow-sm">
        <h1 className="mb-1 text-2xl font-semibold tracking-tight text-gray-900">
          Platform Administration
        </h1>
        <p className="mb-6 text-sm text-muted-foreground">
          Sign in with your Platform Administrator credentials.
        </p>

        {error && (
          <div
            role="alert"
            className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
          >
            {error}
          </div>
        )}

        <form onSubmit={(e) => void handleSubmit(e)} noValidate className="space-y-4">
          <div>
            <label htmlFor="platform_login_email" className="mb-1 block text-sm font-medium text-gray-900">
              Email
            </label>
            <Input
              id="platform_login_email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="platform_login_password" className="mb-1 block text-sm font-medium text-gray-900">
              Password
            </label>
            <Input
              id="platform_login_password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>
      </div>
    </div>
  );
}
