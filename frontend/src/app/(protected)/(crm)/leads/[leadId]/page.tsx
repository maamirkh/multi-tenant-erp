"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getLead,
  updateLead,
  assignLead,
  convertLead,
  type LeadRead,
  type ConversionResult,
} from "@/lib/api/crm";
import { listMembers } from "@/lib/api/users-roles";
import type { MemberListItem } from "@/types/users-roles";
import { classifyCrmError, getCompanyId, type CrmErrorState } from "@/components/crm/apiErrors";
import CrmStateBanner from "@/components/crm/CrmStateBanner";
import StatusBadge from "@/components/crm/StatusBadge";
import LinkedActivities from "@/components/crm/LinkedActivities";

const LEAD_VALID_TRANSITIONS: Record<string, string[]> = {
  NEW: ["CONTACTED", "LOST"],
  CONTACTED: ["QUALIFIED", "UNQUALIFIED"],
  QUALIFIED: ["CONVERTED", "UNQUALIFIED"],
  UNQUALIFIED: ["NEW"],
  CONVERTED: [],
  LOST: [],
};

function leadDisplayName(lead: LeadRead): string {
  const personal = [lead.first_name, lead.last_name].filter(Boolean).join(" ");
  return personal || lead.lead_company_name || "(unnamed lead)";
}

export default function LeadDetailPage() {
  const params = useParams<{ leadId: string }>();
  const leadId = params.leadId;
  const companyId = getCompanyId();

  const [lead, setLead] = useState<LeadRead | null>(null);
  const [members, setMembers] = useState<MemberListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorState, setErrorState] = useState<CrmErrorState | null>(null);
  const [actionBusy, setActionBusy] = useState(false);

  const [qualifyNotes, setQualifyNotes] = useState("");
  const [disqualifyReason, setDisqualifyReason] = useState("");
  const [showQualifyForm, setShowQualifyForm] = useState(false);
  const [showDisqualifyForm, setShowDisqualifyForm] = useState(false);
  const [assignTo, setAssignTo] = useState("");
  const [conversionResult, setConversionResult] = useState<ConversionResult | null>(null);

  const load = useCallback(async () => {
    if (!companyId || !leadId) return;
    setLoading(true);
    setErrorState(null);
    try {
      const res = await getLead(companyId, leadId);
      setLead(res.data);
    } catch (err) {
      setErrorState(classifyCrmError(err));
    } finally {
      setLoading(false);
    }
  }, [companyId, leadId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!companyId) return;
    listMembers(companyId, { page_size: 100 })
      .then((data) => setMembers(data.items))
      .catch(() => setMembers([]));
  }, [companyId]);

  async function transitionStatus(status: string, extra: Record<string, unknown> = {}) {
    if (!companyId || !leadId) return;
    setActionBusy(true);
    setErrorState(null);
    try {
      const res = await updateLead(companyId, leadId, { status, ...extra });
      setLead(res.data);
      setShowQualifyForm(false);
      setShowDisqualifyForm(false);
      setQualifyNotes("");
      setDisqualifyReason("");
    } catch (err) {
      setErrorState(classifyCrmError(err));
    } finally {
      setActionBusy(false);
    }
  }

  async function handleAssign() {
    if (!companyId || !leadId || !assignTo) return;
    setActionBusy(true);
    setErrorState(null);
    try {
      const res = await assignLead(companyId, leadId, assignTo);
      setLead(res.data);
      setAssignTo("");
    } catch (err) {
      setErrorState(classifyCrmError(err));
    } finally {
      setActionBusy(false);
    }
  }

  async function handleConvert() {
    if (!companyId || !leadId) return;
    setActionBusy(true);
    setErrorState(null);
    try {
      const res = await convertLead(companyId, leadId);
      setConversionResult(res.data);
      await load();
    } catch (err) {
      setErrorState(classifyCrmError(err));
    } finally {
      setActionBusy(false);
    }
  }

  if (loading) {
    return <div className="p-6 text-center text-gray-500">Loading…</div>;
  }

  if (!lead) {
    return (
      <div className="p-6">
        {errorState && <CrmStateBanner state={errorState} />}
        <Link href="../leads" className="text-indigo-600 hover:underline text-sm">
          ← Back to Leads
        </Link>
      </div>
    );
  }

  const validNext = LEAD_VALID_TRANSITIONS[lead.status] ?? [];
  const ownerName = members.find((m) => m.user_id === lead.owner_id)?.display_name;

  return (
    <div className="p-6 max-w-3xl">
      <Link href="../leads" className="text-indigo-600 hover:underline text-sm">
        ← Back to Leads
      </Link>

      <div className="flex items-center justify-between mt-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{leadDisplayName(lead)}</h1>
          <div className="mt-1">
            <StatusBadge status={lead.status} />
          </div>
        </div>
      </div>

      {errorState && <CrmStateBanner state={errorState} />}

      {conversionResult && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-md text-sm text-green-800">
          Lead converted.{" "}
          <Link
            href={`../crm-customers/${conversionResult.customer_id}`}
            className="underline font-medium"
          >
            View Customer
          </Link>{" "}
          ·{" "}
          <Link
            href={`../opportunities/${conversionResult.opportunity_id}`}
            className="underline font-medium"
          >
            View Opportunity
          </Link>
        </div>
      )}

      <div className="grid grid-cols-2 gap-x-6 gap-y-3 mb-6 text-sm">
        <div>
          <span className="text-gray-500">Email</span>
          <div className="text-gray-900">{lead.email || "—"}</div>
        </div>
        <div>
          <span className="text-gray-500">Phone</span>
          <div className="text-gray-900">{lead.phone || "—"}</div>
        </div>
        <div>
          <span className="text-gray-500">Company</span>
          <div className="text-gray-900">{lead.lead_company_name || "—"}</div>
        </div>
        <div>
          <span className="text-gray-500">Score</span>
          <div className="text-gray-900">{lead.score ?? "—"}</div>
        </div>
        <div>
          <span className="text-gray-500">Owner</span>
          <div className="text-gray-900">{ownerName || "Unassigned"}</div>
        </div>
        <div>
          <span className="text-gray-500">Next Follow-up</span>
          <div className="text-gray-900">{lead.next_follow_up_date || "—"}</div>
        </div>
        {lead.notes && (
          <div className="col-span-2">
            <span className="text-gray-500">Notes</span>
            <div className="text-gray-900 whitespace-pre-wrap">{lead.notes}</div>
          </div>
        )}
        {lead.status === "UNQUALIFIED" && lead.disqualification_reason && (
          <div className="col-span-2">
            <span className="text-gray-500">Disqualification Reason</span>
            <div className="text-gray-900">{lead.disqualification_reason}</div>
          </div>
        )}
        {lead.qualification_notes && (
          <div className="col-span-2">
            <span className="text-gray-500">Qualification Notes</span>
            <div className="text-gray-900">{lead.qualification_notes}</div>
          </div>
        )}
      </div>

      {validNext.length > 0 && (
        <div className="border-t border-gray-200 pt-4 mb-4">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Actions</h2>
          <div className="flex flex-wrap gap-2">
            {validNext.includes("CONTACTED") && (
              <button
                disabled={actionBusy}
                onClick={() => transitionStatus("CONTACTED")}
                className="px-3 py-1.5 border border-gray-300 rounded-md text-sm hover:bg-gray-50 disabled:opacity-50"
              >
                Mark Contacted
              </button>
            )}
            {validNext.includes("QUALIFIED") && (
              <button
                disabled={actionBusy}
                onClick={() => setShowQualifyForm((v) => !v)}
                className="px-3 py-1.5 bg-teal-600 text-white rounded-md text-sm hover:bg-teal-700 disabled:opacity-50"
              >
                Qualify
              </button>
            )}
            {validNext.includes("UNQUALIFIED") && (
              <button
                disabled={actionBusy}
                onClick={() => setShowDisqualifyForm((v) => !v)}
                className="px-3 py-1.5 border border-gray-300 rounded-md text-sm hover:bg-gray-50 disabled:opacity-50"
              >
                Disqualify
              </button>
            )}
            {validNext.includes("LOST") && (
              <button
                disabled={actionBusy}
                onClick={() => transitionStatus("LOST")}
                className="px-3 py-1.5 border border-gray-300 rounded-md text-sm hover:bg-gray-50 disabled:opacity-50"
              >
                Mark Lost
              </button>
            )}
            {validNext.includes("NEW") && (
              <button
                disabled={actionBusy}
                onClick={() => transitionStatus("NEW")}
                className="px-3 py-1.5 border border-gray-300 rounded-md text-sm hover:bg-gray-50 disabled:opacity-50"
              >
                Reopen
              </button>
            )}
            {validNext.includes("CONVERTED") && (
              <button
                disabled={actionBusy}
                onClick={handleConvert}
                className="px-3 py-1.5 bg-green-600 text-white rounded-md text-sm hover:bg-green-700 disabled:opacity-50"
              >
                Convert to Customer
              </button>
            )}
          </div>

          {showQualifyForm && (
            <div className="mt-3 flex gap-2">
              <input
                placeholder="Qualification notes"
                value={qualifyNotes}
                onChange={(e) => setQualifyNotes(e.target.value)}
                className="flex-1 border border-gray-300 rounded-md px-3 py-1.5 text-sm"
              />
              <button
                disabled={actionBusy}
                onClick={() => transitionStatus("QUALIFIED", { qualification_notes: qualifyNotes })}
                className="px-3 py-1.5 bg-teal-600 text-white rounded-md text-sm hover:bg-teal-700 disabled:opacity-50"
              >
                Confirm
              </button>
            </div>
          )}
          {showDisqualifyForm && (
            <div className="mt-3 flex gap-2">
              <input
                placeholder="Disqualification reason"
                value={disqualifyReason}
                onChange={(e) => setDisqualifyReason(e.target.value)}
                className="flex-1 border border-gray-300 rounded-md px-3 py-1.5 text-sm"
              />
              <button
                disabled={actionBusy || !disqualifyReason}
                onClick={() =>
                  transitionStatus("UNQUALIFIED", { disqualification_reason: disqualifyReason })
                }
                className="px-3 py-1.5 bg-gray-700 text-white rounded-md text-sm hover:bg-gray-800 disabled:opacity-50"
              >
                Confirm
              </button>
            </div>
          )}
        </div>
      )}

      {!["CONVERTED", "LOST"].includes(lead.status) && (
        <div className="border-t border-gray-200 pt-4">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Reassign Owner</h2>
          <div className="flex gap-2">
            <select
              value={assignTo}
              onChange={(e) => setAssignTo(e.target.value)}
              className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
            >
              <option value="">Select a member…</option>
              {members.map((m) => (
                <option key={m.user_id} value={m.user_id}>
                  {m.display_name}
                </option>
              ))}
            </select>
            <button
              disabled={actionBusy || !assignTo}
              onClick={handleAssign}
              className="px-3 py-1.5 border border-gray-300 rounded-md text-sm hover:bg-gray-50 disabled:opacity-50"
            >
              Assign
            </button>
          </div>
        </div>
      )}

      <LinkedActivities companyId={companyId} relation="lead_id" entityId={lead.id} />
    </div>
  );
}
