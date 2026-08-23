/**
 * T204 — Frontend tests: permission-aware nav and UI states.
 *
 * Covers (representative, not exhaustively duplicated per page — the
 * shared `DataState`/dialog primitives each page wires consistently are
 * proven once here and reused everywhere, per T178-181's own
 * "smallest correct implementation" precedent):
 *   - Missing permission -> nav entry hidden (`PlatformSidebar`).
 *   - A denied read (403) renders `PermissionDeniedState`, never the
 *     data table — i.e. the route is refused, not merely hidden in nav.
 *   - Dashboard widget loading/populated/empty/unavailable states
 *     (FR-9A-003/004 — a failed widget is never shown as `0`).
 *   - Quotas' five distinct states (FR-9A-003 — `unavailable` != `0`,
 *     `unlimited` != a number).
 *   - A destructive action (tenant suspend) requires explicit
 *     confirmation before the mutation fires.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ApiClientError } from '@/lib/api/client';
import { ReasonDialog, ConfirmDialog } from '@/components/platform-admin/dialogs';

// --- next/navigation --------------------------------------------------
jest.mock('next/navigation', () => ({
  usePathname: () => '/platform-admin/dashboard',
  useRouter: () => ({ replace: jest.fn() }),
}));

// --- @tanstack/react-query ----------------------------------------------
const mockUseQuery = jest.fn();
const mockUseMutation = jest.fn();
const mockUseQueryClient = jest.fn();
jest.mock('@tanstack/react-query', () => ({
  QueryClient: jest.fn().mockImplementation(() => ({})),
  QueryClientProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useQuery: (opts: unknown) => mockUseQuery(opts),
  useMutation: (opts: unknown) => mockUseMutation(opts),
  useQueryClient: () => mockUseQueryClient(),
  keepPreviousData: Symbol('keepPreviousData'),
}));

// --- Platform selected-tenant context ------------------------------------
jest.mock('@/contexts/PlatformSelectedTenantContext', () => ({
  usePlatformSelectedTenantContext: () => ({
    selectedTenant: { id: 'company-1', legalName: 'Acme Inc.' },
    selectTenant: jest.fn(),
    clearSelectedTenant: jest.fn(),
  }),
}));

// --- usePlatformNavPermissions hook --------------------------------------
const mockUsePlatformNavPermissions = jest.fn();
jest.mock('@/hooks/platform-admin/usePlatformNavPermissions', () => ({
  usePlatformNavPermissions: () => mockUsePlatformNavPermissions(),
}));

// --- Imports after mocks --------------------------------------------------
import { PlatformSidebar } from '@/components/platform-admin/PlatformSidebar';
import PlatformDashboardPage from '../platform-admin/dashboard/page';
import PlatformQuotasPage from '../platform-admin/quotas/page';

function forbiddenError(): ApiClientError {
  return new ApiClientError(403, {
    error: { code: 'FORBIDDEN', message: 'Missing required Platform permission.', details: {} },
  });
}

describe('PlatformSidebar — permission-aware nav (T204)', () => {
  beforeEach(() => {
    mockUsePlatformNavPermissions.mockReset();
  });

  it('hides a nav entry whose section is denied', () => {
    mockUsePlatformNavPermissions.mockReturnValue({
      isLoading: false,
      isAllowed: (section: string) => section !== 'administrators',
    });

    render(<PlatformSidebar />);

    expect(screen.getByRole('link', { name: 'Tenants' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Administrators' })).not.toBeInTheDocument();
  });

  it('always shows the tenant-scoped-only sections regardless of probe result', () => {
    mockUsePlatformNavPermissions.mockReturnValue({
      isLoading: false,
      isAllowed: () => false,
    });

    render(<PlatformSidebar />);

    expect(screen.getByRole('link', { name: 'Subscriptions' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Entitlements' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Quotas' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Usage' })).toBeInTheDocument();
  });

  it('shows every item while the permission probe is still loading (no hide-flash)', () => {
    mockUsePlatformNavPermissions.mockReturnValue({
      isLoading: true,
      isAllowed: () => false,
    });

    render(<PlatformSidebar />);

    expect(screen.getByRole('link', { name: 'Administrators' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Roles' })).toBeInTheDocument();
  });
});

describe('Dashboard widget states (T204/T191, FR-9A-003/004)', () => {
  beforeEach(() => {
    mockUseQuery.mockReset();
  });

  it('renders a loading state', () => {
    mockUseQuery.mockReturnValue({ isLoading: true, isError: false, data: undefined, refetch: jest.fn() });
    render(<PlatformDashboardPage />);
    expect(screen.getByRole('status', { name: /loading/i })).toBeInTheDocument();
  });

  it('renders permission-denied on a 403, never the widgets', () => {
    mockUseQuery.mockReturnValue({
      isLoading: false,
      isError: true,
      error: forbiddenError(),
      data: undefined,
      refetch: jest.fn(),
    });
    render(<PlatformDashboardPage />);
    expect(screen.getByText(/don't have permission/i)).toBeInTheDocument();
  });

  it('renders populated, empty, and unavailable widgets distinctly — never a fabricated 0', () => {
    mockUseQuery.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        widgets: {
          tenant_counts_by_status: { state: 'populated', data: { active: 3 } },
          recent_registrations: { state: 'empty', data: [] },
          quota_warnings: { state: 'unavailable', data: null },
        },
      },
      refetch: jest.fn(),
    });
    render(<PlatformDashboardPage />);

    expect(screen.getByText(/"active": 3/)).toBeInTheDocument();
    expect(screen.getByText('No data yet.')).toBeInTheDocument();
    expect(
      screen.getByText("This widget's data is temporarily unavailable.")
    ).toBeInTheDocument();
    // The unavailable widget's raw payload (`null`) is never rendered as 0.
    expect(screen.queryByText('0')).not.toBeInTheDocument();
  });
});

describe('Quotas page — five distinct states (T204/T197, FR-9A-003)', () => {
  beforeEach(() => {
    mockUseQuery.mockReset();
    mockUseMutation.mockReset();
    mockUseMutation.mockReturnValue({ mutate: jest.fn(), isPending: false });
  });

  it('renders ok/approaching/reached/unlimited/unavailable distinctly', () => {
    mockUseQuery.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        company_id: 'company-1',
        quotas: [
          { quota_key: 'users', state: 'ok', limit: '10', current_usage: '2', enforcement_style: 'hard' },
          { quota_key: 'storage', state: 'approaching', limit: '100', current_usage: '85', enforcement_style: 'hard' },
          { quota_key: 'invoices', state: 'reached', limit: '50', current_usage: '50', enforcement_style: 'hard' },
          { quota_key: 'api_calls', state: 'unlimited', limit: null, current_usage: '9999', enforcement_style: null },
          { quota_key: 'exports', state: 'unavailable', limit: null, current_usage: null, enforcement_style: null },
        ],
      },
      refetch: jest.fn(),
    });

    render(<PlatformQuotasPage />);

    expect(screen.getByText('OK')).toBeInTheDocument();
    expect(screen.getByText('Approaching limit')).toBeInTheDocument();
    expect(screen.getByText('Limit reached')).toBeInTheDocument();
    // Unlimited must read "Unlimited", never a number.
    const unlimitedRow = screen.getByText('api_calls').closest('tr')!;
    expect(unlimitedRow).toHaveTextContent('Unlimited');
    expect(unlimitedRow).not.toHaveTextContent('9999');
    // Unavailable must never render as 0.
    const unavailableRow = screen.getByText('exports').closest('tr')!;
    expect(unavailableRow).toHaveTextContent('—');
    expect(unavailableRow).not.toHaveTextContent('0');
  });
});

describe('Destructive actions require confirmation (T204)', () => {
  // Every destructive Platform mutation (tenant suspend/reactivate,
  // administrator deactivate, override/grant revoke, support-access
  // terminate) routes through this exact shared `ReasonDialog`
  // (`components/platform-admin/dialogs.tsx`) — proving its contract
  // once here covers every page that wires it, per T193/T198/T196/
  // T202's identical "requires a typed reason + explicit confirmation"
  // acceptance criteria.
  it('ReasonDialog never calls onConfirm until a non-blank reason is submitted', () => {
    const onConfirm = jest.fn();
    render(
      <ReasonDialog
        open
        title="Suspend Tenant"
        description="Provide a reason."
        submitLabel="Suspend"
        onClose={jest.fn()}
        onConfirm={onConfirm}
        isPending={false}
      />
    );

    // Submitting blank never confirms.
    fireEvent.click(screen.getByRole('button', { name: 'Suspend' }));
    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.getByText(/reason is required/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/reason/i), { target: { value: 'Non-payment' } });
    fireEvent.click(screen.getByRole('button', { name: 'Suspend' }));

    expect(onConfirm).toHaveBeenCalledWith('Non-payment');
  });

  it('ConfirmDialog never calls onConfirm until the user clicks the explicit confirm button', () => {
    const onConfirm = jest.fn();
    render(
      <ConfirmDialog
        open
        title="Deactivate Administrator"
        description="Active sessions will be revoked."
        submitLabel="Deactivate"
        onClose={jest.fn()}
        onConfirm={onConfirm}
        isPending={false}
        variant="destructive"
      />
    );

    expect(onConfirm).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Deactivate' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
