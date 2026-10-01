/**
 * Row- and report-level drill-down links (FR-RPT-180/182).
 */

import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { DataTable } from '@/components/reports/DataTable';
import {
  isRowLevel,
  rowDrillDownHref,
  splitDrillDowns,
} from '@/components/reports/drillDown';
import type { DrillDownRef } from '@/lib/api/reports';

const CONTRACT: DrillDownRef = {
  label: 'View contract',
  target_route: '/contracts/{contract_id}',
  required_permission: 'installments.contracts.view',
};
const INVOICES: DrillDownRef = {
  label: 'View invoices',
  target_route: '/invoices?date_from=2026-09-01&date_to=2026-09-30',
  required_permission: 'sales.invoices.read',
};

describe('drill-down helpers', () => {
  it('splits row-level (placeholder) refs from report-level refs', () => {
    expect(isRowLevel(CONTRACT)).toBe(true);
    expect(isRowLevel(INVOICES)).toBe(false);
    expect(splitDrillDowns([CONTRACT, INVOICES])).toEqual({
      rowLinks: [CONTRACT],
      reportLinks: [INVOICES],
    });
    expect(splitDrillDowns(undefined)).toEqual({ rowLinks: [], reportLinks: [] });
  });

  it('fills placeholders from the row, keeping the preserved query string', () => {
    const ref = { ...CONTRACT, target_route: '/purchase-orders/{po_id}?supplier_id=s-1' };
    expect(rowDrillDownHref(ref, { po_id: 'po 1' })).toBe('/purchase-orders/po%201?supplier_id=s-1');
  });

  it('returns null when the row lacks a placeholder value', () => {
    expect(rowDrillDownHref(CONTRACT, { contract_id: null })).toBeNull();
    expect(rowDrillDownHref(CONTRACT, { other: 'x' })).toBeNull();
  });
});

describe('DataTable rowLinks', () => {
  it('links each row that has the id, and only those', () => {
    render(
      <DataTable
        caption="Register"
        rows={[
          { contract_number: 'C-1', contract_id: 'abc' },
          { contract_number: 'C-2', contract_id: null },
        ]}
        columns={[{ key: 'contract_number', label: 'Contract' }]}
        rowLinks={[CONTRACT]}
      />
    );
    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]!).getByRole('link', { name: 'View contract' })).toHaveAttribute(
      'href',
      '/contracts/abc'
    );
    expect(within(rows[1]!).queryByRole('link')).not.toBeInTheDocument();
  });

  it('adds no column without row links', () => {
    render(
      <DataTable caption="Plain" rows={[{ a: '1' }]} columns={[{ key: 'a', label: 'A' }]} />
    );
    expect(screen.getAllByRole('columnheader')).toHaveLength(1);
  });
});
