"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { listLeads, listLeadSources, type LeadRead, type LeadSourceRead } from "@/lib/api/crm";
import { classifyCrmError, getCompanyId, type CrmErrorState } from "@/components/crm/apiErrors";
import CrmStateBanner from "@/components/crm/CrmStateBanner";
import StatusBadge from "@/components/crm/StatusBadge";
import Pagination from "@/components/crm/Pagination";
import { useCrmPermissions, useHasCrmPermission } from "@/hooks/crm/useCrmPermissions";

const PAGE_SIZE = 20;

function leadDisplayName(lead: LeadRead): string {
  const personal = [lead.first_name, lead.last_name].filter(Boolean).join(" ");
  return personal || lead.lead_company_name || "(unnamed lead)";
}

export default function LeadsPage() {
  const [leads, setLeads] = useState<LeadRead[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [errorState, setErrorState] = useState<CrmErrorState | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [sources, setSources] = useState<LeadSourceRead[]>([]);

  const companyId = getCompanyId();
  const permissionsState = useCrmPermissions();
  const canCreateLead = useHasCrmPermission(permissionsState, "crm.leads.create");

  const load = useCallback(async () => {
    if (!companyId) return;
    setLoading(true);
    setErrorState(null);
    try {
      const res = await listLeads(companyId, {
        ...(search ? { search } : {}),
        ...(statusFilter ? { status: statusFilter } : {}),
        ...(sourceFilter ? { source_id: sourceFilter } : {}),
        page,
        page_size: PAGE_SIZE,
      });
      setLeads(res.data?.items ?? []);
      setTotal(res.data?.total ?? 0);
    } catch (err) {
      setErrorState(classifyCrmError(err));
      setLeads([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [companyId, search, statusFilter, sourceFilter, page]);

  useEffect(() => {
    if (!companyId) return;
    listLeadSources(companyId)
      .then((res) => setSources(res.data?.items ?? []))
      .catch(() => setSources([]));
  }, [companyId]);

  useEffect(() => {
    load();
  }, [load]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Leads</h1>
          <p className="text-sm text-gray-500 mt-1">{total} total records</p>
        </div>
        {canCreateLead && (
          <Link
            href="leads/new"
            className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 text-sm font-medium"
          >
            New Lead
          </Link>
        )}
      </div>

      <div className="mb-4 flex flex-wrap gap-3">
        <input
          type="search"
          placeholder="Search leads…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="border border-gray-300 rounded-md px-3 py-1.5 text-sm w-56"
        />
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
        >
          <option value="">All Statuses</option>
          <option value="NEW">New</option>
          <option value="CONTACTED">Contacted</option>
          <option value="QUALIFIED">Qualified</option>
          <option value="UNQUALIFIED">Unqualified</option>
          <option value="CONVERTED">Converted</option>
          <option value="LOST">Lost</option>
        </select>
        <select
          value={sourceFilter}
          onChange={(e) => {
            setSourceFilter(e.target.value);
            setPage(1);
          }}
          className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
        >
          <option value="">All Sources</option>
          {sources.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      {errorState && <CrmStateBanner state={errorState} />}

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading…</div>
      ) : leads.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          {errorState
            ? null
            : (
              <>
                No leads found.{" "}
                {canCreateLead && (
                  <Link href="leads/new" className="text-indigo-600 hover:underline">
                    Capture the first one.
                  </Link>
                )}
              </>
            )}
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
                  Contact
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Score
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Next Follow-up
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {leads.map((lead) => (
                <tr key={lead.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    {leadDisplayName(lead)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {lead.email || lead.phone || "—"}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={lead.status} />
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">{lead.score ?? "—"}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {lead.next_follow_up_date ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`leads/${lead.id}`}
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
    </div>
  );
}
