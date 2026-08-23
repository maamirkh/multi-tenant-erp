'use client';

/**
 * T202 — Support Access page. Grant is company-scoped
 * (`PlatformSelectedTenantContext`, T186) + reason-required; the grant
 * window is server-determined — the contract's
 * `InitiateSupportAccessRequest` deliberately accepts no client-supplied
 * `expires_at` (`schemas/support_access.py`) — so this page displays the
 * server-assigned expiry rather than collecting one. An active grant
 * this session created shows a persistent, unmistakable privileged-mode
 * indicator (FR-9A-194) until terminated or expired. Terminate is
 * explicitly confirmed.
 *
 * The contract has no "my active grants" filter (`GET /support-access`
 * takes only page/page_size) and no administrator-identity endpoint, so
 * the indicator tracks only the grant this session itself initiated —
 * documented scope, not a security gap (support access remains
 * independently enforced and audited server-side regardless).
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  initiateSupportAccess,
  terminateSupportAccess,
  listSupportAccessGrants,
  type SupportAccessGrant,
} from '@/lib/api/platform-admin';
import { usePlatformSelectedTenantContext } from '@/contexts/PlatformSelectedTenantContext';
import { NoTenantSelected } from '@/components/platform-admin/NoTenantSelected';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ConfirmDialog } from '@/components/platform-admin/dialogs';
import {
  LoadingState,
  ErrorState,
  EmptyState,
  PermissionDeniedState,
  PaginationFooter,
  messageFromError,
  isForbidden,
} from '@/components/platform-admin/DataState';

const PAGE_SIZE = 20;

export default function PlatformSupportAccessPage(): React.JSX.Element {
  const { selectedTenant } = usePlatformSelectedTenantContext();
  const queryClient = useQueryClient();
  const [reason, setReason] = useState('');
  const [touched, setTouched] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [activeGrant, setActiveGrant] = useState<SupportAccessGrant | null>(null);
  const [terminateConfirm, setTerminateConfirm] = useState(false);
  const [page, setPage] = useState(1);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['platform', 'support-access', page],
    queryFn: () => listSupportAccessGrants({ page, page_size: PAGE_SIZE }),
  });

  const initiateMutation = useMutation({
    mutationFn: () => initiateSupportAccess(selectedTenant!.id, reason.trim()),
    onSuccess: (grant) => {
      setActiveGrant(grant);
      setReason('');
      setTouched(false);
      void queryClient.invalidateQueries({ queryKey: ['platform', 'support-access'] });
    },
    onError: (err) => setFormError(messageFromError(err)),
  });

  const terminateMutation = useMutation({
    mutationFn: (grantId: string) => terminateSupportAccess(grantId),
    onSuccess: () => {
      setActiveGrant(null);
      setTerminateConfirm(false);
      void queryClient.invalidateQueries({ queryKey: ['platform', 'support-access'] });
    },
    onError: (err) => setFormError(messageFromError(err)),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Support Access</h1>
        <p className="text-sm text-muted-foreground">
          Time-bounded, reason-required, inspection-only access grants.
        </p>
      </div>

      {activeGrant && (
        <div
          role="alert"
          className="flex items-center justify-between rounded-lg border-2 border-destructive bg-destructive/10 p-4 text-sm font-semibold text-destructive"
        >
          <span>
            PRIVILEGED SUPPORT ACCESS ACTIVE — expires {new Date(activeGrant.expires_at).toLocaleString()}
          </span>
          <Button variant="destructive" size="sm" onClick={() => setTerminateConfirm(true)}>
            Terminate
          </Button>
        </div>
      )}

      <section className="rounded-lg border border-border p-4">
        <h2 className="mb-3 text-sm font-semibold text-foreground">Initiate Grant</h2>
        {!selectedTenant ? (
          <NoTenantSelected />
        ) : (
          <>
            <p className="mb-3 text-sm text-muted-foreground">For {selectedTenant.legalName}</p>
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
                if (!reason.trim()) return;
                initiateMutation.mutate();
              }}
              noValidate
              className="flex flex-wrap items-end gap-3"
            >
              <div className="flex-1 min-w-48">
                <label htmlFor="support_access_reason" className="mb-1 block text-sm font-medium">Reason</label>
                <Input
                  id="support_access_reason"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  aria-invalid={touched && !reason.trim()}
                />
                {touched && !reason.trim() && (
                  <p className="mt-1 text-xs text-destructive" role="alert">A reason is required.</p>
                )}
              </div>
              <Button type="submit" disabled={initiateMutation.isPending || !!activeGrant}>
                {initiateMutation.isPending ? 'Initiating…' : 'Initiate Grant'}
              </Button>
            </form>
          </>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground">Grant History</h2>
        {isLoading && <LoadingState />}
        {isError && isForbidden(error) && <PermissionDeniedState />}
        {isError && !isForbidden(error) && (
          <ErrorState message={messageFromError(error)} onRetry={() => void refetch()} />
        )}
        {data && data.items.length === 0 && <EmptyState message="No support-access grants recorded yet." />}
        {data && data.items.length > 0 && (
          <>
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="p-3">Company</th>
                    <th className="p-3">Reason</th>
                    <th className="p-3">Status</th>
                    <th className="p-3">Started</th>
                    <th className="p-3">Expires</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((grant) => (
                    <tr key={grant.id} className="border-t border-border">
                      <td className="p-3 font-mono text-xs">{grant.company_id}</td>
                      <td className="p-3">{grant.reason}</td>
                      <td className="p-3">{grant.status}</td>
                      <td className="p-3 text-muted-foreground">{new Date(grant.started_at).toLocaleString()}</td>
                      <td className="p-3 text-muted-foreground">{new Date(grant.expires_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <PaginationFooter page={data.page} pages={data.pages} total={data.total} onPageChange={setPage} />
          </>
        )}
      </section>

      <ConfirmDialog
        open={terminateConfirm}
        title="Terminate Support Access"
        description="End this privileged support-access grant immediately?"
        submitLabel="Terminate"
        variant="destructive"
        onClose={() => setTerminateConfirm(false)}
        onConfirm={() => {
          if (activeGrant) {
            setFormError(null);
            terminateMutation.mutate(activeGrant.id);
          }
        }}
        isPending={terminateMutation.isPending}
      />
    </div>
  );
}
