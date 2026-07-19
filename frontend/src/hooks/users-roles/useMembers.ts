/**
 * useMembers — React Query hooks for member list, add, update, and status changes.
 *
 * Cache strategy (plan Section 10.2):
 *   - List query key: ['members', companyId, params] — staleTime: 30 seconds
 *   - onSettled: invalidate list + single member caches
 *
 * Spec reference: Epic 4, Phase 11 (T089).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';
import {
  addMember,
  archiveMember,
  deactivateMember,
  listMembers,
  lockMember,
  reactivateMember,
  restoreMember,
  suspendMember,
  updateMember,
} from '@/lib/api/users-roles';
import type {
  AddMemberInput,
  ArchiveMemberInput,
  MemberDetail,
  MemberListItem,
  MemberListParams,
  MemberResponse,
  PaginatedData,
  SuspendMemberInput,
  UpdateMemberInput,
} from '@/types/users-roles';

// ── List query ────────────────────────────────────────────────────────────────

export function useMembers(
  companyId: string | undefined,
  params: MemberListParams = {}
): UseQueryResult<PaginatedData<MemberListItem>> {
  return useQuery<PaginatedData<MemberListItem>>({
    queryKey: ['members', companyId, params],
    queryFn: () => listMembers(companyId!, params),
    enabled: companyId !== undefined && companyId !== '',
    staleTime: 30_000,
  });
}

// ── Add member mutation ───────────────────────────────────────────────────────

export function useAddMember(
  companyId: string
): UseMutationResult<MemberResponse, Error, AddMemberInput> {
  const queryClient = useQueryClient();

  return useMutation<MemberResponse, Error, AddMemberInput>({
    mutationFn: (data) => addMember(companyId, data),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['members', companyId] });
    },
  });
}

// ── Update member mutation ────────────────────────────────────────────────────

export function useUpdateMember(
  companyId: string
): UseMutationResult<MemberDetail, Error, { memberId: string; data: UpdateMemberInput }> {
  const queryClient = useQueryClient();

  return useMutation<MemberDetail, Error, { memberId: string; data: UpdateMemberInput }>({
    mutationFn: ({ memberId, data }) => updateMember(companyId, memberId, data),
    onSettled: (_data, _err, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['member', companyId, variables.memberId] });
      void queryClient.invalidateQueries({ queryKey: ['members', companyId] });
    },
  });
}

// ── Status change mutations ───────────────────────────────────────────────────

export type StatusAction =
  | { type: 'deactivate' }
  | { type: 'suspend'; reason: string }
  | { type: 'lock' }
  | { type: 'reactivate' }
  | { type: 'archive'; reason: string }
  | { type: 'restore' };

export interface ChangeMemberStatusVars {
  memberId: string;
  action: StatusAction;
}

export function useChangeMemberStatus(
  companyId: string
): UseMutationResult<MemberDetail, Error, ChangeMemberStatusVars> {
  const queryClient = useQueryClient();

  return useMutation<MemberDetail, Error, ChangeMemberStatusVars>({
    mutationFn: ({ memberId, action }) => {
      switch (action.type) {
        case 'deactivate':
          return deactivateMember(companyId, memberId);
        case 'suspend':
          return suspendMember(companyId, memberId, { reason: action.reason } satisfies SuspendMemberInput);
        case 'lock':
          return lockMember(companyId, memberId);
        case 'reactivate':
          return reactivateMember(companyId, memberId);
        case 'archive':
          return archiveMember(companyId, memberId, { reason: action.reason } satisfies ArchiveMemberInput);
        case 'restore':
          return restoreMember(companyId, memberId);
      }
    },
    onSettled: (_data, _err, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['member', companyId, variables.memberId] });
      void queryClient.invalidateQueries({ queryKey: ['members', companyId] });
    },
  });
}
