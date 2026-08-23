'use client';

/**
 * T195 — Subscriptions page. Shows/changes the subscription for the
 * `PlatformSelectedTenantContext` tenant (T186) — the contract has no
 * tenant-independent subscription list. A downgrade that would place
 * current usage above the target plan's limits returns 409
 * (FR-9A-165); this page surfaces that conflict explicitly and requires
 * the operator to tick "acknowledge" before resubmitting with
 * `acknowledged: true` — never silently retried.
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getTenantSubscription,
  assignSubscription,
  listPlans,
} from '@/lib/api/platform-admin';
import { usePlatformSelectedTenantContext } from '@/contexts/PlatformSelectedTenantContext';
import { NoTenantSelected } from '@/components/platform-admin/NoTenantSelected';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  LoadingState,
  ErrorState,
  EmptyState,
  PermissionDeniedState,
  messageFromError,
  isForbidden,
  isConflict,
} from '@/components/platform-admin/DataState';

export default function PlatformSubscriptionsPage(): React.JSX.Element {
  const { selectedTenant } = usePlatformSelectedTenantContext();
  const queryClient = useQueryClient();
  const [planId, setPlanId] = useState('');
  const [effectiveDate, setEffectiveDate] = useState('');
  const [reason, setReason] = useState('');
  const [conflict, setConflict] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const { data: plansData } = useQuery({
    queryKey: ['platform', 'plans', 'available'],
    queryFn: () => listPlans({ status: 'published', page: 1, page_size: 100 }),
    enabled: !!selectedTenant,
  });

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['platform', 'subscription', selectedTenant?.id],
    queryFn: () => getTenantSubscription(selectedTenant!.id),
    enabled: !!selectedTenant,
  });

  const assignMutation = useMutation({
    mutationFn: () =>
      assignSubscription(selectedTenant!.id, {
        plan_id: planId,
        effective_date: effectiveDate,
        reason: reason || null,
        acknowledged,
      }),
    onSuccess: () => {
      setPlanId('');
      setReason('');
      setConflict(false);
      setAcknowledged(false);
      void queryClient.invalidateQueries({ queryKey: ['platform', 'subscription', selectedTenant?.id] });
    },
    onError: (err) => {
      if (isConflict(err)) {
        setConflict(true);
      } else {
        setFormError(messageFromError(err));
      }
    },
  });

  if (!selectedTenant) {
    return (
      <div className="space-y-6">
        <h1 className="text-xl font-semibold text-foreground">Subscriptions</h1>
        <NoTenantSelected />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Subscriptions</h1>
        <p className="text-sm text-muted-foreground">{selectedTenant.legalName}</p>
      </div>

      {isLoading && <LoadingState />}
      {isError && isForbidden(error) && <PermissionDeniedState />}
      {isError && !isForbidden(error) && (
        <ErrorState message={messageFromError(error)} onRetry={() => void refetch()} />
      )}

      {data && (
        <section className="rounded-lg border border-border p-4">
          <h2 className="mb-2 text-sm font-semibold text-foreground">Current Subscription</h2>
          {data.current ? (
            <p className="text-sm">
              Plan {data.current.plan_id} — {data.current.status} since{' '}
              {new Date(data.current.effective_date).toLocaleDateString()}
            </p>
          ) : (
            <EmptyState message="No active subscription." />
          )}
        </section>
      )}

      {data && data.history.length > 0 && (
        <section className="rounded-lg border border-border p-4">
          <h2 className="mb-2 text-sm font-semibold text-foreground">History</h2>
          <ul className="space-y-2 text-sm">
            {data.history.map((s) => (
              <li key={s.id} className="border-t border-border pt-2 first:border-t-0 first:pt-0">
                Plan {s.plan_id} — {s.status} — effective {new Date(s.effective_date).toLocaleDateString()}
                {s.reason ? ` — ${s.reason}` : ''}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="rounded-lg border border-border p-4">
        <h2 className="mb-3 text-sm font-semibold text-foreground">Assign / Change Plan</h2>

        {formError && (
          <div role="alert" className="mb-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {formError}
          </div>
        )}

        {conflict && (
          <div role="alert" className="mb-3 rounded-lg border border-amber-300/40 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-400">
            <p className="mb-2">
              Current usage exceeds this plan&apos;s limits. Acknowledge to proceed anyway.
            </p>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={acknowledged}
                onChange={(e) => setAcknowledged(e.target.checked)}
              />
              I acknowledge the usage conflict and want to proceed.
            </label>
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            setFormError(null);
            assignMutation.mutate();
          }}
          noValidate
          className="space-y-3"
        >
          <div>
            <label htmlFor="subscription_plan" className="mb-1 block text-sm font-medium">Plan</label>
            <select
              id="subscription_plan"
              required
              value={planId}
              onChange={(e) => setPlanId(e.target.value)}
              className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none"
            >
              <option value="">Select a plan…</option>
              {(plansData?.items ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.code})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="subscription_effective_date" className="mb-1 block text-sm font-medium">
              Effective Date
            </label>
            <Input
              id="subscription_effective_date"
              type="date"
              required
              value={effectiveDate}
              onChange={(e) => setEffectiveDate(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="subscription_reason" className="mb-1 block text-sm font-medium">Reason</label>
            <Input id="subscription_reason" value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
          <Button type="submit" disabled={assignMutation.isPending || (conflict && !acknowledged)}>
            {assignMutation.isPending ? 'Assigning…' : 'Assign'}
          </Button>
        </form>
      </section>
    </div>
  );
}
