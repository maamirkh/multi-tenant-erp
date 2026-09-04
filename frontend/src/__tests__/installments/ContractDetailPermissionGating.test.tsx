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

function makeContract(status: string) {
  return {
    id: 'contract-1',
    contract_number: 'INST-0001',
    status,
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
}

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

const mockUseContract = jest.fn();
jest.mock('@/hooks/installments/useContract', () => ({
  useContract: () => mockUseContract(),
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
jest.mock('@/hooks/installments/useReverseCollection', () => ({
  useReverseCollection: () => mockMutation(),
}));

const mockUseInstallmentsPermissions = jest.fn();
jest.mock('@/hooks/installments/useInstallmentsPermissions', () => ({
  useInstallmentsPermissions: () => mockUseInstallmentsPermissions(),
  useHasInstallmentsPermission: (
    state: { isReady: boolean; permissions: string[] },
    code: string
  ) => state.isReady && state.permissions.includes(code),
}));

function setPermissions(permissions: string[]) {
  mockUseInstallmentsPermissions.mockReturnValue({ permissions, isLoading: false, isReady: true });
}

describe('T235 — Contract Detail permission-gated action buttons', () => {
  beforeEach(() => {
    mockUseInstallmentsPermissions.mockReset();
    mockUseContract.mockReset();
  });

  it('shows Approve/Reject when installments.contract.approve is granted', () => {
    mockUseContract.mockReturnValue(baseQueryResult({ data: makeContract('PENDING_APPROVAL') }));
    setPermissions(['installments.contract.approve']);

    render(<ContractDetailPage />);

    expect(screen.getByRole('button', { name: 'Approve' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reject' })).toBeInTheDocument();
  });

  it('hides (does not render) Approve/Reject when the permission is absent — not merely disabled', () => {
    mockUseContract.mockReturnValue(baseQueryResult({ data: makeContract('PENDING_APPROVAL') }));
    setPermissions([]);

    render(<ContractDetailPage />);

    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument();
    // Confirms absence, not a disabled attribute on a still-rendered button.
    expect(screen.queryByText('Approve')).not.toBeInTheDocument();
  });

  it('shows Activate when installments.contract.activate is granted (APPROVED)', () => {
    mockUseContract.mockReturnValue(baseQueryResult({ data: makeContract('APPROVED') }));
    setPermissions(['installments.contract.activate']);

    render(<ContractDetailPage />);

    expect(screen.getByRole('button', { name: 'Activate' })).toBeInTheDocument();
  });

  it('hides Activate without installments.contract.activate (APPROVED)', () => {
    mockUseContract.mockReturnValue(baseQueryResult({ data: makeContract('APPROVED') }));
    setPermissions([]);

    render(<ContractDetailPage />);

    expect(screen.queryByRole('button', { name: 'Activate' })).not.toBeInTheDocument();
  });

  it('shows Cure and Write Off when granted (DEFAULTED)', () => {
    mockUseContract.mockReturnValue(baseQueryResult({ data: makeContract('DEFAULTED') }));
    setPermissions(['installments.contract.cure', 'installments.contract.writeoff']);

    render(<ContractDetailPage />);

    expect(screen.getByRole('button', { name: 'Cure' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Write Off' })).toBeInTheDocument();
  });

  it('hides Cure and Write Off without their respective permissions (DEFAULTED)', () => {
    mockUseContract.mockReturnValue(baseQueryResult({ data: makeContract('DEFAULTED') }));
    setPermissions([]);

    render(<ContractDetailPage />);

    expect(screen.queryByRole('button', { name: 'Cure' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Write Off' })).not.toBeInTheDocument();
    expect(screen.queryByText('Cure')).not.toBeInTheDocument();
    expect(screen.queryByText('Write Off')).not.toBeInTheDocument();
  });

  it('shows Mark Defaulted when installments.contract.default is granted (ACTIVE)', () => {
    mockUseContract.mockReturnValue(baseQueryResult({ data: makeContract('ACTIVE') }));
    setPermissions(['installments.contract.default']);

    render(<ContractDetailPage />);

    expect(screen.getByRole('button', { name: 'Mark Defaulted' })).toBeInTheDocument();
  });

  it('hides Mark Defaulted without installments.contract.default (ACTIVE)', () => {
    mockUseContract.mockReturnValue(baseQueryResult({ data: makeContract('ACTIVE') }));
    setPermissions([]);

    render(<ContractDetailPage />);

    expect(screen.queryByRole('button', { name: 'Mark Defaulted' })).not.toBeInTheDocument();
    expect(screen.queryByText('Mark Defaulted')).not.toBeInTheDocument();
  });

  it('shows Cancel when installments.contract.cancel is granted (each cancellable status)', () => {
    for (const status of ['DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'ACTIVE']) {
      mockUseContract.mockReturnValue(baseQueryResult({ data: makeContract(status) }));
      setPermissions(['installments.contract.cancel']);

      const { unmount } = render(<ContractDetailPage />);
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
      unmount();
    }
  });

  it('hides Cancel without installments.contract.cancel (ACTIVE)', () => {
    mockUseContract.mockReturnValue(baseQueryResult({ data: makeContract('ACTIVE') }));
    setPermissions([]);

    render(<ContractDetailPage />);

    expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument();
    expect(screen.queryByText('Cancel')).not.toBeInTheDocument();
  });

  it('hides Submit without installments.contract.create (DRAFT)', () => {
    mockUseContract.mockReturnValue(baseQueryResult({ data: makeContract('DRAFT') }));
    setPermissions([]);

    render(<ContractDetailPage />);

    expect(screen.queryByRole('button', { name: 'Submit' })).not.toBeInTheDocument();
  });

  it('shows Submit when installments.contract.create is granted (DRAFT)', () => {
    mockUseContract.mockReturnValue(baseQueryResult({ data: makeContract('DRAFT') }));
    setPermissions(['installments.contract.create']);

    render(<ContractDetailPage />);

    expect(screen.getByRole('button', { name: 'Submit' })).toBeInTheDocument();
  });

  it('shows Record Collection when installments.collection.create is granted (ACTIVE)', () => {
    mockUseContract.mockReturnValue(baseQueryResult({ data: makeContract('ACTIVE') }));
    setPermissions(['installments.collection.create']);

    render(<ContractDetailPage />);

    expect(screen.getByRole('link', { name: 'Record Collection' })).toBeInTheDocument();
  });

  it('hides Record Collection without installments.collection.create (ACTIVE) — regression for the Phase-13-closure verification finding: this action rendered unconditionally for any viewer, unlike every other lifecycle action on this page', () => {
    mockUseContract.mockReturnValue(baseQueryResult({ data: makeContract('ACTIVE') }));
    setPermissions([]);

    render(<ContractDetailPage />);

    expect(screen.queryByRole('link', { name: 'Record Collection' })).not.toBeInTheDocument();
    expect(screen.queryByText('Record Collection')).not.toBeInTheDocument();
  });

  it('shows Reschedule when installments.contract.reschedule is granted (ACTIVE)', () => {
    mockUseContract.mockReturnValue(baseQueryResult({ data: makeContract('ACTIVE') }));
    setPermissions(['installments.contract.reschedule']);

    render(<ContractDetailPage />);

    expect(screen.getByRole('link', { name: 'Reschedule' })).toBeInTheDocument();
  });

  it('hides Reschedule without installments.contract.reschedule (ACTIVE) — same regression as Record Collection', () => {
    mockUseContract.mockReturnValue(baseQueryResult({ data: makeContract('ACTIVE') }));
    setPermissions([]);

    render(<ContractDetailPage />);

    expect(screen.queryByRole('link', { name: 'Reschedule' })).not.toBeInTheDocument();
    expect(screen.queryByText('Reschedule')).not.toBeInTheDocument();
  });
});
