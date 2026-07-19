/**
 * T080 — CompanyStatusActions component.
 *
 * Conditionally renders Activate/Deactivate/Delete buttons based on current
 * status and user role (owner).
 *
 * Deactivate: confirmation dialog with reason input (Zod: min 10 chars).
 * Delete: two-step confirmation with reason + confirm_delete checkbox.
 * Shows optimistic status change while request is in flight.
 *
 * Spec ref: Epic 3, Phase 11 (T080).
 */

'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useRouter } from 'next/navigation';

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
import { useActivateCompany, useDeactivateCompany } from '@/hooks/companies/useCompanyStatus';
import { useDeleteCompany } from '@/hooks/companies/useDeleteCompany';
import type { CompanyDetail } from '@/types/companies';

// ── Zod schemas ──────────────────────────────────────────────────────────────

const deactivateSchema = z.object({
  reason: z.string().min(10, 'Reason must be at least 10 characters'),
});

const deleteSchema = z.object({
  reason: z.string().min(10, 'Reason must be at least 10 characters'),
  confirm_delete: z.literal(true, {
    errorMap: () => ({ message: 'You must confirm deletion' }),
  }),
});

type DeactivateFormData = z.infer<typeof deactivateSchema>;
type DeleteFormData = z.infer<typeof deleteSchema>;

// ── Sub-dialogs ──────────────────────────────────────────────────────────────

interface DeactivateDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
  isPending: boolean;
}

function DeactivateDialog({ open, onClose, onConfirm, isPending }: DeactivateDialogProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<DeactivateFormData>({
    resolver: zodResolver(deactivateSchema),
  });

  function handleClose() {
    reset();
    onClose();
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) handleClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Deactivate Company</DialogTitle>
          <DialogDescription>
            Deactivating this company will prevent users from accessing it. You can reactivate it at any time.
          </DialogDescription>
        </DialogHeader>

        <form
          onSubmit={handleSubmit((data) => onConfirm(data.reason))}
          noValidate
          className="space-y-3"
        >
          <div className="space-y-1">
            <label htmlFor="deactivate_reason" className="text-sm font-medium text-foreground">
              Reason <span aria-hidden="true" className="text-destructive">*</span>
            </label>
            <Input
              id="deactivate_reason"
              type="text"
              placeholder="Provide a reason (min 10 characters)"
              aria-invalid={!!errors.reason}
              aria-describedby={errors.reason ? 'deactivate_reason_error' : undefined}
              {...register('reason')}
            />
            {errors.reason && (
              <p id="deactivate_reason_error" className="text-xs text-destructive" role="alert">
                {errors.reason.message}
              </p>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose} disabled={isPending}>
              Cancel
            </Button>
            <Button type="submit" variant="destructive" disabled={isPending}>
              {isPending ? 'Deactivating…' : 'Deactivate'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

interface DeleteDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
  isPending: boolean;
}

function DeleteDialog({ open, onClose, onConfirm, isPending }: DeleteDialogProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<DeleteFormData>({
    resolver: zodResolver(deleteSchema),
  });

  function handleClose() {
    reset();
    onClose();
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) handleClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete Company</DialogTitle>
          <DialogDescription>
            This will soft-delete the company. It can be restored within the retention period.
            This action cannot be undone after the retention period expires.
          </DialogDescription>
        </DialogHeader>

        <form
          onSubmit={handleSubmit((data) => onConfirm(data.reason))}
          noValidate
          className="space-y-3"
        >
          <div className="space-y-1">
            <label htmlFor="delete_reason" className="text-sm font-medium text-foreground">
              Reason <span aria-hidden="true" className="text-destructive">*</span>
            </label>
            <Input
              id="delete_reason"
              type="text"
              placeholder="Provide a reason (min 10 characters)"
              aria-invalid={!!errors.reason}
              aria-describedby={errors.reason ? 'delete_reason_error' : undefined}
              {...register('reason')}
            />
            {errors.reason && (
              <p id="delete_reason_error" className="text-xs text-destructive" role="alert">
                {errors.reason.message}
              </p>
            )}
          </div>

          <div className="flex items-center gap-2">
            <input
              id="confirm_delete"
              type="checkbox"
              aria-invalid={!!errors.confirm_delete}
              aria-describedby={errors.confirm_delete ? 'confirm_delete_error' : undefined}
              {...register('confirm_delete')}
            />
            <label htmlFor="confirm_delete" className="text-sm text-foreground select-none">
              I understand this company will be deleted
            </label>
          </div>
          {errors.confirm_delete && (
            <p id="confirm_delete_error" className="text-xs text-destructive" role="alert">
              {errors.confirm_delete.message}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose} disabled={isPending}>
              Cancel
            </Button>
            <Button type="submit" variant="destructive" disabled={isPending}>
              {isPending ? 'Deleting…' : 'Delete Company'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface CompanyStatusActionsProps {
  company: CompanyDetail;
  /** Current user's id — actions only shown to the company owner. */
  userId: string;
}

export function CompanyStatusActions({ company, userId }: CompanyStatusActionsProps) {
  const router = useRouter();
  const [deactivateOpen, setDeactivateOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const activate = useActivateCompany(company.id);
  const deactivate = useDeactivateCompany(company.id);
  const deleteCompany = useDeleteCompany();

  const isOwner = company.owner_id === userId;

  if (!isOwner) return null;

  const canActivate = company.status === 'inactive' || company.status === 'pending_setup';
  const canDeactivate = company.status === 'active';
  const canDelete = company.status !== 'deleted';

  function handleDeactivate(reason: string) {
    deactivate.mutate({ reason }, {
      onSuccess: () => {
        setDeactivateOpen(false);
      },
    });
  }

  function handleDelete(reason: string) {
    deleteCompany.mutate(
      { id: company.id, data: { reason, confirm_delete: true } },
      {
        onSuccess: () => {
          setDeleteOpen(false);
          router.push('/companies');
        },
      }
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {canActivate && (
        <Button
          variant="outline"
          onClick={() => activate.mutate()}
          disabled={activate.isPending}
          aria-label={`Activate ${company.legal_name}`}
        >
          {activate.isPending ? 'Activating…' : 'Activate'}
        </Button>
      )}

      {canDeactivate && (
        <Button
          variant="outline"
          onClick={() => setDeactivateOpen(true)}
          disabled={deactivate.isPending}
          aria-label={`Deactivate ${company.legal_name}`}
        >
          Deactivate
        </Button>
      )}

      {canDelete && (
        <Button
          variant="destructive"
          onClick={() => setDeleteOpen(true)}
          disabled={deleteCompany.isPending}
          aria-label={`Delete ${company.legal_name}`}
        >
          Delete
        </Button>
      )}

      <DeactivateDialog
        open={deactivateOpen}
        onClose={() => setDeactivateOpen(false)}
        onConfirm={handleDeactivate}
        isPending={deactivate.isPending}
      />

      <DeleteDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={handleDelete}
        isPending={deleteCompany.isPending}
      />
    </div>
  );
}
