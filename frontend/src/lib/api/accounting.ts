/**
 * Accounting module API client.
 *
 * Provides typed functions for all accounting module endpoints.
 * All requests are scoped to a company_id (tenant isolation).
 *
 * Built on the shared `apiClient` singleton (`@/lib/api/client`), which
 * handles Bearer token injection and 401/token-refresh retry automatically.
 *
 * Spec ref: specs/008-accounting-finance/spec.md
 */

import { apiClient } from './client';
import { getAccessToken } from '@/lib/auth/tokenStorage';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AccountingHealthRead {
  status: string;
  module: string;
  version: string;
}

export interface AccountingFeatureFlagRead {
  flag_key: string;
  label: string;
  description: string;
  is_enabled: boolean;
  is_overridden: boolean;
  default_enabled: boolean;
}

export interface AccountingFeatureFlagUpdate {
  is_enabled: boolean;
  description?: string | null;
}

export interface AccountingConfigurationRead {
  id: string;
  company_id: string;
  base_currency_code: string;
  journal_approval_threshold: string | null;
  payment_approval_threshold: string | null;
  credit_warning_threshold_pct: string;
  cheque_stale_days: number;
  default_ar_account_id: string | null;
  default_ap_account_id: string | null;
  default_retained_earnings_account_id: string | null;
  default_exchange_gain_account_id: string | null;
  default_exchange_loss_account_id: string | null;
  default_bad_debt_account_id: string | null;
  default_revenue_account_id: string | null;
  default_expense_account_id: string | null;
  default_tax_liability_account_id: string | null;
  default_input_tax_account_id: string | null;
}

export type AccountingConfigurationUpdate = Partial<
  Omit<AccountingConfigurationRead, 'id' | 'company_id'>
>;

export interface CurrencyRead {
  id: string;
  iso_code: string;
  name: string;
  symbol: string;
  decimal_places: number;
  is_active: boolean;
}

export interface CurrencyCreate {
  iso_code: string;
  name: string;
  symbol: string;
  decimal_places?: number;
}

export interface ExchangeRateRead {
  id: string;
  company_id: string;
  from_currency_code: string;
  to_currency_code: string;
  rate_date: string;
  rate: string;
  rate_type: string;
}

export interface ExchangeRateCreate {
  from_currency_code: string;
  to_currency_code: string;
  rate_date: string;
  rate: string;
  rate_type?: 'SPOT' | 'AVERAGE' | 'CLOSING' | 'HISTORICAL';
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export async function getAccountingHealth(companyId: string) {
  return apiClient.get<AccountingHealthRead>(
    `/api/v1/companies/${companyId}/accounting/health`
  );
}

// ---------------------------------------------------------------------------
// Feature Flags
// ---------------------------------------------------------------------------

export async function getAccountingFeatureFlags(companyId: string) {
  return apiClient.get<AccountingFeatureFlagRead[]>(
    `/api/v1/companies/${companyId}/accounting/feature-flags`
  );
}

export async function updateAccountingFeatureFlag(
  companyId: string,
  flagKey: string,
  data: AccountingFeatureFlagUpdate
) {
  return apiClient.put<AccountingFeatureFlagRead>(
    `/api/v1/companies/${companyId}/accounting/feature-flags/${flagKey}`,
    data
  );
}

// ---------------------------------------------------------------------------
// Accounting Configuration
// ---------------------------------------------------------------------------

export async function getAccountingConfiguration(companyId: string) {
  return apiClient.get<AccountingConfigurationRead>(
    `/api/v1/companies/${companyId}/accounting/configuration`
  );
}

export async function updateAccountingConfiguration(
  companyId: string,
  data: AccountingConfigurationUpdate
) {
  return apiClient.put<AccountingConfigurationRead>(
    `/api/v1/companies/${companyId}/accounting/configuration`,
    data
  );
}

// ---------------------------------------------------------------------------
// Currencies
// ---------------------------------------------------------------------------

export async function getCurrencies(companyId: string, activeOnly = false) {
  const query = activeOnly ? '?active_only=true' : '';
  return apiClient.get<CurrencyRead[]>(
    `/api/v1/companies/${companyId}/accounting/currencies${query}`
  );
}

export async function createCurrency(companyId: string, data: CurrencyCreate) {
  return apiClient.post<CurrencyRead>(
    `/api/v1/companies/${companyId}/accounting/currencies`,
    data
  );
}

// ---------------------------------------------------------------------------
// Exchange Rates
// ---------------------------------------------------------------------------

export async function getExchangeRates(companyId: string) {
  return apiClient.get<ExchangeRateRead[]>(
    `/api/v1/companies/${companyId}/accounting/exchange-rates`
  );
}

export async function createExchangeRate(companyId: string, data: ExchangeRateCreate) {
  return apiClient.post<ExchangeRateRead>(
    `/api/v1/companies/${companyId}/accounting/exchange-rates`,
    data
  );
}

// ---------------------------------------------------------------------------
// Chart of Accounts — Types
// ---------------------------------------------------------------------------

export type AccountType = 'ASSET' | 'LIABILITY' | 'EQUITY' | 'REVENUE' | 'EXPENSE';

export interface AccountResponse {
  id: string;
  company_id: string;
  account_code: string;
  account_name: string;
  account_type: AccountType;
  account_group_id: string | null;
  parent_account_id: string | null;
  is_leaf: boolean;
  currency_code: string | null;
  requires_cost_center: boolean;
  is_bank_account: boolean;
  is_cash_account: boolean;
  is_active: boolean;
  tax_category: string | null;
  notes: string | null;
}

export interface AccountTreeNode {
  id: string;
  account_code: string;
  account_name: string;
  account_type: AccountType;
  is_leaf: boolean;
  is_active: boolean;
  children: AccountTreeNode[];
}

export interface AccountCreateRequest {
  account_code: string;
  account_name: string;
  account_type: AccountType;
  account_group_id?: string | null;
  parent_account_id?: string | null;
  is_leaf?: boolean;
  currency_code?: string | null;
  requires_cost_center?: boolean;
  is_bank_account?: boolean;
  is_cash_account?: boolean;
  tax_category?: string | null;
  notes?: string | null;
}

export type AccountUpdateRequest = Partial<Omit<AccountCreateRequest, 'account_type'>>;

export interface AccountGroupRead {
  id: string;
  company_id: string;
  group_code: string;
  group_name: string;
  account_type: AccountType;
  parent_group_id: string | null;
  display_order: number;
  is_active: boolean;
}

export interface AccountGroupCreate {
  group_code: string;
  group_name: string;
  account_type: AccountType;
  parent_group_id?: string | null;
  display_order?: number;
}

export interface COAImportResultRow {
  row: number;
  success: boolean;
  account_code: string;
  error: string | null;
}

export interface COATemplateInfo {
  key: string;
  label: string;
}

export const SYSTEM_ACCOUNT_ROLES = [
  { role: 'default_ar_account_id', label: 'Accounts Receivable' },
  { role: 'default_ap_account_id', label: 'Accounts Payable' },
  { role: 'default_retained_earnings_account_id', label: 'Retained Earnings' },
  { role: 'default_exchange_gain_account_id', label: 'Exchange Gain' },
  { role: 'default_exchange_loss_account_id', label: 'Exchange Loss' },
  { role: 'default_bad_debt_account_id', label: 'Bad Debt Expense' },
  { role: 'default_revenue_account_id', label: 'Default Revenue' },
  { role: 'default_expense_account_id', label: 'Default Expense' },
  { role: 'default_tax_liability_account_id', label: 'Output Tax Liability' },
  { role: 'default_input_tax_account_id', label: 'Input Tax Recoverable' },
] as const;

// ---------------------------------------------------------------------------
// Chart of Accounts — Accounts
// ---------------------------------------------------------------------------

export async function getAccounts(companyId: string, tree = false) {
  const query = tree ? '?tree=true' : '';
  return apiClient.get<AccountResponse[] | AccountTreeNode[]>(
    `/api/v1/companies/${companyId}/accounting/accounts${query}`
  );
}

export async function getAccount(companyId: string, accountId: string) {
  return apiClient.get<AccountResponse>(
    `/api/v1/companies/${companyId}/accounting/accounts/${accountId}`
  );
}

export async function createAccount(companyId: string, data: AccountCreateRequest) {
  return apiClient.post<AccountResponse>(
    `/api/v1/companies/${companyId}/accounting/accounts`,
    data
  );
}

export async function updateAccount(
  companyId: string,
  accountId: string,
  data: AccountUpdateRequest
) {
  return apiClient.put<AccountResponse>(
    `/api/v1/companies/${companyId}/accounting/accounts/${accountId}`,
    data
  );
}

export async function deactivateAccount(companyId: string, accountId: string) {
  return apiClient.delete<AccountResponse>(
    `/api/v1/companies/${companyId}/accounting/accounts/${accountId}`
  );
}

export async function activateAccount(companyId: string, accountId: string) {
  return apiClient.post<AccountResponse>(
    `/api/v1/companies/${companyId}/accounting/accounts/${accountId}/activate`,
    {}
  );
}

export async function bulkImportAccounts(companyId: string, rows: Record<string, unknown>[]) {
  return apiClient.post<COAImportResultRow[]>(
    `/api/v1/companies/${companyId}/accounting/accounts/bulk-import`,
    rows
  );
}

export async function exportAccounts(companyId: string) {
  return apiClient.get<AccountResponse[]>(
    `/api/v1/companies/${companyId}/accounting/accounts/export`
  );
}

// ---------------------------------------------------------------------------
// Chart of Accounts — Account Groups
// ---------------------------------------------------------------------------

export async function getAccountGroups(companyId: string) {
  return apiClient.get<AccountGroupRead[]>(
    `/api/v1/companies/${companyId}/accounting/account-groups`
  );
}

export async function createAccountGroup(companyId: string, data: AccountGroupCreate) {
  return apiClient.post<AccountGroupRead>(
    `/api/v1/companies/${companyId}/accounting/account-groups`,
    data
  );
}

// ---------------------------------------------------------------------------
// System Accounts
// ---------------------------------------------------------------------------

export async function getSystemAccounts(companyId: string) {
  return apiClient.get<AccountingConfigurationRead>(
    `/api/v1/companies/${companyId}/accounting/system-accounts`
  );
}

export async function setSystemAccount(companyId: string, role: string, accountId: string) {
  return apiClient.put<AccountingConfigurationRead>(
    `/api/v1/companies/${companyId}/accounting/system-accounts`,
    { role, account_id: accountId }
  );
}

// ---------------------------------------------------------------------------
// COA Industry Templates
// ---------------------------------------------------------------------------

export async function getCOATemplates(companyId: string) {
  return apiClient.get<COATemplateInfo[]>(
    `/api/v1/companies/${companyId}/accounting/coa-templates`
  );
}

export async function applyCOATemplate(companyId: string, templateKey: string) {
  return apiClient.post<AccountResponse[]>(
    `/api/v1/companies/${companyId}/accounting/coa-templates/apply`,
    { template_key: templateKey }
  );
}

// ---------------------------------------------------------------------------
// Fiscal Calendar — Types
// ---------------------------------------------------------------------------

export type FiscalYearStatus = 'SETUP' | 'OPEN' | 'CLOSED';
export type FiscalPeriodStatus = 'OPEN' | 'LOCKED' | 'CLOSED';

export interface FiscalYearResponse {
  id: string;
  company_id: string;
  fiscal_year_name: string;
  start_date: string;
  end_date: string;
  status: FiscalYearStatus;
  base_currency_code: string;
  is_current: boolean;
}

export interface FiscalYearCreateRequest {
  fiscal_year_name: string;
  start_date: string;
  end_date: string;
  base_currency_code: string;
  is_current?: boolean;
}

export interface FiscalYearUpdateRequest {
  fiscal_year_name?: string;
  is_current?: boolean;
}

export interface FiscalPeriodResponse {
  id: string;
  company_id: string;
  fiscal_year_id: string;
  period_number: number;
  period_name: string;
  start_date: string;
  end_date: string;
  status: FiscalPeriodStatus;
  locked_at: string | null;
  locked_by_user_id: string | null;
  lock_reason: string | null;
  closed_at: string | null;
  closed_by_user_id: string | null;
}

export interface OpeningBalanceLine {
  account_id: string;
  debit_amount?: string;
  credit_amount?: string;
  currency_code?: string | null;
  notes?: string | null;
}

export interface OpeningBalanceResponse {
  id: string;
  company_id: string;
  fiscal_year_id: string;
  account_id: string;
  debit_amount: string;
  credit_amount: string;
  currency_code: string | null;
  notes: string | null;
}

// ---------------------------------------------------------------------------
// Fiscal Calendar — Fiscal Years
// ---------------------------------------------------------------------------

export async function getFiscalYears(companyId: string) {
  return apiClient.get<FiscalYearResponse[]>(
    `/api/v1/companies/${companyId}/accounting/fiscal-years`
  );
}

export async function getFiscalYear(companyId: string, fiscalYearId: string) {
  return apiClient.get<FiscalYearResponse>(
    `/api/v1/companies/${companyId}/accounting/fiscal-years/${fiscalYearId}`
  );
}

export async function createFiscalYear(
  companyId: string,
  data: FiscalYearCreateRequest
) {
  return apiClient.post<FiscalYearResponse>(
    `/api/v1/companies/${companyId}/accounting/fiscal-years`,
    data
  );
}

export async function updateFiscalYear(
  companyId: string,
  fiscalYearId: string,
  data: FiscalYearUpdateRequest
) {
  return apiClient.put<FiscalYearResponse>(
    `/api/v1/companies/${companyId}/accounting/fiscal-years/${fiscalYearId}`,
    data
  );
}

// ---------------------------------------------------------------------------
// Fiscal Calendar — Periods
// ---------------------------------------------------------------------------

export async function getFiscalPeriods(companyId: string, fiscalYearId: string) {
  return apiClient.get<FiscalPeriodResponse[]>(
    `/api/v1/companies/${companyId}/accounting/fiscal-years/${fiscalYearId}/periods`
  );
}

export async function lockFiscalPeriod(
  companyId: string,
  fiscalYearId: string,
  periodId: string,
  lockReason: string
) {
  return apiClient.post<FiscalPeriodResponse>(
    `/api/v1/companies/${companyId}/accounting/fiscal-years/${fiscalYearId}/periods/${periodId}/lock`,
    { lock_reason: lockReason }
  );
}

export async function unlockFiscalPeriod(
  companyId: string,
  fiscalYearId: string,
  periodId: string,
  reason: string
) {
  return apiClient.post<FiscalPeriodResponse>(
    `/api/v1/companies/${companyId}/accounting/fiscal-years/${fiscalYearId}/periods/${periodId}/unlock`,
    { reason }
  );
}

// ---------------------------------------------------------------------------
// Fiscal Calendar — Opening Balances
// ---------------------------------------------------------------------------

export async function getOpeningBalances(companyId: string, fiscalYearId: string) {
  return apiClient.get<OpeningBalanceResponse[]>(
    `/api/v1/companies/${companyId}/accounting/fiscal-years/${fiscalYearId}/opening-balances`
  );
}

export async function setupOpeningBalances(
  companyId: string,
  fiscalYearId: string,
  lines: OpeningBalanceLine[]
) {
  return apiClient.post<OpeningBalanceResponse[]>(
    `/api/v1/companies/${companyId}/accounting/fiscal-years/${fiscalYearId}/opening-balances`,
    { lines }
  );
}

// ---------------------------------------------------------------------------
// Fiscal Calendar — Year-End Close
// ---------------------------------------------------------------------------

export async function executeYearEndClose(companyId: string, fiscalYearId: string) {
  return apiClient.post<FiscalYearResponse>(
    `/api/v1/companies/${companyId}/accounting/fiscal-years/${fiscalYearId}/year-end-close`,
    {}
  );
}

// ---------------------------------------------------------------------------
// General Ledger — Types (Phase 4)
// ---------------------------------------------------------------------------

export type JournalEntryStatus =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'APPROVED'
  | 'POSTED'
  | 'REJECTED'
  | 'REVERSED';

export type JournalType =
  | 'STANDARD'
  | 'ADJUSTING'
  | 'REVERSING'
  | 'RECURRING_INSTANCE'
  | 'OPENING_BALANCE'
  | 'CLOSING'
  | 'AUTOMATED';

export type PostingSource =
  | 'MANUAL'
  | 'SALES'
  | 'PURCHASE'
  | 'INVENTORY'
  | 'BANK'
  | 'CASH'
  | 'PAYMENT'
  | 'RECURRING'
  | 'SYSTEM';

export interface PostingLineRequest {
  account_id: string;
  debit_amount?: string;
  credit_amount?: string;
  currency_code?: string | null;
  exchange_rate?: string | null;
  cost_center_id?: string | null;
  department_id?: string | null;
  project_id?: string | null;
  description?: string | null;
  reference?: string | null;
}

export interface PostingRequest {
  journal_type: JournalType;
  posting_source?: PostingSource;
  posting_date: string;
  currency_code?: string | null;
  exchange_rate?: string;
  reference?: string | null;
  description?: string | null;
  notes?: string | null;
  source_document_type?: string | null;
  source_document_id?: string | null;
  lines: PostingLineRequest[];
}

export interface PostingResult {
  journal_entry_id: string;
  journal_number: string;
  posted_at: string;
}

export interface JournalLineResponse {
  id: string;
  line_number: number;
  account_id: string;
  account_code: string;
  debit_amount: string;
  credit_amount: string;
  debit_amount_base: string;
  credit_amount_base: string;
  currency_code: string;
  exchange_rate: string;
  cost_center_id: string | null;
  department_id: string | null;
  project_id: string | null;
  description: string | null;
  reference: string | null;
}

export interface JournalEntryResponse {
  id: string;
  company_id: string;
  journal_number: string | null;
  journal_type: JournalType;
  posting_source: PostingSource;
  posting_date: string;
  fiscal_period_id: string | null;
  fiscal_year_id: string | null;
  reference: string | null;
  description: string | null;
  notes: string | null;
  status: JournalEntryStatus;
  reversal_of_journal_id: string | null;
  is_reversal: boolean;
  posted_at: string | null;
  posted_by_user_id: string | null;
  source_document_type: string | null;
  source_document_id: string | null;
  currency_code: string;
  exchange_rate: string;
  total_debit_base: string;
  total_credit_base: string;
  is_balanced: boolean | null;
}

export interface JournalEntryDetailResponse extends JournalEntryResponse {
  lines: JournalLineResponse[];
}

export interface GLReportRow {
  journal_entry_id: string;
  journal_number: string | null;
  posting_date: string;
  account_id: string;
  account_code: string;
  line_number: number;
  debit_amount: string;
  credit_amount: string;
  description: string | null;
  reference: string | null;
  source_document_type: string | null;
  source_document_id: string | null;
  cost_center_id: string | null;
}

// ---------------------------------------------------------------------------
// General Ledger — Journals
// ---------------------------------------------------------------------------

export interface JournalListFilters {
  start_date?: string | undefined;
  end_date?: string | undefined;
  account_id?: string | undefined;
  fiscal_period_id?: string | undefined;
  posting_source?: string | undefined;
  reference?: string | undefined;
  status?: string | undefined;
  cost_center_id?: string | undefined;
  skip?: number | undefined;
  limit?: number | undefined;
}

export async function getJournals(companyId: string, filters: JournalListFilters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value));
  });
  const query = params.toString() ? `?${params.toString()}` : '';
  return apiClient.get<JournalEntryResponse[]>(
    `/api/v1/companies/${companyId}/accounting/journals${query}`
  );
}

export async function getJournal(companyId: string, journalId: string) {
  return apiClient.get<JournalEntryDetailResponse>(
    `/api/v1/companies/${companyId}/accounting/journals/${journalId}`
  );
}

export async function createJournal(companyId: string, data: PostingRequest) {
  return apiClient.post<JournalEntryDetailResponse>(
    `/api/v1/companies/${companyId}/accounting/journals`,
    data
  );
}

export async function submitJournal(companyId: string, journalId: string) {
  return apiClient.post<JournalEntryResponse>(
    `/api/v1/companies/${companyId}/accounting/journals/${journalId}/submit`,
    {}
  );
}

export async function approveJournal(companyId: string, journalId: string) {
  return apiClient.post<JournalEntryResponse>(
    `/api/v1/companies/${companyId}/accounting/journals/${journalId}/approve`,
    {}
  );
}

export async function rejectJournal(
  companyId: string,
  journalId: string,
  rejectionReason: string
) {
  return apiClient.post<JournalEntryResponse>(
    `/api/v1/companies/${companyId}/accounting/journals/${journalId}/reject`,
    { rejection_reason: rejectionReason }
  );
}

export async function postJournal(companyId: string, journalId: string) {
  return apiClient.post<PostingResult>(
    `/api/v1/companies/${companyId}/accounting/journals/${journalId}/post`,
    {}
  );
}

export async function reverseJournal(
  companyId: string,
  journalId: string,
  reason?: string
) {
  return apiClient.post<JournalEntryDetailResponse>(
    `/api/v1/companies/${companyId}/accounting/journals/${journalId}/reverse`,
    { reason: reason ?? null }
  );
}

// ---------------------------------------------------------------------------
// General Ledger — Report
// ---------------------------------------------------------------------------

export interface GLReportFilters {
  account_id?: string | undefined;
  cost_center_id?: string | undefined;
  fiscal_period_id?: string | undefined;
  start_date?: string | undefined;
  end_date?: string | undefined;
  skip?: number | undefined;
  limit?: number | undefined;
}

export async function getGLReport(companyId: string, filters: GLReportFilters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value));
  });
  const query = params.toString() ? `?${params.toString()}` : '';
  return apiClient.get<GLReportRow[]>(
    `/api/v1/companies/${companyId}/accounting/reports/gl${query}`
  );
}

// ---------------------------------------------------------------------------
// Batch Posting — Types + API (Phase 5)
// ---------------------------------------------------------------------------

export async function batchPostJournals(companyId: string, journalEntryIds: string[]) {
  return apiClient.post<{ results: PostingResult[] }>(
    `/api/v1/companies/${companyId}/accounting/journals/batch-post`,
    { journal_entry_ids: journalEntryIds }
  );
}

// ---------------------------------------------------------------------------
// Recurring Journal Templates — Types (Phase 5)
// ---------------------------------------------------------------------------

export type RecurringFrequency = 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'QUARTERLY' | 'ANNUALLY';

export interface RecurringTemplateLineRequest {
  account_id: string;
  debit_amount?: string;
  credit_amount?: string;
  description?: string | null;
  cost_center_id?: string | null;
}

export interface RecurringTemplateLineResponse {
  id: string;
  line_number: number;
  account_id: string;
  debit_amount: string;
  credit_amount: string;
  description: string | null;
  cost_center_id: string | null;
}

export interface RecurringTemplateCreateRequest {
  template_name: string;
  frequency: RecurringFrequency;
  start_date: string;
  end_date?: string | null;
  auto_post?: boolean;
  approval_required?: boolean;
  currency_code?: string | null;
  reference?: string | null;
  description?: string | null;
  lines: RecurringTemplateLineRequest[];
}

export interface RecurringTemplateUpdateRequest {
  template_name?: string;
  end_date?: string | null;
  auto_post?: boolean;
  approval_required?: boolean;
  reference?: string | null;
  description?: string | null;
}

export interface RecurringTemplateResponse {
  id: string;
  company_id: string;
  template_name: string;
  frequency: RecurringFrequency;
  start_date: string;
  end_date: string | null;
  next_run_date: string;
  is_active: boolean;
  auto_post: boolean;
  approval_required: boolean;
  currency_code: string;
  reference: string | null;
  description: string | null;
}

export interface RecurringTemplateDetailResponse extends RecurringTemplateResponse {
  lines: RecurringTemplateLineResponse[];
}

export interface RecurringInstanceResponse {
  id: string;
  template_id: string;
  journal_entry_id: string | null;
  execution_date: string;
  status: 'SUCCESS' | 'FAILED';
  error_message: string | null;
}

// ---------------------------------------------------------------------------
// Recurring Journal Templates — API (Phase 5)
// ---------------------------------------------------------------------------

export async function getRecurringTemplates(companyId: string) {
  return apiClient.get<RecurringTemplateResponse[]>(
    `/api/v1/companies/${companyId}/accounting/recurring-journals`
  );
}

export async function getRecurringTemplate(companyId: string, templateId: string) {
  return apiClient.get<RecurringTemplateDetailResponse>(
    `/api/v1/companies/${companyId}/accounting/recurring-journals/${templateId}`
  );
}

export async function createRecurringTemplate(
  companyId: string,
  data: RecurringTemplateCreateRequest
) {
  return apiClient.post<RecurringTemplateDetailResponse>(
    `/api/v1/companies/${companyId}/accounting/recurring-journals`,
    data
  );
}

export async function updateRecurringTemplate(
  companyId: string,
  templateId: string,
  data: RecurringTemplateUpdateRequest
) {
  return apiClient.put<RecurringTemplateResponse>(
    `/api/v1/companies/${companyId}/accounting/recurring-journals/${templateId}`,
    data
  );
}

export async function activateRecurringTemplate(companyId: string, templateId: string) {
  return apiClient.post<RecurringTemplateResponse>(
    `/api/v1/companies/${companyId}/accounting/recurring-journals/${templateId}/activate`,
    {}
  );
}

export async function deactivateRecurringTemplate(companyId: string, templateId: string) {
  return apiClient.post<RecurringTemplateResponse>(
    `/api/v1/companies/${companyId}/accounting/recurring-journals/${templateId}/deactivate`,
    {}
  );
}

export async function getRecurringTemplateHistory(companyId: string, templateId: string) {
  return apiClient.get<RecurringInstanceResponse[]>(
    `/api/v1/companies/${companyId}/accounting/recurring-journals/${templateId}/history`
  );
}

// ---------------------------------------------------------------------------
// Accounts Receivable (Phase 6)
// ---------------------------------------------------------------------------

export interface CustomerLedgerResponse {
  id: string;
  customer_id: string;
  credit_limit: string;
  credit_status: 'GOOD' | 'WARNING' | 'EXCEEDED' | 'HOLD';
  credit_hold_at: string | null;
  credit_hold_reason: string | null;
  credit_hold_by: string | null;
  total_outstanding_base: string;
  last_payment_date: string | null;
  average_payment_days: string | null;
}

export interface ARTransactionResponse {
  id: string;
  customer_ledger_id: string;
  transaction_type: string;
  transaction_date: string;
  due_date: string | null;
  currency_code: string;
  exchange_rate: string;
  amount_foreign: string;
  amount_base: string;
  outstanding_amount: string;
  status: string;
  source_document_type: string | null;
  source_document_id: string | null;
  journal_entry_id: string | null;
  invoice_number: string | null;
}

export interface ARAgingRow {
  customer_ledger_id: string | null;
  customer_id: string | null;
  current: string;
  days_1_30: string;
  days_31_60: string;
  days_61_90: string;
  days_91_120: string;
  days_120_plus: string;
  total: string;
}

export interface ARAgingReport {
  as_of_date: string;
  rows: ARAgingRow[];
  totals: ARAgingRow;
}

export interface CustomerStatementResponse {
  customer_id: string;
  from_date: string;
  to_date: string;
  opening_balance: string;
  transactions: ARTransactionResponse[];
  closing_balance: string;
}

export async function getCustomerLedger(companyId: string, customerId: string) {
  return apiClient.get<CustomerLedgerResponse>(
    `/api/v1/companies/${companyId}/accounting/ar/customer-ledger/${customerId}`
  );
}

export async function getARAgingReport(companyId: string, asOfDate?: string) {
  const query = asOfDate ? `?as_of_date=${asOfDate}` : '';
  return apiClient.get<ARAgingReport>(
    `/api/v1/companies/${companyId}/accounting/ar/aging${query}`
  );
}

export async function getCustomerStatement(
  companyId: string,
  customerId: string,
  fromDate: string,
  toDate: string
) {
  return apiClient.get<CustomerStatementResponse>(
    `/api/v1/companies/${companyId}/accounting/ar/customer-statement/${customerId}` +
      `?from_date=${fromDate}&to_date=${toDate}`
  );
}

export async function placeCreditHold(companyId: string, customerId: string, reason: string) {
  return apiClient.post<CustomerLedgerResponse>(
    `/api/v1/companies/${companyId}/accounting/ar/customers/${customerId}/credit-hold`,
    { reason }
  );
}

export async function releaseCreditHold(
  companyId: string,
  customerId: string,
  reason?: string
) {
  return apiClient.post<CustomerLedgerResponse>(
    `/api/v1/companies/${companyId}/accounting/ar/customers/${customerId}/credit-hold/release`,
    { reason: reason ?? null }
  );
}

export async function setCreditLimit(
  companyId: string,
  customerId: string,
  creditLimit: string
) {
  return apiClient.post<CustomerLedgerResponse>(
    `/api/v1/companies/${companyId}/accounting/ar/customers/${customerId}/credit-limit`,
    { credit_limit: creditLimit }
  );
}

export async function writeOffARTransaction(
  companyId: string,
  arTransactionId: string,
  reason: string
) {
  return apiClient.post<ARTransactionResponse>(
    `/api/v1/companies/${companyId}/accounting/ar/transactions/${arTransactionId}/write-off`,
    { reason }
  );
}

// ---------------------------------------------------------------------------
// Accounts Payable (Phase 7)
// ---------------------------------------------------------------------------

export interface SupplierLedgerResponse {
  id: string;
  supplier_id: string;
  total_outstanding_base: string;
  last_payment_date: string | null;
}

export interface APTransactionResponse {
  id: string;
  supplier_ledger_id: string;
  transaction_type: string;
  transaction_date: string;
  due_date: string | null;
  currency_code: string;
  exchange_rate: string;
  amount_foreign: string;
  amount_base: string;
  outstanding_amount: string;
  status: string;
  source_document_type: string | null;
  source_document_id: string | null;
  journal_entry_id: string | null;
  bill_number: string | null;
}

export interface APAgingRow {
  supplier_ledger_id: string | null;
  supplier_id: string | null;
  current: string;
  days_1_30: string;
  days_31_60: string;
  days_61_90: string;
  days_91_120: string;
  days_120_plus: string;
  total: string;
}

export interface APAgingReport {
  as_of_date: string;
  rows: APAgingRow[];
  totals: APAgingRow;
}

export interface SupplierStatementResponse {
  supplier_id: string;
  from_date: string;
  to_date: string;
  opening_balance: string;
  transactions: APTransactionResponse[];
  closing_balance: string;
}

export interface ReconciliationItemResponse {
  id: string;
  reconciliation_id: string;
  ap_transaction_id: string | null;
  statement_line_reference: string | null;
  statement_amount: string | null;
  gl_amount: string | null;
  match_status: 'MATCHED' | 'UNMATCHED_GL' | 'UNMATCHED_STATEMENT' | 'DISPUTED';
  difference: string;
}

export interface SupplierStatementReconciliationResponse {
  id: string;
  supplier_id: string;
  statement_date: string;
  statement_total: string;
  status: 'DRAFT' | 'IN_PROGRESS' | 'COMPLETED';
  items: ReconciliationItemResponse[];
}

export interface ReconcileStatementLine {
  reference?: string | null;
  amount: string;
}

export async function getSupplierLedger(companyId: string, supplierId: string) {
  return apiClient.get<SupplierLedgerResponse>(
    `/api/v1/companies/${companyId}/accounting/ap/supplier-ledger/${supplierId}`
  );
}

export async function getAPAgingReport(companyId: string, asOfDate?: string) {
  const query = asOfDate ? `?as_of_date=${asOfDate}` : '';
  return apiClient.get<APAgingReport>(
    `/api/v1/companies/${companyId}/accounting/ap/aging${query}`
  );
}

export async function getSupplierStatement(
  companyId: string,
  supplierId: string,
  fromDate: string,
  toDate: string
) {
  return apiClient.get<SupplierStatementResponse>(
    `/api/v1/companies/${companyId}/accounting/ap/supplier-statement/${supplierId}` +
      `?from_date=${fromDate}&to_date=${toDate}`
  );
}

export async function reconcileSupplierStatement(
  companyId: string,
  supplierId: string,
  statementDate: string,
  statementTotal: string,
  statementLines: ReconcileStatementLine[]
) {
  return apiClient.post<SupplierStatementReconciliationResponse>(
    `/api/v1/companies/${companyId}/accounting/ap/reconcile-statement`,
    {
      supplier_id: supplierId,
      statement_date: statementDate,
      statement_total: statementTotal,
      statement_lines: statementLines,
    }
  );
}

export async function createSupplierBill(
  companyId: string,
  data: {
    supplier_id: string;
    bill_number: string;
    total_amount: string;
    currency_code: string;
    transaction_date: string;
    due_date?: string | null;
  }
) {
  return apiClient.post<APTransactionResponse>(
    `/api/v1/companies/${companyId}/accounting/ap/bills`,
    data
  );
}

// ---------------------------------------------------------------------------
// Banking (Phase 8)
// ---------------------------------------------------------------------------

export interface BankAccountResponse {
  id: string;
  bank_name: string;
  branch_name: string | null;
  account_number: string;
  iban: string | null;
  swift_bic: string | null;
  currency_code: string;
  gl_account_id: string;
  opening_balance: string;
  opening_balance_date: string | null;
  current_gl_balance: string;
  is_active: boolean;
}

export interface BankTransactionResponse {
  id: string;
  bank_account_id: string;
  transaction_date: string;
  transaction_type: 'RECEIPT' | 'PAYMENT' | 'TRANSFER' | 'BANK_CHARGE';
  amount: string;
  reference: string | null;
  description: string | null;
  journal_entry_id: string | null;
  is_reconciled: boolean;
}

export interface BankStatementLineResponse {
  id: string;
  bank_account_id: string;
  statement_date: string;
  value_date: string | null;
  amount: string;
  reference: string | null;
  description: string | null;
  transaction_type: string | null;
  is_matched: boolean;
}

export interface BankReconciliationResponse {
  id: string;
  bank_account_id: string;
  statement_date: string;
  statement_closing_balance: string;
  gl_balance_at_date: string | null;
  difference: string;
  status: 'DRAFT' | 'IN_PROGRESS' | 'COMPLETED' | 'LOCKED';
  completed_at: string | null;
  completed_by_user_id: string | null;
}

export interface BankReconciliationMatchResponse {
  id: string;
  reconciliation_id: string;
  bank_transaction_id: string;
  statement_line_id: string;
  match_type: 'AUTO' | 'MANUAL';
  matched_at: string;
}

export interface ReconciliationReportResponse {
  reconciliation: BankReconciliationResponse;
  matches: BankReconciliationMatchResponse[];
  unmatched_transactions: BankTransactionResponse[];
  unmatched_statement_lines: BankStatementLineResponse[];
}

export interface ChequeResponse {
  id: string;
  bank_account_id: string;
  cheque_number: string;
  payee_name: string;
  cheque_date: string;
  amount: string;
  status: 'ISSUED' | 'PRESENTED' | 'CLEARED' | 'CANCELLED' | 'STALE';
  bank_transaction_id: string | null;
  bank_statement_line_id: string | null;
  cancelled_at: string | null;
  cancel_reason: string | null;
}

export async function getBankAccounts(companyId: string, activeOnly = false) {
  return apiClient.get<BankAccountResponse[]>(
    `/api/v1/companies/${companyId}/accounting/bank-accounts?active_only=${activeOnly}`
  );
}

export async function createBankAccount(
  companyId: string,
  data: {
    bank_name: string;
    branch_name?: string | null;
    account_number: string;
    iban?: string | null;
    swift_bic?: string | null;
    currency_code: string;
    gl_account_id: string;
    opening_balance?: string;
    opening_balance_date?: string | null;
  }
) {
  return apiClient.post<BankAccountResponse>(
    `/api/v1/companies/${companyId}/accounting/bank-accounts`,
    data
  );
}

export async function getBankAccount(companyId: string, bankAccountId: string) {
  return apiClient.get<BankAccountResponse>(
    `/api/v1/companies/${companyId}/accounting/bank-accounts/${bankAccountId}`
  );
}

export async function transferBetweenBankAccounts(
  companyId: string,
  fromBankAccountId: string,
  data: {
    to_bank_account_id: string;
    amount: string;
    transfer_date: string;
    reference?: string | null;
    description?: string | null;
  }
) {
  return apiClient.post<{
    from_transaction: BankTransactionResponse;
    to_transaction: BankTransactionResponse;
    journal_entry_id: string;
  }>(
    `/api/v1/companies/${companyId}/accounting/bank-accounts/${fromBankAccountId}/transfer`,
    data
  );
}

export async function startBankReconciliation(
  companyId: string,
  bankAccountId: string,
  statementDate: string,
  statementClosingBalance: string
) {
  return apiClient.post<BankReconciliationResponse>(
    `/api/v1/companies/${companyId}/accounting/bank-accounts/${bankAccountId}/reconciliations`,
    { statement_date: statementDate, statement_closing_balance: statementClosingBalance }
  );
}

export async function getBankReconciliationReport(
  companyId: string,
  bankAccountId: string,
  reconciliationId: string
) {
  return apiClient.get<ReconciliationReportResponse>(
    `/api/v1/companies/${companyId}/accounting/bank-accounts/${bankAccountId}` +
      `/reconciliations/${reconciliationId}`
  );
}

export async function importBankStatement(
  companyId: string,
  bankAccountId: string,
  reconciliationId: string,
  lines: {
    statement_date: string;
    value_date?: string | null;
    amount: string;
    reference?: string | null;
    description?: string | null;
    transaction_type?: string | null;
  }[]
) {
  return apiClient.post<BankStatementLineResponse[]>(
    `/api/v1/companies/${companyId}/accounting/bank-accounts/${bankAccountId}` +
      `/reconciliations/${reconciliationId}/import-statement`,
    { lines }
  );
}

export async function autoMatchBankReconciliation(
  companyId: string,
  bankAccountId: string,
  reconciliationId: string
) {
  return apiClient.post<{ matched_count: number; unmatched_count: number }>(
    `/api/v1/companies/${companyId}/accounting/bank-accounts/${bankAccountId}` +
      `/reconciliations/${reconciliationId}/auto-match`,
    {}
  );
}

export async function manualMatchBankReconciliation(
  companyId: string,
  bankAccountId: string,
  reconciliationId: string,
  bankTransactionId: string,
  statementLineId: string
) {
  return apiClient.post<{ match_id: string }>(
    `/api/v1/companies/${companyId}/accounting/bank-accounts/${bankAccountId}` +
      `/reconciliations/${reconciliationId}/manual-match`,
    { bank_transaction_id: bankTransactionId, statement_line_id: statementLineId }
  );
}

export async function unmatchBankReconciliation(
  companyId: string,
  bankAccountId: string,
  reconciliationId: string,
  matchId: string
) {
  return apiClient.post<{ status: string }>(
    `/api/v1/companies/${companyId}/accounting/bank-accounts/${bankAccountId}` +
      `/reconciliations/${reconciliationId}/unmatch/${matchId}`,
    {}
  );
}

export async function completeBankReconciliation(
  companyId: string,
  bankAccountId: string,
  reconciliationId: string
) {
  return apiClient.post<BankReconciliationResponse>(
    `/api/v1/companies/${companyId}/accounting/bank-accounts/${bankAccountId}` +
      `/reconciliations/${reconciliationId}/complete`,
    {}
  );
}

export async function lockBankReconciliation(
  companyId: string,
  bankAccountId: string,
  reconciliationId: string
) {
  return apiClient.post<BankReconciliationResponse>(
    `/api/v1/companies/${companyId}/accounting/bank-accounts/${bankAccountId}` +
      `/reconciliations/${reconciliationId}/lock`,
    {}
  );
}

export async function getCheques(companyId: string, status?: string) {
  const query = status ? `?status=${status}` : '';
  return apiClient.get<ChequeResponse[]>(
    `/api/v1/companies/${companyId}/accounting/cheques${query}`
  );
}

export async function createCheque(
  companyId: string,
  data: {
    bank_account_id: string;
    cheque_number: string;
    payee_name: string;
    cheque_date: string;
    amount: string;
  }
) {
  return apiClient.post<ChequeResponse>(`/api/v1/companies/${companyId}/accounting/cheques`, data);
}

export async function updateChequeStatus(
  companyId: string,
  chequeId: string,
  status: 'PRESENTED' | 'CLEARED' | 'CANCELLED' | 'STALE',
  cancelReason?: string | null
) {
  return apiClient.post<ChequeResponse>(
    `/api/v1/companies/${companyId}/accounting/cheques/${chequeId}/status`,
    { status, cancel_reason: cancelReason ?? null }
  );
}

// ---------------------------------------------------------------------------
// Cash Management (Phase 9)
// ---------------------------------------------------------------------------

export interface CashAccountResponse {
  id: string;
  account_name: string;
  currency_code: string;
  gl_account_id: string;
  current_balance: string;
  is_petty_cash: boolean;
  float_amount: string;
  is_active: boolean;
}

export interface CashTransactionResponse {
  id: string;
  cash_account_id: string;
  transaction_date: string;
  transaction_type: 'RECEIPT' | 'PAYMENT' | 'TRANSFER' | 'ADJUSTMENT';
  amount: string;
  reference: string | null;
  description: string | null;
  journal_entry_id: string | null;
  counterparty_type: string | null;
  counterparty_id: string | null;
}

export interface PettyCashVoucherResponse {
  id: string;
  cash_account_id: string;
  voucher_date: string;
  amount: string;
  expense_account_id: string;
  recipient_name: string;
  purpose: string;
  approved_by_user_id: string | null;
  voucher_number: string;
  journal_entry_id: string | null;
}

export interface CashReconciliationResponse {
  id: string;
  cash_account_id: string;
  reconciliation_date: string;
  physical_count_amount: string;
  gl_balance_amount: string;
  difference: string;
  difference_account_id: string | null;
  journal_entry_id: string | null;
  status: 'DRAFT' | 'COMPLETED';
  completed_at: string | null;
}

export interface CashBookRow {
  id: string;
  transaction_date: string;
  transaction_type: string;
  amount: string;
  reference: string | null;
  description: string | null;
}

export interface CashBookResponse {
  cash_account_id: string;
  from_date: string;
  to_date: string;
  opening_balance: string;
  transactions: CashBookRow[];
  closing_balance: string;
}

export async function getCashAccounts(companyId: string, activeOnly = false) {
  return apiClient.get<CashAccountResponse[]>(
    `/api/v1/companies/${companyId}/accounting/cash-accounts?active_only=${activeOnly}`
  );
}

export async function createCashAccount(
  companyId: string,
  data: {
    account_name: string;
    currency_code: string;
    gl_account_id: string;
    is_petty_cash?: boolean;
    float_amount?: string;
  }
) {
  return apiClient.post<CashAccountResponse>(
    `/api/v1/companies/${companyId}/accounting/cash-accounts`,
    data
  );
}

export async function recordCashReceipt(
  companyId: string,
  cashAccountId: string,
  data: {
    amount: string;
    contra_account_id: string;
    receipt_date: string;
    reference?: string | null;
    description?: string | null;
    counterparty_type?: string | null;
    counterparty_id?: string | null;
  }
) {
  return apiClient.post<CashTransactionResponse>(
    `/api/v1/companies/${companyId}/accounting/cash-accounts/${cashAccountId}/receipts`,
    data
  );
}

export async function recordCashPayment(
  companyId: string,
  cashAccountId: string,
  data: {
    amount: string;
    contra_account_id: string;
    payment_date: string;
    reference?: string | null;
    description?: string | null;
    counterparty_type?: string | null;
    counterparty_id?: string | null;
  }
) {
  return apiClient.post<CashTransactionResponse>(
    `/api/v1/companies/${companyId}/accounting/cash-accounts/${cashAccountId}/payments`,
    data
  );
}

export async function getPettyCashVouchers(companyId: string, cashAccountId: string) {
  return apiClient.get<PettyCashVoucherResponse[]>(
    `/api/v1/companies/${companyId}/accounting/cash-accounts/${cashAccountId}/petty-cash-vouchers`
  );
}

export async function createPettyCashVoucher(
  companyId: string,
  cashAccountId: string,
  data: {
    voucher_date: string;
    amount: string;
    expense_account_id: string;
    recipient_name: string;
    purpose: string;
    voucher_number: string;
    approved_by_user_id?: string | null;
  }
) {
  return apiClient.post<PettyCashVoucherResponse>(
    `/api/v1/companies/${companyId}/accounting/cash-accounts/${cashAccountId}/petty-cash-vouchers`,
    data
  );
}

export async function replenishPettyCash(
  companyId: string,
  cashAccountId: string,
  data: {
    voucher_ids: string[];
    bank_gl_account_id: string;
    replenishment_date: string;
    reference?: string | null;
    description?: string | null;
  }
) {
  return apiClient.post<{
    cash_transaction: CashTransactionResponse;
    vouchers: PettyCashVoucherResponse[];
    journal_entry_id: string;
  }>(
    `/api/v1/companies/${companyId}/accounting/cash-accounts/${cashAccountId}/replenish`,
    data
  );
}

export async function reconcileCash(
  companyId: string,
  cashAccountId: string,
  data: {
    reconciliation_date: string;
    physical_count_amount: string;
    difference_account_id?: string | null;
  }
) {
  return apiClient.post<CashReconciliationResponse>(
    `/api/v1/companies/${companyId}/accounting/cash-accounts/${cashAccountId}/reconcile`,
    data
  );
}

export async function getCashBook(
  companyId: string,
  cashAccountId: string,
  fromDate: string,
  toDate: string
) {
  return apiClient.get<CashBookResponse>(
    `/api/v1/companies/${companyId}/accounting/cash-accounts/${cashAccountId}` +
      `/cash-book?from_date=${fromDate}&to_date=${toDate}`
  );
}

// ---------------------------------------------------------------------------
// Payment Processing (Phase 10)
// ---------------------------------------------------------------------------

export interface PaymentResponse {
  id: string;
  payment_type: 'CUSTOMER_RECEIPT' | 'SUPPLIER_DISBURSEMENT' | 'ADVANCE_RECEIPT' | 'ADVANCE_PAYMENT';
  payment_method: 'CASH' | 'BANK_TRANSFER' | 'CHEQUE' | 'CARD' | 'ONLINE';
  payment_date: string;
  currency_code: string;
  exchange_rate: string;
  amount_foreign: string;
  amount_base: string;
  bank_account_id: string | null;
  cash_account_id: string | null;
  party_type: 'CUSTOMER' | 'SUPPLIER';
  party_id: string;
  reference: string | null;
  notes: string | null;
  status: 'DRAFT' | 'POSTED' | 'ALLOCATED' | 'CANCELLED';
  journal_entry_id: string | null;
  cheque_id: string | null;
  discount_amount: string;
  wht_amount: string;
}

export interface PaymentAllocationLineResponse {
  id: string;
  payment_id: string;
  ar_transaction_id: string | null;
  ap_transaction_id: string | null;
  allocated_amount_foreign: string;
  allocated_amount_base: string;
  discount_amount: string;
  gain_loss_amount: string;
  gain_loss_journal_entry_id: string | null;
  allocated_at: string;
}

export interface PaymentRefundResponse {
  id: string;
  original_payment_id: string;
  refund_date: string;
  amount: string;
  reason: string;
  journal_entry_id: string | null;
  bank_account_id: string | null;
  cash_account_id: string | null;
}

export interface WHTCertificateResponse {
  payment_id: string;
  party_id: string;
  payment_date: string;
  currency_code: string;
  gross_amount: string;
  wht_amount: string;
  net_amount: string;
  wht_rate_percent: string;
}

export interface AllocationLineInput {
  transaction_id: string;
  amount_foreign: string;
  discount_amount?: string;
  discount_account_id?: string | null;
  release_account_id?: string | null;
}

export async function getCustomerPayments(companyId: string, customerId: string) {
  return apiClient.get<PaymentResponse[]>(
    `/api/v1/companies/${companyId}/accounting/payments/customer?customer_id=${customerId}`
  );
}

export async function createCustomerPayment(
  companyId: string,
  data: {
    customer_id: string;
    payment_method: string;
    payment_date: string;
    amount: string;
    currency_code: string;
    exchange_rate?: string;
    payment_type?: string;
    bank_account_id?: string | null;
    cash_account_id?: string | null;
    advance_account_id?: string | null;
    reference?: string | null;
    notes?: string | null;
    cheque_id?: string | null;
  }
) {
  return apiClient.post<PaymentResponse>(
    `/api/v1/companies/${companyId}/accounting/payments/customer`,
    data
  );
}

export async function getSupplierPayments(companyId: string, supplierId: string) {
  return apiClient.get<PaymentResponse[]>(
    `/api/v1/companies/${companyId}/accounting/payments/supplier?supplier_id=${supplierId}`
  );
}

export async function createSupplierPayment(
  companyId: string,
  data: {
    supplier_id: string;
    payment_method: string;
    payment_date: string;
    amount: string;
    currency_code: string;
    exchange_rate?: string;
    payment_type?: string;
    bank_account_id?: string | null;
    cash_account_id?: string | null;
    advance_account_id?: string | null;
    wht_amount?: string;
    wht_payable_account_id?: string | null;
    reference?: string | null;
    notes?: string | null;
    cheque_id?: string | null;
  }
) {
  return apiClient.post<PaymentResponse>(
    `/api/v1/companies/${companyId}/accounting/payments/supplier`,
    data
  );
}

export async function allocatePayment(
  companyId: string,
  paymentId: string,
  allocationLines: AllocationLineInput[]
) {
  return apiClient.post<PaymentAllocationLineResponse[]>(
    `/api/v1/companies/${companyId}/accounting/payments/${paymentId}/allocate`,
    { allocation_lines: allocationLines }
  );
}

export async function reallocatePayment(
  companyId: string,
  paymentId: string,
  allocationLines: AllocationLineInput[]
) {
  return apiClient.post<PaymentAllocationLineResponse[]>(
    `/api/v1/companies/${companyId}/accounting/payments/${paymentId}/reallocate`,
    { allocation_lines: allocationLines }
  );
}

export async function cancelPayment(companyId: string, paymentId: string, reason: string) {
  return apiClient.post<PaymentResponse>(
    `/api/v1/companies/${companyId}/accounting/payments/${paymentId}/cancel`,
    { reason }
  );
}

export async function refundPayment(
  companyId: string,
  paymentId: string,
  data: {
    refund_date: string;
    amount: string;
    reason: string;
    bank_account_id?: string | null;
    cash_account_id?: string | null;
  }
) {
  return apiClient.post<PaymentRefundResponse>(
    `/api/v1/companies/${companyId}/accounting/payments/${paymentId}/refund`,
    data
  );
}

export async function getUnallocatedPayments(companyId: string, partyType?: string) {
  const query = partyType ? `?party_type=${partyType}` : '';
  return apiClient.get<PaymentResponse[]>(
    `/api/v1/companies/${companyId}/accounting/payments/unallocated${query}`
  );
}

export async function getWHTCertificate(companyId: string, paymentId: string) {
  return apiClient.get<WHTCertificateResponse>(
    `/api/v1/companies/${companyId}/accounting/payments/${paymentId}/wht-certificate`
  );
}

// ---------------------------------------------------------------------------
// Tax Engine (Phase 11)
// ---------------------------------------------------------------------------

export interface TaxCodeResponse {
  id: string;
  tax_code: string;
  tax_name: string;
  tax_type:
    | 'SALES_TAX'
    | 'VAT'
    | 'GST'
    | 'WITHHOLDING'
    | 'COMPOUND'
    | 'EXEMPT'
    | 'ZERO_RATED'
    | 'OUT_OF_SCOPE';
  applicability: 'SALES' | 'PURCHASES' | 'BOTH';
  gl_account_id: string;
  is_input_tax_recoverable: boolean;
  country_code: string | null;
  is_active: boolean;
}

export interface TaxRateResponse {
  id: string;
  tax_code_id: string;
  effective_from: string;
  effective_to: string | null;
  rate: string;
  rounding_rule: 'HALF_UP' | 'HALF_EVEN' | 'DOWN' | 'UP';
}

export interface TaxGroupResponse {
  id: string;
  group_code: string;
  group_name: string;
  applicability: 'SALES' | 'PURCHASES' | 'BOTH';
  is_active: boolean;
}

export interface TaxGroupLineResponse {
  id: string;
  tax_group_id: string;
  tax_code_id: string;
  display_order: number;
}

export interface TaxAmountResponse {
  tax_code_id: string;
  tax_code: string;
  base_amount: string;
  tax_rate: string;
  tax_amount: string;
  gl_account_id: string;
  is_input_tax_recoverable: boolean;
}

export interface TaxCalculationResult {
  lines: TaxAmountResponse[];
  total_tax_amount: string;
}

export interface TaxSummaryReportRow {
  tax_code_id: string;
  tax_code: string;
  tax_name: string;
  output_tax: string;
  input_tax: string;
  is_input_tax_recoverable: boolean;
}

export interface TaxSummaryReport {
  period_start: string;
  period_end: string;
  rows: TaxSummaryReportRow[];
  total_output_tax: string;
  total_input_tax: string;
  net_payable: string;
}

export interface TaxDetailRow {
  journal_entry_id: string;
  journal_number: string;
  posting_date: string;
  account_id: string;
  account_code: string;
  debit_amount: string;
  credit_amount: string;
  description: string | null;
  reference: string | null;
  source_document_type: string | null;
  source_document_id: string | null;
  tax_code_id: string;
  tax_code: string;
  tax_type: string;
}

export interface WHTReportRow {
  supplier_id: string;
  gross_amount: string;
  wht_amount: string;
  net_amount: string;
  payment_count: number;
}

export interface WHTReport {
  period_start: string;
  period_end: string;
  rows: WHTReportRow[];
  total_wht: string;
}

export async function getTaxCodes(companyId: string, activeOnly = false) {
  return apiClient.get<TaxCodeResponse[]>(
    `/api/v1/companies/${companyId}/accounting/tax-codes?active_only=${activeOnly}`
  );
}

export async function createTaxCode(
  companyId: string,
  data: {
    tax_code: string;
    tax_name: string;
    tax_type: string;
    applicability: string;
    gl_account_id: string;
    is_input_tax_recoverable?: boolean;
    country_code?: string | null;
  }
) {
  return apiClient.post<TaxCodeResponse>(
    `/api/v1/companies/${companyId}/accounting/tax-codes`,
    data
  );
}

export async function getTaxCode(companyId: string, taxCodeId: string) {
  return apiClient.get<TaxCodeResponse>(
    `/api/v1/companies/${companyId}/accounting/tax-codes/${taxCodeId}`
  );
}

export async function updateTaxCode(
  companyId: string,
  taxCodeId: string,
  data: {
    tax_name?: string;
    is_input_tax_recoverable?: boolean;
    country_code?: string | null;
    is_active?: boolean;
  }
) {
  return apiClient.put<TaxCodeResponse>(
    `/api/v1/companies/${companyId}/accounting/tax-codes/${taxCodeId}`,
    data
  );
}

export async function getTaxRates(companyId: string, taxCodeId: string) {
  return apiClient.get<TaxRateResponse[]>(
    `/api/v1/companies/${companyId}/accounting/tax-codes/${taxCodeId}/rates`
  );
}

export async function createTaxRate(
  companyId: string,
  taxCodeId: string,
  data: {
    effective_from: string;
    effective_to?: string | null;
    rate: string;
    rounding_rule?: string;
  }
) {
  return apiClient.post<TaxRateResponse>(
    `/api/v1/companies/${companyId}/accounting/tax-codes/${taxCodeId}/rates`,
    data
  );
}

export async function getTaxGroups(companyId: string, activeOnly = false) {
  return apiClient.get<TaxGroupResponse[]>(
    `/api/v1/companies/${companyId}/accounting/tax-groups?active_only=${activeOnly}`
  );
}

export async function createTaxGroup(
  companyId: string,
  data: { group_code: string; group_name: string; applicability: string }
) {
  return apiClient.post<TaxGroupResponse>(
    `/api/v1/companies/${companyId}/accounting/tax-groups`,
    data
  );
}

export async function getTaxGroupLines(companyId: string, taxGroupId: string) {
  return apiClient.get<TaxGroupLineResponse[]>(
    `/api/v1/companies/${companyId}/accounting/tax-groups/${taxGroupId}/lines`
  );
}

export async function addTaxGroupLine(
  companyId: string,
  taxGroupId: string,
  data: { tax_code_id: string; display_order?: number }
) {
  return apiClient.post<TaxGroupLineResponse>(
    `/api/v1/companies/${companyId}/accounting/tax-groups/${taxGroupId}/lines`,
    data
  );
}

export async function calculateTax(
  companyId: string,
  data: {
    tax_code_or_group_id: string;
    base_amount: string;
    transaction_date: string;
    is_tax_inclusive?: boolean;
  }
) {
  return apiClient.post<TaxCalculationResult>(
    `/api/v1/companies/${companyId}/accounting/tax/calculate`,
    data
  );
}

export async function getTaxSummaryReport(
  companyId: string,
  periodStart: string,
  periodEnd: string
) {
  return apiClient.get<TaxSummaryReport>(
    `/api/v1/companies/${companyId}/accounting/reports/tax-summary` +
      `?period_start=${periodStart}&period_end=${periodEnd}`
  );
}

export async function getTaxDetailReport(
  companyId: string,
  params: { periodStart?: string; periodEnd?: string; taxCodeId?: string } = {}
) {
  const query = new URLSearchParams();
  if (params.periodStart) query.set('period_start', params.periodStart);
  if (params.periodEnd) query.set('period_end', params.periodEnd);
  if (params.taxCodeId) query.set('tax_code_id', params.taxCodeId);
  return apiClient.get<TaxDetailRow[]>(
    `/api/v1/companies/${companyId}/accounting/reports/tax-detail?${query.toString()}`
  );
}

export async function getWHTReport(companyId: string, periodStart: string, periodEnd: string) {
  return apiClient.get<WHTReport>(
    `/api/v1/companies/${companyId}/accounting/reports/wht` +
      `?period_start=${periodStart}&period_end=${periodEnd}`
  );
}

// ---------------------------------------------------------------------------
// Cost Accounting (Phase 11)
// ---------------------------------------------------------------------------

export interface DepartmentResponse {
  id: string;
  dept_code: string;
  dept_name: string;
  parent_dept_id: string | null;
  is_active: boolean;
}

export interface CostCenterResponse {
  id: string;
  center_code: string;
  center_name: string;
  department_id: string | null;
  responsible_user_id: string | null;
  is_active: boolean;
}

export interface ProjectResponse {
  id: string;
  project_code: string;
  project_name: string;
  start_date: string | null;
  end_date: string | null;
  budget_amount: string | null;
  responsible_user_id: string | null;
  is_active: boolean;
}

export interface PLReportLine {
  account_id: string;
  account_code: string;
  account_name: string;
  account_type: string;
  amount: string;
}

export interface CostCenterPLReport {
  id: string;
  name: string;
  period_start: string | null;
  period_end: string | null;
  revenue_lines: PLReportLine[];
  expense_lines: PLReportLine[];
  total_revenue: string;
  total_expense: string;
  net_income: string;
}

export async function getDepartments(companyId: string, activeOnly = false) {
  return apiClient.get<DepartmentResponse[]>(
    `/api/v1/companies/${companyId}/accounting/departments?active_only=${activeOnly}`
  );
}

export async function createDepartment(
  companyId: string,
  data: { dept_code: string; dept_name: string; parent_dept_id?: string | null }
) {
  return apiClient.post<DepartmentResponse>(
    `/api/v1/companies/${companyId}/accounting/departments`,
    data
  );
}

export async function getCostCenters(companyId: string, activeOnly = false) {
  return apiClient.get<CostCenterResponse[]>(
    `/api/v1/companies/${companyId}/accounting/cost-centers?active_only=${activeOnly}`
  );
}

export async function createCostCenter(
  companyId: string,
  data: {
    center_code: string;
    center_name: string;
    department_id?: string | null;
    responsible_user_id?: string | null;
  }
) {
  return apiClient.post<CostCenterResponse>(
    `/api/v1/companies/${companyId}/accounting/cost-centers`,
    data
  );
}

export async function getProjects(companyId: string, activeOnly = false) {
  return apiClient.get<ProjectResponse[]>(
    `/api/v1/companies/${companyId}/accounting/projects?active_only=${activeOnly}`
  );
}

export async function createProject(
  companyId: string,
  data: {
    project_code: string;
    project_name: string;
    start_date?: string | null;
    end_date?: string | null;
    budget_amount?: string | null;
    responsible_user_id?: string | null;
  }
) {
  return apiClient.post<ProjectResponse>(
    `/api/v1/companies/${companyId}/accounting/projects`,
    data
  );
}

export async function getCostCenterPLReport(
  companyId: string,
  costCenterId: string,
  periodStart?: string,
  periodEnd?: string
) {
  const query = new URLSearchParams({ cost_center_id: costCenterId });
  if (periodStart) query.set('period_start', periodStart);
  if (periodEnd) query.set('period_end', periodEnd);
  return apiClient.get<CostCenterPLReport>(
    `/api/v1/companies/${companyId}/accounting/reports/cost-center-pl?${query.toString()}`
  );
}

export async function getProjectPLReport(
  companyId: string,
  projectId: string,
  periodStart?: string,
  periodEnd?: string
) {
  const query = new URLSearchParams({ project_id: projectId });
  if (periodStart) query.set('period_start', periodStart);
  if (periodEnd) query.set('period_end', periodEnd);
  return apiClient.get<CostCenterPLReport>(
    `/api/v1/companies/${companyId}/accounting/reports/project-pl?${query.toString()}`
  );
}

// ---------------------------------------------------------------------------
// Multi-Currency — Currency Revaluation (Phase 12)
// ---------------------------------------------------------------------------

export interface RevaluationLine {
  transaction_type: string;
  transaction_id: string;
  currency_code: string;
  booking_rate: string;
  current_rate: string;
  outstanding_foreign: string;
  outstanding_base_before: string;
  gain_loss_amount: string;
}

export interface RevaluationReport {
  id: string;
  company_id: string;
  fiscal_period_id: string;
  revaluation_date: string;
  currencies_revalued: string[];
  lines: RevaluationLine[];
  total_unrealized_gain_base: string;
  total_unrealized_loss_base: string;
  net_gain_loss_base: string;
  journal_entry_id: string | null;
  created_at: string;
}

export async function runCurrencyRevaluation(
  companyId: string,
  data: { fiscal_period_id: string; revaluation_date: string }
) {
  return apiClient.post<RevaluationReport>(
    `/api/v1/companies/${companyId}/accounting/currency-revaluation`,
    data
  );
}

export async function getCurrencyRevaluationHistory(companyId: string) {
  return apiClient.get<RevaluationReport[]>(
    `/api/v1/companies/${companyId}/accounting/currency-revaluation/history`
  );
}

export async function getCurrencyRevaluationReport(companyId: string, revaluationId: string) {
  return apiClient.get<RevaluationReport>(
    `/api/v1/companies/${companyId}/accounting/currency-revaluation/${revaluationId}/report`
  );
}

// ---------------------------------------------------------------------------
// Financial Statements & Reports (Phase 13)
// ---------------------------------------------------------------------------

export interface TrialBalanceRow {
  account_id: string;
  account_code: string;
  total_debit: string;
  total_credit: string;
}

export interface TrialBalanceReport {
  company_id: string;
  fiscal_period_id: string;
  rows: TrialBalanceRow[];
  total_debit: string;
  total_credit: string;
  is_balanced: boolean;
  comparative: TrialBalanceReport | null;
}

export interface BalanceSheetLine {
  account_id: string | null;
  account_code: string;
  account_name: string;
  account_type: string;
  total_debit: string;
  total_credit: string;
  amount: string;
}

export interface BalanceSheetSection {
  name: string;
  lines: BalanceSheetLine[];
  total: string;
}

export interface BalanceSheetReport {
  company_id: string;
  as_of_date: string;
  report_currency: string;
  assets: BalanceSheetSection;
  liabilities: BalanceSheetSection;
  equity: BalanceSheetSection;
  total_assets: string;
  total_liabilities: string;
  total_equity: string;
  is_balanced: boolean;
  comparative: BalanceSheetReport | null;
}

export interface PLLine {
  account_id: string;
  account_code: string;
  account_name: string;
  account_type: string;
  total_debit: string;
  total_credit: string;
  amount: string;
}

export interface PLSection {
  name: string;
  lines: PLLine[];
  total: string;
}

export interface PLReport {
  company_id: string;
  period_from: string;
  period_to: string;
  cost_center_id: string | null;
  report_currency: string;
  revenue: PLSection;
  expense: PLSection;
  total_revenue: string;
  total_expense: string;
  net_income: string;
  comparative: PLReport | null;
}

export interface CashFlowAdjustmentLine {
  account_id: string;
  account_code: string;
  account_type: string;
  total_debit: string;
  total_credit: string;
  adjustment: string;
}

export interface CashFlowReport {
  company_id: string;
  period_from: string;
  period_to: string;
  net_income: string;
  working_capital_adjustments: CashFlowAdjustmentLine[];
  net_cash_from_operating_activities: string;
  opening_cash_balance: string;
  closing_cash_balance: string;
  net_change_in_cash: string;
  reconciles: boolean;
}

export interface LedgerStatementTransaction {
  [key: string]: unknown;
  transaction_date?: string;
  invoice_number?: string;
  bill_number?: string;
  amount_base?: string;
  amount?: string;
  outstanding_amount?: string;
}

export interface LedgerStatementReport {
  from_date: string;
  to_date: string;
  opening_balance: string;
  transactions: LedgerStatementTransaction[];
  closing_balance: string;
}

export interface JournalEntrySummary {
  id: string;
  journal_number: string | null;
  journal_type: string;
  posting_date: string;
  status: string;
  total_debit_base: string;
  total_credit_base: string;
  description: string | null;
}

export interface JournalReportResponse {
  company_id: string;
  fiscal_period_id: string;
  entries: JournalEntrySummary[];
  total: number;
}

export async function getTrialBalanceReport(
  companyId: string,
  periodId: string,
  comparativePeriodId?: string
) {
  const q = new URLSearchParams({ period_id: periodId });
  if (comparativePeriodId) q.set('comparative_period_id', comparativePeriodId);
  return apiClient.get<TrialBalanceReport>(
    `/api/v1/companies/${companyId}/accounting/reports/trial-balance?${q.toString()}`
  );
}

export async function getBalanceSheetReport(
  companyId: string,
  asOfDate: string,
  comparativeDate?: string,
  reportCurrency?: string
) {
  const q = new URLSearchParams({ as_of_date: asOfDate });
  if (comparativeDate) q.set('comparative_date', comparativeDate);
  if (reportCurrency) q.set('report_currency', reportCurrency);
  return apiClient.get<BalanceSheetReport>(
    `/api/v1/companies/${companyId}/accounting/reports/balance-sheet?${q.toString()}`
  );
}

export async function getProfitLossReport(
  companyId: string,
  periodFrom: string,
  periodTo: string,
  options?: {
    comparativeFrom?: string | undefined;
    comparativeTo?: string | undefined;
    costCenterId?: string | undefined;
    reportCurrency?: string | undefined;
  }
) {
  const q = new URLSearchParams({ period_from: periodFrom, period_to: periodTo });
  if (options?.comparativeFrom) q.set('comparative_from', options.comparativeFrom);
  if (options?.comparativeTo) q.set('comparative_to', options.comparativeTo);
  if (options?.costCenterId) q.set('cost_center_id', options.costCenterId);
  if (options?.reportCurrency) q.set('report_currency', options.reportCurrency);
  return apiClient.get<PLReport>(
    `/api/v1/companies/${companyId}/accounting/reports/profit-loss?${q.toString()}`
  );
}

export async function getCashFlowReport(companyId: string, periodFrom: string, periodTo: string) {
  const q = new URLSearchParams({ period_from: periodFrom, period_to: periodTo });
  return apiClient.get<CashFlowReport>(
    `/api/v1/companies/${companyId}/accounting/reports/cash-flow?${q.toString()}`
  );
}

export async function getJournalReport(
  companyId: string,
  periodId: string,
  skip = 0,
  limit = 500
) {
  const q = new URLSearchParams({
    period_id: periodId,
    skip: String(skip),
    limit: String(limit),
  });
  return apiClient.get<JournalReportResponse>(
    `/api/v1/companies/${companyId}/accounting/reports/journals?${q.toString()}`
  );
}

export async function getBankBookReport(
  companyId: string,
  bankAccountId: string,
  fromDate: string,
  toDate: string
) {
  const q = new URLSearchParams({ from_date: fromDate, to_date: toDate });
  return apiClient.get<LedgerStatementReport>(
    `/api/v1/companies/${companyId}/accounting/reports/bank-book/${bankAccountId}?${q.toString()}`
  );
}

export async function getCashBookReport(
  companyId: string,
  cashAccountId: string,
  fromDate: string,
  toDate: string
) {
  const q = new URLSearchParams({ from_date: fromDate, to_date: toDate });
  return apiClient.get<LedgerStatementReport>(
    `/api/v1/companies/${companyId}/accounting/reports/cash-book/${cashAccountId}?${q.toString()}`
  );
}

/** File extension used for each downloadable export format. */
const EXPORT_EXTENSIONS: Record<'pdf' | 'excel' | 'csv', string> = {
  pdf: 'pdf',
  excel: 'xlsx',
  csv: 'csv',
};

/**
 * Download a report as PDF, Excel, or CSV — /reports/* endpoints accept
 * ?format=pdf|excel (tasks.md T261); other exportable endpoints (e.g. the
 * audit log, tasks.md T281) additionally accept ?format=csv. Triggers a
 * browser download.
 */
export async function downloadReportExport(
  companyId: string,
  reportPath: string,
  format: 'pdf' | 'excel' | 'csv',
  filename: string,
  extraParams?: Record<string, string>
): Promise<void> {
  const base = process.env['NEXT_PUBLIC_API_URL'] ?? 'http://localhost:8000';
  const q = new URLSearchParams({ format, ...(extraParams ?? {}) });
  const token = getAccessToken();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const resp = await fetch(
    `${base}/api/v1/companies/${companyId}/accounting${reportPath}?${q.toString()}`,
    { headers }
  );
  if (!resp.ok) {
    throw new Error(`Export failed: ${resp.statusText}`);
  }
  const blob = await resp.blob();
  const ext = EXPORT_EXTENSIONS[format];
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${filename}.${ext}`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Audit Trail ──────────────────────────────────────────────────────────

/** A single immutable audit log entry recorded for a company. */
export interface AuditLogEntry {
  id: string;
  company_id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor_user_id: string | null;
  occurred_at: string;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  reason: string | null;
}

export interface AuditLogListResponse {
  entries: AuditLogEntry[];
  total: number;
  skip: number;
  limit: number;
}

export interface AuditLogFilters {
  entity_type?: string | undefined;
  entity_id?: string | undefined;
  actor_user_id?: string | undefined;
  action?: string | undefined;
  date_from?: string | undefined;
  date_to?: string | undefined;
  skip?: number | undefined;
  limit?: number | undefined;
}

/**
 * Searchable, paginated, immutable audit history for a company.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T281
 */
export async function getAuditLog(companyId: string, filters: AuditLogFilters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value));
  });
  const query = params.toString() ? `?${params.toString()}` : '';
  return apiClient.get<AuditLogListResponse>(
    `/api/v1/companies/${companyId}/accounting/audit-log${query}`
  );
}

// ---------------------------------------------------------------------------
// Financial Intelligence & KPI Dashboard (Phase 15, T286-T291)
// ---------------------------------------------------------------------------

export interface KPIValue {
  label: string;
  current_value: string;
  prior_value: string;
  change_pct: string | null;
  trend: 'up' | 'down' | 'flat';
}

export interface PeriodCloseStatusItem {
  period_name: string;
  period_number: number;
  status: string;
}

export interface FinancialKPIResponse {
  company_id: string;
  as_of_date: string;
  kpis: Record<string, KPIValue>;
  period_close_status: PeriodCloseStatusItem[];
}

export interface CashAccountBalance {
  account_id: string;
  account_code: string;
  account_name: string;
  is_bank_account: boolean;
  is_cash_account: boolean;
  balance: string;
}

export interface CashTrendPoint {
  date: string;
  balance: string;
}

export interface CashPositionResponse {
  company_id: string;
  as_of_date: string;
  total_cash_position: string;
  accounts: CashAccountBalance[];
  trend: CashTrendPoint[];
}

/**
 * All 15 CFO dashboard KPIs (spec.md §40), each with its prior-period value,
 * percentage change, and trend direction.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T287
 */
export async function getDashboardKPIs(companyId: string, asOfDate?: string) {
  const q = new URLSearchParams();
  if (asOfDate) q.set('as_of_date', asOfDate);
  const query = q.toString() ? `?${q.toString()}` : '';
  return apiClient.get<FinancialKPIResponse>(
    `/api/v1/companies/${companyId}/accounting/dashboard/kpis${query}`
  );
}

/**
 * Bank + cash account balances with a trailing daily trend series.
 *
 * Spec ref: specs/008-accounting-finance/tasks.md T288
 */
export async function getDashboardCashPosition(
  companyId: string,
  options?: { asOfDate?: string | undefined; trendDays?: number | undefined }
) {
  const q = new URLSearchParams();
  if (options?.asOfDate) q.set('as_of_date', options.asOfDate);
  if (options?.trendDays) q.set('trend_days', String(options.trendDays));
  const query = q.toString() ? `?${q.toString()}` : '';
  return apiClient.get<CashPositionResponse>(
    `/api/v1/companies/${companyId}/accounting/dashboard/cash-position${query}`
  );
}
