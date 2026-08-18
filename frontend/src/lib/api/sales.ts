/**
 * Sales module API client.
 *
 * Provides typed functions for all sales module endpoints.
 * All requests are scoped to a company_id (tenant isolation).
 *
 * Spec ref: specs/007-sales-management/spec.md §23 Functional Requirements
 */

import { getAccessToken } from "@/lib/auth/tokenStorage";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CustomerCategoryRead {
  id: string;
  company_id: string;
  code: string;
  name: string;
  description: string | null;
  default_payment_term_id: string | null;
  default_credit_limit: string;
  is_active: boolean;
}

export interface CustomerCategoryCreate {
  code: string;
  name: string;
  description?: string | null;
  default_payment_term_id?: string | null;
  default_credit_limit?: number;
}

export interface CustomerGroupRead {
  id: string;
  company_id: string;
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
}

export interface CustomerGroupCreate {
  code: string;
  name: string;
  description?: string | null;
}

export interface SalesPaymentTermRead {
  id: string;
  company_id: string;
  code: string;
  name: string;
  due_days: number;
  discount_days: number | null;
  discount_percent: string | null;
  description: string | null;
  is_active: boolean;
}

export interface SalesPaymentTermCreate {
  code: string;
  name: string;
  due_days: number;
  discount_days?: number | null;
  discount_percent?: string | null;
  description?: string | null;
}

export interface SalesReasonCodeRead {
  id: string;
  company_id: string;
  code: string;
  name: string;
  reason_type: string;
  is_active: boolean;
}

export interface SalesReasonCodeCreate {
  code: string;
  name: string;
  reason_type: "RETURN" | "CANCELLATION" | "REJECTION" | "GENERAL";
}

export interface SalesConfigurationRead {
  id: string;
  company_id: string;
  default_quotation_validity_days: number;
  quotation_expiry_warning_days: number;
  auto_approve_threshold: string | null;
  minimum_margin_percentage: string | null;
  credit_warning_threshold: string;
  reservation_expiry_hours: number;
  require_quotation_before_order: boolean;
  tax_inclusive_pricing: boolean;
}

export interface SalesFeatureFlagRead {
  flag_key: string;
  label: string;
  description: string;
  is_enabled: boolean;
  is_overridden: boolean;
  default_enabled: boolean;
}

export interface StandardResponse<T> {
  data: T;
  message: string;
  meta: { request_id: string; timestamp: string };
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function authHeaders(token?: string): HeadersInit {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  // Callers historically passed a token retrieved from
  // localStorage.getItem("access_token"), a key that is never populated
  // (the real access token is kept in-memory only — see
  // lib/auth/tokenStorage.ts). Fall back to the real token whenever the
  // caller didn't supply a genuinely valid one.
  const effectiveToken = token || getAccessToken();
  if (effectiveToken) headers["Authorization"] = `Bearer ${effectiveToken}`;
  return headers;
}

async function apiCall<T>(
  url: string,
  options: RequestInit = {},
  token?: string
): Promise<StandardResponse<T>> {
  const res = await fetch(url, {
    ...options,
    headers: { ...authHeaders(token), ...(options.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json();
}

function salesBase(companyId: string): string {
  return `${API_BASE}/api/v1/companies/${companyId}/sales`;
}

// ---------------------------------------------------------------------------
// Customer Categories
// ---------------------------------------------------------------------------

export function getCustomerCategories(
  companyId: string,
  token?: string
): Promise<StandardResponse<CustomerCategoryRead[]>> {
  return apiCall(`${salesBase(companyId)}/customer-categories`, {}, token);
}

export function createCustomerCategory(
  companyId: string,
  data: CustomerCategoryCreate,
  token?: string
): Promise<StandardResponse<CustomerCategoryRead>> {
  return apiCall(`${salesBase(companyId)}/customer-categories`, {
    method: "POST",
    body: JSON.stringify(data),
  }, token);
}

// ---------------------------------------------------------------------------
// Customer Groups
// ---------------------------------------------------------------------------

export function getCustomerGroups(
  companyId: string,
  token?: string
): Promise<StandardResponse<CustomerGroupRead[]>> {
  return apiCall(`${salesBase(companyId)}/customer-groups`, {}, token);
}

export function createCustomerGroup(
  companyId: string,
  data: CustomerGroupCreate,
  token?: string
): Promise<StandardResponse<CustomerGroupRead>> {
  return apiCall(`${salesBase(companyId)}/customer-groups`, {
    method: "POST",
    body: JSON.stringify(data),
  }, token);
}

// ---------------------------------------------------------------------------
// Payment Terms
// ---------------------------------------------------------------------------

export function getSalesPaymentTerms(
  companyId: string,
  token?: string
): Promise<StandardResponse<SalesPaymentTermRead[]>> {
  return apiCall(`${salesBase(companyId)}/payment-terms`, {}, token);
}

export function createSalesPaymentTerm(
  companyId: string,
  data: SalesPaymentTermCreate,
  token?: string
): Promise<StandardResponse<SalesPaymentTermRead>> {
  return apiCall(`${salesBase(companyId)}/payment-terms`, {
    method: "POST",
    body: JSON.stringify(data),
  }, token);
}

// ---------------------------------------------------------------------------
// Reason Codes
// ---------------------------------------------------------------------------

export function getSalesReasonCodes(
  companyId: string,
  token?: string
): Promise<StandardResponse<SalesReasonCodeRead[]>> {
  return apiCall(`${salesBase(companyId)}/reason-codes`, {}, token);
}

export function createSalesReasonCode(
  companyId: string,
  data: SalesReasonCodeCreate,
  token?: string
): Promise<StandardResponse<SalesReasonCodeRead>> {
  return apiCall(`${salesBase(companyId)}/reason-codes`, {
    method: "POST",
    body: JSON.stringify(data),
  }, token);
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

export function getSalesConfiguration(
  companyId: string,
  token?: string
): Promise<StandardResponse<SalesConfigurationRead>> {
  return apiCall(`${salesBase(companyId)}/configuration`, {}, token);
}

export function updateSalesConfiguration(
  companyId: string,
  data: Partial<SalesConfigurationRead>,
  token?: string
): Promise<StandardResponse<SalesConfigurationRead>> {
  return apiCall(`${salesBase(companyId)}/configuration`, {
    method: "PUT",
    body: JSON.stringify(data),
  }, token);
}

// ---------------------------------------------------------------------------
// Feature Flags
// ---------------------------------------------------------------------------

export function getSalesFeatureFlags(
  companyId: string,
  token?: string
): Promise<StandardResponse<SalesFeatureFlagRead[]>> {
  return apiCall(`${salesBase(companyId)}/feature-flags`, {}, token);
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export function getSalesHealth(
  companyId: string,
  token?: string
): Promise<StandardResponse<{ status: string; module: string; version: string }>> {
  return apiCall(`${salesBase(companyId)}/health`, {}, token);
}

// ---------------------------------------------------------------------------
// Phase 1 – Customer Master types
// ---------------------------------------------------------------------------

export interface CustomerListItem {
  id: string;
  customer_code: string;
  legal_name: string;
  customer_type: string;
  status: string;
  credit_status: string;
  currency_code: string;
  created_at: string;
}

export interface CustomerSearchResult {
  items: CustomerListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface Customer {
  id: string;
  customer_code: string;
  legal_name: string;
  trading_name?: string | null;
  customer_type: string;
  category_id?: string | null;
  group_id?: string | null;
  status: string;
  credit_status: string;
  credit_limit: number;
  credit_used: number;
  currency_code: string;
  payment_term?: string | null;
  tax_number?: string | null;
  website?: string | null;
  notes?: string | null;
  rating?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CustomerContact {
  id: string;
  contact_name: string;
  email?: string | null;
  phone?: string | null;
  mobile?: string | null;
  position?: string | null;
  is_primary: boolean;
}

export interface CustomerAddress {
  id: string;
  address_type: string;
  address_line_1: string;
  address_line_2?: string | null;
  city: string;
  state_province?: string | null;
  postal_code?: string | null;
  country_code: string;
  is_default_billing: boolean;
  is_default_shipping: boolean;
}

export interface CustomerNote {
  id: string;
  content: string;
  author_name: string;
  created_at: string;
}

export interface CustomerImportResult {
  total_rows: number;
  imported: number;
  skipped: number;
  errors: Array<{ row: number; message: string }>;
}

// ---------------------------------------------------------------------------
// Phase 1 – Customer CRUD
// ---------------------------------------------------------------------------

export function listCustomers(
  companyId: string,
  params?: {
    q?: string;
    status?: string;
    customer_type?: string;
    category_id?: string;
    group_id?: string;
    page?: number;
    page_size?: number;
  },
  token?: string
): Promise<StandardResponse<CustomerSearchResult>> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set("q", params.q);
  if (params?.status) qs.set("status", params.status);
  if (params?.customer_type) qs.set("customer_type", params.customer_type);
  if (params?.category_id) qs.set("category_id", params.category_id);
  if (params?.group_id) qs.set("group_id", params.group_id);
  if (params?.page) qs.set("page", String(params.page));
  if (params?.page_size) qs.set("page_size", String(params.page_size));
  const query = qs.toString() ? `?${qs}` : "";
  return apiCall(`${salesBase(companyId)}/customers${query}`, {}, token);
}

export function getCustomer(
  companyId: string,
  customerId: string,
  token?: string
): Promise<StandardResponse<Customer>> {
  return apiCall(
    `${salesBase(companyId)}/customers/${customerId}`,
    {},
    token
  );
}

export function createCustomer(
  companyId: string,
  data: Record<string, unknown>,
  token?: string
): Promise<StandardResponse<Customer>> {
  return apiCall(
    `${salesBase(companyId)}/customers`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function updateCustomer(
  companyId: string,
  customerId: string,
  data: Record<string, unknown>,
  token?: string
): Promise<StandardResponse<Customer>> {
  return apiCall(
    `${salesBase(companyId)}/customers/${customerId}`,
    { method: "PUT", body: JSON.stringify(data) },
    token
  );
}

export function transitionCustomer(
  companyId: string,
  customerId: string,
  action: string,
  reason?: string,
  token?: string
): Promise<StandardResponse<Customer>> {
  return apiCall(
    `${salesBase(companyId)}/customers/${customerId}/transitions`,
    { method: "POST", body: JSON.stringify({ action, reason }) },
    token
  );
}

export function updateCustomerCredit(
  companyId: string,
  customerId: string,
  data: { credit_limit?: number; credit_used?: number },
  token?: string
): Promise<StandardResponse<Customer>> {
  return apiCall(
    `${salesBase(companyId)}/customers/${customerId}/credit`,
    { method: "PUT", body: JSON.stringify(data) },
    token
  );
}

// ---------------------------------------------------------------------------
// Phase 1 – Contacts, Addresses, Notes
// ---------------------------------------------------------------------------

export function listCustomerContacts(
  companyId: string,
  customerId: string,
  token?: string
): Promise<StandardResponse<CustomerContact[]>> {
  return apiCall(
    `${salesBase(companyId)}/customers/${customerId}/contacts`,
    {},
    token
  );
}

export function addCustomerContact(
  companyId: string,
  customerId: string,
  data: Record<string, unknown>,
  token?: string
): Promise<StandardResponse<CustomerContact>> {
  return apiCall(
    `${salesBase(companyId)}/customers/${customerId}/contacts`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function listCustomerAddresses(
  companyId: string,
  customerId: string,
  token?: string
): Promise<StandardResponse<CustomerAddress[]>> {
  return apiCall(
    `${salesBase(companyId)}/customers/${customerId}/addresses`,
    {},
    token
  );
}

export function addCustomerAddress(
  companyId: string,
  customerId: string,
  data: Record<string, unknown>,
  token?: string
): Promise<StandardResponse<CustomerAddress>> {
  return apiCall(
    `${salesBase(companyId)}/customers/${customerId}/addresses`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function listCustomerNotes(
  companyId: string,
  customerId: string,
  token?: string
): Promise<StandardResponse<CustomerNote[]>> {
  return apiCall(
    `${salesBase(companyId)}/customers/${customerId}/notes`,
    {},
    token
  );
}

export function addCustomerNote(
  companyId: string,
  customerId: string,
  content: string,
  token?: string
): Promise<StandardResponse<CustomerNote>> {
  return apiCall(
    `${salesBase(companyId)}/customers/${customerId}/notes`,
    { method: "POST", body: JSON.stringify({ content }) },
    token
  );
}

// ---------------------------------------------------------------------------
// Phase 1 – Import / Export
// ---------------------------------------------------------------------------

export async function importCustomers(
  companyId: string,
  file: File,
  token?: string
): Promise<StandardResponse<CustomerImportResult>> {
  const formData = new FormData();
  formData.append("file", file);
  const headers = authHeaders(token);
  // Remove Content-Type so browser sets multipart boundary automatically
  const { "Content-Type": _ct, ...rest } = headers as Record<string, string>;
  const res = await fetch(`${salesBase(companyId)}/customers/import`, {
    method: "POST",
    headers: rest,
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw Object.assign(new Error(err.detail ?? "Import failed"), {
      status: res.status,
    });
  }
  return res.json();
}

export function exportCustomersUrl(companyId: string, status?: string): string {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  return `/api/v1/companies/${companyId}/sales/customers/export${qs}`;
}

// ---------------------------------------------------------------------------
// Phase 2 – Pricing Engine types
// ---------------------------------------------------------------------------

export interface PriceListRead {
  id: string;
  company_id: string;
  name: string;
  description: string | null;
  currency_code: string;
  effective_from: string;
  effective_to: string | null;
  is_default: boolean;
  is_active: boolean;
  priority: number;
  customer_group_id: string | null;
  customer_category_id: string | null;
  version: number;
  is_deleted: boolean;
  entries: PriceEntryRead[];
}

export interface PriceListCreate {
  name: string;
  currency_code?: string;
  effective_from: string;
  effective_to?: string | null;
  description?: string | null;
  is_default?: boolean;
  is_active?: boolean;
  priority?: number;
  customer_group_id?: string | null;
  customer_category_id?: string | null;
}

export interface PriceListUpdate {
  name?: string;
  description?: string | null;
  currency_code?: string;
  effective_from?: string;
  effective_to?: string | null;
  is_default?: boolean;
  is_active?: boolean;
  priority?: number;
  customer_group_id?: string | null;
  customer_category_id?: string | null;
}

export interface PriceEntryRead {
  id: string;
  company_id: string;
  price_list_id: string;
  product_id: string;
  unit_price: string;
  minimum_quantity: string;
  unit_of_measure: string;
  is_deleted: boolean;
}

export interface PriceEntryCreate {
  product_id: string;
  unit_price: string;
  minimum_quantity?: string;
  unit_of_measure?: string;
}

export interface CustomerSpecificPriceRead {
  id: string;
  company_id: string;
  customer_id: string;
  product_id: string;
  unit_price: string;
  effective_from: string;
  effective_to: string | null;
  minimum_quantity: string;
  is_deleted: boolean;
}

export interface CustomerSpecificPriceCreate {
  customer_id: string;
  product_id: string;
  unit_price: string;
  effective_from: string;
  effective_to?: string | null;
  minimum_quantity?: string;
}

export interface DiscountRuleRead {
  id: string;
  company_id: string;
  name: string;
  rule_type: string;
  applicability: string;
  applicability_id: string | null;
  product_scope: string;
  product_scope_id: string | null;
  minimum_quantity: string | null;
  minimum_order_value: string | null;
  discount_value: string;
  effective_from: string;
  effective_to: string | null;
  is_active: boolean;
  priority: number;
  is_stackable: boolean;
  is_deleted: boolean;
}

export interface DiscountRuleCreate {
  name: string;
  rule_type: string;
  discount_value: string;
  effective_from: string;
  applicability?: string;
  applicability_id?: string | null;
  product_scope?: string;
  product_scope_id?: string | null;
  minimum_quantity?: string | null;
  minimum_order_value?: string | null;
  effective_to?: string | null;
  is_active?: boolean;
  priority?: number;
  is_stackable?: boolean;
}

export interface PriceResolutionResponse {
  unit_price: string;
  price_source: string;
  resolution_level: number;
  price_list_id: string | null;
  price_list_name: string | null;
  price_entry_id: string | null;
  customer_specific_price_id: string | null;
}

export interface MarginCheckRequest {
  unit_price: string;
  cost_price: string;
  min_margin_pct?: string | null;
  block_on_low_margin?: boolean;
}

export interface MarginCheckResponse {
  margin_percentage: string;
  passes: boolean;
  action: string;
  threshold_pct: string;
}

// ---------------------------------------------------------------------------
// Phase 2 – Price Lists
// ---------------------------------------------------------------------------

export function listPriceLists(
  companyId: string,
  params?: { is_active?: boolean; skip?: number; limit?: number },
  token?: string
): Promise<StandardResponse<PriceListRead[]>> {
  const qs = new URLSearchParams();
  if (params?.is_active !== undefined) qs.set("is_active", String(params.is_active));
  if (params?.skip !== undefined) qs.set("skip", String(params.skip));
  if (params?.limit !== undefined) qs.set("limit", String(params.limit));
  const query = qs.toString() ? `?${qs}` : "";
  return apiCall(`${salesBase(companyId)}/price-lists${query}`, {}, token);
}

export function getPriceList(
  companyId: string,
  priceListId: string,
  token?: string
): Promise<StandardResponse<PriceListRead>> {
  return apiCall(`${salesBase(companyId)}/price-lists/${priceListId}`, {}, token);
}

export function createPriceList(
  companyId: string,
  data: PriceListCreate,
  token?: string
): Promise<StandardResponse<PriceListRead>> {
  return apiCall(
    `${salesBase(companyId)}/price-lists`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function updatePriceList(
  companyId: string,
  priceListId: string,
  data: PriceListUpdate,
  token?: string
): Promise<StandardResponse<PriceListRead>> {
  return apiCall(
    `${salesBase(companyId)}/price-lists/${priceListId}`,
    { method: "PUT", body: JSON.stringify(data) },
    token
  );
}

export function deletePriceList(
  companyId: string,
  priceListId: string,
  token?: string
): Promise<void> {
  return apiCall(
    `${salesBase(companyId)}/price-lists/${priceListId}`,
    { method: "DELETE" },
    token
  ).then(() => undefined);
}

export function addPriceEntry(
  companyId: string,
  priceListId: string,
  data: PriceEntryCreate,
  token?: string
): Promise<StandardResponse<PriceEntryRead>> {
  return apiCall(
    `${salesBase(companyId)}/price-lists/${priceListId}/entries`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function deletePriceEntry(
  companyId: string,
  priceListId: string,
  entryId: string,
  token?: string
): Promise<void> {
  return apiCall(
    `${salesBase(companyId)}/price-lists/${priceListId}/entries/${entryId}`,
    { method: "DELETE" },
    token
  ).then(() => undefined);
}

// ---------------------------------------------------------------------------
// Phase 2 – Customer-Specific Prices
// ---------------------------------------------------------------------------

export function listCustomerSpecificPrices(
  companyId: string,
  params?: { customer_id?: string; skip?: number; limit?: number },
  token?: string
): Promise<StandardResponse<CustomerSpecificPriceRead[]>> {
  const qs = new URLSearchParams();
  if (params?.customer_id) qs.set("customer_id", params.customer_id);
  if (params?.skip !== undefined) qs.set("skip", String(params.skip));
  if (params?.limit !== undefined) qs.set("limit", String(params.limit));
  const query = qs.toString() ? `?${qs}` : "";
  return apiCall(`${salesBase(companyId)}/customer-prices${query}`, {}, token);
}

export function createCustomerSpecificPrice(
  companyId: string,
  data: CustomerSpecificPriceCreate,
  token?: string
): Promise<StandardResponse<CustomerSpecificPriceRead>> {
  return apiCall(
    `${salesBase(companyId)}/customer-prices`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function deleteCustomerSpecificPrice(
  companyId: string,
  priceId: string,
  token?: string
): Promise<void> {
  return apiCall(
    `${salesBase(companyId)}/customer-prices/${priceId}`,
    { method: "DELETE" },
    token
  ).then(() => undefined);
}

// ---------------------------------------------------------------------------
// Phase 2 – Discount Rules
// ---------------------------------------------------------------------------

export function listDiscountRules(
  companyId: string,
  params?: { skip?: number; limit?: number },
  token?: string
): Promise<StandardResponse<DiscountRuleRead[]>> {
  const qs = new URLSearchParams();
  if (params?.skip !== undefined) qs.set("skip", String(params.skip));
  if (params?.limit !== undefined) qs.set("limit", String(params.limit));
  const query = qs.toString() ? `?${qs}` : "";
  return apiCall(`${salesBase(companyId)}/discount-rules${query}`, {}, token);
}

export function createDiscountRule(
  companyId: string,
  data: DiscountRuleCreate,
  token?: string
): Promise<StandardResponse<DiscountRuleRead>> {
  return apiCall(
    `${salesBase(companyId)}/discount-rules`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function deleteDiscountRule(
  companyId: string,
  ruleId: string,
  token?: string
): Promise<void> {
  return apiCall(
    `${salesBase(companyId)}/discount-rules/${ruleId}`,
    { method: "DELETE" },
    token
  ).then(() => undefined);
}

// ---------------------------------------------------------------------------
// Phase 2 – Price Resolution & Margin Guard
// ---------------------------------------------------------------------------

export function resolvePrice(
  companyId: string,
  data: {
    product_id: string;
    quantity: string;
    customer_id?: string;
    group_id?: string;
    category_id?: string;
    manual_price?: string;
    as_of_date?: string;
  },
  token?: string
): Promise<StandardResponse<PriceResolutionResponse>> {
  return apiCall(
    `${salesBase(companyId)}/pricing/resolve`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function checkMargin(
  companyId: string,
  data: MarginCheckRequest,
  token?: string
): Promise<StandardResponse<MarginCheckResponse>> {
  return apiCall(
    `${salesBase(companyId)}/pricing/check-margin`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

// ---------------------------------------------------------------------------
// Phase 3 – Sales Quotations: Types
// ---------------------------------------------------------------------------

export interface QuotationLineRead {
  id: string;
  company_id: string;
  quotation_id: string;
  line_number: number;
  product_id: string | null;
  description: string;
  quantity: string;
  unit_of_measure: string;
  unit_price: string;
  discount_percentage: string | null;
  discount_amount: string | null;
  tax_category: string | null;
  extended_amount: string;
  notes: string | null;
}

export interface QuotationLineCreate {
  product_id?: string | null;
  description: string;
  quantity: number;
  unit_of_measure?: string;
  unit_price: number;
  discount_percentage?: number | null;
  tax_category?: string | null;
  notes?: string | null;
}

export interface SalesQuotationCreate {
  customer_id: string;
  quotation_date: string;
  validity_date: string;
  currency_code?: string;
  payment_term_id?: string | null;
  shipping_address_id?: string | null;
  billing_address_id?: string | null;
  sales_rep_id: string;
  discount_type?: string | null;
  discount_value?: number | null;
  internal_notes?: string | null;
  customer_notes?: string | null;
  lines?: QuotationLineCreate[];
}

export interface SalesQuotationRead {
  id: string;
  company_id: string;
  quotation_number: string;
  customer_id: string;
  quotation_date: string;
  validity_date: string;
  currency_code: string;
  payment_term_id: string | null;
  shipping_address_id: string | null;
  billing_address_id: string | null;
  sales_rep_id: string;
  revision_number: number;
  status: string;
  subtotal: string;
  discount_type: string | null;
  discount_value: string | null;
  discount_amount: string;
  tax_amount: string;
  total_amount: string;
  internal_notes: string | null;
  customer_notes: string | null;
  converted_order_id: string | null;
  version: number;
  lines: QuotationLineRead[];
}

export interface SalesQuotationListItem {
  id: string;
  company_id: string;
  quotation_number: string;
  customer_id: string;
  quotation_date: string;
  validity_date: string;
  currency_code: string;
  status: string;
  total_amount: string;
  revision_number: number;
}

export interface QuotationRevisionRead {
  id: string;
  company_id: string;
  quotation_id: string;
  revision_number: number;
  snapshot: Record<string, unknown>;
  modified_by: string;
  modified_at: string;
  change_summary: string | null;
}

export interface QuotationConvertResponse {
  quotation_id: string;
  quotation_number: string;
  order_id: string;
  order_number: string;
  message: string;
}

// ---------------------------------------------------------------------------
// Phase 3 – Sales Quotations: API functions
// ---------------------------------------------------------------------------

export function listQuotations(
  companyId: string,
  params: {
    skip?: number;
    limit?: number;
    status?: string;
    customer_id?: string;
    search?: string;
  } = {},
  token?: string
): Promise<StandardResponse<SalesQuotationListItem[]>> {
  const qs = new URLSearchParams();
  if (params.skip !== undefined) qs.set("skip", String(params.skip));
  if (params.limit !== undefined) qs.set("limit", String(params.limit));
  if (params.status) qs.set("status", params.status);
  if (params.customer_id) qs.set("customer_id", params.customer_id);
  if (params.search) qs.set("search", params.search);
  const query = qs.toString() ? `?${qs}` : "";
  return apiCall(`${salesBase(companyId)}/quotations${query}`, {}, token);
}

export function getQuotation(
  companyId: string,
  quotationId: string,
  token?: string
): Promise<StandardResponse<SalesQuotationRead>> {
  return apiCall(
    `${salesBase(companyId)}/quotations/${quotationId}`,
    {},
    token
  );
}

export function createQuotation(
  companyId: string,
  data: SalesQuotationCreate,
  token?: string
): Promise<StandardResponse<SalesQuotationRead>> {
  return apiCall(
    `${salesBase(companyId)}/quotations`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function sendQuotation(
  companyId: string,
  quotationId: string,
  data: { notes?: string },
  token?: string
): Promise<StandardResponse<SalesQuotationRead>> {
  return apiCall(
    `${salesBase(companyId)}/quotations/${quotationId}/send`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function acceptQuotation(
  companyId: string,
  quotationId: string,
  data: { notes?: string },
  token?: string
): Promise<StandardResponse<SalesQuotationRead>> {
  return apiCall(
    `${salesBase(companyId)}/quotations/${quotationId}/accept`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function rejectQuotation(
  companyId: string,
  quotationId: string,
  data: { reason: string },
  token?: string
): Promise<StandardResponse<SalesQuotationRead>> {
  return apiCall(
    `${salesBase(companyId)}/quotations/${quotationId}/reject`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function cancelQuotation(
  companyId: string,
  quotationId: string,
  data: { reason: string },
  token?: string
): Promise<StandardResponse<SalesQuotationRead>> {
  return apiCall(
    `${salesBase(companyId)}/quotations/${quotationId}/cancel`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function expireQuotation(
  companyId: string,
  quotationId: string,
  token?: string
): Promise<StandardResponse<SalesQuotationRead>> {
  return apiCall(
    `${salesBase(companyId)}/quotations/${quotationId}/expire`,
    { method: "POST", body: JSON.stringify({}) },
    token
  );
}

export function convertQuotation(
  companyId: string,
  quotationId: string,
  token?: string
): Promise<StandardResponse<QuotationConvertResponse>> {
  return apiCall(
    `${salesBase(companyId)}/quotations/${quotationId}/convert`,
    { method: "POST", body: JSON.stringify({}) },
    token
  );
}

export function getQuotationRevisions(
  companyId: string,
  quotationId: string,
  token?: string
): Promise<StandardResponse<QuotationRevisionRead[]>> {
  return apiCall(
    `${salesBase(companyId)}/quotations/${quotationId}/revisions`,
    {},
    token
  );
}

export function addQuotationLine(
  companyId: string,
  quotationId: string,
  data: QuotationLineCreate,
  token?: string
): Promise<StandardResponse<QuotationLineRead>> {
  return apiCall(
    `${salesBase(companyId)}/quotations/${quotationId}/lines`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function deleteQuotationLine(
  companyId: string,
  quotationId: string,
  lineId: string,
  token?: string
): Promise<void> {
  return apiCall(
    `${salesBase(companyId)}/quotations/${quotationId}/lines/${lineId}`,
    { method: "DELETE" },
    token
  ).then(() => undefined);
}

// ---------------------------------------------------------------------------
// Phase 4 – Sales Orders: Types
// ---------------------------------------------------------------------------

export interface OrderLineRead {
  id: string;
  company_id: string;
  order_id: string;
  line_number: number;
  product_id: string | null;
  description: string;
  quantity_ordered: string;
  quantity_delivered: string;
  unit_of_measure: string;
  unit_price: string;
  cost_price: string | null;
  discount_percentage: string | null;
  discount_amount: string | null;
  tax_category: string | null;
  tax_rate: string | null;
  tax_amount: string;
  extended_amount: string;
  delivery_status: string;
  price_source: string;
  notes: string | null;
}

export interface SalesOrderListItem {
  id: string;
  order_number: string;
  customer_id: string;
  order_date: string;
  status: string;
  priority: string;
  total_amount: string;
  currency_code: string;
  sales_rep_id: string;
}

export interface SalesOrderRead {
  id: string;
  company_id: string;
  order_number: string;
  customer_id: string;
  quotation_id: string | null;
  order_date: string;
  required_delivery_date: string | null;
  currency_code: string;
  payment_term_id: string | null;
  shipping_address_id: string | null;
  billing_address_id: string | null;
  sales_rep_id: string;
  priority: string;
  status: string;
  subtotal: string;
  discount_type: string | null;
  discount_value: string | null;
  discount_amount: string;
  tax_amount: string;
  charges_amount: string;
  total_amount: string;
  internal_notes: string | null;
  customer_notes: string | null;
  cancellation_reason: string | null;
  approval_version: number;
  version: number;
  lines: OrderLineRead[];
}

export interface SalesOrderCreate {
  customer_id: string;
  quotation_id?: string | null;
  order_date: string;
  required_delivery_date?: string | null;
  currency_code?: string;
  payment_term_id?: string | null;
  shipping_address_id?: string | null;
  billing_address_id?: string | null;
  sales_rep_id: string;
  priority?: string;
  internal_notes?: string | null;
  customer_notes?: string | null;
  lines?: OrderLineCreate[];
}

export interface OrderLineCreate {
  product_id?: string | null;
  description: string;
  quantity_ordered: number;
  unit_of_measure?: string;
  unit_price: number;
  cost_price?: number | null;
  discount_percentage?: number | null;
  tax_category?: string | null;
  tax_rate?: number | null;
  price_source?: string;
  notes?: string | null;
}

export interface SalesApprovalMatrixRead {
  id: string;
  company_id: string;
  name: string;
  document_type: string;
  is_active: boolean;
  rules: SalesMatrixRuleRead[];
}

export interface SalesMatrixRuleRead {
  id: string;
  company_id: string;
  matrix_id: string;
  approval_level: number;
  min_amount: string;
  max_amount: string | null;
  approver_role: string | null;
  approver_user_id: string | null;
  customer_category_id: string | null;
  auto_approve: boolean;
}

export interface SalesApprovalMatrixCreate {
  name: string;
  document_type: string;
  is_active?: boolean;
  rules?: SalesMatrixRuleCreate[];
}

export interface SalesMatrixRuleCreate {
  approval_level: number;
  min_amount?: number;
  max_amount?: number | null;
  approver_role?: string | null;
  approver_user_id?: string | null;
  customer_category_id?: string | null;
  auto_approve?: boolean;
}

export interface SalesApprovalRecordRead {
  id: string;
  company_id: string;
  document_type: string;
  document_id: string;
  approval_level: number;
  approver_id: string;
  decision: string;
  comments: string | null;
  decided_at: string | null;
  approval_version: number;
}

// ---------------------------------------------------------------------------
// Phase 4 – Sales Orders: API functions
// ---------------------------------------------------------------------------

export function listSalesOrders(
  companyId: string,
  params: {
    status?: string;
    customer_id?: string;
    search?: string;
    skip?: number;
    limit?: number;
  } = {},
  token?: string
): Promise<StandardResponse<SalesOrderListItem[]>> {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status", params.status);
  if (params.customer_id) qs.set("customer_id", params.customer_id);
  if (params.search) qs.set("search", params.search);
  if (params.skip !== undefined) qs.set("skip", String(params.skip));
  if (params.limit !== undefined) qs.set("limit", String(params.limit));
  const query = qs.toString() ? `?${qs}` : "";
  return apiCall(`${salesBase(companyId)}/sales-orders${query}`, {}, token);
}

export function getSalesOrder(
  companyId: string,
  orderId: string,
  token?: string
): Promise<StandardResponse<SalesOrderRead>> {
  return apiCall(`${salesBase(companyId)}/sales-orders/${orderId}`, {}, token);
}

export function createSalesOrder(
  companyId: string,
  data: SalesOrderCreate,
  token?: string
): Promise<StandardResponse<SalesOrderRead>> {
  return apiCall(
    `${salesBase(companyId)}/sales-orders`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function submitSalesOrder(
  companyId: string,
  orderId: string,
  data: { submitted_by: string },
  token?: string
): Promise<StandardResponse<SalesOrderRead>> {
  return apiCall(
    `${salesBase(companyId)}/sales-orders/${orderId}/submit`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function approveSalesOrder(
  companyId: string,
  orderId: string,
  data: { approver_id: string; comments?: string },
  token?: string
): Promise<StandardResponse<SalesOrderRead>> {
  return apiCall(
    `${salesBase(companyId)}/sales-orders/${orderId}/approve`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function rejectSalesOrder(
  companyId: string,
  orderId: string,
  data: { approver_id: string; rejection_reason: string; comments?: string },
  token?: string
): Promise<StandardResponse<SalesOrderRead>> {
  return apiCall(
    `${salesBase(companyId)}/sales-orders/${orderId}/reject`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function cancelSalesOrder(
  companyId: string,
  orderId: string,
  data: { cancellation_reason: string; cancelled_by: string },
  token?: string
): Promise<StandardResponse<SalesOrderRead>> {
  return apiCall(
    `${salesBase(companyId)}/sales-orders/${orderId}/cancel`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function closeSalesOrder(
  companyId: string,
  orderId: string,
  data: { closed_by: string },
  token?: string
): Promise<StandardResponse<SalesOrderRead>> {
  return apiCall(
    `${salesBase(companyId)}/sales-orders/${orderId}/close`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function listApprovalMatrices(
  companyId: string,
  documentType?: string,
  token?: string
): Promise<StandardResponse<SalesApprovalMatrixRead[]>> {
  const qs = documentType ? `?document_type=${documentType}` : "";
  return apiCall(
    `${salesBase(companyId)}/approval-matrices${qs}`,
    {},
    token
  );
}

export function createApprovalMatrix(
  companyId: string,
  data: SalesApprovalMatrixCreate,
  token?: string
): Promise<StandardResponse<SalesApprovalMatrixRead>> {
  return apiCall(
    `${salesBase(companyId)}/approval-matrices`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function getPendingApprovals(
  companyId: string,
  approverId: string,
  token?: string
): Promise<StandardResponse<SalesApprovalRecordRead[]>> {
  return apiCall(
    `${salesBase(companyId)}/approvals/pending?approver_id=${approverId}`,
    {},
    token
  );
}

export function getOrderApprovalHistory(
  companyId: string,
  orderId: string,
  token?: string
): Promise<StandardResponse<SalesApprovalRecordRead[]>> {
  return apiCall(
    `${salesBase(companyId)}/sales-orders/${orderId}/approvals`,
    {},
    token
  );
}

// ---------------------------------------------------------------------------
// Delivery Notes — Types
// ---------------------------------------------------------------------------

export interface DeliveryNoteLineCreate {
  order_line_id: string;
  product_id?: string | null;
  description: string;
  quantity_dispatched: number;
  unit_of_measure: string;
  notes?: string | null;
}

export interface DeliveryNoteCreate {
  order_id: string;
  shipping_address_id?: string | null;
  expected_delivery_date?: string | null;
  carrier?: string | null;
  tracking_number?: string | null;
  internal_notes?: string | null;
  lines: DeliveryNoteLineCreate[];
}

export interface DeliveryNoteDispatch {
  dispatch_date: string;
}

export interface DeliveryNoteLineRead {
  id: string;
  delivery_note_id: string;
  order_line_id: string;
  product_id: string | null;
  description: string;
  quantity_dispatched: string;
  unit_of_measure: string;
  notes: string | null;
}

export interface DeliveryNoteRead {
  id: string;
  company_id: string;
  delivery_number: string;
  order_id: string;
  customer_id: string | null;
  shipping_address_id: string | null;
  dispatch_date: string | null;
  expected_delivery_date: string | null;
  carrier: string | null;
  tracking_number: string | null;
  status: "DRAFT" | "DISPATCHED" | "DELIVERED" | "CANCELLED";
  total_packages: number | null;
  total_weight: string | null;
  dispatched_by: string | null;
  internal_notes: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  lines?: DeliveryNoteLineRead[];
}

export interface DeliveryNoteListItem {
  id: string;
  delivery_number: string;
  order_id: string;
  customer_id: string | null;
  status: "DRAFT" | "DISPATCHED" | "DELIVERED" | "CANCELLED";
  dispatch_date: string | null;
  expected_delivery_date: string | null;
  created_at: string;
}

export interface DeliveryNoteListResponse {
  items: DeliveryNoteListItem[];
  total: number;
  limit: number;
  offset: number;
}

// ---------------------------------------------------------------------------
// Delivery Notes — API
// ---------------------------------------------------------------------------

export function listDeliveryNotes(
  companyId: string,
  params?: {
    order_id?: string;
    status?: string;
    customer_id?: string;
    limit?: number;
    offset?: number;
  },
  token?: string
): Promise<StandardResponse<DeliveryNoteListResponse>> {
  const qs = new URLSearchParams();
  if (params?.order_id) qs.set("order_id", params.order_id);
  if (params?.status) qs.set("status", params.status);
  if (params?.customer_id) qs.set("customer_id", params.customer_id);
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.offset != null) qs.set("offset", String(params.offset));
  const query = qs.toString() ? `?${qs}` : "";
  return apiCall(
    `${salesBase(companyId)}/delivery-notes${query}`,
    {},
    token
  );
}

export function createDeliveryNote(
  companyId: string,
  data: DeliveryNoteCreate,
  token?: string
): Promise<StandardResponse<DeliveryNoteRead>> {
  return apiCall(
    `${salesBase(companyId)}/delivery-notes`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function getDeliveryNote(
  companyId: string,
  deliveryNoteId: string,
  token?: string
): Promise<StandardResponse<DeliveryNoteRead>> {
  return apiCall(
    `${salesBase(companyId)}/delivery-notes/${deliveryNoteId}`,
    {},
    token
  );
}

export function dispatchDeliveryNote(
  companyId: string,
  deliveryNoteId: string,
  data: DeliveryNoteDispatch,
  token?: string
): Promise<StandardResponse<DeliveryNoteRead>> {
  return apiCall(
    `${salesBase(companyId)}/delivery-notes/${deliveryNoteId}/dispatch`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function deliverDeliveryNote(
  companyId: string,
  deliveryNoteId: string,
  token?: string
): Promise<StandardResponse<DeliveryNoteRead>> {
  return apiCall(
    `${salesBase(companyId)}/delivery-notes/${deliveryNoteId}/deliver`,
    { method: "POST" },
    token
  );
}

export function cancelDeliveryNote(
  companyId: string,
  deliveryNoteId: string,
  token?: string
): Promise<StandardResponse<DeliveryNoteRead>> {
  return apiCall(
    `${salesBase(companyId)}/delivery-notes/${deliveryNoteId}/cancel`,
    { method: "POST" },
    token
  );
}

export function listDeliveryNoteLines(
  companyId: string,
  deliveryNoteId: string,
  token?: string
): Promise<StandardResponse<DeliveryNoteLineRead[]>> {
  return apiCall(
    `${salesBase(companyId)}/delivery-notes/${deliveryNoteId}/lines`,
    {},
    token
  );
}

// ---------------------------------------------------------------------------
// Phase 6 — Sales Invoices
// ---------------------------------------------------------------------------

export interface InvoiceLineCreate {
  product_id?: string | null;
  description: string;
  quantity: string;
  unit_of_measure: string;
  unit_price: string;
  discount_percentage?: string | null;
  discount_amount?: string | null;
  tax_rate?: string | null;
  delivery_note_line_id?: string | null;
  order_line_id?: string | null;
}

export interface InvoiceLineRead {
  id: string;
  company_id: string;
  invoice_id: string;
  line_number: number;
  product_id: string | null;
  description: string;
  quantity: string;
  unit_of_measure: string;
  unit_price: string;
  discount_percentage: string | null;
  discount_amount: string | null;
  tax_rate: string | null;
  tax_amount: string;
  extended_amount: string;
  delivery_note_line_id: string | null;
  order_line_id: string | null;
  is_deleted: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface InvoiceChargeCreate {
  charge_type: "FREIGHT" | "HANDLING" | "INSURANCE" | "OTHER";
  description: string;
  amount: string;
  tax_applicable?: boolean;
}

export interface InvoiceChargeRead {
  id: string;
  company_id: string;
  invoice_id: string;
  charge_type: string;
  description: string;
  amount: string;
  tax_applicable: boolean;
  is_deleted: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface InvoiceCreate {
  customer_id: string;
  order_id?: string | null;
  delivery_note_id?: string | null;
  invoice_date: string;
  currency_code: string;
  payment_term_id?: string | null;
  billing_address_id?: string | null;
  internal_notes?: string | null;
  customer_notes?: string | null;
  lines?: InvoiceLineCreate[];
  charges?: InvoiceChargeCreate[];
}

export interface InvoiceRead {
  id: string;
  company_id: string;
  invoice_number: string;
  customer_id: string;
  order_id: string | null;
  delivery_note_id: string | null;
  payment_term_id: string | null;
  billing_address_id: string | null;
  invoice_date: string;
  due_date: string;
  currency_code: string;
  status: string;
  subtotal: string;
  discount_amount: string;
  tax_amount: string;
  charges_amount: string;
  total_amount: string;
  amount_in_words: string | null;
  credit_note_amount: string | null;
  internal_notes: string | null;
  customer_notes: string | null;
  version: number;
  is_deleted: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface InvoiceListItem {
  id: string;
  invoice_number: string;
  customer_id: string;
  order_id: string | null;
  status: string;
  invoice_date: string;
  due_date: string;
  total_amount: string;
  currency_code: string;
  created_at: string | null;
}

export interface InvoiceListResponse {
  items: InvoiceListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface InvoiceListParams {
  customer_id?: string;
  status?: string;
  order_id?: string;
  delivery_note_id?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export function listInvoices(
  companyId: string,
  params: InvoiceListParams = {},
  token?: string
): Promise<StandardResponse<InvoiceListResponse>> {
  const qs = new URLSearchParams();
  if (params.customer_id) qs.set("customer_id", params.customer_id);
  if (params.status) qs.set("status", params.status);
  if (params.order_id) qs.set("order_id", params.order_id);
  if (params.delivery_note_id) qs.set("delivery_note_id", params.delivery_note_id);
  if (params.date_from) qs.set("date_from", params.date_from);
  if (params.date_to) qs.set("date_to", params.date_to);
  if (params.limit != null) qs.set("limit", String(params.limit));
  if (params.offset != null) qs.set("offset", String(params.offset));
  const q = qs.toString();
  return apiCall(
    `${salesBase(companyId)}/invoices${q ? `?${q}` : ""}`,
    {},
    token
  );
}

export function createInvoice(
  companyId: string,
  data: InvoiceCreate,
  token?: string
): Promise<StandardResponse<InvoiceRead>> {
  return apiCall(
    `${salesBase(companyId)}/invoices`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function getInvoice(
  companyId: string,
  invoiceId: string,
  token?: string
): Promise<StandardResponse<InvoiceRead>> {
  return apiCall(
    `${salesBase(companyId)}/invoices/${invoiceId}`,
    {},
    token
  );
}

export function issueInvoice(
  companyId: string,
  invoiceId: string,
  token?: string
): Promise<StandardResponse<InvoiceRead>> {
  return apiCall(
    `${salesBase(companyId)}/invoices/${invoiceId}/issue`,
    { method: "POST", body: JSON.stringify({}) },
    token
  );
}

export function cancelInvoice(
  companyId: string,
  invoiceId: string,
  token?: string
): Promise<StandardResponse<InvoiceRead>> {
  return apiCall(
    `${salesBase(companyId)}/invoices/${invoiceId}/cancel`,
    { method: "POST" },
    token
  );
}

export function issueCreditNote(
  companyId: string,
  invoiceId: string,
  creditNoteAmount: string,
  token?: string
): Promise<StandardResponse<InvoiceRead>> {
  return apiCall(
    `${salesBase(companyId)}/invoices/${invoiceId}/credit-note`,
    { method: "POST", body: JSON.stringify({ credit_note_amount: creditNoteAmount }) },
    token
  );
}

export function listInvoiceLines(
  companyId: string,
  invoiceId: string,
  token?: string
): Promise<StandardResponse<InvoiceLineRead[]>> {
  return apiCall(
    `${salesBase(companyId)}/invoices/${invoiceId}/lines`,
    {},
    token
  );
}

export function listInvoiceCharges(
  companyId: string,
  invoiceId: string,
  token?: string
): Promise<StandardResponse<InvoiceChargeRead[]>> {
  return apiCall(
    `${salesBase(companyId)}/invoices/${invoiceId}/charges`,
    {},
    token
  );
}

// ---------------------------------------------------------------------------
// Phase 7 — Sales Returns
// ---------------------------------------------------------------------------

export interface ReturnLineRead {
  id: string;
  company_id: string;
  return_id: string;
  product_id: string | null;
  description: string;
  quantity_returned: string;
  quantity_accepted: string;
  quantity_rejected: string;
  unit_price: string;
  extended_amount: string;
  condition: string;
  reason_code_id: string | null;
  is_deleted: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface ReturnLineCreate {
  product_id?: string | null;
  description: string;
  quantity_returned: string;
  unit_price: string;
  condition?: "NEW" | "USED" | "DAMAGED" | "DEFECTIVE";
  reason_code_id?: string | null;
}

export interface SalesReturnRead {
  id: string;
  company_id: string;
  return_number: string;
  customer_id: string;
  order_id: string | null;
  invoice_id: string | null;
  replacement_order_id: string | null;
  return_date: string;
  reason_code_id: string;
  reason_description: string | null;
  resolution_type: string;
  status: string;
  approval_version: number;
  received_by: string | null;
  received_at: string | null;
  credit_note_amount: string | null;
  internal_notes: string | null;
  version: number;
  is_deleted: boolean;
  created_at: string | null;
  updated_at: string | null;
  lines: ReturnLineRead[];
}

export interface SalesReturnListItem {
  id: string;
  return_number: string;
  customer_id: string;
  order_id: string | null;
  return_date: string;
  resolution_type: string;
  status: string;
  created_at: string | null;
}

export interface SalesReturnListResponse {
  items: SalesReturnListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface SalesReturnCreate {
  customer_id: string;
  order_id?: string | null;
  invoice_id?: string | null;
  return_date: string;
  reason_code_id: string;
  reason_description?: string | null;
  resolution_type?: "CREDIT_NOTE" | "REPLACEMENT" | "REFUND_READINESS";
  lines: ReturnLineCreate[];
  internal_notes?: string | null;
}

export interface ReturnReceiveLineItem {
  line_id: string;
  quantity_accepted: string;
  quantity_rejected: string;
}

export interface SalesReturnListParams {
  customer_id?: string;
  status?: string;
  order_id?: string;
  resolution_type?: string;
  limit?: number;
  offset?: number;
}

export function listSalesReturns(
  companyId: string,
  params?: SalesReturnListParams,
  token?: string
): Promise<StandardResponse<SalesReturnListResponse>> {
  const qs = new URLSearchParams();
  if (params?.customer_id) qs.set("customer_id", params.customer_id);
  if (params?.status) qs.set("status", params.status);
  if (params?.order_id) qs.set("order_id", params.order_id);
  if (params?.resolution_type) qs.set("resolution_type", params.resolution_type);
  if (params?.limit !== undefined) qs.set("limit", String(params.limit));
  if (params?.offset !== undefined) qs.set("offset", String(params.offset));
  const q = qs.toString();
  return apiCall(
    `${salesBase(companyId)}/returns${q ? `?${q}` : ""}`,
    {},
    token
  );
}

export function createSalesReturn(
  companyId: string,
  data: SalesReturnCreate,
  token?: string
): Promise<StandardResponse<SalesReturnRead>> {
  return apiCall(
    `${salesBase(companyId)}/returns`,
    { method: "POST", body: JSON.stringify(data) },
    token
  );
}

export function getSalesReturn(
  companyId: string,
  returnId: string,
  token?: string
): Promise<StandardResponse<SalesReturnRead>> {
  return apiCall(
    `${salesBase(companyId)}/returns/${returnId}`,
    {},
    token
  );
}

export function submitSalesReturn(
  companyId: string,
  returnId: string,
  token?: string
): Promise<StandardResponse<SalesReturnRead>> {
  return apiCall(
    `${salesBase(companyId)}/returns/${returnId}/submit`,
    { method: "POST", body: JSON.stringify({}) },
    token
  );
}

export function approveSalesReturn(
  companyId: string,
  returnId: string,
  token?: string
): Promise<StandardResponse<SalesReturnRead>> {
  return apiCall(
    `${salesBase(companyId)}/returns/${returnId}/approve`,
    { method: "POST", body: JSON.stringify({ auto_approved: false }) },
    token
  );
}

export function rejectSalesReturn(
  companyId: string,
  returnId: string,
  rejectionReason: string,
  token?: string
): Promise<StandardResponse<SalesReturnRead>> {
  return apiCall(
    `${salesBase(companyId)}/returns/${returnId}/reject`,
    { method: "POST", body: JSON.stringify({ rejection_reason: rejectionReason }) },
    token
  );
}

export function receiveSalesReturn(
  companyId: string,
  returnId: string,
  acceptedLines: ReturnReceiveLineItem[],
  token?: string
): Promise<StandardResponse<SalesReturnRead>> {
  return apiCall(
    `${salesBase(companyId)}/returns/${returnId}/receive`,
    { method: "POST", body: JSON.stringify({ accepted_lines: acceptedLines }) },
    token
  );
}

export function completeSalesReturn(
  companyId: string,
  returnId: string,
  creditNoteAmount?: string | null,
  notes?: string | null,
  token?: string
): Promise<StandardResponse<SalesReturnRead>> {
  return apiCall(
    `${salesBase(companyId)}/returns/${returnId}/complete`,
    {
      method: "POST",
      body: JSON.stringify({
        credit_note_amount: creditNoteAmount ?? null,
        notes: notes ?? null,
      }),
    },
    token
  );
}

export function cancelSalesReturn(
  companyId: string,
  returnId: string,
  token?: string
): Promise<StandardResponse<SalesReturnRead>> {
  return apiCall(
    `${salesBase(companyId)}/returns/${returnId}/cancel`,
    { method: "POST", body: JSON.stringify({}) },
    token
  );
}

export function listReturnLines(
  companyId: string,
  returnId: string,
  token?: string
): Promise<StandardResponse<ReturnLineRead[]>> {
  return apiCall(
    `${salesBase(companyId)}/returns/${returnId}/lines`,
    {},
    token
  );
}

// ===========================================================================
// Phase 8 — Sales Intelligence & Reporting
// ===========================================================================

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface KPIResult {
  kpi_id: string;
  name: string;
  value: string | null;
  unit: string;
  period_label: string;
  trend: "UP" | "DOWN" | "STABLE" | null;
  change_pct: string | null;
}

export interface KPIDashboard {
  company_id: string;
  period_label: string;
  kpis: KPIResult[];
}

export interface ReportResponse {
  report_type: string;
  company_id: string;
  params: Record<string, unknown>;
  total: number;
  rows: Record<string, unknown>[];
}

export interface ReportParams {
  date_from?: string;
  date_to?: string;
  customer_id?: string;
  sales_rep_id?: string;
  currency_code?: string;
  limit?: number;
  offset?: number;
}

// ---------------------------------------------------------------------------
// KPI Dashboard
// ---------------------------------------------------------------------------

export function getKPIDashboard(
  companyId: string,
  params?: { date_from?: string; date_to?: string },
  token?: string
): Promise<StandardResponse<KPIDashboard>> {
  const qs = new URLSearchParams();
  if (params?.date_from) qs.set("date_from", params.date_from);
  if (params?.date_to) qs.set("date_to", params.date_to);
  const query = qs.toString() ? `?${qs}` : "";
  return apiCall(`${salesBase(companyId)}/kpis${query}`, {}, token);
}

// ---------------------------------------------------------------------------
// Report runner
// ---------------------------------------------------------------------------

export function getSalesReport(
  companyId: string,
  reportType: string,
  params?: ReportParams,
  token?: string
): Promise<StandardResponse<ReportResponse>> {
  const qs = new URLSearchParams();
  if (params?.date_from) qs.set("date_from", params.date_from);
  if (params?.date_to) qs.set("date_to", params.date_to);
  if (params?.customer_id) qs.set("customer_id", params.customer_id);
  if (params?.sales_rep_id) qs.set("sales_rep_id", params.sales_rep_id);
  if (params?.currency_code) qs.set("currency_code", params.currency_code);
  if (params?.limit !== undefined) qs.set("limit", String(params.limit));
  if (params?.offset !== undefined) qs.set("offset", String(params.offset));
  const query = qs.toString() ? `?${qs}` : "";
  return apiCall(
    `${salesBase(companyId)}/reports/${reportType}${query}`,
    {},
    token
  );
}

// ---------------------------------------------------------------------------
// Report export (returns a Blob for file download)
// ---------------------------------------------------------------------------

export async function exportSalesReport(
  companyId: string,
  reportType: string,
  params?: ReportParams & { fmt?: "csv" | "excel" },
  token?: string
): Promise<Blob> {
  const qs = new URLSearchParams();
  if (params?.fmt) qs.set("fmt", params.fmt);
  if (params?.date_from) qs.set("date_from", params.date_from);
  if (params?.date_to) qs.set("date_to", params.date_to);
  if (params?.customer_id) qs.set("customer_id", params.customer_id);
  if (params?.limit !== undefined) qs.set("limit", String(params.limit));
  if (params?.offset !== undefined) qs.set("offset", String(params.offset));
  const query = qs.toString() ? `?${qs}` : "";
  const url = `${salesBase(companyId)}/reports/${reportType}/export${query}`;

  const headers: Record<string, string> = {};
  const effectiveToken = token || getAccessToken();
  if (effectiveToken) headers["Authorization"] = `Bearer ${effectiveToken}`;

  // salesBase() already includes API_BASE — url is already absolute.
  const resp = await fetch(url, { headers });
  if (!resp.ok) throw new Error(`Export failed: ${resp.statusText}`);
  return resp.blob();
}
