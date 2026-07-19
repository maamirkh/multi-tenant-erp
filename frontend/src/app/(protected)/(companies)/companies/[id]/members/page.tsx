/**
 * MemberListPage — displays a searchable, filterable paginated list of company
 * members. Accessible to Admin+ (rank ≥ 80). All authenticated members can
 * view the list (enforced by backend — frontend shows it to all to allow
 * self-lookup; Admin+ sees the "Add Member" button).
 *
 * Spec reference: Epic 4, Phase 11 (T098).
 */

'use client';

import { use } from 'react';
import Link from 'next/link';
import { ArrowLeftIcon, PlusIcon } from 'lucide-react';
import { buttonVariants } from '@/components/ui/button';
import { MemberTable } from '@/components/users-roles/MemberTable';
import { CompanyMemberProvider } from '@/components/users-roles/CompanyMemberProvider';
import { RequireRank } from '@/components/users-roles/RequireRank';
import { cn } from '@/lib/utils';

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function MemberListPage({ params }: PageProps) {
  const { id } = use(params);
  const basePath = `/companies/${id}/members`;

  return (
    <CompanyMemberProvider companyId={id}>
      <div className="space-y-6">
        {/* Navigation */}
        <Link
          href={`/companies/${id}`}
          aria-label="Back to company"
          className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'gap-1.5')}
        >
          <ArrowLeftIcon className="size-4" />
          Company
        </Link>

        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-xl font-semibold text-foreground">Members</h1>
          <RequireRank minRank={80}>
            <Link
              href={`${basePath}/add`}
              className={cn(buttonVariants({ size: 'sm' }), 'gap-1.5')}
              aria-label="Add new member"
            >
              <PlusIcon className="size-4" />
              Add Member
            </Link>
          </RequireRank>
        </div>

        {/* Table */}
        <MemberTable companyId={id} basePath={basePath} />
      </div>
    </CompanyMemberProvider>
  );
}
