"use client";

import { useState, useEffect, useCallback } from "react";
import { listActivities, completeActivity, type ActivityRead } from "@/lib/api/crm";
import { listMembers } from "@/lib/api/users-roles";
import type { MemberListItem } from "@/types/users-roles";
import { classifyCrmError, getCompanyId, type CrmErrorState } from "@/components/crm/apiErrors";
import CrmStateBanner from "@/components/crm/CrmStateBanner";
import StatusBadge from "@/components/crm/StatusBadge";
import Pagination from "@/components/crm/Pagination";
import { useCrmPermissions, useHasCrmPermission } from "@/hooks/crm/useCrmPermissions";

const PAGE_SIZE = 20;

function isOverdue(activity: ActivityRead): boolean {
  if (activity.status !== "PLANNED" || !activity.due_date) return false;
  return new Date(activity.due_date).getTime() < Date.now();
}

export default function ActivitiesPage() {
  const companyId = getCompanyId();
  const permissionsState = useCrmPermissions();
  const canUpdateActivity = useHasCrmPermission(permissionsState, "crm.activities.update");

  const [activities, setActivities] = useState<ActivityRead[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [errorState, setErrorState] = useState<CrmErrorState | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [view, setView] = useState<"all" | "due">("all");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [assignedFilter, setAssignedFilter] = useState("");
  const [members, setMembers] = useState<MemberListItem[]>([]);

  const load = useCallback(async () => {
    if (!companyId) return;
    setLoading(true);
    setErrorState(null);
    try {
      const res = await listActivities(companyId, {
        ...(view === "due" ? {} : typeFilter ? { activity_type: typeFilter } : {}),
        ...(view === "due" ? { status: "PLANNED" } : statusFilter ? { status: statusFilter } : {}),
        ...(assignedFilter ? { assigned_to: assignedFilter } : {}),
        page,
        page_size: PAGE_SIZE,
      });
      let items = res.data?.items ?? [];
      if (view === "due") {
        items = items
          .filter((a) => a.activity_type === "TASK" || a.activity_type === "FOLLOW_UP")
          .sort((a, b) => (a.due_date ?? "").localeCompare(b.due_date ?? ""));
      }
      setActivities(items);
      setTotal(res.data?.total ?? 0);
    } catch (err) {
      setErrorState(classifyCrmError(err));
      setActivities([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [companyId, view, typeFilter, statusFilter, assignedFilter, page]);

  useEffect(() => {
    if (!companyId) return;
    listMembers(companyId, { page_size: 100 })
      .then((data) => setMembers(data.items))
      .catch(() => setMembers([]));
  }, [companyId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleComplete(activityId: string) {
    if (!companyId) return;
    setBusyId(activityId);
    try {
      const res = await completeActivity(companyId, activityId);
      setActivities((prev) => prev.map((a) => (a.id === activityId ? res.data : a)));
    } catch (err) {
      setErrorState(classifyCrmError(err));
    } finally {
      setBusyId(null);
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Activities</h1>
          <p className="text-sm text-gray-500 mt-1">{total} total records</p>
        </div>
        <div className="flex border border-gray-300 rounded-md overflow-hidden text-sm">
          <button
            onClick={() => {
              setView("all");
              setPage(1);
            }}
            className={`px-3 py-1.5 ${view === "all" ? "bg-indigo-600 text-white" : "bg-white text-gray-700"}`}
          >
            All
          </button>
          <button
            onClick={() => {
              setView("due");
              setPage(1);
            }}
            className={`px-3 py-1.5 ${view === "due" ? "bg-indigo-600 text-white" : "bg-white text-gray-700"}`}
          >
            Due (Tasks &amp; Follow-ups)
          </button>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-3">
        {view === "all" && (
          <>
            <select
              value={typeFilter}
              onChange={(e) => {
                setTypeFilter(e.target.value);
                setPage(1);
              }}
              className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
            >
              <option value="">All Types</option>
              <option value="CALL">Call</option>
              <option value="EMAIL">Email</option>
              <option value="MEETING">Meeting</option>
              <option value="TASK">Task</option>
              <option value="NOTE">Note</option>
              <option value="FOLLOW_UP">Follow-up</option>
            </select>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
            >
              <option value="">All Statuses</option>
              <option value="PLANNED">Planned</option>
              <option value="COMPLETED">Completed</option>
              <option value="CANCELLED">Cancelled</option>
            </select>
          </>
        )}
        <select
          value={assignedFilter}
          onChange={(e) => {
            setAssignedFilter(e.target.value);
            setPage(1);
          }}
          className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
        >
          <option value="">All Owners</option>
          {members.map((m) => (
            <option key={m.user_id} value={m.user_id}>
              {m.display_name}
            </option>
          ))}
        </select>
      </div>

      {errorState && <CrmStateBanner state={errorState} />}

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading…</div>
      ) : activities.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          {errorState ? null : "No activities found."}
        </div>
      ) : (
        <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 rounded-lg">
          <table className="min-w-full divide-y divide-gray-300">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Type
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Subject
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Due
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Status
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {activities.map((a) => (
                <tr key={a.id} className={isOverdue(a) ? "bg-red-50" : "hover:bg-gray-50"}>
                  <td className="px-4 py-3 text-sm text-gray-500">{a.activity_type}</td>
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">{a.subject}</td>
                  <td className={`px-4 py-3 text-sm ${isOverdue(a) ? "text-red-700 font-medium" : "text-gray-500"}`}>
                    {a.due_date ?? "—"}
                    {isOverdue(a) && " (overdue)"}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={a.status} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    {canUpdateActivity && a.status === "PLANNED" && (
                      <button
                        disabled={busyId === a.id}
                        onClick={() => handleComplete(a.id)}
                        className="text-indigo-600 hover:text-indigo-700 text-sm font-medium disabled:opacity-50"
                      >
                        Complete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {view === "all" && <Pagination page={page} totalPages={totalPages} onChange={setPage} />}
    </div>
  );
}
