/**
 * Companies API — typed fetch functions wrapping the shared ApiClient.
 *
 * Each function unwraps the `StandardResponse<T>` envelope and returns the
 * inner `data` payload so callers work with domain types directly.
 *
 * Spec reference: Epic 3, Phase 10 (T060).
 */

import { apiClient } from '@/lib/api/client';
import type { PaginatedData } from '@/lib/api/types';
import type {
  AdminListParams,
  AuditLogEntry,
  AuditLogParams,
  Company,
  CompanyAddress,
  CompanyDetail,
  CompanyListItem,
  CompanySettings,
  CreateAddressInput,
  CreateCompanyInput,
  DeactivateInput,
  DeleteCompanyInput,
  DeleteCompanyResult,
  LogoUploadResponse,
  PaginatedResponse,
  UpdateAddressInput,
  UpdateCompanyInput,
  UpdateSettingsInput,
} from '@/types/companies';

// ── Company CRUD ──────────────────────────────────────────────────────────────

export async function createCompany(data: CreateCompanyInput): Promise<Company> {
  const res = await apiClient.post<Company>('/api/v1/companies', data);
  return res.data;
}

export async function getCompany(id: string): Promise<CompanyDetail> {
  const res = await apiClient.get<CompanyDetail>(`/api/v1/companies/${id}`);
  return res.data;
}

export async function updateCompany(
  id: string,
  data: UpdateCompanyInput
): Promise<CompanyDetail> {
  const res = await apiClient.patch<CompanyDetail>(`/api/v1/companies/${id}`, data);
  return res.data;
}

// ── Status transitions ────────────────────────────────────────────────────────

export async function activateCompany(id: string): Promise<CompanyDetail> {
  const res = await apiClient.post<CompanyDetail>(
    `/api/v1/companies/${id}/activate`,
    {}
  );
  return res.data;
}

export async function deactivateCompany(
  id: string,
  data: DeactivateInput
): Promise<CompanyDetail> {
  const res = await apiClient.post<CompanyDetail>(
    `/api/v1/companies/${id}/deactivate`,
    data
  );
  return res.data;
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

export async function deleteCompany(
  id: string,
  data: DeleteCompanyInput
): Promise<DeleteCompanyResult> {
  const res = await apiClient.deleteWithBody<DeleteCompanyResult>(
    `/api/v1/companies/${id}`,
    data
  );
  return res.data;
}

export async function restoreCompany(id: string): Promise<CompanyDetail> {
  const res = await apiClient.post<CompanyDetail>(
    `/api/v1/companies/${id}/restore`,
    {}
  );
  return res.data;
}

// ── Logo ──────────────────────────────────────────────────────────────────────

export async function uploadCompanyLogo(
  id: string,
  file: File
): Promise<LogoUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await apiClient.postMultipart<LogoUploadResponse>(
    `/api/v1/companies/${id}/logo`,
    formData
  );
  return res.data;
}

// ── Settings ──────────────────────────────────────────────────────────────────

export async function updateCompanySettings(
  id: string,
  data: UpdateSettingsInput
): Promise<CompanySettings> {
  const res = await apiClient.patch<CompanySettings>(
    `/api/v1/companies/${id}/settings`,
    data
  );
  return res.data;
}

// ── Listing ───────────────────────────────────────────────────────────────────

export async function listCompanies(): Promise<Company[]> {
  const res = await apiClient.get<Company[]>('/api/v1/companies');
  return res.data;
}

export async function listAdminCompanies(
  params: AdminListParams
): Promise<PaginatedResponse<CompanyListItem>> {
  const query = new URLSearchParams();
  if (params.page !== undefined) query.set('page', String(params.page));
  if (params.page_size !== undefined) query.set('page_size', String(params.page_size));
  if (params.status !== undefined) query.set('status', params.status);
  if (params.country !== undefined) query.set('country', params.country);
  if (params.search !== undefined) query.set('search', params.search);
  if (params.include_deleted !== undefined)
    query.set('include_deleted', String(params.include_deleted));

  const qs = query.toString();
  const path = `/api/v1/companies/admin/companies${qs ? `?${qs}` : ''}`;
  const res = await apiClient.get<PaginatedData<CompanyListItem>>(path);
  return res as unknown as PaginatedResponse<CompanyListItem>;
}

export async function getCompanyAuditLog(
  id: string,
  params: AuditLogParams
): Promise<PaginatedResponse<AuditLogEntry>> {
  const query = new URLSearchParams();
  if (params.page !== undefined) query.set('page', String(params.page));
  if (params.page_size !== undefined) query.set('page_size', String(params.page_size));
  if (params.action !== undefined) query.set('action', params.action);
  if (params.actor_id !== undefined) query.set('actor_id', params.actor_id);
  if (params.date_from !== undefined) query.set('date_from', params.date_from);
  if (params.date_to !== undefined) query.set('date_to', params.date_to);

  const qs = query.toString();
  const path = `/api/v1/companies/${id}/audit-logs${qs ? `?${qs}` : ''}`;
  const res = await apiClient.get<PaginatedData<AuditLogEntry>>(path);
  return res as unknown as PaginatedResponse<AuditLogEntry>;
}

// ── Addresses ─────────────────────────────────────────────────────────────────

export async function getCompanyAddresses(id: string): Promise<CompanyAddress[]> {
  const res = await apiClient.get<CompanyAddress[]>(`/api/v1/companies/${id}/addresses`);
  return res.data;
}

export async function createCompanyAddress(
  id: string,
  data: CreateAddressInput
): Promise<CompanyAddress> {
  const res = await apiClient.post<CompanyAddress>(
    `/api/v1/companies/${id}/addresses`,
    data
  );
  return res.data;
}

export async function updateCompanyAddress(
  id: string,
  addressId: string,
  data: UpdateAddressInput
): Promise<CompanyAddress> {
  const res = await apiClient.put<CompanyAddress>(
    `/api/v1/companies/${id}/addresses/${addressId}`,
    data
  );
  return res.data;
}

export async function deleteCompanyAddress(
  id: string,
  addressId: string
): Promise<void> {
  await apiClient.delete(`/api/v1/companies/${id}/addresses/${addressId}`);
}
