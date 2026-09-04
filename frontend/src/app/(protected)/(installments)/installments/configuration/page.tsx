"use client";

import { useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  getInstallmentConfiguration,
  upsertInstallmentConfiguration,
} from "@/lib/api/installments";
import {
  InstallmentConfigurationSchema,
  INSTALLMENT_SUPPORTED_FREQUENCIES,
  type InstallmentConfigurationFormData,
} from "@/schemas/installments";
import { getCompanyId, classifyInstallmentsError } from "@/components/installments/apiErrors";
import InstallmentsStateBanner from "@/components/installments/InstallmentsStateBanner";
import { useInstallmentsPermissions, useHasInstallmentsPermission } from "@/hooks/installments/useInstallmentsPermissions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LoadingState, PermissionDeniedState } from "@/components/platform-admin/DataState";

const ALL_FREQUENCIES = INSTALLMENT_SUPPORTED_FREQUENCIES;

export default function InstallmentConfigurationPage() {
  const companyId = getCompanyId();
  const queryClient = useQueryClient();
  const permissionsState = useInstallmentsPermissions();
  const canManage = useHasInstallmentsPermission(permissionsState, "installments.config.manage");

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["installmentConfig", companyId],
    queryFn: async () => (await getInstallmentConfiguration(companyId)).data,
    enabled: companyId !== "" && canManage,
    retry: false,
  });

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors },
  } = useForm<InstallmentConfigurationFormData>({
    resolver: zodResolver(InstallmentConfigurationSchema),
    defaultValues: {
      allowed_frequencies: ["MONTHLY"],
      min_term: 1,
      max_term: 60,
      rounding_policy: "ROUND_HALF_UP",
      grace_period_days: 0,
      backdating_allowed: false,
      writeoff_requires_permission: true,
      cure_enabled: false,
    },
  });

  useEffect(() => {
    if (!data) return;
    reset({
      // Filter out any legacy stored value outside the current supported
      // set (e.g. a pre-fix BIWEEKLY) — it was explicitly edited by this
      // very form, so dropping it here (rather than round-tripping, as we
      // do for the unrelated policy-object fields below) is the correct
      // cleanup, not a silent-erasure risk.
      allowed_frequencies: data.allowed_frequencies.filter(
        (f): f is (typeof INSTALLMENT_SUPPORTED_FREQUENCIES)[number] =>
          (INSTALLMENT_SUPPORTED_FREQUENCIES as readonly string[]).includes(f)
      ),
      min_term: data.min_term,
      max_term: data.max_term,
      min_down_payment_pct: data.min_down_payment_pct ?? "",
      min_down_payment_amount: data.min_down_payment_amount ?? "",
      max_financed_amount: data.max_financed_amount ?? "",
      rounding_policy: data.rounding_policy,
      grace_period_days: data.grace_period_days,
      approval_threshold_amount: data.approval_threshold_amount ?? "",
      backdating_allowed: data.backdating_allowed,
      backdating_max_days: data.backdating_max_days ?? undefined,
      writeoff_requires_permission: data.writeoff_requires_permission,
      cure_enabled: data.cure_enabled,
    });
  }, [data, reset]);

  const allowedFrequencies = watch("allowed_frequencies");

  const upsertMutation = useMutation({
    // `PUT /config` is a full-replace endpoint (see configuration_service.py's
    // upsert_config, which setattr's every key of the request body onto the
    // existing row). This form has no controls for the five policy-object
    // fields (late_charge_policy, early_settlement_policy,
    // cancellation_policy, default_policy, eligibility_rules) — they're
    // opaque, arbitrarily-shaped dicts with no UI editor yet, and we do not
    // invent fake values for them. So every save round-trips whatever was
    // last read from GET /config verbatim, preserving them exactly instead
    // of omitting the keys (which the backend would otherwise interpret as
    // "set to null", silently erasing previously-configured policy data).
    mutationFn: (formData: InstallmentConfigurationFormData) =>
      upsertInstallmentConfiguration(companyId, {
        allowed_frequencies: formData.allowed_frequencies,
        min_term: Number(formData.min_term),
        max_term: Number(formData.max_term),
        min_down_payment_pct: formData.min_down_payment_pct || null,
        min_down_payment_amount: formData.min_down_payment_amount || null,
        max_financed_amount: formData.max_financed_amount || null,
        rounding_policy: formData.rounding_policy,
        grace_period_days: Number(formData.grace_period_days),
        late_charge_policy: data?.late_charge_policy ?? null,
        early_settlement_policy: data?.early_settlement_policy ?? null,
        approval_threshold_amount: formData.approval_threshold_amount || null,
        backdating_allowed: formData.backdating_allowed,
        backdating_max_days: formData.backdating_max_days ?? null,
        cancellation_policy: data?.cancellation_policy ?? null,
        default_policy: data?.default_policy ?? null,
        writeoff_requires_permission: formData.writeoff_requires_permission,
        cure_enabled: formData.cure_enabled,
        eligibility_rules: data?.eligibility_rules ?? null,
      }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["installmentConfig", companyId] }),
  });

  if (permissionsState.isReady && !canManage) {
    return (
      <div className="p-6">
        <PermissionDeniedState message="You cannot manage installment configuration." />
      </div>
    );
  }

  const errorState = isError ? classifyInstallmentsError(error) : null;
  if (errorState?.featureDisabled) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Installment Configuration</h1>
        <InstallmentsStateBanner state={errorState} />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Installment Configuration</h1>

      {upsertMutation.isSuccess && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-md text-sm text-green-700">
          Configuration saved.
        </div>
      )}
      {upsertMutation.isError && (
        <InstallmentsStateBanner state={classifyInstallmentsError(upsertMutation.error)} />
      )}

      {isLoading ? (
        <LoadingState label="Loading configuration…" />
      ) : (
        <form
          onSubmit={handleSubmit((formData) => upsertMutation.mutate(formData))}
          className="space-y-4"
        >
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Allowed Frequencies</label>
            <div className="flex gap-4 flex-wrap">
              {ALL_FREQUENCIES.map((f) => (
                <label key={f} className="flex items-center gap-1.5 text-sm">
                  <input
                    type="checkbox"
                    checked={allowedFrequencies?.includes(f) ?? false}
                    onChange={(e) => {
                      const next = e.target.checked
                        ? [...(allowedFrequencies ?? []), f]
                        : (allowedFrequencies ?? []).filter((x) => x !== f);
                      setValue("allowed_frequencies", next, { shouldDirty: true });
                    }}
                  />
                  {f}
                </label>
              ))}
            </div>
            {errors.allowed_frequencies && (
              <p className="text-xs text-red-600 mt-1">{errors.allowed_frequencies.message}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Min Term</label>
              <Input type="number" min={1} {...register("min_term")} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Max Term</label>
              <Input type="number" min={1} {...register("max_term")} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Min Down Payment %</label>
              <Input {...register("min_down_payment_pct")} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Min Down Payment Amount</label>
              <Input {...register("min_down_payment_amount")} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Max Financed Amount</label>
              <Input {...register("max_financed_amount")} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Approval Threshold</label>
              <Input {...register("approval_threshold_amount")} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Grace Period (days)</label>
              <Input type="number" min={0} {...register("grace_period_days")} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Rounding Policy</label>
              <Input {...register("rounding_policy")} />
            </div>
          </div>

          <div className="flex gap-6 pt-1">
            <label className="flex items-center gap-1.5 text-sm">
              <input type="checkbox" {...register("backdating_allowed")} />
              Backdating Allowed
            </label>
            <label className="flex items-center gap-1.5 text-sm">
              <input type="checkbox" {...register("writeoff_requires_permission")} />
              Write-off Requires Permission
            </label>
            <label className="flex items-center gap-1.5 text-sm">
              <input type="checkbox" {...register("cure_enabled")} />
              Cure Enabled
            </label>
          </div>

          <div className="pt-2">
            <Button type="submit" disabled={upsertMutation.isPending}>
              {upsertMutation.isPending ? "Saving…" : "Save Configuration"}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
