/**
 * OwnershipTransferPage — entry point for the ownership transfer flow.
 *
 * Access: Owner-only (rank = 100). Shows OwnershipTransferDialog.
 * On success or cancel, navigates back to the company members page.
 *
 * Spec reference: Epic 4, Phase 14 (T125).
 */

'use client';

import { use } from 'react';
import { useRouter } from 'next/navigation';
import { CompanyMemberProvider } from '@/components/users-roles/CompanyMemberProvider';
import { RequireRank } from '@/components/users-roles/RequireRank';
import { OwnershipTransferDialog } from '@/components/users-roles/OwnershipTransferDialog';

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function OwnershipTransferPage({ params }: PageProps) {
  const { id } = use(params);
  const router = useRouter();
  const membersPath = `/companies/${id}/members`;

  return (
    <CompanyMemberProvider companyId={id}>
      <RequireRank
        minRank={100}
        fallback={
          <div
            role="alert"
            className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
          >
            Only the company Owner can transfer ownership.
          </div>
        }
      >
        <OwnershipTransferDialog
          companyId={id}
          onSuccess={() => router.push(membersPath)}
          onCancel={() => router.push(membersPath)}
        />
      </RequireRank>
    </CompanyMemberProvider>
  );
}
