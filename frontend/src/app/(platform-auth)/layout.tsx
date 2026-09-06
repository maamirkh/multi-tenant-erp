'use client';

/**
 * T190 — Public `(platform-auth)` route group layout.
 *
 * Minimal centered layout for the Platform login page — no guard, no
 * sidebar. Mirrors `app/(auth)/layout.tsx`'s existing shape exactly
 * (added only because that sibling tenant group already has one).
 * Wraps children in `PlatformAuthProvider` so `usePlatformAuthContext()`
 * is available on the login page — deliberately not
 * `PlatformSelectedTenantProvider`, which has no purpose before a
 * Platform session exists.
 */

import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PlatformAuthProvider } from '@/contexts/PlatformAuthContext';

export default function PlatformAuthLayout({
  children,
}: {
  children: React.ReactNode;
}): React.JSX.Element {
  const [queryClient] = useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: false } } })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <PlatformAuthProvider>
        <div className="flex min-h-screen items-center justify-center bg-gray-50">
          {children}
        </div>
      </PlatformAuthProvider>
    </QueryClientProvider>
  );
}
