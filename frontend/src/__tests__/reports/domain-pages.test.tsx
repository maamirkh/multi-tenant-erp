/**
 * T249 — Phase 8 domain report pages (one describe block per domain + the
 * generic `[reportKey]` view): filter interaction, permission-denied /
 * module-disabled rendering, and export-button wiring.
 * T250 — axe accessibility pass over all 7 pages (extends T235).
 */

import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { axe, toHaveNoViolations } from 'jest-axe';
import SalesPage from '@/app/(protected)/(reports)/analytics/sales/page';
import PurchasePage from '@/app/(protected)/(reports)/analytics/purchase/page';
import InventoryPage from '@/app/(protected)/(reports)/analytics/inventory/page';
import FinancePage from '@/app/(protected)/(reports)/analytics/finance/page';
import CrmPage from '@/app/(protected)/(reports)/analytics/crm/page';
import InstallmentsPage from '@/app/(protected)/(reports)/analytics/installments/page';
import ReportDetailPage from '@/app/(protected)/(reports)/analytics/[reportKey]/page';
import { ApiClientError } from '@/lib/api/client';
import {
  exportReport,
  getReport,
  getReportDiscovery,
  listSavedViews,
  saveExportedFile,
  type ExportFormat,
  type GetReportParams,
  type ReportData,
  type ReportDiscoveryItem,
  type ReportResponse,
} from '@/lib/api/reports';

expect.extend(toHaveNoViolations);

let mockParams: Record<string, string> = {};
jest.mock('next/navigation', () => ({
  usePathname: () => '/analytics',
  useParams: () => mockParams,
}));

jest.mock('@/lib/api/reports', () => {
  const actual = jest.requireActual('@/lib/api/reports');
  return {
    ...actual,
    getReportDiscovery: jest.fn(),
    getReport: jest.fn(),
    exportReport: jest.fn(),
    saveExportedFile: jest.fn(),
    listSavedViews: jest.fn(),
  };
});

jest.mock('@/lib/api/accounting', () => ({
  getFiscalYears: jest.fn().mockResolvedValue({
    data: [{ id: 'fy-1', fiscal_year_name: 'FY2026' }],
  }),
  getFiscalPeriods: jest.fn().mockResolvedValue({
    data: [{ id: 'period-1', period_name: 'January' }],
  }),
  getBankAccounts: jest.fn().mockResolvedValue({ data: [] }),
  getCashAccounts: jest.fn().mockResolvedValue({ data: [] }),
  getCostCenters: jest.fn().mockResolvedValue({ data: [] }),
}));

const discoveryMock = getReportDiscovery as jest.MockedFunction<typeof getReportDiscovery>;
const reportMock = getReport as jest.MockedFunction<typeof getReport>;
const exportMock = exportReport as jest.MockedFunction<typeof exportReport>;
const saveMock = saveExportedFile as jest.MockedFunction<typeof saveExportedFile>;
const savedViewsMock = listSavedViews as jest.MockedFunction<typeof listSavedViews>;

const META = { request_id: 'r', timestamp: '2026-09-28T00:00:00Z' };

function item(
  key: string,
  domain: string,
  exportFormats: ExportFormat[] = [],
  name = key
): ReportDiscoveryItem {
  return {
    key,
    name,
    domain,
    description: `${name} description`,
    exportable: exportFormats.length > 0,
    export_formats: exportFormats,
    branch_filterable: false,
    drill_down_targets: [],
  };
}

function reportResponse(
  reportKey: string,
  data: ReportData,
  readOnlyServicing = false
): ReportResponse {
  return {
    data,
    report_meta: {
      report_key: reportKey,
      applied_filters: {},
      period: {
        start: '2026-01-01T00:00:00Z',
        end: '2026-02-01T00:00:00Z',
        timezone: 'UTC',
        is_partial_current_period: false,
      },
      freshness: 'transactional_live',
      drill_down: [],
      comparison: null,
      read_only_servicing_continuity: readOnlyServicing,
    },
    message: 'ok',
    meta: META,
  };
}

function paginated(items: Record<string, string | number | null>[]): ReportData {
  return { items, total: items.length, page: 1, page_size: 20, pages: 1 };
}

function forbidden(code: string): ApiClientError {
  return new ApiClientError(403, { error: { code, message: code, details: {} } });
}

function setDiscovery(reports: ReportDiscoveryItem[]): void {
  discoveryMock.mockResolvedValue({ data: { reports }, message: 'ok', meta: META });
}

function renderPage(Page: () => React.JSX.Element) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Page />
    </QueryClientProvider>
  );
}

function lastReportCall(): [string, string, GetReportParams | undefined] {
  const call = reportMock.mock.calls.at(-1);
  if (!call) throw new Error('getReport was never called');
  return [call[0], call[1], call[2]];
}

beforeEach(() => {
  jest.clearAllMocks();
  mockParams = {};
  window.localStorage.setItem('erp_active_company_id', 'company-1');
  savedViewsMock.mockResolvedValue({
    data: { items: [], total: 0, page: 1, page_size: 100, pages: 0 },
    message: 'ok',
    meta: META,
  });
});

afterEach(() => {
  window.localStorage.clear();
});

// ---------------------------------------------------------------------------

describe('Sales page', () => {
  beforeEach(() => {
    setDiscovery([
      item('sales.by_customer', 'sales', ['csv', 'xlsx'], 'Sales by Customer'),
      item('sales.kpis', 'sales', [], 'Sales KPI Dashboard'),
    ]);
    reportMock.mockImplementation(async (_c, key) =>
      reportResponse(
        key,
        key === 'sales.kpis'
          ? { net_sales: '1500.00' }
          : paginated([{ customer_name: 'Acme', invoice_count: 2, revenue: '1200.50' }])
      )
    );
  });

  it('lists only discovered reports and runs the first with typed columns', async () => {
    renderPage(SalesPage);
    const nav = await screen.findByRole('navigation', { name: 'Sales reports' });
    expect(within(nav).getAllByRole('button')).toHaveLength(2);
    // Sales rows carry no currency code, so money renders without a symbol.
    expect(await screen.findByText('1,200.50')).toBeInTheDocument();
    expect(lastReportCall()[0]).toBe('company-1');
    expect(lastReportCall()[1]).toBe('sales.by_customer');
  });

  it('applies filters only on submit, sending the backend field names', async () => {
    renderPage(SalesPage);
    await screen.findByText('Acme');
    const callsBefore = reportMock.mock.calls.length;
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2026-01-01' } });
    expect(reportMock.mock.calls.length).toBe(callsBefore); // no query per keystroke
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    await waitFor(() =>
      expect(lastReportCall()[2]?.filters).toEqual({ date_from: '2026-01-01' })
    );
    expect(lastReportCall()[2]?.page).toBe(1);
  });

  it('exports in the exact applied filter scope, only in discovered formats', async () => {
    exportMock.mockResolvedValue({ blob: new Blob(['x']), filename: 'sales-by_customer.csv' });
    renderPage(SalesPage);
    await screen.findByText('Acme');
    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2026-01-31' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    await waitFor(() => expect(lastReportCall()[2]?.filters).toEqual({ date_to: '2026-01-31' }));

    expect(screen.getByRole('button', { name: /Export CSV/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Export Excel/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Export PDF/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Export CSV/ }));
    await waitFor(() =>
      expect(exportMock).toHaveBeenCalledWith('company-1', 'sales.by_customer', 'csv', {
        filters: { date_to: '2026-01-31' },
        sort: undefined,
      })
    );
    expect(saveMock).toHaveBeenCalled();
  });

  it('shows the too-large message when an export exceeds the limit', async () => {
    exportMock.mockRejectedValue(
      new ApiClientError(422, { error: { code: 'EXPORT_TOO_LARGE', message: 'x', details: {} } })
    );
    renderPage(SalesPage);
    await screen.findByText('Acme');
    fireEvent.click(screen.getByRole('button', { name: /Export CSV/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/Narrow your filters/);
  });

  it('renders the permission-denied state for REPORT_PERMISSION_DENIED', async () => {
    reportMock.mockRejectedValue(forbidden('REPORT_PERMISSION_DENIED'));
    renderPage(SalesPage);
    expect(await screen.findByTestId('report-state-permission-denied')).toBeInTheDocument();
  });

  it('renders the module-disabled state when discovery says reports is not entitled', async () => {
    discoveryMock.mockRejectedValue(forbidden('REPORT_NOT_ENTITLED'));
    renderPage(SalesPage);
    expect(await screen.findByTestId('report-state-module-disabled')).toBeInTheDocument();
    expect(reportMock).not.toHaveBeenCalled();
  });

  it('renders aggregates without export when the report has no export formats', async () => {
    renderPage(SalesPage);
    fireEvent.click(await screen.findByRole('button', { name: 'Sales KPI Dashboard' }));
    expect(await screen.findByText('Net sales')).toBeInTheDocument();
    expect(screen.getByText('1,500')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Export/ })).not.toBeInTheDocument();
  });
});

describe('Purchase page', () => {
  beforeEach(() => {
    setDiscovery([
      item('purchase.summary', 'purchase', ['csv'], 'Purchase Summary'),
      item('purchase.open_commitments', 'purchase', ['csv'], 'Open Purchase Commitments'),
    ]);
    reportMock.mockImplementation(async (_c, key) => reportResponse(key, paginated([])));
  });

  it('offers the branch filter only on open commitments / pending deliveries', async () => {
    renderPage(PurchasePage);
    await screen.findByLabelText('Supplier ID');
    expect(screen.queryByLabelText('Branch ID')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Open Purchase Commitments' }));
    expect(await screen.findByLabelText('Branch ID')).toBeInTheDocument();
  });

  it('renders the empty state for a zero-row result', async () => {
    renderPage(PurchasePage);
    expect(await screen.findByTestId('report-state-empty')).toBeInTheDocument();
  });

  it('renders the module-disabled state for REPORT_NOT_ENTITLED', async () => {
    reportMock.mockRejectedValue(forbidden('REPORT_NOT_ENTITLED'));
    renderPage(PurchasePage);
    expect(await screen.findByTestId('report-state-module-disabled')).toBeInTheDocument();
  });
});

describe('Inventory page', () => {
  it('renders the valuation-basis disclaimer visibly', async () => {
    setDiscovery([item('inventory.valuation', 'inventory', ['csv'], 'Operational Stock Valuation')]);
    reportMock.mockImplementation(async (_c, key) =>
      reportResponse(key, { grand_total_value: '5000.00', valuation_basis: 'operational_wac', rows: [] })
    );
    renderPage(InventoryPage);
    const disclaimer = await screen.findByTestId('report-disclaimer');
    expect(disclaimer).toBeVisible();
    expect(disclaimer).toHaveTextContent(/not a reconciled accounting balance/);
  });

  it('derives columns for pass-through inventory rows', async () => {
    setDiscovery([item('inventory.dead_stock', 'inventory', ['csv'], 'Dead Stock')]);
    reportMock.mockImplementation(async (_c, key) =>
      reportResponse(key, paginated([{ product_name: 'Widget', days_idle: 120 }]))
    );
    renderPage(InventoryPage);
    expect(await screen.findByRole('columnheader', { name: 'Product name' })).toBeInTheDocument();
    await waitFor(() =>
      expect(lastReportCall()[2]?.filters).toEqual({ threshold_days: '90' })
    );
  });
});

describe('Finance page', () => {
  it('does not run a report until its required filters are filled', async () => {
    setDiscovery([item('accounting.trial_balance', 'accounting', ['pdf', 'xlsx'], 'Trial Balance')]);
    reportMock.mockImplementation(async (_c, key) => reportResponse(key, { total_debit: '10.00' }));
    renderPage(FinancePage);
    expect(await screen.findByTestId('missing-filters')).toHaveTextContent('Fiscal period');
    expect(reportMock).not.toHaveBeenCalled();

    // Renders as a text input until the fiscal-period lookup loads, then a select.
    const select = await screen.findByRole('combobox', { name: 'Fiscal period' });
    expect(within(select).getByRole('option', { name: 'FY2026 · January' })).toBeInTheDocument();
    fireEvent.change(select, { target: { value: 'period-1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    await waitFor(() => expect(lastReportCall()[2]?.filters).toEqual({ period_id: 'period-1' }));
    expect(await screen.findByRole('button', { name: /Export PDF/ })).toBeInTheDocument();
  });

  it('pages the General Ledger with a cursor "Load more", not numbered pages', async () => {
    setDiscovery([item('accounting.gl', 'accounting', ['csv'], 'General Ledger')]);
    reportMock.mockImplementation(async (_c, key, params) =>
      reportResponse(
        key,
        params?.filters?.['cursor'] === 'c2'
          ? { items: [{ posting_date: '2026-01-02', account_code: '2000' }], has_more: false, next_cursor: null }
          : { items: [{ posting_date: '2026-01-01', account_code: '1000' }], has_more: true, next_cursor: 'c2' }
      )
    );
    renderPage(FinancePage);
    expect(await screen.findByText('1000')).toBeInTheDocument();
    expect(screen.queryByText(/Page \d+ of/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Load more' }));
    expect(await screen.findByText('2000')).toBeInTheDocument();
    expect(screen.getByText('1000')).toBeInTheDocument(); // appended, not replaced
    expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument();
  });
});

describe('CRM page', () => {
  it('renders CRM reports with no export or branch controls', async () => {
    setDiscovery([item('crm.pipeline', 'crm', [], 'Pipeline Report')]);
    reportMock.mockImplementation(async (_c, key) =>
      reportResponse(key, { total_pipeline_value: '900.00', stages: [{ stage: 'Won', count: 2 }] })
    );
    renderPage(CrmPage);
    expect(await screen.findByText('Total pipeline value')).toBeInTheDocument();
    expect(screen.getByRole('table', { name: 'Stages' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Export/ })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Branch/)).not.toBeInTheDocument();
  });

  it('renders the permission-denied state', async () => {
    setDiscovery([item('crm.pipeline', 'crm', [], 'Pipeline Report')]);
    reportMock.mockRejectedValue(forbidden('REPORT_PERMISSION_DENIED'));
    renderPage(CrmPage);
    expect(await screen.findByTestId('report-state-permission-denied')).toBeInTheDocument();
  });
});

describe('Installments page', () => {
  it('shows the read-only servicing banner under Case B and hides non-allow-listed reports', async () => {
    // Case B discovery: plan_performance/dashboard are simply absent.
    setDiscovery([
      item('installments.register', 'installments', ['csv'], 'Contract Register'),
      item('installments.aging', 'installments', ['csv'], 'Installment Aging'),
    ]);
    reportMock.mockImplementation(async (_c, key) =>
      reportResponse(key, paginated([{ contract_number: 'C-1' }]), true)
    );
    renderPage(InstallmentsPage);
    expect(await screen.findByTestId('servicing-continuity-banner')).toBeInTheDocument();
    const nav = screen.getByRole('navigation', { name: 'Installments reports' });
    expect(within(nav).queryByText(/Plan/)).not.toBeInTheDocument();
    expect(within(nav).queryByText(/Dashboard/)).not.toBeInTheDocument();
    expect(within(nav).getAllByRole('button')).toHaveLength(2);
  });

  it('shows no banner when fully entitled', async () => {
    setDiscovery([item('installments.register', 'installments', ['csv'], 'Contract Register')]);
    reportMock.mockImplementation(async (_c, key) =>
      reportResponse(key, paginated([{ contract_number: 'C-1' }]), false)
    );
    renderPage(InstallmentsPage);
    expect(await screen.findByText('C-1')).toBeInTheDocument();
    expect(screen.queryByTestId('servicing-continuity-banner')).not.toBeInTheDocument();
  });

  it('sends the status filter as the backend enum value', async () => {
    setDiscovery([item('installments.register', 'installments', ['csv'], 'Contract Register')]);
    reportMock.mockImplementation(async (_c, key) => reportResponse(key, paginated([])));
    renderPage(InstallmentsPage);
    fireEvent.change(await screen.findByLabelText('Status'), { target: { value: 'ACTIVE' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    await waitFor(() => expect(lastReportCall()[2]?.filters).toEqual({ status: 'ACTIVE' }));
  });
});

describe('Generic [reportKey] page', () => {
  it('renders any discoverable report through the same view', async () => {
    mockParams = { reportKey: 'sales.by_customer' };
    setDiscovery([item('sales.by_customer', 'sales', ['csv'], 'Sales by Customer')]);
    reportMock.mockImplementation(async (_c, key) =>
      reportResponse(key, paginated([{ customer_name: 'Acme', invoice_count: 1, revenue: '5.00' }]))
    );
    renderPage(ReportDetailPage);
    expect(await screen.findByRole('heading', { name: 'Sales by Customer' })).toBeInTheDocument();
    expect(await screen.findByText('Acme')).toBeInTheDocument();
  });

  it('never requests a report that discovery does not return', async () => {
    mockParams = { reportKey: 'accounting.tax' }; // deferred / not discoverable
    setDiscovery([item('sales.by_customer', 'sales')]);
    renderPage(ReportDetailPage);
    expect(await screen.findByText('Report not available')).toBeInTheDocument();
    expect(reportMock).not.toHaveBeenCalled();
  });

  it('sends composite reports to their dedicated pages, not the generic view', async () => {
    mockParams = { reportKey: 'exec.dashboard' };
    setDiscovery([item('exec.dashboard', 'executive')]);
    renderPage(ReportDetailPage);
    expect(await screen.findByText('Report not available')).toBeInTheDocument();
    expect(reportMock).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// T250 — accessibility pass on all 7 pages
// ---------------------------------------------------------------------------

describe('accessibility (T250)', () => {
  const pages: Array<[string, () => React.JSX.Element, ReportDiscoveryItem, ReportData]> = [
    ['sales', SalesPage, item('sales.by_customer', 'sales', ['csv']), paginated([{ customer_name: 'A', invoice_count: 1, revenue: '1.00' }])],
    ['purchase', PurchasePage, item('purchase.summary', 'purchase', ['csv']), paginated([{ po_number: 'PO-1', total: '2.00' }])],
    ['inventory', InventoryPage, item('inventory.valuation', 'inventory', ['csv']), { grand_total_value: '3.00', rows: [] }],
    ['finance', FinancePage, item('accounting.ar_aging', 'accounting', ['csv']), paginated([{ customer_id: 'c', total: '4.00' }])],
    ['crm', CrmPage, item('crm.dashboard', 'crm'), { open_leads: 3 }],
    ['installments', InstallmentsPage, item('installments.due_overdue', 'installments', ['csv']), paginated([{ contract_number: 'C-1' }])],
  ];

  it.each(pages)('%s page has no axe violations', async (_name, Page, discovered, data) => {
    setDiscovery([discovered]);
    reportMock.mockImplementation(async (_c, key) => reportResponse(key, data));
    const { container } = renderPage(Page);
    await screen.findByRole('navigation');
    await waitFor(() => expect(reportMock).toHaveBeenCalled());
    await screen.findByRole('group', { name: 'Export report' }).catch(() => undefined);
    expect(await axe(container)).toHaveNoViolations();
  });

  it('generic [reportKey] page has no axe violations', async () => {
    mockParams = { reportKey: 'sales.by_customer' };
    setDiscovery([item('sales.by_customer', 'sales', ['csv'], 'Sales by Customer')]);
    reportMock.mockImplementation(async (_c, key) =>
      reportResponse(key, paginated([{ customer_name: 'A', invoice_count: 1, revenue: '1.00' }]))
    );
    const { container } = renderPage(ReportDetailPage);
    await screen.findByText('A');
    expect(await axe(container)).toHaveNoViolations();
  });
});
