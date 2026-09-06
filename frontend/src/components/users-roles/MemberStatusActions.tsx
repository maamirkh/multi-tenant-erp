'use client';

/**
 * MemberStatusActions — lifecycle action buttons for a member.
 *
 * Available actions depend on the member's current status and the actor's rank
 * relative to the member's rank (actor must outrank the member).
 *
 * Status transitions:
 *   active           → deactivate, suspend, lock, archive
 *   inactive         → reactivate, archive
 *   suspended        → reactivate, lock, archive
 *   locked           → reactivate, archive
 *   pending_invitation → archive
 *   archived         → restore
 *
 * Suspend and Archive show confirmation dialogs with a required reason field.
 * Deactivate, Lock, Reactivate, Restore show simple confirmation dialogs.
 *
 * Spec reference: Epic 4, Phase 11 (T097).
 */

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
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
import { useChangeMemberStatus } from '@/hooks/users-roles/useMembers';
import { SuspendSchema } from '@/schemas/users-roles';
import type { SuspendFormData, ArchiveFormData } from '@/schemas/users-roles';
import type { MemberDetail } from '@/types/users-roles';
import { ApiClientError } from '@/lib/api/client';

// ── Reason dialog ─────────────────────────────────────────────────────────────

interface ReasonDialogProps {
  open: boolean;
  title: string;
  description: string;
  submitLabel: string;
  onClose: () => void;
  onConfirm: (reason: string) => void;
  isPending: boolean;
}

function ReasonDialog({
  open,
  title,
  description,
  submitLabel,
  onClose,
  onConfirm,
  isPending,
}: ReasonDialogProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<SuspendFormData | ArchiveFormData>({
    resolver: zodResolver(SuspendSchema),
  });

  function handleClose() {
    reset();
    onClose();
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) handleClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <form
          onSubmit={handleSubmit((data) => onConfirm(data.reason))}
          noValidate
          className="space-y-3"
        >
          <div>
            <label htmlFor="action_reason" className="block text-sm font-medium text-foreground mb-1">
              Reason <span aria-hidden="true" className="text-destructive">*</span>
            </label>
            <Input
              id="action_reason"
              type="text"
              placeholder="Provide a reason"
              aria-invalid={!!errors.reason}
              {...register('reason')}
            />
            {errors.reason && (
              <p className="text-xs text-destructive mt-1" role="alert">
                {errors.reason.message}
              </p>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose} disabled={isPending}>
              Cancel
            </Button>
            <Button type="submit" variant="destructive" disabled={isPending}>
              {isPending ? 'Processing…' : submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── Simple confirmation dialog ────────────────────────────────────────────────

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  submitLabel: string;
  onClose: () => void;
  onConfirm: () => void;
  isPending: boolean;
  variant?: 'default' | 'destructive';
}

function ConfirmDialog({
  open,
  title,
  description,
  submitLabel,
  onClose,
  onConfirm,
  isPending,
  variant = 'default',
}: ConfirmDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={isPending}>
            Cancel
          </Button>
          <Button
            type="button"
            variant={variant}
            onClick={onConfirm}
            disabled={isPending}
          >
            {isPending ? 'Processing…' : submitLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

type DialogType = 'deactivate' | 'suspend' | 'lock' | 'reactivate' | 'archive' | 'restore' | null;

interface MemberStatusActionsProps {
  companyId: string;
  member: MemberDetail;
  /** Rank of the actor (current logged-in user). */
  actorRank: number;
  /** Called after any successful status change. */
  onStatusChange?: () => void;
}

export function MemberStatusActions({
  companyId,
  member,
  actorRank,
  onStatusChange,
}: MemberStatusActionsProps) {
  const [openDialog, setOpenDialog] = useState<DialogType>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const changeStatus = useChangeMemberStatus(companyId);

  // Actor must outrank the member to perform lifecycle actions.
  const canManage = actorRank > member.role.rank;

  if (!canManage) return null;

  const status = member.status;

  const canDeactivate = status === 'active';
  const canSuspend = status === 'active';
  const canLock = status === 'active' || status === 'suspended';
  const canReactivate =
    status === 'inactive' || status === 'suspended' || status === 'locked';
  const canArchive =
    status !== 'archived';
  const canRestore = status === 'archived';

  function handleAction(action: Parameters<typeof changeStatus.mutate>[0]['action']) {
    setActionError(null);
    changeStatus.mutate(
      { memberId: member.id, action },
      {
        onSuccess: () => {
          setOpenDialog(null);
          onStatusChange?.();
        },
        onError: (err) => {
          if (err instanceof ApiClientError) {
            setActionError(err.error.error.message);
          } else {
            setActionError(err.message ?? 'An error occurred');
          }
        },
      }
    );
  }

  const isPending = changeStatus.isPending;

  return (
    <div className="space-y-2">
      {/* Action error banner */}
      {actionError && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
        >
          {actionError}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap gap-2">
        {canReactivate && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setOpenDialog('reactivate')}
            disabled={isPending}
          >
            Reactivate
          </Button>
        )}
        {canDeactivate && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setOpenDialog('deactivate')}
            disabled={isPending}
          >
            Deactivate
          </Button>
        )}
        {canSuspend && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setOpenDialog('suspend')}
            disabled={isPending}
          >
            Suspend
          </Button>
        )}
        {canLock && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setOpenDialog('lock')}
            disabled={isPending}
          >
            Lock
          </Button>
        )}
        {canArchive && (
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setOpenDialog('archive')}
            disabled={isPending}
          >
            Archive
          </Button>
        )}
        {canRestore && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setOpenDialog('restore')}
            disabled={isPending}
          >
            Restore
          </Button>
        )}
      </div>

      {/* Deactivate dialog */}
      <ConfirmDialog
        open={openDialog === 'deactivate'}
        title="Deactivate Member"
        description={`Deactivate ${member.display_name}? Their access will be revoked immediately. You can reactivate them later.`}
        submitLabel="Deactivate"
        onClose={() => setOpenDialog(null)}
        onConfirm={() => handleAction({ type: 'deactivate' })}
        isPending={isPending}
        variant="destructive"
      />

      {/* Suspend dialog */}
      <ReasonDialog
        open={openDialog === 'suspend'}
        title="Suspend Member"
        description={`Suspend ${member.display_name}? Their access will be suspended and sessions revoked. Provide a reason.`}
        submitLabel="Suspend"
        onClose={() => setOpenDialog(null)}
        onConfirm={(reason) => handleAction({ type: 'suspend', reason })}
        isPending={isPending}
      />

      {/* Lock dialog */}
      <ConfirmDialog
        open={openDialog === 'lock'}
        title="Lock Member"
        description={`Lock ${member.display_name}? Their account will be locked and sessions revoked.`}
        submitLabel="Lock"
        onClose={() => setOpenDialog(null)}
        onConfirm={() => handleAction({ type: 'lock' })}
        isPending={isPending}
        variant="destructive"
      />

      {/* Reactivate dialog */}
      <ConfirmDialog
        open={openDialog === 'reactivate'}
        title="Reactivate Member"
        description={`Reactivate ${member.display_name}? They will regain access to the company.`}
        submitLabel="Reactivate"
        onClose={() => setOpenDialog(null)}
        onConfirm={() => handleAction({ type: 'reactivate' })}
        isPending={isPending}
      />

      {/* Archive dialog */}
      <ReasonDialog
        open={openDialog === 'archive'}
        title="Archive Member"
        description={`Archive ${member.display_name}? This soft-deletes their membership. Provide a reason.`}
        submitLabel="Archive"
        onClose={() => setOpenDialog(null)}
        onConfirm={(reason) => handleAction({ type: 'archive', reason })}
        isPending={isPending}
      />

      {/* Restore dialog */}
      <ConfirmDialog
        open={openDialog === 'restore'}
        title="Restore Member"
        description={`Restore ${member.display_name} from archive? They will be set to active.`}
        submitLabel="Restore"
        onClose={() => setOpenDialog(null)}
        onConfirm={() => handleAction({ type: 'restore' })}
        isPending={isPending}
      />
    </div>
  );
}
