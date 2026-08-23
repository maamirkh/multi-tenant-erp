'use client';

/**
 * Shared confirmation dialogs for Platform pages (Phase 15).
 *
 * Mirrors `components/users-roles/MemberStatusActions.tsx`'s existing
 * `ReasonDialog`/`ConfirmDialog` pattern exactly — extracted here since
 * every Platform mutation (suspend/reactivate/deactivate/terminate/
 * override/adjust) requires the same "reason + explicit confirm" shape
 * (plan.md §7 Architecture Freeze — reason-bound, audited mutations).
 */

import { useState } from 'react';
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

export interface ReasonDialogProps {
  open: boolean;
  title: string;
  description: string;
  submitLabel: string;
  onClose: () => void;
  onConfirm: (reason: string) => void;
  isPending: boolean;
  variant?: 'default' | 'destructive';
}

export function ReasonDialog({
  open,
  title,
  description,
  submitLabel,
  onClose,
  onConfirm,
  isPending,
  variant = 'default',
}: ReasonDialogProps): React.JSX.Element {
  const [reason, setReason] = useState('');
  const [touched, setTouched] = useState(false);
  const trimmed = reason.trim();
  const invalid = touched && trimmed.length === 0;

  function handleClose(): void {
    setReason('');
    setTouched(false);
    onClose();
  }

  function handleSubmit(e: React.FormEvent): void {
    e.preventDefault();
    setTouched(true);
    if (trimmed.length === 0) return;
    onConfirm(trimmed);
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) handleClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} noValidate className="space-y-3">
          <div>
            <label htmlFor="platform_action_reason" className="mb-1 block text-sm font-medium text-foreground">
              Reason <span aria-hidden="true" className="text-destructive">*</span>
            </label>
            <Input
              id="platform_action_reason"
              type="text"
              placeholder="Provide a reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              aria-invalid={invalid}
            />
            {invalid && (
              <p className="mt-1 text-xs text-destructive" role="alert">
                A reason is required.
              </p>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose} disabled={isPending}>
              Cancel
            </Button>
            <Button type="submit" variant={variant} disabled={isPending}>
              {isPending ? 'Processing…' : submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  submitLabel: string;
  onClose: () => void;
  onConfirm: () => void;
  isPending: boolean;
  variant?: 'default' | 'destructive';
}

export function ConfirmDialog({
  open,
  title,
  description,
  submitLabel,
  onClose,
  onConfirm,
  isPending,
  variant = 'default',
}: ConfirmDialogProps): React.JSX.Element {
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
          <Button type="button" variant={variant} onClick={onConfirm} disabled={isPending}>
            {isPending ? 'Processing…' : submitLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
