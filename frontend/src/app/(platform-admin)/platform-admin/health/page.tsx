'use client';

/**
 * T203 — Platform Health page. Requires `platform.monitoring.read`.
 * Names each specific failing check by key rather than a generic
 * "unhealthy" banner, and labels the outbox relay honestly as a stub —
 * no message-bus is integrated in this Epic (`services/health_service.py`).
 */

import { useQuery } from '@tanstack/react-query';
import { getPlatformHealth } from '@/lib/api/platform-admin';
import {
  LoadingState,
  ErrorState,
  PermissionDeniedState,
  messageFromError,
  isForbidden,
} from '@/components/platform-admin/DataState';

export default function PlatformHealthPage(): React.JSX.Element {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['platform', 'health'],
    queryFn: getPlatformHealth,
    refetchInterval: 30_000,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Platform Health</h1>
        <p className="text-sm text-muted-foreground">Operational status of the Platform&apos;s own dependencies.</p>
      </div>

      {isLoading && <LoadingState />}
      {isError && isForbidden(error) && <PermissionDeniedState />}
      {isError && !isForbidden(error) && (
        <ErrorState message={messageFromError(error)} onRetry={() => void refetch()} />
      )}

      {data && (
        <>
          <div
            className={`rounded-lg border p-4 text-sm font-semibold ${
              data.status === 'healthy'
                ? 'border-green-300/40 bg-green-500/10 text-green-700'
                : 'border-destructive/30 bg-destructive/10 text-destructive'
            }`}
          >
            Overall status: {data.status}
          </div>

          <section className="rounded-lg border border-border p-4">
            <h2 className="mb-3 text-sm font-semibold text-foreground">Checks</h2>
            <ul className="space-y-1 text-sm">
              {Object.entries(data.checks).map(([name, result]) => (
                <li key={name} className="flex justify-between">
                  <span>{name}</span>
                  <span className={result === 'ok' ? 'text-green-600' : 'text-destructive'}>
                    {result}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-border p-4">
              <h2 className="mb-2 text-sm font-semibold text-foreground">Event Outbox</h2>
              <p className="text-sm">Pending: {data.outbox_pending}</p>
              <p className="text-sm">Published: {data.outbox_published}</p>
            </div>
            <div className="rounded-lg border border-amber-300/40 bg-amber-500/10 p-4">
              <h2 className="mb-2 text-sm font-semibold text-amber-700 dark:text-amber-400">
                Relay (stub — logging only)
              </h2>
              <p className="mb-2 text-xs text-amber-700 dark:text-amber-400">
                No message-bus is integrated in this Epic; this reflects a logging-only stub, not a real relay.
              </p>
              <pre className="max-h-32 overflow-auto rounded bg-muted p-2 text-xs text-muted-foreground">
                {JSON.stringify(data.relay, null, 2)}
              </pre>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
