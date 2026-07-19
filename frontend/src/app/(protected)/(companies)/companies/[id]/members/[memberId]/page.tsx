/**
 * MemberDetailPage — full member profile with status badge, employee info,
 * role, and lifecycle action buttons.
 *
 * Accessible to Admin+ and to the member themselves (self-view).
 * MemberStatusActions and notes are only shown to Admin+ (rank ≥ 80).
 *
 * Spec reference: Epic 4, Phase 11 (T100).
 */

'use client';

import { use } from 'react';
import Link from 'next/link';
import { ArrowLeftIcon, PencilIcon } from 'lucide-react';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { MemberStatusBadge } from '@/components/users-roles/MemberStatusBadge';
import { MemberStatusActions } from '@/components/users-roles/MemberStatusActions';
import { CompanyMemberProvider, useCompanyMemberContext } from '@/components/users-roles/CompanyMemberProvider';
import { useMember } from '@/hooks/users-roles/useMember';
import { cn } from '@/lib/utils';
import { useAuthContext } from '@/contexts/AuthContext';

// ── Detail row helper ─────────────────────────────────────────────────────────

function DetailRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex justify-between py-2 border-b border-border last:border-b-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium text-foreground">{value ?? '—'}</span>
    </div>
  );
}

// ── Loading skeleton ──────────────────────────────────────────────────────────

function MemberDetailSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading member details">
      <div className="h-8 w-48 animate-pulse rounded bg-muted" />
      <div className="h-64 animate-pulse rounded-xl bg-muted" />
    </div>
  );
}

// ── Inner content (needs CompanyMemberProvider) ───────────────────────────────

interface MemberDetailContentProps {
  companyId: string;
  memberId: string;
}

function MemberDetailContent({ companyId, memberId }: MemberDetailContentProps) {
  const { user } = useAuthContext();
  const { currentMemberRank } = useCompanyMemberContext();
  const { data: member, isLoading, isError, error, refetch } = useMember(companyId, memberId);

  if (isLoading) return <MemberDetailSkeleton />;

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

  const isAdmin = currentMemberRank >= 80;
  const isSelf = user?.user_id === member.user_id;

  // Non-admin can only view themselves.
  if (!isAdmin && !isSelf) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
      >
        You do not have permission to view this member profile.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Member header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-xl font-semibold text-foreground">{member.display_name}</h1>
          <p className="text-sm text-muted-foreground">{member.email}</p>
          <div className="flex items-center gap-2 mt-1">
            <MemberStatusBadge status={member.status} />
            <span className="text-xs text-muted-foreground">{member.role.name}</span>
          </div>
        </div>

        {isAdmin && (
          <Link
            href={`/companies/${companyId}/members/${memberId}/edit`}
            className={cn(buttonVariants({ variant: 'outline', size: 'sm' }), 'gap-1.5')}
            aria-label={`Edit ${member.display_name}`}
          >
            <PencilIcon className="size-4" />
            Edit
          </Link>
        )}
      </div>

      {/* Status actions (Admin+ only) */}
      {isAdmin && (
        <MemberStatusActions
          companyId={companyId}
          member={member}
          actorRank={currentMemberRank}
          onStatusChange={() => void refetch()}
        />
      )}

      {/* Profile card */}
      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
        </CardHeader>
        <CardContent className="space-y-0">
          <DetailRow label="Name" value={member.display_name} />
          <DetailRow label="Email" value={member.email} />
          <DetailRow label="Role" value={member.role.name} />
          <DetailRow label="Status" value={member.status} />
          <DetailRow label="Member since" value={member.created_at.split('T')[0]} />
        </CardContent>
      </Card>

      {/* Employee info card */}
      <Card>
        <CardHeader>
          <CardTitle>Employee Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-0">
          <DetailRow label="Job Title" value={member.job_title} />
          <DetailRow label="Department" value={member.department} />
          <DetailRow label="Employee ID" value={member.employee_id} />
          <DetailRow label="Work Phone" value={member.work_phone} />
          <DetailRow label="Hire Date" value={member.hire_date} />
          {/* Notes hidden from non-admins by backend (FR-023), frontend mirrors */}
          {isAdmin && member.notes !== null && (
            <DetailRow label="Notes" value={member.notes} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

interface PageProps {
  params: Promise<{ id: string; memberId: string }>;
}

export default function MemberDetailPage({ params }: PageProps) {
  const { id, memberId } = use(params);

  return (
    <CompanyMemberProvider companyId={id}>
      <div className="space-y-6">
        <Link
          href={`/companies/${id}/members`}
          aria-label="Back to members"
          className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'gap-1.5')}
        >
          <ArrowLeftIcon className="size-4" />
          Members
        </Link>

        <MemberDetailContent companyId={id} memberId={memberId} />
      </div>
    </CompanyMemberProvider>
  );
}
