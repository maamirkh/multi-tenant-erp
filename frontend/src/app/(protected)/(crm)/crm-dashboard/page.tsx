"use client";

import { useState, useEffect, useCallback } from "react";
import { getCrmDashboard, type CrmDashboard } from "@/lib/api/crm";
import { classifyCrmError, getCompanyId, type CrmErrorState } from "@/components/crm/apiErrors";
import CrmStateBanner from "@/components/crm/CrmStateBanner";
import KpiTile from "@/components/crm/KpiTile";

function pct(value: string | null): string {
  return value === null ? "—" : `${value}%`;
}

export default function CrmDashboardPage() {
  const companyId = getCompanyId();
  const [dashboard, setDashboard] = useState<CrmDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorState, setErrorState] = useState<CrmErrorState | null>(null);

  const load = useCallback(async () => {
    if (!companyId) return;
    setLoading(true);
    setErrorState(null);
    try {
      const res = await getCrmDashboard(companyId);
      setDashboard(res.data);
    } catch (err) {
      setErrorState(classifyCrmError(err));
    } finally {
      setLoading(false);
    }
  }, [companyId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">CRM Dashboard</h1>
      {dashboard && (
        <p className="text-sm text-gray-500 mb-6">
          Period: {dashboard.period_from} – {dashboard.period_to}
        </p>
      )}

      {errorState && <CrmStateBanner state={errorState} />}

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading…</div>
      ) : dashboard ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiTile label="Open Pipeline Value" value={dashboard.open_pipeline_value} />
          <KpiTile label="Weighted Pipeline Value" value={dashboard.weighted_pipeline_value} />
          <KpiTile label="Lead Count" value={String(dashboard.lead_count)} />
          <KpiTile label="Conversion Rate" value={pct(dashboard.conversion_rate)} />
          <KpiTile label="Win Rate" value={pct(dashboard.win_rate)} />
          <KpiTile label="Overdue Follow-ups" value={String(dashboard.overdue_follow_up_count)} />
          <KpiTile label="Activities Completed" value={String(dashboard.activities_completed)} />
        </div>
      ) : null}
    </div>
  );
}
