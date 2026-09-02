"use client";

import { useParams, useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  InstallmentCollectionCreateSchema,
  type InstallmentCollectionCreateFormData,
} from "@/schemas/installments";
import { useRecordCollection } from "@/hooks/installments/useRecordCollection";
import { classifyInstallmentsError, type InstallmentsErrorState } from "@/components/installments/apiErrors";
import InstallmentsStateBanner from "@/components/installments/InstallmentsStateBanner";
import { useInstallmentsPermissions, useHasInstallmentsPermission } from "@/hooks/installments/useInstallmentsPermissions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useState } from "react";
import { PermissionDeniedState } from "@/components/platform-admin/DataState";

const PAYMENT_METHODS = ["CASH", "BANK_TRANSFER", "CHEQUE", "CARD"];

export default function RecordCollectionPage() {
  const params = useParams<{ contractId: string }>();
  const contractId = params.contractId;
  const router = useRouter();

  const permissionsState = useInstallmentsPermissions();
  const canCollect = useHasInstallmentsPermission(permissionsState, "installments.collection.create");

  const recordCollection = useRecordCollection(contractId);
  const [errorState, setErrorState] = useState<InstallmentsErrorState | null>(null);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<InstallmentCollectionCreateFormData>({
    resolver: zodResolver(InstallmentCollectionCreateSchema),
    defaultValues: { amount: "", payment_method: "CASH", bank_account_id: "", cash_account_id: "" },
  });

  const paymentMethod = watch("payment_method");

  async function onSubmit(data: InstallmentCollectionCreateFormData) {
    setErrorState(null);
    try {
      await recordCollection.mutateAsync({
        amount: data.amount,
        payment_method: data.payment_method,
        bank_account_id: data.bank_account_id || null,
        cash_account_id: data.cash_account_id || null,
      });
      router.push(`../${contractId}`);
    } catch (err) {
      setErrorState(classifyInstallmentsError(err));
    }
  }

  if (permissionsState.isReady && !canCollect) {
    return (
      <div className="p-6">
        <PermissionDeniedState message="You cannot record installment collections." />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-lg">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Record Collection</h1>

      {errorState && <InstallmentsStateBanner state={errorState} />}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Amount</label>
          <Input {...register("amount")} />
          {errors.amount && <p className="text-xs text-red-600 mt-1">{errors.amount.message}</p>}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Payment Method</label>
          <select
            {...register("payment_method")}
            className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm h-9"
          >
            {PAYMENT_METHODS.map((m) => (
              <option key={m} value={m}>
                {m.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>

        {paymentMethod === "BANK_TRANSFER" || paymentMethod === "CHEQUE" || paymentMethod === "CARD" ? (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Bank Account ID</label>
            <Input {...register("bank_account_id")} placeholder="Bank account UUID" />
          </div>
        ) : (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Cash Account ID</label>
            <Input {...register("cash_account_id")} placeholder="Cash account UUID" />
          </div>
        )}
        {errors.bank_account_id && (
          <p className="text-xs text-red-600 mt-1">{errors.bank_account_id.message}</p>
        )}

        <div className="flex gap-3 pt-2">
          <Button type="submit" disabled={recordCollection.isPending}>
            {recordCollection.isPending ? "Recording…" : "Record Collection"}
          </Button>
          <Button type="button" variant="outline" onClick={() => router.back()}>
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
}
