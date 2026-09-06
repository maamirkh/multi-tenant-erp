/**
 * Platform Administration domain API — typed fetch functions wrapping
 * `platformApiClient` (T178-T181, ADR-11).
 *
 * Mirrors `lib/api/companies.ts`'s existing convention: each function
 * unwraps the `StandardResponse<T>`/`PaginatedResponse<T>` envelope and
 * returns the inner payload so Platform pages (Phase 15) work with plain
 * domain types. Every path/permission/request-response shape here is
 * taken directly from `contracts/platform-admin-v1.yaml` and the backend
 * Pydantic schemas under `backend/modules/platform_admin/schemas/` — no
 * invented CRUD (plan.md §10 API Contract Lock).
 *
 * Every function in this file uses `platformApiClient`, never the
 * tenant `apiClient` — Platform pages must never import `lib/api/client`
 * directly (T179/ADR-11 isolation).
 */

import { platformApiClient, platformBase } from '@/lib/api/platform';
import type { PaginatedData } from '@/lib/api/types';

// ── Dashboard (T171-T173) ───────────────────────────────────────────────

export interface DashboardWidget {
  state: 'populated' | 'empty' | 'unavailable';
  data: unknown;
}

export interface DashboardResponse {
  widgets: Record<string, DashboardWidget>;
}

export async function getDashboard(): Promise<DashboardResponse> {
  const res = await platformApiClient.get<DashboardResponse>(`${platformBase()}/dashboard`);
  return res.data;
}

// ── Tenants / tenant directory (T167-T169) ──────────────────────────────

export interface TenantSummary {
  id: string;
  legal_name: string;
  slug: string;
  status: string;
  country: string | null;
  email: string;
  created_at: string;
}

export interface PlanSummary {
  id: string;
  code: string;
  name: string;
  status: string;
}

export interface CapabilityEntitlement {
  capability_key: string;
  available: boolean;
  reason: string;
}

export interface QuotaStatus {
  quota_key: string;
  state: 'ok' | 'approaching' | 'reached' | 'unlimited' | 'unavailable';
  limit: string | null;
  current_usage: string | null;
  enforcement_style: string | null;
}

export interface SubscriptionRecord {
  id: string;
  company_id: string;
  plan_id: string;
  status: string;
  effective_date: string;
  ended_at: string | null;
  actor_id: string;
  reason: string | null;
  created_at: string;
}

export interface AuditEventSummary {
  id: string;
  action: string;
  actor_platform_administrator_id: string | null;
  target_type: string;
  reason: string | null;
  created_at: string;
}

export interface LifecycleEvent {
  action: string;
  actor_platform_administrator_id: string | null;
  reason: string | null;
  created_at: string;
}

export interface TenantDetail {
  id: string;
  legal_name: string;
  slug: string;
  status: string;
  pre_suspension_status: string | null;
  access_invalidated_at: string | null;
  email: string;
  country: string | null;
  created_at: string;
  plan: PlanSummary | null;
  subscription: SubscriptionRecord | null;
  entitlements: CapabilityEntitlement[];
  quotas: QuotaStatus[];
  user_count: number;
  lifecycle_history: LifecycleEvent[];
  recent_audit_events: AuditEventSummary[];
}

export interface ListTenantsParams {
  status?: string | undefined;
  country?: string | undefined;
  search?: string | undefined;
  include_deleted?: boolean | undefined;
  sort_by?: string | undefined;
  sort_order?: string | undefined;
  page?: number | undefined;
  page_size?: number | undefined;
}

export async function listTenants(
  params: ListTenantsParams
): Promise<PaginatedData<TenantSummary>> {
  const q = new URLSearchParams();
  if (params.status) q.set('status', params.status);
  if (params.country) q.set('country', params.country);
  if (params.search) q.set('search', params.search);
  if (params.include_deleted !== undefined)
    q.set('include_deleted', String(params.include_deleted));
  if (params.sort_by) q.set('sort_by', params.sort_by);
  if (params.sort_order) q.set('sort_order', params.sort_order);
  q.set('page', String(params.page ?? 1));
  q.set('page_size', String(params.page_size ?? 20));
  const res = await platformApiClient.get<PaginatedData<TenantSummary>>(
    `${platformBase()}/tenants?${q.toString()}`
  );
  return res.data;
}

export async function getTenantDetail(companyId: string): Promise<TenantDetail> {
  const res = await platformApiClient.get<TenantDetail>(
    `${platformBase()}/tenants/${companyId}`
  );
  return res.data;
}

export interface TenantLifecycleHistory {
  company_id: string;
  events: LifecycleEvent[];
}

export async function getTenantLifecycleHistory(
  companyId: string
): Promise<TenantLifecycleHistory> {
  const res = await platformApiClient.get<TenantLifecycleHistory>(
    `${platformBase()}/tenants/${companyId}/lifecycle-history`
  );
  return res.data;
}

export interface TenantLifecycleResult {
  id: string;
  status: string;
  pre_suspension_status: string | null;
  access_invalidated_at: string | null;
}

export async function suspendTenant(
  companyId: string,
  reason: string
): Promise<TenantLifecycleResult> {
  const res = await platformApiClient.post<TenantLifecycleResult>(
    `${platformBase()}/tenants/${companyId}/suspend`,
    { reason }
  );
  return res.data;
}

export async function reactivateTenant(
  companyId: string,
  reason: string
): Promise<TenantLifecycleResult> {
  const res = await platformApiClient.post<TenantLifecycleResult>(
    `${platformBase()}/tenants/${companyId}/reactivate`,
    { reason }
  );
  return res.data;
}

// ── Plans (T114) ─────────────────────────────────────────────────────────

export interface Plan {
  id: string;
  code: string;
  name: string;
  status: string;
  description: string | null;
  is_commercially_available: boolean;
  billing_cycle_metadata: Record<string, unknown> | null;
  pricing_metadata: Record<string, unknown> | null;
  capability_map: Record<string, boolean>;
  created_at: string;
  updated_at: string;
}

export async function listPlans(params: {
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedData<Plan>> {
  const q = new URLSearchParams();
  if (params.status) q.set('status', params.status);
  q.set('page', String(params.page ?? 1));
  q.set('page_size', String(params.page_size ?? 20));
  const res = await platformApiClient.get<PaginatedData<Plan>>(
    `${platformBase()}/plans?${q.toString()}`
  );
  return res.data;
}

export interface CreatePlanInput {
  code: string;
  name: string;
  description?: string | null;
  capability_map?: Record<string, boolean> | null;
  reason?: string | null;
}

export async function createPlan(input: CreatePlanInput): Promise<Plan> {
  const res = await platformApiClient.post<Plan>(`${platformBase()}/plans`, input);
  return res.data;
}

export interface UpdatePlanInput {
  action?: 'update' | 'publish' | 'retire';
  name?: string;
  description?: string | null;
  is_commercially_available?: boolean;
  capability_map?: Record<string, boolean>;
  reason?: string | null;
}

export async function updatePlan(planId: string, input: UpdatePlanInput): Promise<Plan> {
  const res = await platformApiClient.patch<Plan>(`${platformBase()}/plans/${planId}`, input);
  return res.data;
}

// ── Subscriptions (T114) ────────────────────────────────────────────────

export interface SubscriptionHistory {
  current: SubscriptionRecord | null;
  history: SubscriptionRecord[];
}

export async function getTenantSubscription(companyId: string): Promise<SubscriptionHistory> {
  const res = await platformApiClient.get<SubscriptionHistory>(
    `${platformBase()}/tenants/${companyId}/subscription`
  );
  return res.data;
}

export interface AssignSubscriptionInput {
  plan_id: string;
  effective_date: string;
  end_date?: string | null;
  reason?: string | null;
  acknowledged?: boolean;
}

export async function assignSubscription(
  companyId: string,
  input: AssignSubscriptionInput
): Promise<SubscriptionRecord> {
  const res = await platformApiClient.post<SubscriptionRecord>(
    `${platformBase()}/tenants/${companyId}/subscription`,
    input
  );
  return res.data;
}

// ── Entitlements (T123) ─────────────────────────────────────────────────

export interface TenantEntitlements {
  company_id: string;
  entitlements: CapabilityEntitlement[];
}

export async function getTenantEntitlements(companyId: string): Promise<TenantEntitlements> {
  const res = await platformApiClient.get<TenantEntitlements>(
    `${platformBase()}/tenants/${companyId}/entitlements`
  );
  return res.data;
}

export interface EntitlementOverride {
  id: string;
  company_id: string;
  capability_key: string;
  reason: string;
  actor_id: string;
  granted_at: string;
  expires_at: string | null;
  revoked_at: string | null;
  is_active: boolean;
}

export async function grantEntitlementOverride(
  companyId: string,
  input: { capability_key: string; reason: string; expires_at?: string | null }
): Promise<EntitlementOverride> {
  const res = await platformApiClient.post<EntitlementOverride>(
    `${platformBase()}/tenants/${companyId}/entitlement-overrides`,
    input
  );
  return res.data;
}

export async function revokeEntitlementOverride(
  companyId: string,
  overrideId: string
): Promise<void> {
  await platformApiClient.delete(
    `${platformBase()}/tenants/${companyId}/entitlement-overrides/${overrideId}`
  );
}

// ── Quotas (T149/T157) ──────────────────────────────────────────────────

export interface TenantQuotas {
  company_id: string;
  quotas: QuotaStatus[];
}

export async function getTenantQuotas(companyId: string): Promise<TenantQuotas> {
  const res = await platformApiClient.get<TenantQuotas>(
    `${platformBase()}/tenants/${companyId}/quotas`
  );
  return res.data;
}

export interface QuotaOverride {
  id: string;
  company_id: string;
  quota_key: string;
  override_limit: string | null;
  reason: string;
  actor_id: string;
  granted_at: string;
  expires_at: string | null;
  revoked_at: string | null;
  is_active: boolean;
}

export async function grantQuotaOverride(
  companyId: string,
  input: {
    quota_key: string;
    override_limit?: string | null;
    reason: string;
    expires_at?: string | null;
  }
): Promise<QuotaOverride> {
  const res = await platformApiClient.post<QuotaOverride>(
    `${platformBase()}/tenants/${companyId}/quota-overrides`,
    input
  );
  return res.data;
}

// ── Administrators (T068) ───────────────────────────────────────────────

export interface PlatformAdministrator {
  id: string;
  user_id: string;
  is_active: boolean;
  last_login_at: string | null;
  deactivated_at: string | null;
  deactivated_by: string | null;
  created_at: string;
  updated_at: string;
}

export async function listAdministrators(params: {
  page?: number;
  page_size?: number;
}): Promise<PaginatedData<PlatformAdministrator>> {
  const q = new URLSearchParams();
  q.set('page', String(params.page ?? 1));
  q.set('page_size', String(params.page_size ?? 20));
  const res = await platformApiClient.get<PaginatedData<PlatformAdministrator>>(
    `${platformBase()}/administrators?${q.toString()}`
  );
  return res.data;
}

export async function createAdministrator(userId: string): Promise<PlatformAdministrator> {
  const res = await platformApiClient.post<PlatformAdministrator>(
    `${platformBase()}/administrators`,
    { user_id: userId }
  );
  return res.data;
}

export async function updateAdministrator(
  adminId: string,
  input: { is_active: boolean; reason?: string | null }
): Promise<PlatformAdministrator> {
  const res = await platformApiClient.patch<PlatformAdministrator>(
    `${platformBase()}/administrators/${adminId}`,
    input
  );
  return res.data;
}

// ── RBAC / Roles (T069) ─────────────────────────────────────────────────

export interface PlatformRole {
  id: string;
  code: string;
  name: string;
  description: string | null;
  permission_codes: string[];
  created_at: string;
  updated_at: string;
}

export async function listRoles(params: {
  page?: number;
  page_size?: number;
}): Promise<PaginatedData<PlatformRole>> {
  const q = new URLSearchParams();
  q.set('page', String(params.page ?? 1));
  q.set('page_size', String(params.page_size ?? 20));
  const res = await platformApiClient.get<PaginatedData<PlatformRole>>(
    `${platformBase()}/roles?${q.toString()}`
  );
  return res.data;
}

export async function createOrUpdateRole(input: {
  code: string;
  name: string;
  description?: string | null;
  permission_codes: string[];
  reason?: string | null;
}): Promise<PlatformRole> {
  const res = await platformApiClient.post<PlatformRole>(`${platformBase()}/roles`, input);
  return res.data;
}

export interface RoleAssignment {
  id: string;
  platform_administrator_id: string;
  role_id: string;
  assigned_by: string | null;
  assigned_at: string;
}

export async function assignRole(
  adminId: string,
  roleId: string,
  reason?: string | null
): Promise<RoleAssignment> {
  const res = await platformApiClient.post<RoleAssignment>(
    `${platformBase()}/administrators/${adminId}/roles`,
    { role_id: roleId, reason: reason ?? null }
  );
  return res.data;
}

// ── Support access (T158-T162) ──────────────────────────────────────────

export interface SupportAccessGrant {
  id: string;
  platform_administrator_id: string;
  company_id: string;
  reason: string;
  started_at: string;
  expires_at: string;
  ended_at: string | null;
  ended_by: string | null;
  status: string;
}

export async function initiateSupportAccess(
  companyId: string,
  reason: string
): Promise<SupportAccessGrant> {
  const res = await platformApiClient.post<SupportAccessGrant>(
    `${platformBase()}/tenants/${companyId}/support-access`,
    { reason }
  );
  return res.data;
}

export async function terminateSupportAccess(grantId: string): Promise<void> {
  await platformApiClient.delete(`${platformBase()}/support-access/${grantId}`);
}

export async function listSupportAccessGrants(params: {
  page?: number;
  page_size?: number;
}): Promise<PaginatedData<SupportAccessGrant>> {
  const q = new URLSearchParams();
  q.set('page', String(params.page ?? 1));
  q.set('page_size', String(params.page_size ?? 20));
  const res = await platformApiClient.get<PaginatedData<SupportAccessGrant>>(
    `${platformBase()}/support-access?${q.toString()}`
  );
  return res.data;
}

// ── Audit (T170) ─────────────────────────────────────────────────────────

export interface AuditQueryParams {
  actor_platform_administrator_id?: string | undefined;
  company_id?: string | undefined;
  action?: string | undefined;
  target_type?: string | undefined;
  target_id?: string | undefined;
  created_after?: string | undefined;
  created_before?: string | undefined;
  outcome?: 'success' | 'denied' | undefined;
  page?: number | undefined;
  page_size?: number | undefined;
}

export async function listAuditEvents(
  params: AuditQueryParams
): Promise<PaginatedData<AuditEventSummary>> {
  const q = new URLSearchParams();
  if (params.actor_platform_administrator_id)
    q.set('actor_platform_administrator_id', params.actor_platform_administrator_id);
  if (params.company_id) q.set('company_id', params.company_id);
  if (params.action) q.set('action', params.action);
  if (params.target_type) q.set('target_type', params.target_type);
  if (params.target_id) q.set('target_id', params.target_id);
  if (params.created_after) q.set('created_after', params.created_after);
  if (params.created_before) q.set('created_before', params.created_before);
  if (params.outcome) q.set('outcome', params.outcome);
  q.set('page', String(params.page ?? 1));
  q.set('page_size', String(params.page_size ?? 50));
  const res = await platformApiClient.get<PaginatedData<AuditEventSummary>>(
    `${platformBase()}/audit?${q.toString()}`
  );
  return res.data;
}

// ── Usage (T150-T152) ────────────────────────────────────────────────────

export interface UsageRecord {
  id: string;
  company_id: string;
  metric_key: string;
  quantity: string;
  period_start: string;
  period_end: string;
  source: string;
  recorded_at: string;
}

export interface TenantUsage {
  company_id: string;
  records: UsageRecord[];
}

export async function getTenantUsage(companyId: string): Promise<TenantUsage> {
  const res = await platformApiClient.get<TenantUsage>(
    `${platformBase()}/tenants/${companyId}/usage`
  );
  return res.data;
}

// ── AI credits (T154/T155) ──────────────────────────────────────────────

export interface AiCreditLedgerEntry {
  id: string;
  company_id: string;
  delta: string;
  reason: string | null;
  actor_platform_administrator_id: string | null;
  provider: string | null;
  model: string | null;
  occurred_at: string;
}

export interface TenantAiCredits {
  company_id: string;
  status: 'not_yet_active' | 'active';
  balance: string;
  entries: AiCreditLedgerEntry[];
}

export async function getTenantAiCredits(companyId: string): Promise<TenantAiCredits> {
  const res = await platformApiClient.get<TenantAiCredits>(
    `${platformBase()}/tenants/${companyId}/ai-credits`
  );
  return res.data;
}

export async function adjustAiCredits(
  companyId: string,
  input: { delta: string; reason: string }
): Promise<AiCreditLedgerEntry> {
  const res = await platformApiClient.post<AiCreditLedgerEntry>(
    `${platformBase()}/tenants/${companyId}/ai-credits`,
    input
  );
  return res.data;
}

// ── Health (T174) ────────────────────────────────────────────────────────

export interface PlatformHealth {
  status: string;
  checks: Record<string, string>;
  outbox_pending: number;
  outbox_published: number;
  relay: Record<string, unknown>;
}

export async function getPlatformHealth(): Promise<PlatformHealth> {
  const res = await platformApiClient.get<PlatformHealth>(`${platformBase()}/health`);
  return res.data;
}
