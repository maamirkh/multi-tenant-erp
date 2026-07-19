/**
 * CreateRolePage — renders RoleForm in create mode.
 *
 * Access: Admin+ (rank ≥ 80). Navigates to the new role's detail page on success.
 *
 * Spec reference: Epic 4, Phase 12 (T111).
 */

'use client';

import { use, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeftIcon } from 'lucide-react';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { RoleForm } from '@/components/users-roles/RoleForm';
import { CompanyMemberProvider } from '@/components/users-roles/CompanyMemberProvider';
import { RequireRank } from '@/components/users-roles/RequireRank';
import { useCreateRole } from '@/hooks/users-roles/useRoles';
import { ApiClientError } from '@/lib/api/client';
import type { CreateRoleFormData } from '@/schemas/users-roles';
import { cn } from '@/lib/utils';

interface PageProps {
  params: Promise<{ id: string }>;
}

function CreateRoleContent({ companyId }: { companyId: string }) {
  const router = useRouter();
  const rolesPath = `/companies/${companyId}/roles`;
  const [serverError, setServerError] = useState<string | undefined>(undefined);
  const createRole = useCreateRole(companyId);

  function handleSubmit(data: CreateRoleFormData) {
    setServerError(undefined);
    createRole.mutate(
      {
        name: data.name,
        rank: data.rank,
        permission_codes: data.permission_codes,
        ...(data.description ? { description: data.description } : {}),
      },
      {
        onSuccess: (role) => router.push(`${rolesPath}/${role.id}`),
        onError: (err) => {
          if (err instanceof ApiClientError) {
            setServerError(err.error.error.message);
          } else {
            setServerError(err.message ?? 'Failed to create role');
          }
        },
      }
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>New Role</CardTitle>
      </CardHeader>
      <CardContent>
        <RoleForm
          mode="create"
          onSubmit={handleSubmit}
          onCancel={() => router.push(rolesPath)}
          isPending={createRole.isPending}
          serverError={serverError}
        />
      </CardContent>
    </Card>
  );
}

export default function CreateRolePage({ params }: PageProps) {
  const { id } = use(params);
  const rolesPath = `/companies/${id}/roles`;

  return (
    <CompanyMemberProvider companyId={id}>
      <div className="space-y-6">
        {/* Navigation */}
        <Link
          href={rolesPath}
          aria-label="Back to roles"
          className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'gap-1.5')}
        >
          <ArrowLeftIcon className="size-4" />
          Roles
        </Link>

        <RequireRank
          minRank={80}
          fallback={
            <div
              role="alert"
              className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
            >
              You do not have permission to create roles. Admin access is required.
            </div>
          }
        >
          <CreateRoleContent companyId={id} />
        </RequireRank>
      </div>
    </CompanyMemberProvider>
  );
}
