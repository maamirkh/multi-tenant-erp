/**
 * T235 — Reports accessibility (FR-RPT-331), via jest-axe (T218):
 * - DataTable: zero axe violations; every sort/pagination control is a
 *   native, focusable button reachable by keyboard; the active sort column
 *   exposes `aria-sort`.
 * - ChartWrapper: the chart's accessible table alternative is present and
 *   labelled by the chart's title; the SVG itself is hidden from AT.
 * - Availability states: each announces itself with text (never color
 *   alone) and has zero axe violations.
 */

import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import { DataTable, type DataTableColumn } from '@/components/reports/DataTable';
import { ChartWrapper } from '@/components/reports/ChartWrapper';
import {
  EmptyState,
  ErrorState,
  ModuleDisabledState,
  PermissionDeniedState,
  UnavailableState,
} from '@/components/reports/states';

expect.extend(toHaveNoViolations);

beforeAll(() => {
  // Recharts' ResponsiveContainer needs ResizeObserver, which jsdom lacks.
  class ResizeObserverStub {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  (globalThis as unknown as { ResizeObserver: typeof ResizeObserverStub }).ResizeObserver =
    ResizeObserverStub;
});

const COLUMNS: DataTableColumn[] = [
  { key: 'customer_name', label: 'Customer', sortable: true },
  { key: 'revenue', label: 'Revenue', format: 'money', currency: 'USD', sortable: true },
  { key: 'invoice_count', label: 'Invoices', format: 'number' },
];

const ROWS = [
  { customer_name: 'Acme', revenue: '1200.50', invoice_count: 3 },
  { customer_name: 'Globex', revenue: '-45.00', invoice_count: 1 },
];

describe('DataTable accessibility', () => {
  it('has no axe violations', async () => {
    const { container } = render(
      <DataTable
        caption="Sales by customer"
        rows={ROWS}
        columns={COLUMNS}
        sortField="revenue"
        onSortChange={() => undefined}
        pagination={{ kind: 'offset', page: 1, pageSize: 2, total: 4, onPageChange: () => undefined }}
      />
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it('is keyboard-operable: sort and pagination are focusable native buttons', () => {
    const onSortChange = jest.fn();
    const onPageChange = jest.fn();
    render(
      <DataTable
        caption="Sales by customer"
        rows={ROWS}
        columns={COLUMNS}
        sortField={null}
        onSortChange={onSortChange}
        pagination={{ kind: 'offset', page: 1, pageSize: 2, total: 4, onPageChange }}
      />
    );

    const table = screen.getByRole('table', { name: 'Sales by customer' });
    const sortButtons = within(table).getAllByRole('button');
    expect(sortButtons).toHaveLength(2); // only the sortable columns
    for (const button of sortButtons) {
      expect(button.tagName).toBe('BUTTON');
      button.focus();
      expect(button).toHaveFocus();
    }
    // Native buttons activate on Enter/Space via click in the browser.
    fireEvent.click(sortButtons[1]!);
    expect(onSortChange).toHaveBeenCalledWith('revenue');

    const next = screen.getByRole('button', { name: 'Next' });
    next.focus();
    expect(next).toHaveFocus();
    fireEvent.click(next);
    expect(onPageChange).toHaveBeenCalledWith(2);
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
  });

  it('exposes the active sort column via aria-sort', () => {
    render(
      <DataTable
        caption="Sales by customer"
        rows={ROWS}
        columns={COLUMNS}
        sortField="revenue"
        onSortChange={() => undefined}
      />
    );
    expect(screen.getByRole('columnheader', { name: /Revenue/ })).toHaveAttribute(
      'aria-sort',
      'descending'
    );
    expect(screen.getByRole('columnheader', { name: /Customer/ })).not.toHaveAttribute('aria-sort');
  });

  it('shows negative amounts with a sign, not color alone', () => {
    render(<DataTable caption="Sales" rows={ROWS} columns={COLUMNS} />);
    expect(screen.getByText('-$45.00')).toBeInTheDocument();
  });
});

describe('ChartWrapper accessibility', () => {
  const data = [
    { date: '2026-01-01', revenue: '100.00' },
    { date: '2026-01-02', revenue: '250.50' },
  ];

  it('renders a labelled data-table alternative with every value', () => {
    render(
      <ChartWrapper
        title="Revenue trend"
        type="line"
        data={data}
        xKey="date"
        xLabel="Date"
        series={[{ key: 'revenue', label: 'Revenue' }]}
        formatValue={(v) => `$${v}`}
      />
    );
    const table = screen.getByRole('table', { name: 'Revenue trend', hidden: true });
    expect(within(table).getByRole('columnheader', { name: 'Date', hidden: true })).toBeInTheDocument();
    expect(within(table).getByRole('columnheader', { name: 'Revenue', hidden: true })).toBeInTheDocument();
    expect(within(table).getByText('$250.50')).toBeInTheDocument();
    expect(screen.getByRole('figure', { name: 'Revenue trend' })).toBeInTheDocument();
  });

  it('hides the SVG chart from assistive technology and has no axe violations', async () => {
    const { container } = render(
      <ChartWrapper
        title="Revenue by customer"
        type="bar"
        data={data}
        xKey="date"
        series={[{ key: 'revenue', label: 'Revenue' }]}
      />
    );
    const chartBox = container.querySelector('figure > div');
    expect(chartBox).toHaveAttribute('aria-hidden', 'true');
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe('availability states', () => {
  const cases: Array<[string, React.JSX.Element, RegExp]> = [
    ['empty', <EmptyState key="e" />, /No data for this selection/],
    ['error', <ErrorState key="x" onRetry={() => undefined} />, /Something went wrong/],
    ['permission', <PermissionDeniedState key="p" />, /Access restricted/],
    ['module disabled', <ModuleDisabledState key="m" moduleName="CRM" />, /Module not enabled/],
    ['unavailable', <UnavailableState key="u" />, /Not available yet/],
  ];

  it.each(cases)('%s state communicates with text and passes axe', async (_name, element, title) => {
    const { container } = render(element);
    expect(screen.getByText(title)).toBeInTheDocument();
    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
    expect(await axe(container)).toHaveNoViolations();
  });

  it('keeps the five states textually distinct from each other', () => {
    const titles = cases.map(([, element]) => {
      const { container, unmount } = render(element);
      const text = container.textContent ?? '';
      unmount();
      return text;
    });
    expect(new Set(titles).size).toBe(cases.length);
  });

  it('announces errors assertively and other states politely', () => {
    const { rerender } = render(<ErrorState />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    rerender(<UnavailableState />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });
});
