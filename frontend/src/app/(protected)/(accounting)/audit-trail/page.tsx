"use client";

import { Fragment, useEffect, useState } from "react";
import ExportButton from "@/components/accounting/ExportButton";
import { ApiClientError } from "@/lib/api/client";
import { AuditLogEntry, getAuditLog } from "@/lib/api/accounting";

interface PageProps {
  params: { company_id: string };
}

const PAGE_SIZE = 50;

/** Deterministic color per action string, so the same action always reads the same. */
const ACTION_COLORS = [
  "bg-blue-100 text-blue-800",
  "bg-green-100 text-green-800",
  "bg-amber-100 text-amber-800",
  "bg-purple-100 text-purple-800",
  "bg-rose-100 text-rose-800",
  "bg-cyan-100 text-cyan-800",
];

function actionColor(action: string): string {
  let hash = 0;
  for (let i = 0; i < action.length; i++) {
    hash = (hash * 31 + action.charCodeAt(i)) >>> 0;
  }
  return ACTION_COLORS[hash % ACTION_COLORS.length] as string;
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function JsonBlock({ label, value }: { label: string; value: Record<string, unknown> | null }) {
  return (
    <div>
      <p className="mb-1 text-xs font-medium text-gray-500">{label}</p>
      {value ? (
        <pre className="max-h-64 overflow-auto rounded-md bg-gray-50 p-2 text-xs text-gray-800">
          {JSON.stringify(value, null, 2)}
        </pre>
      ) : (
        <p className="text-xs text-gray-400">—</p>
      )}
    </div>
  );
}

function EntityIdCell({ entityId }: { entityId: string }) {
  const [copied, setCopied] = useState(false);
  const truncated = entityId.length > 12 ? `${entityId.slice(0, 8)}…` : entityId;

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        navigator.clipboard
          .writeText(entityId)
          .then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          })
          .catch(() => {
            // Clipboard API unavailable — ignore, the id is still visible via title.
          });
      }}
      title={entityId}
      className="rounded font-mono text-xs text-gray-700 hover:bg-gray-100 hover:underline"
    >
      {copied ? "Copied!" : truncated}
    </button>
  );
}

/**
 * Audit Trail page — searchable, paginated, immutable history of changes
 * across accounting entities. Read-only: no create/edit/delete affordances.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T281
 */
export default function AuditTrailPage({ params }: PageProps) {
  const companyId = params?.company_id ?? "";

  const [entityType, setEntityType] = useState("");
  const [actorUserId, setActorUserId] = useState("");
  const [action, setAction] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [skip, setSkip] = useState(0);

  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      setForbidden(false);
      try {
        const res = await getAuditLog(companyId, {
          entity_type: entityType || undefined,
          actor_user_id: actorUserId || undefined,
          action: action || undefined,
          date_from: dateFrom ? new Date(dateFrom).toISOString() : undefined,
          date_to: dateTo ? new Date(dateTo).toISOString() : undefined,
          skip,
          limit: PAGE_SIZE,
        });
        if (cancelled) return;
        setEntries(res.data.entries);
        setTotal(res.data.total);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiClientError && err.status === 403) {
          setForbidden(true);
          setError(err.error.error.message);
        } else {
          setError(err instanceof Error ? err.message : "Failed to load audit log");
        }
        setEntries([]);
        setTotal(0);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [companyId, entityType, actorUserId, action, dateFrom, dateTo, skip]);

  function updateFilter(setter: (value: string) => void, value: string) {
    setter(value);
    setSkip(0);
  }

  const currentPage = Math.floor(skip / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const exportParams: Record<string, string> = {};
  if (entityType) exportParams["entity_type"] = entityType;
  if (actorUserId) exportParams["actor_user_id"] = actorUserId;
  if (action) exportParams["action"] = action;
  if (dateFrom) exportParams["date_from"] = new Date(dateFrom).toISOString();
  if (dateTo) exportParams["date_to"] = new Date(dateTo).toISOString();

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Audit Trail</h1>
          <p className="mt-1 text-sm text-gray-500">
            Searchable, immutable history of changes across accounting entities.
          </p>
        </div>
        {!forbidden && entries.length > 0 && (
          <ExportButton
            companyId={companyId}
            reportPath="/audit-log/export"
            filename="audit-trail"
            extraParams={exportParams}
            formats={[
              { value: "excel", label: "Export Excel" },
              { value: "csv", label: "Export CSV" },
            ]}
          />
        )}
      </div>

      <div className="mb-6 flex flex-wrap items-end gap-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div>
          <label className="block text-xs text-gray-500" htmlFor="entity-type">
            Entity Type
          </label>
          <input
            id="entity-type"
            type="text"
            placeholder="e.g. JournalEntry"
            value={entityType}
            onChange={(e) => updateFilter(setEntityType, e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500" htmlFor="actor-user">
            Actor (user ID)
          </label>
          <input
            id="actor-user"
            type="text"
            placeholder="user UUID"
            value={actorUserId}
            onChange={(e) => updateFilter(setActorUserId, e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500" htmlFor="action">
            Action
          </label>
          <input
            id="action"
            type="text"
            placeholder="e.g. UPDATE"
            value={action}
            onChange={(e) => updateFilter(setAction, e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500" htmlFor="date-from">
            From
          </label>
          <input
            id="date-from"
            type="date"
            value={dateFrom}
            onChange={(e) => updateFilter(setDateFrom, e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500" htmlFor="date-to">
            To
          </label>
          <input
            id="date-to"
            type="date"
            value={dateTo}
            onChange={(e) => updateFilter(setDateTo, e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm"
          />
        </div>
      </div>

      {error && (
        <div
          className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700"
          role="alert"
        >
          {forbidden ? (
            <>
              <p className="font-medium">Access denied</p>
              <p className="mt-0.5">
                {error || "You do not have permission to view the audit trail."}
              </p>
            </>
          ) : (
            error
          )}
        </div>
      )}

      {loading ? (
        <div className="py-8 text-center text-gray-500">Loading...</div>
      ) : forbidden ? null : entries.length === 0 ? (
        <div className="rounded-md border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          No audit log entries match these filters.
        </div>
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
          <p className="border-b border-gray-100 px-4 py-2 text-xs text-gray-500">
            Showing {entries.length} of {total} entries
          </p>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left text-xs text-gray-500">
                  <th className="px-4 py-2">Occurred At</th>
                  <th className="px-4 py-2">Entity Type</th>
                  <th className="px-4 py-2">Entity ID</th>
                  <th className="px-4 py-2">Action</th>
                  <th className="px-4 py-2">Actor</th>
                  <th className="px-4 py-2">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {entries.map((entry) => (
                  <Fragment key={entry.id}>
                    <tr
                      className="cursor-pointer hover:bg-gray-50"
                      onClick={() =>
                        setExpandedId((cur) => (cur === entry.id ? null : entry.id))
                      }
                      aria-expanded={expandedId === entry.id}
                    >
                      <td className="whitespace-nowrap px-4 py-2 text-gray-600">
                        {formatTimestamp(entry.occurred_at)}
                      </td>
                      <td className="px-4 py-2 text-gray-900">{entry.entity_type}</td>
                      <td className="px-4 py-2">
                        <EntityIdCell entityId={entry.entity_id} />
                      </td>
                      <td className="px-4 py-2">
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${actionColor(entry.action)}`}
                        >
                          {entry.action}
                        </span>
                      </td>
                      <td className="px-4 py-2 font-mono text-xs text-gray-600">
                        {entry.actor_user_id ?? (
                          <span className="text-gray-400">system</span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-gray-600">{entry.reason ?? "—"}</td>
                    </tr>
                    {expandedId === entry.id && (
                      <tr className="bg-gray-50/60">
                        <td colSpan={6} className="px-4 py-3">
                          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                            <JsonBlock label="Before" value={entry.before_state} />
                            <JsonBlock label="After" value={entry.after_state} />
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-gray-100 px-4 py-3">
              <span className="text-xs text-gray-500">
                Page {currentPage} of {totalPages}
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
                  disabled={skip === 0}
                  className="rounded-md border border-gray-300 px-3 py-1 text-sm text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  type="button"
                  onClick={() => setSkip(skip + PAGE_SIZE)}
                  disabled={skip + PAGE_SIZE >= total}
                  className="rounded-md border border-gray-300 px-3 py-1 text-sm text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
