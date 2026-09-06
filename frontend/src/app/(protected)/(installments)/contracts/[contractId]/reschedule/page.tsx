"use client";

import { useParams, useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  InstallmentRescheduleSchema,
  type InstallmentRescheduleFormData,
} from "@/schemas/installments";
import { useRescheduleContract } from "@/hooks/installments/useRescheduleContract";
import { classifyInstallmentsError, type InstallmentsErrorState } from "@/components/installments/apiErrors";
import InstallmentsStateBanner from "@/components/installments/InstallmentsStateBanner";
import { useInstallmentsPermissions, useHasInstallmentsPermission } from "@/hooks/installments/useInstallmentsPermissions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useState } from "react";
import { PermissionDeniedState } from "@/components/platform-admin/DataState";

export default function RescheduleContractPage() {
  const params = useParams<{ contractId: string }>();
  const contractId = params.contractId;
  const router = useRouter();

  const permissionsState = useInstallmentsPermissions();
  const canReschedule = useHasInstallmentsPermission(
    permissionsState,
    "installments.contract.reschedule"
  );

  const reschedule = useRescheduleContract(contractId);
  const [errorState, setErrorState] = useState<InstallmentsErrorState | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<InstallmentRescheduleFormData>({
    resolver: zodResolver(InstallmentRescheduleSchema),
    defaultValues: { first_due_date: "", reason: "", requested_by: "" },
  });

  async function onSubmit(data: InstallmentRescheduleFormData) {
    setErrorState(null);
    try {
      await reschedule.mutateAsync({
        first_due_date: data.first_due_date,
        reason: data.reason,
        requested_by: data.requested_by,
      });
      router.push(`../${contractId}`);
    } catch (err) {
      setErrorState(classifyInstallmentsError(err));
    }
  }

  if (permissionsState.isReady && !canReschedule) {
    return (
      <div className="p-6">
        <PermissionDeniedState message="You cannot reschedule installment contracts." />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-lg">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Reschedule Contract</h1>
      <p className="text-sm text-gray-500 mb-4">
        Controlled due-date-only amendment — creates a new schedule version. Principal, markup,
        and installment count cannot be changed here.
      </p>

      {errorState && <InstallmentsStateBanner state={errorState} />}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">New First Due Date</label>
          <Input type="date" {...register("first_due_date")} />
          {errors.first_due_date && (
            <p className="text-xs text-red-600 mt-1">{errors.first_due_date.message}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Requested By (user ID, must differ from you — maker-checker)
          </label>
          <Input {...register("requested_by")} placeholder="Requester user UUID" />
          {errors.requested_by && (
            <p className="text-xs text-red-600 mt-1">{errors.requested_by.message}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Reason</label>
          <textarea
            {...register("reason")}
            rows={3}
            className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm"
          />
          {errors.reason && <p className="text-xs text-red-600 mt-1">{errors.reason.message}</p>}
        </div>

        <div className="flex gap-3 pt-2">
          <Button type="submit" disabled={reschedule.isPending}>
            {reschedule.isPending ? "Saving…" : "Reschedule"}
          </Button>
          <Button type="button" variant="outline" onClick={() => router.back()}>
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
}
