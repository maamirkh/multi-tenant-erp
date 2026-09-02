/**
 * useContractLifecycleActions — mutations for every named contract
 * lifecycle transition (submit/approve/reject/activate/cure/cancel/
 * default/writeoff), used by the Contract Detail page's (T224)
 * permission-gated action buttons. Idempotency-protected commands
 * (activate/cancel/default/writeoff) generate a fresh client-side key
 * per invocation via `newIdempotencyKey()` (plan.md §20).
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  submitInstallmentContract,
  approveInstallmentContract,
  rejectInstallmentContract,
  activateInstallmentContract,
  cureInstallmentContract,
  cancelInstallmentContract,
  defaultInstallmentContract,
  writeoffInstallmentContract,
  newIdempotencyKey,
  type InstallmentContractRead,
  type InstallmentCancelRequest,
} from '@/lib/api/installments';
import { getCompanyId } from '@/components/installments/apiErrors';

export function useContractLifecycleActions(contractId: string) {
  const queryClient = useQueryClient();
  const companyId = getCompanyId();

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ['contract', contractId] });
    void queryClient.invalidateQueries({ queryKey: ['contracts'] });
    void queryClient.invalidateQueries({ queryKey: ['auditHistory', contractId] });
  }

  const submit = useMutation<InstallmentContractRead, unknown, void>({
    mutationFn: async () => (await submitInstallmentContract(companyId, contractId)).data,
    onSuccess: invalidate,
  });

  const approve = useMutation<InstallmentContractRead, unknown, void>({
    mutationFn: async () => (await approveInstallmentContract(companyId, contractId)).data,
    onSuccess: invalidate,
  });

  const reject = useMutation<InstallmentContractRead, unknown, string>({
    mutationFn: async (reason) =>
      (await rejectInstallmentContract(companyId, contractId, reason)).data,
    onSuccess: invalidate,
  });

  const activate = useMutation<InstallmentContractRead, unknown, void>({
    mutationFn: async () =>
      (await activateInstallmentContract(companyId, contractId, newIdempotencyKey())).data,
    onSuccess: invalidate,
  });

  const cure = useMutation<InstallmentContractRead, unknown, string | undefined>({
    mutationFn: async (reason) => (await cureInstallmentContract(companyId, contractId, reason)).data,
    onSuccess: invalidate,
  });

  const cancel = useMutation<InstallmentContractRead, unknown, InstallmentCancelRequest>({
    mutationFn: async (data) =>
      (await cancelInstallmentContract(companyId, contractId, data, newIdempotencyKey())).data,
    onSuccess: invalidate,
  });

  const markDefaulted = useMutation<InstallmentContractRead, unknown, string>({
    mutationFn: async (reason) =>
      (await defaultInstallmentContract(companyId, contractId, reason, newIdempotencyKey())).data,
    onSuccess: invalidate,
  });

  const writeoff = useMutation<InstallmentContractRead, unknown, string>({
    mutationFn: async (reason) =>
      (await writeoffInstallmentContract(companyId, contractId, reason, newIdempotencyKey())).data,
    onSuccess: invalidate,
  });

  return { submit, approve, reject, activate, cure, cancel, markDefaulted, writeoff };
}
