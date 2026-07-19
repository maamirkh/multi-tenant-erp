/**
 * T076 — Color-coded badge for CompanyStatus values.
 *
 * Spec ref: Epic 3, Phase 11 (T076).
 */

import { cn } from '@/lib/utils';
import type { CompanyStatus } from '@/types/companies';

const STATUS_CONFIG: Record<CompanyStatus, { label: string; className: string }> = {
  pending_setup: {
    label: 'Pending Setup',
    className: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
  },
  active: {
    label: 'Active',
    className: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
  },
  inactive: {
    label: 'Inactive',
    className: 'bg-gray-100 text-gray-600 dark:bg-gray-800/50 dark:text-gray-400',
  },
  suspended: {
    label: 'Suspended',
    className: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
  },
  deleted: {
    label: 'Deleted',
    className: 'bg-gray-200 text-gray-500 dark:bg-gray-700/50 dark:text-gray-500',
  },
};

interface CompanyStatusBadgeProps {
  status: CompanyStatus;
  className?: string;
}

export function CompanyStatusBadge({ status, className }: CompanyStatusBadgeProps) {
  const config = STATUS_CONFIG[status];

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
        config.className,
        className
      )}
      aria-label={`Status: ${config.label}`}
    >
      {config.label}
    </span>
  );
}
