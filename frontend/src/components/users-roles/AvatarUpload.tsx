'use client';

/**
 * AvatarUpload — avatar display with file upload and delete.
 *
 * - Shows current avatar image or initials placeholder when no avatar set.
 * - File input accepts JPEG, PNG, WebP only; validates ≤2 MiB client-side
 *   before calling onUpload.
 * - Upload triggered by clicking the avatar or the file input button.
 * - Delete button shown only when an avatar URL exists.
 *
 * Props:
 *   avatarUrl:   current avatar URL (null for no avatar).
 *   displayName: used to derive initials for the placeholder.
 *   onUpload:    called with the validated File.
 *   onDelete:    called when user confirms avatar removal.
 *   isUploading: disables controls while upload is in progress.
 *   isDeleting:  disables controls while delete is in progress.
 *   error:       error message to display below the avatar.
 *
 * Spec reference: Epic 4, Phase 13 (T117).
 */

import { useRef, useState } from 'react';
import { Button } from '@/components/ui/button';

const MAX_BYTES = 2 * 1024 * 1024; // 2 MiB
const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

function getInitials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('');
}

interface AvatarUploadProps {
  avatarUrl: string | null;
  displayName: string;
  onUpload: (file: File) => void;
  onDelete: () => void;
  isUploading: boolean;
  isDeleting: boolean;
  error: string | undefined;
}

export function AvatarUpload({
  avatarUrl,
  displayName,
  onUpload,
  onDelete,
  isUploading,
  isDeleting,
  error,
}: AvatarUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [validationError, setValidationError] = useState<string | undefined>(undefined);

  const isPending = isUploading || isDeleting;

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setValidationError(undefined);

    if (!ACCEPTED_TYPES.includes(file.type)) {
      setValidationError('Only JPEG, PNG, and WebP images are accepted.');
      e.target.value = '';
      return;
    }

    if (file.size > MAX_BYTES) {
      setValidationError('Image must be 2 MB or smaller.');
      e.target.value = '';
      return;
    }

    onUpload(file);
    e.target.value = '';
  }

  const displayError = validationError ?? error;

  return (
    <div className="flex flex-col items-center gap-3">
      {/* Avatar display */}
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={isPending}
        className="relative size-24 rounded-full overflow-hidden border-2 border-border focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:opacity-60 group"
        aria-label={avatarUrl ? 'Change avatar' : 'Upload avatar'}
        title={avatarUrl ? 'Click to change avatar' : 'Click to upload avatar'}
      >
        {avatarUrl ? (
          <img
            src={avatarUrl}
            alt={`${displayName} avatar`}
            className="size-full object-cover"
          />
        ) : (
          <span className="flex size-full items-center justify-center bg-primary/10 text-primary text-2xl font-semibold">
            {getInitials(displayName) || '?'}
          </span>
        )}
        {/* Upload overlay */}
        <span className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity text-white text-xs font-medium">
          {isUploading ? 'Uploading…' : 'Change'}
        </span>
      </button>

      {/* Hidden file input */}
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="sr-only"
        onChange={handleFileChange}
        disabled={isPending}
        aria-label="Upload avatar file"
      />

      {/* Action buttons */}
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => inputRef.current?.click()}
          disabled={isPending}
        >
          {isUploading ? 'Uploading…' : 'Upload Photo'}
        </Button>
        {avatarUrl && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onDelete}
            disabled={isPending}
            className="text-destructive hover:text-destructive"
          >
            {isDeleting ? 'Removing…' : 'Remove'}
          </Button>
        )}
      </div>

      {/* Validation / server error */}
      {displayError && (
        <p className="text-xs text-destructive" role="alert">
          {displayError}
        </p>
      )}

      <p className="text-xs text-muted-foreground">
        JPEG, PNG, or WebP · max 2 MB
      </p>
    </div>
  );
}
