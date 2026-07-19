/**
 * RoleDetailPage — displays role info, permissions grouped by module,
 * and a member count summary.
 *
 * Access: Admin+ (rank ≥ 80).
 *
 * Spec reference: Epic 4, Phase 12 (T112).
 */

'use client';

import { use } from 'react';
import Link from 'next/link';
import { ArrowLeftIcon, PencilIcon } from 'lucide-react';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { RoleBadge } from '@/components/users-roles/RoleBadge';
import { CompanyMemberProvider } from '@/components/users-roles/CompanyMemberProvider';
import { RequireRank } from '@/components/users-roles/RequireRank';
import { useRole } from '@/hooks/users-roles/useRole';
import { cn } from '@/lib/utils';
import type { PermissionItem } from '@/types/users-roles';

// ── Detail row helper ─────────────────────────────────────────────────────────

function DetailRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="flex justify-between py-2 border-b border-border last:border-b-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium text-foreground">{value ?? '—'}</span>
    </div>
  );
}

// ── Permissions grouped by module ─────────────────────────────────────────────

function PermissionsByModule({ permissions }: { permissions: PermissionItem[] }) {
  if (permissions.length === 0) {
    return <p className="text-sm text-muted-foreground">No permissions assigned.</p>;
  }

  const groups = permissions.reduce<Record<string, PermissionItem[]>>((acc, perm) => {
    (acc[perm.module] ??= []).push(perm);
    return acc;
  }, {});

  return (
    <div className="space-y-3">
      {Object.entries(groups).map(([module, perms]) => (
        <fieldset key={module} className="rounded-lg border border-border p-3">
          <legend className="text-sm font-semibold text-foreground capitalize px-1">
            {module}
          </legend>
          <ul className="grid grid-cols-1 gap-1.5 sm:grid-cols-2 mt-1">
            {perms.map((perm) => (
              <li key={perm.code} className="text-sm">
                <span className="font-medium text-foreground">{perm.label}</span>
                {perm.description && (
                  <span className="block text-xs text-muted-foreground">{perm.description}</span>
                )}
              </li>
            ))}
          </ul>
        </fieldset>
      ))}
    </div>
  );
}

// ── Loading skeleton ──────────────────────────────────────────────────────────

function RoleDetailSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading role details">
      <div className="h-8 w-48 animate-pulse rounded bg-muted" />
      <div className="h-48 animate-pulse rounded-xl bg-muted" />
      <div className="h-64 animate-pulse rounded-xl bg-muted" />
    </div>
  );
}

// ── Inner content (needs CompanyMemberProvider) ───────────────────────────────

interface RoleDetailContentProps {
  companyId: string;
  roleId: string;
}

function RoleDetailContent({ companyId, roleId }: RoleDetailContentProps) {
  const rolesPath = `/companies/${companyId}/roles`;
  const { data: role, isLoading, isError, error } = useRole(companyId, roleId);

  if (isLoading) return <RoleDetailSkeleton />;

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

  return (
    <div className="space-y-6">
      {/* Role header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <RoleBadge name={role.name} rank={role.rank} isSystem={role.is_system} />
          {role.description && (
            <p className="text-sm text-muted-foreground mt-1">{role.description}</p>
          )}
        </div>
        <Link
          href={`${rolesPath}/${roleId}/edit`}
          className={cn(buttonVariants({ variant: 'outline', size: 'sm' }), 'gap-1.5')}
          aria-label={`Edit ${role.name}`}
        >
          <PencilIcon className="size-4" />
          {role.is_system ? 'View Details' : 'Edit'}
        </Link>
      </div>

      {/* Role info card */}
      <Card>
        <CardHeader>
          <CardTitle>Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-0">
          <DetailRow label="Name" value={role.name} />
          <DetailRow label="Slug" value={role.slug} />
          <DetailRow label="Rank" value={role.rank} />
          <DetailRow label="Type" value={role.is_system ? 'System' : 'Custom'} />
          <DetailRow label="Status" value={role.is_active ? 'Active' : 'Inactive'} />
          <DetailRow label="Members assigned" value={role.member_count} />
          <DetailRow label="Created" value={role.created_at.split('T')[0]} />
          <DetailRow label="Updated" value={role.updated_at.split('T')[0]} />
        </CardContent>
      </Card>

      {/* Permissions card */}
      <Card>
        <CardHeader>
          <CardTitle>Permissions</CardTitle>
        </CardHeader>
        <CardContent>
          <PermissionsByModule permissions={role.permissions} />
        </CardContent>
      </Card>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

interface PageProps {
  params: Promise<{ id: string; roleId: string }>;
}

export default function RoleDetailPage({ params }: PageProps) {
  const { id, roleId } = use(params);

  return (
    <CompanyMemberProvider companyId={id}>
      <div className="space-y-6">
        <Link
          href={`/companies/${id}/roles`}
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
              You do not have permission to view role details. Admin access is required.
            </div>
          }
        >
          <RoleDetailContent companyId={id} roleId={roleId} />
        </RequireRank>
      </div>
    </CompanyMemberProvider>
  );
}
