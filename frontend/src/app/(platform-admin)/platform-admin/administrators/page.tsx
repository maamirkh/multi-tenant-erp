'use client';

/**
 * T198 — Platform Administrators page. Consumes only the Administrator
 * API routes (T068) through `platformApiClient` (T179) — never any
 * tenant/company service. Requires `platform.admins.read` for listing;
 * create/activate/deactivate gated on `platform.admins.manage`
 * server-side. Deactivate warns that active sessions are invalidated;
 * the `LastPlatformOwnerError` 409 is surfaced verbatim as a specific
 * message (never a generic failure banner).
 *
 * The contract's `CreatePlatformAdministratorRequest` accepts only an
 * existing `user_id` (mass-assignment protection,
 * `schemas/platform_administrator.py`) — there is no Platform user-search
 * endpoint, so the operator supplies the target User's UUID directly.
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listAdministrators,
  createAdministrator,
  updateAdministrator,
  type PlatformAdministrator,
} from '@/lib/api/platform-admin';
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
import { ReasonDialog, ConfirmDialog } from '@/components/platform-admin/dialogs';
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

function CreateAdministratorDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}): React.JSX.Element {
  const queryClient = useQueryClient();
  const [userId, setUserId] = useState('');
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => createAdministrator(userId),
    onSuccess: () => {
      setUserId('');
      void queryClient.invalidateQueries({ queryKey: ['platform', 'administrators'] });
      onClose();
    },
    onError: (err) => setError(messageFromError(err)),
  });

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create Platform Administrator</DialogTitle>
          <DialogDescription>
            Grants Platform authority to an existing User account (reuses their credentials).
          </DialogDescription>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setError(null);
            mutation.mutate();
          }}
          noValidate
          className="space-y-3"
        >
          {error && (
            <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <div>
            <label htmlFor="admin_user_id" className="mb-1 block text-sm font-medium">User ID</label>
            <Input
              id="admin_user_id"
              required
              placeholder="Existing User UUID"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={mutation.isPending}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? 'Creating…' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function PlatformAdministratorsPage(): React.JSX.Element {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [showCreate, setShowCreate] = useState(false);
  const [deactivateTarget, setDeactivateTarget] = useState<PlatformAdministrator | null>(null);
  const [activateTarget, setActivateTarget] = useState<PlatformAdministrator | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['platform', 'administrators', page],
    queryFn: () => listAdministrators({ page, page_size: PAGE_SIZE }),
  });

  const activateMutation = useMutation({
    mutationFn: (admin: PlatformAdministrator) =>
      updateAdministrator(admin.id, { is_active: true }),
    onSuccess: () => {
      setActivateTarget(null);
      void queryClient.invalidateQueries({ queryKey: ['platform', 'administrators'] });
    },
    onError: (err) => setActionError(messageFromError(err)),
  });

  const deactivateMutation = useMutation({
    mutationFn: ({ admin, reason }: { admin: PlatformAdministrator; reason: string }) =>
      updateAdministrator(admin.id, { is_active: false, reason }),
    onSuccess: () => {
      setDeactivateTarget(null);
      void queryClient.invalidateQueries({ queryKey: ['platform', 'administrators'] });
    },
    onError: (err) => setActionError(messageFromError(err)),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Platform Administrators</h1>
          <p className="text-sm text-muted-foreground">Accounts with Platform authority, independent of any tenant membership.</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>New Administrator</Button>
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

      {data && data.items.length === 0 && <EmptyState message="No Platform Administrators found." />}

      {data && data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="p-3">User ID</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Last Login</th>
                  <th className="p-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((admin) => (
                  <tr key={admin.id} className="border-t border-border">
                    <td className="p-3 font-mono text-xs">{admin.user_id}</td>
                    <td className="p-3">{admin.is_active ? 'Active' : 'Deactivated'}</td>
                    <td className="p-3 text-muted-foreground">
                      {admin.last_login_at ? new Date(admin.last_login_at).toLocaleString() : 'Never'}
                    </td>
                    <td className="p-3">
                      {admin.is_active ? (
                        <Button variant="destructive" size="sm" onClick={() => setDeactivateTarget(admin)}>
                          Deactivate
                        </Button>
                      ) : (
                        <Button variant="outline" size="sm" onClick={() => setActivateTarget(admin)}>
                          Activate
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <PaginationFooter page={data.page} pages={data.pages} total={data.total} onPageChange={setPage} />
        </>
      )}

      <CreateAdministratorDialog open={showCreate} onClose={() => setShowCreate(false)} />

      <ReasonDialog
        open={deactivateTarget !== null}
        title="Deactivate Platform Administrator"
        description="This immediately revokes all of this administrator's active Platform sessions. Provide a reason."
        submitLabel="Deactivate"
        variant="destructive"
        onClose={() => setDeactivateTarget(null)}
        onConfirm={(reason) => {
          if (deactivateTarget) {
            setActionError(null);
            deactivateMutation.mutate({ admin: deactivateTarget, reason });
          }
        }}
        isPending={deactivateMutation.isPending}
      />

      <ConfirmDialog
        open={activateTarget !== null}
        title="Activate Platform Administrator"
        description="Restore this administrator's Platform access."
        submitLabel="Activate"
        onClose={() => setActivateTarget(null)}
        onConfirm={() => {
          if (activateTarget) {
            setActionError(null);
            activateMutation.mutate(activateTarget);
          }
        }}
        isPending={activateMutation.isPending}
      />
    </div>
  );
}
