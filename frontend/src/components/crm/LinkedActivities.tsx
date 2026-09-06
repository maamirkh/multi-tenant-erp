"use client";

import { useState, useEffect, useCallback, FormEvent } from "react";
import { listActivities, createActivity, completeActivity, type ActivityRead } from "@/lib/api/crm";
import { useAuthContext } from "@/contexts/AuthContext";
import { classifyCrmError, type CrmErrorState } from "@/components/crm/apiErrors";
import CrmStateBanner from "@/components/crm/CrmStateBanner";
import StatusBadge from "@/components/crm/StatusBadge";
import { useCrmPermissions, useHasCrmPermission } from "@/hooks/crm/useCrmPermissions";

interface LinkedActivitiesProps {
  companyId: string;
  /** Which foreign key on the Activity this panel is scoped to. */
  relation: "lead_id" | "customer_id" | "opportunity_id";
  entityId: string;
}

/**
 * Activities linked to a single Lead, Customer, or Opportunity — shared by
 * the Lead detail, Opportunity detail, and Customer 360 pages (spec.md §39
 * table: both detail pages "include linked activities").
 */
export default function LinkedActivities({ companyId, relation, entityId }: LinkedActivitiesProps) {
  const { user } = useAuthContext();
  const permissionsState = useCrmPermissions();
  const canCreateActivity = useHasCrmPermission(permissionsState, "crm.activities.create");
  const canUpdateActivity = useHasCrmPermission(permissionsState, "crm.activities.update");
  const [activities, setActivities] = useState<ActivityRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorState, setErrorState] = useState<CrmErrorState | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [activityType, setActivityType] = useState("CALL");
  const [subject, setSubject] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    if (!companyId || !entityId) return;
    setLoading(true);
    setErrorState(null);
    try {
      const res = await listActivities(companyId, { [relation]: entityId, page_size: 50 } as never);
      setActivities(res.data?.items ?? []);
    } catch (err) {
      setErrorState(classifyCrmError(err));
    } finally {
      setLoading(false);
    }
  }, [companyId, relation, entityId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleComplete(activityId: string) {
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

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!user || !subject) return;
    const requiresDueDate = activityType === "TASK" || activityType === "FOLLOW_UP";
    if (requiresDueDate && !dueDate) {
      setErrorState({
        message: "A due date is required for TASK and FOLLOW_UP activities.",
        forbidden: false,
        featureDisabled: false,
      });
      return;
    }
    setSubmitting(true);
    setErrorState(null);
    try {
      await createActivity(companyId, {
        activity_type: activityType,
        subject,
        assigned_to: user.user_id,
        [relation]: entityId,
        ...(dueDate ? { due_date: new Date(dueDate).toISOString() } : {}),
      });
      setSubject("");
      setDueDate("");
      setShowForm(false);
      await load();
    } catch (err) {
      setErrorState(classifyCrmError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="border-t border-gray-200 pt-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-700">Activities</h2>
        {canCreateActivity && (
          <button
            onClick={() => setShowForm((v) => !v)}
            className="text-xs text-indigo-600 hover:underline"
          >
            {showForm ? "Cancel" : "+ Log Activity"}
          </button>
        )}
      </div>

      {errorState && <CrmStateBanner state={errorState} />}

      {showForm && (
        <form onSubmit={handleSubmit} className="mb-4 flex flex-wrap gap-2 items-start">
          <select
            value={activityType}
            onChange={(e) => setActivityType(e.target.value)}
            className="border border-gray-300 rounded-md px-2 py-1.5 text-sm"
          >
            <option value="CALL">Call</option>
            <option value="EMAIL">Email</option>
            <option value="MEETING">Meeting</option>
            <option value="TASK">Task</option>
            <option value="NOTE">Note</option>
            <option value="FOLLOW_UP">Follow-up</option>
          </select>
          <input
            placeholder="Subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className="flex-1 min-w-[160px] border border-gray-300 rounded-md px-2 py-1.5 text-sm"
          />
          <input
            type="datetime-local"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
            className="border border-gray-300 rounded-md px-2 py-1.5 text-sm"
          />
          <button
            type="submit"
            disabled={submitting || !subject}
            className="px-3 py-1.5 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700 disabled:opacity-50"
          >
            Save
          </button>
        </form>
      )}

      {loading ? (
        <p className="text-sm text-gray-500">Loading…</p>
      ) : activities.length === 0 ? (
        <p className="text-sm text-gray-500">No activities logged yet.</p>
      ) : (
        <ul className="space-y-2">
          {activities.map((a) => (
            <li
              key={a.id}
              className="flex items-center justify-between border border-gray-200 rounded-md px-3 py-2"
            >
              <div>
                <span className="text-xs font-medium text-gray-500 mr-2">{a.activity_type}</span>
                <span className="text-sm text-gray-900">{a.subject}</span>
                {a.due_date && (
                  <span className="text-xs text-gray-400 ml-2">due {a.due_date}</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={a.status} />
                {canUpdateActivity && a.status === "PLANNED" && (
                  <button
                    disabled={busyId === a.id}
                    onClick={() => handleComplete(a.id)}
                    className="text-xs text-indigo-600 hover:underline disabled:opacity-50"
                  >
                    Complete
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
