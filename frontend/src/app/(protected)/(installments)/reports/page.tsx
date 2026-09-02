"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getInstallmentReport, type InstallmentReportType } from "@/lib/api/installments";
import { getCompanyId, classifyInstallmentsError } from "@/components/installments/apiErrors";
import InstallmentsStateBanner from "@/components/installments/InstallmentsStateBanner";
import { useInstallmentsPermissions, useHasInstallmentsPermission } from "@/hooks/installments/useInstallmentsPermissions";
import { LoadingState, PermissionDeniedState } from "@/components/platform-admin/DataState";

const REPORT_TYPES: { value: InstallmentReportType; label: string }[] = [
  { value: "contract-register", label: "Contract Register" },
  { value: "collection", label: "Collection" },
  { value: "due", label: "Due" },
  { value: "overdue", label: "Overdue" },
  { value: "aging", label: "Aging" },
  { value: "settlement", label: "Settlement" },
  { value: "default-writeoff", label: "Default / Write-off" },
  { value: "plan-performance", label: "Plan Performance" },
];

export default function InstallmentReportsPage() {
  const companyId = getCompanyId();
  const [reportType, setReportType] = useState<InstallmentReportType>("contract-register");
  const permissionsState = useInstallmentsPermissions();
  const canView = useHasInstallmentsPermission(permissionsState, "installments.report.view");

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["installmentReport", reportType],
    queryFn: async () => (await getInstallmentReport(companyId, reportType, 1, 100)).data,
    enabled: companyId !== "" && canView,
  });

  if (permissionsState.isReady && !canView) {
    return (
      <div className="p-6">
        <PermissionDeniedState message="You cannot view installment reports." />
      </div>
    );
  }

  const rows = data?.items ?? [];
  const firstRow = rows[0];
  const columns = firstRow ? Object.keys(firstRow).filter((k) => k !== "report_type") : [];
  const errorState = isError ? classifyInstallmentsError(error) : null;

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Installment Reports</h1>
        <select
          value={reportType}
          onChange={(e) => setReportType(e.target.value as InstallmentReportType)}
          className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
        >
          {REPORT_TYPES.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      </div>

      {errorState && <InstallmentsStateBanner state={errorState} />}

      {isLoading ? (
        <LoadingState label="Loading report…" />
      ) : rows.length === 0 ? (
        <div className="text-center py-12 text-gray-500">{errorState ? null : "No rows for this report."}</div>
      ) : (
        <div className="overflow-x-auto shadow ring-1 ring-black ring-opacity-5 rounded-lg">
          <table className="min-w-full divide-y divide-gray-300">
            <thead className="bg-gray-50">
              <tr>
                {columns.map((col) => (
                  <th
                    key={col}
                    className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide"
                  >
                    {col.replace(/_/g, " ")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {rows.map((row, idx) => (
                <tr key={idx} className="hover:bg-gray-50">
                  {columns.map((col) => (
                    <td key={col} className="px-4 py-3 text-sm text-gray-700">
                      {String(row[col] ?? "—")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
