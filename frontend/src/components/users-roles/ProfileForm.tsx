'use client';

/**
 * ProfileForm — edit display name and phone; upload/delete avatar.
 *
 * Uses React Hook Form + Zod (UpdateProfileSchema) for field validation.
 * Avatar mutations (upload/delete) fire immediately on user action
 * and invalidate the profile cache via useUploadAvatar / useDeleteAvatar.
 *
 * Props:
 *   profile:    current UserProfile data used to pre-fill defaults.
 *   onSuccess:  called after a successful PATCH /profile submission.
 *
 * Spec reference: Epic 4, Phase 13 (T118).
 */

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { AvatarUpload } from '@/components/users-roles/AvatarUpload';
import { useUpdateProfile, useUploadAvatar, useDeleteAvatar } from '@/hooks/users-roles/useProfile';
import { UpdateProfileSchema } from '@/schemas/users-roles';
import type { UpdateProfileFormData } from '@/schemas/users-roles';
import { ApiClientError } from '@/lib/api/client';
import type { UserProfile } from '@/types/users-roles';

interface ProfileFormProps {
  profile: UserProfile;
  onSuccess: () => void;
}

function FieldError({ message }: { message: string | undefined }) {
  if (!message) return null;
  return (
    <p className="text-xs text-destructive mt-1" role="alert">
      {message}
    </p>
  );
}

export function ProfileForm({ profile, onSuccess }: ProfileFormProps) {
  const [serverError, setServerError] = useState<string | undefined>(undefined);
  const [avatarError, setAvatarError] = useState<string | undefined>(undefined);
  const [successMessage, setSuccessMessage] = useState<string | undefined>(undefined);

  const updateProfile = useUpdateProfile();
  const uploadAvatar = useUploadAvatar();
  const deleteAvatar = useDeleteAvatar();

  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<UpdateProfileFormData>({
    resolver: zodResolver(UpdateProfileSchema),
    defaultValues: {
      display_name: profile.display_name,
      phone: profile.phone ?? '',
    },
  });

  function handleSubmitForm(data: UpdateProfileFormData) {
    setServerError(undefined);
    setSuccessMessage(undefined);

    const payload: Parameters<typeof updateProfile.mutate>[0] = {};
    if (data.display_name !== undefined && data.display_name !== '') {
      payload.display_name = data.display_name;
    }
    // phone: empty string → null (clear); string → value; undefined → omit
    if (data.phone === '' || data.phone === null) {
      payload.phone = null;
    } else if (data.phone !== undefined) {
      payload.phone = data.phone;
    }

    updateProfile.mutate(payload, {
      onSuccess: () => {
        setSuccessMessage('Profile updated successfully.');
        onSuccess();
      },
      onError: (err) => {
        if (err instanceof ApiClientError) {
          setServerError(err.error.error.message);
        } else {
          setServerError(err.message ?? 'Failed to update profile');
        }
      },
    });
  }

  function handleUpload(file: File) {
    setAvatarError(undefined);
    uploadAvatar.mutate(file, {
      onError: (err) => {
        if (err instanceof ApiClientError) {
          setAvatarError(err.error.error.message);
        } else {
          setAvatarError(err.message ?? 'Failed to upload avatar');
        }
      },
    });
  }

  function handleDeleteAvatar() {
    setAvatarError(undefined);
    deleteAvatar.mutate(undefined, {
      onError: (err) => {
        if (err instanceof ApiClientError) {
          setAvatarError(err.error.error.message);
        } else {
          setAvatarError(err.message ?? 'Failed to remove avatar');
        }
      },
    });
  }

  const isFormPending = updateProfile.isPending;

  return (
    <form onSubmit={handleSubmit(handleSubmitForm)} noValidate className="space-y-6">
      {/* Server error */}
      {serverError && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
        >
          {serverError}
        </div>
      )}

      {/* Success message */}
      {successMessage && (
        <div
          role="status"
          className="rounded-lg border border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950/30 p-3 text-sm text-green-700 dark:text-green-400"
        >
          {successMessage}
        </div>
      )}

      {/* Avatar */}
      <div className="flex justify-center">
        <AvatarUpload
          avatarUrl={profile.avatar_url}
          displayName={profile.display_name}
          onUpload={handleUpload}
          onDelete={handleDeleteAvatar}
          isUploading={uploadAvatar.isPending}
          isDeleting={deleteAvatar.isPending}
          error={avatarError}
        />
      </div>

      {/* Display name */}
      <div>
        <label htmlFor="display_name" className="block text-sm font-medium text-foreground mb-1">
          Display Name
        </label>
        <Input
          id="display_name"
          type="text"
          placeholder="Your display name"
          aria-invalid={!!errors.display_name}
          {...register('display_name')}
        />
        <FieldError message={errors.display_name?.message} />
      </div>

      {/* Phone */}
      <div>
        <label htmlFor="phone" className="block text-sm font-medium text-foreground mb-1">
          Phone
        </label>
        <Input
          id="phone"
          type="tel"
          placeholder="+1 555 000 0000"
          aria-invalid={!!errors.phone}
          {...register('phone')}
        />
        <p className="text-xs text-muted-foreground mt-1">
          Leave empty to clear your phone number.
        </p>
        <FieldError message={errors.phone?.message} />
      </div>

      {/* Email (read-only) */}
      <div>
        <label htmlFor="email" className="block text-sm font-medium text-foreground mb-1">
          Email
        </label>
        <Input
          id="email"
          type="email"
          value={profile.email}
          disabled
          className="disabled:opacity-60"
        />
        <p className="text-xs text-muted-foreground mt-1">
          Email cannot be changed here.
        </p>
      </div>

      {/* Actions */}
      <div className="flex justify-end pt-2">
        <Button type="submit" disabled={isFormPending || !isDirty}>
          {isFormPending ? 'Saving…' : 'Save Changes'}
        </Button>
      </div>
    </form>
  );
}
