'use client';

/**
 * RolePermissionChecklist — permission selector grouped by module.
 *
 * Controlled component: receives `value` (selected permission codes) and
 * `onChange` to update selections. Disabled when `readOnly` is true
 * (used for system roles and the EditRolePage read-only view).
 *
 * Loads permissions from usePermissions() (global catalogue, 30 min stale).
 *
 * Spec reference: Epic 4, Phase 12 (T108).
 */

import { usePermissions } from '@/hooks/users-roles/usePermissions';

interface RolePermissionChecklistProps {
  /** Selected permission codes (controlled). */
  value: string[];
  onChange: (codes: string[]) => void;
  /** When true, all checkboxes are disabled. */
  readOnly?: boolean;
}

export function RolePermissionChecklist({
  value,
  onChange,
  readOnly = false,
}: RolePermissionChecklistProps) {
  const { data: groups, isLoading } = usePermissions();

  function handleToggle(code: string, checked: boolean) {
    if (readOnly) return;
    if (checked) {
      onChange([...value, code]);
    } else {
      onChange(value.filter((c) => c !== code));
    }
  }

  function handleToggleModule(moduleCodes: string[], checked: boolean) {
    if (readOnly) return;
    if (checked) {
      const next = new Set([...value, ...moduleCodes]);
      onChange(Array.from(next));
    } else {
      const removeSet = new Set(moduleCodes);
      onChange(value.filter((c) => !removeSet.has(c)));
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-2" aria-busy="true" aria-label="Loading permissions">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-20 animate-pulse rounded bg-muted" />
        ))}
      </div>
    );
  }

  if (!groups || groups.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No permissions available.</p>
    );
  }

  return (
    <div className="space-y-4">
      {groups.map((group) => {
        const moduleCodes = group.permissions.map((p) => p.code);
        const allSelected = moduleCodes.every((c) => value.includes(c));
        const someSelected = moduleCodes.some((c) => value.includes(c));

        return (
          <fieldset
            key={group.module}
            className="rounded-lg border border-border p-3"
          >
            {/* Module header with select-all */}
            <div className="flex items-center gap-2 mb-2">
              <input
                id={`module-${group.module}`}
                type="checkbox"
                checked={allSelected}
                ref={(el) => {
                  if (el) el.indeterminate = someSelected && !allSelected;
                }}
                onChange={(e) => handleToggleModule(moduleCodes, e.target.checked)}
                disabled={readOnly}
                className="h-4 w-4 rounded border-border text-primary"
                aria-label={`Select all ${group.module} permissions`}
              />
              <legend
                className="text-sm font-semibold text-foreground capitalize cursor-pointer select-none"
                onClick={() => handleToggleModule(moduleCodes, !allSelected)}
              >
                {group.module}
              </legend>
            </div>

            {/* Individual permissions */}
            <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2 ml-6">
              {group.permissions.map((perm) => (
                <label
                  key={perm.code}
                  className="flex items-start gap-2 cursor-pointer select-none"
                >
                  <input
                    type="checkbox"
                    checked={value.includes(perm.code)}
                    onChange={(e) => handleToggle(perm.code, e.target.checked)}
                    disabled={readOnly}
                    className="mt-0.5 h-4 w-4 rounded border-border text-primary flex-shrink-0"
                    aria-label={perm.label}
                  />
                  <span className="text-sm">
                    <span className="font-medium text-foreground">{perm.label}</span>
                    {perm.description && (
                      <span className="block text-xs text-muted-foreground">
                        {perm.description}
                      </span>
                    )}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
        );
      })}
    </div>
  );
}
