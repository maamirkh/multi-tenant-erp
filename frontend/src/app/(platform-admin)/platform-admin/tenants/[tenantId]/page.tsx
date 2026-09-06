'use client';

/**
 * T193 — Tenant Detail page ("Tenant 360").
 *
 * Uses `PlatformSelectedTenantContext` (T186) — never
 * `erp_active_company_id` (BR-9A-034/035/036) — to make this tenant's
 * identity available to sibling pages (Entitlements/Quotas/Usage/
 * Subscriptions, T196/T197/T201/T195), which have no tenant-independent
 * list endpoint of their own. Shows administrative/aggregate context
 * only — never tenant business records (FR-9A-021). Suspend/reactivate
 * require a typed reason and an explicit confirmation (via the shared
 * `ReasonDialog`).
 */

import { use, useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getTenantDetail,
  suspendTenant,
  reactivateTenant,
} from '@/lib/api/platform-admin';
import { usePlatformSelectedTenantContext } from '@/contexts/PlatformSelectedTenantContext';
import { ReasonDialog } from '@/components/platform-admin/dialogs';
import {
  LoadingState,
  UnavailableState,
  PermissionDeniedState,
  EmptyState,
  messageFromError,
  isForbidden,
} from '@/components/platform-admin/DataState';

export default function TenantDetailPage({
  params,
}: {
  params: Promise<{ tenantId: string }>;
}): React.JSX.Element {
  const { tenantId } = use(params);
  const { selectTenant } = usePlatformSelectedTenantContext();
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState<'suspend' | 'reactivate' | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: tenant, isLoading, isError, error } = useQuery({
    queryKey: ['platform', 'tenant', tenantId],
    queryFn: () => getTenantDetail(tenantId),
  });

  useEffect(() => {
    if (tenant) {
      selectTenant({ id: tenant.id, legalName: tenant.legal_name });
    }
    // Only re-run when the fetched tenant identity changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenant?.id, tenant?.legal_name]);

  const suspendMutation = useMutation({
    mutationFn: (reason: string) => suspendTenant(tenantId, reason),
    onSuccess: () => {
      setDialog(null);
      void queryClient.invalidateQueries({ queryKey: ['platform', 'tenant', tenantId] });
    },
    onError: (err) => setActionError(messageFromError(err)),
  });

  const reactivateMutation = useMutation({
    mutationFn: (reason: string) => reactivateTenant(tenantId, reason),
    onSuccess: () => {
      setDialog(null);
      void queryClient.invalidateQueries({ queryKey: ['platform', 'tenant', tenantId] });
    },
    onError: (err) => setActionError(messageFromError(err)),
  });

  if (isLoading) return <LoadingState />;
  if (isError && isForbidden(error)) return <PermissionDeniedState />;
  if (isError || !tenant) {
    return <UnavailableState message={messageFromError(error) || 'Tenant detail unavailable.'} />;
  }

  const canSuspend = tenant.status === 'active' || tenant.status === 'inactive';
  const canReactivate = tenant.status === 'suspended';

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">{tenant.legal_name}</h1>
          <p className="text-sm text-muted-foreground">
            {tenant.slug} · {tenant.email} · {tenant.country ?? 'Unknown country'}
          </p>
        </div>
        <div className="flex gap-2">
          {canSuspend && (
            <button
              type="button"
              onClick={() => setDialog('suspend')}
              className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-1.5 text-sm text-destructive hover:bg-destructive/20"
            >
              Suspend
            </button>
          )}
          {canReactivate && (
            <button
              type="button"
              onClick={() => setDialog('reactivate')}
              className="rounded-lg border border-input bg-background px-3 py-1.5 text-sm hover:bg-muted"
            >
              Reactivate
            </button>
          )}
        </div>
      </div>

      {actionError && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {actionError}
        </div>
      )}

      <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-lg border border-border p-4">
          <h2 className="mb-2 text-sm font-semibold text-foreground">Status</h2>
          <p className="text-sm">{tenant.status}</p>
          {tenant.pre_suspension_status && (
            <p className="text-xs text-muted-foreground">
              Pre-suspension: {tenant.pre_suspension_status}
            </p>
          )}
        </div>
        <div className="rounded-lg border border-border p-4">
          <h2 className="mb-2 text-sm font-semibold text-foreground">Plan</h2>
          {tenant.plan ? (
            <p className="text-sm">{tenant.plan.name} ({tenant.plan.status})</p>
          ) : (
            <EmptyState message="No plan assigned." />
          )}
        </div>
        <div className="rounded-lg border border-border p-4">
          <h2 className="mb-2 text-sm font-semibold text-foreground">Users</h2>
          <p className="text-sm">{tenant.user_count}</p>
        </div>
      </section>

      <section className="rounded-lg border border-border p-4">
        <h2 className="mb-3 text-sm font-semibold text-foreground">Entitlements</h2>
        {tenant.entitlements.length === 0 ? (
          <EmptyState message="No capabilities resolved." />
        ) : (
          <ul className="space-y-1 text-sm">
            {tenant.entitlements.map((e) => (
              <li key={e.capability_key} className="flex justify-between">
                <span>{e.capability_key}</span>
                <span className={e.available ? 'text-green-600' : 'text-muted-foreground'}>
                  {e.available ? 'Available' : e.reason}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-lg border border-border p-4">
        <h2 className="mb-3 text-sm font-semibold text-foreground">Quotas</h2>
        {tenant.quotas.length === 0 ? (
          <EmptyState message="No quota categories resolved." />
        ) : (
          <ul className="space-y-1 text-sm">
            {tenant.quotas.map((q) => (
              <li key={q.quota_key} className="flex justify-between">
                <span>{q.quota_key}</span>
                <span className="text-muted-foreground">
                  {q.state === 'unavailable'
                    ? 'unavailable'
                    : q.state === 'unlimited'
                      ? 'unlimited'
                      : `${q.current_usage ?? 0} / ${q.limit ?? '—'} (${q.state})`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-lg border border-border p-4">
        <h2 className="mb-3 text-sm font-semibold text-foreground">Lifecycle History</h2>
        {tenant.lifecycle_history.length === 0 ? (
          <EmptyState message="No lifecycle transitions recorded." />
        ) : (
          <ul className="space-y-2 text-sm">
            {tenant.lifecycle_history.map((event, i) => (
              <li key={i} className="border-t border-border pt-2 first:border-t-0 first:pt-0">
                <p className="font-medium">{event.action}</p>
                <p className="text-xs text-muted-foreground">
                  {new Date(event.created_at).toLocaleString()}
                  {event.reason ? ` — ${event.reason}` : ''}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-lg border border-border p-4">
        <h2 className="mb-3 text-sm font-semibold text-foreground">Recent Platform Actions</h2>
        {tenant.recent_audit_events.length === 0 ? (
          <EmptyState message="No recent platform actions for this tenant." />
        ) : (
          <ul className="space-y-2 text-sm">
            {tenant.recent_audit_events.map((event) => (
              <li key={event.id} className="border-t border-border pt-2 first:border-t-0 first:pt-0">
                <p className="font-medium">{event.action}</p>
                <p className="text-xs text-muted-foreground">
                  {new Date(event.created_at).toLocaleString()}
                  {event.reason ? ` — ${event.reason}` : ''}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <ReasonDialog
        open={dialog === 'suspend'}
        title="Suspend Tenant"
        description={`Suspend ${tenant.legal_name}? Active sessions will be revoked immediately. Provide a reason.`}
        submitLabel="Suspend"
        variant="destructive"
        onClose={() => setDialog(null)}
        onConfirm={(reason) => {
          setActionError(null);
          suspendMutation.mutate(reason);
        }}
        isPending={suspendMutation.isPending}
      />

      <ReasonDialog
        open={dialog === 'reactivate'}
        title="Reactivate Tenant"
        description={`Reactivate ${tenant.legal_name}? This restores its pre-suspension status; existing revoked sessions are not restored. Provide a reason.`}
        submitLabel="Reactivate"
        onClose={() => setDialog(null)}
        onConfirm={(reason) => {
          setActionError(null);
          reactivateMutation.mutate(reason);
        }}
        isPending={reactivateMutation.isPending}
      />
    </div>
  );
}
