'use client';

/**
 * T201 — Usage page, for the `PlatformSelectedTenantContext` tenant
 * (T186; same tenant-scoped-only reasoning as T195/T196/T197). Usage
 * per metric/period; the AI section shows an explicit "not yet active"
 * state until the ledger has real data (BR-9A-026/027, never fabricated
 * as a populated zero-balance section). Manual credit adjustment
 * requires a reason.
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getTenantUsage,
  getTenantAiCredits,
  adjustAiCredits,
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
} from '@/components/platform-admin/DataState';

export default function PlatformUsagePage(): React.JSX.Element {
  const { selectedTenant } = usePlatformSelectedTenantContext();
  const queryClient = useQueryClient();
  const [delta, setDelta] = useState('');
  const [reason, setReason] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);

  const usageQuery = useQuery({
    queryKey: ['platform', 'usage', selectedTenant?.id],
    queryFn: () => getTenantUsage(selectedTenant!.id),
    enabled: !!selectedTenant,
  });

  const aiCreditsQuery = useQuery({
    queryKey: ['platform', 'ai-credits', selectedTenant?.id],
    queryFn: () => getTenantAiCredits(selectedTenant!.id),
    enabled: !!selectedTenant,
  });

  const adjustMutation = useMutation({
    mutationFn: () => adjustAiCredits(selectedTenant!.id, { delta, reason: reason.trim() }),
    onSuccess: () => {
      setDelta('');
      setReason('');
      setTouched(false);
      void queryClient.invalidateQueries({ queryKey: ['platform', 'ai-credits', selectedTenant?.id] });
    },
    onError: (err) => setFormError(messageFromError(err)),
  });

  if (!selectedTenant) {
    return (
      <div className="space-y-6">
        <h1 className="text-xl font-semibold text-foreground">Usage</h1>
        <NoTenantSelected />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Usage</h1>
        <p className="text-sm text-muted-foreground">{selectedTenant.legalName}</p>
      </div>

      <section className="rounded-lg border border-border p-4">
        <h2 className="mb-3 text-sm font-semibold text-foreground">Usage Records</h2>
        {usageQuery.isLoading && <LoadingState />}
        {usageQuery.isError && isForbidden(usageQuery.error) && <PermissionDeniedState />}
        {usageQuery.isError && !isForbidden(usageQuery.error) && (
          <ErrorState message={messageFromError(usageQuery.error)} onRetry={() => void usageQuery.refetch()} />
        )}
        {usageQuery.data && usageQuery.data.records.length === 0 && (
          <EmptyState message="No usage recorded for this tenant yet." />
        )}
        {usageQuery.data && usageQuery.data.records.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="p-3">Metric</th>
                  <th className="p-3">Quantity</th>
                  <th className="p-3">Period</th>
                  <th className="p-3">Source</th>
                </tr>
              </thead>
              <tbody>
                {usageQuery.data.records.map((r) => (
                  <tr key={r.id} className="border-t border-border">
                    <td className="p-3">{r.metric_key}</td>
                    <td className="p-3">{r.quantity}</td>
                    <td className="p-3 text-muted-foreground">
                      {new Date(r.period_start).toLocaleDateString()} – {new Date(r.period_end).toLocaleDateString()}
                    </td>
                    <td className="p-3 text-muted-foreground">{r.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="rounded-lg border border-border p-4">
        <h2 className="mb-3 text-sm font-semibold text-foreground">AI Usage & Credits</h2>
        {aiCreditsQuery.isLoading && <LoadingState />}
        {aiCreditsQuery.isError && isForbidden(aiCreditsQuery.error) && <PermissionDeniedState />}
        {aiCreditsQuery.isError && !isForbidden(aiCreditsQuery.error) && (
          <ErrorState
            message={messageFromError(aiCreditsQuery.error)}
            onRetry={() => void aiCreditsQuery.refetch()}
          />
        )}
        {aiCreditsQuery.data && aiCreditsQuery.data.status === 'not_yet_active' && (
          <EmptyState message="No AI capability is active for this tenant yet." />
        )}
        {aiCreditsQuery.data && aiCreditsQuery.data.status === 'active' && (
          <>
            <p className="mb-3 text-sm">Balance: {aiCreditsQuery.data.balance}</p>
            <ul className="mb-4 space-y-2 text-sm">
              {aiCreditsQuery.data.entries.map((entry) => (
                <li key={entry.id} className="border-t border-border pt-2 first:border-t-0 first:pt-0">
                  {entry.delta} — {entry.reason ?? 'No reason recorded'} —{' '}
                  {new Date(entry.occurred_at).toLocaleString()}
                </li>
              ))}
            </ul>
          </>
        )}

        <h3 className="mb-2 text-sm font-medium text-foreground">Manual Credit Adjustment</h3>
        {formError && (
          <div role="alert" className="mb-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {formError}
          </div>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setTouched(true);
            setFormError(null);
            if (!delta || !reason.trim()) return;
            adjustMutation.mutate();
          }}
          noValidate
          className="flex flex-wrap items-end gap-3"
        >
          <div>
            <label htmlFor="ai_credit_delta" className="mb-1 block text-sm font-medium">
              Delta (+/-)
            </label>
            <Input id="ai_credit_delta" type="number" value={delta} onChange={(e) => setDelta(e.target.value)} />
          </div>
          <div>
            <label htmlFor="ai_credit_reason" className="mb-1 block text-sm font-medium">Reason</label>
            <Input id="ai_credit_reason" value={reason} onChange={(e) => setReason(e.target.value)} aria-invalid={touched && !reason.trim()} />
            {touched && !reason.trim() && (
              <p className="mt-1 text-xs text-destructive" role="alert">A reason is required.</p>
            )}
          </div>
          <Button type="submit" disabled={adjustMutation.isPending}>
            {adjustMutation.isPending ? 'Adjusting…' : 'Adjust'}
          </Button>
        </form>
      </section>
    </div>
  );
}
