"use client";

import { useState, useEffect, useCallback, FormEvent } from "react";
import {
  listLeadSources,
  createLeadSource,
  updateLeadSource,
  listPipelines,
  createPipeline,
  updatePipeline,
  listPipelineStages,
  createPipelineStage,
  updatePipelineStage,
  type LeadSourceRead,
  type PipelineRead,
  type PipelineStageRead,
} from "@/lib/api/crm";
import { classifyCrmError, getCompanyId, type CrmErrorState } from "@/components/crm/apiErrors";
import CrmStateBanner from "@/components/crm/CrmStateBanner";

export default function CrmSettingsPage() {
  const companyId = getCompanyId();
  const [errorState, setErrorState] = useState<CrmErrorState | null>(null);

  // Lead Sources
  const [sources, setSources] = useState<LeadSourceRead[]>([]);
  const [newSourceCode, setNewSourceCode] = useState("");
  const [newSourceName, setNewSourceName] = useState("");

  // Pipelines & Stages
  const [pipelines, setPipelines] = useState<PipelineRead[]>([]);
  const [selectedPipelineId, setSelectedPipelineId] = useState("");
  const [stages, setStages] = useState<PipelineStageRead[]>([]);
  const [newPipelineName, setNewPipelineName] = useState("");
  const [newStageName, setNewStageName] = useState("");
  const [newStageSequence, setNewStageSequence] = useState("1");
  const [newStageProbability, setNewStageProbability] = useState("50");

  const loadSources = useCallback(async () => {
    if (!companyId) return;
    try {
      const res = await listLeadSources(companyId);
      setSources(res.data?.items ?? []);
    } catch (err) {
      setErrorState(classifyCrmError(err));
    }
  }, [companyId]);

  const loadPipelines = useCallback(async () => {
    if (!companyId) return;
    try {
      const res = await listPipelines(companyId);
      const list = res.data ?? [];
      setPipelines(list);
      const initial = list.find((p) => p.is_default) ?? list[0];
      if (!selectedPipelineId && initial) {
        setSelectedPipelineId(initial.id);
      }
    } catch (err) {
      setErrorState(classifyCrmError(err));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId]);

  const loadStages = useCallback(async () => {
    if (!companyId || !selectedPipelineId) return;
    try {
      const res = await listPipelineStages(companyId, selectedPipelineId);
      setStages((res.data ?? []).sort((a, b) => a.sequence - b.sequence));
    } catch (err) {
      setErrorState(classifyCrmError(err));
    }
  }, [companyId, selectedPipelineId]);

  useEffect(() => {
    loadSources();
    loadPipelines();
  }, [loadSources, loadPipelines]);

  useEffect(() => {
    loadStages();
  }, [loadStages]);

  async function handleCreateSource(e: FormEvent) {
    e.preventDefault();
    if (!newSourceCode || !newSourceName) return;
    setErrorState(null);
    try {
      await createLeadSource(companyId, { code: newSourceCode, name: newSourceName });
      setNewSourceCode("");
      setNewSourceName("");
      await loadSources();
    } catch (err) {
      setErrorState(classifyCrmError(err));
    }
  }

  async function toggleSourceActive(source: LeadSourceRead) {
    setErrorState(null);
    try {
      await updateLeadSource(companyId, source.id, { is_active: !source.is_active });
      await loadSources();
    } catch (err) {
      setErrorState(classifyCrmError(err));
    }
  }

  async function handleCreatePipeline(e: FormEvent) {
    e.preventDefault();
    if (!newPipelineName) return;
    setErrorState(null);
    try {
      await createPipeline(companyId, { name: newPipelineName });
      setNewPipelineName("");
      await loadPipelines();
    } catch (err) {
      setErrorState(classifyCrmError(err));
    }
  }

  async function setDefaultPipeline(pipelineId: string) {
    setErrorState(null);
    try {
      await updatePipeline(companyId, pipelineId, { is_default: true });
      await loadPipelines();
    } catch (err) {
      setErrorState(classifyCrmError(err));
    }
  }

  async function handleCreateStage(e: FormEvent) {
    e.preventDefault();
    if (!newStageName || !selectedPipelineId) return;
    setErrorState(null);
    try {
      await createPipelineStage(companyId, selectedPipelineId, {
        name: newStageName,
        sequence: Number(newStageSequence),
        probability: Number(newStageProbability),
      });
      setNewStageName("");
      await loadStages();
    } catch (err) {
      setErrorState(classifyCrmError(err));
    }
  }

  async function toggleStageActive(stage: PipelineStageRead) {
    setErrorState(null);
    try {
      await updatePipelineStage(companyId, stage.id, { is_active: !stage.is_active });
      await loadStages();
    } catch (err) {
      setErrorState(classifyCrmError(err));
    }
  }

  return (
    <div className="p-6 max-w-4xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">CRM Settings</h1>

      {errorState && <CrmStateBanner state={errorState} />}

      <section className="mb-8">
        <h2 className="text-sm font-semibold text-gray-700 mb-3 border-b border-gray-200 pb-2">
          Lead Sources
        </h2>
        <ul className="space-y-1 mb-3">
          {sources.map((s) => (
            <li key={s.id} className="flex items-center justify-between text-sm border border-gray-200 rounded-md px-3 py-1.5">
              <span>
                <span className="font-mono text-gray-500 mr-2">{s.code}</span>
                {s.name}
              </span>
              <button
                onClick={() => toggleSourceActive(s)}
                className={`text-xs ${s.is_active ? "text-gray-500" : "text-green-600"} hover:underline`}
              >
                {s.is_active ? "Deactivate" : "Activate"}
              </button>
            </li>
          ))}
        </ul>
        <form onSubmit={handleCreateSource} className="flex gap-2">
          <input
            placeholder="Code"
            value={newSourceCode}
            onChange={(e) => setNewSourceCode(e.target.value)}
            className="w-32 border border-gray-300 rounded-md px-2 py-1.5 text-sm"
          />
          <input
            placeholder="Name"
            value={newSourceName}
            onChange={(e) => setNewSourceName(e.target.value)}
            className="flex-1 border border-gray-300 rounded-md px-2 py-1.5 text-sm"
          />
          <button
            type="submit"
            className="px-3 py-1.5 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700"
          >
            Add
          </button>
        </form>
      </section>

      <section className="mb-8">
        <h2 className="text-sm font-semibold text-gray-700 mb-3 border-b border-gray-200 pb-2">
          Pipelines
        </h2>
        <ul className="space-y-1 mb-3">
          {pipelines.map((p) => (
            <li
              key={p.id}
              className={`flex items-center justify-between text-sm border rounded-md px-3 py-1.5 cursor-pointer ${
                p.id === selectedPipelineId ? "border-indigo-400 bg-indigo-50" : "border-gray-200"
              }`}
              onClick={() => setSelectedPipelineId(p.id)}
            >
              <span>
                {p.name} {p.is_default && <span className="text-xs text-indigo-600 ml-1">(default)</span>}
              </span>
              {!p.is_default && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setDefaultPipeline(p.id);
                  }}
                  className="text-xs text-gray-500 hover:underline"
                >
                  Set Default
                </button>
              )}
            </li>
          ))}
        </ul>
        <form onSubmit={handleCreatePipeline} className="flex gap-2">
          <input
            placeholder="New pipeline name"
            value={newPipelineName}
            onChange={(e) => setNewPipelineName(e.target.value)}
            className="flex-1 border border-gray-300 rounded-md px-2 py-1.5 text-sm"
          />
          <button
            type="submit"
            className="px-3 py-1.5 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700"
          >
            Add
          </button>
        </form>
      </section>

      {selectedPipelineId && (
        <section>
          <h2 className="text-sm font-semibold text-gray-700 mb-3 border-b border-gray-200 pb-2">
            Stages — {pipelines.find((p) => p.id === selectedPipelineId)?.name}
          </h2>
          <ul className="space-y-1 mb-3">
            {stages.map((s) => (
              <li
                key={s.id}
                className="flex items-center justify-between text-sm border border-gray-200 rounded-md px-3 py-1.5"
              >
                <span>
                  {s.sequence}. {s.name} ({s.probability}%)
                  {s.is_won_stage && <span className="text-xs text-green-600 ml-1">won</span>}
                  {s.is_lost_stage && <span className="text-xs text-red-600 ml-1">lost</span>}
                </span>
                <button
                  onClick={() => toggleStageActive(s)}
                  className={`text-xs ${s.is_active ? "text-gray-500" : "text-green-600"} hover:underline`}
                >
                  {s.is_active ? "Deactivate" : "Activate"}
                </button>
              </li>
            ))}
          </ul>
          <form onSubmit={handleCreateStage} className="flex gap-2">
            <input
              placeholder="Name"
              value={newStageName}
              onChange={(e) => setNewStageName(e.target.value)}
              className="flex-1 border border-gray-300 rounded-md px-2 py-1.5 text-sm"
            />
            <input
              type="number"
              placeholder="Seq"
              value={newStageSequence}
              onChange={(e) => setNewStageSequence(e.target.value)}
              className="w-20 border border-gray-300 rounded-md px-2 py-1.5 text-sm"
            />
            <input
              type="number"
              placeholder="Prob %"
              value={newStageProbability}
              onChange={(e) => setNewStageProbability(e.target.value)}
              className="w-24 border border-gray-300 rounded-md px-2 py-1.5 text-sm"
            />
            <button
              type="submit"
              className="px-3 py-1.5 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700"
            >
              Add
            </button>
          </form>
        </section>
      )}
    </div>
  );
}
