/**
 * T090 — CompanyLogoUpload.
 *
 * Drag-and-drop logo upload component.
 * Client-side validates: file type (PNG/JPG/SVG/WebP), size < 5MB.
 * Calls useUploadLogo() on submit. Shows preview on selection and after
 * successful upload. Shows pending state and error messages.
 *
 * Spec ref: Epic 3, Phase 12 (T090).
 */

'use client';

import { useRef, useState } from 'react';
import { useUploadLogo } from '@/hooks/companies/useUploadLogo';
import { Button } from '@/components/ui/button';

// ── Constants ─────────────────────────────────────────────────────────────────

const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/svg+xml', 'image/webp'];
const MAX_BYTES = 5 * 1024 * 1024; // 5 MB

// ── Component ─────────────────────────────────────────────────────────────────

interface CompanyLogoUploadProps {
  companyId: string;
  currentLogoUrl?: string | null;
}

export function CompanyLogoUpload({ companyId, currentLogoUrl }: CompanyLogoUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(currentLogoUrl ?? null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const uploadLogo = useUploadLogo();

  function validateAndStage(file: File): void {
    setClientError(null);

    if (!ALLOWED_TYPES.includes(file.type)) {
      setClientError('File must be PNG, JPG, SVG, or WebP.');
      return;
    }

    if (file.size > MAX_BYTES) {
      setClientError('File must be smaller than 5 MB.');
      return;
    }

    setSelectedFile(file);
    const objectUrl = URL.createObjectURL(file);
    setPreviewUrl(objectUrl);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>): void {
    const file = e.target.files?.[0];
    if (file) validateAndStage(file);
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>): void {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) validateAndStage(file);
  }

  function handleDragOver(e: React.DragEvent<HTMLDivElement>): void {
    e.preventDefault();
    setIsDragging(true);
  }

  function handleDragLeave(): void {
    setIsDragging(false);
  }

  function handleUpload(): void {
    if (!selectedFile) return;

    uploadLogo.mutate(
      { id: companyId, file: selectedFile },
      {
        onSuccess: (result) => {
          setPreviewUrl(result.logo_url);
          setSelectedFile(null);
          if (inputRef.current) inputRef.current.value = '';
        },
      }
    );
  }

  const errorMessage = clientError ?? (uploadLogo.isError ? (uploadLogo.error?.message ?? 'Upload failed.') : null);

  return (
    <div className="space-y-3">
      {/* Preview */}
      {previewUrl && (
        <div className="flex items-center gap-4">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={previewUrl}
            alt="Company logo preview"
            className="h-20 w-20 rounded-lg border border-border object-contain bg-muted"
          />
          <p className="text-xs text-muted-foreground">
            {selectedFile ? 'Preview — not yet saved' : 'Current logo'}
          </p>
        </div>
      )}

      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload logo — click or drag and drop"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click(); }}
        className={[
          'flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-sm transition-colors',
          isDragging
            ? 'border-primary bg-primary/5 text-primary'
            : 'border-border text-muted-foreground hover:border-primary/50 hover:bg-muted/50',
        ].join(' ')}
      >
        <span className="font-medium">Click or drag to upload logo</span>
        <span className="mt-1 text-xs">PNG, JPG, SVG, WebP — max 5 MB</span>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/svg+xml,image/webp"
        className="sr-only"
        onChange={handleFileChange}
        aria-label="Logo file input"
      />

      {/* Error */}
      {errorMessage && (
        <p role="alert" className="text-xs text-destructive">{errorMessage}</p>
      )}

      {/* Upload button — only shown when a file is staged */}
      {selectedFile && !clientError && (
        <Button
          type="button"
          onClick={handleUpload}
          disabled={uploadLogo.isPending}
          size="sm"
        >
          {uploadLogo.isPending ? 'Uploading…' : 'Upload Logo'}
        </Button>
      )}

      {uploadLogo.isSuccess && !selectedFile && (
        <p role="status" className="text-xs text-green-700 dark:text-green-400">
          Logo updated successfully.
        </p>
      )}
    </div>
  );
}
