/**
 * AddMemberPage — renders AddMemberForm for inviting a new member.
 *
 * Access: Admin+ (rank ≥ 80). Navigates back to member list on success.
 *
 * Spec reference: Epic 4, Phase 11 (T099).
 */

'use client';

import { use } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeftIcon } from 'lucide-react';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AddMemberForm } from '@/components/users-roles/AddMemberForm';
import { CompanyMemberProvider } from '@/components/users-roles/CompanyMemberProvider';
import { RequireRank } from '@/components/users-roles/RequireRank';
import { cn } from '@/lib/utils';

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function AddMemberPage({ params }: PageProps) {
  const { id } = use(params);
  const router = useRouter();
  const membersPath = `/companies/${id}/members`;

  return (
    <CompanyMemberProvider companyId={id}>
      <div className="space-y-6">
        {/* Navigation */}
        <Link
          href={membersPath}
          aria-label="Back to members"
          className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'gap-1.5')}
        >
          <ArrowLeftIcon className="size-4" />
          Members
        </Link>

        <RequireRank
          minRank={80}
          fallback={
            <div
              role="alert"
              className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
            >
              You do not have permission to add members. Admin access is required.
            </div>
          }
        >
          <Card>
            <CardHeader>
              <CardTitle>Add Member</CardTitle>
            </CardHeader>
            <CardContent>
              <AddMemberForm
                companyId={id}
                onSuccess={() => router.push(membersPath)}
                onCancel={() => router.push(membersPath)}
              />
            </CardContent>
          </Card>
        </RequireRank>
      </div>
    </CompanyMemberProvider>
  );
}
