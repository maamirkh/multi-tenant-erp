# Data Model: Epic 8 — Accounting & Finance

**Generated**: 2026-08-05
**Feature**: 008-accounting-finance
**Source**: spec.md + research.md Phase 0 decisions
**Architecture**: DDD — Aggregate Roots, Entities, Value Objects, Domain Events

---

## Table of Contents

1. [Domain Layer Overview](#1-domain-layer-overview)
2. [Aggregate Roots](#2-aggregate-roots)
3. [Value Objects](#3-value-objects)
4. [Domain Services](#4-domain-services)
5. [Application Services](#5-application-services)
6. [Repositories](#6-repositories)
7. [Domain Events](#7-domain-events)
8. [State Machines](#8-state-machines)
9. [Entity Relationships](#9-entity-relationships)
10. [Aggregate Boundaries](#10-aggregate-boundaries)
11. [Database Tables (Conceptual)](#11-database-tables-conceptual)
12. [Migration Strategy](#12-migration-strategy)

---

## 1. Domain Layer Overview

The Accounting domain is structured as 9 bounded aggregates. All aggregates share:
- `tenant_id` — SaaS tenant isolation (top level)
- `company_id` — Company-level financial isolation
- `is_deleted` / `deleted_at` / `deleted_by_user_id` — Soft delete (all non-financial entities)
- `created_at` / `created_by_user_id` — Immutable creation stamp
- `updated_at` / `updated_by_user_id` — Last modification stamp

**Financial records (GL entries, journal lines, payment records, audit entries) are NEVER soft-deleted.** They are append-only and immutable after posting.

### Layer Separation

```
Domain Layer
  ├── Aggregates (JournalEntry, FiscalYear, CustomerLedger, ...)
  ├── Value Objects (Money, AccountCode, ExchangeRate, TaxAmount, ...)
  ├── Domain Services (PostingEngine, TaxCalculator, AllocationEngine, ...)
  └── Domain Events (journal.posted, payment.received, period.locked, ...)

Application Layer
  ├── Application Services (one service class per use case group)
  ├── Command/Query objects
  └── Event Handlers (consumes external events from Sales, Purchase, Inventory)

Infrastructure Layer
  ├── Repositories (SQLAlchemy 2.x async implementations)
  ├── ORM Models (SQLAlchemy declarative, strict table-per-class)
  └── Event Bus (InProcessEventBus — same pattern as Epics 5–7)

API Layer
  ├── FastAPI Routers
  ├── Pydantic v2 Schemas (request/response)
  └── Dependency injection (company_id, auth context, session)
```

---

## 2. Aggregate Roots

### 2.1 ChartOfAccounts

**Aggregate Root**: `Account`
**Invariants**:
- Account code unique per company
- Leaf accounts only accept postings (parent/group accounts block postings)
- Inactive accounts reject all new postings
- Deactivation not permitted if account has GL activity in the current fiscal year

**Entities Within Aggregate**:
- `Account` (root)
- `AccountGroup` (parent classification; self-referencing hierarchy)

**Key Attributes**:
- account_code, account_name, account_type (ASSET / LIABILITY / EQUITY / REVENUE / EXPENSE)
- account_group_id, parent_account_id (nullable — null = root account)
- is_leaf (bool — only leaf accounts accept postings)
- currency_code (nullable — null = base currency; set for foreign-denominated accounts)
- requires_cost_center (bool)
- is_bank_account, is_cash_account (bool — for bank/cash module linkage)
- is_active (bool — false blocks all postings)
- tax_category (nullable — for tax account linkage)
- notes

**State Transitions**: Active → Inactive (if no current-year activity); Inactive → Active

---

### 2.2 FiscalCalendar

**Aggregate Root**: `FiscalYear`
**Invariants**:
- Fiscal periods within a year are non-overlapping and contiguous
- A period can only transition OPEN → LOCKED → CLOSED (no reversal of CLOSED)
- LOCKED can revert to OPEN (with controller authority + audit record)
- Year-end close cannot proceed until all periods in the year are LOCKED
- Only one active fiscal year setup process at a time

**Entities Within Aggregate**:
- `FiscalYear` (root)
- `FiscalPeriod` (1–13 periods per year; 12 months + optional adjustment period)
- `OpeningBalance` (one per account per fiscal year setup)

**Key Attributes (FiscalYear)**:
- fiscal_year_name, start_date, end_date
- status (SETUP / OPEN / CLOSED)
- base_currency_code
- is_current (bool — the active operating year)

**Key Attributes (FiscalPeriod)**:
- period_number (1–13), period_name, start_date, end_date
- status (OPEN / LOCKED / CLOSED)
- locked_at, locked_by_user_id, lock_reason
- closed_at, closed_by_user_id

---

### 2.3 JournalEntry

**Aggregate Root**: `JournalEntry`
**Invariants** (enforced by PostingEngine):
- Sum(debit_amounts) == Sum(credit_amounts) — balanced (zero variance allowed)
- All referenced accounts must be active leaf accounts
- Posting date must fall within an OPEN fiscal period
- All required cost centers must be provided
- Approval required before posting if amount exceeds threshold
- A posted entry is immutable — no updates or deletes

**Entities Within Aggregate**:
- `JournalEntry` (root)
- `JournalLine` (minimum 2 lines; debit or credit)
- `JournalApproval` (approval record — created when approval required)
- `JournalAttachment` (supporting document references)

**Key Attributes (JournalEntry)**:
- journal_number (auto-generated, gap-free per company)
- journal_type (STANDARD / ADJUSTING / REVERSING / RECURRING_INSTANCE / OPENING_BALANCE / CLOSING / AUTOMATED)
- source (MANUAL / SALES / PURCHASE / INVENTORY / BANK / CASH / PAYMENT / RECURRING / SYSTEM)
- posting_date, fiscal_period_id, fiscal_year_id
- reference, description, notes
- status (DRAFT / SUBMITTED / APPROVED / POSTED / REVERSED)
- reversal_of_journal_id (nullable — links to original if this is a reversal)
- is_reversal (bool)
- posted_at, posted_by_user_id
- source_document_type, source_document_id (for drilldown to origin)
- currency_code, exchange_rate (if foreign currency)
- total_debit_base_currency, total_credit_base_currency

**Key Attributes (JournalLine)**:
- line_number (sequential within entry)
- account_id, account_code (denormalized for query performance)
- debit_amount, credit_amount (one must be zero, the other positive)
- debit_amount_base, credit_amount_base (base currency equivalent)
- currency_code, exchange_rate
- cost_center_id (nullable unless account.requires_cost_center)
- department_id (nullable)
- project_id (nullable)
- description, reference

---

### 2.4 CustomerLedger

**Aggregate Root**: `CustomerLedger`
**Invariants**:
- CustomerLedger balance = Sum(open transactions) − Sum(allocations) per customer
- CustomerLedger balance MUST reconcile to AR control account in GL at all times
- A closed (fully paid) invoice cannot accept new allocations
- Credit hold status blocks new invoice creation (enforced at application layer; Sales is notified)

**Entities Within Aggregate**:
- `CustomerLedger` (root — one per customer per company)
- `ARTransaction` (invoice, credit note, debit note, adjustment, write-off)
- `ARPaymentAllocation` (links payments to invoices; tracks allocated amounts)
- `CustomerCreditHistory` (credit limit changes, hold events)

**Key Attributes (ARTransaction)**:
- transaction_type (INVOICE / CREDIT_NOTE / DEBIT_NOTE / PAYMENT / ADVANCE / ADJUSTMENT / WRITE_OFF)
- transaction_date, due_date
- currency_code, exchange_rate
- amount_foreign, amount_base
- outstanding_amount (denormalized for aging query performance; updated on allocation)
- status (OPEN / PARTIALLY_PAID / PAID / OVERDUE / DISPUTED / WRITTEN_OFF)
- source_document_type, source_document_id
- journal_entry_id (GL cross-reference)
- is_reconciled, reconciled_at

**Key Attributes (CustomerLedger root)**:
- customer_id (reference to Epic 7 customer)
- credit_limit, credit_status (GOOD / WARNING / EXCEEDED / HOLD)
- credit_hold_at, credit_hold_reason, credit_hold_by
- total_outstanding_base (materialized; updated on each posting)
- last_payment_date, average_payment_days (for DSO calculation)

---

### 2.5 SupplierLedger

**Aggregate Root**: `SupplierLedger`
**Invariants** (mirror of CustomerLedger for AP):
- SupplierLedger balance reconciles to AP control account in GL
- A closed bill cannot accept new allocations
- Supplier credits cannot exceed outstanding balance unless refund is processed

**Entities Within Aggregate**:
- `SupplierLedger` (root)
- `APTransaction` (bill, credit note, debit note, payment, advance, adjustment)
- `APPaymentAllocation` (links payments to bills)
- `SupplierStatementReconciliation` (statement reconciliation records)

**Key Attributes**: Mirror of `CustomerLedger` / `ARTransaction` with supplier context.

---

### 2.6 BankAccount

**Aggregate Root**: `BankAccount`
**Invariants**:
- BankAccount GL balance = Sum(cleared bank transactions) per reconciliation
- A bank account must be linked to exactly one GL account of type Asset/Bank
- A completed reconciliation is locked — no modifications to matched items

**Entities Within Aggregate**:
- `BankAccount` (root)
- `BankTransaction` (receipts, payments, transfers, bank charges)
- `BankStatementLine` (imported from bank statement for reconciliation)
- `BankReconciliation` (reconciliation session)
- `BankReconciliationMatch` (pairs GL transaction with statement line)
- `Cheque` (issued cheque tracking)

**Key Attributes (BankAccount)**:
- bank_name, branch_name, account_number, iban, swift_bic
- currency_code, gl_account_id
- opening_balance, opening_balance_date
- current_gl_balance (denormalized; updated on each posting)
- is_active

**Key Attributes (BankReconciliation)**:
- statement_date, statement_closing_balance
- status (DRAFT / IN_PROGRESS / COMPLETED / LOCKED)
- gl_balance_at_date, difference (must be zero to complete)
- completed_at, completed_by_user_id

**Key Attributes (Cheque)**:
- cheque_number, payee_name, cheque_date, amount
- status (ISSUED / PRESENTED / CLEARED / CANCELLED / STALE)
- bank_transaction_id, bank_statement_line_id (when cleared)

---

### 2.7 CashAccount

**Aggregate Root**: `CashAccount`
**Invariants**:
- CashAccount GL balance = Sum(cash transactions) per account
- Petty cash disbursements require a petty cash voucher

**Entities Within Aggregate**:
- `CashAccount` (root — each till or petty cash box)
- `CashTransaction` (receipts, payments, transfers to/from bank)
- `PettyCashVoucher` (individual petty cash disbursement records)
- `CashReconciliation` (physical count vs GL)

**Key Attributes (CashAccount)**:
- account_name (e.g., "Main Till", "Petty Cash Box 1")
- currency_code, gl_account_id
- current_balance (denormalized)
- is_petty_cash (bool)
- float_amount (target petty cash float)

---

### 2.8 Payment

**Aggregate Root**: `Payment`
**Invariants**:
- Payment amount must be positive
- Sum(allocations) ≤ payment_amount (no over-allocation)
- A cancelled payment cannot be allocated
- Payment to locked period is rejected

**Entities Within Aggregate**:
- `Payment` (root — covers both AR receipts and AP disbursements)
- `PaymentAllocationLine` (links payment to specific invoices/bills)
- `PaymentRefund` (refund of a prior payment)

**Key Attributes (Payment)**:
- payment_type (CUSTOMER_RECEIPT / SUPPLIER_DISBURSEMENT / ADVANCE_RECEIPT / ADVANCE_PAYMENT)
- payment_method (CASH / BANK_TRANSFER / CHEQUE / CARD / ONLINE)
- payment_date
- currency_code, exchange_rate
- amount_foreign, amount_base
- bank_account_id or cash_account_id
- party_type (CUSTOMER / SUPPLIER), party_id
- reference, notes
- status (DRAFT / POSTED / ALLOCATED / CANCELLED)
- journal_entry_id (GL cross-reference)
- cheque_id (nullable — if payment is by cheque)
- discount_amount (early payment discount taken)

---

### 2.9 TaxManagement

**Aggregate Root**: `TaxCode`
**Invariants**:
- Tax code is unique per company
- A tax code's effective date ranges cannot overlap for the same code
- Tax calculations use the rate effective on the transaction date

**Entities Within Aggregate**:
- `TaxCode` (root)
- `TaxRate` (rate history per code — effective date ranges)
- `TaxGroup` (collection of tax codes applied together)
- `TaxGroupLine` (membership of a tax code in a tax group)

**Key Attributes (TaxCode)**:
- tax_code, tax_name
- tax_type (SALES_TAX / VAT / GST / WITHHOLDING / COMPOUND / EXEMPT / ZERO_RATED / OUT_OF_SCOPE)
- applicability (SALES / PURCHASES / BOTH)
- gl_account_id (tax liability/asset GL account)
- is_input_tax_recoverable (bool — for VAT/GST input credit)
- country_code (nullable — for jurisdiction filtering)
- is_active

**Entities Outside Accounting (Reference Data)**:
- CostCenter, Department, Project — these entities are owned by a future Cost Accounting sub-module within the Accounting domain. They are referenced (not owned) by GL journal lines and payment records.

---

## 3. Value Objects

Value objects are immutable; they carry no identity. They are embedded in aggregate entities.

| Value Object | Fields | Used By |
|-------------|--------|---------|
| `Money` | amount (Decimal), currency_code (str) | All financial transactions |
| `ExchangeRate` | from_currency, to_currency, rate (Decimal), rate_date | JournalEntry, Payment, ARTransaction |
| `AccountCode` | code (str) — validated format | Account |
| `FiscalPeriodReference` | fiscal_year_id, period_number, period_name | JournalEntry |
| `TaxAmount` | tax_code, base_amount, tax_rate, tax_amount | JournalLine (automated tax posting) |
| `AllocationAmount` | allocated_amount_foreign, allocated_amount_base | ARPaymentAllocation, APPaymentAllocation |
| `DateRange` | start_date, end_date (inclusive) | FiscalPeriod, TaxRate |
| `PostingReference` | source_type, source_id, source_number | JournalEntry (drilldown linkage) |
| `AuditStamp` | created_at, created_by, updated_at, updated_by | All entities |
| `AddressSnapshot` | used when storing address on financial documents | Not used in GL (reference only) |

---

## 4. Domain Services

### 4.1 PostingEngine

The central domain service. All GL postings go through this service.

**Responsibilities**:
1. Validate journal balance (sum debits == sum credits)
2. Validate all accounts exist, are active, and are leaf accounts
3. Validate posting date falls in an OPEN fiscal period
4. Validate cost center assignment per account requirement
5. Validate approval status (if approval required by threshold)
6. Assign journal number (gap-free via advisory lock on `accounting_sequences`)
7. Insert `JournalEntry` + `JournalLine` records atomically
8. Update denormalized balance columns (bank, cash, AR outstanding, AP outstanding)
9. Write audit record
10. Publish `accounting.journal.posted` domain event

**Input**: `PostingRequest` (journal type, lines, date, reference, source document)
**Output**: `PostingResult` (journal_entry_id, journal_number, posted_at)
**Error**: `PostingValidationError` (with specific validation failure reason)

---

### 4.2 TaxCalculator

Computes tax on a transaction line based on the applicable tax code.

**Responsibilities**:
1. Resolve effective tax rate for the tax code on the transaction date
2. Determine tax base amount (exclusive or inclusive pricing)
3. Calculate tax amount with configured rounding rule
4. Return `TaxAmount` value object for each applicable tax code/group
5. For WHT: calculate deductible amount and return separate WHT posting amounts

**Input**: `TaxCalculationRequest` (tax_code_or_group_id, base_amount, transaction_date, currency)
**Output**: `TaxCalculationResult` (list of `TaxAmount` value objects)

---

### 4.3 AllocationEngine

Manages payment-to-invoice allocation (AR) and payment-to-bill allocation (AP).

**Responsibilities**:
1. Validate allocation amount does not exceed payment available balance
2. Validate allocation amount does not exceed invoice/bill outstanding balance
3. Create `ARPaymentAllocation` / `APPaymentAllocation` records
4. Update outstanding amounts on invoices/bills (denormalized)
5. Mark invoice/bill as PAID or PARTIALLY_PAID based on remaining balance
6. Calculate and post early payment discount GL entry (if discount amount > 0)
7. Calculate and post realized exchange gain/loss (if currency differs)
8. Publish allocation event

**Input**: `AllocationRequest` (payment_id, allocation_lines: [{transaction_id, amount, discount}])
**Output**: `AllocationResult` (updated outstanding amounts, gain/loss amounts)

---

### 4.4 AgingCalculator

Computes AR/AP aging buckets for reporting.

**Responsibilities**:
1. Query all open AR/AP transactions for a company as of a given date
2. Calculate days overdue: max(0, date − due_date) per transaction
3. Bucket transactions: Current / 1-30 / 31-60 / 61-90 / 91-120 / 120+ days
4. Aggregate by customer/supplier and in total
5. Return structured aging report data

---

### 4.5 CurrencyRevaluationService

Executes period-end revaluation of open foreign currency balances.

**Responsibilities**:
1. Identify all open foreign currency AR/AP transactions
2. Compare booking rate to current revaluation rate
3. Calculate unrealized gain/loss per transaction
4. Create one aggregated `JournalEntry` via PostingEngine for all unrealized differences
5. Mark transactions as revalued at the new rate
6. Generate revaluation report data

---

### 4.6 FinancialStatementService

Generates financial statements from the GL.

**Responsibilities**:
1. **Trial Balance**: Aggregate GL lines by account for a period; return debit/credit totals
2. **Balance Sheet**: Aggregate asset, liability, equity accounts as of a date
3. **P&L**: Aggregate revenue and expense accounts for a period
4. **Cash Flow**: Indirect method — start with net income, adjust for non-cash and working capital changes
5. Support comparative periods (current vs prior)
6. Apply account group hierarchy for presentation

---

### 4.7 RecurringJournalScheduler

Manages recurring journal entry execution.

**Responsibilities**:
1. Query due recurring journal templates (next_run_date <= today)
2. For each due template: create a `JournalEntry` via PostingEngine
3. Record the instance in `recurring_journal_instances`
4. Advance `next_run_date` based on frequency
5. Handle end-date reached (deactivate template)
6. Log scheduler execution result

---

## 5. Application Services

Application services orchestrate use cases, calling domain services and repositories.

| Service Class | Key Operations |
|--------------|----------------|
| `ChartOfAccountsService` | CreateAccount, UpdateAccount, ActivateAccount, DeactivateAccount, GetCOATree, BulkImportCOA |
| `FiscalCalendarService` | CreateFiscalYear, OpenPeriod, LockPeriod, UnlockPeriod, ClosePeriod, YearEndClose, SetupOpeningBalances |
| `JournalEntryService` | CreateJournal, SubmitForApproval, ApproveJournal, RejectJournal, PostJournal, ReverseJournal, GetJournal, SearchJournals |
| `RecurringJournalService` | CreateTemplate, UpdateTemplate, ActivateTemplate, DeactivateTemplate, ExecuteDue, GetTemplates |
| `AccountsReceivableService` | GetCustomerLedger, GetCustomerAging, GetCustomerStatement, SetCreditLimit, PlaceCreditHold, ReleaseCreditHold, WriteOffReceivable, AdjustReceivable |
| `AccountsPayableService` | GetSupplierLedger, GetSupplierAging, GetSupplierStatement, ReconcileSupplierStatement, AdjustPayable |
| `PaymentService` | CreateCustomerPayment, CreateSupplierPayment, AllocatePayment, ReallocatePayment, CancelPayment, ProcessRefund, GetPayment |
| `BankAccountService` | CreateBankAccount, UpdateBankAccount, StartReconciliation, ImportStatementLines, AutoMatchLines, ManualMatchLines, CompleteReconciliation, GetBankBook |
| `CashAccountService` | CreateCashAccount, RecordCashReceipt, RecordCashPayment, CreatePettyCashVoucher, ReplenishPettyCash, ReconcileCash, GetCashBook |
| `TaxService` | CreateTaxCode, UpdateTaxRate, CreateTaxGroup, GetTaxReport, GetVATReturn, GetWHTReport |
| `CurrencyService` | CreateCurrency, SetExchangeRate, GetExchangeRates, RunRevaluation, GetRevaluationReport |
| `CostCenterService` | CreateCostCenter, UpdateCostCenter, GetCostCenterReport, CreateDepartment, CreateProject |
| `ReportingService` | GetTrialBalance, GetBalanceSheet, GetProfitAndLoss, GetCashFlowStatement, GetGLReport, GetJournalReport, GetTaxReport, GetFinancialKPIs |
| `IntegrationEventHandlerService` | HandleSalesInvoicePosted, HandleSalesCreditNotePosted, HandlePurchaseBillPosted, HandlePurchaseCreditNotePosted, HandleInventoryAdjustmentPosted |

---

## 6. Repositories

All repositories follow the pattern from Epics 5–7:
- Injected via FastAPI dependency injection
- Async SQLAlchemy sessions
- Every query includes `company_id` filter
- Base class provides soft-delete, audit stamp utilities

| Repository | Primary Operations |
|------------|-------------------|
| `AccountRepository` | find_by_code, find_by_type, get_coa_tree, find_active_leaf_accounts |
| `FiscalYearRepository` | find_current, find_by_year, get_periods, find_open_period_for_date |
| `JournalEntryRepository` | find_by_number, search (date/account/cost_center/source), find_by_source_document |
| `CustomerLedgerRepository` | find_by_customer, get_open_transactions, get_aging_data, get_statement_data |
| `SupplierLedgerRepository` | find_by_supplier, get_open_transactions, get_aging_data, get_statement_data |
| `PaymentRepository` | find_by_party, get_unallocated_payments, find_by_date_range |
| `BankAccountRepository` | find_by_company, find_by_gl_account, get_reconciliation_history |
| `BankReconciliationRepository` | find_current, find_by_period, get_matched_items |
| `CashAccountRepository` | find_by_company, get_petty_cash_accounts |
| `TaxCodeRepository` | find_by_code, find_active_by_type, find_applicable (sales/purchase) |
| `ExchangeRateRepository` | get_rate (currency, date), get_rates_for_period |
| `CostCenterRepository` | find_by_company, get_hierarchy |
| `RecurringJournalRepository` | find_due (next_run_date <= today), find_by_template_id |
| `GLReportRepository` | (read-optimized) trial_balance_query, gl_detail_query, account_balance_query |

---

## 7. Domain Events

### 7.1 Events Published by Accounting

All events follow the pattern: `accounting.<aggregate>.<past_tense_verb>`

| Event | Trigger | Payload |
|-------|---------|---------|
| `accounting.journal.posted` | JournalEntry status → POSTED | journal_id, journal_number, posting_date, total_debit, source |
| `accounting.journal.reversed` | Reversal entry posted | original_journal_id, reversal_journal_id |
| `accounting.period.locked` | FiscalPeriod status → LOCKED | company_id, fiscal_year_id, period_id, period_start, period_end |
| `accounting.period.unlocked` | FiscalPeriod status → OPEN (from LOCKED) | company_id, period_id, unlocked_by, reason |
| `accounting.period.closed` | FiscalPeriod status → CLOSED | company_id, period_id |
| `accounting.fiscalyear.closed` | FiscalYear status → CLOSED | company_id, fiscal_year_id, closing_entry_id |
| `accounting.payment.received` | Customer payment posted | payment_id, customer_id, amount, currency, payment_date |
| `accounting.payment.made` | Supplier payment posted | payment_id, supplier_id, amount, currency, payment_date |
| `accounting.ar.invoice.overdue` | Invoice past due_date | ar_transaction_id, customer_id, days_overdue, outstanding_amount |
| `accounting.ar.customer.credithold` | Customer credit hold placed | customer_id, reason, placed_by |
| `accounting.ar.customer.credithold.released` | Credit hold released | customer_id, released_by |
| `accounting.ar.customer.creditlimit.warning` | 80% of credit limit used | customer_id, current_outstanding, credit_limit, percentage |
| `accounting.ap.bill.due` | Bill approaching due date | ap_transaction_id, supplier_id, due_date, outstanding_amount |
| `accounting.bank.reconciled` | Bank reconciliation completed | bank_account_id, statement_date, statement_balance |
| `accounting.tax.return.due` | Tax period approaching due date | tax_code, period_end_date, net_tax_payable |
| `accounting.revaluation.completed` | Currency revaluation run | fiscal_period_id, total_gain_loss, journal_entry_id |
| `accounting.anomaly.detected` | (Future AI) Anomaly flagged | anomaly_type, entity_type, entity_id, severity |

### 7.2 Events Consumed by Accounting

| Event (from) | Handler | GL Posting Created |
|-------------|---------|-------------------|
| `sales.invoice.posted` (Epic 7) | HandleSalesInvoicePosted | DR Accounts Receivable / CR Revenue / CR Tax Liability |
| `sales.creditnote.posted` (Epic 7) | HandleSalesCreditNotePosted | DR Revenue / DR Tax Liability / CR Accounts Receivable |
| `sales.payment.received` (Epic 7) | HandleCustomerPaymentReceived | DR Bank/Cash / CR Accounts Receivable |
| `purchase.bill.posted` (Epic 6) | HandlePurchaseBillPosted | DR Expense or Inventory / DR Input Tax / CR Accounts Payable |
| `purchase.creditnote.posted` (Epic 6) | HandlePurchaseCreditNotePosted | DR Accounts Payable / CR Expense / CR Input Tax |
| `purchase.payment.made` (Epic 6) | HandleSupplierPaymentMade | DR Accounts Payable / CR Bank/Cash |
| `inventory.adjustment.posted` (Epic 5) | HandleInventoryAdjustmentPosted | DR/CR Inventory Control / DR/CR Inventory Adjustment |
| `inventory.cost.updated` (Epic 5) | HandleInventoryCostUpdated | DR/CR Inventory Control / DR/CR COGS Adjustment |

All event handlers call the PostingEngine; no direct GL manipulation outside PostingEngine.

---

## 8. State Machines

### 8.1 JournalEntry Status

```
DRAFT ──(submit)──► SUBMITTED ──(approve)──► APPROVED ──(post)──► POSTED ──(reverse)──► POSTED
  │                    │                         │                    │
  │                 (recall)                  (reject)             (no modification allowed)
  │                    │                         │
  │                    ▼                         ▼
  └──(delete)──► [DELETED]                    REJECTED ──(revise)──► DRAFT
```

- POSTED entries are immutable. Reversal creates a NEW entry in DRAFT state.
- APPROVED entries require Controller/CFO role to reject or post.
- Auto-posting (from Sales/Purchase/Inventory events): entries skip DRAFT/SUBMITTED/APPROVED states and are directly POSTED.

### 8.2 FiscalPeriod Status

```
OPEN ──(lock)──► LOCKED ──(unlock, controller only)──► OPEN
  │                  │
  │              (close, after year-end close procedure)
  │                  │
  └──────────────────▼
                  CLOSED (terminal — no reversal)
```

### 8.3 BankReconciliation Status

```
DRAFT ──(begin matching)──► IN_PROGRESS ──(all matched)──► COMPLETED ──(confirm)──► LOCKED
                                │
                          (save partial)
                                │
                                ▼ (returns to IN_PROGRESS)
```

### 8.4 ARTransaction / APTransaction Status

```
OPEN ──(partial payment)──► PARTIALLY_PAID ──(full payment)──► PAID
  │                                │
  │                            (reversal)
  │                                │
  ├──(overdue flag, daily job)──► OVERDUE ──(payment)──► PAID
  │
  ├──(dispute)──► DISPUTED ──(resolve)──► OPEN
  │
  └──(write-off, approval required)──► WRITTEN_OFF (terminal)
```

### 8.5 Cheque Status

```
ISSUED ──(bank clears)──► PRESENTED ──(final clearing)──► CLEARED
  │
  └──(cancel before clearing)──► CANCELLED
  └──(not cleared within stale period)──► STALE
```

### 8.6 CustomerLedger Credit Status

```
GOOD ──(80% limit)──► WARNING ──(100%+ limit)──► EXCEEDED ──(manual hold)──► HOLD
  ▲                      │                           │                          │
  └──(payment reduces)───┘                           └──────────────────────────┘
                                                      (payment reduces balance)
```

---

## 9. Entity Relationships

```
Company (Epic 3)
  ├── 1:N ──► Account (Chart of Accounts)
  │             └── self-referencing hierarchy (parent_account_id)
  │
  ├── 1:N ──► FiscalYear
  │             └── 1:N ──► FiscalPeriod
  │             └── 1:N ──► OpeningBalance (per account)
  │
  ├── 1:N ──► JournalEntry
  │             └── 1:N ──► JournalLine (min 2 per entry)
  │             └── 0:1 ──► JournalApproval
  │             └── 0:N ──► JournalAttachment
  │
  ├── 1:N ──► CustomerLedger (one per customer)
  │             └── 1:N ──► ARTransaction
  │                          └── 0:N ──► ARPaymentAllocation
  │
  ├── 1:N ──► SupplierLedger (one per supplier)
  │             └── 1:N ──► APTransaction
  │                          └── 0:N ──► APPaymentAllocation
  │
  ├── 1:N ──► BankAccount
  │             └── 1:N ──► BankTransaction
  │             └── 1:N ──► BankStatementLine
  │             └── 1:N ──► BankReconciliation
  │                          └── 1:N ──► BankReconciliationMatch
  │             └── 1:N ──► Cheque
  │
  ├── 1:N ──► CashAccount
  │             └── 1:N ──► CashTransaction
  │             └── 1:N ──► PettyCashVoucher
  │             └── 1:N ──► CashReconciliation
  │
  ├── 1:N ──► Payment
  │             └── 1:N ──► PaymentAllocationLine
  │             └── 0:N ──► PaymentRefund
  │
  ├── 1:N ──► TaxCode
  │             └── 1:N ──► TaxRate (rate history)
  │
  ├── 1:N ──► TaxGroup
  │             └── 1:N ──► TaxGroupLine
  │
  ├── 1:N ──► Currency (global, shared across companies)
  │             └── 1:N ──► ExchangeRate (per currency per date)
  │
  ├── 1:N ──► CostCenter
  │             └── 1:N ──► Department
  │
  ├── 1:N ──► Project
  │
  └── 1:N ──► RecurringJournalTemplate
                └── 1:N ──► RecurringJournalInstance
```

---

## 10. Aggregate Boundaries

Aggregates never directly reference internal entities of another aggregate. Cross-aggregate references use IDs only.

| From Aggregate | References (ID only) | Reasoning |
|----------------|----------------------|-----------|
| JournalEntry | account_id, fiscal_period_id, cost_center_id | GL lines reference accounts by ID; no Account object embedded in JournalLine |
| CustomerLedger | customer_id (Epic 7 reference) | Customer data owned by Sales domain; ledger holds ID only |
| SupplierLedger | supplier_id (Epic 6 reference) | Supplier data owned by Purchase domain |
| ARTransaction | journal_entry_id | GL entry exists in JournalEntry aggregate; referenced by ID |
| Payment | bank_account_id, cash_account_id, party_id | Cross-aggregate by ID |
| BankAccount | gl_account_id | Account in COA aggregate; referenced by ID |
| CashAccount | gl_account_id | Same |
| TaxCode | gl_account_id | Tax posting account referenced by ID |

---

## 11. Database Tables (Conceptual)

*No SQL — only logical table names and key columns for migration planning.*

### Foundation Tables

| Table | Purpose |
|-------|---------|
| `accounting_currencies` | ISO 4217 currency registry (shared, not company-scoped) |
| `accounting_exchange_rates` | Exchange rate per currency pair per date |
| `accounting_configurations` | Company-level accounting settings (base currency, approval thresholds) |
| `accounting_sequences` | Advisory lock table for gap-free journal numbering (per company) |
| `accounting_feature_flags` | Accounting-specific feature flags (extends company_feature_flags) |

### Chart of Accounts

| Table | Purpose |
|-------|---------|
| `accounting_account_groups` | Account group hierarchy (self-referencing) |
| `accounting_accounts` | Full chart of accounts (leaf and parent nodes) |

### Fiscal Calendar

| Table | Purpose |
|-------|---------|
| `accounting_fiscal_years` | Fiscal year definitions per company |
| `accounting_fiscal_periods` | Period definitions per fiscal year (OPEN/LOCKED/CLOSED) |
| `accounting_opening_balances` | Opening balance amounts per account per fiscal year |

### General Ledger

| Table | Purpose |
|-------|---------|
| `accounting_journal_entries` | Header record per journal (status, type, source, date) |
| `accounting_journal_lines` | Individual debit/credit lines (append-only, never updated/deleted) |
| `accounting_journal_approvals` | Approval records per journal entry |
| `accounting_journal_attachments` | Document attachment references per journal |

### Recurring Journals

| Table | Purpose |
|-------|---------|
| `accounting_recurring_templates` | Recurring journal schedule and template lines |
| `accounting_recurring_template_lines` | Template line items (account, debit/credit, amount) |
| `accounting_recurring_instances` | Audit trail of all executed recurring journal instances |

### Accounts Receivable

| Table | Purpose |
|-------|---------|
| `accounting_customer_ledgers` | One record per customer per company (AR master) |
| `accounting_ar_transactions` | All AR events: invoices, credits, payments, adjustments |
| `accounting_ar_allocations` | Payment-to-invoice allocation records |
| `accounting_customer_credit_history` | Credit limit and hold event log |

### Accounts Payable

| Table | Purpose |
|-------|---------|
| `accounting_supplier_ledgers` | One record per supplier per company |
| `accounting_ap_transactions` | All AP events: bills, credits, payments, adjustments |
| `accounting_ap_allocations` | Payment-to-bill allocation records |
| `accounting_supplier_reconciliations` | Statement reconciliation sessions |
| `accounting_supplier_reconciliation_items` | Per-line reconciliation items |

### Banking

| Table | Purpose |
|-------|---------|
| `accounting_bank_accounts` | Bank account register per company |
| `accounting_bank_transactions` | GL-side bank transactions (receipts, payments, transfers) |
| `accounting_bank_statement_lines` | Imported bank statement lines |
| `accounting_bank_reconciliations` | Reconciliation session per bank account per period |
| `accounting_bank_reconciliation_matches` | Matched pairs of GL transactions and statement lines |
| `accounting_cheques` | Issued cheque register |

### Cash

| Table | Purpose |
|-------|---------|
| `accounting_cash_accounts` | Cash account / till / petty cash box register |
| `accounting_cash_transactions` | Cash receipts and payments |
| `accounting_petty_cash_vouchers` | Petty cash disbursement vouchers |
| `accounting_cash_reconciliations` | Physical count vs GL reconciliation records |

### Payments

| Table | Purpose |
|-------|---------|
| `accounting_payments` | Payment header (customer receipts and supplier disbursements) |
| `accounting_payment_allocation_lines` | Allocation of payment amount to invoices/bills |
| `accounting_payment_refunds` | Refund records linked to original payments |

### Tax

| Table | Purpose |
|-------|---------|
| `accounting_tax_codes` | Tax code definitions |
| `accounting_tax_rates` | Rate history per code (effective date ranges) |
| `accounting_tax_groups` | Tax group definitions |
| `accounting_tax_group_lines` | Tax codes within each group |

### Cost Accounting

| Table | Purpose |
|-------|---------|
| `accounting_cost_centers` | Cost center definitions |
| `accounting_departments` | Department definitions |
| `accounting_projects` | Project definitions |

### Audit

| Table | Purpose |
|-------|---------|
| `accounting_audit_log` | Immutable audit trail for all accounting events |

---

## 12. Migration Strategy

### Alembic Migration Sequence

The accounting module introduces migrations starting at **034** (following Epic 7's 033):

| Migration | Name | Phase |
|-----------|------|-------|
| 034 | `accounting_foundation` | Phase 1 |
| 035 | `accounting_currencies_rates` | Phase 1 |
| 036 | `accounting_chart_of_accounts` | Phase 2 |
| 037 | `accounting_fiscal_calendar` | Phase 3 |
| 038 | `accounting_general_ledger` | Phase 4 |
| 039 | `accounting_recurring_journals` | Phase 4 |
| 040 | `accounting_ar_ledger` | Phase 5 |
| 041 | `accounting_ap_ledger` | Phase 6 |
| 042 | `accounting_banking` | Phase 7 |
| 043 | `accounting_cash_management` | Phase 8 |
| 044 | `accounting_payments` | Phase 9 |
| 045 | `accounting_tax_engine` | Phase 10 |
| 046 | `accounting_cost_centers` | Phase 10 |
| 047 | `accounting_audit_indexes` | Phase 11 |

### Migration Rules

All accounting migrations must:
1. Include `tenant_id` and `company_id` on every business table
2. Include a composite unique index on `(tenant_id, company_id, <business_key>)` for all entities with business keys
3. Include soft-delete columns on all non-financial entities
4. Include `created_at`, `created_by_user_id`, `updated_at`, `updated_by_user_id` on all tables
5. **NOT** include soft-delete on `accounting_journal_lines`, `accounting_audit_log` (these are immutable/append-only)
6. Be fully reversible (downgrade migration provided)
7. Pass `alembic upgrade head` and `alembic downgrade -1` in Docker without errors

### Index Strategy (Conceptual)

- `accounting_journal_lines`: Covering index on `(company_id, account_id, posting_date)` — primary GL query pattern
- `accounting_journal_lines`: Covering index on `(company_id, fiscal_period_id, account_id)` — trial balance query
- `accounting_ar_transactions`: Index on `(company_id, customer_id, status, due_date)` — aging query
- `accounting_ap_transactions`: Index on `(company_id, supplier_id, status, due_date)` — aging query
- `accounting_bank_statement_lines`: Index on `(bank_account_id, transaction_date, amount)` — reconciliation matching
- `accounting_exchange_rates`: Index on `(from_currency, to_currency, rate_date DESC)` — rate lookup
- Full-text search index on `accounting_journal_entries.description` — GL search
