'use client';

/**
 * RoleTable — table of company roles with system/custom type badge,
 * rank, member count, and per-role actions.
 *
 * Edit: available for all roles.
 * Delete: available only for custom roles with 0 assigned members.
 * Requires actorRank ≥ 80 to show the table at all (enforced by page).
 *
 * Spec reference: Epic 4, Phase 12 (T106).
 */

import { useState } from 'react';
import Link from 'next/link';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { RoleBadge } from '@/components/users-roles/RoleBadge';
import { useRoles, useDeleteRole } from '@/hooks/users-roles/useRoles';
import { ApiClientError } from '@/lib/api/client';
import type { RoleListItem } from '@/types/users-roles';

interface RoleTableProps {
  companyId: string;
  /** Base URL for role links, e.g. /companies/{id}/roles */
  basePath: string;
}

interface DeleteDialogProps {
  role: RoleListItem;
  onClose: () => void;
  onConfirm: () => void;
  isPending: boolean;
  error: string | null;
}

function DeleteRoleDialog({
  role,
  onClose,
  onConfirm,
  isPending,
  error,
}: DeleteDialogProps) {
  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete Role</DialogTitle>
          <DialogDescription>
            Delete the custom role <strong>{role.name}</strong>? This cannot be
            undone. Ensure no members are assigned before deleting.
          </DialogDescription>
        </DialogHeader>
        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={isPending}>
            Cancel
          </Button>
          <Button type="button" variant="destructive" onClick={onConfirm} disabled={isPending}>
            {isPending ? 'Deleting…' : 'Delete Role'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function RoleTable({ companyId, basePath }: RoleTableProps) {
  const [deleteTarget, setDeleteTarget] = useState<RoleListItem | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const { data: roles, isLoading, isError, error } = useRoles(companyId);
  const deleteRole = useDeleteRole(companyId);

  function handleDeleteConfirm() {
    if (!deleteTarget) return;
    setDeleteError(null);
    deleteRole.mutate(deleteTarget.id, {
      onSuccess: () => setDeleteTarget(null),
      onError: (err) => {
        if (err instanceof ApiClientError) {
          setDeleteError(err.error.error.message);
        } else {
          setDeleteError(err.message ?? 'Failed to delete role');
        }
      },
    });
  }

  if (isLoading) {
    return (
      <div className="space-y-2" aria-busy="true" aria-label="Loading roles">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-12 animate-pulse rounded bg-muted" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
      >
        {error?.message ?? 'Failed to load roles'}
      </div>
    );
  }

  // Sort: system roles first (by rank desc), then custom (by rank desc)
  const sorted = [...(roles ?? [])].sort((a, b) => {
    if (a.is_system !== b.is_system) return a.is_system ? -1 : 1;
    return b.rank - a.rank;
  });

  return (
    <>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm" aria-label="Company roles">
          <thead className="border-b border-border bg-muted/40">
            <tr>
              <th scope="col" className="px-4 py-3 text-left font-medium text-muted-foreground">
                Role
              </th>
              <th scope="col" className="px-4 py-3 text-center font-medium text-muted-foreground">
                Rank
              </th>
              <th scope="col" className="px-4 py-3 text-center font-medium text-muted-foreground">
                Members
              </th>
              <th scope="col" className="px-4 py-3 text-left font-medium text-muted-foreground">
                Description
              </th>
              <th scope="col" className="px-4 py-3 text-right font-medium text-muted-foreground">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {sorted.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                  No roles found
                </td>
              </tr>
            ) : (
              sorted.map((role) => (
                <tr key={role.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3">
                    <RoleBadge
                      name={role.name}
                      rank={role.rank}
                      isSystem={role.is_system}
                    />
                    {!role.is_active && (
                      <span className="ml-2 text-xs text-muted-foreground">(inactive)</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center font-mono text-foreground">
                    {role.rank}
                  </td>
                  <td className="px-4 py-3 text-center text-foreground">
                    {role.member_count}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground max-w-xs truncate">
                    {role.description ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Link
                        href={`${basePath}/${role.id}`}
                        className="text-xs text-primary underline underline-offset-2 hover:text-primary/80"
                      >
                        View
                      </Link>
                      <Link
                        href={`${basePath}/${role.id}/edit`}
                        className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
                      >
                        Edit
                      </Link>
                      {!role.is_system && role.member_count === 0 && (
                        <button
                          type="button"
                          onClick={() => {
                            setDeleteError(null);
                            setDeleteTarget(role);
                          }}
                          className="text-xs text-destructive underline underline-offset-2 hover:text-destructive/80"
                          aria-label={`Delete ${role.name}`}
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {deleteTarget && (
        <DeleteRoleDialog
          role={deleteTarget}
          onClose={() => setDeleteTarget(null)}
          onConfirm={handleDeleteConfirm}
          isPending={deleteRole.isPending}
          error={deleteError}
        />
      )}
    </>
  );
}
