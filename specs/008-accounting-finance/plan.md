# Implementation Plan: Epic 8 — Accounting & Finance

**Branch**: `008-accounting-finance` | **Date**: 2026-08-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-accounting-finance/spec.md` (v1.0)
**Research**: [research.md](./research.md) | **Data Model**: [data-model.md](./data-model.md)

---

## Summary

Epic 8 implements the **complete Accounting & Finance domain** — the financial backbone of DevSphere ERP. It transforms all business transactions from Sales (Epic 7), Purchase (Epic 6), and Inventory (Epic 5) into a double-entry general ledger that produces real-time, auditable financial statements.

The implementation strategy is **12 sequential phases**, progressing from module scaffolding through Chart of Accounts, Fiscal Calendar, General Ledger, Accounts Receivable, Accounts Payable, Banking, Cash Management, Payments, Tax Engine, Financial Reporting, and Epic Closure. Every phase is independently testable and delivers demonstrable business value. No phase begins until the previous phase passes its exit criteria.

The architecture mirrors Epics 5–7: Clean Architecture with strict layer separation, Repository Pattern with mandatory `company_id` isolation, domain events via `InProcessEventBus`, and feature flags for all optional capabilities.

**The critical architectural constraint**: ALL GL postings flow through a single `PostingEngine` domain service. No code path — manual journal, automated event handler, bank reconciliation, or recurring journal — writes to the GL without going through this engine. This is the non-negotiable integrity guarantee of the Accounting module.

The most architecturally significant components are: (1) the **PostingEngine** — the central posting gate enforcing double-entry, period locks, and account validation; (2) the **AllocationEngine** — managing payment-to-invoice matching; and (3) the **FinancialStatementService** — generating real-time Balance Sheet, P&L, and Cash Flow from GL aggregation.

---

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI 0.115+, Pydantic v2, SQLAlchemy 2.x (async), Alembic, APScheduler (recurring journals), Next.js 15 (App Router), TailwindCSS, shadcn/ui
**Storage**: PostgreSQL 16 LTS (Docker Compose in dev; Neon PostgreSQL in production)
**Testing**: pytest + pytest-asyncio (backend), Jest + React Testing Library (frontend)
**Target Platform**: Linux server (Docker), browser (Next.js SSR + CSR)
**Project Type**: Web application — FastAPI backend + Next.js frontend
**Performance Goals**: Trial balance < 10s (500K entries); financial statements < 15s; GL search < 5s; journal posting < 1s; customer aging < 5s; payment processing < 2s
**Constraints**: company_id isolation on every query; GL entries are append-only and immutable after posting; double-entry enforced at application AND database layers; period lock enforced across all modules; all monetary amounts use Decimal (never float); soft-delete on all non-financial entities; audit trail synchronous within same DB transaction
**Scale/Scope**: 5,000,000 GL entries per company; 500 concurrent financial users per tenant; 100,000 customers/suppliers per tenant; all ISO 4217 currencies

---

## Constitution Check

*GATE: Must pass before Phase 1 implementation. Re-checked after design phase.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Clean Architecture layering | PASS | Domain / Application / Infrastructure / API — zero cross-layer dependency violations; PostingEngine is domain service |
| Multi-tenancy (company_id everywhere) | PASS | Repository base class enforces company_id on every query; GL lines include company_id for direct query safety |
| Soft delete on non-financial entities | PASS | is_deleted + deleted_at + deleted_by on all master data; GL entries and audit log are append-only (no soft-delete needed) |
| Audit trail completeness | PASS | Synchronous write within same DB transaction on every financial state change; immutable audit log |
| Repository Pattern | PASS | No direct DB access from Application or Domain layers; PostingEngine is the sole GL writer |
| DDD Aggregate Roots | PASS | 9 Aggregate Roots: Account, FiscalYear, JournalEntry, CustomerLedger, SupplierLedger, BankAccount, CashAccount, Payment, TaxCode |
| Feature Flag strategy | PASS | Company-scoped DB table; reuses FeatureFlagService from Epic 5 pattern; 8 accounting feature flags |
| No hardcoded secrets | PASS | All config via environment variables |
| No circular dependencies | PASS | Domain has zero framework dependencies; PostingEngine does not import from Application layer |
| Immutability of posted GL entries | PASS | No UPDATE/DELETE on accounting_journal_lines; DB constraint + PostingEngine enforce this |
| Append-only GL design | PASS | Corrections via reversal entries only; original entries permanently visible |
| Epic 4 RBAC integration | PASS | Permission identifiers follow `accounting.<resource>.<action>` pattern |
| Epic 5/6/7 integration | PASS | Events from Sales, Purchase, Inventory consumed via InProcessEventBus; PostingEngine creates GL entries |
| Self-approval prevention | PASS | Domain invariant: approver_id != requestor_id for journal approvals |
| Backward compatibility | PASS | Epics 1–7 interfaces consumed; no modifications to prior epic code beyond event subscription registration |
| Monetary precision | PASS | All monetary amounts stored as `Decimal` (Python) and `numeric(20,6)` (DB); never float |
| Double-entry invariant | PASS | PostingEngine validates SUM(debit) == SUM(credit) before every posting; DB trigger as backstop |
| Period lock cross-module | PASS | `accounting.period.locked` event published via InProcessEventBus; all posting modules subscribe |

**Constitution Check Result: ALL PASS — Phase 1 implementation approved to proceed.**

---

## Project Structure

### Documentation (this feature)

```text
specs/008-accounting-finance/
├── spec.md              # Official SSOT — Epic 8 specification v1.0
├── plan.md              # This file — implementation blueprint
├── research.md          # Phase 0 architecture decisions resolved
├── data-model.md        # Aggregates, state machines, entity relationships, migration strategy
├── quickstart.md        # Developer quickstart guide
├── contracts/
│   ├── events.md        # Domain event contracts (inbound + outbound)
│   └── accounting-v1.yaml   # OpenAPI spec (generated in Phase 12)
├── checklists/
│   └── requirements.md  # Spec quality checklist — all items PASS
└── tasks.md             # /sp.tasks output — NOT created by /sp.plan
```

### Source Code (repository root)

```text
backend/
├── modules/
│   └── accounting/
│       ├── models/               # SQLAlchemy ORM models (all accounting entities)
│       ├── schemas/              # Pydantic v2 request/response schemas
│       ├── repositories/         # Concrete async repository implementations
│       ├── services/             # Application services (one per sub-domain)
│       │   ├── posting_engine.py        # PostingEngine domain service (the GL gate)
│       │   ├── allocation_engine.py     # Payment allocation domain service
│       │   ├── tax_calculator.py        # Tax calculation domain service
│       │   ├── aging_calculator.py      # AR/AP aging calculator
│       │   ├── financial_statements.py  # Financial statement generator
│       │   ├── currency_revaluation.py  # Period-end revaluation service
│       │   └── recurring_scheduler.py   # Recurring journal scheduler (APScheduler)
│       ├── events/               # Domain event class definitions (17+ events)
│       ├── handlers/             # Integration event handlers (consumes Epic 5/6/7 events)
│       ├── dependencies.py       # FastAPI dependency injection
│       ├── constants.py          # Accounting-specific constants and enums
│       └── router.py             # FastAPI router — accounting endpoints
│
└── migrations/
    └── versions/
        └── [0xx]_accounting_*.py    # Alembic migrations 034–047

frontend/
├── src/
│   └── app/
│       └── (protected)/
│           └── (accounting)/
│               ├── chart-of-accounts/    # COA management pages
│               ├── fiscal-calendar/      # Fiscal year/period management
│               ├── journals/             # Journal entry management
│               ├── gl-report/            # General Ledger report
│               ├── receivables/          # AR management pages
│               ├── payables/             # AP management pages
│               ├── banking/              # Bank account + reconciliation
│               ├── cash/                 # Cash management
│               ├── payments/             # Payment processing
│               ├── tax/                  # Tax configuration
│               ├── cost-centers/         # Cost center management
│               ├── reports/              # Financial statements + reports
│               └── dashboard/            # CFO financial KPI dashboard
│   └── components/
│       └── accounting/                   # Reusable accounting UI components
│   └── lib/
│       └── api/
│           └── accounting.ts             # API client for accounting endpoints

backend/tests/
├── unit/modules/accounting/              # Domain + application layer unit tests
├── integration/repositories/accounting/  # Repository + service integration tests
├── integration/api/v1/accounting/        # FastAPI endpoint tests
├── security/accounting/                  # Security + RBAC tests
└── performance/accounting/               # Performance benchmarks
```

**Structure Decision**: Modular monolith pattern consistent with Epics 1–7. Accounting module isolated within `backend/modules/accounting/` following the same structure as `backend/modules/sales/` and `backend/modules/purchase/`. No new infrastructure components required — reuses auth, company context, RBAC, audit logging, and FeatureFlagService established in prior epics. APScheduler added for recurring journal execution (in-process; no Redis/Celery required).

---

## Complexity Tracking

| Decision | Why Needed | Simpler Alternative Rejected Because |
|----------|------------|--------------------------------------|
| PostingEngine as single GL gate | All 9 posting paths (manual, Sales, Purchase, Inventory, bank, cash, payment, reversal, recurring) must satisfy identical invariants | Per-path invariant enforcement multiplies code; one unguarded path breaks ledger integrity |
| Append-only GL with no soft-delete | Regulatory requirement: financial records must be immutable | Soft-delete flag can be bypassed; structural append-only cannot |
| Dual-layer balance validation (app + DB) | DB constraint as backstop for admin access and migration edge cases | App-only validation: direct DB access or buggy migration could break ledger balance |
| AllocationEngine with separate allocation table | Partial payments, re-allocation, reversal without modifying original payment/invoice | Single-table allocation: concurrent payments to same invoice cause race conditions; re-allocation requires data mutation |
| Statement-first bank reconciliation | Matches accountant workflow; statement lines are the reference; GL items must be reconciled to statement | GL-first: hard to see what is on statement but not in GL; timing differences invisible |
| RecurringJournalScheduler with APScheduler | Spec requires automatic execution on schedule without manual trigger | Cron: adds operational complexity; external cron lacks application context for error handling |
| Real-time financial statement aggregation | CFO must see current state at any moment | Pre-computed statements: invalidation logic complex; stale during heavy posting |
| Tax engine with jurisdiction adapters | Country-specific rules change frequently; pluggable adapters allow rate/rule updates without code deploy | Hardcoded country rules: every tax rate change requires code change and deployment |

---

## Implementation Strategy

Epic 8 follows **12 sequential phases** organized by financial domain dependency order. Each phase delivers a complete working vertical slice: domain entity → repository → application service → API endpoint → frontend screen → tests.

### Delivery Philosophy

1. **PostingEngine First** — The PostingEngine is built and hardened in Phase 4 before any AR/AP/Payment/Banking work. All subsequent phases call the engine; they never write to the GL directly.
2. **Invariant-Driven Testing** — Every phase includes tests for the specific financial invariants it introduces. No phase is complete until the invariants (balanced GL, AR/AP reconciliation, period lock) are verified in tests.
3. **Feature Toggle Wrapping** — All optional capabilities (multi-currency, cost centers, approval workflows, WHT) are wrapped in feature flags from day 1.
4. **Integration Event Contract Respect** — Accounting is the downstream consumer of Sales, Purchase, and Inventory events. Event handler tests verify the correct GL entries are created for every source event.
5. **Immutability Never Compromised** — No test helper, fixture, or migration is ever permitted to directly UPDATE or DELETE `accounting_journal_lines`. Reversal is always the path.

### Phase Dependencies

```
Phase 1 (Foundation & Scaffolding)
  └── Phase 2 (Chart of Accounts)
        └── Phase 3 (Fiscal Calendar)
              └── Phase 4 (General Ledger & PostingEngine)
                    ├── Phase 5 (Accounts Receivable)
                    │     └── Phase 9 (Payments)
                    ├── Phase 6 (Accounts Payable)
                    │     └── Phase 9 (Payments)
                    ├── Phase 7 (Banking)
                    │     └── Phase 9 (Payments)
                    └── Phase 8 (Cash Management)
                          └── Phase 9 (Payments)
Phase 4 complete
  └── Phase 10 (Tax Engine & Cost Centers)
Phase 5–10 complete
  └── Phase 11 (Financial Reporting)
Phase 1–11 complete
  └── Phase 12 (Performance, Contracts & Epic Closure)
```

---

## Implementation Phases

---

### Phase 1: Accounting Module Foundation & Scaffolding

**Objective**: Establish the accounting module infrastructure — directory structure, router registration, feature flag registry, accounting configuration, currency setup, and all shared foundation components that subsequent phases depend on.

**Business Value**: No direct user-visible business value; establishes the platform on which all financial capabilities are built.

**Scope**:
- Accounting module scaffolding: directory structure, router registration, base schema classes, base repository class
- Accounting feature flag registry: all 8 feature flags registered with defaults in `company_feature_flags`
- Accounting configuration entity: base currency, approval thresholds, default fiscal year start month, cheque/bank settings
- Currency registry: ISO 4217 currency table (global, not company-scoped); initial seed of common currencies
- Exchange rate management: exchange rate table with currency pair + date; CRUD endpoints
- Journal number sequencing: advisory lock on `accounting_sequences` table; configurable format per company
- Accounting-specific audit logging integration (reuses Epic 5 audit pattern)
- APScheduler integration: startup registration for recurring journal job and daily AR/AP overdue check job
- API router registered at `/api/v1/companies/{company_id}/accounting/`

**Prerequisites**: Epics 1–7 complete; PostgreSQL 16 running; all prior migrations applied

**Dependencies**: Epic 1 (FastAPI scaffold), Epic 3 (company context), Epic 4 (RBAC), Epic 5 (FeatureFlagService pattern)

**Deliverables**:
- Accounting module registered in main router
- `company_feature_flags` table extended with 8 accounting flags
- `accounting_currencies` seed data (major ISO 4217 currencies)
- `accounting_exchange_rates` CRUD: GET /exchange-rates, POST /exchange-rates
- `accounting_configurations` CRUD: GET/PUT /accounting/configuration
- `accounting_sequences` foundation: journal number generation with advisory lock
- Alembic migrations: 034_accounting_foundation, 035_accounting_currencies_rates
- Frontend: Currency management screen, Accounting Configuration screen

**Acceptance Criteria**:
- [ ] Accounting module router responds at `/api/v1/companies/{company_id}/accounting/`
- [ ] Feature flag resolution works for all 8 accounting flags with correct defaults
- [ ] Journal number generation produces sequential, company-unique, prefix-formatted numbers under concurrent load (no gaps, no duplicates)
- [ ] Exchange rate CRUD functional: create, update, list rates by currency and date
- [ ] Base currency configuration enforced on company setup
- [ ] APScheduler starts up and registers jobs without errors

**Exit Criteria**: All unit, integration, and API tests pass; migrations 034–035 run clean; Docker compose up with no errors

**Risks**:
- Advisory lock contention under concurrent journal creation — mitigate with row-level lock on sequence record; test at 100 concurrent
- APScheduler conflicts with test isolation — use mock scheduler in tests; real scheduler only in production startup

**Estimated Complexity**: Medium

---

### Phase 2: Chart of Accounts

**Objective**: Implement the complete Chart of Accounts — hierarchical account structure, account types, account groups, COA templates, and account validation.

**Business Value**: Companies can define and maintain their financial taxonomy. The COA enables all GL postings to be categorized correctly. Without a COA, no financial transactions can be posted.

**Scope**:
- AccountGroup entity: hierarchical grouping with self-referencing parent; seeded with 5 types × standard groups
- Account entity: full attribute set per spec (code, name, type, group, currency, flags)
- COA tree management: parent-child relationships; hierarchy traversal for statement presentation
- Posting eligibility validation: only leaf accounts (is_leaf=true) can receive postings
- Account status lifecycle: Active → Inactive (if no current-year activity)
- COA templates: industry-specific default account structures (Retail, Manufacturing, Services, Construction, Medical, Generic)
- Bulk COA import (feature flag: `accounting.bulkimport.enabled`): CSV/Excel import with validation
- COA export: CSV/Excel
- System account configuration: designate AR control, AP control, bank, cash, retained earnings, exchange gain/loss, inventory control accounts

**Prerequisites**: Phase 1 complete

**Deliverables**:
- Domain entities: Account, AccountGroup
- Account aggregate with invariants (code uniqueness, leaf-only posting, active status)
- AccountRepository: find_by_code, find_by_type, get_coa_tree (recursive), find_active_leaf_accounts
- Application service: ChartOfAccountsService (CreateAccount, UpdateAccount, ActivateAccount, DeactivateAccount, GetCOATree, BulkImportCOA, SetSystemAccount)
- API endpoints: `/accounting/accounts` (CRUD), `/accounting/account-groups` (CRUD), `/accounting/system-accounts` (configuration)
- COA template seeder: 6 industry templates as seed data
- Alembic migration: 036_accounting_chart_of_accounts
- Frontend: COA tree view (expandable hierarchy), Account create/edit modal, System account configuration screen, Bulk import UI

**Acceptance Criteria**:
- [ ] Account code unique per company enforced at domain level
- [ ] Parent (non-leaf) accounts cannot be used for GL postings (PostingEngine rejects)
- [ ] Inactive accounts reject all new postings
- [ ] Account cannot be deactivated if it has GL activity in the current open fiscal year
- [ ] COA tree traversal returns correct parent-child relationships
- [ ] 6 industry COA templates load correctly with all accounts and groups
- [ ] Bulk import 500 accounts completes in < 30 seconds with row-level error reporting
- [ ] System account configuration validated: AR/AP/Bank/Cash/Retained Earnings must be correctly typed accounts
- [ ] All account operations scoped to company_id

**Exit Criteria**: All tests pass; COA tree renders correctly in UI; system account configuration verified; bulk import tested with 500-account dataset

**Risks**:
- COA hierarchy depth performance — index self-referencing tree; limit practical depth to 7 levels
- System account misconfiguration breaks all GL postings — validate type compatibility on configuration save

**Estimated Complexity**: Medium

---

### Phase 3: Fiscal Calendar

**Objective**: Implement fiscal year and period management, opening balance setup, and the period-end close procedure.

**Business Value**: Companies can configure their accounting year and periods. Period locking gives financial controllers the power to prevent unauthorized changes to closed periods. Opening balances enable existing businesses to migrate to the system.

**Scope**:
- FiscalYear aggregate: create, configure, activate as current year
- FiscalPeriod management: 12 monthly periods per year (configurable); period status lifecycle (OPEN → LOCKED → CLOSED)
- Period lock enforcement: PostingEngine must check period status; `accounting.period.locked` event published
- Period unlock (Controller authority required): LOCKED → OPEN with mandatory reason and audit
- Opening balance entry: journal entry type OPENING_BALANCE; validates across all accounts
- Year-end close process: procedure checklist, closing entry automation (net income → retained earnings)
- Next fiscal year initialization: create with correct opening balances from prior year closing

**Prerequisites**: Phase 2 complete (COA must exist for opening balances)

**Deliverables**:
- FiscalYear and FiscalPeriod domain entities with state machines
- FiscalYearRepository, FiscalPeriodRepository
- Application service: FiscalCalendarService
- Period lock event publisher: `accounting.period.locked` → all modules subscribe
- Opening balance service: batch-validates and posts OPENING_BALANCE journal
- Year-end close service: validates all periods locked, posts closing entry
- Alembic migration: 037_accounting_fiscal_calendar
- Frontend: Fiscal Year management screen, Period status dashboard (lock/unlock controls), Opening Balance entry screen, Year-End Close wizard

**Acceptance Criteria**:
- [ ] Fiscal periods cover the full fiscal year with no gaps or overlaps
- [ ] Period lock status checked by PostingEngine on every posting attempt
- [ ] Locked period posting rejected with clear error message (HTTP 422)
- [ ] `accounting.period.locked` event published to InProcessEventBus on lock
- [ ] Opening balance journal must balance: sum of all account opening balances net to zero
- [ ] Period unlock requires Controller role; reason is mandatory; audit record created
- [ ] CLOSED period cannot be unlocked under any circumstance
- [ ] Year-end close creates correct retained earnings transfer entry

**Exit Criteria**: All state transitions tested; period lock enforcement verified across PostingEngine; opening balance tested with 200-account set; year-end close tested end-to-end

**Risks**:
- Period lock event delivery timing — InProcessEventBus delivers synchronously before HTTP response; no timing gap
- Opening balance imbalance — validate total debits == total credits before committing

**Estimated Complexity**: Medium

---

### Phase 4: General Ledger & PostingEngine

**Objective**: Implement the PostingEngine domain service, manual journal entry lifecycle, recurring journal templates, journal reversal, and the GL query/report interface. This is the most critical phase of the entire epic.

**Business Value**: Accountants can create, approve, and post manual journal entries. GL entries from all sources are unified in one queryable ledger. Recurring entries automate periodic accruals. The foundation for all financial reporting is now live.

**Scope**:
- **PostingEngine** (core): validation pipeline (balance, accounts, period, cost center, approval), atomic posting, journal number assignment, audit write, event publish
- Manual journal entry lifecycle: DRAFT → SUBMITTED → APPROVED → POSTED; state machine enforcement
- Journal approval workflow (feature flag: `accounting.approvalworkflow.enabled`): configurable threshold, approver role, self-approval prevention
- Recurring journal templates: schedule, template lines, APScheduler execution, instance tracking
- Journal reversal: any POSTED entry can be reversed; reversal creates new DRAFT; both entries linked
- Batch journal posting: multiple entries approved and posted atomically
- GL query service: filter by date, account, period, cost center, source, reference; pagination
- GL drilldown: every GL entry links to source document (invoice, bill, payment, etc.)
- `accounting_audit_log` implementation: immutable write on every financial state change
- Integration event handlers (registration only in Phase 4; full posting logic in Phases 5–9): subscribe to `sales.invoice.posted`, `purchase.bill.posted`, `inventory.adjustment.posted`

**Prerequisites**: Phases 1–3 complete (COA and fiscal periods must exist)

**Deliverables**:
- PostingEngine domain service: the authoritative GL writer
- JournalEntry aggregate with full state machine
- JournalEntryRepository: search (by date/account/period/source/reference), find_by_number, drilldown
- Application services: JournalEntryService, RecurringJournalService
- GL report query service (read-optimized): date range, account filter, period filter
- Accounting audit log: immutable write for all journal events
- APScheduler recurring journal job: executes due templates daily at configurable time
- Alembic migrations: 038_accounting_general_ledger, 039_accounting_recurring_journals
- Frontend: Journal Entry list (searchable/filterable), Journal create/edit (multi-line form), Approval queue, Recurring Journal template management, GL Report page (with account and date filters, drill-down)

**Acceptance Criteria**:
- [ ] PostingEngine rejects unbalanced journals (sum debits ≠ sum credits) with clear error
- [ ] PostingEngine rejects journals with inactive or non-leaf accounts
- [ ] PostingEngine rejects journals in locked or closed periods
- [ ] Every posted journal entry has a complete, immutable audit record
- [ ] Journal number is gap-free per company (tested with 100 concurrent postings)
- [ ] POSTED journal lines cannot be updated or deleted (DB constraint verified)
- [ ] Journal reversal creates correctly inverted entry linked to original
- [ ] Recurring journal executes on schedule and creates correct instance records
- [ ] GL report filters work correctly for all filter combinations
- [ ] Drilldown from GL entry to source document returns correct document
- [ ] Self-approval rejected: user who created journal cannot be the sole approver
- [ ] Batch posting is atomic: if one entry in batch fails, no entries are posted

**Exit Criteria**: All PostingEngine invariant tests pass; GL balance verified via aggregation query; concurrent journal posting tested at 100 simultaneous requests; recurring journal scheduler verified with mock clock; all journal lifecycle states exercised via API tests

**Risks**:
- Advisory lock deadlock under extreme concurrency — timeout after 500ms; return retry error to client
- Recurring scheduler double-execution on restart — check last_run_date before executing; idempotent instance creation
- GL aggregation performance at 500K entries — verify covering index on (company_id, fiscal_period_id, account_id) eliminates sequential scan

**Estimated Complexity**: Very High (PostingEngine is the most complex component in the module)

---

### Phase 5: Accounts Receivable

**Objective**: Implement the AR sub-module — customer ledger, invoice tracking, AR aging, credit management, credit hold, customer statements, and collections.

**Business Value**: Finance team can see exactly who owes what and when. Credit management prevents overexposure. Collections workflow reduces DSO. Customer statements enable formal communication of account balances.

**Scope**:
- CustomerLedger aggregate: one record per customer per company; links to Epic 7 customer
- ARTransaction entity: all AR events (invoice, credit note, debit note, payment, adjustment)
- Integration event handler (live): `sales.invoice.posted` → PostingEngine creates DR AR / CR Revenue / CR Tax
- Integration event handler (live): `sales.creditnote.posted` → PostingEngine creates DR Revenue/Tax / CR AR
- AR aging: daily background job calculates aging buckets; aging report endpoint
- Credit limit management: credit_status auto-calculated (GOOD/WARNING/EXCEEDED); threshold configurable
- Credit hold: manual place/release; `accounting.ar.customer.credithold` event published
- Customer statement generation: per customer, per period, PDF-ready output
- AR adjustments: authorized users can post adjustments to customer ledger
- Bad debt write-off: approval required; posts DR Bad Debt Expense / CR AR; marks invoice WRITTEN_OFF
- Overdue invoice detection: daily job; publishes `accounting.ar.invoice.overdue` for each overdue invoice

**Prerequisites**: Phase 4 complete (PostingEngine operational; sales event handlers registered)

**Deliverables**:
- CustomerLedger aggregate, ARTransaction entity, ARPaymentAllocation entity
- CustomerLedgerRepository, ARTransactionRepository
- Application service: AccountsReceivableService
- Integration event handler: HandleSalesInvoicePosted, HandleSalesCreditNotePosted
- Daily jobs: AR aging recalculation, overdue invoice detection (via APScheduler)
- Credit hold event publisher
- Alembic migration: 040_accounting_ar_ledger
- Frontend: Customer Ledger screen (per customer), AR Aging Report (summary + detail), Customer Statement generator, Credit Management screen (limits, holds), Write-Off workflow (with approval)

**Acceptance Criteria**:
- [ ] Customer ledger balance reconciles to AR control account GL balance at all times
- [ ] Invoice posted in Epic 7 creates correct GL entry within same transaction (DR AR / CR Revenue)
- [ ] AR aging correctly buckets outstanding invoices by days overdue from due_date
- [ ] Credit limit warning event fires at 80% utilization
- [ ] Credit hold blocks new invoice creation (Sales module notified via event)
- [ ] Credit hold release restores sales capability
- [ ] Customer statement includes all transactions for the period with correct running balance
- [ ] Write-off requires approval and posts correct GL entry (DR Bad Debt / CR AR)
- [ ] All AR operations scoped to company_id
- [ ] AR transaction sum matches AR control account GL balance after every posting (tested via assertion in integration tests)

**Exit Criteria**: Sales invoice → AR → payment → zero balance flow tested end-to-end; AR aging verified with known dataset; credit hold tested across module boundary (verified in Sales API tests)

**Risks**:
- Cross-epic event timing: Sales invoice post and AR ledger update must be atomic — verify within same transaction
- AR control account reconciliation drift — add automated reconciliation check assertion to every integration test that posts to AR

**Estimated Complexity**: High

---

### Phase 6: Accounts Payable

**Objective**: Implement the AP sub-module — supplier ledger, bill tracking, payables aging, vendor credits, supplier statement reconciliation.

**Business Value**: Finance team can see exactly what is owed to suppliers, when, and manage payment priorities. Supplier reconciliation prevents AP disputes.

**Scope**:
- SupplierLedger aggregate: one record per supplier per company; links to Epic 6 supplier
- APTransaction entity: all AP events (bill, credit note, debit note, payment, adjustment)
- Integration event handler (live): `purchase.bill.posted` → PostingEngine creates DR Expense/Inventory+Tax / CR AP
- Integration event handler (live): `purchase.creditnote.posted` → PostingEngine creates DR AP / CR Expense+Tax
- AP aging: daily background job; aging report endpoint
- Supplier statement reconciliation: import supplier statement; side-by-side match; record discrepancies
- AP adjustments: early payment discounts, rounding differences
- Remittance advice generation: PDF-ready per payment

**Prerequisites**: Phase 4 complete

**Deliverables**:
- SupplierLedger aggregate, APTransaction entity, APPaymentAllocation entity
- SupplierLedgerRepository, APTransactionRepository
- Application service: AccountsPayableService
- Integration event handlers: HandlePurchaseBillPosted, HandlePurchaseCreditNotePosted
- SupplierStatementReconciliation entity and service
- Alembic migration: 041_accounting_ap_ledger
- Frontend: Supplier Ledger screen, AP Aging Report, Supplier Statement Reconciliation workspace, Remittance Advice generator

**Acceptance Criteria**:
- [ ] Supplier ledger balance reconciles to AP control account GL balance at all times
- [ ] Purchase bill posted in Epic 6 creates correct GL entry (DR Expense / CR AP)
- [ ] AP aging correctly buckets outstanding bills by days past due
- [ ] Supplier statement reconciliation identifies matched, unmatched GL items, and unmatched statement items
- [ ] Remittance advice generated per payment with correct bill allocation details
- [ ] AP transaction sum matches AP control account GL balance after every posting

**Exit Criteria**: Purchase bill → AP → payment → zero balance flow tested end-to-end; supplier reconciliation tested with simulated statement

**Risks**:
- AP control account reconciliation drift — same mitigation as AR: automated reconciliation assertion in every integration test

**Estimated Complexity**: Medium-High

---

### Phase 7: Banking

**Objective**: Implement bank account management, bank transactions, cheque management, and bank reconciliation.

**Business Value**: Companies can manage multiple bank accounts. Bank reconciliation ensures GL cash balances match bank statements. Cheque tracking prevents lost or fraudulent payments.

**Scope**:
- BankAccount aggregate: multi-bank support; GL account linkage
- BankTransaction entity: receipts, payments, transfers, bank charges
- Bank transfer workflow: from-bank to to-bank; single journal entry with two bank account legs
- Bank deposit aggregation: batch multiple receipts into one deposit record
- BankStatementLine entity: manual entry or CSV import (OFX format readiness)
- BankReconciliation aggregate: session-based reconciliation; auto-match by amount + date + reference; manual match for unmatched items; lock on completion
- BankReconciliationMatch entity: pairs GL transaction with statement line
- Cheque entity: full lifecycle (ISSUED → PRESENTED → CLEARED / CANCELLED / STALE); cheque register
- Bank charges auto-posting: bank charge on statement line auto-creates GL expense entry via PostingEngine
- `accounting.bank.reconciled` event published on reconciliation completion

**Prerequisites**: Phase 4 complete (PostingEngine); Phase 9 will connect payments to bank accounts

**Deliverables**:
- BankAccount, BankTransaction, BankStatementLine, BankReconciliation, BankReconciliationMatch, Cheque entities
- BankAccountRepository, BankReconciliationRepository
- Application service: BankAccountService
- Auto-match service: matches statement lines to GL entries by amount/date/reference heuristic
- Alembic migration: 042_accounting_banking
- Frontend: Bank Account list, Bank Account detail (transactions), Bank Reconciliation workspace (side-by-side match view), Cheque Register

**Acceptance Criteria**:
- [ ] Multiple bank accounts supported; each linked to a distinct GL account
- [ ] Bank transfer creates single balanced journal: DR destination bank / CR source bank
- [ ] Auto-match correctly pairs statement lines with GL entries for standard transactions
- [ ] Manual match UI allows any unmatched item to be paired or written off
- [ ] Reconciliation cannot be completed until statement balance == GL balance (zero difference)
- [ ] Completed reconciliation is locked; no modification after lock
- [ ] Cheque status lifecycle enforced; cleared cheques linked to statement line
- [ ] `accounting.bank.reconciled` event published on completion

**Exit Criteria**: Bank reconciliation tested end-to-end: transactions posted, statement imported, auto-match run, balance verified, locked

**Risks**:
- CSV/OFX import format variety — support generic CSV format initially; OFX parsing as feature flag
- Auto-match false positives (same amount, same date, different transaction) — require reference match for high-confidence; manual confirmation for ambiguous

**Estimated Complexity**: High

---

### Phase 8: Cash Management

**Objective**: Implement cash account management, cash receipts and payments, petty cash voucher system, and cash reconciliation.

**Business Value**: Companies can track physical cash accurately. Petty cash management provides auditability for minor expenses. Cash reconciliation ensures physical cash matches GL balance.

**Scope**:
- CashAccount aggregate: per till/petty cash box; GL linkage; float management
- CashTransaction entity: receipts and payments
- PettyCashVoucher entity: individual disbursement with expense account, amount, recipient, purpose
- Cash transfer: cash to/from bank account; creates two-leg journal entry
- Cash reconciliation: physical count entry; difference (short/over) posting via PostingEngine
- Petty cash replenishment: replenishment journal restores float (debit accounts from vouchers; credit bank)

**Prerequisites**: Phase 4 complete (PostingEngine); Phase 7 preferred (for cash-bank transfers)

**Deliverables**:
- CashAccount, CashTransaction, PettyCashVoucher, CashReconciliation entities
- CashAccountRepository
- Application service: CashAccountService
- Alembic migration: 043_accounting_cash_management
- Frontend: Cash Account list, Cash Account detail (transactions), Petty Cash voucher entry, Petty Cash reconciliation, Cash Book report

**Acceptance Criteria**:
- [ ] Multiple cash accounts supported; each linked to distinct GL cash account
- [ ] Petty cash voucher requires expense account, amount, and purpose
- [ ] Cash reconciliation: physical count vs GL balance difference posted to Cash Short/Over account
- [ ] Petty cash replenishment creates correct journal: DR expense accounts (from vouchers) / CR Bank
- [ ] All cash operations scoped to company_id

**Estimated Complexity**: Medium

---

### Phase 9: Payments

**Objective**: Implement the complete payment processing sub-module — customer receipts, supplier disbursements, payment allocation, partial payments, advance payments, overpayments, refunds, and credit/debit notes.

**Business Value**: Finance team can process all inbound and outbound payments with accurate allocation to specific invoices/bills. The AllocationEngine ensures outstanding balances are always accurate and aging is real-time.

**Scope**:
- Payment aggregate: covers customer receipts and supplier disbursements; all payment methods
- PaymentAllocationLine entity: links payment to specific AR/AP transactions
- AllocationEngine domain service: validate, allocate, calculate realized exchange gain/loss, post discount
- Partial payment: allocate portion of payment to one or more invoices
- Advance payment: record against advance account; defer allocation until invoice raised
- Overpayment: capture as credit on customer/supplier account
- Refund: return payment to customer or receive back from supplier
- Credit note allocation: apply credit note against open invoice
- Debit note processing: increase outstanding balance
- WHT support (feature flag: `accounting.taxwithholding.enabled`): deduct WHT on supplier payment; post to WHT payable account

**Prerequisites**: Phases 5 (AR), 6 (AP), 7 (Banking), 8 (Cash) complete

**Deliverables**:
- Payment aggregate, PaymentAllocationLine entity, PaymentRefund entity
- AllocationEngine domain service
- PaymentRepository
- Application service: PaymentService (CreateCustomerPayment, CreateSupplierPayment, AllocatePayment, ReallocatePayment, CancelPayment, ProcessRefund)
- WHT calculation (conditional): deduct WHT on supplier payment when flag enabled
- Alembic migration: 044_accounting_payments
- Frontend: Customer Payment screen (with allocation table), Supplier Payment screen (with allocation table), Advance Payment management, Refund processing, Unallocated Payment report

**Acceptance Criteria**:
- [ ] Customer payment DR Bank/Cash / CR AR via PostingEngine
- [ ] Supplier payment DR AP / CR Bank/Cash via PostingEngine
- [ ] Partial payment reduces invoice outstanding_amount accurately; aging updated
- [ ] Overpayment recorded as credit on customer account; not auto-allocated
- [ ] Advance payment posted to advance account; allocated to invoice when issued
- [ ] Realized exchange gain/loss posted automatically on foreign currency payment settlement
- [ ] Early payment discount posted to discount account; reduces invoice outstanding
- [ ] WHT deduction (when enabled): payment = gross − WHT; WHT posted to WHT payable account
- [ ] Refund posts correctly: DR Customer AR / CR Bank (for customer refund)
- [ ] Re-allocation: reversal of prior allocation and new allocation; both audit-trailed

**Exit Criteria**: Full Sales-to-Cash and Purchase-to-Pay workflows tested end-to-end with full GL verification

**Risks**:
- Concurrent payments to same invoice: optimistic locking on `outstanding_amount`; retry on conflict
- Exchange gain/loss calculation precision: use Decimal arithmetic throughout; verify to 6 decimal places

**Estimated Complexity**: High

---

### Phase 10: Tax Engine & Cost Centers

**Objective**: Implement the configurable tax engine (tax codes, groups, calculation, reporting) and cost accounting (cost centers, departments, projects).

**Business Value**: Companies can configure tax for any jurisdiction without code changes. Cost center accounting enables internal segment reporting. Tax reports provide the data needed for regulatory filing.

**Scope**:
- TaxCode aggregate: codes, rates (with effective date history), applicability
- TaxGroup: bundles of tax codes applied together
- TaxCalculator domain service: rate resolution, calculation, rounding, multi-tax support
- Tax report queries: output tax, input tax, net payable; VAT return format
- WHT report: deducted and remitted per supplier
- CostCenter entity: code, name, responsible user
- Department entity: groups cost centers
- Project entity: revenue and cost tracking per project
- Cost center posting validation: PostingEngine validates cost_center_id when account.requires_cost_center
- Cost center P&L report: revenue and expenses by cost center

**Prerequisites**: Phase 4 complete

**Deliverables**:
- TaxCode, TaxRate, TaxGroup, TaxGroupLine entities
- CostCenter, Department, Project entities
- TaxCalculator domain service
- TaxRepository, CostCenterRepository
- Application services: TaxService, CostCenterService
- Tax report queries: VAT summary, tax detail, WHT report
- Alembic migrations: 045_accounting_tax_engine, 046_accounting_cost_centers
- Frontend: Tax Code management, Tax Group management, Cost Center management, Department management, Project management, Tax Report screens, Cost Center P&L report

**Acceptance Criteria**:
- [ ] Tax code effective date ranges do not overlap for the same code
- [ ] TaxCalculator applies the correct rate for the transaction date
- [ ] Tax group applies all member tax codes simultaneously
- [ ] Zero-rated transactions produce a tax line with 0.00 amount (still reportable)
- [ ] Tax report output = sum of tax amounts on all transactions for the period
- [ ] Input tax recoverable (VAT/GST) correctly distinguished from non-recoverable tax
- [ ] Cost center assignment enforced on accounts with requires_cost_center = true
- [ ] PostingEngine rejects journal lines missing cost_center_id on required accounts
- [ ] Cost center P&L aggregates GL entries by cost_center_id

**Estimated Complexity**: Medium-High

---

### Phase 11: Financial Reporting

**Objective**: Implement all financial statements and management reports: Trial Balance, Balance Sheet, P&L, Cash Flow, GL Report, Customer/Supplier Ledger reports, Bank Book, Cash Book, Tax Reports, and the CFO KPI dashboard.

**Business Value**: The CFO and business owner can see the full financial picture in real-time. All reports required for management, compliance, and audit are available without external software.

**Scope**:
- FinancialStatementService: Balance Sheet, P&L, Cash Flow (indirect method)
- TrialBalanceService: real-time aggregation from GL with account group hierarchy
- GLReportService: detail GL entries with pagination, filters, export
- CustomerLedgerReport, SupplierLedgerReport: transaction history with running balance
- BankBook: chronological bank transactions with running balance
- CashBook: chronological cash transactions with running balance
- JournalReport: all journal entries for a period
- TaxReport: tax summary and detail views
- FinancialKPIService: real-time KPI calculation (Cash Position, DSO, DPO, Current Ratio, Quick Ratio, Gross/Net Margin, MTD Revenue, AR/AP totals)
- Comparative reporting: current period vs prior period, YTD vs prior YTD
- Report export: PDF and Excel for all statements
- Multi-currency financial statements: base currency and selected foreign currency views

**Prerequisites**: Phases 5–10 complete

**Deliverables**:
- FinancialStatementService (Balance Sheet, P&L, Cash Flow)
- All subsidiary and management report services
- FinancialKPIService
- Report export utilities (PDF via ReportLab/WeasyPrint; Excel via openpyxl)
- Frontend: Balance Sheet page, P&L page, Cash Flow page, Trial Balance page, GL Report page, AR/AP Ledger report pages, Bank Book, Cash Book, Journal Report, Tax Report pages, CFO KPI Dashboard

**Acceptance Criteria**:
- [ ] Balance Sheet equation holds: Assets == Liabilities + Equity (verified in every test)
- [ ] Trial Balance: total debits == total credits (verified in every test)
- [ ] P&L net income matches Balance Sheet retained earnings movement for the period
- [ ] Cash Flow closing balance matches GL cash and bank account balances
- [ ] All reports filterable by date range, cost center, department
- [ ] Comparative columns show prior period data accurately
- [ ] Financial statements generated in < 15 seconds for 500K GL entries
- [ ] Trial balance generated in < 10 seconds for 500K GL entries
- [ ] Reports export to PDF and Excel with correct formatting
- [ ] CFO dashboard shows all 15 KPIs with accurate real-time values

**Exit Criteria**: Financial statement accuracy tested against known test dataset with pre-computed expected values; performance benchmark verified under load test

**Risks**:
- P&L ↔ Balance Sheet net income link: Cash Flow indirect method is complex — implement incrementally; validate against known trial datasets
- PDF rendering performance for large GL reports — paginate reports; limit single PDF to 10,000 lines

**Estimated Complexity**: High

---

### Phase 12: Integration, Contracts, Performance & Epic Closure

**Objective**: Complete all integration contracts, OpenAPI specification, performance validation, security review, and epic closure documentation.

**Business Value**: The Accounting module is production-ready, fully documented, and verified against all acceptance criteria from the spec.

**Scope**:
- OpenAPI specification: generate `contracts/accounting-v1.yaml` covering all 100+ endpoints
- Integration test suite: end-to-end Sales-to-Cash, Purchase-to-Pay, and Inventory-to-GL workflows
- Performance benchmarks: verify all targets from spec §49 under load test
- Security audit: RBAC enforcement tests, SoD validation, cross-tenant isolation tests, immutability tests
- Bulk import/export testing: COA import (500 accounts), opening balance import (100 accounts), GL export (500K entries)
- Bank statement import: CSV format validation and reconciliation end-to-end
- Docker validation: full `docker compose up` with accounting module; all migrations; all tests green
- Documentation: update CLAUDE.md with Epic 8 technology additions; generate quickstart validation
- Agent context update: run `.specify/scripts/bash/update-agent-context.sh claude`
- PHR for epic closure

**Prerequisites**: Phases 1–11 complete; all acceptance criteria verified

**Deliverables**:
- `contracts/accounting-v1.yaml` (OpenAPI 3.0)
- Comprehensive integration test suite (end-to-end financial workflow tests)
- Performance benchmark report
- Security review checklist (all items PASS)
- Docker validation confirmation
- Updated CLAUDE.md (Epic 8 additions)

**Acceptance Criteria** (Epic 8 Completion):
- [ ] All 64-section acceptance criteria from spec.md verified green
- [ ] All unit, integration, API, security, and performance tests pass
- [ ] Balance Sheet equation never violated in any test
- [ ] AR/AP control account reconciliation invariant holds in all tests
- [ ] Period lock enforcement verified across all modules (Sales, Purchase, Inventory)
- [ ] Cross-tenant isolation: company A cannot access company B data (verified in security tests)
- [ ] RBAC: all permission checks verified (controller cannot close fiscal year; accountant cannot approve own journal)
- [ ] PostingEngine rejects unbalanced journal (verified 100% of paths)
- [ ] Performance targets met under load test
- [ ] Docker compose up with no errors; all 047 migrations apply cleanly
- [ ] OpenAPI spec covers all endpoints; no undocumented endpoints

**Exit Criteria**: All acceptance criteria checked; epic declared complete; PHR created

**Estimated Complexity**: Medium

---

## Domain-Driven Design Summary

### Bounded Contexts

| Context | Domain | Communicates With |
|---------|--------|-------------------|
| Accounting | Financial Record — SSOT for all financial truth | Receives from: Sales, Purchase, Inventory. Publishes to: Reporting, CRM, Notifications |
| Sales | Order-to-Cash operations | Publishes invoice/payment events → Accounting |
| Purchase | Purchase-to-Pay operations | Publishes bill/payment events → Accounting |
| Inventory | Stock management | Publishes adjustment events → Accounting |
| Reports (future) | Analytics and BI | Consumes from: Accounting |

### Aggregate Design Principles

- **JournalEntry** is the central aggregate: all financial truth flows through it
- **CustomerLedger** and **SupplierLedger** are subsidiary ledgers — their balances always reconcile to the GL control accounts
- **Payment** orchestrates the AllocationEngine; it does not modify JournalEntry directly
- Aggregates never directly reference each other's internal state — cross-aggregate via IDs and domain events
- PostingEngine is a domain service (not an aggregate) — it creates JournalEntry aggregates but is not one itself

---

## General Ledger Strategy

### Double-Entry Enforcement Chain

```
User / External Event
        ↓
Application Service (e.g., PaymentService.create_customer_payment)
        ↓
PostingEngine.post(PostingRequest)
        ↓
Step 1: Validate balance (sum debit == sum credit) → PostingValidationError if fails
Step 2: Validate all accounts active and leaf → PostingValidationError if fails
Step 3: Validate fiscal period OPEN → PostingValidationError if LOCKED or CLOSED
Step 4: Validate cost center requirements → PostingValidationError if missing
Step 5: Validate approval status → PostingValidationError if unapproved
Step 6: Acquire advisory lock on accounting_sequences
Step 7: Generate journal_number (gap-free)
Step 8: BEGIN TRANSACTION
Step 9: INSERT accounting_journal_entries
Step 10: INSERT accounting_journal_lines (N rows)
Step 11: Update denormalized balance fields (bank, cash, AR outstanding)
Step 12: INSERT accounting_audit_log
Step 13: COMMIT TRANSACTION
Step 14: Release advisory lock
Step 15: Publish accounting.journal.posted event (InProcessEventBus, after commit)
        ↓
PostingResult(journal_entry_id, journal_number, posted_at)
```

### Immutable Ledger Enforcement

- `accounting_journal_lines`: No PRIMARY KEY UPDATE; no DELETE permission granted at the DB role level used by the application
- DB CHECK constraint on `accounting_journal_entries`: `is_balanced = true` required before insert
- Correction path: reversal only — creates a new DRAFT journal with inverted amounts; original permanently preserved

---

## AR/AP Strategy

### Allocation Engine Flow

```
Payment received → PaymentService.create_customer_payment
        ↓
AllocationEngine.allocate(payment_id, allocation_lines)
        ↓
For each allocation_line:
  1. Lock ARTransaction row (SELECT FOR UPDATE)
  2. Validate: allocated_amount ≤ outstanding_amount
  3. Calculate realized gain/loss if foreign currency
  4. INSERT ARPaymentAllocation
  5. UPDATE ARTransaction.outstanding_amount -= allocated_amount
  6. Update ARTransaction.status (PAID / PARTIALLY_PAID)
  7. If discount_amount > 0: PostingEngine posts discount entry
  8. If gain/loss ≠ 0: PostingEngine posts gain/loss entry
COMMIT
        ↓
Publish accounting.payment.received event
```

### Control Account Reconciliation

- After every AR posting: assert `SUM(ar_transactions.amount) - SUM(ar_allocations.amount)` == GL balance of AR control account
- After every AP posting: assert `SUM(ap_transactions.amount) - SUM(ap_allocations.amount)` == GL balance of AP control account
- These assertions run in integration tests after every test that touches AR or AP

---

## Multi-Currency Strategy

### Exchange Rate Resolution Order

1. Explicit rate provided in the posting request (used for manual overrides)
2. Daily spot rate for the transaction date from `accounting_exchange_rates`
3. If no rate found for exact date: use most recent prior rate within 7 days
4. If still not found: PostingEngine raises `ExchangeRateNotFoundError`

### Realized Gain/Loss Trigger

Triggered by AllocationEngine when:
- Foreign currency invoice exists at booking rate R1
- Payment is applied at settlement rate R2
- R1 ≠ R2

Gain/Loss amount = `outstanding_foreign_amount × (R2 - R1)`

PostingEngine is called to post:
- Gain: DR AR (write-down) / CR Exchange Gain
- Loss: DR Exchange Loss / CR AR (write-up)

### Unrealized Gain/Loss (Revaluation)

Triggered by CurrencyRevaluationService at period-end:
- For each open foreign currency AR/AP transaction
- Compare booking rate to current revaluation rate
- Post aggregated unrealized gain/loss journal via PostingEngine
- Revaluation is reversible: CurrencyRevaluationService can reverse the revaluation entry

---

## Security Strategy

### Financial Permission Identifiers

All accounting permissions follow the pattern `accounting.<resource>.<action>`:

| Permission | Roles |
|-----------|-------|
| `accounting.journal.create` | Accountant, Controller, CFO |
| `accounting.journal.approve` | Controller, CFO |
| `accounting.journal.post` | Accountant, Controller, CFO |
| `accounting.journal.reverse` | Controller, CFO |
| `accounting.period.lock` | Controller, CFO |
| `accounting.period.unlock` | Controller, CFO |
| `accounting.fiscalyear.close` | CFO, System Admin |
| `accounting.payment.create` | AR Clerk, AP Clerk, Cashier, Controller, CFO |
| `accounting.payment.approve` | Controller, CFO |
| `accounting.ar.writeoff` | Controller, CFO |
| `accounting.ar.credithold.place` | Controller, CFO |
| `accounting.ar.credithold.release` | Controller, CFO |
| `accounting.tax.configure` | Controller, CFO |
| `accounting.reports.view` | All financial roles |
| `accounting.reports.export` | Controller, CFO, Accountant |

### Tenant and Company Isolation

- All repository queries include `WHERE tenant_id = :tenant_id AND company_id = :company_id`
- FastAPI dependency injection injects company_id from the authenticated session (Epic 2 pattern)
- No repository provides a "get all across companies" method
- Integration tests verify: create in Company A → cannot be retrieved with Company B credentials

### Immutable Financial History

- PostingEngine does not provide an update or delete path for posted entries
- API layer has no PUT/DELETE endpoints for `journal_entries` or `journal_lines`
- Any attempt to access these via direct DB queries is an audit-logged security event

---

## Performance Strategy

### Index Strategy

- **GL queries** (trial balance, P&L): covering index on `(company_id, fiscal_period_id, account_id)` on `accounting_journal_lines`
- **Date range queries**: covering index on `(company_id, posting_date, account_id)` on `accounting_journal_lines`
- **AR/AP aging**: index on `(company_id, customer_id/supplier_id, status, due_date)` on transaction tables
- **Bank reconciliation**: index on `(bank_account_id, transaction_date, amount)` on statement lines
- **Exchange rates**: index on `(from_currency, to_currency, rate_date DESC)` — enables date range lookup efficiently
- **Full-text search**: GIN index on `journal_entries.description` and `journal_entries.reference`

### Pagination

All list endpoints return paginated results (default page size: 50; max: 500). GL report supports cursor-based pagination for large datasets (> 10,000 rows).

### Caching Strategy

- Exchange rates: in-memory cache per request (rate for a given currency+date is immutable once set)
- Account tree: per-request cache (COA changes infrequently; safe to cache within a request context)
- Feature flags: per-request cache (consistent with Epic 5 pattern)
- Financial statements: NOT cached (real-time accuracy required; no stale data acceptable)

### Archiving Readiness

- Fiscal years older than 3 years can be moved to an "archived" status
- Archived years remain queryable but are stored in a separate partition (future)
- The schema supports partitioning `accounting_journal_lines` by fiscal_year_id (PostgreSQL range partitioning)

---

## AI Readiness Architecture

The Accounting module is designed so AI capabilities can be added as a new application service layer without modifying any existing code.

### AI Integration Points

| AI Capability | Data Available | Hook Location |
|--------------|----------------|---------------|
| Cash Flow Forecasting | AR aging, AP aging, payment history | After ARTransaction and APTransaction aggregation |
| Anomaly Detection | GL entry stream (all fields), audit log | Subscribes to `accounting.journal.posted` events |
| Smart Reconciliation | Bank statement lines + GL entries + historical matches | Within BankReconciliation aggregate; ML model suggests matches |
| Revenue Forecasting | P&L historical data by period/cost center | FinancialStatementService output |
| Fraud Detection | Audit log (user, time, amount, counterparty patterns) | Audit log query layer |
| AI Financial Assistant | All report data + domain event stream | Separate AI application service; reads from all repositories |
| Budget Recommendations | Historical expense by account/cost center | CostCenterService + GLReportService output |

All AI capabilities are gated by `accounting.ai.enabled` feature flag. When disabled, no AI-related code runs. The feature flag infrastructure is in place from Phase 1.

---

## Integration Strategy

### Epic 2 — Authentication

- All accounting API requests require valid JWT from Epic 2
- `accounting_configurations` can only be accessed by authenticated company admin
- Session context provides `tenant_id`, `user_id`, `company_id` — injected into all repositories

### Epic 3 — Companies

- Company record provides: base_currency, company_name (for reports), fiscal_year_start_month
- Accounting module reads company configuration on setup; does not modify it
- Multi-company: each company has fully independent COA, GL, AR, AP, banking

### Epic 4 — Users & Roles

- All accounting permissions defined and enforced via Epic 4 RBAC
- Approval matrix uses role IDs from Epic 4
- SoD enforcement: creator ≠ approver checked against user IDs from authenticated session

### Epic 5 — Inventory

- Consumes: `inventory.adjustment.posted`, `inventory.cost.updated`
- Handler creates GL entries for inventory value changes via PostingEngine
- Read-only: Accounting does not modify Epic 5 tables; it only creates GL entries based on events

### Epic 6 — Purchase

- Consumes: `purchase.bill.posted`, `purchase.creditnote.posted`, `purchase.payment.made`
- Handlers create AP ledger entries and GL postings
- Supplier reference: SupplierLedger holds supplier_id (Epic 6 ID); does not duplicate supplier master data

### Epic 7 — Sales

- Consumes: `sales.invoice.posted`, `sales.creditnote.posted`, `sales.payment.received`
- Handlers create AR ledger entries and GL postings
- Publishes: `accounting.ar.customer.credithold` → Sales blocks new orders
- Customer reference: CustomerLedger holds customer_id (Epic 7 ID); does not duplicate customer master data

### Future Epic 9 — CRM

- Consumes: `accounting.ar.customer.credithold`, `accounting.ar.customer.creditlimit.warning`, `accounting.ar.invoice.overdue`
- CRM uses these signals for customer health scoring and relationship management

### Future Epic 10 — Installments

- Will consume AR/AP data for installment schedule management
- Installment payments will post through PaymentService → PostingEngine

### Future Epic 11 — Reports

- Consumes all financial data via read-optimized queries on GL and subsidiary ledgers
- FinancialStatementService becomes a shared API for advanced BI

### Future Epic 12 — Deployment

- Accounting data backup schedule: daily incremental, weekly full, 7-year retention
- Database partitioning strategy for `accounting_journal_lines` by fiscal year
- Monitoring: GL posting volume per hour, failed posting rate, reconciliation overdue alerts

---

## Testing Strategy

### Unit Tests (no DB dependency)

- PostingEngine: balanced journal PASSES; unbalanced journal RAISES; inactive account RAISES; locked period RAISES; missing cost center RAISES; unapproved journal RAISES
- AllocationEngine: over-allocation RAISES; partial allocation PASSES; FX gain/loss calculation is accurate
- TaxCalculator: rate resolution by date is correct; compound tax calculation is correct
- AgingCalculator: bucket assignment is correct for all boundary dates
- JournalEntry state machine: all valid transitions PASS; all invalid transitions RAISE
- FiscalPeriod state machine: OPEN → LOCKED → CLOSED valid; any other sequence RAISES
- Balance Sheet equation: computed from known GL fixture; equation holds

### Integration Tests (real DB, per-test schema isolation)

- PostingEngine: full posting with real DB; journal lines count; balance verified by SELECT SUM
- AR control account reconciliation: post invoice → post payment → SUM(AR transactions) == GL AR control account balance
- AP control account reconciliation: same pattern for AP
- Bank reconciliation: statement import → auto-match → verify difference == 0 → lock
- Currency revaluation: post FX invoice → post revaluation → verify unrealized gain/loss entry
- FX settlement: post FX invoice → post FX payment at different rate → verify realized gain/loss entry
- Recurring journal: advance scheduler clock → verify instance created → verify GL entry created
- Period lock: lock period → post to locked period → verify PostingEngine raises
- Year-end close: post all period journals → run year-end close → verify retained earnings entry

### API Tests (FastAPI TestClient, authenticated)

- Full Sales-to-Cash: simulate `sales.invoice.posted` event → verify AR ledger updated → POST payment → verify invoice outstanding = 0
- Full Purchase-to-Pay: simulate `purchase.bill.posted` → verify AP ledger → POST supplier payment → verify bill outstanding = 0
- Cross-tenant isolation: Company A journal NOT returned in Company B journal list
- RBAC: Accountant cannot approve own journal (403); Controller can approve (200)
- Period lock API: lock period → POST journal to locked period → 422 with clear error
- Financial statement API: GET /balance-sheet returns correct totals for known dataset

### Security Tests

- Cross-tenant: tenant A cannot access tenant B accounting data (verified for all entity types)
- Cross-company: company A cannot access company B GL entries
- RBAC: all 20+ permissions verified with correct role grants and denials
- Immutability: PUT/DELETE on journal_lines returns 404 or 405 (no update endpoints)
- SoD: same user cannot create AND approve the same journal entry
- Period lock: no API path permits posting to locked period

### Performance Tests

- GL aggregation: 500K journal lines; trial balance < 10 seconds
- Financial statements: 500K GL entries; P&L < 15 seconds
- AR aging: 10,000 customers; aging report < 5 seconds
- Concurrent posting: 100 simultaneous journal postings; no deadlocks; no gaps in journal numbers

---

## Quality Gates (Per Phase)

Each phase must pass ALL quality gates before the next phase begins:

1. **Architecture Review**: No cross-layer dependency violations; PostingEngine not bypassed
2. **Security Review**: RBAC, company_id isolation, and immutability checks pass
3. **Business Review**: Acceptance criteria for the phase verified against spec
4. **Performance Review**: Phase-specific performance targets met
5. **Code Review**: Constitution compliance; no hardcoded values; Decimal used for all money
6. **Docker Verification**: `docker compose up && alembic upgrade head` completes without errors
7. **Regression Verification**: All tests from prior phases still pass after this phase's changes
8. **Documentation Review**: All new endpoints documented; quickstart.md updated if needed

---

## Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| PostingEngine deadlock under concurrent posting | Medium | High | Advisory lock with 500ms timeout; return retry-able error to client; test at 100 concurrent |
| AR/AP control account drift from subsidiary ledger | Low | Critical | Automated reconciliation assertion in every AR/AP integration test; daily background reconciliation check job |
| Period lock bypassed by direct SQL insert | Very Low | Critical | DB-level constraint + no UPDATE permission on journal_lines for app DB user; admin access audited |
| GL aggregation performance at 5M entries | Low | High | Covering indexes; verify with 500K dataset in Phase 4; PostgreSQL partitioning prepared for future |
| Recurring journal double-execution on app restart | Medium | Medium | Idempotency check: instance for current scheduled period already exists → skip; APScheduler with persistent job store |
| Exchange rate missing for foreign currency transaction | Medium | Medium | Rate lookup with 7-day fallback; clear error raised; CFO alerted; no silent 1:1 default |
| Tax code misconfiguration (wrong account type) | Medium | High | Tax account type validation on configuration save; warn if non-liability account used for tax |
| Financial statement P&L ↔ Balance Sheet mismatch | Low | High | Cross-check assertion in every integration test: P&L net income == Balance Sheet retained earnings movement |

---

## Future Readiness

### Extension Points Built Into Phase 1

- **Budgeting**: `accounting_configurations` includes `budgeting_enabled` flag; COA and cost center structure supports budget overlays
- **Fixed Assets**: `accounting_accounts` supports Fixed Asset account type; depreciation posting paths can be added as new PostingEngine source type
- **Payroll**: PayrollJournal import endpoint can be added to JournalEntryService; payroll provider sends journal batch
- **Treasury / Loans**: LoanSchedule aggregate will extend BankAccount aggregate; interest posting uses PostingEngine
- **Consolidated Financials**: CompanyGroup entity (future Epic) will consume FinancialStatementService for each company and aggregate
- **E-invoicing**: TaxService has a dedicated export method returning structured tax data; government API adapter is a pluggable implementation
- **Branch Accounting**: All GL entries have a `branch_id` nullable column from Phase 1; branch P&L activates by filtering on branch_id
- **AI Financial Assistant**: All domain event streams and report services are consumable by a future AI application service; no refactoring required

---

*Document Status: Ready for Phase 1 implementation*
*Next Steps: Run `/sp.tasks` to generate the task list for Epic 8*
*Architecture Decision: Suggest `/sp.adr accounting-posting-engine-design` to document the PostingEngine single-gate pattern*
