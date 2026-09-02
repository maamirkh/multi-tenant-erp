"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listInstallmentContracts,
  approveInstallmentContract,
  rejectInstallmentContract,
  type InstallmentContractSummary,
} from "@/lib/api/installments";
import { getCompanyId, classifyInstallmentsError } from "@/components/installments/apiErrors";
import InstallmentsStateBanner from "@/components/installments/InstallmentsStateBanner";
import StatusBadge from "@/components/installments/StatusBadge";
import { useInstallmentsPermissions, useHasInstallmentsPermission } from "@/hooks/installments/useInstallmentsPermissions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LoadingState, PermissionDeniedState } from "@/components/platform-admin/DataState";

function ApprovalRow({ contract }: { contract: InstallmentContractSummary }) {
  const companyId = getCompanyId();
  const queryClient = useQueryClient();
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const approveMutation = useMutation({
    mutationFn: () => approveInstallmentContract(companyId, contract.id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["contracts"] }),
    onError: (err) => setError(classifyInstallmentsError(err).message),
  });

  const rejectMutation = useMutation({
    mutationFn: () => rejectInstallmentContract(companyId, contract.id, reason),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["contracts"] }),
    onError: (err) => setError(classifyInstallmentsError(err).message),
  });

  return (
    <tr className="hover:bg-gray-50 border-t border-gray-100">
      <td className="px-4 py-3 text-sm font-medium text-gray-900">{contract.contract_number}</td>
      <td className="px-4 py-3">
        <StatusBadge status={contract.status} />
      </td>
      <td className="px-4 py-3 text-sm text-gray-500">
        {contract.contractual_total} {contract.currency_code}
      </td>
      <td className="px-4 py-3">
        {error && <p className="text-xs text-red-600 mb-1">{error}</p>}
        {!rejecting ? (
          <div className="flex gap-2">
            <Button
              size="sm"
              disabled={approveMutation.isPending}
              onClick={() => approveMutation.mutate()}
            >
              Approve
            </Button>
            <Button size="sm" variant="outline" onClick={() => setRejecting(true)}>
              Reject
            </Button>
            <Link href={`../contracts/${contract.id}`} className="text-indigo-600 hover:underline text-sm self-center">
              View
            </Link>
          </div>
        ) : (
          <div className="flex gap-2 items-center">
            <Input
              placeholder="Reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="h-8 w-40"
            />
            <Button
              size="sm"
              disabled={rejectMutation.isPending || !reason}
              onClick={() => rejectMutation.mutate()}
            >
              Confirm Reject
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setRejecting(false)}>
              Cancel
            </Button>
          </div>
        )}
      </td>
    </tr>
  );
}

export default function InstallmentApprovalsPage() {
  const companyId = getCompanyId();
  const permissionsState = useInstallmentsPermissions();
  const canApprove = useHasInstallmentsPermission(permissionsState, "installments.contract.approve");

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["contracts", { status: "PENDING_APPROVAL" }],
    queryFn: async () =>
      (await listInstallmentContracts(companyId, 1, 100, "PENDING_APPROVAL")).data,
    enabled: companyId !== "" && canApprove,
  });

  if (permissionsState.isReady && !canApprove) {
    return (
      <div className="p-6">
        <PermissionDeniedState message="You cannot approve installment contracts." />
      </div>
    );
  }

  const contracts = data?.items ?? [];
  const errorState = isError ? classifyInstallmentsError(error) : null;

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Installment Approvals</h1>
      <p className="text-sm text-gray-500 mb-6">{contracts.length} contract(s) pending approval</p>

      {errorState && <InstallmentsStateBanner state={errorState} />}

      {isLoading ? (
        <LoadingState label="Loading approvals…" />
      ) : contracts.length === 0 ? (
        <div className="text-center py-12 text-gray-500">No contracts pending approval.</div>
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
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {contracts.map((contract) => (
                <ApprovalRow key={contract.id} contract={contract} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
