'use client';

/**
 * EditMemberForm — form for updating a member's role and employee info.
 *
 * Pre-populates all fields from the current MemberDetail.
 * Only sends fields that have changed (partial PATCH).
 *
 * Validation: UpdateMemberSchema (Zod) via react-hook-form.
 * Mutation: useUpdateMember.
 *
 * Spec reference: Epic 4, Phase 11 (T096).
 */

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useUpdateMember } from '@/hooks/users-roles/useMembers';
import { useRoles } from '@/hooks/users-roles/useRoles';
import { UpdateMemberSchema } from '@/schemas/users-roles';
import type { UpdateMemberFormData } from '@/schemas/users-roles';
import { ApiClientError } from '@/lib/api/client';
import type { MemberDetail, UpdateMemberInput } from '@/types/users-roles';

interface EditMemberFormProps {
  companyId: string;
  member: MemberDetail;
  onSuccess: () => void;
  onCancel: () => void;
}

function FieldError({ message }: { message: string | undefined }) {
  if (!message) return null;
  return (
    <p className="text-xs text-destructive mt-1" role="alert">
      {message}
    </p>
  );
}

export function EditMemberForm({
  companyId,
  member,
  onSuccess,
  onCancel,
}: EditMemberFormProps) {
  const { data: roles, isLoading: rolesLoading } = useRoles(companyId);
  const updateMember = useUpdateMember(companyId);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<UpdateMemberFormData>({
    resolver: zodResolver(UpdateMemberSchema),
    defaultValues: {
      role_id: member.role.id,
      employee_id: member.employee_id ?? '',
      job_title: member.job_title ?? '',
      department: member.department ?? '',
      work_phone: member.work_phone ?? '',
      hire_date: member.hire_date ?? '',
      notes: member.notes ?? '',
    },
  });

  async function onSubmit(formData: UpdateMemberFormData) {
    const input: UpdateMemberInput = {};

    if (formData.role_id && formData.role_id !== member.role.id) {
      input.role_id = formData.role_id;
    }
    if (formData.employee_id !== (member.employee_id ?? '')) {
      input.employee_id = formData.employee_id || null;
    }
    if (formData.job_title !== (member.job_title ?? '')) {
      input.job_title = formData.job_title || null;
    }
    if (formData.department !== (member.department ?? '')) {
      input.department = formData.department || null;
    }
    if (formData.work_phone !== (member.work_phone ?? '')) {
      input.work_phone = formData.work_phone || null;
    }
    if (formData.hire_date !== (member.hire_date ?? '')) {
      input.hire_date = formData.hire_date || null;
    }
    if (formData.notes !== (member.notes ?? '')) {
      input.notes = formData.notes ?? null;
    }

    updateMember.mutate(
      { memberId: member.id, data: input },
      {
        onSuccess: () => onSuccess(),
        onError: (err) => {
          if (err instanceof ApiClientError && err.status === 409) {
            const code = err.error.error.code;
            if (code === 'EMPLOYEE_ID_CONFLICT') {
              setError('employee_id', {
                message: 'This employee ID is already in use by another member',
              });
            } else {
              setError('root', { message: err.error.error.message });
            }
          } else if (err instanceof ApiClientError && err.status === 422) {
            const code = err.error.error.code;
            if (code === 'HIRE_DATE_IN_FUTURE') {
              setError('hire_date', { message: 'Hire date cannot be in the future' });
            } else {
              setError('root', { message: err.error.error.message });
            }
          } else {
            setError('root', { message: err.message ?? 'An error occurred' });
          }
        },
      }
    );
  }

  const isPending = isSubmitting || updateMember.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-5">
      {errors.root && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
        >
          {errors.root.message}
        </div>
      )}

      {/* Role */}
      <div>
        <label htmlFor="edit_role_id" className="block text-sm font-medium text-foreground mb-1">
          Role
        </label>
        <select
          id="edit_role_id"
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
          aria-invalid={!!errors.role_id}
          disabled={rolesLoading}
          {...register('role_id')}
        >
          <option value="">No change</option>
          {roles
            ?.filter((r) => r.is_active)
            .sort((a, b) => b.rank - a.rank)
            .map((role) => (
              <option key={role.id} value={role.id}>
                {role.name}
              </option>
            ))}
        </select>
        <FieldError message={errors.role_id?.message} />
      </div>

      {/* Employee info */}
      <fieldset className="border border-border rounded-lg p-4 space-y-4">
        <legend className="text-sm font-medium text-muted-foreground px-1">
          Employee Information
        </legend>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="edit_job_title" className="block text-sm font-medium text-foreground mb-1">
              Job Title
            </label>
            <Input
              id="edit_job_title"
              type="text"
              aria-invalid={!!errors.job_title}
              {...register('job_title')}
            />
            <FieldError message={errors.job_title?.message} />
          </div>

          <div>
            <label htmlFor="edit_department" className="block text-sm font-medium text-foreground mb-1">
              Department
            </label>
            <Input
              id="edit_department"
              type="text"
              aria-invalid={!!errors.department}
              {...register('department')}
            />
            <FieldError message={errors.department?.message} />
          </div>

          <div>
            <label htmlFor="edit_employee_id" className="block text-sm font-medium text-foreground mb-1">
              Employee ID
            </label>
            <Input
              id="edit_employee_id"
              type="text"
              aria-invalid={!!errors.employee_id}
              {...register('employee_id')}
            />
            <FieldError message={errors.employee_id?.message} />
          </div>

          <div>
            <label htmlFor="edit_work_phone" className="block text-sm font-medium text-foreground mb-1">
              Work Phone
            </label>
            <Input
              id="edit_work_phone"
              type="tel"
              aria-invalid={!!errors.work_phone}
              {...register('work_phone')}
            />
            <FieldError message={errors.work_phone?.message} />
          </div>

          <div>
            <label htmlFor="edit_hire_date" className="block text-sm font-medium text-foreground mb-1">
              Hire Date
            </label>
            <Input
              id="edit_hire_date"
              type="date"
              aria-invalid={!!errors.hire_date}
              {...register('hire_date')}
            />
            <FieldError message={errors.hire_date?.message} />
          </div>
        </div>

        <div>
          <label htmlFor="edit_notes" className="block text-sm font-medium text-foreground mb-1">
            Notes
            <span className="ml-1 text-xs text-muted-foreground font-normal">
              (visible to admins only)
            </span>
          </label>
          <textarea
            id="edit_notes"
            rows={3}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring resize-none"
            aria-invalid={!!errors.notes}
            {...register('notes')}
          />
          <FieldError message={errors.notes?.message} />
        </div>
      </fieldset>

      <div className="flex justify-end gap-3">
        <Button type="button" variant="outline" onClick={onCancel} disabled={isPending}>
          Cancel
        </Button>
        <Button type="submit" disabled={isPending || !isDirty}>
          {isPending ? 'Saving…' : 'Save Changes'}
        </Button>
      </div>
    </form>
  );
}
