"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  generateInstallmentSettlementQuote,
  executeInstallmentSettlement,
  newIdempotencyKey,
  type InstallmentSettlementQuoteRead,
} from "@/lib/api/installments";
import {
  InstallmentSettlementExecuteSchema,
  type InstallmentSettlementExecuteFormData,
} from "@/schemas/installments";
import { getCompanyId, classifyInstallmentsError, type InstallmentsErrorState } from "@/components/installments/apiErrors";
import InstallmentsStateBanner from "@/components/installments/InstallmentsStateBanner";
import { installmentsKeys } from "@/hooks/installments/queryKeys";
import { useInstallmentsPermissions, useHasInstallmentsPermission } from "@/hooks/installments/useInstallmentsPermissions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PermissionDeniedState } from "@/components/platform-admin/DataState";

const PAYMENT_METHODS = ["CASH", "BANK_TRANSFER", "CHEQUE", "CARD"];

/**
 * Early settlement — quote → execute, contract-detail-adjacent sub-route
 * (mirrors `collect/page.tsx` and `reschedule/page.tsx`'s established
 * pattern). Quote generation is read-only/non-idempotent (deterministic
 * given the same `as_of_date`); execution is idempotency-protected and
 * must resend the quote's own `quoted_amount`/`quoted_as_of_date`
 * unchanged — the backend, never the browser, computes the settlement
 * amount and rejects a mismatch as a stale quote (409
 * `SETTLEMENT_QUOTE_STALE`), surfaced here through the same
 * `InstallmentsStateBanner` every other backend error uses.
 */
export default function SettlementPage() {
  const params = useParams<{ contractId: string }>();
  const contractId = params.contractId;
  const router = useRouter();
  const queryClient = useQueryClient();
  const companyId = getCompanyId();

  const permissionsState = useInstallmentsPermissions();
  const canExecute = useHasInstallmentsPermission(permissionsState, "installments.settlement.execute");

  const [quote, setQuote] = useState<InstallmentSettlementQuoteRead | null>(null);
  const [quoteError, setQuoteError] = useState<InstallmentsErrorState | null>(null);

  const quoteMutation = useMutation({
    mutationFn: async () => (await generateInstallmentSettlementQuote(companyId, contractId)).data,
    onSuccess: (data) => {
      setQuote(data);
      setQuoteError(null);
    },
    onError: (err) => setQuoteError(classifyInstallmentsError(err)),
  });

  const executeMutation = useMutation({
    mutationFn: async (formData: InstallmentSettlementExecuteFormData) => {
      if (!quote) throw new Error("Generate a settlement quote first.");
      return (
        await executeInstallmentSettlement(
          companyId,
          contractId,
          {
            quoted_amount: quote.settlement_amount,
            quoted_as_of_date: quote.as_of_date,
            payment_method: formData.payment_method,
            bank_account_id: formData.bank_account_id || null,
            cash_account_id: formData.cash_account_id || null,
          },
          newIdempotencyKey()
        )
      ).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: installmentsKeys.contract(companyId, contractId),
      });
      void queryClient.invalidateQueries({
        queryKey: installmentsKeys.schedule(companyId, contractId),
      });
      void queryClient.invalidateQueries({
        queryKey: installmentsKeys.collections(companyId, contractId),
      });
      router.push(`../${contractId}`);
    },
  });

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<InstallmentSettlementExecuteFormData>({
    resolver: zodResolver(InstallmentSettlementExecuteSchema),
    defaultValues: { payment_method: "CASH", bank_account_id: "", cash_account_id: "" },
  });
  const paymentMethod = watch("payment_method");

  if (permissionsState.isReady && !canExecute) {
    return (
      <div className="p-6">
        <PermissionDeniedState message="You cannot execute an early settlement for this contract." />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-lg">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Early Settlement</h1>

      {quoteError && <InstallmentsStateBanner state={quoteError} />}
      {executeMutation.isError && (
        <InstallmentsStateBanner state={classifyInstallmentsError(executeMutation.error)} />
      )}

      {!quote ? (
        <Button disabled={quoteMutation.isPending} onClick={() => quoteMutation.mutate()}>
          {quoteMutation.isPending ? "Generating…" : "Generate Settlement Quote"}
        </Button>
      ) : (
        <>
          <div className="border border-gray-200 rounded-md p-4 mb-6 text-sm space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-500">As of</span>
              <span className="text-gray-900">{quote.as_of_date}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Remaining schedule</span>
              <span className="text-gray-900">
                {quote.schedule_outstanding} {quote.currency_code}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Outstanding late charges</span>
              <span className="text-gray-900">
                {quote.late_charge_outstanding} {quote.currency_code}
              </span>
            </div>
            <div className="flex justify-between font-semibold pt-2 border-t border-gray-100">
              <span>Settlement amount</span>
              <span>
                {quote.settlement_amount} {quote.currency_code}
              </span>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="mb-4"
            disabled={quoteMutation.isPending}
            onClick={() => quoteMutation.mutate()}
          >
            Regenerate Quote
          </Button>

          <form
            onSubmit={handleSubmit((data) => executeMutation.mutate(data))}
            className="space-y-4"
          >
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
              <Button type="submit" disabled={executeMutation.isPending}>
                {executeMutation.isPending ? "Executing…" : "Execute Settlement"}
              </Button>
              <Button type="button" variant="outline" onClick={() => router.back()}>
                Cancel
              </Button>
            </div>
          </form>
        </>
      )}
    </div>
  );
}
