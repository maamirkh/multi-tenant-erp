/**
 * Reports & Analytics API client (Epic 11, tasks.md T219).
 *
 * Thin wrapper over the shared `apiClient` singleton, exposing exactly the
 * ten calls the Reports UI needs — every one against an endpoint that
 * already exists on the backend (Phases 3–6):
 *
 *   getReportDiscovery   GET    /reports/discovery              (T130)
 *   getReport            GET    /reports/{report_key}           (T132)
 *   getDashboard         GET    /reports/dashboard              (T150)
 *   getCustomer360       GET    /reports/customer-360/{id}      (T165)
 *   listSavedViews       GET    /reports/saved-views            (T045)
 *   createSavedView      POST   /reports/saved-views            (T045)
 *   updateSavedView      PATCH  /reports/saved-views/{id}       (T045)
 *   deleteSavedView      DELETE /reports/saved-views/{id}       (T045)
 *   loadSavedView        GET    /reports/saved-views/{id}       (T140)
 *   exportReport         GET    /reports/{report_key}/export    (T198)
 *
 * Money and every other Decimal arrive as strings (the backend never
 * serializes a Decimal as a float — FR-RPT-150) and are kept as strings
 * here; the UI only formats them for display (`lib/format/money.ts`).
 *
 * Filters travel as OpenAPI `deepObject` query params
 * (`filters[date_from]=2026-01-01`), the exact contract the backend's
 * `_parse_deep_object_filters()` reads.
 */

import { ApiClientError, apiClient } from './client';
import type { ApiError, PaginatedData, PaginatedResponse, ResponseMeta } from './types';
import { tenantAuthStrategy } from '@/lib/auth/tenantAuthStrategy';

// ---------------------------------------------------------------------------
// Shared vocabulary (mirrors backend `schemas/common.py`)
// ---------------------------------------------------------------------------

/** The 11 standard period presets (FR-RPT-130). */
export const PERIOD_PRESETS = [
  'today',
  'yesterday',
  'this_week',
  'last_week',
  'this_month',
  'last_month',
  'this_quarter',
  'last_quarter',
  'this_year',
  'last_year',
  'custom',
] as const;
export type PeriodPreset = (typeof PERIOD_PRESETS)[number];

/** The 5 comparison options (`ComparisonType`). */
export const COMPARISON_TYPES = [
  'previous_period',
  'previous_month',
  'previous_quarter',
  'previous_year',
  'same_period_last_year',
] as const;
export type ComparisonType = (typeof COMPARISON_TYPES)[number];

export type Comparability = 'full' | 'not_comparable' | 'partial_current_period';

export interface ComparisonResult {
  /** Decimal string — never a float. */
  absolute_change: string;
  percentage_change: string | null;
  comparability: Comparability;
}

export interface PeriodResolution {
  /** ISO-8601 UTC instant, inclusive. */
  start: string;
  /** ISO-8601 UTC instant, exclusive. */
  end: string;
  /** IANA zone the boundaries were computed against. */
  timezone: string;
  is_partial_current_period: boolean;
}

export interface DrillDownRef {
  label: string;
  target_route: string;
  required_permission: string;
}

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export interface ReportEnvelopeMeta {
  report_key: string;
  applied_filters: Record<string, JsonValue>;
  period: PeriodResolution;
  freshness: 'transactional_live' | 'cached_n_minutes';
  drill_down: DrillDownRef[];
  comparison: ComparisonResult | null;
  read_only_servicing_continuity: boolean;
}

export type ExportFormat = 'csv' | 'xlsx' | 'pdf';

/** Filter values as sent on the wire — every one becomes a query string. */
export type ReportFilters = Record<string, string | number | boolean | null | undefined>;

// ---------------------------------------------------------------------------
// Discovery (T130)
// ---------------------------------------------------------------------------

export interface ReportDiscoveryItem {
  key: string;
  name: string;
  domain: string;
  description: string;
  exportable: boolean;
  export_formats: ExportFormat[];
  branch_filterable: boolean;
  drill_down_targets: string[];
}

export interface ReportDiscoveryResponse {
  reports: ReportDiscoveryItem[];
}

// ---------------------------------------------------------------------------
// Report execution (T132) — three envelope shapes, one per pagination style
// ---------------------------------------------------------------------------

export type ReportRow = Record<string, JsonValue>;

export interface CursorPage<T> {
  items: T[];
  has_more: boolean;
  next_cursor: string | null;
}

/** `data` is `PaginatedData` (offset reports), `CursorPage` (`accounting.gl`
 * only) or the report's fixed aggregate object (statements/KPI sets). */
export type ReportData = PaginatedData<ReportRow> | CursorPage<ReportRow> | Record<string, JsonValue>;

export interface ReportResponse<T extends ReportData = ReportData> {
  data: T;
  report_meta: ReportEnvelopeMeta;
  message: string;
  meta: ResponseMeta;
}

export function isPaginatedData(data: ReportData): data is PaginatedData<ReportRow> {
  return Array.isArray((data as PaginatedData<ReportRow>).items) && 'total' in data;
}

export function isCursorPage(data: ReportData): data is CursorPage<ReportRow> {
  return Array.isArray((data as CursorPage<ReportRow>).items) && 'has_more' in data;
}

export interface GetReportParams {
  filters?: ReportFilters | undefined;
  page?: number | undefined;
  page_size?: number | undefined;
  sort?: string | null | undefined;
  compare?: ComparisonType | null | undefined;
}

// ---------------------------------------------------------------------------
// Executive Dashboard (T150) — 10 widgets, 3 states each
// ---------------------------------------------------------------------------

export type WidgetState = 'present' | 'omitted' | 'unavailable';

/**
 * One currency's own figure (FR-RPT-152). A multi-currency aggregate is a
 * list of these — never one sum; its single value field is then `null`.
 */
export interface CurrencyAmount {
  currency_code: string | null;
  amount: string;
  comparison?: ComparisonResult | null;
}

interface WidgetBase {
  state: WidgetState;
  comparison: ComparisonResult | null;
  drill_down: DrillDownRef | null;
}

export interface ValueWidget extends WidgetBase {
  value: string | null;
  /** Present on Sales/Purchase/Inventory widgets; Accounting ones have none. */
  by_currency?: CurrencyAmount[];
}

export interface ArWidget extends WidgetBase {
  balance: string | null;
  overdue: string | null;
}

export interface OperationalInventoryValueWidget extends ValueWidget {
  valuation_basis: 'operational_wac' | null;
}

export interface CrmPipelineWidget extends WidgetBase {
  pipeline_value: string | null;
  pipeline_value_by_currency?: CurrencyAmount[];
  win_rate: string | null;
}

export interface InstallmentExposureWidget extends WidgetBase {
  outstanding_principal: string | null;
  overdue: string | null;
  outstanding_principal_by_currency?: CurrencyAmount[];
  overdue_by_currency?: CurrencyAmount[];
  read_only_servicing_continuity: boolean;
}

export interface ExecutiveDashboardResponse {
  period: PeriodResolution;
  net_sales: ValueWidget;
  gross_sales: ValueWidget;
  purchase_spend: ValueWidget;
  ar: ArWidget;
  ap: ValueWidget;
  cash_position: ValueWidget;
  operational_inventory_value: OperationalInventoryValueWidget;
  crm_pipeline: CrmPipelineWidget;
  installment_exposure: InstallmentExposureWidget;
  gross_profit_margin: ValueWidget;
}

export interface GetDashboardParams {
  period?: PeriodPreset | undefined;
  custom_start?: string | null | undefined;
  custom_end?: string | null | undefined;
  compare?: ComparisonType | null | undefined;
}

// ---------------------------------------------------------------------------
// Customer 360 (T165) — four independently-authorized sections
// ---------------------------------------------------------------------------

export interface OmittedSection {
  state: 'omitted';
  reason: 'not_entitled' | 'not_permitted';
}

export interface UnavailableSection {
  state: 'unavailable';
  reason: 'not_configured' | 'no_data_source';
}

export interface PresentSalesSection {
  state: 'present';
  total_revenue: string | null;
  total_revenue_by_currency?: CurrencyAmount[];
  invoice_count: number;
}

export interface PresentAccountingArSection {
  state: 'present';
  balance: string;
}

export interface PresentCrmSection {
  state: 'present';
  open_opportunity_count: number;
  open_opportunity_value: string | null;
  open_opportunity_value_by_currency?: CurrencyAmount[];
}

export interface PresentInstallmentsSection {
  state: 'present';
  outstanding_principal: string | null;
  outstanding_principal_by_currency?: CurrencyAmount[];
  contract_count: number;
  read_only_servicing_continuity: boolean;
}

type Section<P> = P | OmittedSection | UnavailableSection;

export interface Customer360Response {
  customer_id: string;
  customer_name: string;
  sales: Section<PresentSalesSection>;
  accounting_ar: Section<PresentAccountingArSection>;
  crm: Section<PresentCrmSection>;
  installments: Section<PresentInstallmentsSection>;
}

// ---------------------------------------------------------------------------
// Saved views (T045/T140)
// ---------------------------------------------------------------------------

export interface SavedReportView {
  id: string;
  report_key: string;
  name: string;
  schema_version: number;
  filter_config: Record<string, JsonValue>;
  grouping: string[] | null;
  sorting: string | null;
  visible_columns: string[] | null;
  date_preset: string | null;
  created_at: string;
  updated_at: string;
}

export interface SavedReportViewCreate {
  report_key: string;
  name: string;
  filter_config: Record<string, JsonValue>;
  grouping?: string[] | null;
  sorting?: string | null;
  visible_columns?: string[] | null;
  date_preset?: string | null;
}

export type SavedReportViewUpdate = Partial<SavedReportViewCreate>;

// ---------------------------------------------------------------------------
// URL helpers
// ---------------------------------------------------------------------------

function reportsBase(companyId: string): string {
  return `/api/v1/companies/${companyId}/reports`;
}

/** Encode `filters` as deepObject params; empty values are omitted, never
 * sent as an empty string the backend would then have to reject. */
export function appendFilterParams(params: URLSearchParams, filters?: ReportFilters): void {
  if (!filters) return;
  for (const [field, value] of Object.entries(filters)) {
    if (value === undefined || value === null || value === '') continue;
    params.append(`filters[${field}]`, String(value));
  }
}

function withQuery(path: string, params: URLSearchParams): string {
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

// ---------------------------------------------------------------------------
// Calls
// ---------------------------------------------------------------------------

export async function getReportDiscovery(companyId: string) {
  return apiClient.get<ReportDiscoveryResponse>(`${reportsBase(companyId)}/discovery`);
}

export async function getReport(
  companyId: string,
  reportKey: string,
  { filters, page, page_size, sort, compare }: GetReportParams = {}
): Promise<ReportResponse> {
  const params = new URLSearchParams();
  if (page !== undefined) params.set('page', String(page));
  if (page_size !== undefined) params.set('page_size', String(page_size));
  if (sort) params.set('sort', sort);
  if (compare) params.set('compare', compare);
  appendFilterParams(params, filters);
  const response = await apiClient.get<ReportData>(
    withQuery(`${reportsBase(companyId)}/${encodeURIComponent(reportKey)}`, params)
  );
  // The report envelope adds `report_meta` beside the standard fields.
  return response as unknown as ReportResponse;
}

export async function getDashboard(companyId: string, params: GetDashboardParams = {}) {
  const query = new URLSearchParams();
  if (params.period) query.set('period', params.period);
  if (params.custom_start) query.set('custom_start', params.custom_start);
  if (params.custom_end) query.set('custom_end', params.custom_end);
  if (params.compare) query.set('compare', params.compare);
  return apiClient.get<ExecutiveDashboardResponse>(
    withQuery(`${reportsBase(companyId)}/dashboard`, query)
  );
}

export async function getCustomer360(companyId: string, customerId: string) {
  return apiClient.get<Customer360Response>(
    `${reportsBase(companyId)}/customer-360/${encodeURIComponent(customerId)}`
  );
}

export async function listSavedViews(
  companyId: string,
  page = 1,
  pageSize = 20
): Promise<PaginatedResponse<SavedReportView>> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  const response = await apiClient.get<PaginatedData<SavedReportView>>(
    withQuery(`${reportsBase(companyId)}/saved-views`, params)
  );
  return response;
}

export async function createSavedView(companyId: string, body: SavedReportViewCreate) {
  return apiClient.post<SavedReportView>(`${reportsBase(companyId)}/saved-views`, body);
}

export async function updateSavedView(
  companyId: string,
  viewId: string,
  body: SavedReportViewUpdate
) {
  return apiClient.patch<SavedReportView>(
    `${reportsBase(companyId)}/saved-views/${encodeURIComponent(viewId)}`,
    body
  );
}

export async function deleteSavedView(companyId: string, viewId: string) {
  return apiClient.delete<null>(
    `${reportsBase(companyId)}/saved-views/${encodeURIComponent(viewId)}`
  );
}

/** Loads a view **re-validated against the caller's current permissions and
 * entitlements** (T140) — never the state at save time. */
export async function loadSavedView(companyId: string, viewId: string) {
  return apiClient.get<SavedReportView>(
    `${reportsBase(companyId)}/saved-views/${encodeURIComponent(viewId)}`
  );
}

// ---------------------------------------------------------------------------
// Export (T198) — a binary download, so it cannot use apiClient's JSON path
// ---------------------------------------------------------------------------

export interface ExportedFile {
  blob: Blob;
  filename: string;
}

const API_BASE_URL = process.env['NEXT_PUBLIC_API_URL'] ?? 'http://localhost:8000';

/** Pulls `filename="…"` out of `Content-Disposition`; falls back to a name
 * built from the report key (the backend always sends one). */
export function filenameFromDisposition(
  disposition: string | null,
  fallback: string
): string {
  const match = disposition?.match(/filename="([^"]+)"/);
  return match?.[1] ?? fallback;
}

/**
 * Downloads a report export in the exact filter scope of the online view.
 * The backend only returns file bytes after the export's audit record is
 * durably committed; any failure (row limit exceeded, permission denied,
 * audit failure) arrives as the standard JSON error envelope and is thrown
 * as an `ApiClientError`, so callers render it like every other API error.
 */
export async function exportReport(
  companyId: string,
  reportKey: string,
  format: ExportFormat,
  { filters, sort }: { filters?: ReportFilters | undefined; sort?: string | null | undefined } = {}
): Promise<ExportedFile> {
  const params = new URLSearchParams({ format });
  if (sort) params.set('sort', sort);
  appendFilterParams(params, filters);

  const headers: Record<string, string> = {};
  const token = tenantAuthStrategy.getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await fetch(
    `${API_BASE_URL}${reportsBase(companyId)}/${encodeURIComponent(reportKey)}/export?${params.toString()}`,
    { headers }
  );
  if (!response.ok) {
    let error: ApiError;
    try {
      error = (await response.json()) as ApiError;
    } catch {
      error = {
        error: {
          code: 'NETWORK_ERROR',
          message: `HTTP ${response.status}: ${response.statusText}`,
          details: {},
        },
      };
    }
    throw new ApiClientError(response.status, error);
  }
  return {
    blob: await response.blob(),
    filename: filenameFromDisposition(
      response.headers.get('Content-Disposition'),
      `${reportKey.replace(/\./g, '-')}.${format}`
    ),
  };
}

/** Hands an exported file to the browser as a download. */
export function saveExportedFile({ blob, filename }: ExportedFile): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
