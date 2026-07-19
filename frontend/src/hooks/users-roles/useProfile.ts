/**
 * useProfile — React Query hooks for the current user's profile.
 *
 * Hooks:
 *   useProfile()         — GET /api/v1/profile, staleTime: 60s
 *   useUpdateProfile()   — PATCH /api/v1/profile, invalidates ['profile']
 *   useUploadAvatar()    — POST /api/v1/profile/avatar (multipart), invalidates ['profile']
 *   useDeleteAvatar()    — DELETE /api/v1/profile/avatar, invalidates ['profile']
 *
 * Spec reference: Epic 4, Phase 13 (T115).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';
import {
  deleteAvatar,
  getProfile,
  updateProfile,
  uploadAvatar,
} from '@/lib/api/users-roles';
import type { AvatarUploadResult, UpdateProfileInput, UserProfile } from '@/types/users-roles';

const PROFILE_KEY = ['profile'] as const;

// ── Profile query ─────────────────────────────────────────────────────────────

export function useProfile(): UseQueryResult<UserProfile> {
  return useQuery<UserProfile>({
    queryKey: PROFILE_KEY,
    queryFn: getProfile,
    staleTime: 60_000,
  });
}

// ── Update profile mutation ───────────────────────────────────────────────────

export function useUpdateProfile(): UseMutationResult<UserProfile, Error, UpdateProfileInput> {
  const queryClient = useQueryClient();

  return useMutation<UserProfile, Error, UpdateProfileInput>({
    mutationFn: updateProfile,
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: PROFILE_KEY });
    },
  });
}

// ── Upload avatar mutation ────────────────────────────────────────────────────

export function useUploadAvatar(): UseMutationResult<AvatarUploadResult, Error, File> {
  const queryClient = useQueryClient();

  return useMutation<AvatarUploadResult, Error, File>({
    mutationFn: uploadAvatar,
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: PROFILE_KEY });
    },
  });
}

// ── Delete avatar mutation ────────────────────────────────────────────────────

export function useDeleteAvatar(): UseMutationResult<void, Error, void> {
  const queryClient = useQueryClient();

  return useMutation<void, Error, void>({
    mutationFn: deleteAvatar,
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: PROFILE_KEY });
    },
  });
}
