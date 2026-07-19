/**
 * EditMemberPage — renders EditMemberForm pre-populated with current member data.
 *
 * Access: Admin+ (rank ≥ 80). Navigates to member detail on success or cancel.
 *
 * Spec reference: Epic 4, Phase 11 (T101).
 */

'use client';

import { use } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeftIcon } from 'lucide-react';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EditMemberForm } from '@/components/users-roles/EditMemberForm';
import { CompanyMemberProvider, useCompanyMemberContext } from '@/components/users-roles/CompanyMemberProvider';
import { RequireRank } from '@/components/users-roles/RequireRank';
import { useMember } from '@/hooks/users-roles/useMember';
import { cn } from '@/lib/utils';

// ── Loading skeleton ──────────────────────────────────────────────────────────

function EditMemberSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading member">
      <div className="h-8 w-48 animate-pulse rounded bg-muted" />
      <div className="h-96 animate-pulse rounded-xl bg-muted" />
    </div>
  );
}

// ── Inner content (needs CompanyMemberProvider) ───────────────────────────────

interface EditMemberContentProps {
  companyId: string;
  memberId: string;
  detailPath: string;
}

function EditMemberContent({ companyId, memberId, detailPath }: EditMemberContentProps) {
  const router = useRouter();
  const { currentMemberRank } = useCompanyMemberContext();
  const { data: member, isLoading, isError, error } = useMember(companyId, memberId);

  if (isLoading) return <EditMemberSkeleton />;

  if (isError || !member) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
      >
        {error?.message ?? 'Member not found'}
      </div>
    );
  }

  // Prevent editing members with equal or higher rank.
  if (currentMemberRank <= member.role.rank) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
      >
        You cannot edit a member with equal or higher rank than your own.
      </div>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Edit {member.display_name}</CardTitle>
      </CardHeader>
      <CardContent>
        <EditMemberForm
          companyId={companyId}
          member={member}
          onSuccess={() => router.push(detailPath)}
          onCancel={() => router.push(detailPath)}
        />
      </CardContent>
    </Card>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

interface PageProps {
  params: Promise<{ id: string; memberId: string }>;
}

export default function EditMemberPage({ params }: PageProps) {
  const { id, memberId } = use(params);
  const detailPath = `/companies/${id}/members/${memberId}`;

  return (
    <CompanyMemberProvider companyId={id}>
      <div className="space-y-6">
        <Link
          href={detailPath}
          aria-label="Back to member"
          className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'gap-1.5')}
        >
          <ArrowLeftIcon className="size-4" />
          Member
        </Link>

        <RequireRank
          minRank={80}
          fallback={
            <div
              role="alert"
              className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
            >
              You do not have permission to edit members. Admin access is required.
            </div>
          }
        >
          <EditMemberContent
            companyId={id}
            memberId={memberId}
            detailPath={detailPath}
          />
        </RequireRank>
      </div>
    </CompanyMemberProvider>
  );
}
