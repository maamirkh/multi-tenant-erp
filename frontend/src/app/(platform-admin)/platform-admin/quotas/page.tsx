'use client';

/**
 * T197 — Quotas page, for the `PlatformSelectedTenantContext` tenant
 * (T186; same tenant-scoped-only reasoning as T195/T196/T201). All five
 * quota states (`ok`/`approaching`/`reached`/`unlimited`/`unavailable`)
 * render distinctly — `unavailable` is never shown as `0`, and
 * `unlimited` is never shown as a number (FR-9A-003).
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getTenantQuotas, grantQuotaOverride, type QuotaStatus } from '@/lib/api/platform-admin';
import { usePlatformSelectedTenantContext } from '@/contexts/PlatformSelectedTenantContext';
import { NoTenantSelected } from '@/components/platform-admin/NoTenantSelected';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  LoadingState,
  ErrorState,
  EmptyState,
  PermissionDeniedState,
  UnavailableState,
  messageFromError,
  isForbidden,
} from '@/components/platform-admin/DataState';

const STATE_LABEL: Record<QuotaStatus['state'], string> = {
  ok: 'OK',
  approaching: 'Approaching limit',
  reached: 'Limit reached',
  unlimited: 'Unlimited',
  unavailable: 'Unavailable',
};

const STATE_CLASS: Record<QuotaStatus['state'], string> = {
  ok: 'text-green-600',
  approaching: 'text-amber-600',
  reached: 'text-destructive',
  unlimited: 'text-primary',
  unavailable: 'text-muted-foreground',
};

function QuotaValue({ quota }: { quota: QuotaStatus }): React.JSX.Element {
  if (quota.state === 'unavailable') return <span className={STATE_CLASS.unavailable}>—</span>;
  if (quota.state === 'unlimited') return <span className={STATE_CLASS.unlimited}>Unlimited</span>;
  return (
    <span className={STATE_CLASS[quota.state]}>
      {quota.current_usage ?? '0'} / {quota.limit ?? '—'}
    </span>
  );
}

function GrantQuotaOverrideDialog({
  open,
  quotaKey,
  onClose,
  onGrant,
  isPending,
}: {
  open: boolean;
  quotaKey: string | null;
  onClose: () => void;
  onGrant: (overrideLimit: string | null, reason: string, expiresAt: string | null) => void;
  isPending: boolean;
}): React.JSX.Element {
  const [overrideLimit, setOverrideLimit] = useState('');
  const [unlimited, setUnlimited] = useState(false);
  const [reason, setReason] = useState('');
  const [expiresAt, setExpiresAt] = useState('');

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Grant Quota Override</DialogTitle>
          <DialogDescription>
            Override {quotaKey}. Leave the limit blank and check unlimited for no cap.
          </DialogDescription>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!reason.trim()) return;
            onGrant(
              unlimited ? null : overrideLimit || null,
              reason.trim(),
              expiresAt ? new Date(expiresAt).toISOString() : null
            );
          }}
          noValidate
          className="space-y-3"
        >
          <div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={unlimited} onChange={(e) => setUnlimited(e.target.checked)} />
              Unlimited
            </label>
          </div>
          {!unlimited && (
            <div>
              <label htmlFor="quota_override_limit" className="mb-1 block text-sm font-medium">
                Override Limit
              </label>
              <Input
                id="quota_override_limit"
                type="number"
                value={overrideLimit}
                onChange={(e) => setOverrideLimit(e.target.value)}
              />
            </div>
          )}
          <div>
            <label htmlFor="quota_override_reason" className="mb-1 block text-sm font-medium">Reason</label>
            <Input id="quota_override_reason" required value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
          <div>
            <label htmlFor="quota_override_expires" className="mb-1 block text-sm font-medium">
              Expiry (optional — blank = permanent)
            </label>
            <Input
              id="quota_override_expires"
              type="datetime-local"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={isPending}>
              Cancel
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? 'Granting…' : 'Grant'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function PlatformQuotasPage(): React.JSX.Element {
  const { selectedTenant } = usePlatformSelectedTenantContext();
  const queryClient = useQueryClient();
  const [overrideTarget, setOverrideTarget] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['platform', 'quotas', selectedTenant?.id],
    queryFn: () => getTenantQuotas(selectedTenant!.id),
    enabled: !!selectedTenant,
  });

  const overrideMutation = useMutation({
    mutationFn: ({
      overrideLimit,
      reason,
      expiresAt,
    }: {
      overrideLimit: string | null;
      reason: string;
      expiresAt: string | null;
    }) =>
      grantQuotaOverride(selectedTenant!.id, {
        quota_key: overrideTarget!,
        override_limit: overrideLimit,
        reason,
        expires_at: expiresAt,
      }),
    onSuccess: () => {
      setOverrideTarget(null);
      void queryClient.invalidateQueries({ queryKey: ['platform', 'quotas', selectedTenant?.id] });
    },
    onError: (err) => setActionError(messageFromError(err)),
  });

  if (!selectedTenant) {
    return (
      <div className="space-y-6">
        <h1 className="text-xl font-semibold text-foreground">Quotas</h1>
        <NoTenantSelected />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Quotas</h1>
        <p className="text-sm text-muted-foreground">{selectedTenant.legalName}</p>
      </div>

      {actionError && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {actionError}
        </div>
      )}

      {isLoading && <LoadingState />}
      {isError && isForbidden(error) && <PermissionDeniedState />}
      {isError && !isForbidden(error) && (
        <ErrorState message={messageFromError(error)} onRetry={() => void refetch()} />
      )}

      {data && data.quotas.length === 0 && <EmptyState message="No quota categories configured." />}

      {data && data.quotas.some((q) => q.state === 'unavailable') && (
        <UnavailableState message="One or more quota categories could not be resolved right now." />
      )}

      {data && data.quotas.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="p-3">Quota</th>
                <th className="p-3">State</th>
                <th className="p-3">Usage</th>
                <th className="p-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.quotas.map((q) => (
                <tr key={q.quota_key} className="border-t border-border">
                  <td className="p-3">{q.quota_key}</td>
                  <td className={`p-3 ${STATE_CLASS[q.state]}`}>{STATE_LABEL[q.state]}</td>
                  <td className="p-3">
                    <QuotaValue quota={q} />
                  </td>
                  <td className="p-3">
                    <Button variant="outline" size="sm" onClick={() => setOverrideTarget(q.quota_key)}>
                      Grant Override
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <GrantQuotaOverrideDialog
        open={overrideTarget !== null}
        quotaKey={overrideTarget}
        onClose={() => setOverrideTarget(null)}
        onGrant={(overrideLimit, reason, expiresAt) => {
          setActionError(null);
          overrideMutation.mutate({ overrideLimit, reason, expiresAt });
        }}
        isPending={overrideMutation.isPending}
      />
    </div>
  );
}
