/**
 * Phase-13 closure item F — collection reversal is now user-reachable
 * from the Contract Detail page's Payments section. Proves:
 *   - the Reverse action is hidden without installments.collection.reverse
 *     (RBAC is UX-only here; the backend remains authoritative — see the
 *     real-HTTP `installments.collection.reverse` permission enforcement
 *     in `router.py::reverse_collection`);
 *   - a reversal row (is_reversal: true) never offers its own Reverse
 *     action;
 *   - the reason-confirmation flow requires a non-empty reason before the
 *     mutation fires, and one confirm click produces exactly one
 *     `reverseCollection.mutate` call (no duplicate submission).
 */

import { render, screen, fireEvent } from '@testing-library/react';
import ContractDetailPage from '@/app/(protected)/(installments)/contracts/[contractId]/page';

jest.mock('next/navigation', () => ({
  useParams: () => ({ contractId: 'contract-1' }),
}));

const mockContract = {
  id: 'contract-1',
  contract_number: 'INST-0001',
  status: 'ACTIVE',
  contractual_total: '1000',
  currency_code: 'USD',
  principal_amount: '900',
  down_payment_amount: '100',
  installment_count: 12,
  frequency: 'MONTHLY',
  contract_date: '2026-01-01',
  maturity_date: '2027-01-01',
  first_due_date: '2026-02-01',
  markup_amount: '0',
};

const mockCollectionRows = [
  {
    report_type: 'collection',
    contract_id: 'contract-1',
    schedule_line_id: 'line-1',
    accounting_payment_id: 'payment-1',
    allocated_amount: '250.00',
    allocated_at: '2026-02-01T10:00:00Z',
    is_reversal: false,
    payment_method: 'CASH',
    payment_date: '2026-02-01',
  },
  {
    report_type: 'collection',
    contract_id: 'contract-1',
    schedule_line_id: 'line-2',
    accounting_payment_id: 'payment-2',
    allocated_amount: '250.00',
    allocated_at: '2026-03-01T10:00:00Z',
    is_reversal: true,
    payment_method: 'CASH',
    payment_date: '2026-03-01',
  },
];

function baseQueryResult(overrides: Record<string, unknown> = {}) {
  return {
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    refetch: jest.fn(),
    ...overrides,
  };
}

jest.mock('@/hooks/installments/useContract', () => ({
  useContract: () => baseQueryResult({ data: mockContract }),
}));
jest.mock('@/hooks/installments/useSchedule', () => ({
  useSchedule: () => baseQueryResult({ isError: true }),
}));
jest.mock('@/hooks/installments/useCollections', () => ({
  useCollections: () => baseQueryResult({ data: mockCollectionRows }),
}));
jest.mock('@/hooks/installments/useDelinquency', () => ({
  useDelinquency: () => baseQueryResult({ data: [] }),
}));
jest.mock('@/hooks/installments/useAuditHistory', () => ({
  useAuditHistory: () => baseQueryResult({ data: [] }),
}));
jest.mock('@/components/installments/apiErrors', () => ({
  getCompanyId: () => 'company-1',
  classifyInstallmentsError: (err: unknown) => ({
    message: err instanceof Error ? err.message : 'error',
    forbidden: false,
    featureDisabled: false,
  }),
}));

function mockMutation() {
  return { mutate: jest.fn(), isPending: false, isError: false, error: null };
}

jest.mock('@/hooks/installments/useContractLifecycleActions', () => ({
  useContractLifecycleActions: () => ({
    submit: mockMutation(),
    approve: mockMutation(),
    reject: mockMutation(),
    activate: mockMutation(),
    cure: mockMutation(),
    cancel: mockMutation(),
    markDefaulted: mockMutation(),
    writeoff: mockMutation(),
  }),
}));

const mockReverseMutate = jest.fn();
jest.mock('@/hooks/installments/useReverseCollection', () => ({
  useReverseCollection: () => ({
    mutate: mockReverseMutate,
    isPending: false,
    isError: false,
    error: null,
  }),
}));

const mockUseInstallmentsPermissions = jest.fn();
jest.mock('@/hooks/installments/useInstallmentsPermissions', () => ({
  useInstallmentsPermissions: () => mockUseInstallmentsPermissions(),
  useHasInstallmentsPermission: (
    state: { isReady: boolean; permissions: string[] },
    code: string
  ) => state.isReady && state.permissions.includes(code),
}));

describe('Collection reversal — Contract Detail Payments section', () => {
  beforeEach(() => {
    mockUseInstallmentsPermissions.mockReset();
    mockReverseMutate.mockReset();
  });

  it('hides the Reverse action without installments.collection.reverse', () => {
    mockUseInstallmentsPermissions.mockReturnValue({
      permissions: [],
      isLoading: false,
      isReady: true,
    });

    render(<ContractDetailPage />);

    expect(screen.queryByRole('button', { name: 'Reverse' })).not.toBeInTheDocument();
  });

  it('shows exactly one Reverse action — for the non-reversal row only — when granted', () => {
    mockUseInstallmentsPermissions.mockReturnValue({
      permissions: ['installments.collection.reverse'],
      isLoading: false,
      isReady: true,
    });

    render(<ContractDetailPage />);

    expect(screen.getAllByRole('button', { name: 'Reverse' })).toHaveLength(1);
  });

  it('requires a non-empty reason before the confirm button is enabled, and fires exactly one mutate call on confirm', () => {
    mockUseInstallmentsPermissions.mockReturnValue({
      permissions: ['installments.collection.reverse'],
      isLoading: false,
      isReady: true,
    });

    render(<ContractDetailPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Reverse' }));

    const confirmButton = screen.getByRole('button', { name: 'Confirm Reverse' });
    expect(confirmButton).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText('Reason (required)'), {
      target: { value: 'Customer disputed charge' },
    });
    expect(confirmButton).toBeEnabled();

    fireEvent.click(confirmButton);

    expect(mockReverseMutate).toHaveBeenCalledTimes(1);
    expect(mockReverseMutate).toHaveBeenCalledWith({
      collectionId: 'payment-1',
      reason: 'Customer disputed charge',
    });
  });
});
