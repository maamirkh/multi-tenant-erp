/**
 * MemberStatusBadge — color-coded pill badge for MembershipStatus values.
 *
 * Color scheme:
 *   active         → green
 *   inactive       → gray
 *   suspended      → orange
 *   locked         → red
 *   pending_invitation → blue
 *   archived       → gray strikethrough
 *
 * Spec reference: Epic 4, Phase 11 (T093).
 */

import { cn } from '@/lib/utils';
import type { MembershipStatus } from '@/types/users-roles';

const STATUS_CONFIG: Record<
  MembershipStatus,
  { label: string; className: string }
> = {
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
    className: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  },
  locked: {
    label: 'Locked',
    className: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
  },
  pending_invitation: {
    label: 'Pending',
    className: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  },
  archived: {
    label: 'Archived',
    className:
      'bg-gray-200 text-gray-500 line-through dark:bg-gray-700/50 dark:text-gray-500',
  },
};

interface MemberStatusBadgeProps {
  status: MembershipStatus;
  className?: string;
}

export function MemberStatusBadge({ status, className }: MemberStatusBadgeProps) {
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
