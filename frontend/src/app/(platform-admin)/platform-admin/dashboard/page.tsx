'use client';

/**
 * T191 — Platform Dashboard page.
 *
 * Requires `platform.dashboard.view` (enforced server-side; a 403 on the
 * whole call renders `PermissionDeniedState`). Each widget renders its
 * own `populated`/`empty`/`unavailable` state independently — a failed
 * widget never displays `0` (FR-9A-003) — and a widget the caller lacks
 * the underlying permission for is simply absent from the response
 * (server-side omission, not a client-side filter).
 */

import { useQuery } from '@tanstack/react-query';
import { getDashboard, type DashboardWidget } from '@/lib/api/platform-admin';
import {
  LoadingState,
  ErrorState,
  EmptyState,
  UnavailableState,
  PermissionDeniedState,
  messageFromError,
  isForbidden,
} from '@/components/platform-admin/DataState';

const WIDGET_TITLES: Record<string, string> = {
  tenant_counts_by_status: 'Tenants by Status',
  recent_registrations: 'Recent Registrations',
  plan_subscription_distribution: 'Plan Subscription Distribution',
  quota_warnings: 'Quota Warnings',
  recent_platform_actions: 'Recent Platform Actions',
  health_summary: 'Platform Health',
  ai_usage: 'AI Usage',
};

function WidgetCard({ name, widget }: { name: string; widget: DashboardWidget }): React.JSX.Element {
  return (
    <div className="rounded-lg border border-border p-4">
      <h2 className="mb-3 text-sm font-semibold text-foreground">
        {WIDGET_TITLES[name] ?? name}
      </h2>
      {widget.state === 'unavailable' && <UnavailableState message="This widget's data is temporarily unavailable." />}
      {widget.state === 'empty' && <EmptyState message="No data yet." />}
      {widget.state === 'populated' && (
        <pre className="max-h-64 overflow-auto rounded bg-muted p-3 text-xs text-muted-foreground">
          {JSON.stringify(widget.data, null, 2)}
        </pre>
      )}
    </div>
  );
}

export default function PlatformDashboardPage(): React.JSX.Element {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['platform', 'dashboard'],
    queryFn: getDashboard,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Dashboard</h1>
        <p className="text-sm text-muted-foreground">Platform-wide operational overview.</p>
      </div>

      {isLoading && <LoadingState />}

      {isError && isForbidden(error) && <PermissionDeniedState />}
      {isError && !isForbidden(error) && (
        <ErrorState message={messageFromError(error)} onRetry={() => void refetch()} />
      )}

      {data && Object.keys(data.widgets).length === 0 && (
        <EmptyState message="No widgets are available for your permission set." />
      )}

      {data && Object.keys(data.widgets).length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Object.entries(data.widgets).map(([name, widget]) => (
            <WidgetCard key={name} name={name} widget={widget} />
          ))}
        </div>
      )}
    </div>
  );
}
