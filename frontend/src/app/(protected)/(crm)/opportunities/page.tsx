"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { listOpportunities, listPipelines, type OpportunityRead, type PipelineRead } from "@/lib/api/crm";
import { classifyCrmError, getCompanyId, type CrmErrorState } from "@/components/crm/apiErrors";
import CrmStateBanner from "@/components/crm/CrmStateBanner";
import StatusBadge from "@/components/crm/StatusBadge";
import Pagination from "@/components/crm/Pagination";

const PAGE_SIZE = 20;

export default function OpportunitiesPage() {
  const [opportunities, setOpportunities] = useState<OpportunityRead[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [errorState, setErrorState] = useState<CrmErrorState | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [pipelines, setPipelines] = useState<PipelineRead[]>([]);

  const companyId = getCompanyId();

  const load = useCallback(async () => {
    if (!companyId) return;
    setLoading(true);
    setErrorState(null);
    try {
      const res = await listOpportunities(companyId, {
        ...(statusFilter ? { status: statusFilter } : {}),
        page,
        page_size: PAGE_SIZE,
      });
      setOpportunities(res.data?.items ?? []);
      setTotal(res.data?.total ?? 0);
    } catch (err) {
      setErrorState(classifyCrmError(err));
      setOpportunities([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [companyId, statusFilter, page]);

  useEffect(() => {
    if (!companyId) return;
    listPipelines(companyId)
      .then((res) => setPipelines(res.data ?? []))
      .catch(() => setPipelines([]));
  }, [companyId]);

  useEffect(() => {
    load();
  }, [load]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Opportunities</h1>
          <p className="text-sm text-gray-500 mt-1">{total} total records</p>
        </div>
        <Link
          href="opportunities/pipeline"
          className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 text-sm font-medium"
        >
          Pipeline View
        </Link>
      </div>

      <div className="mb-4 flex flex-wrap gap-3">
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
        >
          <option value="">All Statuses</option>
          <option value="OPEN">Open</option>
          <option value="WON">Won</option>
          <option value="LOST">Lost</option>
        </select>
      </div>

      {errorState && <CrmStateBanner state={errorState} />}

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading…</div>
      ) : opportunities.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          {errorState ? null : "No opportunities found."}
        </div>
      ) : (
        <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 rounded-lg">
          <table className="min-w-full divide-y divide-gray-300">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Value
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Probability
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Expected Close
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {opportunities.map((o) => (
                <tr key={o.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">{o.name}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {o.value} {o.currency_code}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">{o.probability}%</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={o.status} />
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {o.expected_close_date ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`opportunities/${o.id}`}
                      className="text-indigo-600 hover:text-indigo-700 text-sm font-medium"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Pagination page={page} totalPages={totalPages} onChange={setPage} />

      {pipelines.length === 0 && !loading && (
        <p className="mt-4 text-xs text-gray-400">
          No pipelines configured yet — set one up in CRM Settings.
        </p>
      )}
    </div>
  );
}
