/**
 * RoleListPage — displays company roles table.
 *
 * Access: Admin+ (rank ≥ 80). "New Role" button shown to Admin+.
 *
 * Spec reference: Epic 4, Phase 12 (T110).
 */

'use client';

import { use } from 'react';
import Link from 'next/link';
import { ArrowLeftIcon, PlusIcon } from 'lucide-react';
import { buttonVariants } from '@/components/ui/button';
import { RoleTable } from '@/components/users-roles/RoleTable';
import { CompanyMemberProvider } from '@/components/users-roles/CompanyMemberProvider';
import { RequireRank } from '@/components/users-roles/RequireRank';
import { cn } from '@/lib/utils';

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function RoleListPage({ params }: PageProps) {
  const { id } = use(params);
  const basePath = `/companies/${id}/roles`;

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
          <h1 className="text-xl font-semibold text-foreground">Roles</h1>
          <RequireRank minRank={80}>
            <Link
              href={`${basePath}/new`}
              className={cn(buttonVariants({ size: 'sm' }), 'gap-1.5')}
              aria-label="Create new role"
            >
              <PlusIcon className="size-4" />
              New Role
            </Link>
          </RequireRank>
        </div>

        {/* Table */}
        <RequireRank
          minRank={80}
          fallback={
            <div
              role="alert"
              className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
            >
              You do not have permission to view roles. Admin access is required.
            </div>
          }
        >
          <RoleTable companyId={id} basePath={basePath} />
        </RequireRank>
      </div>
    </CompanyMemberProvider>
  );
}
