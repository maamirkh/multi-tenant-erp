/**
 * usePreferences — React Query hooks for current user's preferences.
 *
 * Hooks:
 *   usePreferences()          — GET /api/v1/preferences, staleTime: 5 min
 *   useUpdatePreferences()    — PUT /api/v1/preferences, invalidates ['preferences']
 *
 * Spec reference: Epic 4, Phase 13 (T116).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';
import { getPreferences, updatePreferences } from '@/lib/api/users-roles';
import type { UpdatePreferencesInput, UserPreferences } from '@/types/users-roles';

const PREFERENCES_KEY = ['preferences'] as const;

// ── Preferences query ─────────────────────────────────────────────────────────

export function usePreferences(): UseQueryResult<UserPreferences> {
  return useQuery<UserPreferences>({
    queryKey: PREFERENCES_KEY,
    queryFn: getPreferences,
    staleTime: 5 * 60_000,
  });
}

// ── Update preferences mutation ───────────────────────────────────────────────

export function useUpdatePreferences(): UseMutationResult<
  UserPreferences,
  Error,
  UpdatePreferencesInput
> {
  const queryClient = useQueryClient();

  return useMutation<UserPreferences, Error, UpdatePreferencesInput>({
    mutationFn: updatePreferences,
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: PREFERENCES_KEY });
    },
  });
}
