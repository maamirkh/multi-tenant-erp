/**
 * RoleBadge — displays a role name with its rank indicator and
 * a system/custom type indicator.
 *
 * Spec reference: Epic 4, Phase 12 (T107).
 */

import { cn } from '@/lib/utils';

interface RoleBadgeProps {
  name: string;
  rank: number;
  isSystem: boolean;
  className?: string;
}

export function RoleBadge({ name, rank, isSystem, className }: RoleBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium',
        isSystem
          ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400'
          : 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400',
        className
      )}
    >
      <span aria-hidden="true" className="font-mono text-[10px] opacity-70">
        {rank}
      </span>
      {name}
      {isSystem && (
        <span className="ml-0.5 text-[10px] opacity-60" title="System role">
          ●
        </span>
      )}
    </span>
  );
}
