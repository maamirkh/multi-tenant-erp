'use client';

/**
 * T097 — Reset Password page.
 *
 * The token is read from `?token=` search params inside ResetPasswordForm
 * (which handles missing-token redirect to /forgot-password internally).
 * Wrapped in <Suspense> because ResetPasswordForm uses useSearchParams(),
 * which requires a Suspense boundary in Next.js App Router.
 * Spec ref: spec.md §7 FR-023, US-05.
 */

import { Suspense } from 'react';
import { ResetPasswordForm } from '@/components/auth/ResetPasswordForm';

export default function ResetPasswordPage(): React.JSX.Element {
  return (
    <div className="w-full max-w-md px-4">
      <title>Set New Password — DevSphere ERP</title>
      <div className="rounded-lg border border-gray-200 bg-white p-8 shadow-sm">
        <h1 className="mb-6 text-2xl font-semibold tracking-tight text-gray-900">
          Set New Password
        </h1>
        <Suspense
          fallback={
            <div className="py-4 text-center text-sm text-gray-500">Loading…</div>
          }
        >
          <ResetPasswordForm />
        </Suspense>
      </div>
    </div>
  );
}
