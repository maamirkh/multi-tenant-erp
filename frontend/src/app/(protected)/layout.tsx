'use client';

/**
 * T098 — Protected route group layout with route guard.
 *
 * Wraps children in QueryClientProvider + AuthProvider, then applies the
 * route guard logic:
 *   - isLoading → full-screen spinner (hydration in progress)
 *   - !isAuthenticated → redirect to /login (guard fires after hydration)
 *   - isAuthenticated → render AppLayout wrapping {children}
 *
 * ProtectedContent is a separate inner component so it can call
 * useAuthContext() after AuthProvider has mounted.
 * Spec ref: plan.md §5 (Frontend Modules — Route Guard), plan.md §9.
 */

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuthContext } from '@/contexts/AuthContext';
import AppLayout from '@/components/layout/AppLayout';

function ProtectedContent({
  children,
}: {
  children: React.ReactNode;
}): React.JSX.Element {
  const { isAuthenticated, isLoading } = useAuthContext();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div
          className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent"
          role="status"
          aria-label="Loading"
        />
      </div>
    );
  }

  if (!isAuthenticated) {
    // Redirect is in progress; render nothing to avoid flash.
    return <></>;
  }

  return <AppLayout>{children}</AppLayout>;
}

export default function ProtectedLayout({
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
        <ProtectedContent>{children}</ProtectedContent>
      </AuthProvider>
    </QueryClientProvider>
  );
}
