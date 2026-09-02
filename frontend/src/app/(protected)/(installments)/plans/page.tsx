"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  listPlanTemplates,
  createPlanTemplate,
  deactivatePlanTemplate,
  type InstallmentPlanTemplateRead,
} from "@/lib/api/installments";
import {
  InstallmentPlanTemplateSchema,
  type InstallmentPlanTemplateFormData,
} from "@/schemas/installments";
import { getCompanyId, classifyInstallmentsError, type InstallmentsErrorState } from "@/components/installments/apiErrors";
import InstallmentsStateBanner from "@/components/installments/InstallmentsStateBanner";
import { useInstallmentsPermissions, useHasInstallmentsPermission } from "@/hooks/installments/useInstallmentsPermissions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/platform-admin/DataState";

const FREQUENCIES = ["WEEKLY", "BIWEEKLY", "MONTHLY", "QUARTERLY"];

function NewTemplateForm({ onCreated }: { onCreated: () => void }) {
  const companyId = getCompanyId();
  const [errorState, setErrorState] = useState<InstallmentsErrorState | null>(null);
  const createMutation = useMutation({
    mutationFn: (data: InstallmentPlanTemplateFormData) =>
      createPlanTemplate(companyId, {
        name: data.name,
        description: data.description || null,
        frequency: data.frequency,
        installment_count: Number(data.installment_count),
        down_payment_rule: { type: data.down_payment_type, amount: data.down_payment_value },
        grace_period_days: data.grace_period_days ?? null,
        requires_approval: data.requires_approval ?? false,
      }),
    onSuccess: () => {
      reset();
      onCreated();
    },
    onError: (err) => setErrorState(classifyInstallmentsError(err)),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<InstallmentPlanTemplateFormData>({
    resolver: zodResolver(InstallmentPlanTemplateSchema),
    defaultValues: {
      name: "",
      frequency: "MONTHLY",
      installment_count: 12,
      down_payment_type: "PERCENTAGE",
      down_payment_value: "0",
      grace_period_days: 0,
      requires_approval: false,
    },
  });

  return (
    <form
      onSubmit={handleSubmit((data) => createMutation.mutate(data))}
      className="border border-gray-200 rounded-md p-4 mb-6 space-y-3"
    >
      <h2 className="text-sm font-semibold text-gray-700">New Plan Template</h2>
      {errorState && <InstallmentsStateBanner state={errorState} />}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Name</label>
          <Input {...register("name")} />
          {errors.name && <p className="text-xs text-red-600 mt-1">{errors.name.message}</p>}
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Frequency</label>
          <select {...register("frequency")} className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm h-9">
            {FREQUENCIES.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Installment Count</label>
          <Input type="number" min={1} {...register("installment_count")} />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Down Payment Type</label>
          <select {...register("down_payment_type")} className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm h-9">
            <option value="PERCENTAGE">Percentage</option>
            <option value="FIXED">Fixed</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Down Payment Value</label>
          <Input {...register("down_payment_value")} />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Grace Period (days)</label>
          <Input type="number" min={0} {...register("grace_period_days")} />
        </div>
      </div>
      <Button type="submit" disabled={createMutation.isPending}>
        {createMutation.isPending ? "Creating…" : "Create Template"}
      </Button>
    </form>
  );
}

export default function InstallmentPlansPage() {
  const companyId = getCompanyId();
  const queryClient = useQueryClient();
  const permissionsState = useInstallmentsPermissions();
  const canManage = useHasInstallmentsPermission(permissionsState, "installments.plan.manage");
  const [showNew, setShowNew] = useState(false);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["planTemplates"],
    queryFn: async () => (await listPlanTemplates(companyId, 1, 100)).data,
    enabled: companyId !== "",
  });

  const deactivateMutation = useMutation({
    mutationFn: (planId: string) => deactivatePlanTemplate(companyId, planId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["planTemplates"] }),
  });

  const templates = data?.items ?? [];
  const errorState = isError ? classifyInstallmentsError(error) : null;

  if (errorState?.featureDisabled) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Installment Plan Templates</h1>
        <InstallmentsStateBanner state={errorState} />
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Installment Plan Templates</h1>
        {canManage && (
          <Button variant="outline" size="sm" onClick={() => setShowNew((v) => !v)}>
            {showNew ? "Close" : "New Template"}
          </Button>
        )}
      </div>

      {errorState && <InstallmentsStateBanner state={errorState} />}

      {showNew && canManage && (
        <NewTemplateForm
          onCreated={() => {
            setShowNew(false);
            void queryClient.invalidateQueries({ queryKey: ["planTemplates"] });
          }}
        />
      )}

      {isLoading ? (
        <LoadingState label="Loading templates…" />
      ) : templates.length === 0 ? (
        <div className="text-center py-12 text-gray-500">No plan templates yet.</div>
      ) : (
        <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 rounded-lg">
          <table className="min-w-full divide-y divide-gray-300">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Name</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Frequency</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Installments</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Active</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {templates.map((t: InstallmentPlanTemplateRead) => (
                <tr key={t.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">{t.name}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{t.frequency}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{t.installment_count}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{t.is_active ? "Yes" : "No"}</td>
                  <td className="px-4 py-3 text-right">
                    {canManage && t.is_active && (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={deactivateMutation.isPending}
                        onClick={() => deactivateMutation.mutate(t.id)}
                      >
                        Deactivate
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
