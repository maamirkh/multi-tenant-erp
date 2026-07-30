/**
 * Purchase module API client.
 *
 * Provides typed functions for all purchase module endpoints.
 * All requests are scoped to a company_id (tenant isolation).
 *
 * Spec ref: specs/006-purchase-management/spec.md §23 Functional Requirements
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SupplierCategoryRead {
  id: string;
  company_id: string;
  code: string;
  name: string;
  parent_id: string | null;
  description: string | null;
  status: string;
}

export interface SupplierCategoryCreate {
  code: string;
  name: string;
  parent_id?: string | null;
  description?: string | null;
}

export interface SupplierCategoryUpdate {
  name?: string;
  description?: string | null;
}

export interface PaymentTermsRead {
  id: string;
  company_id: string;
  code: string;
  name: string;
  net_days: number;
  discount_days: number | null;
  discount_percent: string | null;
  description: string | null;
  is_active: boolean;
}

export interface PaymentTermsCreate {
  code: string;
  name: string;
  net_days: number;
  discount_days?: number | null;
  discount_percent?: string | null;
  description?: string | null;
}

export interface PurchaseReasonCodeRead {
  id: string;
  company_id: string;
  code: string;
  name: string;
  reason_type: string;
  is_active: boolean;
}

export interface PurchaseReasonCodeCreate {
  code: string;
  name: string;
  reason_type: "RETURN" | "CANCELLATION" | "REJECTION" | "GENERAL";
}

export interface PurchaseFeatureFlagRead {
  flag_key: string;
  label: string;
  description: string;
  is_enabled: boolean;
  is_overridden: boolean;
  default_enabled: boolean;
}

export interface PurchasePolicyRead {
  id: string;
  company_id: string;
  direct_po_allowed: boolean;
  pr_approval_required: boolean;
  po_approval_required: boolean;
  over_receipt_policy: "BLOCK" | "WARN" | "ALLOW";
  credit_limit_mode: "BLOCK" | "WARN" | "OFF";
  ppv_alert_threshold_percent: string;
  supplier_rating_window: number;
}

export interface StandardResponse<T> {
  data: T;
  message: string;
  meta: {
    request_id: string;
    timestamp: string;
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<StandardResponse<T>> {
  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
    ...options,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(
      err?.detail ?? `API error ${res.status}: ${res.statusText}`
    );
  }

  return res.json() as Promise<StandardResponse<T>>;
}

// ---------------------------------------------------------------------------
// Purchase Health
// ---------------------------------------------------------------------------

export async function getPurchaseHealth(companyId: string) {
  return apiFetch<{ module: string; version: string; status: string }>(
    `/companies/${companyId}/purchase/health`
  );
}

// ---------------------------------------------------------------------------
// Feature Flags
// ---------------------------------------------------------------------------

export async function getPurchaseFeatureFlags(companyId: string) {
  return apiFetch<PurchaseFeatureFlagRead[]>(
    `/companies/${companyId}/purchase/feature-flags`
  );
}

export async function updatePurchaseFeatureFlag(
  companyId: string,
  flagKey: string,
  isEnabled: boolean,
  description?: string
) {
  return apiFetch<PurchaseFeatureFlagRead>(
    `/companies/${companyId}/purchase/feature-flags/${flagKey}`,
    {
      method: "PUT",
      body: JSON.stringify({ is_enabled: isEnabled, description }),
    }
  );
}

// ---------------------------------------------------------------------------
// Supplier Categories
// ---------------------------------------------------------------------------

export async function getSupplierCategories(
  companyId: string,
  status?: string
) {
  const params = status ? `?status=${status}` : "";
  return apiFetch<SupplierCategoryRead[]>(
    `/companies/${companyId}/purchase/settings/categories${params}`
  );
}

export async function getSupplierCategory(companyId: string, id: string) {
  return apiFetch<SupplierCategoryRead>(
    `/companies/${companyId}/purchase/settings/categories/${id}`
  );
}

export async function createSupplierCategory(
  companyId: string,
  data: SupplierCategoryCreate
) {
  return apiFetch<SupplierCategoryRead>(
    `/companies/${companyId}/purchase/settings/categories`,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export async function updateSupplierCategory(
  companyId: string,
  id: string,
  data: SupplierCategoryUpdate
) {
  return apiFetch<SupplierCategoryRead>(
    `/companies/${companyId}/purchase/settings/categories/${id}`,
    { method: "PUT", body: JSON.stringify(data) }
  );
}

export async function deleteSupplierCategory(companyId: string, id: string) {
  const res = await fetch(
    `${API_BASE}/api/v1/companies/${companyId}/purchase/settings/categories/${id}`,
    { method: "DELETE" }
  );
  if (!res.ok && res.status !== 204) {
    throw new Error(`Failed to delete category: ${res.statusText}`);
  }
}

// ---------------------------------------------------------------------------
// Payment Terms
// ---------------------------------------------------------------------------

export async function getPaymentTerms(
  companyId: string,
  activeOnly: boolean = true
) {
  return apiFetch<PaymentTermsRead[]>(
    `/companies/${companyId}/purchase/settings/payment-terms?active_only=${activeOnly}`
  );
}

export async function createPaymentTerms(
  companyId: string,
  data: PaymentTermsCreate
) {
  return apiFetch<PaymentTermsRead>(
    `/companies/${companyId}/purchase/settings/payment-terms`,
    { method: "POST", body: JSON.stringify(data) }
  );
}

// ---------------------------------------------------------------------------
// Reason Codes
// ---------------------------------------------------------------------------

export async function getPurchaseReasonCodes(
  companyId: string,
  reasonType?: string
) {
  const params = reasonType ? `?reason_type=${reasonType}` : "";
  return apiFetch<PurchaseReasonCodeRead[]>(
    `/companies/${companyId}/purchase/settings/reason-codes${params}`
  );
}

export async function createPurchaseReasonCode(
  companyId: string,
  data: PurchaseReasonCodeCreate
) {
  return apiFetch<PurchaseReasonCodeRead>(
    `/companies/${companyId}/purchase/settings/reason-codes`,
    { method: "POST", body: JSON.stringify(data) }
  );
}

// ---------------------------------------------------------------------------
// Purchase Policy
// ---------------------------------------------------------------------------

export async function getPurchasePolicy(companyId: string) {
  return apiFetch<PurchasePolicyRead>(
    `/companies/${companyId}/purchase/settings/policy`
  );
}

export async function updatePurchasePolicy(
  companyId: string,
  data: Partial<Omit<PurchasePolicyRead, "id" | "company_id">>
) {
  return apiFetch<PurchasePolicyRead>(
    `/companies/${companyId}/purchase/settings/policy`,
    { method: "PUT", body: JSON.stringify(data) }
  );
}

// ---------------------------------------------------------------------------
// Supplier types (Phase 1)
// ---------------------------------------------------------------------------

export interface SupplierList {
  id: string;
  company_id: string;
  supplier_code: string;
  legal_name: string;
  trading_name: string | null;
  supplier_type: string;
  status: string;
  is_preferred: boolean;
  rating_score: string | null;
  lead_time_days: number | null;
  created_at: string;
}

export interface SupplierRead extends SupplierList {
  vendor_code: string | null;
  currency_code: string;
  category_id: string | null;
  payment_terms_id: string | null;
  tax_registration_number: string | null;
  tax_category: string | null;
  tax_region: string | null;
  website: string | null;
  notes: string | null;
  updated_at: string | null;
}

export interface SupplierCreate {
  supplier_code: string;
  legal_name: string;
  vendor_code?: string;
  trading_name?: string;
  supplier_type?: string;
  currency_code?: string;
  category_id?: string;
  payment_terms_id?: string;
  tax_registration_number?: string;
  website?: string;
  notes?: string;
  lead_time_days?: number;
}

export interface SupplierUpdate {
  legal_name?: string;
  vendor_code?: string;
  trading_name?: string;
  supplier_type?: string;
  currency_code?: string;
  category_id?: string;
  payment_terms_id?: string;
  tax_registration_number?: string;
  website?: string;
  notes?: string;
  lead_time_days?: number;
}

export interface SupplierContactRead {
  id: string;
  company_id: string;
  supplier_id: string;
  first_name: string;
  last_name: string;
  role: string | null;
  email: string | null;
  phone: string | null;
  mobile: string | null;
  is_primary: boolean;
}

export interface SupplierContactCreate {
  first_name: string;
  last_name: string;
  role?: string;
  email?: string;
  phone?: string;
  mobile?: string;
  is_primary?: boolean;
}

export interface SupplierAddressRead {
  id: string;
  company_id: string;
  supplier_id: string;
  address_type: string;
  address_line_1: string;
  address_line_2: string | null;
  city: string;
  state: string | null;
  postal_code: string | null;
  country_code: string;
  is_default: boolean;
}

export interface SupplierAddressCreate {
  address_type?: string;
  address_line_1: string;
  address_line_2?: string;
  city: string;
  state?: string;
  postal_code?: string;
  country_code: string;
  is_default?: boolean;
}

// ---------------------------------------------------------------------------
// Supplier API functions (Phase 1)
// ---------------------------------------------------------------------------

export interface SupplierSearchParams {
  query?: string;
  status?: string;
  category_id?: string;
  supplier_type?: string;
  is_preferred?: boolean;
  skip?: number;
  limit?: number;
}

export async function getSuppliers(
  companyId: string,
  params: SupplierSearchParams = {}
) {
  const qs = new URLSearchParams();
  if (params.query) qs.set("query", params.query);
  if (params.status) qs.set("status", params.status);
  if (params.category_id) qs.set("category_id", params.category_id);
  if (params.supplier_type) qs.set("supplier_type", params.supplier_type);
  if (params.is_preferred != null) qs.set("is_preferred", String(params.is_preferred));
  if (params.skip != null) qs.set("skip", String(params.skip));
  if (params.limit != null) qs.set("limit", String(params.limit));
  const q = qs.toString() ? `?${qs}` : "";
  return apiFetch<SupplierList[]>(`/companies/${companyId}/purchase/suppliers${q}`);
}

export async function getSupplier(companyId: string, supplierId: string) {
  return apiFetch<SupplierRead>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}`
  );
}

export async function createSupplier(companyId: string, data: SupplierCreate) {
  return apiFetch<SupplierRead>(
    `/companies/${companyId}/purchase/suppliers`,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export async function updateSupplier(
  companyId: string,
  supplierId: string,
  data: SupplierUpdate
) {
  return apiFetch<SupplierRead>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}`,
    { method: "PUT", body: JSON.stringify(data) }
  );
}

export async function activateSupplier(
  companyId: string,
  supplierId: string,
  data: { reason?: string }
) {
  return apiFetch<SupplierRead>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/activate`,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export async function deactivateSupplier(
  companyId: string,
  supplierId: string,
  data: { reason?: string }
) {
  return apiFetch<SupplierRead>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/deactivate`,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export async function blockSupplier(
  companyId: string,
  supplierId: string,
  data: { reason: string }
) {
  return apiFetch<SupplierRead>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/block`,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export async function reactivateSupplier(
  companyId: string,
  supplierId: string,
  data: { reason?: string }
) {
  return apiFetch<SupplierRead>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/reactivate`,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export async function archiveSupplier(
  companyId: string,
  supplierId: string,
  data: { reason?: string }
) {
  return apiFetch<SupplierRead>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/archive`,
    { method: "POST", body: JSON.stringify(data) }
  );
}

// Contacts

export async function getSupplierContacts(companyId: string, supplierId: string) {
  return apiFetch<SupplierContactRead[]>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/contacts`
  );
}

export async function addSupplierContact(
  companyId: string,
  supplierId: string,
  data: SupplierContactCreate
) {
  return apiFetch<SupplierContactRead>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/contacts`,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export async function setPrimaryContact(
  companyId: string,
  supplierId: string,
  contactId: string
) {
  return apiFetch<SupplierContactRead>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/contacts/${contactId}/set-primary`,
    { method: "POST", body: JSON.stringify({}) }
  );
}

// Addresses

export async function getSupplierAddresses(companyId: string, supplierId: string) {
  return apiFetch<SupplierAddressRead[]>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/addresses`
  );
}

export async function addSupplierAddress(
  companyId: string,
  supplierId: string,
  data: SupplierAddressCreate
) {
  return apiFetch<SupplierAddressRead>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/addresses`,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export async function setDefaultAddress(
  companyId: string,
  supplierId: string,
  addressId: string
) {
  return apiFetch<SupplierAddressRead>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/addresses/${addressId}/set-default`,
    { method: "POST", body: JSON.stringify({}) }
  );
}

// =============================================================================
// Phase 2 — Supplier Enrichment
// =============================================================================

// --- Types ---

export interface CreditLimitRead {
  id: string;
  supplier_id: string;
  credit_limit_amount: string;
  currency_code: string;
  enforcement_mode: "BLOCK" | "WARN" | "OFF";
}

export interface BankDetailsRead {
  id: string;
  supplier_id: string;
  bank_name: string;
  account_name: string;
  account_number: string;
  iban: string | null;
  swift_bic: string | null;
  routing_number: string | null;
  bank_country: string;
  currency_code: string;
  is_primary: boolean;
}

export interface BankDetailsCreate {
  bank_name: string;
  account_name: string;
  account_number: string;
  iban?: string;
  swift_bic?: string;
  routing_number?: string;
  bank_country: string;
  currency_code?: string;
  is_primary?: boolean;
}

export interface SupplierRatingRead {
  id: string;
  supplier_id: string;
  on_time_rate: string;
  fill_rate: string;
  rejection_rate: string;
  composite_score: string;
  gr_count_window: number;
  manual_override_score: string | null;
  manual_override_reason: string | null;
  last_computed_at: string;
}

export interface SupplierDocumentRead {
  id: string;
  supplier_id: string;
  document_type: string;
  document_number: string | null;
  issue_date: string | null;
  expiry_date: string | null;
  file_url: string | null;
}

export interface SupplierDocumentCreate {
  document_type: string;
  document_number?: string;
  issue_date?: string;
  expiry_date?: string;
  file_url?: string;
}

// --- Credit Limit ---

export async function getCreditLimit(companyId: string, supplierId: string) {
  return apiFetch<CreditLimitRead>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/credit-limit`
  );
}

export async function setCreditLimit(
  companyId: string,
  supplierId: string,
  data: { credit_limit_amount: number; currency_code?: string; enforcement_mode?: string }
) {
  return apiFetch<CreditLimitRead>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/credit-limit`,
    { method: "PUT", body: JSON.stringify(data) }
  );
}

// --- Bank Details ---

export async function getBankDetails(companyId: string, supplierId: string) {
  return apiFetch<BankDetailsRead[]>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/bank-details`
  );
}

export async function addBankDetails(
  companyId: string,
  supplierId: string,
  data: BankDetailsCreate
) {
  return apiFetch<BankDetailsRead>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/bank-details`,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export async function deleteBankDetails(
  companyId: string,
  supplierId: string,
  bdId: string
) {
  return apiFetch<Record<string, never>>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/bank-details/${bdId}`,
    { method: "DELETE" }
  );
}

// --- Supplier Rating ---

export async function getSupplierRating(companyId: string, supplierId: string) {
  return apiFetch<SupplierRatingRead>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/rating`
  );
}

export async function setRatingOverride(
  companyId: string,
  supplierId: string,
  data: { manual_override_score: number; manual_override_reason?: string }
) {
  return apiFetch<SupplierRatingRead>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/rating/override`,
    { method: "POST", body: JSON.stringify(data) }
  );
}

// --- Supplier Documents ---

export async function getSupplierDocuments(companyId: string, supplierId: string) {
  return apiFetch<SupplierDocumentRead[]>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/documents`
  );
}

export async function addSupplierDocument(
  companyId: string,
  supplierId: string,
  data: SupplierDocumentCreate
) {
  return apiFetch<SupplierDocumentRead>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/documents`,
    { method: "POST", body: JSON.stringify(data) }
  );
}

export async function deleteSupplierDocument(
  companyId: string,
  supplierId: string,
  docId: string
) {
  return apiFetch<Record<string, never>>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/documents/${docId}`,
    { method: "DELETE" }
  );
}

// --- Preferred Supplier ---

export async function setPreferredSupplier(
  companyId: string,
  supplierId: string,
  isPreferred: boolean
) {
  return apiFetch<SupplierRead>(
    `/companies/${companyId}/purchase/suppliers/${supplierId}/preferred`,
    { method: "POST", body: JSON.stringify({ is_preferred: isPreferred }) }
  );
}
