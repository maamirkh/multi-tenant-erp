/**
 * The five Reports availability states (T234) plus the one mapping from a
 * backend error code to the state that should render. Every Reports page
 * uses `ReportErrorState` so a 403/409 is never rendered as a generic
 * failure or, worse, as empty data.
 */

import { ApiClientError } from '@/lib/api/client';
import { EmptyState } from './EmptyState';
import { ErrorState } from './ErrorState';
import { ModuleDisabledState } from './ModuleDisabledState';
import { PermissionDeniedState } from './PermissionDeniedState';
import { UnavailableState } from './UnavailableState';

export { EmptyState, ErrorState, ModuleDisabledState, PermissionDeniedState, UnavailableState };

export type ReportErrorKind = 'permission_denied' | 'module_disabled' | 'unavailable' | 'error';

export function classifyReportError(error: unknown): ReportErrorKind {
  if (error instanceof ApiClientError) {
    switch (error.error.error?.code) {
      case 'REPORT_PERMISSION_DENIED':
        return 'permission_denied';
      case 'REPORT_NOT_ENTITLED':
        return 'module_disabled';
      case 'REPORT_UNAVAILABLE':
        return 'unavailable';
    }
    if (error.status === 403) return 'permission_denied';
  }
  return 'error';
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiClientError) return error.error.error?.message ?? error.message;
  if (error instanceof Error) return error.message;
  return 'An unexpected error occurred.';
}

export function ReportErrorState({
  error,
  onRetry,
}: {
  error: unknown;
  onRetry?: (() => void) | undefined;
}): React.JSX.Element {
  switch (classifyReportError(error)) {
    case 'permission_denied':
      return <PermissionDeniedState />;
    case 'module_disabled':
      return <ModuleDisabledState />;
    case 'unavailable':
      return <UnavailableState />;
    default:
      return <ErrorState message={errorMessage(error)} onRetry={onRetry} />;
  }
}
