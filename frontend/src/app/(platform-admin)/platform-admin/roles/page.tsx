'use client';

/**
 * T199 — Platform Roles page. Consumes only the RBAC API routes (T069)
 * through `platformApiClient` (T179) — never any tenant/company
 * service. Requires `platform.rbac.read` for listing; create/update and
 * assignment gated on `platform.rbac.manage` server-side. Self-
 * escalation (403) and last-Platform-Owner-removal (409) are surfaced
 * verbatim, not folded into a generic failure message.
 *
 * The contract declares no permission-catalogue-listing endpoint, so
 * `permission_codes` is entered as a comma-separated list; the server
 * validates every code against the seeded catalogue (422 on an
 * unrecognised code, `router.py`'s `create_or_update_role`).
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listRoles,
  createOrUpdateRole,
  assignRole,
  listAdministrators,
  type PlatformRole,
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
import {
  LoadingState,
  ErrorState,
  EmptyState,
  PermissionDeniedState,
  messageFromError,
  isForbidden,
} from '@/components/platform-admin/DataState';

function RoleFormDialog({
  open,
  role,
  onClose,
}: {
  open: boolean;
  role: PlatformRole | null;
  onClose: () => void;
}): React.JSX.Element {
  const queryClient = useQueryClient();
  const [code, setCode] = useState(role?.code ?? '');
  const [name, setName] = useState(role?.name ?? '');
  const [description, setDescription] = useState(role?.description ?? '');
  const [permissionCodes, setPermissionCodes] = useState((role?.permission_codes ?? []).join(', '));
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      createOrUpdateRole({
        code: code.trim(),
        name: name.trim(),
        description: description.trim() || null,
        permission_codes: permissionCodes
          .split(',')
          .map((c) => c.trim())
          .filter(Boolean),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['platform', 'roles'] });
      onClose();
    },
    onError: (err) => setError(messageFromError(err)),
  });

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{role ? 'Edit Role' : 'Create Role'}</DialogTitle>
          <DialogDescription>Roles are addressed by their stable code, not an editable id.</DialogDescription>
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
            <label htmlFor="role_code" className="mb-1 block text-sm font-medium">Code</label>
            <Input id="role_code" required disabled={!!role} value={code} onChange={(e) => setCode(e.target.value)} />
          </div>
          <div>
            <label htmlFor="role_name" className="mb-1 block text-sm font-medium">Name</label>
            <Input id="role_name" required value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label htmlFor="role_description" className="mb-1 block text-sm font-medium">Description</label>
            <Input id="role_description" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div>
            <label htmlFor="role_permissions" className="mb-1 block text-sm font-medium">
              Permission codes (comma-separated)
            </label>
            <Input
              id="role_permissions"
              value={permissionCodes}
              onChange={(e) => setPermissionCodes(e.target.value)}
              placeholder="platform.tenants.read, platform.audit.read"
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={mutation.isPending}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? 'Saving…' : 'Save'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function AssignRoleSection({ roles }: { roles: PlatformRole[] }): React.JSX.Element {
  const queryClient = useQueryClient();
  const [adminId, setAdminId] = useState('');
  const [roleId, setRoleId] = useState('');
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const { data: adminsData } = useQuery({
    queryKey: ['platform', 'administrators', 'for-assignment'],
    queryFn: () => listAdministrators({ page: 1, page_size: 100 }),
  });

  const mutation = useMutation({
    mutationFn: () => assignRole(adminId, roleId, reason || null),
    onSuccess: () => {
      setSuccess(true);
      setReason('');
      void queryClient.invalidateQueries({ queryKey: ['platform', 'administrators'] });
    },
    onError: (err) => setError(messageFromError(err)),
  });

  return (
    <section className="rounded-lg border border-border p-4">
      <h2 className="mb-3 text-sm font-semibold text-foreground">Assign Role</h2>
      {error && (
        <div role="alert" className="mb-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}
      {success && !error && (
        <div role="status" className="mb-3 rounded-lg border border-green-300/40 bg-green-500/10 p-3 text-sm text-green-700">
          Role assigned.
        </div>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setError(null);
          setSuccess(false);
          mutation.mutate();
        }}
        noValidate
        className="flex flex-wrap items-end gap-3"
      >
        <div>
          <label htmlFor="assign_admin" className="mb-1 block text-sm font-medium">Administrator</label>
          <select
            id="assign_admin"
            required
            value={adminId}
            onChange={(e) => setAdminId(e.target.value)}
            className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none"
          >
            <option value="">Select…</option>
            {(adminsData?.items ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {a.user_id}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="assign_role" className="mb-1 block text-sm font-medium">Role</label>
          <select
            id="assign_role"
            required
            value={roleId}
            onChange={(e) => setRoleId(e.target.value)}
            className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none"
          >
            <option value="">Select…</option>
            {roles.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="assign_reason" className="mb-1 block text-sm font-medium">Reason</label>
          <Input id="assign_reason" value={reason} onChange={(e) => setReason(e.target.value)} />
        </div>
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? 'Assigning…' : 'Assign'}
        </Button>
      </form>
    </section>
  );
}

export default function PlatformRolesPage(): React.JSX.Element {
  const [showForm, setShowForm] = useState(false);
  const [editRole, setEditRole] = useState<PlatformRole | null>(null);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['platform', 'roles'],
    queryFn: () => listRoles({ page: 1, page_size: 100 }),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Platform Roles</h1>
          <p className="text-sm text-muted-foreground">Permission bundles assignable to Platform Administrators.</p>
        </div>
        <Button
          onClick={() => {
            setEditRole(null);
            setShowForm(true);
          }}
        >
          New Role
        </Button>
      </div>

      {isLoading && <LoadingState />}
      {isError && isForbidden(error) && <PermissionDeniedState />}
      {isError && !isForbidden(error) && (
        <ErrorState message={messageFromError(error)} onRetry={() => void refetch()} />
      )}

      {data && data.items.length === 0 && <EmptyState message="No Platform Roles defined yet." />}

      {data && data.items.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="p-3">Code</th>
                <th className="p-3">Name</th>
                <th className="p-3">Permissions</th>
                <th className="p-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((role) => (
                <tr key={role.id} className="border-t border-border">
                  <td className="p-3 font-mono text-xs">{role.code}</td>
                  <td className="p-3">{role.name}</td>
                  <td className="p-3 text-xs text-muted-foreground">
                    {role.permission_codes.length} permission(s)
                  </td>
                  <td className="p-3">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setEditRole(role);
                        setShowForm(true);
                      }}
                    >
                      Edit
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.items.length > 0 && <AssignRoleSection roles={data.items} />}

      <RoleFormDialog
        open={showForm}
        role={editRole}
        onClose={() => {
          setShowForm(false);
          setEditRole(null);
        }}
      />
    </div>
  );
}
