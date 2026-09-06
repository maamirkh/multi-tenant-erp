"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  listPipelines,
  listPipelineStages,
  listOpportunities,
  changeOpportunityStage,
  type PipelineRead,
  type PipelineStageRead,
  type OpportunityRead,
} from "@/lib/api/crm";
import { classifyCrmError, getCompanyId, type CrmErrorState } from "@/components/crm/apiErrors";
import CrmStateBanner from "@/components/crm/CrmStateBanner";

/**
 * Kanban-style pipeline board grouped by stage.
 *
 * No drag-and-drop library exists anywhere in this frontend yet (checked
 * package.json), and plan.md §21 explicitly forbids introducing a new one
 * for this feature — each card instead exposes a "Move to…" stage select,
 * which calls the same `POST .../stage` endpoint a drag-drop interaction
 * would.
 */
export default function OpportunityPipelinePage() {
  const companyId = getCompanyId();

  const [pipelines, setPipelines] = useState<PipelineRead[]>([]);
  const [pipelineId, setPipelineId] = useState("");
  const [stages, setStages] = useState<PipelineStageRead[]>([]);
  const [opportunities, setOpportunities] = useState<OpportunityRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorState, setErrorState] = useState<CrmErrorState | null>(null);
  const [movingId, setMovingId] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId) return;
    listPipelines(companyId)
      .then((res) => {
        const list = res.data ?? [];
        setPipelines(list);
        const initial = list.find((p) => p.is_default) ?? list[0];
        if (initial) setPipelineId(initial.id);
      })
      .catch((err) => setErrorState(classifyCrmError(err)));
  }, [companyId]);

  const load = useCallback(async () => {
    if (!companyId || !pipelineId) return;
    setLoading(true);
    setErrorState(null);
    try {
      const [stagesRes, oppsRes] = await Promise.all([
        listPipelineStages(companyId, pipelineId),
        listOpportunities(companyId, { status: "OPEN", page_size: 100 }),
      ]);
      setStages((stagesRes.data ?? []).sort((a, b) => a.sequence - b.sequence));
      setOpportunities(
        (oppsRes.data?.items ?? []).filter((o) => o.pipeline_id === pipelineId)
      );
    } catch (err) {
      setErrorState(classifyCrmError(err));
    } finally {
      setLoading(false);
    }
  }, [companyId, pipelineId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleMove(opportunityId: string, stageId: string) {
    if (!companyId) return;
    setMovingId(opportunityId);
    setErrorState(null);
    try {
      const res = await changeOpportunityStage(companyId, opportunityId, stageId);
      setOpportunities((prev) => prev.map((o) => (o.id === opportunityId ? res.data : o)));
    } catch (err) {
      setErrorState(classifyCrmError(err));
    } finally {
      setMovingId(null);
    }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Pipeline</h1>
          <Link href="../opportunities" className="text-sm text-indigo-600 hover:underline">
            ← List view
          </Link>
        </div>
        {pipelines.length > 1 && (
          <select
            value={pipelineId}
            onChange={(e) => setPipelineId(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
          >
            {pipelines.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {errorState && <CrmStateBanner state={errorState} />}

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading…</div>
      ) : stages.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          {errorState ? null : "No pipeline stages configured yet."}
        </div>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {stages.map((stage) => {
            const stageOpps = opportunities.filter((o) => o.stage_id === stage.id);
            return (
              <div key={stage.id} className="flex-shrink-0 w-72">
                <div className="bg-gray-50 rounded-t-md px-3 py-2 border border-gray-200">
                  <h2 className="text-sm font-semibold text-gray-700">{stage.name}</h2>
                  <p className="text-xs text-gray-500">
                    {stageOpps.length} · {stage.probability}%
                  </p>
                </div>
                <div className="border border-t-0 border-gray-200 rounded-b-md min-h-[120px] bg-white p-2 space-y-2">
                  {stageOpps.map((o) => (
                    <div
                      key={o.id}
                      className="border border-gray-200 rounded-md p-2 shadow-sm hover:shadow"
                    >
                      <Link
                        href={`../opportunities/${o.id}`}
                        className="text-sm font-medium text-gray-900 hover:text-indigo-600"
                      >
                        {o.name}
                      </Link>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {o.value} {o.currency_code}
                      </p>
                      <select
                        value={stage.id}
                        disabled={movingId === o.id}
                        onChange={(e) => handleMove(o.id, e.target.value)}
                        className="mt-2 w-full border border-gray-200 rounded text-xs px-1.5 py-1 disabled:opacity-50"
                      >
                        {stages.map((s) => (
                          <option key={s.id} value={s.id}>
                            Move to: {s.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
