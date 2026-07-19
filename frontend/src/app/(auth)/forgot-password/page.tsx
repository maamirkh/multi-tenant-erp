'use client';

/**
 * T096 — Forgot Password page.
 *
 * Renders ForgotPasswordForm inside the auth card.
 * Spec ref: spec.md §7 FR-021, US-04.
 */

import Link from 'next/link';
import { ForgotPasswordForm } from '@/components/auth/ForgotPasswordForm';

export default function ForgotPasswordPage(): React.JSX.Element {
  return (
    <div className="w-full max-w-md px-4">
      <title>Reset Password — DevSphere ERP</title>
      <div className="rounded-lg border border-gray-200 bg-white p-8 shadow-sm">
        <h1 className="mb-6 text-2xl font-semibold tracking-tight text-gray-900">
          Reset Password
        </h1>
        <ForgotPasswordForm />
        <p className="mt-4 text-center text-sm text-gray-600">
          <Link href="/login" className="text-blue-600 hover:underline">
            Back to Sign In
          </Link>
        </p>
      </div>
    </div>
  );
}
