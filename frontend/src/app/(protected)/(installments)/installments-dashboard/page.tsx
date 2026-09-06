"use client";

import { useQuery } from "@tanstack/react-query";
import { getInstallmentDashboard } from "@/lib/api/installments";
import { getCompanyId, classifyInstallmentsError } from "@/components/installments/apiErrors";
import InstallmentsStateBanner from "@/components/installments/InstallmentsStateBanner";
import { LoadingState } from "@/components/platform-admin/DataState";

function KpiTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-gray-200 rounded-md p-4">
      <div className="text-xs text-gray-500 uppercase tracking-wide">{label}</div>
      <div className="text-xl font-semibold text-gray-900 mt-1">{value}</div>
    </div>
  );
}

export default function InstallmentsDashboardPage() {
  const companyId = getCompanyId();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["installmentsDashboard", companyId],
    queryFn: async () => (await getInstallmentDashboard(companyId)).data,
    enabled: companyId !== "",
  });

  const errorState = isError ? classifyInstallmentsError(error) : null;

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Installments Dashboard</h1>

      {errorState && <InstallmentsStateBanner state={errorState} />}

      {isLoading ? (
        <LoadingState label="Loading dashboard…" />
      ) : data ? (
        <>
          <div className="grid grid-cols-4 gap-4 mb-6">
            <KpiTile label="Active Contracts" value={String(data.active_contract_count)} />
            <KpiTile label="Outstanding" value={data.outstanding_amount} />
            <KpiTile label="Due Today" value={data.due_today_amount} />
            <KpiTile label="Due This Month" value={data.due_this_month_amount} />
            <KpiTile label="Collected Today" value={data.collected_today_amount} />
            <KpiTile label="Collected This Month" value={data.collected_this_month_amount} />
            <KpiTile label="Overdue Amount" value={data.overdue_amount} />
            <KpiTile label="Overdue Count" value={String(data.overdue_count)} />
            <KpiTile label="Collection Rate" value={`${data.collection_rate}%`} />
            <KpiTile label="Defaulted Balance" value={data.defaulted_balance} />
            <KpiTile label="Written-Off Balance" value={data.written_off_balance} />
            <KpiTile label="Upcoming Receivables" value={data.upcoming_receivables_amount} />
          </div>

          <section className="border border-gray-200 rounded-md p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3 border-b border-gray-200 pb-2">
              Aging Distribution
            </h2>
            <div className="grid grid-cols-5 gap-2 text-xs">
              {Object.entries(data.aging_distribution).map(([bucket, amount]) => (
                <div key={bucket} className="border border-gray-200 rounded p-2 text-center">
                  <div className="text-gray-500">{bucket}</div>
                  <div className="font-medium">{amount}</div>
                </div>
              ))}
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
