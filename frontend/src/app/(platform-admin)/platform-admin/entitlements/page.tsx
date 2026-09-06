'use client';

/**
 * T196 — Entitlements page, for the `PlatformSelectedTenantContext`
 * tenant (T186; same tenant-scoped-only reasoning as T195/T197/T201).
 * Requires `platform.entitlements.read`; override grant requires
 * `platform.entitlements.override`, a reason, and an optional expiry —
 * permanent (no expiry) vs temporary overrides are visually
 * distinguished.
 *
 * The contract declares no endpoint to *list* active overrides (only
 * grant/revoke-by-id, `contracts/platform-admin-v1.yaml`) — this page
 * tracks overrides it grants in this session so they can be revoked
 * immediately after creation; a page reload returns to the read-only
 * effective-entitlement view, which is always authoritative regardless.
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getTenantEntitlements,
  grantEntitlementOverride,
  revokeEntitlementOverride,
  type EntitlementOverride,
} from '@/lib/api/platform-admin';
import { usePlatformSelectedTenantContext } from '@/contexts/PlatformSelectedTenantContext';
import { NoTenantSelected } from '@/components/platform-admin/NoTenantSelected';
import { Button } from '@/components/ui/button';
import { ConfirmDialog } from '@/components/platform-admin/dialogs';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import {
  LoadingState,
  ErrorState,
  EmptyState,
  PermissionDeniedState,
  messageFromError,
  isForbidden,
} from '@/components/platform-admin/DataState';

function GrantOverrideDialog({
  open,
  capabilityKey,
  onClose,
  onGrant,
  isPending,
}: {
  open: boolean;
  capabilityKey: string | null;
  onClose: () => void;
  onGrant: (reason: string, expiresAt: string | null) => void;
  isPending: boolean;
}): React.JSX.Element {
  const [reason, setReason] = useState('');
  const [expiresAt, setExpiresAt] = useState('');

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Grant Entitlement Override</DialogTitle>
          <DialogDescription>
            Grant {capabilityKey} regardless of the plan ceiling. Leave expiry blank for a permanent override.
          </DialogDescription>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!reason.trim()) return;
            onGrant(reason.trim(), expiresAt ? new Date(expiresAt).toISOString() : null);
          }}
          noValidate
          className="space-y-3"
        >
          <div>
            <label htmlFor="override_reason" className="mb-1 block text-sm font-medium">Reason</label>
            <Input id="override_reason" required value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
          <div>
            <label htmlFor="override_expires" className="mb-1 block text-sm font-medium">
              Expiry (optional — blank = permanent)
            </label>
            <Input
              id="override_expires"
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

export default function PlatformEntitlementsPage(): React.JSX.Element {
  const { selectedTenant } = usePlatformSelectedTenantContext();
  const queryClient = useQueryClient();
  const [grantTarget, setGrantTarget] = useState<string | null>(null);
  const [sessionOverrides, setSessionOverrides] = useState<EntitlementOverride[]>([]);
  const [revokeTarget, setRevokeTarget] = useState<EntitlementOverride | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['platform', 'entitlements', selectedTenant?.id],
    queryFn: () => getTenantEntitlements(selectedTenant!.id),
    enabled: !!selectedTenant,
  });

  const grantMutation = useMutation({
    mutationFn: ({ reason, expiresAt }: { reason: string; expiresAt: string | null }) =>
      grantEntitlementOverride(selectedTenant!.id, {
        capability_key: grantTarget!,
        reason,
        expires_at: expiresAt,
      }),
    onSuccess: (override) => {
      setSessionOverrides((prev) => [...prev, override]);
      setGrantTarget(null);
      void queryClient.invalidateQueries({ queryKey: ['platform', 'entitlements', selectedTenant?.id] });
    },
    onError: (err) => setActionError(messageFromError(err)),
  });

  const revokeMutation = useMutation({
    mutationFn: (override: EntitlementOverride) =>
      revokeEntitlementOverride(selectedTenant!.id, override.id),
    onSuccess: (_void, override) => {
      setSessionOverrides((prev) => prev.filter((o) => o.id !== override.id));
      setRevokeTarget(null);
      void queryClient.invalidateQueries({ queryKey: ['platform', 'entitlements', selectedTenant?.id] });
    },
    onError: (err) => setActionError(messageFromError(err)),
  });

  if (!selectedTenant) {
    return (
      <div className="space-y-6">
        <h1 className="text-xl font-semibold text-foreground">Entitlements</h1>
        <NoTenantSelected />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Entitlements</h1>
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

      {data && data.entitlements.length === 0 && <EmptyState message="No capabilities configured." />}

      {data && data.entitlements.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="p-3">Capability</th>
                <th className="p-3">Available</th>
                <th className="p-3">Reason</th>
                <th className="p-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.entitlements.map((e) => {
                const sessionOverride = sessionOverrides.find(
                  (o) => o.capability_key === e.capability_key && o.is_active
                );
                return (
                  <tr key={e.capability_key} className="border-t border-border">
                    <td className="p-3">{e.capability_key}</td>
                    <td className="p-3">
                      <span className={e.available ? 'text-green-600' : 'text-muted-foreground'}>
                        {e.available ? 'Available' : 'Unavailable'}
                      </span>
                    </td>
                    <td className="p-3 text-muted-foreground">{e.reason}</td>
                    <td className="p-3">
                      {sessionOverride ? (
                        <div className="flex items-center gap-2">
                          <span className="rounded bg-primary/10 px-2 py-0.5 text-xs text-primary">
                            {sessionOverride.expires_at ? 'Temporary override' : 'Permanent override'}
                          </span>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setRevokeTarget(sessionOverride)}
                          >
                            Revoke
                          </Button>
                        </div>
                      ) : (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setGrantTarget(e.capability_key)}
                        >
                          Grant Override
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <GrantOverrideDialog
        open={grantTarget !== null}
        capabilityKey={grantTarget}
        onClose={() => setGrantTarget(null)}
        onGrant={(reason, expiresAt) => {
          setActionError(null);
          grantMutation.mutate({ reason, expiresAt });
        }}
        isPending={grantMutation.isPending}
      />

      <ConfirmDialog
        open={revokeTarget !== null}
        title="Revoke Override"
        description={`Revoke the ${revokeTarget?.capability_key ?? ''} override? This is logged for audit.`}
        submitLabel="Revoke"
        variant="destructive"
        onClose={() => setRevokeTarget(null)}
        onConfirm={() => {
          if (revokeTarget) {
            setActionError(null);
            revokeMutation.mutate(revokeTarget);
          }
        }}
        isPending={revokeMutation.isPending}
      />
    </div>
  );
}
