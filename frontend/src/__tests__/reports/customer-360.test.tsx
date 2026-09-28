/**
 * T256 — Customer 360 partial composition renders exactly what the backend
 * returned (present / omitted → nothing / unavailable → neutral note), and a
 * 404 renders the standard not-found page, never a distinguishable "empty"
 * page.
 * T257 — IDOR-safe navigation: a cross-tenant `customerId` renders the
 * standard not-found page with no transient identity flash.
 * T258 (Customer 360 half) — axe.
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { axe, toHaveNoViolations } from 'jest-axe';
import Customer360Page from '@/app/(protected)/(reports)/analytics/customer-360/[customerId]/page';
import { ApiClientError } from '@/lib/api/client';
import { getCustomer360, type Customer360Response } from '@/lib/api/reports';

expect.extend(toHaveNoViolations);

const NOT_FOUND_MARKER = 'NEXT_NOT_FOUND';
let mockParams: Record<string, string> = {};
jest.mock('next/navigation', () => ({
  usePathname: () => '/analytics/customer-360/x',
  useParams: () => mockParams,
  notFound: jest.fn(() => {
    throw new Error('NEXT_NOT_FOUND');
  }),
}));
jest.mock('@/lib/api/reports', () => {
  const actual = jest.requireActual('@/lib/api/reports');
  return { ...actual, getCustomer360: jest.fn() };
});

const c360Mock = getCustomer360 as jest.MockedFunction<typeof getCustomer360>;
const META = { request_id: 'r', timestamp: '2026-09-28T00:00:00Z' };
const CUSTOMER_ID = '11111111-2222-3333-4444-555555555555';

/** Stands in for Next's not-found boundary: `notFound()` throws, this renders the standard page. */
class NotFoundBoundary extends React.Component<
  { children: React.ReactNode },
  { notFound: boolean }
> {
  state = { notFound: false };
  static getDerivedStateFromError(error: Error) {
    if (error.message === NOT_FOUND_MARKER) return { notFound: true };
    throw error;
  }
  render() {
    return this.state.notFound ? (
      <p data-testid="standard-not-found">404 | This page could not be found.</p>
    ) : (
      this.props.children
    );
  }
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <NotFoundBoundary>
        <Customer360Page />
      </NotFoundBoundary>
    </QueryClientProvider>
  );
}

function partial(): Customer360Response {
  return {
    customer_id: CUSTOMER_ID,
    customer_name: 'Acme Trading',
    sales: { state: 'present', total_revenue: '1545.75', invoice_count: 3 },
    accounting_ar: { state: 'present', balance: '0' },
    crm: { state: 'omitted', reason: 'not_entitled' },
    installments: { state: 'unavailable', reason: 'not_configured' },
  };
}

function notFoundError(): ApiClientError {
  return new ApiClientError(404, {
    error: { code: 'NOT_FOUND', message: 'Customer not found.', details: {} },
  });
}

let consoleError: jest.SpyInstance;
beforeEach(() => {
  jest.clearAllMocks();
  mockParams = { customerId: CUSTOMER_ID };
  window.localStorage.setItem('erp_active_company_id', 'company-1');
  // React logs errors caught by the boundary; keep test output readable.
  consoleError = jest.spyOn(console, 'error').mockImplementation(() => undefined);
});
afterEach(() => {
  consoleError.mockRestore();
  window.localStorage.clear();
});

describe('Customer 360 (T256)', () => {
  it('renders exactly 2 present sections + 1 unavailable note, omitted section absent', async () => {
    c360Mock.mockResolvedValue({ data: partial(), message: 'ok', meta: META });
    renderPage();
    expect(await screen.findByRole('heading', { name: 'Acme Trading' })).toBeInTheDocument();
    expect(screen.getByTestId('c360-section-sales')).toHaveTextContent('1,545.75');
    expect(screen.getByTestId('c360-section-sales')).toHaveTextContent('3');
    // A real zero balance is a real zero, not "unavailable".
    expect(screen.getByTestId('c360-section-accounting_ar')).toHaveTextContent('0.00');
    expect(screen.getByTestId('c360-section-installments')).toHaveTextContent(
      'Not configured for this company yet.'
    );
    expect(screen.queryByTestId('c360-section-crm')).not.toBeInTheDocument();
    expect(screen.queryByText(/CRM/)).not.toBeInTheDocument();
    // No reason codes or access-denied wording leak to the user.
    expect(document.body).not.toHaveTextContent(/not_entitled|not_configured|denied|permission/i);
    expect(screen.getAllByTestId(/^c360-section-/)).toHaveLength(3);
  });

  it('shows the read-only servicing badge on a Case B installments section', async () => {
    const data = partial();
    data.installments = {
      state: 'present',
      outstanding_principal: '800.00',
      contract_count: 1,
      read_only_servicing_continuity: true,
    };
    c360Mock.mockResolvedValue({ data, message: 'ok', meta: META });
    renderPage();
    expect(await screen.findByTestId('c360-servicing-badge')).toHaveTextContent('Read-only servicing');
  });

  it('renders the standard not-found page on 404 — never an "empty" customer page', async () => {
    c360Mock.mockRejectedValue(notFoundError());
    renderPage();
    expect(await screen.findByTestId('standard-not-found')).toBeInTheDocument();
    expect(screen.queryByTestId(/^c360-section-/)).not.toBeInTheDocument();
    expect(screen.queryByTestId('report-state-empty')).not.toBeInTheDocument();
    expect(screen.queryByTestId('report-state-error')).not.toBeInTheDocument();
  });

  it('treats a malformed customer id (422) as not found too', async () => {
    mockParams = { customerId: 'not-a-uuid' };
    c360Mock.mockRejectedValue(
      new ApiClientError(422, { error: { code: 'VALIDATION_ERROR', message: 'x', details: {} } })
    );
    renderPage();
    expect(await screen.findByTestId('standard-not-found')).toBeInTheDocument();
  });

  it('renders the permission-denied state (not not-found) on a base-permission 403', async () => {
    c360Mock.mockRejectedValue(
      new ApiClientError(403, {
        error: { code: 'REPORT_PERMISSION_DENIED', message: 'x', details: {} },
      })
    );
    renderPage();
    expect(await screen.findByTestId('report-state-permission-denied')).toBeInTheDocument();
  });

  it('has no axe violations (T258)', async () => {
    c360Mock.mockResolvedValue({ data: partial(), message: 'ok', meta: META });
    const { container } = renderPage();
    await screen.findByRole('heading', { name: 'Acme Trading' });
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe('IDOR-safe navigation (T257)', () => {
  it('a cross-tenant customerId shows the standard not-found page with no identity flash', async () => {
    const CROSS_TENANT_ID = '99999999-8888-7777-6666-555555555555';
    mockParams = { customerId: CROSS_TENANT_ID };
    let reject: (error: unknown) => void = () => undefined;
    c360Mock.mockReturnValue(
      new Promise((_resolve, rej) => {
        reject = rej;
      })
    );
    renderPage();

    // While the request is in flight nothing identifying is rendered —
    // not even the id from the URL.
    expect(await screen.findByRole('status', { name: 'Loading customer…' })).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(CROSS_TENANT_ID);
    expect(screen.queryByRole('heading', { level: 1 })).not.toBeInTheDocument();

    // The backend answers exactly as it would for a nonexistent customer.
    reject(notFoundError());
    expect(await screen.findByTestId('standard-not-found')).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(CROSS_TENANT_ID);
    expect(screen.queryByRole('heading', { level: 1 })).not.toBeInTheDocument();
    await waitFor(() => expect(c360Mock).toHaveBeenCalledWith('company-1', CROSS_TENANT_ID));
  });

  it('a cross-tenant id and a nonexistent id render byte-identical pages', async () => {
    const pages: string[] = [];
    for (const id of ['99999999-8888-7777-6666-555555555555', '00000000-0000-0000-0000-000000000000']) {
      mockParams = { customerId: id };
      c360Mock.mockRejectedValue(notFoundError());
      const { container, unmount } = renderPage();
      await screen.findByTestId('standard-not-found');
      pages.push(container.innerHTML);
      unmount();
    }
    expect(pages[0]).toBe(pages[1]);
  });
});
