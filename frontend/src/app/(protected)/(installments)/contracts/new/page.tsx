"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  InstallmentContractCreateSchema,
  INSTALLMENT_SUPPORTED_FREQUENCIES,
  type InstallmentContractCreateFormData,
} from "@/schemas/installments";
import {
  previewInstallmentQuote,
  type InstallmentQuotePreviewRead,
} from "@/lib/api/installments";
import { useCreateContract } from "@/hooks/installments/useCreateContract";
import {
  classifyInstallmentsError,
  getCompanyId,
  type InstallmentsErrorState,
} from "@/components/installments/apiErrors";
import InstallmentsStateBanner from "@/components/installments/InstallmentsStateBanner";
import { useInstallmentsPermissions, useHasInstallmentsPermission } from "@/hooks/installments/useInstallmentsPermissions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const FREQUENCIES = INSTALLMENT_SUPPORTED_FREQUENCIES;

export default function NewInstallmentContractPage() {
  const router = useRouter();
  const companyId = getCompanyId();
  const permissionsState = useInstallmentsPermissions();
  const canOriginate = useHasInstallmentsPermission(permissionsState, "installments.contract.create");

  const [quote, setQuote] = useState<InstallmentQuotePreviewRead | null>(null);
  const [quoting, setQuoting] = useState(false);
  const [errorState, setErrorState] = useState<InstallmentsErrorState | null>(null);
  const createContract = useCreateContract();

  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<InstallmentContractCreateFormData>({
    resolver: zodResolver(InstallmentContractCreateSchema),
    defaultValues: {
      sales_invoice_id: "",
      down_payment_amount: "0",
      installment_count: 12,
      frequency: "MONTHLY",
      first_due_date: "",
      maturity_date: "",
      markup_amount: "0",
    },
  });

  async function handleGetQuote() {
    if (!companyId) return;
    const values = getValues();
    setQuoting(true);
    setErrorState(null);
    try {
      const res = await previewInstallmentQuote(companyId, {
        sales_invoice_id: values.sales_invoice_id,
        down_payment_amount: values.down_payment_amount,
        installment_count: Number(values.installment_count),
        frequency: values.frequency,
        first_due_date: values.first_due_date,
        markup_amount: values.markup_amount || "0",
      });
      setQuote(res.data);
    } catch (err) {
      setErrorState(classifyInstallmentsError(err));
      setQuote(null);
    } finally {
      setQuoting(false);
    }
  }

  async function onSubmit(data: InstallmentContractCreateFormData) {
    if (!companyId) return;
    setErrorState(null);
    try {
      const result = await createContract.mutateAsync({
        sales_invoice_id: data.sales_invoice_id,
        down_payment_amount: data.down_payment_amount,
        installment_count: Number(data.installment_count),
        frequency: data.frequency,
        first_due_date: data.first_due_date,
        maturity_date: data.maturity_date,
        markup_amount: data.markup_amount || "0",
        plan_template_id: data.plan_template_id || null,
        branch_id: data.branch_id || null,
        contract_date: data.contract_date || null,
      });
      router.push(`../contracts/${result.id}`);
    } catch (err) {
      setErrorState(classifyInstallmentsError(err));
    }
  }

  if (permissionsState.isReady && !canOriginate) {
    return (
      <div className="p-6">
        <InstallmentsStateBanner
          state={{ message: "You cannot create installment contracts.", forbidden: true, featureDisabled: false }}
        />
      </div>
    );
  }

  if (errorState?.featureDisabled) {
    return (
      <div className="p-6 max-w-2xl">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">New Installment Contract</h1>
        <InstallmentsStateBanner state={errorState} />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">New Installment Contract</h1>

      {errorState && <InstallmentsStateBanner state={errorState} />}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Sales Invoice ID</label>
          <Input {...register("sales_invoice_id")} placeholder="Invoice UUID" />
          {errors.sales_invoice_id && (
            <p className="text-xs text-red-600 mt-1">{errors.sales_invoice_id.message}</p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Down Payment</label>
            <Input {...register("down_payment_amount")} />
            {errors.down_payment_amount && (
              <p className="text-xs text-red-600 mt-1">{errors.down_payment_amount.message}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Markup Amount</label>
            <Input {...register("markup_amount")} />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Installment Count</label>
            <Input type="number" min={1} {...register("installment_count")} />
            {errors.installment_count && (
              <p className="text-xs text-red-600 mt-1">{errors.installment_count.message}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Frequency</label>
            <select
              {...register("frequency")}
              className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm h-9"
            >
              {FREQUENCIES.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">First Due Date</label>
            <Input type="date" {...register("first_due_date")} />
            {errors.first_due_date && (
              <p className="text-xs text-red-600 mt-1">{errors.first_due_date.message}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Maturity Date</label>
            <Input type="date" {...register("maturity_date")} />
            {errors.maturity_date && (
              <p className="text-xs text-red-600 mt-1">{errors.maturity_date.message}</p>
            )}
          </div>
        </div>

        <div className="flex gap-3 pt-2">
          <Button
            type="button"
            variant="outline"
            onClick={handleGetQuote}
            disabled={quoting || !companyId}
          >
            {quoting ? "Generating…" : "Get Quote"}
          </Button>
        </div>

        {quote && (
          <div className="border border-gray-200 rounded-md p-4 text-sm space-y-1 bg-gray-50">
            <h2 className="font-semibold text-gray-700 mb-2">Quote Preview</h2>
            <div>Financed Principal: {quote.financed_principal}</div>
            <div>Contractual Total: {quote.contractual_total}</div>
            <div>
              Per-Installment: {quote.per_installment_amounts[0]} × {quote.installment_count}
              (final {quote.final_installment_amount})
            </div>
            <div>Expected Completion: {quote.expected_completion_date}</div>
          </div>
        )}

        <div className="flex gap-3 pt-2">
          <Button type="submit" disabled={createContract.isPending || !companyId}>
            {createContract.isPending ? "Saving…" : "Create Draft Contract"}
          </Button>
          <Button type="button" variant="outline" onClick={() => router.back()}>
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
}
