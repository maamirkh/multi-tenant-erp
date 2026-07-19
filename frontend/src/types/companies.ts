/**
 * TypeScript types for the Companies module.
 *
 * Mirrors backend Pydantic schemas defined in:
 *   modules/companies/schemas/company.py
 *   modules/companies/schemas/address.py
 *   modules/companies/schemas/audit.py
 *   modules/companies/schemas/settings.py
 *   modules/companies/schemas/status.py
 *   modules/companies/models/enums.py
 *
 * Keep these in sync with the backend contract. No `any` types are used.
 */

import type { Nullable, UUID } from '@/types';
import type { PaginatedResponse } from '@/lib/api/types';

// ── Enumerations ──────────────────────────────────────────────────────────────

export type CompanyStatus =
  | 'pending_setup'
  | 'active'
  | 'inactive'
  | 'suspended'
  | 'deleted';

export type AddressType = 'registered' | 'mailing' | 'billing' | 'shipping';

export type BusinessType =
  | 'sole_proprietor'
  | 'partnership'
  | 'llc'
  | 'corporation'
  | 'non_profit'
  | 'other';

// ── Domain response types ─────────────────────────────────────────────────────

/**
 * Lightweight company reference stored in CompanyContext.
 * Use this instead of the full Company type when only identity is needed.
 */
export interface CompanySummary {
  id: UUID;
  legal_name: string;
  slug: string;
  status: CompanyStatus;
}

/** Summary company record — returned by POST /companies and list endpoints. */
export interface Company {
  id: UUID;
  legal_name: string;
  trade_name: Nullable<string>;
  slug: string;
  status: CompanyStatus;
  owner_id: UUID;
  email: string;
  country: Nullable<string>;
  default_currency: Nullable<string>;
  default_language: Nullable<string>;
  default_timezone: Nullable<string>;
  created_at: string;
  updated_at: string;
}

/** Full company detail — returned by GET /companies/{id}. */
export interface CompanyDetail extends Company {
  primary_admin_id: Nullable<UUID>;
  phone_primary: Nullable<string>;
  phone_secondary: Nullable<string>;
  website: Nullable<string>;
  tax_number: Nullable<string>;
  registration_number: Nullable<string>;
  business_category: Nullable<string>;
  business_type: Nullable<BusinessType>;
  incorporation_date: Nullable<string>;
  fiscal_year_start_month: Nullable<number>;
  date_format: Nullable<string>;
  number_format: Record<string, unknown>;
  logo_url: Nullable<string>;
  brand_color_primary: Nullable<string>;
  brand_color_secondary: Nullable<string>;
  tagline: Nullable<string>;
  settings: Record<string, unknown>;
  addresses: CompanyAddress[];
}

/** Compact company record used in paginated list responses. */
export interface CompanyListItem {
  id: UUID;
  legal_name: string;
  slug: string;
  status: CompanyStatus;
  country: Nullable<string>;
  default_currency: Nullable<string>;
  created_at: string;
}

/** Company address record returned by the addresses endpoints. */
export interface CompanyAddress {
  id: UUID;
  company_id: UUID;
  address_type: AddressType;
  street_line_1: string;
  street_line_2: Nullable<string>;
  city: string;
  state_province: Nullable<string>;
  postal_code: Nullable<string>;
  country: string;
  is_primary: boolean;
  created_at: string;
  updated_at: string;
}

/** Response from PATCH /companies/{id}/settings. */
export interface CompanySettings {
  company_id: UUID;
  settings: Record<string, unknown>;
  updated_at: string;
}

/** Single audit log entry returned by GET /companies/{id}/audit-logs. */
export interface AuditLogEntry {
  id: UUID;
  company_id: UUID;
  actor_user_id: Nullable<UUID>;
  action: string;
  before_state: Nullable<Record<string, unknown>>;
  after_state: Nullable<Record<string, unknown>>;
  ip_address: Nullable<string>;
  user_agent: Nullable<string>;
  request_id: Nullable<UUID>;
  created_at: string;
}

/** Response from POST /companies/{id}/logo. */
export interface LogoUploadResponse {
  company_id: UUID;
  logo_url: string;
}

/** Response from DELETE /companies/{id}. */
export interface DeleteCompanyResult {
  id: UUID;
  status: string;
  deleted_at: string;
  message: string;
}

// ── Request / Input types ─────────────────────────────────────────────────────

export interface CreateCompanyInput {
  legal_name: string;
  email: string;
  trade_name?: string;
  phone_primary?: string;
  country?: string;
  default_currency?: string;
  default_language?: string;
  default_timezone?: string;
  slug?: string;
}

export interface UpdateCompanyInput {
  legal_name?: string;
  slug?: string;
  trade_name?: string;
  email?: string;
  phone_primary?: string;
  phone_secondary?: string;
  website?: string;
  tax_number?: string;
  registration_number?: string;
  business_category?: string;
  business_type?: BusinessType;
  incorporation_date?: string;
  default_currency?: string;
  default_language?: string;
  default_timezone?: string;
  country?: string;
  fiscal_year_start_month?: number;
  date_format?: string;
  brand_color_primary?: string;
  brand_color_secondary?: string;
  tagline?: string;
  confirm_currency_change?: boolean;
}

export interface UpdateSettingsInput {
  settings: Record<string, unknown>;
}

export interface DeactivateInput {
  reason: string;
}

export interface DeleteCompanyInput {
  reason: string;
  confirm_delete: true;
  force_delete?: boolean;
}

export interface CreateAddressInput {
  address_type: AddressType;
  street_line_1: string;
  street_line_2?: string;
  city: string;
  state_province?: string;
  postal_code?: string;
  country: string;
  is_primary?: boolean;
}

export interface UpdateAddressInput {
  address_type?: AddressType;
  street_line_1?: string;
  street_line_2?: string;
  city?: string;
  state_province?: string;
  postal_code?: string;
  country?: string;
  is_primary?: boolean;
}

// ── Query parameter types ─────────────────────────────────────────────────────

export interface AdminListParams {
  page?: number;
  page_size?: number;
  status?: CompanyStatus;
  country?: string;
  search?: string;
  include_deleted?: boolean;
}

export interface AuditLogParams {
  page?: number;
  page_size?: number;
  action?: string;
  actor_id?: UUID;
  date_from?: string;
  date_to?: string;
}

// Re-export PaginatedResponse for hooks that return paginated company data.
export type { PaginatedResponse };
