/**
 * T233 — useInstallmentsPermissions / useHasInstallmentsPermission hook
 * tests. Mirrors the equivalent CRM hook's fail-safe behavior: any error
 * resolves to an empty permission set (hide on load failure), never a
 * false "allowed".
 */

import { act, renderHook, waitFor } from '@testing-library/react';
import {
  useInstallmentsPermissions,
  useHasInstallmentsPermission,
} from '@/hooks/installments/useInstallmentsPermissions';
import { ACTIVE_COMPANY_CHANGED_EVENT } from '@/contexts/CompanyContext';

const mockGetMyInstallmentsPermissions = jest.fn();

jest.mock('@/lib/api/installments', () => ({
  getMyInstallmentsPermissions: (...args: unknown[]) => mockGetMyInstallmentsPermissions(...args),
}));

const mockGetCompanyId = jest.fn();
jest.mock('@/components/installments/apiErrors', () => ({
  getCompanyId: () => mockGetCompanyId(),
}));

describe('T233 — useInstallmentsPermissions', () => {
  beforeEach(() => {
    mockGetMyInstallmentsPermissions.mockReset();
    mockGetCompanyId.mockReset();
    mockGetCompanyId.mockReturnValue('company-1');
  });

  it('returns granted permission codes on success', async () => {
    mockGetMyInstallmentsPermissions.mockResolvedValueOnce({
      data: { permissions: ['installments.contract.view', 'installments.collection.create'] },
    });

    const { result } = renderHook(() => useInstallmentsPermissions());

    await waitFor(() => expect(result.current.isReady).toBe(true));
    expect(result.current.permissions).toEqual([
      'installments.contract.view',
      'installments.collection.create',
    ]);
  });

  it('fails safe to an empty permission set on API error', async () => {
    mockGetMyInstallmentsPermissions.mockRejectedValueOnce(new Error('FEATURE_DISABLED'));

    const { result } = renderHook(() => useInstallmentsPermissions());

    await waitFor(() => expect(result.current.isReady).toBe(true));
    expect(result.current.permissions).toEqual([]);
  });

  it('is ready immediately with no permissions when no company is selected', async () => {
    mockGetCompanyId.mockReturnValue('');

    const { result } = renderHook(() => useInstallmentsPermissions());

    await waitFor(() => expect(result.current.isReady).toBe(true));
    expect(result.current.permissions).toEqual([]);
    expect(mockGetMyInstallmentsPermissions).not.toHaveBeenCalled();
  });

  it('re-scopes to the new company on an active-company-changed event: fails closed immediately, never leaks Tenant A permissions into Tenant B', async () => {
    mockGetCompanyId.mockReturnValue('tenant-a');
    let resolveTenantB!: (value: { data: { permissions: string[] } }) => void;
    mockGetMyInstallmentsPermissions.mockImplementation((companyId: string) => {
      if (companyId === 'tenant-a') {
        return Promise.resolve({ data: { permissions: ['installments.contract.approve'] } });
      }
      // Tenant B's fetch is held open so we can inspect the in-between state.
      return new Promise((resolve) => {
        resolveTenantB = resolve;
      });
    });

    const { result } = renderHook(() => useInstallmentsPermissions());

    await waitFor(() => expect(result.current.isReady).toBe(true));
    expect(result.current.permissions).toEqual(['installments.contract.approve']);
    expect(
      useHasInstallmentsPermission(result.current, 'installments.contract.approve')
    ).toBe(true);

    // Switch to Tenant B, which does not have the approve permission.
    mockGetCompanyId.mockReturnValue('tenant-b');
    act(() => {
      window.dispatchEvent(new Event(ACTIVE_COMPANY_CHANGED_EVENT));
    });

    // Immediately fail-closed: Tenant A's permission must not remain
    // visible/usable while Tenant B's fetch is still in flight.
    expect(result.current.isReady).toBe(false);
    expect(result.current.permissions).toEqual([]);
    expect(
      useHasInstallmentsPermission(result.current, 'installments.contract.approve')
    ).toBe(false);

    act(() => {
      resolveTenantB({ data: { permissions: ['installments.contract.view'] } });
    });

    await waitFor(() => expect(result.current.isReady).toBe(true));
    expect(result.current.permissions).toEqual(['installments.contract.view']);
    expect(
      useHasInstallmentsPermission(result.current, 'installments.contract.approve')
    ).toBe(false);
  });
});

describe('T233 — useHasInstallmentsPermission', () => {
  it('returns true only once ready and the code is granted', () => {
    const notReady = { permissions: [], isLoading: true, isReady: false };
    const readyGranted = {
      permissions: ['installments.contract.view'],
      isLoading: false,
      isReady: true,
    };
    const readyDenied = { permissions: [], isLoading: false, isReady: true };

    expect(useHasInstallmentsPermission(notReady, 'installments.contract.view')).toBe(false);
    expect(useHasInstallmentsPermission(readyGranted, 'installments.contract.view')).toBe(true);
    expect(useHasInstallmentsPermission(readyDenied, 'installments.contract.view')).toBe(false);
  });
});
