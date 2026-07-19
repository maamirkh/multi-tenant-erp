'use client';

/**
 * RoleForm — shared form for creating and editing custom roles.
 *
 * Props:
 *   mode: 'create' | 'edit' — controls submit button label and default values.
 *   role: initial values (edit mode only).
 *   onSubmit: called with form data; returns void (mutations handled by page).
 *   isPending: disables form while request is in flight.
 *   serverError: optional root error message from the mutation.
 *   readOnly: when true, all fields are disabled (used for system role read view).
 *
 * Validation: CreateRoleSchema / UpdateRoleSchema via react-hook-form + Zod.
 * Permission selection: RolePermissionChecklist (controlled by form state).
 *
 * Spec reference: Epic 4, Phase 12 (T109).
 */

import { useController, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { RolePermissionChecklist } from '@/components/users-roles/RolePermissionChecklist';
import { CreateRoleSchema } from '@/schemas/users-roles';
import type { CreateRoleFormData } from '@/schemas/users-roles';
import type { RoleDetail } from '@/types/users-roles';

interface RoleFormProps {
  mode: 'create' | 'edit';
  role?: RoleDetail;
  onSubmit: (data: CreateRoleFormData) => void;
  onCancel: () => void;
  isPending: boolean;
  serverError: string | undefined;
  readOnly?: boolean;
}

function FieldError({ message }: { message: string | undefined }) {
  if (!message) return null;
  return (
    <p className="text-xs text-destructive mt-1" role="alert">
      {message}
    </p>
  );
}

export function RoleForm({
  mode,
  role,
  onSubmit,
  onCancel,
  isPending,
  serverError,
  readOnly = false,
}: RoleFormProps) {
  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isDirty },
  } = useForm<CreateRoleFormData>({
    resolver: zodResolver(CreateRoleSchema),
    defaultValues: {
      name: role?.name ?? '',
      description: role?.description ?? '',
      rank: role?.rank ?? 30,
      permission_codes: role?.permissions.map((p) => p.code) ?? [],
    },
  });

  // Controlled field for permission_codes (array, not natively supported by register)
  const { field: permField } = useController({
    name: 'permission_codes',
    control,
  });

  const isEdit = mode === 'edit';
  const submitLabel = readOnly ? undefined : isEdit ? 'Save Changes' : 'Create Role';
  const pendingLabel = isEdit ? 'Saving…' : 'Creating…';

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      noValidate
      className="space-y-5"
    >
      {/* Server-level error */}
      {serverError && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
        >
          {serverError}
        </div>
      )}

      {/* Read-only notice for system roles */}
      {readOnly && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950/30 p-3 text-sm text-blue-700 dark:text-blue-400">
          System roles are read-only and cannot be modified.
        </div>
      )}

      {/* Name */}
      <div>
        <label htmlFor="role_name" className="block text-sm font-medium text-foreground mb-1">
          Name{!readOnly && <span aria-hidden="true" className="text-destructive ml-0.5">*</span>}
        </label>
        <Input
          id="role_name"
          type="text"
          placeholder="e.g. Warehouse Supervisor"
          disabled={readOnly}
          aria-invalid={!!errors.name}
          {...register('name')}
        />
        <FieldError message={errors.name?.message} />
      </div>

      {/* Description */}
      <div>
        <label htmlFor="role_description" className="block text-sm font-medium text-foreground mb-1">
          Description
        </label>
        <textarea
          id="role_description"
          rows={2}
          placeholder="Describe the purpose of this role"
          disabled={readOnly}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring resize-none disabled:opacity-60"
          aria-invalid={!!errors.description}
          {...register('description')}
        />
        <FieldError message={errors.description?.message} />
      </div>

      {/* Rank */}
      <div>
        <label htmlFor="role_rank" className="block text-sm font-medium text-foreground mb-1">
          Rank{!readOnly && <span aria-hidden="true" className="text-destructive ml-0.5">*</span>}
        </label>
        <Input
          id="role_rank"
          type="number"
          min={1}
          max={99}
          disabled={readOnly}
          aria-invalid={!!errors.rank}
          {...register('rank', { valueAsNumber: true })}
        />
        {!readOnly && (
          <p className="text-xs text-muted-foreground mt-1">
            1–99. System rank values (100, 80, 60, 55, 50, 45, 42, 20) are reserved
            and will be rejected.
          </p>
        )}
        <FieldError message={errors.rank?.message} />
      </div>

      {/* Permissions */}
      <div>
        <p className="text-sm font-medium text-foreground mb-2">
          Permissions
        </p>
        <RolePermissionChecklist
          value={permField.value}
          onChange={permField.onChange}
          readOnly={readOnly}
        />
        <FieldError message={errors.permission_codes?.message} />
      </div>

      {/* Actions */}
      {!readOnly && (
        <div className="flex justify-end gap-3 pt-2">
          <Button
            type="button"
            variant="outline"
            onClick={onCancel}
            disabled={isPending}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={isPending || (isEdit && !isDirty)}
          >
            {isPending ? pendingLabel : submitLabel}
          </Button>
        </div>
      )}

      {readOnly && (
        <div className="flex justify-end pt-2">
          <Button type="button" variant="outline" onClick={onCancel}>
            Back
          </Button>
        </div>
      )}
    </form>
  );
}
