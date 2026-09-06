'use client';

/**
 * T188 — Protected `(platform-admin)` route group layout and guard.
 *
 * Its own shell — never `AppLayout`/tenant `Sidebar` (whose "SuperAdmin"
 * check is an acknowledged placeholder, `components/layout/Sidebar.tsx`).
 * Wraps only the authenticated `/platform-admin/*` pages; the public
 * login page lives in the sibling `(platform-auth)` route group (T190)
 * so it can never be wrapped by this redirecting layout — mirrors the
 * repository's existing `(auth)` vs `(protected)` split exactly
 * (`app/(auth)/layout.tsx` vs `app/(protected)/layout.tsx`).
 *
 * Client-side guard only (no Next.js middleware — the repo has none,
 * plan.md §14 Public Login Route Structure).
 */

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  PlatformAuthProvider,
  usePlatformAuthContext,
} from '@/contexts/PlatformAuthContext';
import { PlatformSelectedTenantProvider } from '@/contexts/PlatformSelectedTenantContext';
import { PlatformSidebar } from '@/components/platform-admin/PlatformSidebar';
import { Button } from '@/components/ui/button';

function PlatformShellContent({
  children,
}: {
  children: React.ReactNode;
}): React.JSX.Element {
  const { isAuthenticated, isLoading, logout } = usePlatformAuthContext();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace('/platform-admin/login');
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
    // Redirect is in progress; render nothing to avoid a flash of the
    // protected shell.
    return <></>;
  }

  async function handleLogout(): Promise<void> {
    await logout();
    router.replace('/platform-admin/login');
  }

  return (
    <div className="flex h-full min-h-screen flex-col">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-background px-6">
        <span className="text-sm font-semibold tracking-tight text-foreground">
          DevSphere Platform Administration
        </span>
        <Button variant="outline" size="sm" onClick={() => void handleLogout()}>
          Log out
        </Button>
      </header>
      <div className="flex flex-1">
        <PlatformSidebar />
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
}

export default function PlatformAdminLayout({
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
        <PlatformSelectedTenantProvider>
          <PlatformShellContent>{children}</PlatformShellContent>
        </PlatformSelectedTenantProvider>
      </PlatformAuthProvider>
    </QueryClientProvider>
  );
}
