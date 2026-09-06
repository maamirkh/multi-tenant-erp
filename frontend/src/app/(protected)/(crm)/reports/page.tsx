"use client";

import { useState, useEffect, useCallback } from "react";
import {
  getPipelineReport,
  getLeadReport,
  getActivityReport,
  type PipelineReport,
  type LeadReport,
  type ActivityReport,
} from "@/lib/api/crm";
import { classifyCrmError, getCompanyId, type CrmErrorState } from "@/components/crm/apiErrors";
import CrmStateBanner from "@/components/crm/CrmStateBanner";
import KpiTile from "@/components/crm/KpiTile";

function pct(value: string | null): string {
  return value === null ? "—" : `${value}%`;
}

export default function CrmReportsPage() {
  const companyId = getCompanyId();

  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [pipeline, setPipeline] = useState<PipelineReport | null>(null);
  const [leads, setLeads] = useState<LeadReport | null>(null);
  const [activities, setActivities] = useState<ActivityReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorState, setErrorState] = useState<CrmErrorState | null>(null);

  const load = useCallback(async () => {
    if (!companyId) return;
    setLoading(true);
    setErrorState(null);
    try {
      const [pipelineRes, leadRes, activityRes] = await Promise.all([
        getPipelineReport(companyId, dateFrom || undefined, dateTo || undefined),
        getLeadReport(companyId, dateFrom || undefined, dateTo || undefined),
        getActivityReport(companyId, dateFrom || undefined, dateTo || undefined),
      ]);
      setPipeline(pipelineRes.data);
      setLeads(leadRes.data);
      setActivities(activityRes.data);
    } catch (err) {
      setErrorState(classifyCrmError(err));
    } finally {
      setLoading(false);
    }
  }, [companyId, dateFrom, dateTo]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">CRM Reports</h1>

      <div className="mb-6 flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">From</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">To</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
          />
        </div>
      </div>

      {errorState && <CrmStateBanner state={errorState} />}

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading…</div>
      ) : (
        <div className="space-y-8">
          {pipeline && (
            <section>
              <h2 className="text-sm font-semibold text-gray-700 mb-3 border-b border-gray-200 pb-2">
                Pipeline Report
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <KpiTile label="Won Value" value={pipeline.won_value} />
                <KpiTile label="Lost Value" value={pipeline.lost_value} />
                <KpiTile label="Win Rate" value={pct(pipeline.win_rate)} />
                <KpiTile label="Avg Deal Size" value={pipeline.avg_deal_size ?? "—"} />
                <KpiTile
                  label="Avg Sales Cycle (days)"
                  value={pipeline.avg_sales_cycle_days ?? "—"}
                />
              </div>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                    Value by Stage
                  </h3>
                  <ul className="space-y-1">
                    {pipeline.value_by_stage.map((s) => (
                      <li key={s.stage_id} className="flex justify-between">
                        <span className="text-gray-500 truncate">{s.stage_id}</span>
                        <span className="text-gray-900">{s.value}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                    Value by Owner
                  </h3>
                  <ul className="space-y-1">
                    {pipeline.value_by_owner.map((o) => (
                      <li key={o.owner_id} className="flex justify-between">
                        <span className="text-gray-500 truncate">{o.owner_id}</span>
                        <span className="text-gray-900">{o.value}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                    Value by Source
                  </h3>
                  <ul className="space-y-1">
                    {pipeline.value_by_source.map((s) => (
                      <li key={s.source_id ?? "none"} className="flex justify-between">
                        <span className="text-gray-500 truncate">{s.source_id ?? "(none)"}</span>
                        <span className="text-gray-900">{s.value}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </section>
          )}

          {leads && (
            <section>
              <h2 className="text-sm font-semibold text-gray-700 mb-3 border-b border-gray-200 pb-2">
                Lead Report
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <KpiTile label="Total Leads" value={String(leads.total_count)} />
                <KpiTile label="Conversion Rate" value={pct(leads.conversion_rate)} />
                <KpiTile
                  label="Qualified-to-Close Rate"
                  value={pct(leads.qualified_to_close_rate)}
                />
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">By Status</h3>
                  <ul className="space-y-1">
                    {Object.entries(leads.count_by_status).map(([status, count]) => (
                      <li key={status} className="flex justify-between">
                        <span className="text-gray-500">{status}</span>
                        <span className="text-gray-900">{count}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">By Source</h3>
                  <ul className="space-y-1">
                    {Object.entries(leads.count_by_source).map(([source, count]) => (
                      <li key={source} className="flex justify-between">
                        <span className="text-gray-500 truncate">{source}</span>
                        <span className="text-gray-900">{count}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </section>
          )}

          {activities && (
            <section>
              <h2 className="text-sm font-semibold text-gray-700 mb-3 border-b border-gray-200 pb-2">
                Activity Report
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <KpiTile label="Completed" value={String(activities.completed_count)} />
                <KpiTile label="Overdue" value={String(activities.overdue_count)} />
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                    Completed by Type
                  </h3>
                  <ul className="space-y-1">
                    {Object.entries(activities.completed_by_type).map(([type, count]) => (
                      <li key={type} className="flex justify-between">
                        <span className="text-gray-500">{type}</span>
                        <span className="text-gray-900">{count}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                    Overdue by Owner
                  </h3>
                  <ul className="space-y-1">
                    {Object.entries(activities.overdue_by_owner).map(([owner, count]) => (
                      <li key={owner} className="flex justify-between">
                        <span className="text-gray-500 truncate">{owner}</span>
                        <span className="text-gray-900">{count}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
