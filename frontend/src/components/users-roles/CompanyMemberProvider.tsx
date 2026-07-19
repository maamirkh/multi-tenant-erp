'use client';

/**
 * CompanyMemberProvider — extends CompanyContext with the current user's
 * membership data (role, rank, status) within the active company.
 *
 * Fetches the current user's member record by searching the member list
 * with their email, then stores role, rank, and status for rank-based
 * UI visibility decisions (RequireRank, notes hiding, action availability).
 *
 * Spec reference: Epic 4, Phase 11 (T091).
 */

import React, {
  createContext,
  useContext,
  useMemo,
} from 'react';
import { useAuthContext } from '@/contexts/AuthContext';
import { useMembers } from '@/hooks/users-roles/useMembers';
import type { MemberListItem, MemberListParams, MembershipStatus } from '@/types/users-roles';

export interface CompanyMemberContextValue {
  /** Current user's membership record in this company, or null if not found. */
  currentMember: MemberListItem | null;
  /** Current user's role rank in this company. 0 when not loaded. */
  currentMemberRank: number;
  /** Current user's membership status, or null when not loaded. */
  currentMemberStatus: MembershipStatus | null;
  /** True while member data is loading. */
  isLoading: boolean;
}

const CompanyMemberContext = createContext<CompanyMemberContextValue | null>(null);

interface CompanyMemberProviderProps {
  companyId: string;
  children: React.ReactNode;
}

export function CompanyMemberProvider({
  companyId,
  children,
}: CompanyMemberProviderProps): React.JSX.Element {
  const { user } = useAuthContext();

  // Search by the current user's email to locate their member record.
  const memberParams: MemberListParams = { page_size: 10 };
  if (user?.email) memberParams.search = user.email;
  const { data: membersPage, isLoading } = useMembers(companyId, memberParams);

  const currentMember = useMemo<MemberListItem | null>(() => {
    if (!user || !membersPage?.items) return null;
    return membersPage.items.find((m) => m.user_id === user.user_id) ?? null;
  }, [user, membersPage]);

  const value = useMemo<CompanyMemberContextValue>(
    () => ({
      currentMember,
      currentMemberRank: currentMember?.role.rank ?? 0,
      currentMemberStatus: currentMember?.status ?? null,
      isLoading,
    }),
    [currentMember, isLoading]
  );

  return (
    <CompanyMemberContext.Provider value={value}>
      {children}
    </CompanyMemberContext.Provider>
  );
}

export function useCompanyMemberContext(): CompanyMemberContextValue {
  const ctx = useContext(CompanyMemberContext);
  if (!ctx) {
    throw new Error(
      'useCompanyMemberContext must be used inside <CompanyMemberProvider>'
    );
  }
  return ctx;
}
