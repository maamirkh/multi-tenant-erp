/**
 * Installments module API client.
 *
 * Provides typed functions for every Installments module endpoint
 * (specs/010-installments/contracts/installments-api.yaml). All requests
 * are scoped to a company_id (tenant isolation). Types are hand-mirrored
 * from the backend Pydantic schemas (backend/modules/installments/schemas/*),
 * matching `frontend/src/lib/api/crm.ts`'s exact convention.
 *
 * Idempotency-protected commands (activate/collections/reverse/settlement
 * execute/reschedule/cancel/default/writeoff, plan.md §20) use
 * `apiClient.postWithHeaders()` to attach a client-generated
 * `Idempotency-Key` header — no other module needed this before
 * Installments.
 *
 * Spec ref: specs/010-installments/plan.md §23; contracts/installments-api.yaml.
 */

import { apiClient } from './client';
import type { PaginatedData, StandardResponse } from './types';

function installmentsBase(companyId: string): string {
  return `/api/v1/companies/${companyId}/installments`;
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') qs.set(key, String(value));
  });
  const query = qs.toString();
  return query ? `?${query}` : '';
}

/** Generates a fresh client-side idempotency key for one protected command
 * invocation (plan.md §20) — a new key per user-initiated action. */
export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type InstallmentContractStatus =
  | 'DRAFT'
  | 'PENDING_APPROVAL'
  | 'APPROVED'
  | 'ACTIVE'
  | 'DEFAULTED'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'WRITTEN_OFF';

export interface InstallmentConfigurationRead {
  id: string;
  company_id: string;
  branch_id: string | null;
  allowed_frequencies: string[];
  min_term: number;
  max_term: number;
  min_down_payment_pct: string | null;
  min_down_payment_amount: string | null;
  max_financed_amount: string | null;
  rounding_policy: string;
  grace_period_days: number;
  late_charge_policy: Record<string, unknown> | null;
  early_settlement_policy: Record<string, unknown> | null;
  approval_threshold_amount: string | null;
  backdating_allowed: boolean;
  backdating_max_days: number | null;
  cancellation_policy: Record<string, unknown> | null;
  default_policy: Record<string, unknown> | null;
  writeoff_requires_permission: boolean;
  cure_enabled: boolean;
  eligibility_rules: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface InstallmentConfigurationUpsert {
  branch_id?: string | null;
  allowed_frequencies: string[];
  min_term: number;
  max_term: number;
  min_down_payment_pct?: string | null;
  min_down_payment_amount?: string | null;
  max_financed_amount?: string | null;
  rounding_policy?: string;
  grace_period_days?: number;
  late_charge_policy?: Record<string, unknown> | null;
  early_settlement_policy?: Record<string, unknown> | null;
  approval_threshold_amount?: string | null;
  backdating_allowed?: boolean;
  backdating_max_days?: number | null;
  cancellation_policy?: Record<string, unknown> | null;
  default_policy?: Record<string, unknown> | null;
  writeoff_requires_permission?: boolean;
  cure_enabled?: boolean;
  eligibility_rules?: Record<string, unknown> | null;
}

export interface InstallmentPlanTemplateRead {
  id: string;
  company_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  frequency: string;
  installment_count: number;
  down_payment_rule: Record<string, unknown>;
  markup_rule: Record<string, unknown> | null;
  grace_period_days: number | null;
  late_charge_policy: Record<string, unknown> | null;
  early_settlement_rule: Record<string, unknown> | null;
  applicable_product_ids: string[] | null;
  requires_approval: boolean;
  created_at: string;
  updated_at: string;
}

export interface InstallmentPlanTemplateCreate {
  name: string;
  description?: string | null;
  is_active?: boolean;
  frequency: string;
  installment_count: number;
  down_payment_rule: Record<string, unknown>;
  markup_rule?: Record<string, unknown> | null;
  grace_period_days?: number | null;
  late_charge_policy?: Record<string, unknown> | null;
  early_settlement_rule?: Record<string, unknown> | null;
  applicable_product_ids?: string[] | null;
  requires_approval?: boolean;
}

export type InstallmentPlanTemplateUpdate = Partial<InstallmentPlanTemplateCreate>;

export interface InstallmentQuoteRequest {
  sales_invoice_id: string;
  down_payment_amount: string;
  installment_count: number;
  frequency: string;
  first_due_date: string;
  markup_amount?: string;
  branch_id?: string | null;
}

export interface InstallmentQuotePreviewRead {
  sales_invoice_id: string;
  invoice_amount: string;
  eligible_amount: string;
  down_payment_amount: string;
  financed_principal: string;
  markup_amount: string;
  contractual_total: string;
  installment_count: number;
  frequency: string;
  first_due_date: string;
  per_installment_amounts: string[];
  final_installment_amount: string;
  expected_completion_date: string;
  currency_code: string;
}

export interface InstallmentContractCreate {
  sales_invoice_id: string;
  down_payment_amount: string;
  installment_count: number;
  frequency: string;
  first_due_date: string;
  maturity_date: string;
  markup_amount?: string;
  plan_template_id?: string | null;
  branch_id?: string | null;
  contract_date?: string | null;
}

export interface InstallmentContractRead {
  id: string;
  company_id: string;
  contract_number: string;
  branch_id: string | null;
  customer_id: string;
  sales_invoice_id: string;
  plan_template_id: string | null;
  contract_date: string;
  principal_amount: string;
  down_payment_amount: string;
  markup_amount: string;
  contractual_total: string;
  installment_count: number;
  frequency: string;
  first_due_date: string;
  maturity_date: string;
  currency_code: string;
  status: InstallmentContractStatus;
  terms_snapshot: Record<string, unknown>;
  active_schedule_version_id: string | null;
  submitted_by: string | null;
  submitted_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  activated_at: string | null;
  closed_at: string | null;
  defaulted_at: string | null;
  cancelled_at: string | null;
  written_off_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface InstallmentContractSummary {
  id: string;
  contract_number: string;
  customer_id: string;
  sales_invoice_id: string;
  status: InstallmentContractStatus;
  contractual_total: string;
  currency_code: string;
  created_at: string;
}

export interface InstallmentScheduleLineRead {
  sequence: number;
  due_date: string;
  scheduled_amount: string;
  waived_at: string | null;
  voided_at: string | null;
}

export interface InstallmentScheduleRead {
  contract_id: string;
  version_number: number;
  status: string;
  generated_at: string;
  lines: InstallmentScheduleLineRead[];
}

export interface InstallmentCollectionCreate {
  amount: string;
  payment_method: string;
  bank_account_id?: string | null;
  cash_account_id?: string | null;
}

export interface InstallmentCollectionResultRead {
  contract_id: string;
  amount: string | null;
  accounting_payment_id: string | null;
  collection_id: string | null;
  contract_status: string | null;
  status: string;
}

export interface InstallmentCollectionReverseRequest {
  reason: string;
}

export interface InstallmentSettlementQuoteRequest {
  as_of_date?: string | null;
}

export interface InstallmentSettlementQuoteRead {
  contract_id: string;
  as_of_date: string;
  schedule_outstanding: string;
  late_charge_outstanding: string;
  settlement_amount: string;
  currency_code: string;
  early_settlement_policy: Record<string, unknown> | null;
}

export interface InstallmentSettlementExecuteRequest {
  quoted_amount: string;
  quoted_as_of_date: string;
  payment_method: string;
  bank_account_id?: string | null;
  cash_account_id?: string | null;
}

export interface InstallmentRescheduleRequest {
  first_due_date: string;
  frequency?: string | null;
  principal_amount?: string | null;
  markup_amount?: string | null;
  installment_count?: number | null;
  reason: string;
  requested_by: string;
}

export interface InstallmentCancelRequest {
  reason: string;
  payment_id?: string | null;
}

export interface InstallmentDefaultRequest {
  reason: string;
}

export interface InstallmentCureRequest {
  reason?: string | null;
}

export interface InstallmentWriteoffRequest {
  reason: string;
}

export interface EligibilityResultRead {
  sales_invoice_id: string;
  customer_id: string;
  currency_code: string;
  outstanding_amount: string;
}

export type InstallmentReportType =
  | 'contract-register'
  | 'collection'
  | 'due'
  | 'overdue'
  | 'aging'
  | 'settlement'
  | 'default-writeoff'
  | 'plan-performance';

export type InstallmentReportRow = Record<string, unknown>;

export interface InstallmentDashboard {
  active_contract_count: number;
  outstanding_amount: string;
  due_today_amount: string;
  due_this_month_amount: string;
  collected_today_amount: string;
  collected_this_month_amount: string;
  overdue_amount: string;
  overdue_count: number;
  collection_rate: string;
  aging_distribution: Record<string, string>;
  defaulted_balance: string;
  written_off_balance: string;
  upcoming_receivables_amount: string;
}

export interface InstallmentAgreementView {
  document_type: string;
  contract_id: string;
  contract_number: string;
  customer_id: string;
  status: string;
  contract_date: string;
  contractual_total: string;
  principal_amount: string;
  down_payment_amount: string;
  markup_amount: string;
  installment_count: number;
  frequency: string;
  first_due_date: string;
  maturity_date: string;
  currency_code: string;
  terms_snapshot: Record<string, unknown>;
}

export interface InstallmentScheduleDocumentLine {
  sequence: number;
  due_date: string;
  scheduled_amount: string;
  allocated_amount: string;
  waived_at: string | null;
  voided_at: string | null;
}

export interface InstallmentScheduleDocument {
  document_type: string;
  contract_id: string;
  contract_number: string;
  version_number: number;
  generated_at: string | null;
  lines: InstallmentScheduleDocumentLine[];
}

export interface InstallmentCustomerStatementContract {
  contract_id: string;
  contract_number: string;
  status: string;
  contractual_total: string;
  schedule_outstanding: string | null;
}

export interface InstallmentCustomerStatement {
  document_type: string;
  customer_id: string;
  contracts: InstallmentCustomerStatementContract[];
}

export interface InstallmentsStatusRead {
  enabled: boolean;
}

export interface InstallmentsMyPermissions {
  permissions: string[];
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

export async function getInstallmentConfiguration(companyId: string, branchId?: string) {
  const query = buildQuery({ branch_id: branchId });
  return apiClient.get<InstallmentConfigurationRead>(
    `${installmentsBase(companyId)}/config${query}`
  );
}

export async function upsertInstallmentConfiguration(
  companyId: string,
  data: InstallmentConfigurationUpsert
) {
  return apiClient.put<InstallmentConfigurationRead>(
    `${installmentsBase(companyId)}/config`,
    data
  );
}

// ---------------------------------------------------------------------------
// Plans / Templates
// ---------------------------------------------------------------------------

export async function listPlanTemplates(companyId: string, page = 1, pageSize = 20) {
  const query = buildQuery({ page, page_size: pageSize });
  return apiClient.get<PaginatedData<InstallmentPlanTemplateRead>>(
    `${installmentsBase(companyId)}/plans${query}`
  );
}

export async function createPlanTemplate(
  companyId: string,
  data: InstallmentPlanTemplateCreate
) {
  return apiClient.post<InstallmentPlanTemplateRead>(
    `${installmentsBase(companyId)}/plans`,
    data
  );
}

export async function updatePlanTemplate(
  companyId: string,
  planId: string,
  data: InstallmentPlanTemplateUpdate
) {
  return apiClient.patch<InstallmentPlanTemplateRead>(
    `${installmentsBase(companyId)}/plans/${planId}`,
    data
  );
}

export async function deactivatePlanTemplate(companyId: string, planId: string) {
  return apiClient.post<InstallmentPlanTemplateRead>(
    `${installmentsBase(companyId)}/plans/${planId}/deactivate`,
    {}
  );
}

// ---------------------------------------------------------------------------
// Quote / Preview
// ---------------------------------------------------------------------------

export async function previewInstallmentQuote(
  companyId: string,
  data: InstallmentQuoteRequest
) {
  return apiClient.post<InstallmentQuotePreviewRead>(
    `${installmentsBase(companyId)}/quotes`,
    data
  );
}

// ---------------------------------------------------------------------------
// Contracts
// ---------------------------------------------------------------------------

export async function listInstallmentContracts(
  companyId: string,
  page = 1,
  pageSize = 20,
  status?: InstallmentContractStatus
) {
  const query = buildQuery({ page, page_size: pageSize, status });
  return apiClient.get<PaginatedData<InstallmentContractSummary>>(
    `${installmentsBase(companyId)}/contracts${query}`
  );
}

export async function getInstallmentContract(companyId: string, contractId: string) {
  return apiClient.get<InstallmentContractRead>(
    `${installmentsBase(companyId)}/contracts/${contractId}`
  );
}

export interface InstallmentAuditLogRead {
  id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor_user_id: string | null;
  occurred_at: string;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  reason: string | null;
}

export async function getInstallmentContractAuditHistory(companyId: string, contractId: string) {
  return apiClient.get<InstallmentAuditLogRead[]>(
    `${installmentsBase(companyId)}/contracts/${contractId}/audit`
  );
}

export async function createInstallmentContract(
  companyId: string,
  data: InstallmentContractCreate
) {
  return apiClient.post<InstallmentContractRead>(
    `${installmentsBase(companyId)}/contracts`,
    data
  );
}

export async function submitInstallmentContract(companyId: string, contractId: string) {
  return apiClient.post<InstallmentContractRead>(
    `${installmentsBase(companyId)}/contracts/${contractId}/submit`,
    {}
  );
}

export async function approveInstallmentContract(companyId: string, contractId: string) {
  return apiClient.post<InstallmentContractRead>(
    `${installmentsBase(companyId)}/contracts/${contractId}/approve`,
    {}
  );
}

export async function rejectInstallmentContract(
  companyId: string,
  contractId: string,
  reason: string
) {
  return apiClient.post<InstallmentContractRead>(
    `${installmentsBase(companyId)}/contracts/${contractId}/reject`,
    { reason }
  );
}

// ---------------------------------------------------------------------------
// Activation / Collections / Reversals (idempotency-protected)
// ---------------------------------------------------------------------------

export async function activateInstallmentContract(
  companyId: string,
  contractId: string,
  idempotencyKey: string
) {
  return apiClient.postWithHeaders<InstallmentContractRead>(
    `${installmentsBase(companyId)}/contracts/${contractId}/activate`,
    {},
    { 'Idempotency-Key': idempotencyKey }
  );
}

export async function recordInstallmentCollection(
  companyId: string,
  contractId: string,
  data: InstallmentCollectionCreate,
  idempotencyKey: string
) {
  return apiClient.postWithHeaders<InstallmentCollectionResultRead>(
    `${installmentsBase(companyId)}/contracts/${contractId}/collections`,
    data,
    { 'Idempotency-Key': idempotencyKey }
  );
}

export async function reverseInstallmentCollection(
  companyId: string,
  collectionId: string,
  reason: string,
  idempotencyKey: string
) {
  return apiClient.postWithHeaders<InstallmentCollectionResultRead>(
    `${installmentsBase(companyId)}/collections/${collectionId}/reverse`,
    { reason } satisfies InstallmentCollectionReverseRequest,
    { 'Idempotency-Key': idempotencyKey }
  );
}

// ---------------------------------------------------------------------------
// Settlement
// ---------------------------------------------------------------------------

export async function generateInstallmentSettlementQuote(
  companyId: string,
  contractId: string,
  asOfDate?: string
) {
  return apiClient.post<InstallmentSettlementQuoteRead>(
    `${installmentsBase(companyId)}/contracts/${contractId}/settlement/quote`,
    { as_of_date: asOfDate ?? null } satisfies InstallmentSettlementQuoteRequest
  );
}

export async function executeInstallmentSettlement(
  companyId: string,
  contractId: string,
  data: InstallmentSettlementExecuteRequest,
  idempotencyKey: string
) {
  return apiClient.postWithHeaders<InstallmentContractRead>(
    `${installmentsBase(companyId)}/contracts/${contractId}/settlement/execute`,
    data,
    { 'Idempotency-Key': idempotencyKey }
  );
}

// ---------------------------------------------------------------------------
// Advanced Lifecycle
// ---------------------------------------------------------------------------

export async function rescheduleInstallmentContract(
  companyId: string,
  contractId: string,
  data: InstallmentRescheduleRequest,
  idempotencyKey: string
) {
  return apiClient.postWithHeaders<InstallmentContractRead>(
    `${installmentsBase(companyId)}/contracts/${contractId}/reschedule`,
    data,
    { 'Idempotency-Key': idempotencyKey }
  );
}

export async function cancelInstallmentContract(
  companyId: string,
  contractId: string,
  data: InstallmentCancelRequest,
  idempotencyKey: string
) {
  return apiClient.postWithHeaders<InstallmentContractRead>(
    `${installmentsBase(companyId)}/contracts/${contractId}/cancel`,
    data,
    { 'Idempotency-Key': idempotencyKey }
  );
}

export async function defaultInstallmentContract(
  companyId: string,
  contractId: string,
  reason: string,
  idempotencyKey: string
) {
  return apiClient.postWithHeaders<InstallmentContractRead>(
    `${installmentsBase(companyId)}/contracts/${contractId}/default`,
    { reason } satisfies InstallmentDefaultRequest,
    { 'Idempotency-Key': idempotencyKey }
  );
}

export async function cureInstallmentContract(
  companyId: string,
  contractId: string,
  reason?: string
) {
  return apiClient.post<InstallmentContractRead>(
    `${installmentsBase(companyId)}/contracts/${contractId}/cure`,
    { reason: reason ?? null } satisfies InstallmentCureRequest
  );
}

export async function writeoffInstallmentContract(
  companyId: string,
  contractId: string,
  reason: string,
  idempotencyKey: string
) {
  return apiClient.postWithHeaders<InstallmentContractRead>(
    `${installmentsBase(companyId)}/contracts/${contractId}/writeoff`,
    { reason } satisfies InstallmentWriteoffRequest,
    { 'Idempotency-Key': idempotencyKey }
  );
}

// ---------------------------------------------------------------------------
// Schedules
// ---------------------------------------------------------------------------

export async function getActiveInstallmentSchedule(companyId: string, contractId: string) {
  return apiClient.get<InstallmentScheduleRead>(
    `${installmentsBase(companyId)}/contracts/${contractId}/schedule`
  );
}

export async function getInstallmentScheduleVersion(
  companyId: string,
  contractId: string,
  versionNumber: number
) {
  return apiClient.get<InstallmentScheduleRead>(
    `${installmentsBase(companyId)}/contracts/${contractId}/schedule/versions/${versionNumber}`
  );
}

// ---------------------------------------------------------------------------
// Eligibility
// ---------------------------------------------------------------------------

export async function checkInstallmentEligibility(companyId: string, salesInvoiceId: string) {
  const query = buildQuery({ sales_invoice_id: salesInvoiceId });
  return apiClient.get<EligibilityResultRead>(`${installmentsBase(companyId)}/eligibility${query}`);
}

// ---------------------------------------------------------------------------
// Reports / Dashboard
// ---------------------------------------------------------------------------

export async function getInstallmentReport(
  companyId: string,
  reportType: InstallmentReportType,
  page = 1,
  pageSize = 20,
  statusFilter?: string
) {
  const query = buildQuery({ page, page_size: pageSize, status: statusFilter });
  return apiClient.get<PaginatedData<InstallmentReportRow>>(
    `${installmentsBase(companyId)}/reports/${reportType}${query}`
  );
}

export async function getInstallmentDashboard(companyId: string) {
  return apiClient.get<InstallmentDashboard>(`${installmentsBase(companyId)}/dashboard`);
}

// ---------------------------------------------------------------------------
// Documents / Statements
// ---------------------------------------------------------------------------

export async function getInstallmentAgreementDocument(companyId: string, contractId: string) {
  return apiClient.get<InstallmentAgreementView>(
    `${installmentsBase(companyId)}/contracts/${contractId}/documents/agreement`
  );
}

export async function getInstallmentScheduleDocument(companyId: string, contractId: string) {
  return apiClient.get<InstallmentScheduleDocument>(
    `${installmentsBase(companyId)}/contracts/${contractId}/documents/schedule`
  );
}

export async function getInstallmentSettlementQuoteDocument(
  companyId: string,
  contractId: string
) {
  return apiClient.get<InstallmentSettlementQuoteRead>(
    `${installmentsBase(companyId)}/contracts/${contractId}/documents/settlement-quote`
  );
}

export async function getInstallmentCustomerStatement(companyId: string, customerId: string) {
  return apiClient.get<InstallmentCustomerStatement>(
    `${installmentsBase(companyId)}/customers/${customerId}/statement`
  );
}

// ---------------------------------------------------------------------------
// Module administration & current-user permissions
// ---------------------------------------------------------------------------

export async function getInstallmentsStatus(companyId: string) {
  return apiClient.get<InstallmentsStatusRead>(`${installmentsBase(companyId)}/status`);
}

export async function enableInstallments(companyId: string) {
  return apiClient.post<InstallmentsStatusRead>(`${installmentsBase(companyId)}/enable`, {});
}

export async function disableInstallments(companyId: string) {
  return apiClient.post<InstallmentsStatusRead>(`${installmentsBase(companyId)}/disable`, {});
}

export async function getMyInstallmentsPermissions(companyId: string) {
  return apiClient.get<InstallmentsMyPermissions>(`${installmentsBase(companyId)}/my-permissions`);
}

export type { StandardResponse };
