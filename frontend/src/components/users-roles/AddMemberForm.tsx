'use client';

/**
 * AddMemberForm — form for inviting a new member to the company.
 *
 * Fields: email (required), role (required), plus optional employee info
 * (job_title, department, employee_id, work_phone, hire_date, notes).
 *
 * Validation: AddMemberSchema (Zod) via react-hook-form.
 * Mutation: useAddMember — navigates to member list on success.
 *
 * Spec reference: Epic 4, Phase 11 (T095).
 */

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAddMember } from '@/hooks/users-roles/useMembers';
import { useRoles } from '@/hooks/users-roles/useRoles';
import { AddMemberSchema } from '@/schemas/users-roles';
import type { AddMemberFormData } from '@/schemas/users-roles';
import type { AddMemberInput } from '@/types/users-roles';
import { ApiClientError } from '@/lib/api/client';

interface AddMemberFormProps {
  companyId: string;
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

export function AddMemberForm({ companyId, onSuccess, onCancel }: AddMemberFormProps) {
  const { data: roles, isLoading: rolesLoading } = useRoles(companyId);
  const addMember = useAddMember(companyId);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<AddMemberFormData>({
    resolver: zodResolver(AddMemberSchema),
    defaultValues: {
      email: '',
      role_id: '',
    },
  });

  async function onSubmit(formData: AddMemberFormData) {
    const input: AddMemberInput = {
      email: formData.email,
      role_id: formData.role_id,
      ...(formData.employee_id && { employee_id: formData.employee_id }),
      ...(formData.job_title && { job_title: formData.job_title }),
      ...(formData.department && { department: formData.department }),
      ...(formData.work_phone && { work_phone: formData.work_phone }),
      ...(formData.hire_date && { hire_date: formData.hire_date }),
      ...(formData.notes && { notes: formData.notes }),
    };

    addMember.mutate(input, {
      onSuccess: () => onSuccess(),
      onError: (err) => {
        if (err instanceof ApiClientError && err.status === 409) {
          setError('email', { message: 'This user is already a member of the company' });
        } else if (err instanceof ApiClientError && err.status === 422) {
          setError('root', { message: err.error.error.message });
        } else {
          setError('root', { message: err.message ?? 'An error occurred' });
        }
      },
    });
  }

  const isPending = isSubmitting || addMember.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-5">
      {/* Root error */}
      {errors.root && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
        >
          {errors.root.message}
        </div>
      )}

      {/* Email */}
      <div>
        <label htmlFor="email" className="block text-sm font-medium text-foreground mb-1">
          Email <span aria-hidden="true" className="text-destructive">*</span>
        </label>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          placeholder="member@example.com"
          aria-invalid={!!errors.email}
          aria-describedby={errors.email ? 'email-error' : undefined}
          {...register('email')}
        />
        <FieldError message={errors.email?.message} />
      </div>

      {/* Role */}
      <div>
        <label htmlFor="role_id" className="block text-sm font-medium text-foreground mb-1">
          Role <span aria-hidden="true" className="text-destructive">*</span>
        </label>
        <select
          id="role_id"
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
          aria-invalid={!!errors.role_id}
          disabled={rolesLoading}
          {...register('role_id')}
        >
          <option value="">Select a role…</option>
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

      {/* Optional employee info */}
      <fieldset className="border border-border rounded-lg p-4 space-y-4">
        <legend className="text-sm font-medium text-muted-foreground px-1">
          Employee Information (optional)
        </legend>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="job_title" className="block text-sm font-medium text-foreground mb-1">
              Job Title
            </label>
            <Input
              id="job_title"
              type="text"
              placeholder="e.g. Senior Engineer"
              aria-invalid={!!errors.job_title}
              {...register('job_title')}
            />
            <FieldError message={errors.job_title?.message} />
          </div>

          <div>
            <label htmlFor="department" className="block text-sm font-medium text-foreground mb-1">
              Department
            </label>
            <Input
              id="department"
              type="text"
              placeholder="e.g. Engineering"
              aria-invalid={!!errors.department}
              {...register('department')}
            />
            <FieldError message={errors.department?.message} />
          </div>

          <div>
            <label htmlFor="employee_id" className="block text-sm font-medium text-foreground mb-1">
              Employee ID
            </label>
            <Input
              id="employee_id"
              type="text"
              placeholder="e.g. EMP-001"
              aria-invalid={!!errors.employee_id}
              {...register('employee_id')}
            />
            <FieldError message={errors.employee_id?.message} />
          </div>

          <div>
            <label htmlFor="work_phone" className="block text-sm font-medium text-foreground mb-1">
              Work Phone
            </label>
            <Input
              id="work_phone"
              type="tel"
              placeholder="e.g. +1 555 000 0000"
              aria-invalid={!!errors.work_phone}
              {...register('work_phone')}
            />
            <FieldError message={errors.work_phone?.message} />
          </div>

          <div>
            <label htmlFor="hire_date" className="block text-sm font-medium text-foreground mb-1">
              Hire Date
            </label>
            <Input
              id="hire_date"
              type="date"
              aria-invalid={!!errors.hire_date}
              {...register('hire_date')}
            />
            <FieldError message={errors.hire_date?.message} />
          </div>
        </div>

        <div>
          <label htmlFor="notes" className="block text-sm font-medium text-foreground mb-1">
            Notes
          </label>
          <textarea
            id="notes"
            rows={3}
            placeholder="Internal notes (visible to admins only)"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring resize-none"
            aria-invalid={!!errors.notes}
            {...register('notes')}
          />
          <FieldError message={errors.notes?.message} />
        </div>
      </fieldset>

      {/* Actions */}
      <div className="flex justify-end gap-3">
        <Button type="button" variant="outline" onClick={onCancel} disabled={isPending}>
          Cancel
        </Button>
        <Button type="submit" disabled={isPending}>
          {isPending ? 'Adding…' : 'Add Member'}
        </Button>
      </div>
    </form>
  );
}
