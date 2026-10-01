/**
 * Code-defined per-report UI configuration (Phase 8, T242–T248; T229).
 *
 * The discovery contract carries no filter schema, so each report's filter
 * fields are declared here, **matching the backend filter schema field for
 * field** (`backend/modules/reports/schemas/<domain>.py`). Those schemas
 * are `extra="forbid"`: a field that isn't listed there must never appear
 * here, or the report 422s.
 *
 * Domain reports take explicit dates (`date_from`/`date_to`, `since`/
 * `until`, `as_of_date`), not period presets — period presets are resolved
 * server-side only for the Executive Dashboard (decision recorded in
 * tasks.md, Phase 8). No client-side period arithmetic happens here.
 *
 * `columns` gives typed formatting where the row schema is fixed; reports
 * whose rows are pass-through (`InventoryReportRow`/`InstallmentReportRow`,
 * `extra="allow"`) omit it and the table derives columns from the data.
 */

import type { DataTableColumn } from './DataTable';
import type { FilterField, FilterValues } from './FilterBar';

/** Filter fields whose options are loaded from an existing domain API. */
export type FilterLookup = 'fiscal_period' | 'bank_or_cash_account' | 'cost_center';

export interface ReportFilterField extends FilterField {
  lookup?: FilterLookup;
}

export interface ReportConfig {
  filters: ReportFilterField[];
  columns?: DataTableColumn[];
  defaults?: FilterValues;
  /** Rendered visibly above the data (e.g. a valuation-basis disclaimer). */
  disclaimer?: string;
}

// ---------------------------------------------------------------------------
// Field builders
// ---------------------------------------------------------------------------

const date = (name: string, label: string, required = false): ReportFilterField => ({
  name,
  label,
  type: 'date',
  required,
});

const text = (name: string, label: string, placeholder?: string): ReportFilterField => ({
  name,
  label,
  type: 'text',
  ...(placeholder ? { placeholder } : {}),
});

const uuid = (name: string, label: string): ReportFilterField =>
  text(name, label, 'UUID');

const DATE_RANGE: ReportFilterField[] = [date('date_from', 'From'), date('date_to', 'To')];

/** Today as YYYY-MM-DD in the browser's calendar — only an input default. */
export function todayIso(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

const money = (key: string, label: string, currencyKey?: string): DataTableColumn => ({
  key,
  label,
  format: 'money',
  ...(currencyKey ? { currencyKey } : {}),
});
const num = (key: string, label: string): DataTableColumn => ({ key, label, format: 'number' });
const day = (key: string, label: string): DataTableColumn => ({ key, label, format: 'date' });
const col = (key: string, label: string): DataTableColumn => ({ key, label });

// ---------------------------------------------------------------------------
// Sales (8) — backend/modules/reports/schemas/sales.py
// ---------------------------------------------------------------------------

// Revenue aggregates come one row per currency (FR-RPT-152), so each row
// formats its amounts in its own `currency_code`.
const CURRENCY = 'currency_code';
const SALES_SUMMARY_COLUMNS = [
  day('date', 'Date'),
  col(CURRENCY, 'Currency'),
  num('invoice_count', 'Invoices'),
  money('revenue', 'Revenue', CURRENCY),
  money('total_discount', 'Discounts', CURRENCY),
];
const SALES_BY_CUSTOMER_COLUMNS = [
  col('customer_name', 'Customer'),
  col(CURRENCY, 'Currency'),
  num('invoice_count', 'Invoices'),
  money('revenue', 'Revenue', CURRENCY),
];

const SALES: Record<string, ReportConfig> = {
  'sales.summary': {
    filters: [...DATE_RANGE, text('customer_id', 'Customer ID')],
    columns: SALES_SUMMARY_COLUMNS,
  },
  'sales.by_customer': { filters: DATE_RANGE, columns: SALES_BY_CUSTOMER_COLUMNS },
  'sales.by_product': {
    filters: [...DATE_RANGE, text('customer_id', 'Customer ID')],
    columns: [
      col('description', 'Product'),
      col(CURRENCY, 'Currency'),
      num('total_qty', 'Quantity'),
      num('line_count', 'Lines'),
      money('revenue', 'Revenue', CURRENCY),
    ],
  },
  'sales.top_customers': {
    filters: [...DATE_RANGE, { name: 'limit', label: 'Top N', type: 'number' }],
    columns: SALES_BY_CUSTOMER_COLUMNS,
    defaults: { limit: '10' },
  },
  'sales.trend': { filters: DATE_RANGE, columns: SALES_SUMMARY_COLUMNS },
  'sales.quotation_pipeline': {
    filters: [text('customer_id', 'Customer ID')],
    columns: [
      col('quotation_number', 'Quotation'),
      day('quotation_date', 'Date'),
      day('validity_date', 'Valid until'),
      col('status', 'Status'),
      money('total_amount', 'Amount'),
    ],
  },
  'sales.returns': {
    filters: [
      text('customer_id', 'Customer ID'),
      text('status', 'Status'),
      text('order_id', 'Order ID'),
      text('resolution_type', 'Resolution'),
    ],
    columns: [
      col('return_number', 'Return'),
      day('return_date', 'Date'),
      col('status', 'Status'),
      col('resolution_type', 'Resolution'),
      col('order_id', 'Order'),
    ],
  },
  'sales.kpis': { filters: DATE_RANGE },
};

// ---------------------------------------------------------------------------
// Purchase (7) — backend/modules/reports/schemas/purchase.py
// `branch_id` exists ONLY on open_commitments/pending_deliveries (FR-RPT-062).
// ---------------------------------------------------------------------------

const PURCHASE: Record<string, ReportConfig> = {
  'purchase.summary': {
    filters: [
      text('status', 'Status'),
      uuid('supplier_id', 'Supplier ID'),
      ...DATE_RANGE,
    ],
    columns: [
      col('po_number', 'PO'),
      col('status', 'Status'),
      money('subtotal', 'Subtotal', 'currency_code'),
      money('tax_amount', 'Tax', 'currency_code'),
      money('total', 'Total', 'currency_code'),
      day('expected_delivery_date', 'Expected'),
    ],
  },
  'purchase.by_supplier': {
    filters: DATE_RANGE,
    columns: [
      col('supplier_id', 'Supplier'),
      col(CURRENCY, 'Currency'),
      num('gr_count', 'Receipts'),
      money('total_subtotal', 'Subtotal', CURRENCY),
      money('total_charges', 'Charges', CURRENCY),
      money('total_discounts', 'Discounts', CURRENCY),
      money('total_spend', 'Total spend', CURRENCY),
    ],
  },
  'purchase.open_commitments': {
    filters: [uuid('supplier_id', 'Supplier ID'), uuid('branch_id', 'Branch ID')],
    columns: [
      col('po_number', 'PO'),
      col('product_description', 'Product'),
      num('quantity_ordered', 'Ordered'),
      num('quantity_received', 'Received'),
      num('open_quantity', 'Open qty'),
      money('open_value', 'Open value', 'currency_code'),
      day('expected_delivery_date', 'Expected'),
    ],
  },
  'purchase.supplier_performance': {
    filters: DATE_RANGE,
    columns: [
      col('supplier_id', 'Supplier'),
      num('total_grs', 'Receipts'),
      num('on_time_rate', 'On-time rate'),
      num('fill_rate', 'Fill rate'),
      num('rejection_rate', 'Rejection rate'),
      num('composite_rating', 'Rating'),
    ],
  },
  'purchase.pending_deliveries': {
    filters: [date('as_of', 'As of'), uuid('branch_id', 'Branch ID')],
    columns: [
      col('po_number', 'PO'),
      col('status', 'Status'),
      day('expected_delivery_date', 'Expected'),
      num('days_overdue', 'Days overdue'),
      money('total', 'Total', 'currency_code'),
    ],
  },
  'purchase.vendor_returns': {
    filters: [...DATE_RANGE, uuid('supplier_id', 'Supplier ID')],
    columns: [
      col('rma_number', 'RMA'),
      col('status', 'Status'),
      col('supplier_id', 'Supplier'),
      col('credit_note_pending', 'Credit note pending'),
      day('created_at', 'Created'),
    ],
  },
  'purchase.kpis': { filters: DATE_RANGE },
};

// ---------------------------------------------------------------------------
// Inventory (8) — backend/modules/reports/schemas/inventory.py
// ---------------------------------------------------------------------------

const INVENTORY: Record<string, ReportConfig> = {
  'inventory.summary': {
    filters: [uuid('warehouse_id', 'Warehouse ID'), uuid('category_id', 'Category ID')],
  },
  'inventory.valuation': {
    filters: [uuid('warehouse_id', 'Warehouse ID')],
    disclaimer:
      'Operational valuation at weighted average cost (WAC). This is an inventory-module figure, not a reconciled accounting balance.',
  },
  'inventory.stock_position': {
    filters: [
      uuid('product_id', 'Product ID'),
      uuid('warehouse_id', 'Warehouse ID'),
      date('date_from', 'From'),
      date('date_to', 'To'),
    ],
  },
  'inventory.dead_stock': {
    filters: [{ name: 'threshold_days', label: 'No movement for (days)', type: 'number' }],
    defaults: { threshold_days: '90' },
  },
  'inventory.movement_velocity': { filters: [date('date_from', 'From'), date('date_to', 'To')] },
  'inventory.stock_aging': { filters: [uuid('warehouse_id', 'Warehouse ID')] },
  'inventory.low_stock': {
    filters: [
      text('status', 'Status'),
      text('alert_type', 'Alert type'),
      uuid('product_id', 'Product ID'),
      uuid('warehouse_id', 'Warehouse ID'),
    ],
  },
  'inventory.kpis': {
    filters: [{ name: 'period_days', label: 'Period (days)', type: 'number' }],
    defaults: { period_days: '90' },
  },
};

// ---------------------------------------------------------------------------
// Accounting / Finance (9) — backend/modules/reports/schemas/accounting.py
// ---------------------------------------------------------------------------

const AGING_COLUMNS = [
  money('current', 'Current'),
  money('days_1_30', '1–30'),
  money('days_31_60', '31–60'),
  money('days_61_90', '61–90'),
  money('days_91_120', '91–120'),
  money('days_120_plus', '120+'),
  money('total', 'Total'),
];

const ACCOUNTING: Record<string, ReportConfig> = {
  'accounting.trial_balance': {
    filters: [
      { name: 'period_id', label: 'Fiscal period', type: 'select', required: true, lookup: 'fiscal_period' },
      { name: 'comparative_period_id', label: 'Compare with period', type: 'select', lookup: 'fiscal_period' },
    ],
  },
  'accounting.gl': {
    filters: [
      uuid('account_id', 'Account ID'),
      { ...uuid('cost_center_id', 'Cost center'), type: 'select', lookup: 'cost_center' },
      { ...uuid('fiscal_period_id', 'Fiscal period'), type: 'select', lookup: 'fiscal_period' },
      date('start_date', 'From'),
      date('end_date', 'To'),
    ],
    columns: [
      day('posting_date', 'Date'),
      col('journal_number', 'Journal'),
      col('account_code', 'Account'),
      col('description', 'Description'),
      money('debit_amount', 'Debit'),
      money('credit_amount', 'Credit'),
      col('reference', 'Reference'),
    ],
  },
  'accounting.profit_loss': {
    filters: [
      date('period_from', 'From', true),
      date('period_to', 'To', true),
      date('comparative_from', 'Compare from'),
      date('comparative_to', 'Compare to'),
      { ...uuid('cost_center_id', 'Cost center'), type: 'select', lookup: 'cost_center' },
      text('report_currency', 'Report currency', 'e.g. USD'),
    ],
  },
  'accounting.balance_sheet': {
    filters: [
      date('as_of_date', 'As of', true),
      date('comparative_date', 'Compare with'),
      text('report_currency', 'Report currency', 'e.g. USD'),
    ],
    defaults: { as_of_date: todayIso() },
  },
  'accounting.cash_flow': {
    filters: [date('period_from', 'From', true), date('period_to', 'To', true)],
  },
  'accounting.ar_aging': {
    filters: [date('as_of_date', 'As of', true)],
    columns: [col('customer_id', 'Customer'), ...AGING_COLUMNS],
    defaults: { as_of_date: todayIso() },
  },
  'accounting.ap_aging': {
    filters: [date('as_of_date', 'As of', true)],
    columns: [col('supplier_id', 'Supplier'), ...AGING_COLUMNS],
    defaults: { as_of_date: todayIso() },
  },
  'accounting.bank_cash_book': {
    filters: [
      {
        name: 'account_type',
        label: 'Book',
        type: 'select',
        required: true,
        options: [
          { value: 'bank', label: 'Bank book' },
          { value: 'cash', label: 'Cash book' },
        ],
      },
      { ...uuid('account_id', 'Account'), type: 'select', required: true, lookup: 'bank_or_cash_account' },
      date('from_date', 'From', true),
      date('to_date', 'To', true),
    ],
    columns: [
      day('transaction_date', 'Date'),
      col('transaction_type', 'Type'),
      col('reference', 'Reference'),
      col('description', 'Description'),
      money('amount', 'Amount'),
      col('is_reconciled', 'Reconciled'),
    ],
    defaults: { account_type: 'bank' },
  },
  'accounting.kpis': {
    filters: [date('as_of_date', 'As of', true)],
    defaults: { as_of_date: todayIso() },
  },
};

// ---------------------------------------------------------------------------
// CRM (4) — backend/modules/reports/schemas/crm.py (no export, no branch)
// ---------------------------------------------------------------------------

const CRM: Record<string, ReportConfig> = {
  'crm.pipeline': { filters: DATE_RANGE },
  'crm.leads': { filters: DATE_RANGE },
  'crm.activities': { filters: DATE_RANGE },
  'crm.dashboard': { filters: [] },
};

// ---------------------------------------------------------------------------
// Installments (7) — backend/modules/reports/schemas/installments.py
// No `branch_id` anywhere (T108 correction).
// ---------------------------------------------------------------------------

const INSTALLMENTS: Record<string, ReportConfig> = {
  'installments.register': {
    filters: [
      {
        name: 'status',
        label: 'Status',
        type: 'select',
        options: [
          'DRAFT',
          'PENDING_APPROVAL',
          'APPROVED',
          'ACTIVE',
          'DEFAULTED',
          'COMPLETED',
          'CANCELLED',
          'WRITTEN_OFF',
        ].map((s) => ({ value: s, label: s.replace(/_/g, ' ').toLowerCase() })),
      },
    ],
  },
  'installments.collections': { filters: [date('since', 'From'), date('until', 'To')] },
  'installments.due_overdue': { filters: [] },
  'installments.aging': { filters: [date('as_of_date', 'As of')] },
  'installments.settlement_writeoff': { filters: [] },
  'installments.plan_performance': { filters: [] },
  'installments.dashboard': { filters: [date('as_of_date', 'As of')] },
};

export const REPORT_CONFIGS: Readonly<Record<string, ReportConfig>> = {
  ...SALES,
  ...PURCHASE,
  ...INVENTORY,
  ...ACCOUNTING,
  ...CRM,
  ...INSTALLMENTS,
};

const NO_FILTERS: ReportConfig = { filters: [] };

/** Unknown keys (e.g. a future report) render with no filters and derived columns. */
export function configFor(reportKey: string): ReportConfig {
  return REPORT_CONFIGS[reportKey] ?? NO_FILTERS;
}

export function missingRequiredFilters(config: ReportConfig, values: FilterValues): string[] {
  return config.filters
    .filter((f) => f.required && !(values[f.name] ?? '').trim())
    .map((f) => f.label);
}
