'use client';

/**
 * T094 — Auth route group layout.
 *
 * Minimal centered layout for auth pages (no sidebar, no header).
 * Wraps children in QueryClientProvider + AuthProvider so auth hooks are
 * available on login / forgot-password / reset-password pages.
 */

import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '@/contexts/AuthContext';

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}): React.JSX.Element {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { retry: false } },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <div className="flex min-h-screen items-center justify-center bg-gray-50">
          {children}
        </div>
      </AuthProvider>
    </QueryClientProvider>
  );
}
