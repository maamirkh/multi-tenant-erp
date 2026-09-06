"use client";

import { useState } from "react";
import Link from "next/link";
import { useContracts } from "@/hooks/installments/useContracts";
import { useInstallmentsPermissions, useHasInstallmentsPermission } from "@/hooks/installments/useInstallmentsPermissions";
import { classifyInstallmentsError, getCompanyId } from "@/components/installments/apiErrors";
import InstallmentsStateBanner from "@/components/installments/InstallmentsStateBanner";
import StatusBadge from "@/components/installments/StatusBadge";

const PAGE_SIZE = 20;

export default function InstallmentContractsPage() {
  const [page, setPage] = useState(1);
  const companyId = getCompanyId();
  const permissionsState = useInstallmentsPermissions();
  const canCreateContract = useHasInstallmentsPermission(
    permissionsState,
    "installments.contract.create"
  );

  const { data, isLoading, isError, error } = useContracts({ page, page_size: PAGE_SIZE });
  const contracts = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.pages ?? 0;
  const errorState = isError ? classifyInstallmentsError(error) : null;

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Installment Contracts</h1>
          <p className="text-sm text-gray-500 mt-1">{total} total records</p>
        </div>
        {canCreateContract && (
          <Link
            href="contracts/new"
            className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 text-sm font-medium"
          >
            New Contract
          </Link>
        )}
      </div>

      {errorState && <InstallmentsStateBanner state={errorState} />}
      {!companyId && !errorState && (
        <p className="text-sm text-gray-500">Select a company to view installment contracts.</p>
      )}

      {isLoading ? (
        <div className="text-center py-12 text-gray-500">Loading…</div>
      ) : contracts.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          {errorState ? null : "No installment contracts found."}
        </div>
      ) : (
        <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 rounded-lg">
          <table className="min-w-full divide-y divide-gray-300">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Contract #
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Total
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Created
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {contracts.map((contract) => (
                <tr key={contract.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    {contract.contract_number}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={contract.status} />
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {contract.contractual_total} {contract.currency_code}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {new Date(contract.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`contracts/${contract.id}`}
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

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between text-sm text-gray-600">
          <span>
            Page {page} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1 border rounded disabled:opacity-40 hover:bg-gray-50"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1 border rounded disabled:opacity-40 hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
