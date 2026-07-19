'use client';

/**
 * RequireRank — renders children only when the current user's role rank
 * meets or exceeds the required threshold.
 *
 * Returns null (nothing rendered) when:
 *   - Member data is still loading
 *   - Current user's rank is below the required minimum
 *
 * Used for Admin-only UI sections (rank >= 80), Owner-only actions
 * (rank >= 100), etc.
 *
 * Spec reference: Epic 4, Phase 11 (T092).
 */

import type { ReactNode } from 'react';
import { useCompanyMemberContext } from '@/components/users-roles/CompanyMemberProvider';

interface RequireRankProps {
  /** Minimum rank required to see the children. */
  minRank: number;
  children: ReactNode;
  /** Optional fallback rendered when rank is insufficient (default: null). */
  fallback?: ReactNode;
}

export function RequireRank({ minRank, children, fallback = null }: RequireRankProps) {
  const { currentMemberRank, isLoading } = useCompanyMemberContext();

  if (isLoading) return null;
  if (currentMemberRank < minRank) return <>{fallback}</>;

  return <>{children}</>;
}
