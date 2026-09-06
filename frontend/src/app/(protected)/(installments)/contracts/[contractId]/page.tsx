"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useContract } from "@/hooks/installments/useContract";
import { useSchedule } from "@/hooks/installments/useSchedule";
import { useCollections } from "@/hooks/installments/useCollections";
import { useDelinquency } from "@/hooks/installments/useDelinquency";
import { useAuditHistory } from "@/hooks/installments/useAuditHistory";
import { useContractLifecycleActions } from "@/hooks/installments/useContractLifecycleActions";
import { useReverseCollection } from "@/hooks/installments/useReverseCollection";
import {
  getInstallmentAgreementDocument,
  getInstallmentScheduleDocument,
  type InstallmentAgreementView,
  type InstallmentScheduleDocument,
} from "@/lib/api/installments";
import { getCompanyId } from "@/components/installments/apiErrors";
import { useInstallmentsPermissions, useHasInstallmentsPermission } from "@/hooks/installments/useInstallmentsPermissions";
import { classifyInstallmentsError } from "@/components/installments/apiErrors";
import InstallmentsStateBanner from "@/components/installments/InstallmentsStateBanner";
import StatusBadge from "@/components/installments/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  LoadingState,
  ErrorState,
  PermissionDeniedState,
  messageFromError,
  isForbidden,
} from "@/components/platform-admin/DataState";
import type { InstallmentContractStatus } from "@/lib/api/installments";

function ReasonAction({
  label,
  pending,
  onConfirm,
}: {
  label: string;
  pending: boolean;
  onConfirm: (reason: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");

  if (!open) {
    return (
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        {label}
      </Button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <Input
        placeholder="Reason (required)"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        className="w-48 h-8"
      />
      <Button
        size="sm"
        disabled={pending || !reason}
        onClick={() => {
          onConfirm(reason);
          setOpen(false);
          setReason("");
        }}
      >
        Confirm {label}
      </Button>
      <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
        Cancel
      </Button>
    </div>
  );
}

export default function InstallmentContractDetailPage() {
  const params = useParams<{ contractId: string }>();
  const contractId = params.contractId;

  const permissionsState = useInstallmentsPermissions();
  const canCreate = useHasInstallmentsPermission(permissionsState, "installments.contract.create");
  const canApprove = useHasInstallmentsPermission(permissionsState, "installments.contract.approve");
  const canActivate = useHasInstallmentsPermission(permissionsState, "installments.contract.activate");
  const canCancel = useHasInstallmentsPermission(permissionsState, "installments.contract.cancel");
  const canDefault = useHasInstallmentsPermission(permissionsState, "installments.contract.default");
  const canCure = useHasInstallmentsPermission(permissionsState, "installments.contract.cure");
  const canWriteoff = useHasInstallmentsPermission(permissionsState, "installments.contract.writeoff");
  const canReverse = useHasInstallmentsPermission(permissionsState, "installments.collection.reverse");
  const canSettle = useHasInstallmentsPermission(permissionsState, "installments.settlement.execute");
  const canCollect = useHasInstallmentsPermission(permissionsState, "installments.collection.create");
  const canReschedule = useHasInstallmentsPermission(permissionsState, "installments.contract.reschedule");

  const contractQuery = useContract(contractId);
  const scheduleQuery = useSchedule(contractId);
  const collectionsQuery = useCollections(contractId);
  const delinquencyQuery = useDelinquency(contractId);
  const auditQuery = useAuditHistory(contractId);
  const actions = useContractLifecycleActions(contractId ?? "");
  const reverseCollection = useReverseCollection(contractId ?? "");
  const [agreement, setAgreement] = useState<InstallmentAgreementView | null>(null);
  const [scheduleDoc, setScheduleDoc] = useState<InstallmentScheduleDocument | null>(null);
  const [docError, setDocError] = useState<string | null>(null);
  const companyId = getCompanyId();

  if (contractQuery.isLoading) {
    return (
      <div className="p-6">
        <LoadingState label="Loading contract…" />
      </div>
    );
  }

  if (contractQuery.isError) {
    if (isForbidden(contractQuery.error)) {
      const state = classifyInstallmentsError(contractQuery.error);
      if (state.featureDisabled) {
        return (
          <div className="p-6">
            <InstallmentsStateBanner state={state} />
          </div>
        );
      }
      return (
        <div className="p-6">
          <PermissionDeniedState message="You cannot view this installment contract." />
        </div>
      );
    }
    return (
      <div className="p-6">
        <ErrorState
          message={messageFromError(contractQuery.error)}
          onRetry={() => contractQuery.refetch()}
        />
      </div>
    );
  }

  const contract = contractQuery.data;
  if (!contract) return null;

  const status: InstallmentContractStatus = contract.status;

  return (
    <div className="p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
            {contract.contract_number}
            <StatusBadge status={status} />
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {contract.contractual_total} {contract.currency_code}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          {status === "DRAFT" && canCreate && (
            <Button size="sm" disabled={actions.submit.isPending} onClick={() => actions.submit.mutate()}>
              Submit
            </Button>
          )}
          {status === "PENDING_APPROVAL" && canApprove && (
            <Button size="sm" disabled={actions.approve.isPending} onClick={() => actions.approve.mutate()}>
              Approve
            </Button>
          )}
          {status === "PENDING_APPROVAL" && canApprove && (
            <ReasonAction
              label="Reject"
              pending={actions.reject.isPending}
              onConfirm={(reason) => actions.reject.mutate(reason)}
            />
          )}
          {status === "APPROVED" && canActivate && (
            <Button size="sm" disabled={actions.activate.isPending} onClick={() => actions.activate.mutate()}>
              Activate
            </Button>
          )}
          {status === "ACTIVE" && (
            <>
              {canCollect && (
                <Link href={`${contractId}/collect`}>
                  <Button size="sm" variant="outline">
                    Record Collection
                  </Button>
                </Link>
              )}
              {canReschedule && (
                <Link href={`${contractId}/reschedule`}>
                  <Button size="sm" variant="outline">
                    Reschedule
                  </Button>
                </Link>
              )}
              {canSettle && (
                <Link href={`${contractId}/settlement`}>
                  <Button size="sm" variant="outline">
                    Settle Early
                  </Button>
                </Link>
              )}
            </>
          )}
          {status === "ACTIVE" && canDefault && (
            <ReasonAction
              label="Mark Defaulted"
              pending={actions.markDefaulted.isPending}
              onConfirm={(reason) => actions.markDefaulted.mutate(reason)}
            />
          )}
          {status === "DEFAULTED" && canCure && (
            <Button size="sm" disabled={actions.cure.isPending} onClick={() => actions.cure.mutate(undefined)}>
              Cure
            </Button>
          )}
          {status === "DEFAULTED" && canWriteoff && (
            <ReasonAction
              label="Write Off"
              pending={actions.writeoff.isPending}
              onConfirm={(reason) => actions.writeoff.mutate(reason)}
            />
          )}
          {["DRAFT", "PENDING_APPROVAL", "APPROVED", "ACTIVE"].includes(status) && canCancel && (
            <ReasonAction
              label="Cancel"
              pending={actions.cancel.isPending}
              onConfirm={(reason) => actions.cancel.mutate({ reason })}
            />
          )}
        </div>
      </div>

      {(actions.submit.isError ||
        actions.approve.isError ||
        actions.reject.isError ||
        actions.activate.isError ||
        actions.cure.isError ||
        actions.cancel.isError ||
        actions.markDefaulted.isError ||
        actions.writeoff.isError) && (
        <InstallmentsStateBanner
          state={classifyInstallmentsError(
            actions.submit.error ??
              actions.approve.error ??
              actions.reject.error ??
              actions.activate.error ??
              actions.cure.error ??
              actions.cancel.error ??
              actions.markDefaulted.error ??
              actions.writeoff.error
          )}
        />
      )}

      <div className="grid grid-cols-3 gap-4 mb-6 text-sm">
        <div className="border border-gray-200 rounded-md p-3">
          <span className="text-gray-500">Principal</span>
          <div className="text-gray-900 font-medium">{contract.principal_amount}</div>
        </div>
        <div className="border border-gray-200 rounded-md p-3">
          <span className="text-gray-500">Down Payment</span>
          <div className="text-gray-900 font-medium">{contract.down_payment_amount}</div>
        </div>
        <div className="border border-gray-200 rounded-md p-3">
          <span className="text-gray-500">Installments</span>
          <div className="text-gray-900 font-medium">
            {contract.installment_count} × {contract.frequency}
          </div>
        </div>
      </div>

      <section className="mb-6 border border-gray-200 rounded-md p-4">
        <h2 className="text-sm font-semibold text-gray-700 mb-3 border-b border-gray-200 pb-2">Terms</h2>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-gray-500">Contract Date</span>
            <div className="text-gray-900">{contract.contract_date}</div>
          </div>
          <div>
            <span className="text-gray-500">Maturity Date</span>
            <div className="text-gray-900">{contract.maturity_date}</div>
          </div>
          <div>
            <span className="text-gray-500">First Due Date</span>
            <div className="text-gray-900">{contract.first_due_date}</div>
          </div>
          <div>
            <span className="text-gray-500">Markup</span>
            <div className="text-gray-900">{contract.markup_amount}</div>
          </div>
        </div>
      </section>

      <section className="mb-6 border border-gray-200 rounded-md p-4">
        <h2 className="text-sm font-semibold text-gray-700 mb-3 border-b border-gray-200 pb-2">Schedule</h2>
        {scheduleQuery.isLoading ? (
          <p className="text-sm text-gray-500">Loading…</p>
        ) : scheduleQuery.isError ? (
          <p className="text-sm text-gray-500">No schedule yet (contract not activated).</p>
        ) : (
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 uppercase">
                <th className="py-1 pr-4">#</th>
                <th className="py-1 pr-4">Due Date</th>
                <th className="py-1 pr-4">Amount</th>
                <th className="py-1 pr-4">Status</th>
              </tr>
            </thead>
            <tbody>
              {(scheduleQuery.data?.lines ?? []).map((line) => (
                <tr key={line.sequence} className="border-t border-gray-100">
                  <td className="py-1 pr-4">{line.sequence}</td>
                  <td className="py-1 pr-4">{line.due_date}</td>
                  <td className="py-1 pr-4">{line.scheduled_amount}</td>
                  <td className="py-1 pr-4">
                    {line.voided_at ? "VOIDED" : line.waived_at ? "WAIVED" : "SCHEDULED"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="mb-6 border border-gray-200 rounded-md p-4">
        <h2 className="text-sm font-semibold text-gray-700 mb-3 border-b border-gray-200 pb-2">Payments</h2>
        {reverseCollection.isError && (
          <InstallmentsStateBanner state={classifyInstallmentsError(reverseCollection.error)} />
        )}
        {collectionsQuery.isLoading ? (
          <p className="text-sm text-gray-500">Loading…</p>
        ) : (collectionsQuery.data ?? []).length === 0 ? (
          <p className="text-sm text-gray-500">No collections recorded yet.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {(collectionsQuery.data ?? []).map((row, idx) => {
              // `reverse_collection`'s `collection_id` path param is the
              // Accounting Payment.id the original collection created
              // (`collection_service.py::reverse_collection`'s own
              // docstring) — exactly `accounting_payment_id` here, not a
              // separate "collection" primary key (the report row has
              // none).
              const paymentId = row["accounting_payment_id"];
              const isReversal = row["is_reversal"] === true;
              return (
                <li
                  key={idx}
                  className="flex items-center justify-between border-b border-gray-100 pb-2 last:border-0 last:pb-0"
                >
                  <div>
                    <span className={isReversal ? "text-red-700" : "text-gray-900"}>
                      {isReversal ? "Reversal — " : ""}
                      {String(row["allocated_amount"] ?? "—")}
                    </span>
                    <span className="text-gray-500 ml-2">
                      {String(row["allocated_at"] ?? "—")}
                      {row["payment_method"] ? ` · ${String(row["payment_method"])}` : ""}
                    </span>
                  </div>
                  {canReverse && !isReversal && typeof paymentId === "string" && (
                    <ReasonAction
                      label="Reverse"
                      pending={reverseCollection.isPending}
                      onConfirm={(reason) =>
                        reverseCollection.mutate({ collectionId: paymentId, reason })
                      }
                    />
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="mb-6 border border-gray-200 rounded-md p-4">
        <h2 className="text-sm font-semibold text-gray-700 mb-3 border-b border-gray-200 pb-2">Delinquency</h2>
        {delinquencyQuery.isLoading ? (
          <p className="text-sm text-gray-500">Loading…</p>
        ) : (delinquencyQuery.data ?? []).length === 0 ? (
          <p className="text-sm text-gray-500">No overdue installments.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {(delinquencyQuery.data ?? []).map((row, idx) => (
              <li key={idx} className="flex justify-between text-red-700">
                <span>Due {String(row["due_date"])}</span>
                <span>
                  {String(row["outstanding_amount"])} ({String(row["days_overdue"])} days overdue)
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mb-6 border border-gray-200 rounded-md p-4">
        <h2 className="text-sm font-semibold text-gray-700 mb-3 border-b border-gray-200 pb-2">Audit History</h2>
        {auditQuery.isLoading ? (
          <p className="text-sm text-gray-500">Loading…</p>
        ) : (auditQuery.data ?? []).length === 0 ? (
          <p className="text-sm text-gray-500">No audit entries yet.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {(auditQuery.data ?? []).map((entry) => (
              <li key={entry.id} className="flex justify-between">
                <span className="font-medium text-gray-900">{entry.action}</span>
                <span className="text-gray-500">{new Date(entry.occurred_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mb-6 border border-gray-200 rounded-md p-4">
        <h2 className="text-sm font-semibold text-gray-700 mb-3 border-b border-gray-200 pb-2">Documents</h2>
        {docError && (
          <InstallmentsStateBanner state={{ message: docError, forbidden: false, featureDisabled: false }} />
        )}
        <div className="flex gap-3 mb-3">
          <Button
            size="sm"
            variant="outline"
            onClick={async () => {
              setDocError(null);
              try {
                const res = await getInstallmentAgreementDocument(companyId, contractId!);
                setAgreement(res.data);
              } catch (err) {
                setDocError(messageFromError(err));
              }
            }}
          >
            View Agreement
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={async () => {
              setDocError(null);
              try {
                const res = await getInstallmentScheduleDocument(companyId, contractId!);
                setScheduleDoc(res.data);
              } catch (err) {
                setDocError(messageFromError(err));
              }
            }}
          >
            View Schedule Document
          </Button>
        </div>
        {agreement && (
          <div className="text-sm bg-gray-50 border border-gray-200 rounded p-3 mb-3">
            <p>Contract: {agreement.contract_number}</p>
            <p>Total: {agreement.contractual_total} {agreement.currency_code}</p>
            <p>Status: {agreement.status}</p>
          </div>
        )}
        {scheduleDoc && (
          <div className="text-sm bg-gray-50 border border-gray-200 rounded p-3">
            <p>Version {scheduleDoc.version_number} — {scheduleDoc.lines.length} lines</p>
          </div>
        )}
      </section>
    </div>
  );
}
