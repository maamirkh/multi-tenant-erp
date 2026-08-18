"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getOpportunity,
  assignOpportunity,
  changeOpportunityStage,
  winOpportunity,
  loseOpportunity,
  updateOpportunity,
  listPipelineStages,
  type OpportunityRead,
  type PipelineStageRead,
} from "@/lib/api/crm";
import { listMembers } from "@/lib/api/users-roles";
import type { MemberListItem } from "@/types/users-roles";
import { classifyCrmError, getCompanyId, type CrmErrorState } from "@/components/crm/apiErrors";
import CrmStateBanner from "@/components/crm/CrmStateBanner";
import StatusBadge from "@/components/crm/StatusBadge";
import LinkedActivities from "@/components/crm/LinkedActivities";

export default function OpportunityDetailPage() {
  const params = useParams<{ opportunityId: string }>();
  const opportunityId = params.opportunityId;
  const companyId = getCompanyId();

  const [opportunity, setOpportunity] = useState<OpportunityRead | null>(null);
  const [stages, setStages] = useState<PipelineStageRead[]>([]);
  const [members, setMembers] = useState<MemberListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorState, setErrorState] = useState<CrmErrorState | null>(null);
  const [actionBusy, setActionBusy] = useState(false);

  const [assignTo, setAssignTo] = useState("");
  const [loseReason, setLoseReason] = useState("");
  const [showLoseForm, setShowLoseForm] = useState(false);
  const [quotationIdInput, setQuotationIdInput] = useState("");

  const load = useCallback(async () => {
    if (!companyId || !opportunityId) return;
    setLoading(true);
    setErrorState(null);
    try {
      const res = await getOpportunity(companyId, opportunityId);
      setOpportunity(res.data);
      const stagesRes = await listPipelineStages(companyId, res.data.pipeline_id);
      setStages((stagesRes.data ?? []).sort((a, b) => a.sequence - b.sequence));
    } catch (err) {
      setErrorState(classifyCrmError(err));
    } finally {
      setLoading(false);
    }
  }, [companyId, opportunityId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!companyId) return;
    listMembers(companyId, { page_size: 100 })
      .then((data) => setMembers(data.items))
      .catch(() => setMembers([]));
  }, [companyId]);

  async function handleStageChange(stageId: string) {
    if (!companyId || !opportunityId) return;
    setActionBusy(true);
    setErrorState(null);
    try {
      const res = await changeOpportunityStage(companyId, opportunityId, stageId);
      setOpportunity(res.data);
    } catch (err) {
      setErrorState(classifyCrmError(err));
    } finally {
      setActionBusy(false);
    }
  }

  async function handleAssign() {
    if (!companyId || !opportunityId || !assignTo) return;
    setActionBusy(true);
    setErrorState(null);
    try {
      const res = await assignOpportunity(companyId, opportunityId, assignTo);
      setOpportunity(res.data);
      setAssignTo("");
    } catch (err) {
      setErrorState(classifyCrmError(err));
    } finally {
      setActionBusy(false);
    }
  }

  async function handleWin() {
    if (!companyId || !opportunityId) return;
    setActionBusy(true);
    setErrorState(null);
    try {
      const res = await winOpportunity(companyId, opportunityId);
      setOpportunity(res.data);
    } catch (err) {
      setErrorState(classifyCrmError(err));
    } finally {
      setActionBusy(false);
    }
  }

  async function handleLose() {
    if (!companyId || !opportunityId || !loseReason) return;
    setActionBusy(true);
    setErrorState(null);
    try {
      const res = await loseOpportunity(companyId, opportunityId, loseReason);
      setOpportunity(res.data);
      setShowLoseForm(false);
      setLoseReason("");
    } catch (err) {
      setErrorState(classifyCrmError(err));
    } finally {
      setActionBusy(false);
    }
  }

  async function handleLinkQuotation() {
    if (!companyId || !opportunityId || !quotationIdInput) return;
    setActionBusy(true);
    setErrorState(null);
    try {
      const res = await updateOpportunity(companyId, opportunityId, {
        quotation_id: quotationIdInput,
      });
      setOpportunity(res.data);
      setQuotationIdInput("");
    } catch (err) {
      setErrorState(classifyCrmError(err));
    } finally {
      setActionBusy(false);
    }
  }

  if (loading) {
    return <div className="p-6 text-center text-gray-500">Loading…</div>;
  }

  if (!opportunity) {
    return (
      <div className="p-6">
        {errorState && <CrmStateBanner state={errorState} />}
        <Link href="../opportunities" className="text-indigo-600 hover:underline text-sm">
          ← Back to Opportunities
        </Link>
      </div>
    );
  }

  const isOpen = opportunity.status === "OPEN";
  const ownerName = members.find((m) => m.user_id === opportunity.owner_id)?.display_name;

  return (
    <div className="p-6 max-w-3xl">
      <Link href="../opportunities" className="text-indigo-600 hover:underline text-sm">
        ← Back to Opportunities
      </Link>

      <div className="flex items-center justify-between mt-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{opportunity.name}</h1>
          <div className="mt-1">
            <StatusBadge status={opportunity.status} />
          </div>
        </div>
        {isOpen && (
          <Link
            href={`/quotations?customer_id=${opportunity.customer_id}`}
            className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 text-sm font-medium"
          >
            Create Quotation
          </Link>
        )}
      </div>

      {errorState && <CrmStateBanner state={errorState} />}

      <div className="grid grid-cols-2 gap-x-6 gap-y-3 mb-6 text-sm">
        <div>
          <span className="text-gray-500">Value</span>
          <div className="text-gray-900">
            {opportunity.value} {opportunity.currency_code}
          </div>
        </div>
        <div>
          <span className="text-gray-500">Weighted Value</span>
          <div className="text-gray-900">
            {opportunity.weighted_value} {opportunity.currency_code}
          </div>
        </div>
        <div>
          <span className="text-gray-500">Probability</span>
          <div className="text-gray-900">{opportunity.probability}%</div>
        </div>
        <div>
          <span className="text-gray-500">Expected Close</span>
          <div className="text-gray-900">{opportunity.expected_close_date ?? "—"}</div>
        </div>
        <div>
          <span className="text-gray-500">Owner</span>
          <div className="text-gray-900">{ownerName || "Unassigned"}</div>
        </div>
        <div>
          <span className="text-gray-500">Customer</span>
          <div className="text-gray-900">
            <Link href={`../customers/${opportunity.customer_id}`} className="text-indigo-600 hover:underline">
              View Customer 360
            </Link>
          </div>
        </div>
        <div>
          <span className="text-gray-500">Quotation</span>
          <div className="text-gray-900">{opportunity.quotation_id ?? "Not linked"}</div>
        </div>
        {opportunity.status === "LOST" && opportunity.lost_reason && (
          <div className="col-span-2">
            <span className="text-gray-500">Lost Reason</span>
            <div className="text-gray-900">{opportunity.lost_reason}</div>
          </div>
        )}
        {opportunity.description && (
          <div className="col-span-2">
            <span className="text-gray-500">Description</span>
            <div className="text-gray-900 whitespace-pre-wrap">{opportunity.description}</div>
          </div>
        )}
      </div>

      {isOpen && (
        <>
          <div className="border-t border-gray-200 pt-4 mb-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Stage</h2>
            <select
              value={opportunity.stage_id}
              disabled={actionBusy}
              onChange={(e) => handleStageChange(e.target.value)}
              className="border border-gray-300 rounded-md px-3 py-1.5 text-sm disabled:opacity-50"
            >
              {stages.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          <div className="border-t border-gray-200 pt-4 mb-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Close</h2>
            <div className="flex flex-wrap gap-2">
              <button
                disabled={actionBusy}
                onClick={handleWin}
                className="px-3 py-1.5 bg-green-600 text-white rounded-md text-sm hover:bg-green-700 disabled:opacity-50"
              >
                Mark Won
              </button>
              <button
                disabled={actionBusy}
                onClick={() => setShowLoseForm((v) => !v)}
                className="px-3 py-1.5 border border-gray-300 rounded-md text-sm hover:bg-gray-50 disabled:opacity-50"
              >
                Mark Lost
              </button>
            </div>
            {showLoseForm && (
              <div className="mt-3 flex gap-2">
                <input
                  placeholder="Lost reason"
                  value={loseReason}
                  onChange={(e) => setLoseReason(e.target.value)}
                  className="flex-1 border border-gray-300 rounded-md px-3 py-1.5 text-sm"
                />
                <button
                  disabled={actionBusy || !loseReason}
                  onClick={handleLose}
                  className="px-3 py-1.5 bg-gray-700 text-white rounded-md text-sm hover:bg-gray-800 disabled:opacity-50"
                >
                  Confirm
                </button>
              </div>
            )}
          </div>

          <div className="border-t border-gray-200 pt-4 mb-4">
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

          {!opportunity.quotation_id && (
            <div className="border-t border-gray-200 pt-4">
              <h2 className="text-sm font-semibold text-gray-700 mb-3">Link Quotation</h2>
              <p className="text-xs text-gray-500 mb-2">
                After creating the quotation in Sales, paste its ID here to link it to this
                opportunity.
              </p>
              <div className="flex gap-2">
                <input
                  placeholder="Quotation ID"
                  value={quotationIdInput}
                  onChange={(e) => setQuotationIdInput(e.target.value)}
                  className="flex-1 border border-gray-300 rounded-md px-3 py-1.5 text-sm"
                />
                <button
                  disabled={actionBusy || !quotationIdInput}
                  onClick={handleLinkQuotation}
                  className="px-3 py-1.5 border border-gray-300 rounded-md text-sm hover:bg-gray-50 disabled:opacity-50"
                >
                  Link
                </button>
              </div>
            </div>
          )}
        </>
      )}

      <LinkedActivities
        companyId={companyId}
        relation="opportunity_id"
        entityId={opportunity.id}
      />
    </div>
  );
}
