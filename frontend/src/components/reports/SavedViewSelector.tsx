'use client';

/**
 * SavedViewSelector (T233) — list / apply / save-as / rename / update /
 * delete the caller's own private saved views for one report.
 *
 * Applying a view goes through `loadSavedView()` (`GET /saved-views/{id}`),
 * which the backend re-validates against the user's **current** permissions
 * and entitlements — a view saved before access was revoked fails to load
 * with an explanatory message rather than silently running.
 */

import { useId, useState } from 'react';
import { Button } from '@/components/ui/button';
import type { JsonValue, SavedReportView } from '@/lib/api/reports';
import { useSavedViews } from '@/hooks/reports/useSavedViews';
import { errorMessage } from './states';
import { FIELD_CLASS, LABEL_CLASS } from './fieldStyles';

export function SavedViewSelector({
  reportKey,
  currentFilters,
  onApply,
}: {
  reportKey: string;
  currentFilters: Record<string, JsonValue>;
  onApply: (view: SavedReportView) => void;
}): React.JSX.Element {
  const id = useId();
  const { views, create, update, remove, load } = useSavedViews();
  const [selectedId, setSelectedId] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState<string | null>(null);

  const reportViews = (views.data?.items ?? []).filter((v) => v.report_key === reportKey);
  const selected = reportViews.find((v) => v.id === selectedId) ?? null;
  const busy = create.isPending || update.isPending || remove.isPending || load.isPending;

  const guard = async (action: () => Promise<unknown>) => {
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const apply = (viewId: string) =>
    guard(async () => {
      setSelectedId(viewId);
      if (!viewId) return;
      const view = await load.mutateAsync(viewId);
      setName(view.name);
      onApply(view);
    });

  const saveAsNew = () =>
    guard(async () => {
      const view = await create.mutateAsync({
        report_key: reportKey,
        name: name.trim(),
        filter_config: currentFilters,
      });
      setSelectedId(view.id);
    });

  const saveChanges = () =>
    guard(async () => {
      if (!selected) return;
      await update.mutateAsync({
        viewId: selected.id,
        body: { name: name.trim(), filter_config: currentFilters },
      });
    });

  const deleteSelected = () =>
    guard(async () => {
      if (!selected) return;
      await remove.mutateAsync(selected.id);
      setSelectedId('');
      setName('');
    });

  return (
    <section aria-label="Saved views" className="flex flex-wrap items-end gap-2">
      <label className={LABEL_CLASS} htmlFor={`${id}-view`}>
        Saved view
        <select
          id={`${id}-view`}
          className={FIELD_CLASS}
          value={selectedId}
          disabled={busy || views.isLoading}
          onChange={(event) => void apply(event.target.value)}
        >
          <option value="">{views.isLoading ? 'Loading…' : 'None'}</option>
          {reportViews.map((view) => (
            <option key={view.id} value={view.id}>
              {view.name}
            </option>
          ))}
        </select>
      </label>
      <label className={LABEL_CLASS} htmlFor={`${id}-name`}>
        View name
        <input
          id={`${id}-name`}
          className={FIELD_CLASS}
          value={name}
          maxLength={150}
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={busy || name.trim() === ''}
        onClick={() => void saveAsNew()}
      >
        Save as new
      </Button>
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={busy || !selected || name.trim() === ''}
        onClick={() => void saveChanges()}
      >
        Update
      </Button>
      <Button
        type="button"
        size="sm"
        variant="destructive"
        disabled={busy || !selected}
        onClick={() => void deleteSelected()}
      >
        Delete
      </Button>
      {error && (
        <p role="alert" className="w-full text-xs text-destructive">
          {error}
        </p>
      )}
    </section>
  );
}
