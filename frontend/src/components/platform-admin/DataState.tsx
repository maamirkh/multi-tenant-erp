/**
 * Shared loading/empty/error/unavailable state primitives for Platform
 * pages (Phase 15). A failed metric must never render as `0`/empty
 * (FR-9A-003/004) — `Unavailable` is visually and textually distinct
 * from `Empty`.
 */

import { Button } from '@/components/ui/button';
import { ApiClientError } from '@/lib/api/client';

export function messageFromError(err: unknown): string {
  if (err instanceof ApiClientError) return err.error.error.message;
  if (err instanceof Error) return err.message;
  return 'An unexpected error occurred.';
}

export function isForbidden(err: unknown): boolean {
  return err instanceof ApiClientError && err.status === 403;
}

export function isConflict(err: unknown): boolean {
  return err instanceof ApiClientError && err.status === 409;
}

export function LoadingState({ label = 'Loading…' }: { label?: string }): React.JSX.Element {
  return (
    <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
      <div
        className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent"
        role="status"
        aria-label={label}
      />
      {label}
    </div>
  );
}

export function EmptyState({ message }: { message: string }): React.JSX.Element {
  return (
    <div className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
      {message}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}): React.JSX.Element {
  return (
    <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
      <p>{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-2" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

/** Distinct from `ErrorState`/`EmptyState` — data genuinely could not be
 * resolved server-side (FR-9A-003). Never shown as `0` or blank. */
export function UnavailableState({
  message = 'Data unavailable.',
}: {
  message?: string;
}): React.JSX.Element {
  return (
    <div className="rounded-lg border border-amber-300/40 bg-amber-500/10 p-4 text-sm text-amber-700 dark:text-amber-400">
      {message}
    </div>
  );
}

export function PermissionDeniedState({
  message = "You don't have permission to view this.",
}: {
  message?: string;
}): React.JSX.Element {
  return (
    <div role="alert" className="rounded-lg border border-border bg-muted p-6 text-center text-sm text-muted-foreground">
      {message}
    </div>
  );
}

export function PaginationFooter({
  page,
  pages,
  total,
  onPageChange,
}: {
  page: number;
  pages: number;
  total: number;
  onPageChange: (page: number) => void;
}): React.JSX.Element | null {
  if (pages <= 1) return null;
  return (
    <div className="flex items-center justify-between text-sm text-muted-foreground">
      <span>{total} total</span>
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
          aria-label="Previous page"
        >
          Previous
        </Button>
        <span className="flex items-center px-2">
          Page {page} of {pages}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(Math.min(pages, page + 1))}
          disabled={page >= pages}
          aria-label="Next page"
        >
          Next
        </Button>
      </div>
    </div>
  );
}
