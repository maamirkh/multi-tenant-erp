"use client";

import { useState } from "react";

interface CustomFieldValue {
  id: string;
  field_key: string;
  value_text: string | null;
  value_number: string | null;
  value_bool: boolean | null;
  value_json: Record<string, unknown> | null;
}

interface ProductCustomFieldsProps {
  values: CustomFieldValue[];
  onSet?: (fieldKey: string, valueText: string) => Promise<void>;
  onDelete?: (fieldKey: string) => Promise<void>;
  readonly?: boolean;
}

function displayValue(v: CustomFieldValue): string {
  if (v.value_bool !== null && v.value_bool !== undefined) {
    return v.value_bool ? "Yes" : "No";
  }
  if (v.value_number !== null && v.value_number !== undefined) return v.value_number;
  if (v.value_json !== null && v.value_json !== undefined)
    return JSON.stringify(v.value_json);
  return v.value_text ?? "—";
}

export function ProductCustomFields({
  values,
  onSet,
  onDelete,
  readonly = false,
}: ProductCustomFieldsProps) {
  const [editKey, setEditKey] = useState<string | null>(null);
  const [editVal, setEditVal] = useState("");
  const [newKey, setNewKey] = useState("");
  const [newVal, setNewVal] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSave = async (key: string, val: string) => {
    if (!onSet) return;
    setSaving(true);
    try {
      await onSet(key, val);
      setEditKey(null);
    } finally {
      setSaving(false);
    }
  };

  const handleAdd = async () => {
    if (!onSet || !newKey.trim()) return;
    setSaving(true);
    try {
      await onSet(newKey.trim(), newVal.trim());
      setNewKey("");
      setNewVal("");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium text-gray-700">Custom Fields</h3>

      {values.length === 0 && (
        <p className="text-sm text-gray-400">No custom fields set.</p>
      )}

      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <tbody className="divide-y divide-gray-100">
          {values.map((v) => (
            <tr key={v.id} className="group">
              <td className="py-2 pr-4 font-mono text-gray-600">{v.field_key}</td>
              <td className="py-2 pr-4 text-gray-800">
                {editKey === v.field_key ? (
                  <input
                    className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
                    value={editVal}
                    onChange={(e) => setEditVal(e.target.value)}
                    autoFocus
                  />
                ) : (
                  displayValue(v)
                )}
              </td>
              {!readonly && (
                <td className="py-2 text-right">
                  {editKey === v.field_key ? (
                    <span className="flex gap-1 justify-end">
                      <button
                        className="text-xs text-blue-600 hover:underline"
                        onClick={() => handleSave(v.field_key, editVal)}
                        disabled={saving}
                      >
                        Save
                      </button>
                      <button
                        className="text-xs text-gray-400 hover:underline"
                        onClick={() => setEditKey(null)}
                      >
                        Cancel
                      </button>
                    </span>
                  ) : (
                    <span className="flex gap-2 justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        className="text-xs text-blue-600 hover:underline"
                        onClick={() => {
                          setEditKey(v.field_key);
                          setEditVal(v.value_text ?? v.value_number ?? "");
                        }}
                      >
                        Edit
                      </button>
                      {onDelete && (
                        <button
                          className="text-xs text-red-500 hover:underline"
                          onClick={() => onDelete(v.field_key)}
                        >
                          Delete
                        </button>
                      )}
                    </span>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      {!readonly && onSet && (
        <div className="flex items-end gap-2 pt-2">
          <div>
            <label className="block text-xs font-medium text-gray-600">Field key</label>
            <input
              className="rounded border border-gray-300 px-2 py-1 text-sm"
              placeholder="e.g. warranty_months"
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600">Value</label>
            <input
              className="rounded border border-gray-300 px-2 py-1 text-sm"
              placeholder="Value"
              value={newVal}
              onChange={(e) => setNewVal(e.target.value)}
            />
          </div>
          <button
            className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            onClick={handleAdd}
            disabled={saving || !newKey.trim()}
          >
            Add
          </button>
        </div>
      )}
    </div>
  );
}
