/**
 * Shared frame for the five Reports availability states (T234, plan.md
 * §26). Every state is announced with an icon **and** a text heading — a
 * state is never communicated by color alone (FR-RPT-331).
 */

import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface StateFrameProps {
  icon: ReactNode;
  title: string;
  message?: string;
  role?: 'status' | 'alert';
  tone?: 'neutral' | 'warning' | 'danger';
  action?: ReactNode;
  testId?: string;
}

const TONE_CLASSES: Record<NonNullable<StateFrameProps['tone']>, string> = {
  neutral: 'border-border',
  warning: 'border-amber-300 dark:border-amber-700',
  danger: 'border-destructive/40',
};

export function StateFrame({
  icon,
  title,
  message,
  role = 'status',
  tone = 'neutral',
  action,
  testId,
}: StateFrameProps): React.JSX.Element {
  return (
    <div
      role={role}
      data-testid={testId}
      className={cn(
        'flex flex-col items-center gap-2 rounded-lg border border-dashed p-6 text-center',
        TONE_CLASSES[tone]
      )}
    >
      <span className="text-muted-foreground" aria-hidden="true">
        {icon}
      </span>
      <p className="text-sm font-medium text-foreground">{title}</p>
      {message && <p className="max-w-prose text-sm text-muted-foreground">{message}</p>}
      {action}
    </div>
  );
}
