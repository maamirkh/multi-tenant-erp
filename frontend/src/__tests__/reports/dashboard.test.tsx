/**
 * T254 — Executive Dashboard rendering: 3 omitted + 1 unavailable widget
 * renders exactly 6 full cards + 1 unavailable card — never 10 cards with 4
 * blanks. T258 (dashboard half) — axe.
 */

import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { axe, toHaveNoViolations } from 'jest-axe';
import AnalyticsOverviewPage from '@/app/(protected)/(reports)/analytics/page';
import { ApiClientError } from '@/lib/api/client';
import { getDashboard, type ExecutiveDashboardResponse } from '@/lib/api/reports';

expect.extend(toHaveNoViolations);

jest.mock('next/navigation', () => ({ usePathname: () => '/analytics' }));
jest.mock('@/lib/api/reports', () => {
  const actual = jest.requireActual('@/lib/api/reports');
  return { ...actual, getDashboard: jest.fn() };
});

const dashboardMock = getDashboard as jest.MockedFunction<typeof getDashboard>;
const META = { request_id: 'r', timestamp: '2026-09-28T00:00:00Z' };
const base = { comparison: null, drill_down: null };

function payload(): ExecutiveDashboardResponse {
  return {
    period: {
      start: '2026-09-01T00:00:00Z',
      end: '2026-10-01T00:00:00Z',
      timezone: 'UTC',
      is_partial_current_period: true,
    },
    net_sales: {
      ...base,
      state: 'present',
      value: '1500.00',
      comparison: { absolute_change: '150.00', percentage_change: '11.11', comparability: 'full' },
    },
    gross_sales: { ...base, state: 'present', value: '1650.00' },
    purchase_spend: { ...base, state: 'present', value: '0' },
    ar: { ...base, state: 'unavailable', balance: null, overdue: null },
    ap: { ...base, state: 'present', value: '420.00' },
    cash_position: { ...base, state: 'present', value: '-35.50' },
    operational_inventory_value: {
      ...base,
      state: 'present',
      value: '9000.00',
      valuation_basis: 'operational_wac',
    },
    crm_pipeline: { ...base, state: 'omitted', pipeline_value: null, win_rate: null },
    installment_exposure: {
      ...base,
      state: 'omitted',
      outstanding_principal: null,
      overdue: null,
      read_only_servicing_continuity: false,
    },
    gross_profit_margin: { ...base, state: 'omitted', value: null },
  };
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AnalyticsOverviewPage />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  window.localStorage.setItem('erp_active_company_id', 'company-1');
});
afterEach(() => window.localStorage.clear());

describe('Executive Dashboard', () => {
  it('renders 6 full cards + 1 unavailable card for 3 omitted + 1 unavailable widgets', async () => {
    dashboardMock.mockResolvedValue({ data: payload(), message: 'ok', meta: META });
    renderPage();
    const list = await screen.findByRole('list', { name: 'Key figures' });
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(7); // never 10 with 4 blanks
    expect(items.filter((i) => i.dataset['state'] === 'present')).toHaveLength(6);
    expect(within(list).getAllByTestId('dashboard-widget-unavailable')).toHaveLength(1);
    expect(within(list).getByText('Currently unavailable')).toBeInTheDocument();
    for (const omitted of ['crm_pipeline', 'installment_exposure', 'gross_profit_margin']) {
      expect(screen.queryByTestId(`dashboard-widget-${omitted}`)).not.toBeInTheDocument();
    }
    expect(screen.queryByText(/CRM pipeline/)).not.toBeInTheDocument();
  });

  it('renders present values, real zeros, signs, comparisons and the WAC disclaimer', async () => {
    dashboardMock.mockResolvedValue({ data: payload(), message: 'ok', meta: META });
    renderPage();
    const netSales = await screen.findByTestId('dashboard-widget-net_sales');
    expect(netSales).toHaveTextContent('1,500.00');
    expect(netSales).toHaveTextContent('+11.11%');
    expect(screen.getByTestId('dashboard-widget-purchase_spend')).toHaveTextContent('0.00');
    expect(screen.getByTestId('dashboard-widget-cash_position')).toHaveTextContent('-35.50');
    expect(screen.getByTestId('dashboard-widget-operational_inventory_value')).toHaveTextContent(
      /not a reconciled accounting balance/
    );
    expect(screen.getByText('Sep 1, 2026 – Sep 30, 2026 (to date)')).toBeInTheDocument();
  });

  it('shows the Installments continuity badge only under servicing continuity', async () => {
    const data = payload();
    data.installment_exposure = {
      ...base,
      state: 'present',
      outstanding_principal: '800.00',
      overdue: '100.00',
      read_only_servicing_continuity: true,
    };
    dashboardMock.mockResolvedValue({ data, message: 'ok', meta: META });
    renderPage();
    const widget = await screen.findByTestId('dashboard-widget-installment_exposure');
    expect(within(widget).getByTestId('installments-servicing-badge')).toHaveTextContent(
      'Read-only servicing'
    );
    expect(widget).toHaveTextContent('Overdue: 100.00');
  });

  it('links a widget to its drill-down report under /analytics (FR-RPT-180)', async () => {
    const data = payload();
    data.net_sales = {
      ...data.net_sales,
      drill_down: {
        label: 'View sales KPIs',
        target_route: '/reports/sales.kpis',
        required_permission: 'reports.sales.view',
      },
    };
    dashboardMock.mockResolvedValue({ data, message: 'ok', meta: META });
    renderPage();
    const link = await screen.findByTestId('dashboard-drilldown-net_sales');
    expect(link).toHaveTextContent('View sales KPIs');
    expect(link).toHaveAttribute('href', '/analytics/sales.kpis');
    // No drill-down reference → no link.
    expect(screen.queryByTestId('dashboard-drilldown-gross_sales')).not.toBeInTheDocument();
  });

  it('shows a multi-currency figure per currency, never summed (FR-RPT-152)', async () => {
    const data = payload();
    data.gross_sales = {
      ...base,
      state: 'present',
      value: null,
      by_currency: [
        { currency_code: 'USD', amount: '100.00' },
        { currency_code: 'PKR', amount: '5000.00' },
      ],
    };
    data.purchase_spend = {
      ...base,
      state: 'present',
      value: '250.00',
      by_currency: [{ currency_code: 'USD', amount: '250.00' }],
    };
    dashboardMock.mockResolvedValue({ data, message: 'ok', meta: META });
    renderPage();
    const gross = await screen.findByTestId('dashboard-widget-gross_sales');
    expect(gross).toHaveTextContent('$100.00');
    expect(gross).toHaveTextContent('PKR 5,000');
    expect(gross).not.toHaveTextContent('5,100');
    // One currency: rendered in that currency.
    expect(screen.getByTestId('dashboard-widget-purchase_spend')).toHaveTextContent('$250.00');
  });

  it('renders an empty state when every widget is omitted', async () => {
    const data = payload();
    for (const key of Object.keys(data) as (keyof ExecutiveDashboardResponse)[]) {
      if (key !== 'period') (data[key] as { state: string }).state = 'omitted';
    }
    dashboardMock.mockResolvedValue({ data, message: 'ok', meta: META });
    renderPage();
    expect(await screen.findByTestId('report-state-empty')).toBeInTheDocument();
    expect(screen.queryByRole('list', { name: 'Key figures' })).not.toBeInTheDocument();
  });

  it('renders the permission-denied state on 403', async () => {
    dashboardMock.mockRejectedValue(
      new ApiClientError(403, {
        error: { code: 'REPORT_PERMISSION_DENIED', message: 'x', details: {} },
      })
    );
    renderPage();
    expect(await screen.findByTestId('report-state-permission-denied')).toBeInTheDocument();
  });

  it('has no axe violations (T258)', async () => {
    dashboardMock.mockResolvedValue({ data: payload(), message: 'ok', meta: META });
    const { container } = renderPage();
    await screen.findByRole('list', { name: 'Key figures' });
    expect(await axe(container)).toHaveNoViolations();
  });
});
