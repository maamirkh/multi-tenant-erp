/**
 * CRM module API client.
 *
 * Provides typed functions for every CRM module endpoint (spec.md §38).
 * All requests are scoped to a company_id (tenant isolation).
 *
 * Built on the shared `apiClient` singleton (`@/lib/api/client`), matching
 * `frontend/src/lib/api/accounting.ts`'s exact pattern — Bearer token
 * injection and 401/token-refresh retry are handled automatically, no
 * per-call token parameter is needed.
 *
 * Spec ref: specs/009-crm/spec.md §38; plan.md §23.
 */

import { apiClient } from './client';
import type { PaginatedData, StandardResponse } from './types';

function crmBase(companyId: string): string {
  return `/api/v1/companies/${companyId}/crm`;
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') qs.set(key, String(value));
  });
  const query = qs.toString();
  return query ? `?${query}` : '';
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type LeadStatus =
  | 'NEW'
  | 'CONTACTED'
  | 'QUALIFIED'
  | 'UNQUALIFIED'
  | 'CONVERTED'
  | 'LOST';

export type OpportunityStatus = 'OPEN' | 'WON' | 'LOST';

export type ActivityType = 'CALL' | 'EMAIL' | 'MEETING' | 'TASK' | 'NOTE' | 'FOLLOW_UP';
export type ActivityStatus = 'PLANNED' | 'COMPLETED' | 'CANCELLED';
export type ActivityPriority = 'LOW' | 'MEDIUM' | 'HIGH';

export interface LeadSourceRead {
  id: string;
  company_id: string;
  code: string;
  name: string;
  is_active: boolean;
}

export interface LeadRead {
  id: string;
  company_id: string;
  first_name: string | null;
  last_name: string | null;
  lead_company_name: string | null;
  email: string | null;
  phone: string | null;
  mobile: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  country_code: string | null;
  source_id: string | null;
  status: LeadStatus;
  score: number | null;
  owner_id: string | null;
  notes: string | null;
  last_contact_date: string | null;
  next_follow_up_date: string | null;
  qualification_notes: string | null;
  disqualification_reason: string | null;
  converted_customer_id: string | null;
  converted_opportunity_id: string | null;
  converted_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ConversionResult {
  lead_id: string;
  customer_id: string;
  opportunity_id: string;
  customer_matched: boolean;
}

export interface PipelineRead {
  id: string;
  company_id: string;
  name: string;
  is_default: boolean;
  is_active: boolean;
}

export interface PipelineStageRead {
  id: string;
  company_id: string;
  pipeline_id: string;
  name: string;
  sequence: number;
  probability: number;
  is_won_stage: boolean;
  is_lost_stage: boolean;
  is_active: boolean;
}

export interface OpportunityRead {
  id: string;
  company_id: string;
  name: string;
  customer_id: string;
  owner_id: string;
  pipeline_id: string;
  stage_id: string;
  value: string;
  currency_code: string;
  probability: number;
  weighted_value: string;
  expected_close_date: string | null;
  source_lead_id: string | null;
  description: string | null;
  status: OpportunityStatus;
  lost_reason: string | null;
  won_at: string | null;
  lost_at: string | null;
  quotation_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ActivityRead {
  id: string;
  company_id: string;
  activity_type: ActivityType;
  subject: string;
  description: string | null;
  status: ActivityStatus;
  priority: ActivityPriority;
  due_date: string | null;
  completed_at: string | null;
  assigned_to: string;
  lead_id: string | null;
  customer_id: string | null;
  opportunity_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CustomerSummary {
  id: string;
  customer_code: string;
  legal_name: string;
  trading_name: string | null;
  status: string;
  currency_code: string;
}

export interface SalesHistorySummary {
  quotation_count: number;
  order_count: number;
  invoice_count: number;
  delivery_count: number;
}

export interface FinancialSummary {
  total_outstanding_base: string;
  credit_limit: string;
  credit_status: string;
  as_of_date: string;
  current: string;
  days_1_30: string;
  days_31_60: string;
  days_61_90: string;
  days_91_120: string;
  days_120_plus: string;
}

export interface Customer360 {
  customer: CustomerSummary;
  converted_leads: LeadRead[];
  opportunities: OpportunityRead[];
  activities: ActivityRead[];
  sales_history: SalesHistorySummary;
  financial_summary: FinancialSummary;
  last_interaction: string | null;
  next_follow_up: string | null;
}

export interface PipelineReport {
  value_by_stage: { stage_id: string; value: string }[];
  value_by_owner: { owner_id: string; value: string }[];
  value_by_source: { source_id: string | null; value: string }[];
  won_value: string;
  lost_value: string;
  win_rate: string | null;
  avg_deal_size: string | null;
  avg_sales_cycle_days: string | null;
  date_from: string | null;
  date_to: string | null;
}

export interface LeadReport {
  total_count: number;
  count_by_status: Record<string, number>;
  count_by_source: Record<string, number>;
  conversion_rate: string | null;
  qualified_to_close_rate: string | null;
  date_from: string | null;
  date_to: string | null;
}

export interface ActivityReport {
  completed_count: number;
  completed_by_type: Record<string, number>;
  overdue_count: number;
  overdue_by_owner: Record<string, number>;
  date_from: string | null;
  date_to: string | null;
}

export interface CrmDashboard {
  open_pipeline_value: string;
  weighted_pipeline_value: string;
  lead_count: number;
  conversion_rate: string | null;
  win_rate: string | null;
  overdue_follow_up_count: number;
  activities_completed: number;
  period_from: string;
  period_to: string;
}

// ---------------------------------------------------------------------------
// Lead Sources
// ---------------------------------------------------------------------------

export async function listLeadSources(companyId: string, isActive?: boolean) {
  const query = buildQuery({ is_active: isActive === undefined ? undefined : String(isActive) });
  return apiClient.get<PaginatedData<LeadSourceRead>>(
    `${crmBase(companyId)}/lead-sources${query}`
  );
}

export async function createLeadSource(
  companyId: string,
  data: { code: string; name: string; is_active?: boolean }
): Promise<StandardResponse<LeadSourceRead>> {
  return apiClient.post(`${crmBase(companyId)}/lead-sources`, data);
}

export async function updateLeadSource(
  companyId: string,
  sourceId: string,
  data: Partial<{ name: string; is_active: boolean }>
): Promise<StandardResponse<LeadSourceRead>> {
  return apiClient.patch(`${crmBase(companyId)}/lead-sources/${sourceId}`, data);
}

// ---------------------------------------------------------------------------
// Leads
// ---------------------------------------------------------------------------

export interface LeadListFilters {
  status?: string;
  source_id?: string;
  owner_id?: string;
  created_from?: string;
  created_to?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

export async function listLeads(companyId: string, filters: LeadListFilters = {}) {
  const query = buildQuery({ ...filters });
  return apiClient.get<PaginatedData<LeadRead>>(`${crmBase(companyId)}/leads${query}`);
}

export async function getLead(companyId: string, leadId: string) {
  return apiClient.get<LeadRead>(`${crmBase(companyId)}/leads/${leadId}`);
}

export async function createLead(companyId: string, data: Record<string, unknown>) {
  return apiClient.post<LeadRead>(`${crmBase(companyId)}/leads`, data);
}

export async function updateLead(
  companyId: string,
  leadId: string,
  data: Record<string, unknown>
) {
  return apiClient.patch<LeadRead>(`${crmBase(companyId)}/leads/${leadId}`, data);
}

export async function deleteLead(companyId: string, leadId: string) {
  return apiClient.delete<null>(`${crmBase(companyId)}/leads/${leadId}`);
}

export async function assignLead(companyId: string, leadId: string, ownerId: string) {
  return apiClient.post<LeadRead>(`${crmBase(companyId)}/leads/${leadId}/assign`, {
    owner_id: ownerId,
  });
}

export async function convertLead(companyId: string, leadId: string) {
  return apiClient.post<ConversionResult>(`${crmBase(companyId)}/leads/${leadId}/convert`, {});
}

// ---------------------------------------------------------------------------
// Pipelines & Stages
// ---------------------------------------------------------------------------

export async function listPipelines(companyId: string) {
  return apiClient.get<PipelineRead[]>(`${crmBase(companyId)}/pipelines`);
}

export async function createPipeline(
  companyId: string,
  data: { name: string; is_default?: boolean; is_active?: boolean }
) {
  return apiClient.post<PipelineRead>(`${crmBase(companyId)}/pipelines`, data);
}

export async function updatePipeline(
  companyId: string,
  pipelineId: string,
  data: Partial<{ name: string; is_default: boolean; is_active: boolean }>
) {
  return apiClient.patch<PipelineRead>(`${crmBase(companyId)}/pipelines/${pipelineId}`, data);
}

export async function listPipelineStages(companyId: string, pipelineId: string) {
  return apiClient.get<PipelineStageRead[]>(
    `${crmBase(companyId)}/pipelines/${pipelineId}/stages`
  );
}

export async function createPipelineStage(
  companyId: string,
  pipelineId: string,
  data: {
    name: string;
    sequence: number;
    probability: number;
    is_won_stage?: boolean;
    is_lost_stage?: boolean;
    is_active?: boolean;
  }
) {
  return apiClient.post<PipelineStageRead>(
    `${crmBase(companyId)}/pipelines/${pipelineId}/stages`,
    data
  );
}

export async function updatePipelineStage(
  companyId: string,
  stageId: string,
  data: Partial<{
    name: string;
    sequence: number;
    probability: number;
    is_won_stage: boolean;
    is_lost_stage: boolean;
    is_active: boolean;
  }>
) {
  return apiClient.patch<PipelineStageRead>(
    `${crmBase(companyId)}/pipeline-stages/${stageId}`,
    data
  );
}

// ---------------------------------------------------------------------------
// Opportunities
// ---------------------------------------------------------------------------

export interface OpportunityListFilters {
  status?: string;
  stage_id?: string;
  owner_id?: string;
  customer_id?: string;
  expected_close_from?: string;
  expected_close_to?: string;
  min_value?: string;
  max_value?: string;
  page?: number;
  page_size?: number;
}

export async function listOpportunities(
  companyId: string,
  filters: OpportunityListFilters = {}
) {
  const query = buildQuery({ ...filters });
  return apiClient.get<PaginatedData<OpportunityRead>>(
    `${crmBase(companyId)}/opportunities${query}`
  );
}

export async function getOpportunity(companyId: string, opportunityId: string) {
  return apiClient.get<OpportunityRead>(`${crmBase(companyId)}/opportunities/${opportunityId}`);
}

export async function createOpportunity(companyId: string, data: Record<string, unknown>) {
  return apiClient.post<OpportunityRead>(`${crmBase(companyId)}/opportunities`, data);
}

export async function updateOpportunity(
  companyId: string,
  opportunityId: string,
  data: Record<string, unknown>
) {
  return apiClient.patch<OpportunityRead>(
    `${crmBase(companyId)}/opportunities/${opportunityId}`,
    data
  );
}

export async function deleteOpportunity(companyId: string, opportunityId: string) {
  return apiClient.delete<null>(`${crmBase(companyId)}/opportunities/${opportunityId}`);
}

export async function assignOpportunity(
  companyId: string,
  opportunityId: string,
  ownerId: string
) {
  return apiClient.post<OpportunityRead>(
    `${crmBase(companyId)}/opportunities/${opportunityId}/assign`,
    { owner_id: ownerId }
  );
}

export async function changeOpportunityStage(
  companyId: string,
  opportunityId: string,
  stageId: string,
  probability?: number
) {
  return apiClient.post<OpportunityRead>(
    `${crmBase(companyId)}/opportunities/${opportunityId}/stage`,
    { stage_id: stageId, ...(probability === undefined ? {} : { probability }) }
  );
}

export async function winOpportunity(companyId: string, opportunityId: string) {
  return apiClient.post<OpportunityRead>(
    `${crmBase(companyId)}/opportunities/${opportunityId}/win`,
    {}
  );
}

export async function loseOpportunity(
  companyId: string,
  opportunityId: string,
  lostReason: string
) {
  return apiClient.post<OpportunityRead>(
    `${crmBase(companyId)}/opportunities/${opportunityId}/lose`,
    { lost_reason: lostReason }
  );
}

// ---------------------------------------------------------------------------
// Activities
// ---------------------------------------------------------------------------

export interface ActivityListFilters {
  activity_type?: string;
  status?: string;
  assigned_to?: string;
  lead_id?: string;
  customer_id?: string;
  opportunity_id?: string;
  due_from?: string;
  due_to?: string;
  page?: number;
  page_size?: number;
}

export async function listActivities(companyId: string, filters: ActivityListFilters = {}) {
  const query = buildQuery({ ...filters });
  return apiClient.get<PaginatedData<ActivityRead>>(
    `${crmBase(companyId)}/activities${query}`
  );
}

export async function getActivity(companyId: string, activityId: string) {
  return apiClient.get<ActivityRead>(`${crmBase(companyId)}/activities/${activityId}`);
}

export async function createActivity(companyId: string, data: Record<string, unknown>) {
  return apiClient.post<ActivityRead>(`${crmBase(companyId)}/activities`, data);
}

export async function updateActivity(
  companyId: string,
  activityId: string,
  data: Record<string, unknown>
) {
  return apiClient.patch<ActivityRead>(`${crmBase(companyId)}/activities/${activityId}`, data);
}

export async function deleteActivity(companyId: string, activityId: string) {
  return apiClient.delete<null>(`${crmBase(companyId)}/activities/${activityId}`);
}

export async function completeActivity(companyId: string, activityId: string) {
  return apiClient.post<ActivityRead>(
    `${crmBase(companyId)}/activities/${activityId}/complete`,
    {}
  );
}

// ---------------------------------------------------------------------------
// Customer 360
// ---------------------------------------------------------------------------

export async function getCustomer360(companyId: string, customerId: string) {
  return apiClient.get<Customer360>(`${crmBase(companyId)}/customers/${customerId}/360`);
}

// ---------------------------------------------------------------------------
// Dashboard & Reports
// ---------------------------------------------------------------------------

export async function getCrmDashboard(companyId: string) {
  return apiClient.get<CrmDashboard>(`${crmBase(companyId)}/dashboard`);
}

export async function getPipelineReport(
  companyId: string,
  dateFrom?: string,
  dateTo?: string
) {
  const query = buildQuery({ date_from: dateFrom, date_to: dateTo });
  return apiClient.get<PipelineReport>(`${crmBase(companyId)}/reports/pipeline${query}`);
}

export async function getLeadReport(companyId: string, dateFrom?: string, dateTo?: string) {
  const query = buildQuery({ date_from: dateFrom, date_to: dateTo });
  return apiClient.get<LeadReport>(`${crmBase(companyId)}/reports/leads${query}`);
}

export async function getActivityReport(
  companyId: string,
  dateFrom?: string,
  dateTo?: string
) {
  const query = buildQuery({ date_from: dateFrom, date_to: dateTo });
  return apiClient.get<ActivityReport>(`${crmBase(companyId)}/reports/activities${query}`);
}
