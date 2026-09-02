/**
 * T235 — Contract Detail page: permission-gated lifecycle action buttons
 * hide (not merely disable) when the corresponding installments.*
 * permission is absent. Proven for the PENDING_APPROVAL → Approve/Reject
 * buttons (installments.contract.approve).
 */

import { render, screen } from '@testing-library/react';
import ContractDetailPage from '@/app/(protected)/(installments)/contracts/[contractId]/page';

jest.mock('next/navigation', () => ({
  useParams: () => ({ contractId: 'contract-1' }),
}));

const mockContract = {
  id: 'contract-1',
  contract_number: 'INST-0001',
  status: 'PENDING_APPROVAL',
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
  useCollections: () => baseQueryResult({ data: [] }),
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

const mockUseInstallmentsPermissions = jest.fn();
jest.mock('@/hooks/installments/useInstallmentsPermissions', () => ({
  useInstallmentsPermissions: () => mockUseInstallmentsPermissions(),
  useHasInstallmentsPermission: (
    state: { isReady: boolean; permissions: string[] },
    code: string
  ) => state.isReady && state.permissions.includes(code),
}));

describe('T235 — Contract Detail permission-gated action buttons', () => {
  beforeEach(() => {
    mockUseInstallmentsPermissions.mockReset();
  });

  it('shows Approve/Reject when installments.contract.approve is granted', () => {
    mockUseInstallmentsPermissions.mockReturnValue({
      permissions: ['installments.contract.approve'],
      isLoading: false,
      isReady: true,
    });

    render(<ContractDetailPage />);

    expect(screen.getByRole('button', { name: 'Approve' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reject' })).toBeInTheDocument();
  });

  it('hides (does not render) Approve/Reject when the permission is absent — not merely disabled', () => {
    mockUseInstallmentsPermissions.mockReturnValue({
      permissions: [],
      isLoading: false,
      isReady: true,
    });

    render(<ContractDetailPage />);

    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument();
    // Confirms absence, not a disabled attribute on a still-rendered button.
    expect(screen.queryByText('Approve')).not.toBeInTheDocument();
  });
});
