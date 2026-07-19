'use client';

/**
 * T095 — Login page.
 *
 * Renders LoginForm inside the auth card.
 * If the user is already authenticated, redirects to /dashboard.
 * Spec ref: spec.md §7 FR-001, US-01.
 */

import { useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { LoginForm } from '@/components/auth/LoginForm';
import { useAuthContext } from '@/contexts/AuthContext';

export default function LoginPage(): React.JSX.Element {
  const { isAuthenticated, isLoading } = useAuthContext();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace('/dashboard');
    }
  }, [isAuthenticated, isLoading, router]);

  return (
    <div className="w-full max-w-md px-4">
      <title>Sign In — DevSphere ERP</title>
      <div className="rounded-lg border border-gray-200 bg-white p-8 shadow-sm">
        <h1 className="mb-6 text-2xl font-semibold tracking-tight text-gray-900">
          Sign In
        </h1>
        <LoginForm />
        <p className="mt-4 text-center text-sm text-gray-600">
          <Link href="/forgot-password" className="text-blue-600 hover:underline">
            Forgot your password?
          </Link>
        </p>
      </div>
    </div>
  );
}
