'use client';

/**
 * T099 — Dashboard page (protected).
 *
 * Calls GET /api/v1/auth/me via TanStack Query and displays the current
 * user's display name and email. Confirms the /me endpoint is reachable
 * from a protected route.
 * Spec ref: spec.md §7 FR-006, US-06.
 */

import { useQuery } from '@tanstack/react-query';
import { getMeApi } from '@/lib/api/auth';

export default function DashboardPage(): React.JSX.Element {
  const {
    data: user,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['me'],
    queryFn: getMeApi,
    retry: false,
  });

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div
          className="h-6 w-6 animate-spin rounded-full border-4 border-blue-600 border-t-transparent"
          role="status"
          aria-label="Loading"
        />
      </div>
    );
  }

  if (isError || !user) {
    return (
      <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
        Failed to load user profile. Please try refreshing the page.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Dashboard
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Welcome back, {user.display_name}.
        </p>
      </div>

      <div className="rounded-lg border border-border bg-card p-4 text-sm text-card-foreground">
        <p className="font-medium">Your Profile</p>
        <dl className="mt-2 space-y-1">
          <div className="flex gap-2">
            <dt className="text-muted-foreground">Name:</dt>
            <dd>{user.display_name}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="text-muted-foreground">Email:</dt>
            <dd>{user.email}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="text-muted-foreground">Status:</dt>
            <dd>{user.account_status}</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
