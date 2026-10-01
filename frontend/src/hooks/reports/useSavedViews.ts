/**
 * useSavedViews (T221) — the caller's own private saved views plus the
 * create / update / delete / load mutations. Every mutation invalidates the
 * tenant-scoped list key, so the selector never shows a stale list.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import {
  createSavedView,
  deleteSavedView,
  listSavedViews,
  loadSavedView,
  updateSavedView,
  type SavedReportView,
  type SavedReportViewCreate,
  type SavedReportViewUpdate,
} from '@/lib/api/reports';
import type { PaginatedData } from '@/lib/api/types';
import { reportsKeys } from './queryKeys';
import { useActiveCompanyId } from './useActiveCompanyId';

export interface UseSavedViewsResult {
  views: UseQueryResult<PaginatedData<SavedReportView>>;
  create: UseMutationResult<SavedReportView, Error, SavedReportViewCreate>;
  update: UseMutationResult<
    SavedReportView,
    Error,
    { viewId: string; body: SavedReportViewUpdate }
  >;
  remove: UseMutationResult<void, Error, string>;
  /** Re-validated server-side against the caller's current access (T140). */
  load: UseMutationResult<SavedReportView, Error, string>;
}

export function useSavedViews(): UseSavedViewsResult {
  const companyId = useActiveCompanyId();
  const queryClient = useQueryClient();
  const listKey = reportsKeys.savedViews(companyId);
  const invalidate = () => queryClient.invalidateQueries({ queryKey: listKey });

  const views = useQuery<PaginatedData<SavedReportView>>({
    queryKey: listKey,
    queryFn: async () => (await listSavedViews(companyId, 1, 100)).data,
    enabled: companyId !== '',
  });

  const create = useMutation<SavedReportView, Error, SavedReportViewCreate>({
    mutationFn: async (body) => (await createSavedView(companyId, body)).data,
    onSuccess: invalidate,
  });

  const update = useMutation<
    SavedReportView,
    Error,
    { viewId: string; body: SavedReportViewUpdate }
  >({
    mutationFn: async ({ viewId, body }) =>
      (await updateSavedView(companyId, viewId, body)).data,
    onSuccess: invalidate,
  });

  const remove = useMutation<void, Error, string>({
    mutationFn: async (viewId) => {
      await deleteSavedView(companyId, viewId);
    },
    onSuccess: invalidate,
  });

  const load = useMutation<SavedReportView, Error, string>({
    mutationFn: async (viewId) => (await loadSavedView(companyId, viewId)).data,
  });

  return { views, create, update, remove, load };
}
