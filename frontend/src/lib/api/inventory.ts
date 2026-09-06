/**
 * Inventory module API client functions.
 *
 * Typed wrappers around the apiClient singleton for all Inventory endpoints.
 * Covers Phase 0 endpoints (health, feature flags) — additional functions
 * are added in Phases 1–10 as each sub-domain is implemented.
 *
 * Spec ref: specs/005-inventory-management/spec.md
 */

import { apiClient } from '@/lib/api/client';
import type { StandardResponse } from '@/lib/api/types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface InventoryHealthResponse {
  module: string;
  version: string;
  status: string;
}

export interface FeatureFlagResponse {
  flag_key: string;
  label: string;
  description: string;
  is_enabled: boolean;
  is_overridden: boolean;
  default_enabled: boolean;
}

export interface FeatureFlagUpdateRequest {
  is_enabled: boolean;
  description?: string;
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

/**
 * Check the Inventory module health endpoint.
 * Returns the module version and operational status.
 */
export async function getInventoryHealth(): Promise<StandardResponse<InventoryHealthResponse>> {
  return apiClient.get<InventoryHealthResponse>('/api/v1/inventory/health');
}

// ---------------------------------------------------------------------------
// Feature flags
// ---------------------------------------------------------------------------

/**
 * List all inventory feature flags with their effective state for a company.
 *
 * @param companyId - The company UUID (tenant identifier).
 */
export async function listFeatureFlags(
  companyId: string,
): Promise<StandardResponse<FeatureFlagResponse[]>> {
  return apiClient.get<FeatureFlagResponse[]>(
    `/api/v1/companies/${companyId}/inventory/feature-flags`,
  );
}

/**
 * Enable or disable a specific inventory feature flag for a company.
 *
 * @param companyId - The company UUID (tenant identifier).
 * @param flagKey   - The feature flag key (e.g. "inventory.product_variants").
 * @param payload   - The new enabled state and optional override description.
 */
export async function updateFeatureFlag(
  companyId: string,
  flagKey: string,
  payload: FeatureFlagUpdateRequest,
): Promise<StandardResponse<FeatureFlagResponse>> {
  return apiClient.put<FeatureFlagResponse>(
    `/api/v1/companies/${companyId}/inventory/feature-flags/${encodeURIComponent(flagKey)}`,
    payload,
  );
}

// ---------------------------------------------------------------------------
// Phase 1 — Master Data Types
// ---------------------------------------------------------------------------

export interface CategoryResponse {
  id: string;
  company_id: string;
  code: string;
  name: string;
  description: string | null;
  parent_id: string | null;
  sort_order: number;
  status: 'active' | 'inactive';
  created_at: string;
  updated_at: string;
}

export interface CategoryCreateRequest {
  code: string;
  name: string;
  description?: string;
  parent_id?: string;
  sort_order?: number;
}

export interface BrandResponse {
  id: string;
  company_id: string;
  code: string;
  name: string;
  country_of_origin: string | null;
  logo_url: string | null;
  website: string | null;
  status: 'active' | 'inactive';
  created_at: string;
  updated_at: string;
}

export interface BrandCreateRequest {
  code: string;
  name: string;
  country_of_origin?: string;
  logo_url?: string;
  website?: string;
}

export interface UOMResponse {
  id: string;
  company_id: string;
  code: string;
  name: string;
  uom_type: string;
  symbol: string | null;
  status: 'active' | 'inactive';
  created_at: string;
  updated_at: string;
}

export interface UOMCreateRequest {
  code: string;
  name: string;
  uom_type: string;
  symbol?: string;
}

export interface TagResponse {
  id: string;
  company_id: string;
  name: string;
  color: string | null;
  usage_count: number;
  created_at: string;
  updated_at: string;
}

export interface ReasonCodeResponse {
  id: string;
  company_id: string;
  code: string;
  label: string;
  applies_to: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CustomFieldResponse {
  id: string;
  company_id: string;
  entity_type: string;
  field_key: string;
  field_label: string;
  data_type: string;
  is_required: boolean;
  sort_order: number;
  placeholder: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// ---------------------------------------------------------------------------
// Phase 1 — Category API
// ---------------------------------------------------------------------------

export async function listCategories(
  companyId: string,
): Promise<StandardResponse<CategoryResponse[]>> {
  return apiClient.get(`/api/v1/companies/${companyId}/inventory/categories`);
}

export async function createCategory(
  companyId: string,
  payload: CategoryCreateRequest,
): Promise<StandardResponse<CategoryResponse>> {
  return apiClient.post(`/api/v1/companies/${companyId}/inventory/categories`, payload);
}

export async function deactivateCategory(
  companyId: string,
  categoryId: string,
): Promise<StandardResponse<CategoryResponse>> {
  return apiClient.post(
    `/api/v1/companies/${companyId}/inventory/categories/${categoryId}/deactivate`,
    {},
  );
}

export async function deleteCategory(companyId: string, categoryId: string): Promise<unknown> {
  return apiClient.delete(`/api/v1/companies/${companyId}/inventory/categories/${categoryId}`);
}

// ---------------------------------------------------------------------------
// Phase 1 — Brand API
// ---------------------------------------------------------------------------

export async function listBrands(
  companyId: string,
  page = 1,
  pageSize = 20,
): Promise<StandardResponse<PaginatedResponse<BrandResponse>>> {
  return apiClient.get(
    `/api/v1/companies/${companyId}/inventory/brands?page=${page}&page_size=${pageSize}`,
  );
}

export async function createBrand(
  companyId: string,
  payload: BrandCreateRequest,
): Promise<StandardResponse<BrandResponse>> {
  return apiClient.post(`/api/v1/companies/${companyId}/inventory/brands`, payload);
}

export async function deactivateBrand(
  companyId: string,
  brandId: string,
): Promise<StandardResponse<BrandResponse>> {
  return apiClient.post(
    `/api/v1/companies/${companyId}/inventory/brands/${brandId}/deactivate`,
    {},
  );
}

// ---------------------------------------------------------------------------
// Phase 1 — UOM API
// ---------------------------------------------------------------------------

export async function listUOMs(
  companyId: string,
  page = 1,
  pageSize = 50,
): Promise<StandardResponse<PaginatedResponse<UOMResponse>>> {
  return apiClient.get(
    `/api/v1/companies/${companyId}/inventory/uom?page=${page}&page_size=${pageSize}`,
  );
}

export async function createUOM(
  companyId: string,
  payload: UOMCreateRequest,
): Promise<StandardResponse<UOMResponse>> {
  return apiClient.post(`/api/v1/companies/${companyId}/inventory/uom`, payload);
}

// ---------------------------------------------------------------------------
// Phase 1 — Tags API
// ---------------------------------------------------------------------------

export async function listTags(companyId: string): Promise<StandardResponse<TagResponse[]>> {
  return apiClient.get(`/api/v1/companies/${companyId}/inventory/tags`);
}

// ---------------------------------------------------------------------------
// Phase 1 — Reason Codes API
// ---------------------------------------------------------------------------

export async function listReasonCodes(
  companyId: string,
  page = 1,
  pageSize = 50,
): Promise<StandardResponse<PaginatedResponse<ReasonCodeResponse>>> {
  return apiClient.get(
    `/api/v1/companies/${companyId}/inventory/reason-codes?page=${page}&page_size=${pageSize}`,
  );
}

// ---------------------------------------------------------------------------
// Phase 1 — Custom Fields API
// ---------------------------------------------------------------------------

export async function listCustomFields(
  companyId: string,
  entityType = 'PRODUCT',
): Promise<StandardResponse<CustomFieldResponse[]>> {
  return apiClient.get(
    `/api/v1/companies/${companyId}/inventory/custom-fields?entity_type=${entityType}`,
  );
}

// ---------------------------------------------------------------------------
// Phase 2 — Product Types
// ---------------------------------------------------------------------------

export type ProductType = 'STANDARD' | 'VARIANT' | 'SERVICE' | 'BUNDLE' | 'RAW_MATERIAL';
export type ProductStatus = 'DRAFT' | 'ACTIVE' | 'INACTIVE' | 'DISCONTINUED' | 'ARCHIVED';

export interface ProductResponse {
  id: string;
  company_id: string;
  product_code: string;
  name: string;
  product_type: ProductType;
  status: ProductStatus;
  description: string | null;
  short_description: string | null;
  base_uom_id: string;
  category_id: string | null;
  brand_id: string | null;
  hs_code: string | null;
  country_of_origin: string | null;
  lead_time_days: number | null;
  min_order_qty: number | null;
  max_order_qty: number | null;
  reorder_point: number | null;
  weight_kg: number | null;
  width_cm: number | null;
  height_cm: number | null;
  depth_cm: number | null;
  is_serialized: boolean;
  is_batch_tracked: boolean;
  cost_price: number | null;
  created_by: string | null;
}

export interface ProductCreateRequest {
  product_code: string;
  name: string;
  product_type?: ProductType;
  base_uom_id: string;
  description?: string;
  short_description?: string;
  category_id?: string;
  brand_id?: string;
  hs_code?: string;
  country_of_origin?: string;
  lead_time_days?: number;
  min_order_qty?: number;
  max_order_qty?: number;
  reorder_point?: number;
  weight_kg?: number;
  is_serialized?: boolean;
  is_batch_tracked?: boolean;
  cost_price?: number;
}

export interface ProductUpdateRequest {
  name?: string | undefined;
  description?: string | undefined;
  short_description?: string | undefined;
  category_id?: string | undefined;
  brand_id?: string | undefined;
  cost_price?: number | undefined;
  lead_time_days?: number | undefined;
  reorder_point?: number | undefined;
  is_serialized?: boolean | undefined;
  is_batch_tracked?: boolean | undefined;
}

export interface ProductVariantResponse {
  id: string;
  product_id: string;
  company_id: string;
  variant_code: string;
  attributes: Record<string, unknown> | null;
  is_stock_tracked: boolean;
  status: string;
}

export interface BarcodeResponse {
  id: string;
  product_id: string;
  variant_id: string | null;
  barcode_value: string;
  barcode_type: string;
  is_primary: boolean;
  created_at: string | null;
}

// ---------------------------------------------------------------------------
// Phase 2 — Product API
// ---------------------------------------------------------------------------

export interface ListProductsParams {
  q?: string | undefined;
  status?: string | undefined;
  product_type?: string | undefined;
  page?: number | undefined;
  page_size?: number | undefined;
}

export async function listProducts(
  companyId: string,
  params?: ListProductsParams,
): Promise<StandardResponse<PaginatedResponse<ProductResponse>>> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set('q', params.q);
  if (params?.status) qs.set('status_filter', params.status);
  if (params?.product_type) qs.set('product_type', params.product_type);
  if (params?.page) qs.set('page', String(params.page));
  if (params?.page_size) qs.set('page_size', String(params.page_size));
  const query = qs.toString() ? `?${qs.toString()}` : '';
  return apiClient.get(`/api/v1/companies/${companyId}/inventory/products${query}`);
}

export async function getProduct(
  companyId: string,
  productId: string,
): Promise<StandardResponse<ProductResponse>> {
  return apiClient.get(`/api/v1/companies/${companyId}/inventory/products/${productId}`);
}

export async function createProduct(
  companyId: string,
  payload: ProductCreateRequest,
): Promise<StandardResponse<ProductResponse>> {
  return apiClient.post(`/api/v1/companies/${companyId}/inventory/products`, payload);
}

export async function updateProduct(
  companyId: string,
  productId: string,
  payload: ProductUpdateRequest,
): Promise<StandardResponse<ProductResponse>> {
  return apiClient.put(
    `/api/v1/companies/${companyId}/inventory/products/${productId}`,
    payload,
  );
}

export async function transitionProductStatus(
  companyId: string,
  productId: string,
  action: 'activate' | 'deactivate' | 'discontinue' | 'archive',
): Promise<StandardResponse<ProductResponse>> {
  return apiClient.patch(
    `/api/v1/companies/${companyId}/inventory/products/${productId}/status`,
    { action },
  );
}

export async function deleteProduct(companyId: string, productId: string): Promise<unknown> {
  return apiClient.delete(`/api/v1/companies/${companyId}/inventory/products/${productId}`);
}

export async function listProductVariants(
  companyId: string,
  productId: string,
): Promise<StandardResponse<ProductVariantResponse[]>> {
  return apiClient.get(
    `/api/v1/companies/${companyId}/inventory/products/${productId}/variants`,
  );
}

export async function listProductBarcodes(
  companyId: string,
  productId: string,
): Promise<StandardResponse<BarcodeResponse[]>> {
  return apiClient.get(
    `/api/v1/companies/${companyId}/inventory/products/${productId}/barcodes`,
  );
}
