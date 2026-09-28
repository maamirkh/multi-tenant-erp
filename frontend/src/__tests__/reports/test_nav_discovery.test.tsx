/**
 * T237 — Reports navigation is driven entirely by discovery (FR-RPT-320):
 * - a CRM-disabled tenant (discovery returns no `crm` keys) never renders
 *   the CRM link;
 * - a `reports`-disabled tenant (discovery 403 REPORT_NOT_ENTITLED)
 *   renders no Reports nav at all — no probe, no empty heading;
 * - links point at the `/analytics` tree, never at CRM/Accounting's
 *   existing `/reports` pages.
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ReportsNavSection from '@/components/layout/ReportsNavSection';
import { ApiClientError } from '@/lib/api/client';
import { getReportDiscovery, type ReportDiscoveryItem } from '@/lib/api/reports';

jest.mock('next/navigation', () => ({
  usePathname: () => '/analytics',
}));

jest.mock('@/lib/api/reports', () => {
  const actual = jest.requireActual('@/lib/api/reports');
  return { ...actual, getReportDiscovery: jest.fn() };
});

const mockedDiscovery = getReportDiscovery as jest.MockedFunction<typeof getReportDiscovery>;

function item(key: string, domain: string): ReportDiscoveryItem {
  return {
    key,
    name: key,
    domain,
    description: '',
    exportable: false,
    export_formats: [],
    branch_filterable: false,
    drill_down_targets: [],
  };
}

function discoveryResponse(reports: ReportDiscoveryItem[]) {
  return {
    data: { reports },
    message: 'ok',
    meta: { request_id: 'r', timestamp: '2026-09-28T00:00:00Z' },
  };
}

function renderNav(): { container: HTMLElement } {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ReportsNavSection />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  mockedDiscovery.mockReset();
  window.localStorage.setItem('erp_active_company_id', 'company-1');
});

afterEach(() => {
  window.localStorage.clear();
});

describe('ReportsNavSection', () => {
  it('renders only the domains discovery returns — CRM-disabled tenant has no CRM link', async () => {
    mockedDiscovery.mockResolvedValue(
      discoveryResponse([
        item('exec.dashboard', 'executive'),
        item('sales.summary', 'sales'),
        item('accounting.trial_balance', 'accounting'),
      ])
    );
    renderNav();

    expect(await screen.findByRole('link', { name: 'Overview' })).toHaveAttribute('href', '/analytics');
    expect(screen.getByRole('link', { name: 'Sales' })).toHaveAttribute('href', '/analytics/sales');
    expect(screen.getByRole('link', { name: 'Finance' })).toHaveAttribute('href', '/analytics/finance');
    expect(screen.queryByRole('link', { name: 'CRM' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Installments' })).not.toBeInTheDocument();
    expect(mockedDiscovery).toHaveBeenCalledWith('company-1');
  });

  it('renders the CRM link once discovery includes a crm key', async () => {
    mockedDiscovery.mockResolvedValue(discoveryResponse([item('crm.pipeline', 'crm')]));
    renderNav();
    expect(await screen.findByRole('link', { name: 'CRM' })).toHaveAttribute('href', '/analytics/crm');
    expect(screen.queryByRole('link', { name: 'Overview' })).not.toBeInTheDocument();
  });

  it('renders no Reports nav at all when reports is disabled for the tenant', async () => {
    mockedDiscovery.mockRejectedValue(
      new ApiClientError(403, {
        error: { code: 'REPORT_NOT_ENTITLED', message: 'not entitled', details: {} },
      })
    );
    const { container } = renderNav();
    await waitFor(() => expect(mockedDiscovery).toHaveBeenCalled());
    await waitFor(() => expect(container).toBeEmptyDOMElement());
    expect(screen.queryByText(/Reports & Analytics/)).not.toBeInTheDocument();
  });

  it('renders nothing when discovery returns zero reports', async () => {
    mockedDiscovery.mockResolvedValue(discoveryResponse([]));
    const { container } = renderNav();
    await waitFor(() => expect(mockedDiscovery).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it('does not query discovery at all without an active company', () => {
    window.localStorage.clear();
    const { container } = renderNav();
    expect(mockedDiscovery).not.toHaveBeenCalled();
    expect(container).toBeEmptyDOMElement();
  });

  it('never links into the existing CRM/Accounting /reports pages', async () => {
    mockedDiscovery.mockResolvedValue(
      discoveryResponse([item('exec.dashboard', 'executive'), item('crm.pipeline', 'crm')])
    );
    renderNav();
    await screen.findByRole('link', { name: 'Overview' });
    for (const link of screen.getAllByRole('link')) {
      expect(link.getAttribute('href')).toMatch(/^\/analytics(\/|$)/);
    }
  });
});
