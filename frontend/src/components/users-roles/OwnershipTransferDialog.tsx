'use client';

/**
 * OwnershipTransferDialog — two-step UI for transferring company ownership.
 *
 * Step 1 — Selection:
 *   Displays a list of active members (excluding the current owner).
 *   User selects the intended new owner.
 *
 * Step 2 — Confirmation:
 *   Shows the selected member's name prominently.
 *   Requires an explicit "Transfer Ownership" click to proceed.
 *   Warns that the action cannot be undone and the current user becomes Admin.
 *
 * Uses useMembers (active filter, page_size 100) and useTransferOwnership.
 * Excludes the current user via useCompanyMemberContext().currentMember.user_id.
 *
 * Props:
 *   companyId: company scoping the transfer.
 *   onSuccess:  called after successful transfer.
 *   onCancel:   called when user dismisses without transferring.
 *
 * Spec reference: Epic 4, Phase 14 (T124).
 */

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useCompanyMemberContext } from '@/components/users-roles/CompanyMemberProvider';
import { useMembers } from '@/hooks/users-roles/useMembers';
import { useTransferOwnership } from '@/hooks/users-roles/useOwnershipTransfer';
import { ApiClientError } from '@/lib/api/client';
import type { MemberListItem } from '@/types/users-roles';

interface OwnershipTransferDialogProps {
  companyId: string;
  onSuccess: () => void;
  onCancel: () => void;
}

type Step = 'select' | 'confirm';

export function OwnershipTransferDialog({
  companyId,
  onSuccess,
  onCancel,
}: OwnershipTransferDialogProps) {
  const [step, setStep] = useState<Step>('select');
  const [selectedMember, setSelectedMember] = useState<MemberListItem | null>(null);
  const [serverError, setServerError] = useState<string | undefined>(undefined);

  const { currentMember } = useCompanyMemberContext();
  const { data: membersPage, isLoading: membersLoading } = useMembers(companyId, {
    status: 'active',
    page_size: 100,
  });
  const transfer = useTransferOwnership(companyId);

  // Exclude current owner from candidate list.
  const candidates = (membersPage?.items ?? []).filter(
    (m) => m.user_id !== currentMember?.user_id
  );

  function handleSelect(member: MemberListItem) {
    setSelectedMember(member);
  }

  function handleProceedToConfirm() {
    if (!selectedMember) return;
    setStep('confirm');
    setServerError(undefined);
  }

  function handleBack() {
    setStep('select');
    setServerError(undefined);
  }

  function handleConfirm() {
    if (!selectedMember) return;
    setServerError(undefined);
    transfer.mutate(selectedMember.id, {
      onSuccess: () => onSuccess(),
      onError: (err) => {
        if (err instanceof ApiClientError) {
          setServerError(err.error.error.message);
        } else {
          setServerError(err.message ?? 'Failed to transfer ownership');
        }
      },
    });
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onCancel(); }}>
      <DialogContent className="sm:max-w-md">
        {step === 'select' ? (
          <>
            <DialogHeader>
              <DialogTitle>Transfer Ownership</DialogTitle>
              <DialogDescription>
                Select the member who will become the new Owner of this company.
                Active members only are shown.
              </DialogDescription>
            </DialogHeader>

            {/* Member list */}
            <div className="space-y-2 max-h-72 overflow-y-auto py-1">
              {membersLoading && (
                <div className="space-y-2" aria-busy="true" aria-label="Loading members">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="h-12 animate-pulse rounded-lg bg-muted" />
                  ))}
                </div>
              )}

              {!membersLoading && candidates.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No active members available for ownership transfer.
                </p>
              )}

              {candidates.map((member) => {
                const isSelected = selectedMember?.id === member.id;
                return (
                  <button
                    key={member.id}
                    type="button"
                    onClick={() => handleSelect(member)}
                    className={`w-full flex items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors ${
                      isSelected
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:bg-muted/50'
                    }`}
                    aria-pressed={isSelected}
                  >
                    {/* Avatar or initials */}
                    <span className="size-8 rounded-full bg-muted flex items-center justify-center text-xs font-semibold text-muted-foreground flex-shrink-0 overflow-hidden">
                      {member.avatar_url ? (
                        <img
                          src={member.avatar_url}
                          alt=""
                          className="size-full object-cover"
                        />
                      ) : (
                        member.display_name
                          .split(/\s+/)
                          .slice(0, 2)
                          .map((w) => w[0]?.toUpperCase() ?? '')
                          .join('')
                      )}
                    </span>
                    <span className="min-w-0">
                      <span className="block text-sm font-medium text-foreground truncate">
                        {member.display_name}
                      </span>
                      <span className="block text-xs text-muted-foreground truncate">
                        {member.email}
                      </span>
                    </span>
                    {isSelected && (
                      <span className="ml-auto text-primary text-xs font-medium flex-shrink-0">
                        Selected
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={onCancel}>
                Cancel
              </Button>
              <Button
                type="button"
                onClick={handleProceedToConfirm}
                disabled={!selectedMember}
              >
                Continue
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Confirm Ownership Transfer</DialogTitle>
              <DialogDescription>
                This action cannot be undone. You will become an Admin after
                the transfer.
              </DialogDescription>
            </DialogHeader>

            {/* Prominent target name */}
            <div className="rounded-lg border border-border bg-muted/30 p-4 text-center">
              <p className="text-xs text-muted-foreground mb-1">New Owner</p>
              <p className="text-lg font-semibold text-foreground">
                {selectedMember?.display_name}
              </p>
              <p className="text-sm text-muted-foreground">{selectedMember?.email}</p>
            </div>

            <p className="text-sm text-muted-foreground">
              After confirming, <strong>{selectedMember?.display_name}</strong> will
              become the Owner and you will be demoted to Admin. This cannot be
              reversed without their consent.
            </p>

            {/* Server error */}
            {serverError && (
              <p className="text-sm text-destructive" role="alert">
                {serverError}
              </p>
            )}

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={handleBack}
                disabled={transfer.isPending}
              >
                Back
              </Button>
              <Button
                type="button"
                variant="destructive"
                onClick={handleConfirm}
                disabled={transfer.isPending}
              >
                {transfer.isPending ? 'Transferring…' : 'Transfer Ownership'}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
