/**
 * EditRolePage — renders RoleForm in edit mode.
 *
 * System roles are displayed in read-only mode (no edits allowed).
 * Custom roles can be fully edited by Admin+ (rank ≥ 80).
 *
 * Spec reference: Epic 4, Phase 12 (T113).
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
import { useRole } from '@/hooks/users-roles/useRole';
import { useUpdateRole } from '@/hooks/users-roles/useRoles';
import { ApiClientError } from '@/lib/api/client';
import type { CreateRoleFormData } from '@/schemas/users-roles';
import { cn } from '@/lib/utils';

// ── Loading skeleton ──────────────────────────────────────────────────────────

function EditRoleSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading role">
      <div className="h-8 w-48 animate-pulse rounded bg-muted" />
      <div className="h-96 animate-pulse rounded-xl bg-muted" />
    </div>
  );
}

// ── Inner content (needs CompanyMemberProvider) ───────────────────────────────

interface EditRoleContentProps {
  companyId: string;
  roleId: string;
  detailPath: string;
}

function EditRoleContent({ companyId, roleId, detailPath }: EditRoleContentProps) {
  const router = useRouter();
  const [serverError, setServerError] = useState<string | undefined>(undefined);
  const { data: role, isLoading, isError, error } = useRole(companyId, roleId);
  const updateRole = useUpdateRole(companyId);

  if (isLoading) return <EditRoleSkeleton />;

  if (isError || !role) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
      >
        {error?.message ?? 'Role not found'}
      </div>
    );
  }

  function handleSubmit(data: CreateRoleFormData) {
    setServerError(undefined);
    updateRole.mutate(
      {
        roleId,
        data: {
          name: data.name,
          description: data.description || null,
          rank: data.rank,
          permission_codes: data.permission_codes,
        },
      },
      {
        onSuccess: () => router.push(detailPath),
        onError: (err) => {
          if (err instanceof ApiClientError) {
            setServerError(err.error.error.message);
          } else {
            setServerError(err.message ?? 'Failed to update role');
          }
        },
      }
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{role.is_system ? role.name : `Edit ${role.name}`}</CardTitle>
      </CardHeader>
      <CardContent>
        <RoleForm
          mode="edit"
          role={role}
          onSubmit={handleSubmit}
          onCancel={() => router.push(detailPath)}
          isPending={updateRole.isPending}
          serverError={serverError}
          readOnly={role.is_system}
        />
      </CardContent>
    </Card>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

interface PageProps {
  params: Promise<{ id: string; roleId: string }>;
}

export default function EditRolePage({ params }: PageProps) {
  const { id, roleId } = use(params);
  const detailPath = `/companies/${id}/roles/${roleId}`;

  return (
    <CompanyMemberProvider companyId={id}>
      <div className="space-y-6">
        <Link
          href={detailPath}
          aria-label="Back to role"
          className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'gap-1.5')}
        >
          <ArrowLeftIcon className="size-4" />
          Role
        </Link>

        <RequireRank
          minRank={80}
          fallback={
            <div
              role="alert"
              className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
            >
              You do not have permission to edit roles. Admin access is required.
            </div>
          }
        >
          <EditRoleContent companyId={id} roleId={roleId} detailPath={detailPath} />
        </RequireRank>
      </div>
    </CompanyMemberProvider>
  );
}
