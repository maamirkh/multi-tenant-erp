# Tasks: Epic 8 — Accounting & Finance

**Branch**: `008-accounting-finance` | **Date**: 2026-08-05
**Input**: `specs/008-accounting-finance/` — spec.md (v1.0), plan.md, research.md, data-model.md, contracts/events.md
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Data Model**: [data-model.md](./data-model.md)

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Parallelizable — no dependency on an incomplete task in the same phase
- **[USN]**: User Story number this task delivers
- File paths use `backend/modules/accounting/` and `frontend/src/app/(protected)/(accounting)/`

---

## User Story Map

| Story | Domain | Plan Phase | Spec Section | Priority |
|-------|--------|------------|--------------|----------|
| US1 | Module Foundation & Scaffolding | Phase 1 | spec §12 | P0 — Foundation |
| US2 | Chart of Accounts | Phase 2 | spec §13 | P1 |
| US3 | Fiscal Calendar & Period Management | Phase 3 | spec §16 | P1 |
| US4 | PostingEngine & General Ledger | Phase 4 | spec §14, §15 | P1 — Critical |
| US5 | Journal Entries (Manual, Recurring, Reversal) | Phase 4 | spec §15 | P1 |
| US6 | Accounts Receivable | Phase 5 | spec §18 | P1 |
| US7 | Accounts Payable | Phase 6 | spec §19 | P1 |
| US8 | Banking & Bank Reconciliation | Phase 7 | spec §20 | P1 |
| US9 | Cash Management | Phase 8 | spec §21 | P2 |
| US10 | Payment Processing & Allocation | Phase 9 | spec §22 | P1 |
| US11 | Tax Engine & Cost Centers | Phase 10 | spec §23, §25 | P2 |
| US12 | Multi-Currency & Exchange Rates | Phase 10 | spec §24 | P2 |
| US13 | Financial Statements & Reports | Phase 11 | spec §17, §39 | P1 |
| US14 | Financial Controls & Audit Trail | Phase 11 | spec §26, §44 | P1 |
| US15 | Financial Intelligence & KPI Dashboard | Phase 11 | spec §40 | P2 |
| US16 | Integration Contracts, Performance & Closure | Phase 12 | spec §51–53, §64 | P1 |

---

## Phase 0: Architecture Preparation

**Objective**: Validate all dependencies, review approved artifacts, prepare accounting bounded contexts, aggregates, domain events, and Docker environment before any implementation begins.

**Business Value**: Prevents architectural mistakes that would require costly refactoring later. Ensures all integrations with Epics 5–7 are clearly defined before the first line of code.

**Prerequisites**: Epics 1–7 complete and stable on main; PostgreSQL 16 running; migrations 001–033 applied

**Dependencies**: Epic 1 (FastAPI scaffold), Epic 3 (company context), Epic 4 (RBAC), Epic 5 (InProcessEventBus, FeatureFlagService), Epic 6 (AP patterns), Epic 7 (AR/Sales patterns)

### Tasks

- [ ] T001 Review `specs/008-accounting-finance/spec.md` in full — verify all 66 sections are understood; confirm business rules BR-001 to BR-033 and invariants INV-001 to INV-010
- [ ] T002 [P] Review `specs/008-accounting-finance/plan.md` in full — confirm 12 phases, Constitution Check ALL PASS, PostingEngine single-gate constraint understood
- [ ] T003 [P] Review `specs/008-accounting-finance/research.md` — internalize all 15 architecture decisions; note Decision 1 (append-only GL), Decision 2 (PostingEngine gate), Decision 4 (dual-layer balance validation)
- [ ] T004 [P] Review `specs/008-accounting-finance/data-model.md` — map all 9 aggregate roots, 47 conceptual DB tables, state machines, and migration sequence 034–047
- [ ] T005 [P] Review `.specify/memory/constitution.md` — confirm all relevant principles (company_id isolation, soft-delete, audit trail, Decimal for money, no hardcoded secrets)
- [ ] T006 Verify Epic 5 integration: confirm `InProcessEventBus`, `FeatureFlagService`, and `BaseRepository` are importable from `backend/modules/inventory/` or shared core; document import paths
- [ ] T007 [P] Verify Epic 6 integration: confirm `purchase.bill.posted` and `purchase.creditnote.posted` events are published; verify supplier_id reference format used in Epic 6
- [ ] T008 [P] Verify Epic 7 integration: confirm `sales.invoice.posted` and `sales.creditnote.posted` events are published; verify customer_id reference format used in Epic 7; confirm sales AR account configuration pattern
- [ ] T009 Prepare domain event class inventory: list all 17 outbound events from `contracts/events.md`; confirm event envelope schema aligns with Epic 5/6/7 event format
- [ ] T010 [P] Prepare integration event handler registry: list all 8 inbound events from `contracts/events.md`; map each to its GL posting entry (DR/CR) per spec §38
- [ ] T011 [P] Prepare feature flag registry: document all 8 accounting feature flags with correct key names and defaults per `quickstart.md`
- [ ] T012 [P] Verify Docker environment: run `docker compose up -d`; confirm PostgreSQL 16 accessible; run `alembic upgrade head` (migrations 001–033 must apply cleanly)
- [ ] T013 [P] Verify existing test suite green: run `pytest backend/tests/ -v --tb=short`; confirm 0 failures before accounting module begins
- [ ] T014 Confirm accounting module router mount point: `/api/v1/companies/{company_id}/accounting/` does not conflict with any existing route in `backend/api/v1/router.py`
- [ ] T015 Document PostingEngine contract in `specs/008-accounting-finance/quickstart.md` — update with confirmed import paths and integration event formats from T006–T008

### Phase 0 Exit Criteria

- [ ] All 15 tasks complete; no open questions about integration contracts or shared infrastructure
- [ ] Docker running; prior tests green; architecture decision review signed off

---

## Phase 1: Module Foundation & Scaffolding (US1)

**Objective**: Establish the accounting module infrastructure — directory structure, router registration, base repository, feature flag registry, accounting configuration, currency/exchange rate foundation, journal number sequencing, and APScheduler integration.

**Business Value**: No direct user-visible value; this is the platform on which all financial capabilities are built. Without this foundation, no accounting function can operate.

**Story Goal (US1)**: The Accountant can access the accounting module, view configuration, manage currencies and exchange rates, and the system can generate gap-free journal numbers.

**Independent Test**: `GET /api/v1/companies/{id}/accounting/health` → 200; feature flags resolve correctly; journal number generation is gap-free under concurrent load.

### Tasks

- [ ] T016 Create the accounting module directory skeleton with `models/`, `schemas/`, `repositories/`, `services/`, `events/`, `handlers/` sub-modules inside `backend/modules/accounting/`
- [ ] T017 [P] Register the accounting module with the FastAPI application factory in `backend/api/v1/router.py` (include accounting router under `/api/v1/companies/{company_id}/accounting/`)
- [ ] T018 [P] Create `backend/modules/accounting/__init__.py` with public exports declaration
- [ ] T019 Create abstract `BaseAccountingRepository` class enforcing mandatory `company_id` on all queries, soft-delete pattern, and audit stamp utilities in `backend/modules/accounting/repositories/__init__.py`
- [ ] T020 [P] Define all accounting permission identifiers (constants) following `accounting.<resource>.<action>` pattern for all 20+ permissions per plan §Security Strategy in `backend/modules/accounting/constants.py`
- [ ] T021 [P] Define all accounting enums: `AccountType`, `AccountGroupType`, `JournalEntryStatus`, `JournalType`, `PostingSource`, `FiscalYearStatus`, `FiscalPeriodStatus`, `ARTransactionType`, `ARTransactionStatus`, `APTransactionType`, `APTransactionStatus`, `PaymentType`, `PaymentMethod`, `PaymentStatus`, `BankReconciliationStatus`, `ChequeStatus`, `TaxType`, `CreditStatus` in `backend/modules/accounting/constants.py`
- [ ] T022 [P] Register all 8 accounting feature flags in the shared `company_feature_flags` system with defaults in `backend/modules/accounting/constants.py`
- [ ] T023 Create the accounting module API router with health endpoint and feature-flag listing endpoint in `backend/modules/accounting/router.py`; register in `backend/api/v1/router.py`
- [ ] T024 [P] Create shared accounting request/response base schemas (pagination wrapper, `AccountingBaseSchema` with `from_attributes=True`, standard financial error response with error_code and details) in `backend/modules/accounting/schemas/base.py`
- [ ] T025 [P] Create accounting API dependencies (company context injection, RBAC permission checker, feature flag service, accounting configuration injection) in `backend/modules/accounting/dependencies.py`
- [ ] T026 [P] Create `SalesDomainEvent` base dataclass → create analogous `AccountingDomainEvent` base dataclass with `event_type`, `tenant_id`, `company_id`, `occurred_at`, `event_version`, `raised_by_user_id`, `to_dict()` in `backend/modules/accounting/events/__init__.py`
- [ ] T027 [US1] Create `AccountingConfiguration` ORM model with company-level settings: base_currency_code, journal_approval_threshold, payment_approval_threshold, credit_warning_threshold_pct, cheque_stale_days, default_ar_account_id, default_ap_account_id, default_retained_earnings_account_id, default_exchange_gain_account_id, default_exchange_loss_account_id, default_bad_debt_account_id in `backend/modules/accounting/models/foundation.py`
- [ ] T028 [P] [US1] Create `AccountingSequence` ORM model with company_id, sequence_type (JOURNAL), prefix, current_value, format_pattern for advisory-lock gap-free number generation in `backend/modules/accounting/models/foundation.py`
- [ ] T029 [P] [US1] Create `Currency` ORM model (global — not company-scoped): iso_code, name, symbol, decimal_places, is_active in `backend/modules/accounting/models/foundation.py`
- [ ] T030 [P] [US1] Create `ExchangeRate` ORM model: from_currency_code, to_currency_code, rate_date, rate (Decimal), rate_type (SPOT/AVERAGE/CLOSING/HISTORICAL), created_by_user_id in `backend/modules/accounting/models/foundation.py`
- [ ] T031 [US1] Implement `AccountingSequenceService` with `generate_next_journal_number(company_id)` using `SELECT FOR UPDATE` on `accounting_sequences` table for gap-free sequential numbering in `backend/modules/accounting/services/sequence_service.py`
- [ ] T032 [US1] Implement `CurrencyService` with `list_currencies()`, `create_currency()`, `set_exchange_rate()`, `get_rate(from_currency, to_currency, date)` (with 7-day fallback), `list_rates()` in `backend/modules/accounting/services/currency_service.py`
- [ ] T033 [US1] Create Pydantic v2 schemas for AccountingConfiguration, Currency, ExchangeRate (request/response) in `backend/modules/accounting/schemas/foundation.py`
- [ ] T034 [US1] Create repositories: `CurrencyRepository` (find_by_code, find_all_active), `ExchangeRateRepository` (get_rate_for_date, get_rates_for_period) in `backend/modules/accounting/repositories/foundation.py`
- [ ] T035 [US1] Create API endpoints: `GET/PUT /accounting/configuration`, `GET/POST /accounting/currencies`, `GET/POST/PUT /accounting/exchange-rates` in `backend/modules/accounting/router.py`
- [ ] T036 [US1] Integrate APScheduler into FastAPI startup lifecycle: register `recurring_journal_job` (daily at configurable time) and `ar_ap_overdue_check_job` (daily) as scheduler jobs in `backend/modules/accounting/services/scheduler.py`
- [ ] T037 Create Alembic migration `034_accounting_foundation.py` for tables: `accounting_configurations`, `accounting_sequences`, feature flags extension in `backend/migrations/versions/034_accounting_foundation.py`
- [ ] T038 Create Alembic migration `035_accounting_currencies_rates.py` for tables: `accounting_currencies` (with seed data for major ISO 4217 currencies), `accounting_exchange_rates` in `backend/migrations/versions/035_accounting_currencies_rates.py`
- [ ] T039 [P] [US1] Create frontend layout and navigation for the accounting module in `frontend/src/app/(protected)/(accounting)/layout.tsx`
- [ ] T040 [P] [US1] Create accounting API client base module with typed response handling and all base types in `frontend/src/lib/api/accounting.ts`
- [ ] T041 [P] [US1] Create frontend Currency management page (list + activate/deactivate) in `frontend/src/app/(protected)/(accounting)/currencies/page.tsx`
- [ ] T042 [P] [US1] Create frontend Exchange Rate management page (list + set rate per currency pair per date) in `frontend/src/app/(protected)/(accounting)/exchange-rates/page.tsx`
- [ ] T043 [P] [US1] Create frontend Accounting Configuration page (base currency, approval thresholds, system accounts) in `frontend/src/app/(protected)/(accounting)/configuration/page.tsx`
- [ ] T044 Write unit tests for `AccountingSequenceService` (sequential generation, company isolation, concurrent gap-free numbering at 100 concurrent requests) in `backend/tests/unit/modules/accounting/test_sequence_service.py`
- [ ] T045 [P] Write unit tests for accounting constants (permission codes unique, flag keys unique, enum values) in `backend/tests/unit/modules/accounting/test_constants.py`
- [ ] T046 [P] Write unit tests for `CurrencyService.get_rate()` (exact date match, 7-day fallback, not-found raises error) in `backend/tests/unit/modules/accounting/test_currency_service.py`
- [ ] T047 Write integration tests for Phase 1 repositories (Currency CRUD, ExchangeRate CRUD, company_id scoping, configuration CRUD) in `backend/tests/integration/repositories/accounting/test_phase1_repositories.py`
- [ ] T048 Write API tests for Phase 1 endpoints (configuration GET/PUT, currency list/create, exchange rate create/list, health endpoint, feature flag resolution) in `backend/tests/integration/api/v1/accounting/test_phase1_api.py`
- [ ] T049 Docker verification: `docker compose up`, `alembic upgrade head` (migrations 034–035 apply cleanly), accounting health endpoint responds 200, all Phase 1 routes registered, 0 import errors

### Phase 1 Exit Criteria

- [ ] All 34 tasks (T016–T049) complete
- [ ] Accounting module router responds at `/api/v1/companies/{company_id}/accounting/health`
- [ ] Feature flags resolve correctly for all 8 accounting flags
- [ ] Journal number generation gap-free under 100 concurrent requests (unit test passes)
- [ ] Currency and exchange rate CRUD operational

---

## Phase 2: Chart of Accounts (US2)

**Objective**: Implement the complete Chart of Accounts — hierarchical account structure (type → group → account), COA templates for 6 industries, system account configuration, and account validation.

**Business Value**: The Accountant can define the company's financial taxonomy. The COA enables all GL postings to be categorized correctly. This is the prerequisite for every financial transaction.

**Story Goal (US2)**: The Accountant can create, organize, and maintain a full chart of accounts. The Controller can configure system accounts (AR, AP, Bank, Cash, Retained Earnings, Tax accounts).

**Independent Test**: `GET /accounting/accounts?tree=true` returns the full COA hierarchy; posting to a non-leaf account is rejected; inactive account rejects posting attempt.

### Tasks

- [ ] T050 [P] [US2] Create `AccountGroup` ORM model (self-referencing): group_code, group_name, account_type, parent_group_id, display_order, is_active in `backend/modules/accounting/models/coa.py`
- [ ] T051 [P] [US2] Create `Account` ORM model: account_code, account_name, account_type (ASSET/LIABILITY/EQUITY/REVENUE/EXPENSE), account_group_id, parent_account_id, is_leaf, currency_code, requires_cost_center, is_bank_account, is_cash_account, is_active, tax_category, notes + soft-delete + audit stamps in `backend/modules/accounting/models/coa.py`
- [ ] T052 [US2] Implement `AccountRepository` with `find_by_code(company_id, code)`, `find_active_leaf_accounts(company_id, account_type)`, `get_coa_tree(company_id)` (recursive CTE), `find_by_type(company_id, type)`, `search(company_id, query)` in `backend/modules/accounting/repositories/coa.py`
- [ ] T053 [US2] Implement `ChartOfAccountsService` with `create_account()`, `update_account()`, `activate_account()`, `deactivate_account()` (validates no current-year GL activity), `get_coa_tree()`, `set_system_account()`, `bulk_import_coa()` (feature flag: `accounting.bulkimport.enabled`), `export_coa()` in `backend/modules/accounting/services/coa_service.py`
- [ ] T054 [P] [US2] Implement `AccountInvariantValidator`: code unique per company; only leaf accounts accept postings; inactive accounts block posting; parent accounts cannot be set inactive if they have active children in `backend/modules/accounting/services/coa_service.py`
- [ ] T055 [US2] Create Pydantic v2 schemas: `AccountCreateRequest`, `AccountUpdateRequest`, `AccountResponse` (with nested group and type), `AccountTreeNode` (recursive), `COAImportRow`, `SystemAccountConfigRequest` in `backend/modules/accounting/schemas/coa.py`
- [ ] T056 [US2] Create COA seed data: 6 industry COA templates (Retail, Manufacturing, Services, Construction, Medical, Generic) with account groups and standard accounts as seed/fixture files in `backend/modules/accounting/services/coa_templates.py`
- [ ] T057 [US2] Create API endpoints: `GET/POST /accounting/accounts`, `GET/PUT/DELETE /accounting/accounts/{id}`, `GET /accounting/accounts?tree=true`, `POST /accounting/accounts/bulk-import`, `GET /accounting/accounts/export`, `GET/POST /accounting/account-groups`, `GET/PUT /accounting/system-accounts` in `backend/modules/accounting/router.py`
- [ ] T058 Create Alembic migration `036_accounting_chart_of_accounts.py` for tables: `accounting_account_groups` (with seed standard groups), `accounting_accounts` in `backend/migrations/versions/036_accounting_chart_of_accounts.py`
- [ ] T059 [P] [US2] Create frontend COA page (expandable hierarchical tree view with account type/group grouping and inline status badge) in `frontend/src/app/(protected)/(accounting)/chart-of-accounts/page.tsx`
- [ ] T060 [P] [US2] Create `AccountFormModal` component (create/edit with account type, group, code, name, flags) in `frontend/src/components/accounting/AccountFormModal.tsx`
- [ ] T061 [P] [US2] Create frontend System Accounts configuration page (designate AR, AP, Bank, Cash, Tax, Retained Earnings, Exchange accounts) in `frontend/src/app/(protected)/(accounting)/chart-of-accounts/system-accounts/page.tsx`
- [ ] T062 [P] [US2] Create frontend COA Bulk Import page with template download and CSV upload with row-level error display in `frontend/src/app/(protected)/(accounting)/chart-of-accounts/import/page.tsx`
- [ ] T063 Write unit tests for `ChartOfAccountsService` account invariants: code uniqueness enforced; leaf-only posting; deactivation blocked with current-year activity; account type validation in `backend/tests/unit/modules/accounting/test_coa_service.py`
- [ ] T064 [P] Write unit tests for COA tree traversal: parent-child relationships correct; root accounts have no parent; leaf accounts have no children in `backend/tests/unit/modules/accounting/test_coa_tree.py`
- [ ] T065 Write integration tests for AccountRepository (CRUD, code uniqueness per company, tree query, cross-company isolation, soft-delete) in `backend/tests/integration/repositories/accounting/test_coa_repository.py`
- [ ] T066 Write API tests for COA endpoints (CRUD lifecycle, tree endpoint, bulk import 500 accounts, system account configuration, cross-tenant isolation) in `backend/tests/integration/api/v1/accounting/test_coa_api.py`
- [ ] T067 Docker verification: migrations 036 apply; COA tree renders with 6 industry templates; bulk import test 500 accounts < 30s

### Phase 2 Exit Criteria

- [ ] All 18 tasks (T050–T067) complete
- [ ] Account code unique per company enforced at domain and DB levels
- [ ] Leaf-only posting rule enforced (non-leaf returns clear error)
- [ ] COA tree traversal returns correct hierarchy
- [ ] 6 industry COA templates load correctly
- [ ] Bulk import 500 accounts < 30 seconds with row-level error reporting

---

## Phase 3: Fiscal Calendar (US3)

**Objective**: Implement fiscal year and period management — create fiscal years, manage period statuses (OPEN/LOCKED/CLOSED), opening balance setup, period-end close, and year-end close process.

**Business Value**: The Controller can manage the accounting calendar. Period locking prevents unauthorized retroactive postings. Opening balance setup enables business migration to the platform.

**Story Goal (US3)**: The Controller can create fiscal years, manage period locks/unlocks, enter opening balances, and execute year-end close. The system enforces period status across all modules via domain events.

**Independent Test**: Locking a period → subsequent `POST /accounting/journals` with that period's date → HTTP 422 "Period is locked". Year-end close creates correct retained earnings entry.

### Tasks

- [ ] T068 [P] [US3] Create `FiscalYear` ORM model: fiscal_year_name, start_date, end_date, status (SETUP/OPEN/CLOSED), base_currency_code, is_current + soft-delete + audit stamps in `backend/modules/accounting/models/fiscal.py`
- [ ] T069 [P] [US3] Create `FiscalPeriod` ORM model: fiscal_year_id, period_number (1–13), period_name, start_date, end_date, status (OPEN/LOCKED/CLOSED), locked_at, locked_by_user_id, lock_reason, closed_at + audit stamps in `backend/modules/accounting/models/fiscal.py`
- [ ] T070 [P] [US3] Create `OpeningBalance` ORM model: fiscal_year_id, account_id, debit_amount, credit_amount, currency_code, notes in `backend/modules/accounting/models/fiscal.py`
- [ ] T071 [US3] Implement `FiscalYearRepository` with `find_current(company_id)`, `find_by_year(company_id, year_name)`, `list_all(company_id)` in `backend/modules/accounting/repositories/fiscal.py`
- [ ] T072 [US3] Implement `FiscalPeriodRepository` with `find_open_period_for_date(company_id, date)`, `find_by_id(company_id, period_id)`, `list_periods(company_id, fiscal_year_id)` in `backend/modules/accounting/repositories/fiscal.py`
- [ ] T073 [US3] Implement `FiscalCalendarService` with `create_fiscal_year()`, `open_period()`, `lock_period()` (publishes `accounting.period.locked`), `unlock_period()` (Controller role required; reason mandatory), `close_period()` (terminal; no reversal), `setup_opening_balances()` (validates sum = 0), `execute_year_end_close()` (calls PostingEngine for retained earnings entry) in `backend/modules/accounting/services/fiscal_service.py`
- [ ] T074 [US3] Implement `FiscalPeriodStateMachine`: enforce OPEN → LOCKED → CLOSED transitions; reject CLOSED → any; reject LOCKED → CLOSED without year-end close completion in `backend/modules/accounting/services/fiscal_service.py`
- [ ] T075 [US3] Create `accounting.period.locked` domain event class with payload: company_id, fiscal_year_id, fiscal_period_id, period_number, period_name, period_start_date, period_end_date, locked_by_user_id, lock_reason in `backend/modules/accounting/events/fiscal_events.py`
- [ ] T076 [US3] Register `accounting.period.locked` event subscription in Sales (Epic 7) and Purchase (Epic 6) and Inventory (Epic 5) modules — each module's PostingService must check period lock status via event cache in `backend/modules/accounting/handlers/period_lock_handler.py`
- [ ] T077 [US3] Create Pydantic v2 schemas: `FiscalYearCreateRequest`, `FiscalYearResponse`, `FiscalPeriodResponse`, `PeriodLockRequest`, `PeriodUnlockRequest`, `OpeningBalanceImportRequest`, `YearEndCloseRequest` in `backend/modules/accounting/schemas/fiscal.py`
- [ ] T078 [US3] Create API endpoints: `GET/POST /accounting/fiscal-years`, `GET/PUT /accounting/fiscal-years/{id}`, `GET /accounting/fiscal-years/{id}/periods`, `POST /accounting/fiscal-years/{id}/periods/{pid}/lock`, `POST /accounting/fiscal-years/{id}/periods/{pid}/unlock`, `POST /accounting/fiscal-years/{id}/opening-balances`, `POST /accounting/fiscal-years/{id}/year-end-close` in `backend/modules/accounting/router.py`
- [ ] T079 Create Alembic migration `037_accounting_fiscal_calendar.py` for tables: `accounting_fiscal_years`, `accounting_fiscal_periods`, `accounting_opening_balances` in `backend/migrations/versions/037_accounting_fiscal_calendar.py`
- [ ] T080 [P] [US3] Create frontend Fiscal Year management page (list fiscal years + create new) in `frontend/src/app/(protected)/(accounting)/fiscal-calendar/page.tsx`
- [ ] T081 [P] [US3] Create frontend Period Dashboard page (grid showing all periods with OPEN/LOCKED/CLOSED status badges + lock/unlock controls) in `frontend/src/app/(protected)/(accounting)/fiscal-calendar/[yearId]/periods/page.tsx`
- [ ] T082 [P] [US3] Create frontend Opening Balance entry screen (account list with debit/credit input; running total showing balance/imbalance) in `frontend/src/app/(protected)/(accounting)/fiscal-calendar/[yearId]/opening-balances/page.tsx`
- [ ] T083 [P] [US3] Create `YearEndCloseWizard` component (multi-step checklist: periods locked, bank reconciled, AR/AP confirmed, closing entry preview) in `frontend/src/components/accounting/YearEndCloseWizard.tsx`
- [ ] T084 Write unit tests for `FiscalPeriodStateMachine`: all valid transitions; all invalid transitions raise error; CLOSED is terminal in `backend/tests/unit/modules/accounting/test_fiscal_state_machine.py`
- [ ] T085 [P] Write unit tests for `FiscalCalendarService.setup_opening_balances()`: balanced set passes; imbalanced set raises error in `backend/tests/unit/modules/accounting/test_fiscal_service.py`
- [ ] T086 Write integration tests for fiscal period lock enforcement: lock period → attempt posting → verify PostingEngine raises `PeriodLockedError` in `backend/tests/integration/repositories/accounting/test_fiscal_repository.py`
- [ ] T087 Write API tests for fiscal calendar endpoints (CRUD, lock, unlock, opening balance, year-end close) in `backend/tests/integration/api/v1/accounting/test_fiscal_api.py`
- [ ] T088 Docker verification: migrations 037 apply; fiscal year create, period lock, opening balance import tested end-to-end

### Phase 3 Exit Criteria

- [ ] All 21 tasks (T068–T088) complete
- [ ] Fiscal period state machine enforces all transitions
- [ ] Period lock immediately prevents GL postings (PostingEngine test passes)
- [ ] `accounting.period.locked` event published on lock
- [ ] Opening balance validates sum = 0 before commit
- [ ] Year-end close creates correct retained earnings entry

---

## Phase 4: PostingEngine & General Ledger (US4 — CRITICAL PHASE)

**Objective**: Implement the `PostingEngine` domain service (the single GL gate) and the complete GL infrastructure — `JournalEntry` aggregate, immutable `JournalLine` records, accounting audit log, and GL query interface.

**Business Value**: The Accountant and system can post all financial transactions to the GL. Every financial event from Sales, Purchase, and Inventory creates auditable, balanced, immutable GL records. This phase enables all downstream accounting capabilities.

**Story Goal (US4)**: The Accountant can post balanced journal entries. The system can post automated entries from Sales/Purchase/Inventory events. Every posted entry is immediately visible in the GL report with drilldown to the source document.

**Independent Test**: Post a balanced manual journal → GL balance verified (SUM debits == SUM credits); post an unbalanced journal → HTTP 422 with "Journal must balance"; post to a locked period → HTTP 422 with "Period is locked".

### Tasks

- [ ] T089 [P] [US4] Create `JournalEntry` ORM model: journal_number, journal_type, posting_source, posting_date, fiscal_period_id, fiscal_year_id, reference, description, notes, status (DRAFT/SUBMITTED/APPROVED/POSTED/REVERSED), reversal_of_journal_id, is_reversal, posted_at, posted_by_user_id, source_document_type, source_document_id, currency_code, exchange_rate, total_debit_base, total_credit_base + audit stamps in `backend/modules/accounting/models/gl.py`
- [ ] T090 [P] [US4] Create `JournalLine` ORM model (append-only — NO soft-delete, NO UPDATE): line_number, account_id, account_code (denormalized), debit_amount, credit_amount, debit_amount_base, credit_amount_base, currency_code, exchange_rate, cost_center_id, department_id, project_id, description, reference in `backend/modules/accounting/models/gl.py`
- [ ] T091 [P] [US4] Create `JournalApproval` ORM model: journal_entry_id, approver_user_id, approval_status, approved_at, rejection_reason in `backend/modules/accounting/models/gl.py`
- [ ] T092 [P] [US4] Create `AccountingAuditLog` ORM model (append-only — immutable): entity_type, entity_id, action, actor_user_id, occurred_at (UTC), before_state (JSONB), after_state (JSONB), session_context, reason in `backend/modules/accounting/models/gl.py`
- [ ] T093 [US4] Implement `PostingEngine` domain service with full validation pipeline and atomic posting:
  - Step 1: Validate SUM(debit) == SUM(credit) — raise `PostingValidationError("Journal must balance")` if not
  - Step 2: Validate all account_ids exist, are active leaf accounts — raise `PostingValidationError("Invalid account: {code}")`
  - Step 3: Validate posting_date falls in OPEN fiscal period via `FiscalPeriodRepository` — raise `PostingValidationError("Period is locked/closed")`
  - Step 4: Validate cost_center_id present on lines where account.requires_cost_center — raise `PostingValidationError("Cost center required for account: {code}")`
  - Step 5: Validate approval status if amount exceeds configuration threshold — raise `PostingValidationError("Approval required")`
  - Step 6: Acquire advisory lock on `accounting_sequences` → generate gap-free journal_number
  - Step 7: BEGIN TRANSACTION → INSERT `accounting_journal_entries` → INSERT `accounting_journal_lines` (N rows) → update denormalized balances → INSERT `accounting_audit_log` → COMMIT
  - Step 8: Publish `accounting.journal.posted` event via InProcessEventBus
  - Returns: `PostingResult(journal_entry_id, journal_number, posted_at)`
  in `backend/modules/accounting/services/posting_engine.py`
- [ ] T094 [US4] Implement `JournalEntryStateMachine`: DRAFT → SUBMITTED → APPROVED → POSTED → (REVERSED); REJECTED is a terminal rejection state; auto-posted entries skip to POSTED directly; no backward transitions after POSTED in `backend/modules/accounting/services/posting_engine.py`
- [ ] T095 [US4] Add DB-level immutability constraint for `accounting_journal_lines`: DB-level CHECK constraint on `accounting_journal_entries.is_balanced`; DB trigger to block UPDATE/DELETE on `accounting_journal_lines` after INSERT in Alembic migration 038
- [ ] T096 [US4] Implement `JournalEntryRepository` with `find_by_number(company_id, number)`, `search(company_id, filters)` (filter by date/account/period/source/reference/cost_center with pagination), `find_by_source_document(company_id, doc_type, doc_id)`, `find_by_status(company_id, status)` in `backend/modules/accounting/repositories/gl.py`
- [ ] T097 [US4] Implement `GLReportRepository` (read-optimized): `trial_balance_query(company_id, period_id)`, `gl_detail_query(company_id, filters)` (with covering index hints), `account_balance_query(company_id, account_id, date_range)` in `backend/modules/accounting/repositories/gl.py`
- [ ] T098 [US4] Implement `AuditLogService` with `record(entity_type, entity_id, action, actor_id, before, after, reason)` — synchronous write within the same transaction as the action being audited in `backend/modules/accounting/services/audit_service.py`
- [ ] T099 [US4] Implement integration event handler stubs for all 8 inbound events: `HandleSalesInvoicePosted`, `HandleSalesCreditNotePosted`, `HandlePurchaseBillPosted`, `HandlePurchaseCreditNotePosted`, `HandleInventoryAdjustmentPosted`, `HandleInventoryCostUpdated`, `HandleSalesPaymentReceived`, `HandleSupplierPaymentMade` — each handler calls PostingEngine with the correct DR/CR lines per spec §38 in `backend/modules/accounting/handlers/integration_handlers.py`
- [ ] T100 [US4] Create Pydantic v2 schemas: `PostingRequest` (journal_type, source, posting_date, lines: list[PostingLineRequest]), `PostingLineRequest` (account_id, debit_amount, credit_amount, currency_code, exchange_rate, cost_center_id, description), `PostingResult`, `JournalEntryResponse`, `JournalLineResponse`, `GLReportRow`, `GLReportRequest` in `backend/modules/accounting/schemas/gl.py`
- [ ] T101 [US4] Create API endpoints: `GET/POST /accounting/journals`, `GET /accounting/journals/{id}`, `POST /accounting/journals/{id}/submit`, `POST /accounting/journals/{id}/approve`, `POST /accounting/journals/{id}/reject`, `POST /accounting/journals/{id}/post`, `POST /accounting/journals/{id}/reverse`, `GET /accounting/reports/gl` (with filters) in `backend/modules/accounting/router.py`
- [ ] T102 Create Alembic migration `038_accounting_general_ledger.py` for tables: `accounting_journal_entries`, `accounting_journal_lines` (with immutability constraint), `accounting_journal_approvals`, `accounting_audit_log`; covering indexes on `(company_id, fiscal_period_id, account_id)` and `(company_id, posting_date, account_id)` on `accounting_journal_lines` in `backend/migrations/versions/038_accounting_general_ledger.py`
- [ ] T103 [P] [US4] Create frontend Journal Entry list page (filterable by date/account/status/source with pagination) in `frontend/src/app/(protected)/(accounting)/journals/page.tsx`
- [ ] T104 [P] [US4] Create frontend Journal Entry create/edit page (multi-line form with account selector, debit/credit inputs, running balance indicator, balance status badge) in `frontend/src/app/(protected)/(accounting)/journals/new/page.tsx`
- [ ] T105 [P] [US4] Create frontend Approval Queue page (pending journals requiring approval, with approve/reject actions) in `frontend/src/app/(protected)/(accounting)/journals/approval-queue/page.tsx`
- [ ] T106 [P] [US4] Create frontend GL Report page (searchable/filterable GL with account, date, cost center filters; drill-down to source document on row click) in `frontend/src/app/(protected)/(accounting)/reports/gl/page.tsx`
- [ ] T107 Write unit tests for `PostingEngine` — CRITICAL: ALL 7 validation steps must be tested individually:
  - T107a: Balanced journal PASSES
  - T107b: Unbalanced journal raises `PostingValidationError`
  - T107c: Inactive account raises `PostingValidationError`
  - T107d: Non-leaf account raises `PostingValidationError`
  - T107e: Locked period raises `PostingValidationError`
  - T107f: Missing cost center (when required) raises `PostingValidationError`
  - T107g: Unapproved journal above threshold raises `PostingValidationError`
  in `backend/tests/unit/modules/accounting/test_posting_engine.py`
- [ ] T108 Write unit tests for `JournalEntryStateMachine`: all valid transitions; all invalid transitions raise error; POSTED is immutable in `backend/tests/unit/modules/accounting/test_journal_state_machine.py`
- [ ] T109 Write integration tests for PostingEngine with real DB: post journal → verify GL lines; verify SUM(debit)==SUM(credit) in DB; verify journal_number gap-free; 100 concurrent postings → no gaps no deadlocks in `backend/tests/integration/repositories/accounting/test_posting_engine.py`
- [ ] T110 Write integration tests for GL immutability: attempt UPDATE on `accounting_journal_lines` → DB constraint blocks it; attempt DELETE → DB constraint blocks it in `backend/tests/integration/repositories/accounting/test_gl_immutability.py`
- [ ] T111 Write integration tests for audit log: every journal state change → audit record created; audit records cannot be deleted in `backend/tests/integration/repositories/accounting/test_audit_log.py`
- [ ] T112 Write API tests for journal endpoints (full DRAFT → POST lifecycle, approval, rejection, reversal, GL report filters, cross-tenant isolation) in `backend/tests/integration/api/v1/accounting/test_journal_api.py`
- [ ] T113 Write integration tests for all 8 inbound event handlers: simulate event → verify correct GL entry created with correct DR/CR accounts and amounts in `backend/tests/integration/repositories/accounting/test_integration_handlers.py`
- [ ] T114 Docker verification: migrations 038 apply with immutability constraint; journal posting end-to-end; GL report query performance test for 10K entries

### Phase 4 Exit Criteria

- [ ] All 26 tasks (T089–T114) complete
- [ ] PostingEngine rejects unbalanced journals (100% of validation paths tested)
- [ ] Journal lines immutable after posting (DB constraint verified)
- [ ] Gap-free journal numbering verified at 100 concurrent requests
- [ ] All 8 integration event handlers create correct GL entries
- [ ] Audit log created for every journal state change

---

## Phase 5: Journal Entries — Manual, Recurring & Reversal (US5)

**Objective**: Implement the full journal entry workflow — manual journal creation with approval, recurring journal templates with APScheduler execution, and journal reversal.

**Business Value**: The Accountant can post month-end accruals, set up automated recurring entries (rent, insurance, subscriptions), and reverse incorrect postings through the proper correction path.

**Story Goal (US5)**: The Accountant can create manual journals, set up recurring monthly accruals, and reverse any posted entry. The approval workflow requires a second authorized reviewer for large entries.

**Independent Test**: Create recurring template → advance mock clock by 1 month → verify instance created and GL entry posted; create journal → reverse → verify both entries in GL with opposite sign.

### Tasks

- [ ] T115 [P] [US5] Create `RecurringJournalTemplate` ORM model: template_name, frequency (DAILY/WEEKLY/MONTHLY/QUARTERLY/ANNUALLY), start_date, end_date, next_run_date, is_active, auto_post (bool), approval_required (bool), template lines (stored as JSONB or separate table) in `backend/modules/accounting/models/recurring.py`
- [ ] T116 [P] [US5] Create `RecurringJournalTemplateLine` ORM model: template_id, line_number, account_id, debit_amount, credit_amount, description, cost_center_id in `backend/modules/accounting/models/recurring.py`
- [ ] T117 [P] [US5] Create `RecurringJournalInstance` ORM model: template_id, journal_entry_id, execution_date, status (SUCCESS/FAILED), error_message in `backend/modules/accounting/models/recurring.py`
- [ ] T118 [US5] Implement `RecurringJournalService` with `create_template()`, `update_template()`, `activate_template()`, `deactivate_template()`, `execute_due_templates()` (called by APScheduler), `get_template_history()` in `backend/modules/accounting/services/recurring_journal_service.py`
- [ ] T119 [US5] Implement idempotency check in `execute_due_templates()`: before creating instance, check if instance already exists for this template + scheduled date; skip if exists (handles APScheduler restart double-execution risk) in `backend/modules/accounting/services/recurring_journal_service.py`
- [ ] T120 [US5] Implement journal reversal in `JournalEntryService.reverse_journal()`: create new `PostingRequest` with all debits and credits swapped from original; set `reversal_of_journal_id`; call PostingEngine; mark original as REVERSED in `backend/modules/accounting/services/journal_service.py`
- [ ] T121 [US5] Implement self-approval prevention in journal approval workflow: `approver_user_id != created_by_user_id` enforced at domain layer in `backend/modules/accounting/services/journal_service.py`
- [ ] T122 [US5] Implement batch journal posting: accept list of journal_entry_ids; approve and post all atomically (all succeed or none post) in `backend/modules/accounting/services/journal_service.py`
- [ ] T123 [US5] Create Pydantic v2 schemas: `RecurringTemplateCreateRequest`, `RecurringTemplateResponse`, `RecurringInstanceResponse`, `JournalReversalRequest`, `BatchPostingRequest` in `backend/modules/accounting/schemas/recurring.py`
- [ ] T124 [US5] Create API endpoints: `GET/POST /accounting/recurring-journals`, `GET/PUT /accounting/recurring-journals/{id}`, `POST /accounting/recurring-journals/{id}/activate`, `POST /accounting/recurring-journals/{id}/deactivate`, `GET /accounting/recurring-journals/{id}/history` in `backend/modules/accounting/router.py`
- [ ] T125 Create Alembic migration `039_accounting_recurring_journals.py` for tables: `accounting_recurring_templates`, `accounting_recurring_template_lines`, `accounting_recurring_instances` in `backend/migrations/versions/039_accounting_recurring_journals.py`
- [ ] T126 [P] [US5] Create frontend Recurring Journal Templates list page in `frontend/src/app/(protected)/(accounting)/journals/recurring/page.tsx`
- [ ] T127 [P] [US5] Create frontend Recurring Journal Template create/edit page (schedule configuration + template lines + auto-post toggle) in `frontend/src/app/(protected)/(accounting)/journals/recurring/new/page.tsx`
- [ ] T128 Write unit tests for `RecurringJournalService.execute_due_templates()` with mock clock: due template executes; future template skips; idempotency: second call for same period skips in `backend/tests/unit/modules/accounting/test_recurring_journal_service.py`
- [ ] T129 [P] Write unit tests for journal reversal: reversed entry has opposite sign; original marked REVERSED; reversal entry links to original in `backend/tests/unit/modules/accounting/test_journal_reversal.py`
- [ ] T130 [P] Write unit tests for self-approval prevention: same user create + approve → raises error in `backend/tests/unit/modules/accounting/test_journal_approval.py`
- [ ] T131 Write API tests for recurring journal endpoints (CRUD, activate/deactivate, history) in `backend/tests/integration/api/v1/accounting/test_recurring_journal_api.py`

### Phase 5 Exit Criteria

- [ ] All 17 tasks (T115–T131) complete
- [ ] Recurring journal executes on schedule with idempotency (tested with mock clock)
- [ ] Reversal creates correct inverse entry linked to original
- [ ] Self-approval blocked at domain layer

---

## Phase 6: Accounts Receivable (US6)

**Objective**: Implement the AR sub-module — customer ledger, invoice tracking from Sales integration, AR aging, credit limit management, credit hold, customer statements, and write-off readiness.

**Business Value**: The AR Clerk can see exactly who owes what and when. Credit management prevents overexposure. Customer statements enable formal communication. Collections workflow reduces DSO.

**Story Goal (US6)**: The AR Clerk can view the customer ledger, run aging reports, place and release credit holds, generate customer statements, and initiate write-off requests.

**Independent Test**: Publish `sales.invoice.posted` event → verify CustomerLedger balance updated; verify AR control account GL balance == sum of all CustomerLedger open balances.

### Tasks

- [ ] T132 [P] [US6] Create `CustomerLedger` ORM model: customer_id (Epic 7 reference), credit_limit, credit_status (GOOD/WARNING/EXCEEDED/HOLD), credit_hold_at, credit_hold_reason, credit_hold_by, total_outstanding_base (materialized), last_payment_date, average_payment_days in `backend/modules/accounting/models/ar.py`
- [ ] T133 [P] [US6] Create `ARTransaction` ORM model: customer_ledger_id, transaction_type, transaction_date, due_date, currency_code, exchange_rate, amount_foreign, amount_base, outstanding_amount (denormalized), status (OPEN/PARTIALLY_PAID/PAID/OVERDUE/DISPUTED/WRITTEN_OFF), source_document_type, source_document_id, journal_entry_id, invoice_number in `backend/modules/accounting/models/ar.py`
- [ ] T134 [P] [US6] Create `ARPaymentAllocation` ORM model: ar_transaction_id (invoice), payment_id, allocated_amount_foreign, allocated_amount_base, allocated_at, discount_amount in `backend/modules/accounting/models/ar.py`
- [ ] T135 [P] [US6] Create `CustomerCreditHistory` ORM model: customer_ledger_id, event_type (LIMIT_CHANGED/HOLD_PLACED/HOLD_RELEASED/STATUS_CHANGED), old_value, new_value, reason, actor_user_id, occurred_at in `backend/modules/accounting/models/ar.py`
- [ ] T136 [US6] Implement `CustomerLedgerRepository` with `find_by_customer(company_id, customer_id)`, `get_open_transactions(company_id, customer_id)`, `get_aging_data(company_id, as_of_date)` (returns all open transactions with days_overdue), `get_statement_data(company_id, customer_id, from_date, to_date)` in `backend/modules/accounting/repositories/ar.py`
- [ ] T137 [US6] Implement `AccountsReceivableService` with `get_customer_ledger()`, `get_customer_aging()`, `get_customer_statement()`, `set_credit_limit()`, `place_credit_hold()` (publishes `accounting.ar.customer.credithold`), `release_credit_hold()` (publishes `accounting.ar.customer.credithold.released`), `adjust_receivable()`, `initiate_write_off()` (approval required), `confirm_write_off()` in `backend/modules/accounting/services/ar_service.py`
- [ ] T138 [US6] Implement `AgingCalculator` domain service with `calculate_ar_aging(company_id, as_of_date)` returning buckets: Current / 1-30 / 31-60 / 61-90 / 91-120 / 120+ days overdue per customer and in aggregate in `backend/modules/accounting/services/aging_calculator.py`
- [ ] T139 [US6] Implement credit status auto-calculation in `CustomerLedgerRepository`: GOOD (< 80%), WARNING (80–100%), EXCEEDED (> 100%) based on `total_outstanding_base / credit_limit` ratio in `backend/modules/accounting/services/ar_service.py`
- [ ] T140 [US6] Implement AR control account reconciliation assertion: `assert SUM(ar_transactions.amount - allocated) == GL_balance(AR_control_account)` — called in integration tests after every AR posting in `backend/modules/accounting/services/ar_service.py`
- [ ] T141 [US6] Wire `HandleSalesInvoicePosted` event handler (created in T099): create `ARTransaction` record in CustomerLedger + call PostingEngine for DR AR / CR Revenue / CR Tax; all within one transaction in `backend/modules/accounting/handlers/integration_handlers.py`
- [ ] T142 [US6] Wire `HandleSalesCreditNotePosted` event handler: create credit ARTransaction + call PostingEngine for DR Revenue / DR Tax / CR AR in `backend/modules/accounting/handlers/integration_handlers.py`
- [ ] T143 [US6] Implement daily APScheduler job `ar_overdue_check_job()`: find invoices past due_date; update status to OVERDUE; publish `accounting.ar.invoice.overdue` event per invoice; publish `accounting.ar.customer.creditlimit.warning` at 80% threshold in `backend/modules/accounting/services/scheduler.py`
- [ ] T144 [US6] Create Pydantic v2 schemas: `CustomerLedgerResponse`, `ARTransactionResponse`, `ARAgingReport` (with customer rows and bucket totals), `CustomerStatementResponse`, `CreditHoldRequest`, `WriteOffRequest` in `backend/modules/accounting/schemas/ar.py`
- [ ] T145 [US6] Create API endpoints: `GET /accounting/ar/customer-ledger/{customer_id}`, `GET /accounting/ar/aging`, `GET /accounting/ar/customer-statement/{customer_id}`, `POST /accounting/ar/customers/{id}/credit-hold`, `POST /accounting/ar/customers/{id}/credit-hold/release`, `POST /accounting/ar/customers/{id}/credit-limit`, `POST /accounting/ar/transactions/{id}/write-off` in `backend/modules/accounting/router.py`
- [ ] T146 Create Alembic migration `040_accounting_ar_ledger.py` for tables: `accounting_customer_ledgers`, `accounting_ar_transactions`, `accounting_ar_allocations`, `accounting_customer_credit_history`; indexes on `(company_id, customer_id, status, due_date)` in `backend/migrations/versions/040_accounting_ar_ledger.py`
- [ ] T147 [P] [US6] Create frontend Customer Ledger page (per customer: transactions, running balance, outstanding, credit status) in `frontend/src/app/(protected)/(accounting)/receivables/customers/[customerId]/page.tsx`
- [ ] T148 [P] [US6] Create frontend AR Aging Report page (summary table by bucket with customer drill-down) in `frontend/src/app/(protected)/(accounting)/receivables/aging/page.tsx`
- [ ] T149 [P] [US6] Create frontend Customer Statement generator page (select customer + period → preview + download PDF) in `frontend/src/app/(protected)/(accounting)/receivables/statements/page.tsx`
- [ ] T150 [P] [US6] Create frontend Credit Management page (list customers with credit status, hold controls, limit adjustment) in `frontend/src/app/(protected)/(accounting)/receivables/credit-management/page.tsx`
- [ ] T151 Write unit tests for `AgingCalculator` — bucket assignment for boundary dates: invoice due today (Current), 30 days overdue (1-30), 31 days (31-60), etc. in `backend/tests/unit/modules/accounting/test_aging_calculator.py`
- [ ] T152 [P] Write unit tests for credit status auto-calculation: 0% = GOOD, 79% = GOOD, 80% = WARNING, 100% = EXCEEDED, 101% = EXCEEDED in `backend/tests/unit/modules/accounting/test_credit_status.py`
- [ ] T153 Write integration tests for AR: publish `sales.invoice.posted` → verify ARTransaction created and CustomerLedger balance updated → verify AR control account GL balance == CustomerLedger sum in `backend/tests/integration/repositories/accounting/test_ar_repository.py`
- [ ] T154 Write integration tests for credit hold: place hold → verify `accounting.ar.customer.credithold` event published → verify Sales module event received in `backend/tests/integration/repositories/accounting/test_credit_hold.py`
- [ ] T155 Write API tests for AR endpoints (ledger, aging, statement, credit hold, write-off) in `backend/tests/integration/api/v1/accounting/test_ar_api.py`

### Phase 6 Exit Criteria

- [ ] All 24 tasks (T132–T155) complete
- [ ] Sales invoice → AR ledger update is atomic and correct
- [ ] AR control account reconciliation holds after every posting
- [ ] Aging buckets correct for all boundary conditions
- [ ] Credit hold event received by Sales module (cross-module test passes)

---

## Phase 7: Accounts Payable (US7)

**Objective**: Implement the AP sub-module — supplier ledger, bill tracking from Purchase integration, AP aging, vendor credits, supplier statement reconciliation, and remittance advice.

**Business Value**: The AP Clerk can see what is owed to every supplier, prioritize payments, reconcile supplier statements, and generate remittance advice for payments made.

**Story Goal (US7)**: The AP Clerk can view the supplier ledger, run AP aging, reconcile supplier statements, and confirm that AP control account always reconciles to supplier ledger balances.

**Independent Test**: Publish `purchase.bill.posted` → verify SupplierLedger updated; verify AP control account GL == sum of all SupplierLedger open balances.

### Tasks

- [ ] T156 [P] [US7] Create `SupplierLedger` ORM model: supplier_id (Epic 6 reference), total_outstanding_base (materialized), last_payment_date in `backend/modules/accounting/models/ap.py`
- [ ] T157 [P] [US7] Create `APTransaction` ORM model: supplier_ledger_id, transaction_type, transaction_date, due_date, currency_code, exchange_rate, amount_foreign, amount_base, outstanding_amount (denormalized), status, source_document_type, source_document_id, journal_entry_id, bill_number in `backend/modules/accounting/models/ap.py`
- [ ] T158 [P] [US7] Create `APPaymentAllocation` ORM model: ap_transaction_id (bill), payment_id, allocated_amount_foreign, allocated_amount_base, allocated_at, discount_amount in `backend/modules/accounting/models/ap.py`
- [ ] T159 [P] [US7] Create `SupplierStatementReconciliation` ORM model: supplier_id, statement_date, statement_total, status (DRAFT/IN_PROGRESS/COMPLETED) in `backend/modules/accounting/models/ap.py`
- [ ] T160 [P] [US7] Create `SupplierStatementReconciliationItem` ORM model: reconciliation_id, ap_transaction_id, statement_line_reference, statement_amount, gl_amount, match_status (MATCHED/UNMATCHED_GL/UNMATCHED_STATEMENT/DISPUTED), difference in `backend/modules/accounting/models/ap.py`
- [ ] T161 [US7] Implement `SupplierLedgerRepository` with `find_by_supplier()`, `get_open_transactions()`, `get_aging_data()`, `get_statement_data()` in `backend/modules/accounting/repositories/ap.py`
- [ ] T162 [US7] Implement `AccountsPayableService` with `get_supplier_ledger()`, `get_supplier_aging()`, `get_supplier_statement()`, `reconcile_supplier_statement()`, `adjust_payable()`, `generate_remittance_advice(payment_id)` in `backend/modules/accounting/services/ap_service.py`
- [ ] T163 [US7] Wire `HandlePurchaseBillPosted` event handler: create `APTransaction` in SupplierLedger + call PostingEngine for DR Expense/Inventory + DR Input Tax / CR AP in `backend/modules/accounting/handlers/integration_handlers.py`
- [ ] T164 [US7] Wire `HandlePurchaseCreditNotePosted` event handler: create credit APTransaction + call PostingEngine for DR AP / CR Expense + CR Input Tax in `backend/modules/accounting/handlers/integration_handlers.py`
- [ ] T165 [US7] Implement AP control account reconciliation assertion (same pattern as AR): `SUM(ap_transactions.outstanding) == GL_balance(AP_control_account)` in `backend/modules/accounting/services/ap_service.py`
- [ ] T166 [US7] Implement daily APScheduler job `ap_bill_due_reminder_job()`: find bills due within N days (configurable); publish `accounting.ap.bill.due` event per bill in `backend/modules/accounting/services/scheduler.py`
- [ ] T167 [US7] Create Pydantic v2 schemas: `SupplierLedgerResponse`, `APTransactionResponse`, `APAgingReport`, `SupplierStatementReconciliationResponse`, `RemittanceAdviceResponse` in `backend/modules/accounting/schemas/ap.py`
- [ ] T168 [US7] Create API endpoints: `GET /accounting/ap/supplier-ledger/{supplier_id}`, `GET /accounting/ap/aging`, `GET /accounting/ap/supplier-statement/{id}`, `POST /accounting/ap/reconcile-statement`, `GET /accounting/ap/payments/{id}/remittance-advice` in `backend/modules/accounting/router.py`
- [ ] T169 Create Alembic migration `041_accounting_ap_ledger.py` for: `accounting_supplier_ledgers`, `accounting_ap_transactions`, `accounting_ap_allocations`, `accounting_supplier_reconciliations`, `accounting_supplier_reconciliation_items` in `backend/migrations/versions/041_accounting_ap_ledger.py`
- [ ] T170 [P] [US7] Create frontend Supplier Ledger page in `frontend/src/app/(protected)/(accounting)/payables/suppliers/[supplierId]/page.tsx`
- [ ] T171 [P] [US7] Create frontend AP Aging Report page in `frontend/src/app/(protected)/(accounting)/payables/aging/page.tsx`
- [ ] T172 [P] [US7] Create frontend Supplier Statement Reconciliation workspace (side-by-side GL vs statement with match/unmatch actions) in `frontend/src/app/(protected)/(accounting)/payables/reconcile/page.tsx`
- [ ] T173 Write integration tests for AP: `purchase.bill.posted` → APTransaction created → AP control account reconciles in `backend/tests/integration/repositories/accounting/test_ap_repository.py`
- [ ] T174 Write API tests for AP endpoints (ledger, aging, reconciliation, remittance) in `backend/tests/integration/api/v1/accounting/test_ap_api.py`

### Phase 7 Exit Criteria

- [ ] All 19 tasks (T156–T174) complete
- [ ] Purchase bill → AP ledger update atomic and correct
- [ ] AP control account reconciliation holds after every posting

---

## Phase 8: Banking (US8)

**Objective**: Implement bank account management, bank transactions, cheque tracking, and the bank reconciliation workflow.

**Business Value**: The Accountant can manage multiple bank accounts, track all bank transactions, manage cheques, and reconcile GL bank balances to bank statements.

**Story Goal (US8)**: The Accountant can import a bank statement, auto-match GL entries to statement lines, manually match unmatched items, verify the difference is zero, and lock the reconciliation.

**Independent Test**: Import 100 bank statement lines → run auto-match → verify matched count; complete reconciliation → verify `statement_balance == GL_balance`; lock reconciliation → verify no further modifications allowed.

### Tasks

- [ ] T175 [P] [US8] Create `BankAccount` ORM model: bank_name, branch_name, account_number, iban, swift_bic, currency_code, gl_account_id, opening_balance, opening_balance_date, current_gl_balance (materialized), is_active in `backend/modules/accounting/models/banking.py`
- [ ] T176 [P] [US8] Create `BankTransaction` ORM model: bank_account_id, transaction_date, transaction_type (RECEIPT/PAYMENT/TRANSFER/BANK_CHARGE), amount, reference, description, journal_entry_id, is_reconciled, reconciliation_match_id in `backend/modules/accounting/models/banking.py`
- [ ] T177 [P] [US8] Create `BankStatementLine` ORM model: bank_account_id, statement_date, value_date, amount, reference, description, transaction_type, is_matched, reconciliation_match_id in `backend/modules/accounting/models/banking.py`
- [ ] T178 [P] [US8] Create `BankReconciliation` ORM model: bank_account_id, statement_date, statement_closing_balance, gl_balance_at_date, difference (must be 0 to complete), status (DRAFT/IN_PROGRESS/COMPLETED/LOCKED), completed_at, completed_by_user_id in `backend/modules/accounting/models/banking.py`
- [ ] T179 [P] [US8] Create `BankReconciliationMatch` ORM model: reconciliation_id, bank_transaction_id, statement_line_id, match_type (AUTO/MANUAL), matched_at, matched_by_user_id in `backend/modules/accounting/models/banking.py`
- [ ] T180 [P] [US8] Create `Cheque` ORM model: bank_account_id, cheque_number, payee_name, cheque_date, amount, status (ISSUED/PRESENTED/CLEARED/CANCELLED/STALE), bank_transaction_id, bank_statement_line_id, cancelled_at, cancel_reason in `backend/modules/accounting/models/banking.py`
- [ ] T181 [US8] Implement `BankAccountService` with `create_bank_account()`, `update_bank_account()`, `record_bank_transfer()` (creates two-leg journal via PostingEngine: DR destination / CR source), `record_bank_deposit()`, `issue_cheque()`, `update_cheque_status()`, `get_bank_book()` in `backend/modules/accounting/services/bank_service.py`
- [ ] T182 [US8] Implement `BankReconciliationService` with `start_reconciliation()`, `import_statement_lines()` (CSV import), `run_auto_match()` (match by amount + date + reference heuristic), `manual_match()` (user-directed), `unmatch()`, `post_bank_charge()` (auto-creates GL entry via PostingEngine), `complete_reconciliation()` (validates difference == 0), `lock_reconciliation()`, `get_reconciliation_report()` in `backend/modules/accounting/services/bank_service.py`
- [ ] T183 [US8] Publish `accounting.bank.reconciled` event on successful reconciliation lock in `backend/modules/accounting/services/bank_service.py`
- [ ] T184 [US8] Create Pydantic v2 schemas: `BankAccountCreateRequest`, `BankAccountResponse`, `BankTransferRequest`, `BankStatementImportRequest`, `ReconciliationMatchRequest`, `BankReconciliationResponse`, `BankBookRow`, `ChequeResponse` in `backend/modules/accounting/schemas/banking.py`
- [ ] T185 [US8] Create API endpoints: `GET/POST /accounting/bank-accounts`, `GET/PUT /accounting/bank-accounts/{id}`, `POST /accounting/bank-accounts/{id}/transfer`, `POST /accounting/bank-accounts/{id}/reconciliations`, `POST /accounting/bank-accounts/{id}/reconciliations/{rid}/import-statement`, `POST /accounting/bank-accounts/{id}/reconciliations/{rid}/auto-match`, `POST /accounting/bank-accounts/{id}/reconciliations/{rid}/manual-match`, `POST /accounting/bank-accounts/{id}/reconciliations/{rid}/complete`, `POST /accounting/bank-accounts/{id}/reconciliations/{rid}/lock`, `GET /accounting/cheques`, `POST /accounting/cheques` in `backend/modules/accounting/router.py`
- [ ] T186 Create Alembic migration `042_accounting_banking.py` for: `accounting_bank_accounts`, `accounting_bank_transactions`, `accounting_bank_statement_lines`, `accounting_bank_reconciliations`, `accounting_bank_reconciliation_matches`, `accounting_cheques` in `backend/migrations/versions/042_accounting_banking.py`
- [ ] T187 [P] [US8] Create frontend Bank Accounts list and management page in `frontend/src/app/(protected)/(accounting)/banking/page.tsx`
- [ ] T188 [P] [US8] Create frontend Bank Reconciliation workspace (split-panel: GL transactions left, statement lines right; match/unmatch controls; difference indicator; complete/lock buttons) in `frontend/src/app/(protected)/(accounting)/banking/[accountId]/reconcile/page.tsx`
- [ ] T189 [P] [US8] Create frontend Cheque Register page (list with status filter, status update controls) in `frontend/src/app/(protected)/(accounting)/banking/cheques/page.tsx`
- [ ] T190 Write integration tests for bank reconciliation: import 100 statement lines; run auto-match; verify matched items; complete (difference = 0); lock; verify no further modifications in `backend/tests/integration/repositories/accounting/test_bank_reconciliation.py`
- [ ] T191 Write API tests for banking endpoints (CRUD, transfer, reconciliation lifecycle) in `backend/tests/integration/api/v1/accounting/test_banking_api.py`

### Phase 8 Exit Criteria

- [ ] All 17 tasks (T175–T191) complete
- [ ] Bank reconciliation locks when difference == 0
- [ ] Locked reconciliation rejects further modifications
- [ ] Bank transfer creates balanced two-leg GL entry

---

## Phase 9: Cash Management (US9)

**Objective**: Implement cash account management, cash receipts and payments, petty cash voucher system, and cash reconciliation.

**Business Value**: The Cashier can track physical cash accurately. Petty cash vouchers provide auditability for minor expenses. Cash reconciliation ensures physical cash matches GL balance.

**Story Goal (US9)**: The Cashier can record cash receipts and payments, manage petty cash vouchers, reconcile physical cash count to the GL, and process petty cash replenishment.

**Independent Test**: Create petty cash vouchers totalling £150 → run replenishment → verify GL entry: DR individual expense accounts / CR Bank = £150.

### Tasks

- [ ] T192 [P] [US9] Create `CashAccount` ORM model: account_name, currency_code, gl_account_id, current_balance (materialized), is_petty_cash, float_amount, is_active in `backend/modules/accounting/models/cash.py`
- [ ] T193 [P] [US9] Create `CashTransaction` ORM model: cash_account_id, transaction_date, transaction_type (RECEIPT/PAYMENT/TRANSFER/ADJUSTMENT), amount, reference, description, journal_entry_id, counterparty_type, counterparty_id in `backend/modules/accounting/models/cash.py`
- [ ] T194 [P] [US9] Create `PettyCashVoucher` ORM model: cash_account_id, voucher_date, amount, expense_account_id, recipient_name, purpose, approved_by_user_id, voucher_number in `backend/modules/accounting/models/cash.py`
- [ ] T195 [P] [US9] Create `CashReconciliation` ORM model: cash_account_id, reconciliation_date, physical_count_amount, gl_balance_amount, difference, difference_account_id, journal_entry_id, status in `backend/modules/accounting/models/cash.py`
- [ ] T196 [US9] Implement `CashAccountService` with `create_cash_account()`, `record_cash_receipt()` (calls PostingEngine: DR Cash / CR Revenue or AR), `record_cash_payment()` (DR Expense or AP / CR Cash), `create_petty_cash_voucher()`, `replenish_petty_cash()` (creates GL: DR expense accounts from vouchers / CR Bank), `reconcile_cash()` (posts difference to Cash Short/Over account via PostingEngine), `get_cash_book()` in `backend/modules/accounting/services/cash_service.py`
- [ ] T197 [US9] Create Pydantic v2 schemas: `CashAccountResponse`, `CashReceiptRequest`, `CashPaymentRequest`, `PettyCashVoucherRequest`, `PettyCashReplenishmentRequest`, `CashReconciliationRequest`, `CashBookRow` in `backend/modules/accounting/schemas/cash.py`
- [ ] T198 [US9] Create API endpoints: `GET/POST /accounting/cash-accounts`, `POST /accounting/cash-accounts/{id}/receipts`, `POST /accounting/cash-accounts/{id}/payments`, `GET/POST /accounting/cash-accounts/{id}/petty-cash-vouchers`, `POST /accounting/cash-accounts/{id}/replenish`, `POST /accounting/cash-accounts/{id}/reconcile`, `GET /accounting/cash-accounts/{id}/cash-book` in `backend/modules/accounting/router.py`
- [ ] T199 Create Alembic migration `043_accounting_cash_management.py` for: `accounting_cash_accounts`, `accounting_cash_transactions`, `accounting_petty_cash_vouchers`, `accounting_cash_reconciliations` in `backend/migrations/versions/043_accounting_cash_management.py`
- [ ] T200 [P] [US9] Create frontend Cash Accounts list and Cash Book page in `frontend/src/app/(protected)/(accounting)/cash/page.tsx`
- [ ] T201 [P] [US9] Create frontend Petty Cash management page (voucher entry + reconciliation + replenishment workflow) in `frontend/src/app/(protected)/(accounting)/cash/petty-cash/page.tsx`
- [ ] T202 Write integration tests for petty cash: create vouchers → replenishment → verify GL entry correct in `backend/tests/integration/repositories/accounting/test_cash_management.py`
- [ ] T203 Write API tests for cash management endpoints in `backend/tests/integration/api/v1/accounting/test_cash_api.py`

### Phase 9 Exit Criteria

- [ ] All 12 tasks (T192–T203) complete
- [ ] Petty cash replenishment creates correct GL entry
- [ ] Cash reconciliation posts difference to Cash Short/Over account

---

## Phase 10: Payment Processing & Allocation (US10)

**Objective**: Implement the complete payment sub-module — customer receipts, supplier disbursements, the AllocationEngine (partial payments, advance payments, overpayments), refunds, credit/debit notes, and WHT support.

**Business Value**: The AR and AP Clerks can process all inbound and outbound payments with accurate allocation. Outstanding balances are always accurate. The allocation engine handles every payment scenario including FX, WHT, and early payment discounts.

**Story Goal (US10)**: The AR Clerk can process a customer payment allocating to multiple invoices with partial amounts; the AP Clerk can process a supplier payment with early payment discount; the system posts realized FX gain/loss automatically.

**Independent Test**: Post sales invoice in EUR → receive EUR payment at different rate → verify realized gain/loss GL entry created automatically.

### Tasks

- [ ] T204 [P] [US10] Create `Payment` ORM model: payment_type, payment_method, payment_date, currency_code, exchange_rate, amount_foreign, amount_base, bank_account_id, cash_account_id, party_type, party_id, reference, notes, status (DRAFT/POSTED/ALLOCATED/CANCELLED), journal_entry_id, cheque_id, discount_amount in `backend/modules/accounting/models/payments.py`
- [ ] T205 [P] [US10] Create `PaymentAllocationLine` ORM model: payment_id, ar_transaction_id (or ap_transaction_id), allocated_amount_foreign, allocated_amount_base, discount_amount, gain_loss_amount, gain_loss_journal_entry_id in `backend/modules/accounting/models/payments.py`
- [ ] T206 [P] [US10] Create `PaymentRefund` ORM model: original_payment_id, refund_date, amount, reason, journal_entry_id in `backend/modules/accounting/models/payments.py`
- [ ] T207 [US10] Implement `AllocationEngine` domain service with `allocate(payment_id, allocation_lines)`:
  - For each line: SELECT FOR UPDATE on ARTransaction/APTransaction row
  - Validate: allocated_amount ≤ outstanding_amount
  - Calculate realized FX gain/loss: if settlement rate ≠ booking rate → PostingEngine posts gain/loss entry
  - INSERT PaymentAllocationLine
  - UPDATE ARTransaction/APTransaction outstanding_amount -= allocated_amount
  - Update status (PAID if outstanding = 0, PARTIALLY_PAID if > 0)
  - If discount_amount > 0: PostingEngine posts discount entry (DR AR / CR Discount Income)
  in `backend/modules/accounting/services/allocation_engine.py`
- [ ] T208 [US10] Implement `PaymentService` with `create_customer_payment()` (DR Bank/Cash / CR AR), `create_supplier_payment()` (DR AP / CR Bank/Cash), `allocate_payment()` (calls AllocationEngine), `reallocate_payment()` (reverse prior + new allocation), `cancel_payment()`, `process_refund()`, `get_payment()`, `list_unallocated_payments()` in `backend/modules/accounting/services/payment_service.py`
- [ ] T209 [US10] Implement advance payment handling in `PaymentService`: advance posted to designated advance account; defer allocation until invoice raised; track as open advance in `backend/modules/accounting/services/payment_service.py`
- [ ] T210 [US10] Implement overpayment handling: capture excess as credit on customer/supplier account; visible in aging as credit balance; can be refunded or applied to future invoices in `backend/modules/accounting/services/payment_service.py`
- [ ] T211 [US10] Implement WHT support (feature flag: `accounting.taxwithholding.enabled`): deduct WHT from gross supplier payment; post WHT to WHT payable account via PostingEngine; generate WHT certificate data in `backend/modules/accounting/services/payment_service.py`
- [ ] T212 [US10] Wire `HandleSalesPaymentReceived` event handler (payments originating from Epic 7): post GL and update CustomerLedger in `backend/modules/accounting/handlers/integration_handlers.py`
- [ ] T213 [US10] Wire `HandleSupplierPaymentMade` event handler (payments originating from Epic 6): post GL and update SupplierLedger in `backend/modules/accounting/handlers/integration_handlers.py`
- [ ] T214 [US10] Create Pydantic v2 schemas: `CustomerPaymentRequest`, `SupplierPaymentRequest`, `AllocationLineRequest`, `PaymentAllocationRequest`, `PaymentResponse`, `RefundRequest`, `WHTCertificateResponse` in `backend/modules/accounting/schemas/payments.py`
- [ ] T215 [US10] Create API endpoints: `GET/POST /accounting/payments/customer`, `GET/POST /accounting/payments/supplier`, `POST /accounting/payments/{id}/allocate`, `POST /accounting/payments/{id}/reallocate`, `POST /accounting/payments/{id}/cancel`, `POST /accounting/payments/{id}/refund`, `GET /accounting/payments/unallocated`, `GET /accounting/payments/{id}/wht-certificate` in `backend/modules/accounting/router.py`
- [ ] T216 Create Alembic migration `044_accounting_payments.py` for: `accounting_payments`, `accounting_payment_allocation_lines`, `accounting_payment_refunds` in `backend/migrations/versions/044_accounting_payments.py`
- [ ] T217 [P] [US10] Create frontend Customer Payment page (payment form + allocation table with invoice selection and amounts) in `frontend/src/app/(protected)/(accounting)/payments/customer/page.tsx`
- [ ] T218 [P] [US10] Create frontend Supplier Payment page (payment form + bill allocation table) in `frontend/src/app/(protected)/(accounting)/payments/supplier/page.tsx`
- [ ] T219 [P] [US10] Create frontend Unallocated Payments report page (list of payments not yet fully allocated, with allocate action) in `frontend/src/app/(protected)/(accounting)/payments/unallocated/page.tsx`
- [ ] T220 Write unit tests for `AllocationEngine`: over-allocation raises error; partial allocation updates outstanding correctly; realized FX gain calculated correctly (EUR invoice at rate 1.1 settled at 1.15 = gain); concurrent allocation to same invoice uses row lock in `backend/tests/unit/modules/accounting/test_allocation_engine.py`
- [ ] T221 [P] Write unit tests for WHT calculation: gross 1000 WHT 10% → payment 900, WHT payable 100; GL entries correct in `backend/tests/unit/modules/accounting/test_wht.py`
- [ ] T222 Write integration tests for full Sales-to-Cash flow: invoice → customer payment → allocation → invoice outstanding = 0 → AR control account reconciles in `backend/tests/integration/repositories/accounting/test_payment_allocation.py`
- [ ] T223 Write API tests for payment endpoints (customer/supplier payment, allocation, refund, WHT) in `backend/tests/integration/api/v1/accounting/test_payment_api.py`

### Phase 10 Exit Criteria

- [ ] All 20 tasks (T204–T223) complete
- [ ] Full Sales-to-Cash workflow verified (invoice → payment → zero outstanding)
- [ ] Full Purchase-to-Pay workflow verified (bill → payment → zero outstanding)
- [ ] Realized FX gain/loss posted automatically on settlement
- [ ] WHT deduction and GL posting correct

---

## Phase 11: Tax Engine & Cost Centers (US11, US12)

**Objective**: Implement configurable tax codes, tax groups, tax calculation engine, tax reports, WHT reporting, cost centers, departments, and projects.

**Business Value**: The Tax Consultant can configure tax codes for any jurisdiction, generate VAT/GST returns, and prepare WHT reports. The CFO can track costs and revenue by cost center and project.

**Story Goal (US11)**: The Tax Consultant can configure a VAT code at 15% for sales and purchases; transactions automatically apply the tax; the VAT return shows correct output tax, input tax, and net payable.

**Story Goal (US12)**: The Controller can set up cost centers and require their assignment on expense accounts; the Cost Center P&L shows revenue and expenses correctly by center.

### Tasks

- [ ] T224 [P] [US11] Create `TaxCode` ORM model: tax_code, tax_name, tax_type, applicability, gl_account_id, is_input_tax_recoverable, country_code, is_active + soft-delete + audit stamps in `backend/modules/accounting/models/tax.py`
- [ ] T225 [P] [US11] Create `TaxRate` ORM model: tax_code_id, effective_from, effective_to, rate (Decimal), rounding_rule in `backend/modules/accounting/models/tax.py`
- [ ] T226 [P] [US11] Create `TaxGroup` ORM model: group_code, group_name, applicability, is_active in `backend/modules/accounting/models/tax.py`
- [ ] T227 [P] [US11] Create `TaxGroupLine` ORM model: tax_group_id, tax_code_id, display_order in `backend/modules/accounting/models/tax.py`
- [ ] T228 [P] [US12] Create `CostCenter` ORM model: center_code, center_name, department_id, responsible_user_id, is_active + soft-delete + audit stamps in `backend/modules/accounting/models/cost.py`
- [ ] T229 [P] [US12] Create `Department` ORM model: dept_code, dept_name, parent_dept_id, is_active in `backend/modules/accounting/models/cost.py`
- [ ] T230 [P] [US12] Create `Project` ORM model: project_code, project_name, start_date, end_date, budget_amount, responsible_user_id, is_active in `backend/modules/accounting/models/cost.py`
- [ ] T231 [US11] Implement `TaxCalculator` domain service with `calculate(tax_code_or_group_id, base_amount, transaction_date, is_tax_inclusive)` → returns list of `TaxAmount` value objects; applies correct effective rate for transaction date; handles zero-rated and exempt (returns 0.00 amount but still reportable) in `backend/modules/accounting/services/tax_calculator.py`
- [ ] T232 [US11] Implement `TaxService` with `create_tax_code()`, `update_tax_rate()` (validates no date overlap), `create_tax_group()`, `add_group_line()`, `get_vat_summary_report(period_start, period_end)`, `get_tax_detail_report(filters)`, `get_wht_report(period)` in `backend/modules/accounting/services/tax_service.py`
- [ ] T233 [US12] Implement `CostCenterService` with `create_cost_center()`, `create_department()`, `create_project()`, `get_cost_center_pl_report(cost_center_id, period)`, `get_project_report(project_id, period)` in `backend/modules/accounting/services/cost_center_service.py`
- [ ] T234 [US11] Create Pydantic v2 schemas for TaxCode, TaxRate, TaxGroup, TaxCalculationRequest, TaxCalculationResult, TaxSummaryReport, TaxDetailRow, WHTReport in `backend/modules/accounting/schemas/tax.py`
- [ ] T235 [US12] Create Pydantic v2 schemas for CostCenter, Department, Project, CostCenterPLReport in `backend/modules/accounting/schemas/cost.py`
- [ ] T236 [US11] Create API endpoints: `GET/POST /accounting/tax-codes`, `GET/PUT /accounting/tax-codes/{id}`, `POST /accounting/tax-codes/{id}/rates`, `GET/POST /accounting/tax-groups`, `GET /accounting/reports/tax-summary`, `GET /accounting/reports/tax-detail`, `GET /accounting/reports/wht` in `backend/modules/accounting/router.py`
- [ ] T237 [US12] Create API endpoints: `GET/POST /accounting/cost-centers`, `GET/POST /accounting/departments`, `GET/POST /accounting/projects`, `GET /accounting/reports/cost-center-pl`, `GET /accounting/reports/project-pl` in `backend/modules/accounting/router.py`
- [ ] T238 Create Alembic migrations: `045_accounting_tax_engine.py` (tax_codes, tax_rates, tax_groups, tax_group_lines) and `046_accounting_cost_centers.py` (cost_centers, departments, projects) in `backend/migrations/versions/`
- [ ] T239 [P] [US11] Create frontend Tax Code management page in `frontend/src/app/(protected)/(accounting)/tax/codes/page.tsx`
- [ ] T240 [P] [US11] Create frontend Tax Group management page in `frontend/src/app/(protected)/(accounting)/tax/groups/page.tsx`
- [ ] T241 [P] [US11] Create frontend Tax Summary Report page (output tax, input tax, net payable by period) in `frontend/src/app/(protected)/(accounting)/reports/tax-summary/page.tsx`
- [ ] T242 [P] [US12] Create frontend Cost Center management page in `frontend/src/app/(protected)/(accounting)/cost-centers/page.tsx`
- [ ] T243 [P] [US12] Create frontend Cost Center P&L Report page in `frontend/src/app/(protected)/(accounting)/reports/cost-center-pl/page.tsx`
- [ ] T244 Write unit tests for `TaxCalculator`: correct rate for transaction date; date range boundary (effective_from, effective_to); zero-rated returns 0.00 but reportable; tax group applies all member codes in `backend/tests/unit/modules/accounting/test_tax_calculator.py`
- [ ] T245 Write integration tests for tax: post invoice with VAT code → verify tax GL entry created; run VAT summary → verify output == sum of posted tax amounts in `backend/tests/integration/repositories/accounting/test_tax_engine.py`
- [ ] T246 Write API tests for tax and cost center endpoints in `backend/tests/integration/api/v1/accounting/test_tax_api.py`

### Phase 11 Exit Criteria

- [ ] All 23 tasks (T224–T246) complete
- [ ] Tax rate resolution correct for all boundary dates
- [ ] VAT summary report output == sum of all posted tax entries for period
- [ ] Cost center assignment enforced on required accounts
- [ ] Cost Center P&L report aggregates correctly

---

## Phase 12: Multi-Currency & Exchange Rates (US12)

**Objective**: Activate multi-currency operations — FX rate management, realized gain/loss at payment settlement, unrealized gain/loss via period-end revaluation, and multi-currency financial statement reporting.

**Business Value**: The CFO can manage foreign currency transactions accurately. Realized and unrealized FX differences are automatically calculated and posted, ensuring financial statements reflect true currency exposure.

**Story Goal (US12)**: A EUR invoice is raised at rate 1.10; payment received at rate 1.15; system automatically posts a realized FX gain of (1.15 − 1.10) × invoice_amount.

**Independent Test**: Post EUR invoice at rate 1.10 → post EUR payment at rate 1.15 → verify realized gain journal entry created and posted by AllocationEngine automatically.

### Tasks

- [ ] T247 [US12] Implement `CurrencyRevaluationService` with `run_revaluation(company_id, period_id, revaluation_date)`:
  - Query all open foreign currency AR/AP transactions
  - Compare booking rate to current revaluation rate from ExchangeRateRepository
  - Calculate unrealized gain/loss per transaction
  - Create one aggregated PostingRequest via PostingEngine for all unrealized differences
  - Record revaluation as reversible (creates reversal template for next period)
  - Return revaluation report data
  in `backend/modules/accounting/services/currency_revaluation_service.py`
- [ ] T248 [US12] Implement multi-currency financial statement generation in `FinancialStatementService`: `get_balance_sheet(company_id, date, report_currency)` — translate foreign balances using closing rate; `get_pl(company_id, period, report_currency)` — translate using average rate in `backend/modules/accounting/services/financial_statements.py`
- [ ] T249 [US12] Publish `accounting.revaluation.completed` event on revaluation completion in `backend/modules/accounting/services/currency_revaluation_service.py`
- [ ] T250 [US12] Create Pydantic v2 schemas: `RevaluationRequest`, `RevaluationReport`, `RevaluationLine` in `backend/modules/accounting/schemas/currency.py`
- [ ] T251 [US12] Create API endpoints: `POST /accounting/currency-revaluation`, `GET /accounting/currency-revaluation/history`, `GET /accounting/currency-revaluation/{id}/report` in `backend/modules/accounting/router.py`
- [ ] T252 [P] [US12] Create frontend Currency Revaluation page (select period + rates + preview report before confirming) in `frontend/src/app/(protected)/(accounting)/currency-revaluation/page.tsx`
- [ ] T253 Write unit tests for `CurrencyRevaluationService`: EUR invoice at 1.10 revalued at 1.15 → unrealized gain = 0.05 × amount; revaluation creates correct GL entry in `backend/tests/unit/modules/accounting/test_currency_revaluation.py`
- [ ] T254 Write integration tests for FX settlement: post EUR invoice → post EUR payment at different rate → verify realized gain/loss GL entry exists in `backend/tests/integration/repositories/accounting/test_fx_settlement.py`

### Phase 12 Exit Criteria

- [ ] All 8 tasks (T247–T254) complete
- [ ] Realized FX gain/loss posted automatically at payment settlement
- [ ] Period-end revaluation creates correct unrealized gain/loss entry
- [ ] Multi-currency P&L uses average rate; Balance Sheet uses closing rate

---

## Phase 13: Financial Statements & Reports (US13)

**Objective**: Implement all financial statements and management reports — Trial Balance, Balance Sheet, P&L, Cash Flow, GL Report, Customer/Supplier Ledger Reports, Bank Book, Cash Book, Journal Report, and export to PDF/Excel.

**Business Value**: The CFO and Business Owner have full financial visibility in real-time. All reports required for management, compliance, and audit are available without external software.

**Story Goal (US13)**: The CFO can view the Balance Sheet at any date — it shows correct total assets, total liabilities, total equity — and Assets always equal Liabilities + Equity. The P&L shows net income for any period.

**Independent Test**: Post known test dataset (10 invoices, 5 expenses, 3 payments) → generate Balance Sheet → verify Assets == Liabilities + Equity; generate P&L → verify net income matches expected value from test data.

### Tasks

- [ ] T255 [US13] Implement `FinancialStatementService` with:
  - `get_trial_balance(company_id, period_id, comparative_period_id=None)` — aggregate GL lines by account with debit/credit totals; verify total debits == total credits
  - `get_balance_sheet(company_id, date, comparative_date=None, report_currency=None)` — aggregate asset/liability/equity accounts; verify Assets == Liabilities + Equity
  - `get_pl(company_id, period_from, period_to, comparative_from=None, comparative_to=None, cost_center_id=None)` — aggregate revenue and expense accounts
  - `get_cash_flow(company_id, period_from, period_to)` — indirect method: net income + non-cash adjustments + working capital changes
  in `backend/modules/accounting/services/financial_statements.py`
- [ ] T256 [US13] Implement `GLReportService` with `get_gl_report(company_id, filters, pagination)` — detailed GL entries with account/date/cost_center filters; cursor-based pagination for > 10K rows in `backend/modules/accounting/services/report_service.py`
- [ ] T257 [US13] Implement subsidiary ledger reports: `get_customer_ledger_report(company_id, customer_id, from_date, to_date)`, `get_supplier_ledger_report(company_id, supplier_id, from_date, to_date)`, `get_bank_book(company_id, bank_account_id, from_date, to_date)`, `get_cash_book(company_id, cash_account_id, from_date, to_date)`, `get_journal_report(company_id, period_id)` in `backend/modules/accounting/services/report_service.py`
- [ ] T258 [US13] Implement report export utilities: `export_to_pdf(report_data, template)` (using ReportLab or WeasyPrint), `export_to_excel(report_data)` (using openpyxl) in `backend/modules/accounting/services/report_export.py`
- [ ] T259 [US13] Create Pydantic v2 schemas: `TrialBalanceRow`, `TrialBalanceReport`, `BalanceSheetSection`, `BalanceSheetReport`, `PLSection`, `PLReport`, `CashFlowReport`, `GLReportRow`, `GLReportResponse` in `backend/modules/accounting/schemas/reports.py`
- [ ] T260 [US13] Create API endpoints for all financial statements and reports: `GET /accounting/reports/trial-balance`, `GET /accounting/reports/balance-sheet`, `GET /accounting/reports/profit-loss`, `GET /accounting/reports/cash-flow`, `GET /accounting/reports/gl` (paginated), `GET /accounting/reports/customer-ledger/{id}`, `GET /accounting/reports/supplier-ledger/{id}`, `GET /accounting/reports/bank-book/{id}`, `GET /accounting/reports/cash-book/{id}`, `GET /accounting/reports/journals` in `backend/modules/accounting/router.py`
- [ ] T261 [US13] Add export query parameters to all report endpoints: `?format=pdf` and `?format=excel` triggers report export response in `backend/modules/accounting/router.py`
- [ ] T262 [P] [US13] Create frontend Balance Sheet page (hierarchical view by account group; comparative column; expand/collapse groups) in `frontend/src/app/(protected)/(accounting)/reports/balance-sheet/page.tsx`
- [ ] T263 [P] [US13] Create frontend Profit & Loss page (revenue/COGS/expenses sections; gross margin; net profit; comparative column; cost center filter) in `frontend/src/app/(protected)/(accounting)/reports/profit-loss/page.tsx`
- [ ] T264 [P] [US13] Create frontend Trial Balance page (account list with debit/credit totals; balance check indicator; comparative column) in `frontend/src/app/(protected)/(accounting)/reports/trial-balance/page.tsx`
- [ ] T265 [P] [US13] Create frontend Cash Flow Statement page (operating/investing/financing sections) in `frontend/src/app/(protected)/(accounting)/reports/cash-flow/page.tsx`
- [ ] T266 [P] [US13] Create frontend Bank Book and Cash Book report pages in `frontend/src/app/(protected)/(accounting)/reports/bank-book/page.tsx` and `.../cash-book/page.tsx`
- [ ] T267 [P] [US13] Create frontend Journal Report page in `frontend/src/app/(protected)/(accounting)/reports/journals/page.tsx`
- [ ] T268 [P] [US13] Create reusable `ExportButton` component (PDF/Excel download trigger) in `frontend/src/components/accounting/ExportButton.tsx`
- [ ] T269 Write unit tests for `FinancialStatementService` against known test dataset:
  - Balance Sheet: Assets == Liabilities + Equity
  - P&L: net income matches expected
  - Trial Balance: total debits == total credits
  - P&L net income == Balance Sheet retained earnings movement for period
  in `backend/tests/unit/modules/accounting/test_financial_statements.py`
- [ ] T270 Write performance tests for financial statement generation: 500K GL entries → trial balance < 10s; financial statements < 15s in `backend/tests/performance/accounting/test_report_performance.py`
- [ ] T271 Write API tests for all report endpoints (correctness, filters, export formats) in `backend/tests/integration/api/v1/accounting/test_reports_api.py`

### Phase 13 Exit Criteria

- [ ] All 17 tasks (T255–T271) complete
- [ ] Balance Sheet equation holds: Assets == Liabilities + Equity (verified in every test)
- [ ] Trial Balance: total debits == total credits
- [ ] P&L net income == Balance Sheet retained earnings movement
- [ ] Financial statements generated in < 15s for 500K GL entries (performance test passes)
- [ ] PDF and Excel export functional for all reports

---

## Phase 14: Financial Controls & Audit Trail (US14)

**Objective**: Implement financial approval workflows, period locking (cross-module), SoD enforcement, financial permissions RBAC, and the complete audit trail system.

**Business Value**: The CFO can enforce financial governance — no large journal or payment is posted without proper authorization. Period controls prevent retroactive manipulation. The audit trail gives auditors complete visibility of all financial actions.

**Story Goal (US14)**: The Controller can configure approval thresholds; journals above the threshold require approval before posting; the approver cannot be the same person who created the journal; the full approval decision trail is auditable.

**Independent Test**: Create journal above threshold → verify status = SUBMITTED; have same user approve → verify rejected (self-approval blocked); have different Controller approve → verify journal posts.

### Tasks

- [ ] T272 [US14] Implement configurable approval threshold in `AccountingConfiguration`: `journal_approval_threshold`, `payment_approval_threshold` — PostingEngine checks these thresholds against journal total in `backend/modules/accounting/services/posting_engine.py`
- [ ] T273 [US14] Implement journal approval workflow in `JournalEntryService`: `submit_for_approval()`, `approve_journal(approver_id)` (validates approver ≠ creator), `reject_journal(approver_id, reason)` — all transitions logged to audit in `backend/modules/accounting/services/journal_service.py`
- [ ] T274 [US14] Implement payment approval workflow in `PaymentService` (when `payment_approval_threshold` exceeded): same pattern as journal approval in `backend/modules/accounting/services/payment_service.py`
- [ ] T275 [US14] Implement period-lock cross-module enforcement: accounting module maintains a `PeriodLockCache` (company_id → {period_id: status}); updated on `accounting.period.locked` and `accounting.period.unlocked` events; PostingEngine reads from cache for fast period status check in `backend/modules/accounting/services/period_lock_cache.py`
- [ ] T276 [US14] Implement SoD enforcement RBAC check: before approving any financial document, verify approver_user_id ≠ created_by_user_id AND approver has `accounting.<resource>.approve` permission via Epic 4 RBAC in `backend/modules/accounting/services/journal_service.py`
- [ ] T277 [US14] Verify all financial RBAC permissions are registered in Epic 4 permission store: create 20+ accounting permissions (`accounting.journal.create`, `accounting.journal.approve`, `accounting.period.lock`, etc.) via migration or seed in `backend/migrations/versions/047_accounting_audit_indexes.py`
- [ ] T278 [US14] Implement comprehensive audit log for all financial events: ensure `AuditLogService.record()` is called by every application service method that modifies financial state (cover JournalEntryService, PaymentService, ARService, APService, FiscalCalendarService, BankAccountService) in `backend/modules/accounting/services/audit_service.py`
- [ ] T279 [US14] Create API endpoints: `GET /accounting/audit-log` (filterable by entity_type, entity_id, actor, action, date range; paginated), `GET /accounting/audit-log/export` (Excel/CSV export of audit records) in `backend/modules/accounting/router.py`
- [ ] T280 Create Alembic migration `047_accounting_audit_indexes.py` for: performance indexes on `accounting_audit_log`; accounting RBAC permissions seed; composite index on `accounting_journal_lines(company_id, fiscal_period_id, account_id)` in `backend/migrations/versions/047_accounting_audit_indexes.py`
- [ ] T281 [P] [US14] Create frontend Audit Trail page (searchable immutable audit history with entity type, action, user, date filters) in `frontend/src/app/(protected)/(accounting)/audit-trail/page.tsx`
- [ ] T282 Write security tests for financial controls: SoD blocked (creator = approver → 403); Controller cannot close fiscal year (only CFO); Accountant cannot approve own journal; cross-tenant data access → 403 in `backend/tests/security/accounting/test_financial_controls.py`
- [ ] T283 Write security tests for RBAC: all 20+ permission checks verified with correct roles granted and denied; verify no endpoint is accessible without authentication in `backend/tests/security/accounting/test_rbac.py`
- [ ] T284 Write security tests for data isolation: Company A journal NOT visible in Company B journal list; Company A customer ledger NOT accessible with Company B credentials in `backend/tests/security/accounting/test_tenant_isolation.py`
- [ ] T285 Write security tests for GL immutability: no PUT/DELETE endpoints exist for posted journal lines; DB constraint also blocks direct SQL update in `backend/tests/security/accounting/test_immutability.py`

### Phase 14 Exit Criteria

- [ ] All 14 tasks (T272–T285) complete
- [ ] SoD enforcement: creator cannot be sole approver (verified in security tests)
- [ ] Period lock enforced immediately across all modules
- [ ] Audit trail complete and immutable for all financial events
- [ ] All 20+ RBAC permissions verified with correct role grants/denials
- [ ] Cross-tenant isolation: zero data leakage (all isolation tests pass)

---

## Phase 15: Financial Intelligence & KPI Dashboard (US15)

**Objective**: Implement the CFO KPI dashboard with real-time financial KPIs, AR/AP overviews, and cash position.

**Business Value**: The Business Owner and CFO have a single-screen view of financial health — cash position, receivables, payables, margins, and ratios — without generating separate reports.

**Story Goal (US15)**: The CFO can see all 15 financial KPIs on the dashboard with real-time values; cash position updates within seconds of a payment being processed.

**Independent Test**: Post customer payment → refresh CFO dashboard → verify Cash Position KPI updates; verify AR total decreases by payment amount.

### Tasks

- [ ] T286 [US15] Implement `FinancialKPIService` calculating all 15 KPIs in real-time: Cash Position (sum all bank + cash GL balances), Total AR, Total AP, AR Overdue %, AP Overdue %, Revenue MTD, Gross Profit Margin, Net Profit Margin, Current Ratio, Quick Ratio, DSO (average days to collect), DPO (average days to pay), Operating Cash Flow (from Cash Flow statement), Tax Liability Balance, Period Close Status in `backend/modules/accounting/services/kpi_service.py`
- [ ] T287 [US15] Create API endpoint: `GET /accounting/dashboard/kpis` → returns all 15 KPIs with values and change vs prior period in `backend/modules/accounting/router.py`
- [ ] T288 [US15] Create API endpoint: `GET /accounting/dashboard/cash-position` → bank + cash account balances with trend data in `backend/modules/accounting/router.py`
- [ ] T289 [US15] Create Pydantic v2 schemas: `FinancialKPIResponse`, `KPIValue` (current_value, prior_value, change_pct, trend), `CashPositionResponse` in `backend/modules/accounting/schemas/dashboard.py`
- [ ] T290 [P] [US15] Create frontend CFO KPI Dashboard page (grid of KPI cards with current value, trend indicator, sparkline; real-time refresh every 60s) in `frontend/src/app/(protected)/(accounting)/dashboard/page.tsx`
- [ ] T291 [P] [US15] Create reusable `KPICard` component with value, trend, and sparkline in `frontend/src/components/accounting/KPICard.tsx`
- [ ] T292 Write unit tests for `FinancialKPIService`: each KPI calculated correctly from known test data; DSO calculation correct; Current Ratio formula verified in `backend/tests/unit/modules/accounting/test_kpi_service.py`
- [ ] T293 Write API tests for dashboard endpoints (KPIs return correct structure; cash position accurate after payment) in `backend/tests/integration/api/v1/accounting/test_dashboard_api.py`

### Phase 15 Exit Criteria

- [ ] All 8 tasks (T286–T293) complete
- [ ] All 15 KPIs return correct values for known test dataset
- [ ] Dashboard accessible to CFO role; blocked for Cashier role

---

## Phase 16: Integration Readiness & Contracts (US16)

**Objective**: Generate the complete OpenAPI specification, verify all Epic 5–7 integration event contracts, run end-to-end workflow integration tests, and validate import/export capabilities.

**Business Value**: External teams, future microservices, and AI integrations can consume the accounting API with confidence. All cross-module contracts are verified and documented.

**Story Goal (US16)**: The full Sales-to-Cash workflow (Epic 7 invoice → Accounting GL → Payment → Zero AR) and Purchase-to-Pay workflow (Epic 6 bill → Accounting GL → Payment → Zero AP) are verified end-to-end in automated tests.

### Tasks

- [ ] T294 Generate OpenAPI specification `contracts/accounting-v1.yaml` covering all 100+ accounting endpoints; verify all request/response schemas are documented; verify all error responses are typed in `specs/008-accounting-finance/contracts/accounting-v1.yaml`
- [ ] T295 [P] Write end-to-end integration test: full Sales-to-Cash flow — `sales.invoice.posted` → AR created → customer payment → AR outstanding = 0 → GL verified in `backend/tests/integration/api/v1/accounting/test_e2e_sales_to_cash.py`
- [ ] T296 [P] Write end-to-end integration test: full Purchase-to-Pay flow — `purchase.bill.posted` → AP created → supplier payment → AP outstanding = 0 → GL verified in `backend/tests/integration/api/v1/accounting/test_e2e_purchase_to_pay.py`
- [ ] T297 [P] Write integration test: Inventory adjustment event → GL inventory control account entry created correctly in `backend/tests/integration/api/v1/accounting/test_e2e_inventory_gl.py`
- [ ] T298 Write integration test: month-end close workflow — post all journals → bank reconcile → lock period → generate statements → verify all pass in `backend/tests/integration/api/v1/accounting/test_e2e_month_end_close.py`
- [ ] T299 [P] Test COA bulk import with 500 accounts: import via API → verify all accounts created; test with validation errors → verify row-level error report in `backend/tests/integration/api/v1/accounting/test_bulk_import.py`
- [ ] T300 [P] Test GL export with 500K entries: export completes within performance budget; all rows present in output file in `backend/tests/performance/accounting/test_gl_export.py`
- [ ] T301 [P] Test bank statement CSV import with 5000 lines: import completes < 30s; all lines stored correctly in `backend/tests/integration/api/v1/accounting/test_bank_statement_import.py`
- [ ] T302 Run `.specify/scripts/bash/update-agent-context.sh claude` to confirm CLAUDE.md is updated with all Phase 16 changes in `CLAUDE.md`

### Phase 16 Exit Criteria

- [ ] All 9 tasks (T294–T302) complete
- [ ] OpenAPI spec covers all endpoints; no undocumented endpoints
- [ ] End-to-end S2C and P2P integration tests pass
- [ ] Import/export tested for COA, GL, bank statement

---

## Phase 17: AI ERP Readiness (US16)

**Objective**: Verify all AI readiness hooks are in place — event stream structured for ML consumption, anomaly detection stub, forecasting data endpoints, and AI feature flag architecture.

**Business Value**: Prepares the Accounting module for future AI capabilities without requiring refactoring. AI developers can begin work on anomaly detection and forecasting immediately.

### Tasks

- [ ] T303 [P] Verify `accounting.journal.posted` event payload includes all fields needed for ML anomaly detection: amount, account_type, time_of_day, user_id, posting_source, reference — document any gaps in `specs/008-accounting-finance/contracts/events.md`
- [ ] T304 [P] Create AI-ready GL event stream endpoint: `GET /accounting/events/stream?from={date}` — returns paginated journal event history for ML training data consumption (read-only; gated by `accounting.ai.enabled` feature flag) in `backend/modules/accounting/router.py`
- [ ] T305 [P] Create AI-ready P&L history endpoint: `GET /accounting/ai/pl-history?periods=24` — returns last N period P&L data structured for revenue/expense forecasting ML models (gated by feature flag) in `backend/modules/accounting/router.py`
- [ ] T306 [P] Create AI-ready cash flow history endpoint: `GET /accounting/ai/cashflow-history?periods=12` — returns historical cash flow data for cash flow forecasting models in `backend/modules/accounting/router.py`
- [ ] T307 [P] Create anomaly detection stub endpoint: `POST /accounting/ai/anomaly-report` — accepts list of journal_entry_ids flagged as anomalies; stores in `accounting_anomaly_flags` table; publishes `accounting.anomaly.detected` event (gated by feature flag) in `backend/modules/accounting/router.py`
- [ ] T308 Create Pydantic v2 schemas for all AI endpoints: `GLEventStreamRow`, `PLHistoryResponse`, `CashFlowHistoryResponse`, `AnomalyReportRequest` in `backend/modules/accounting/schemas/ai.py`
- [ ] T309 Verify `accounting.ai.enabled` feature flag correctly gates all AI endpoints: when false → 403; when true → 200 with data in `backend/tests/integration/api/v1/accounting/test_ai_readiness.py`

### Phase 17 Exit Criteria

- [ ] All 7 tasks (T303–T309) complete
- [ ] AI event stream endpoint accessible when feature flag enabled
- [ ] Anomaly detection stub operational
- [ ] All AI endpoints gated by `accounting.ai.enabled` flag

---

## Phase 18: Testing, Validation & Documentation (US16)

**Objective**: Complete the full test suite — unit, integration, API, security, performance, Docker — verify all acceptance criteria from spec.md §64, and finalize all documentation.

**Business Value**: The Accounting module is production-ready, fully tested, and trusted. The CFO and auditors can rely on the data.

### Tasks

- [ ] T310 Run the complete unit test suite for the accounting module: verify all unit tests pass in `backend/tests/unit/modules/accounting/` with pytest; 0 failures required in `backend/tests/unit/modules/accounting/`
- [ ] T311 [P] Run the complete integration test suite: `pytest backend/tests/integration/repositories/accounting/ -v`; 0 failures required in `backend/tests/integration/repositories/accounting/`
- [ ] T312 [P] Run the complete API test suite: `pytest backend/tests/integration/api/v1/accounting/ -v`; 0 failures required in `backend/tests/integration/api/v1/accounting/`
- [ ] T313 [P] Run the complete security test suite: `pytest backend/tests/security/accounting/ -v`; ALL PASS required (cross-tenant, RBAC, immutability, SoD) in `backend/tests/security/accounting/`
- [ ] T314 Run performance benchmark suite: trial balance 500K entries < 10s; P&L generation < 15s; AR aging 10K customers < 5s; payment processing < 2s; concurrent journal posting 100 requests — no deadlocks in `backend/tests/performance/accounting/`
- [ ] T315 Execute Docker full validation: `docker compose down -v && docker compose up -d && alembic upgrade head` (all 47 migrations apply cleanly from scratch); `alembic downgrade base` and `alembic upgrade head` (bi-directional verified) in Docker environment
- [ ] T316 [P] Execute smoke test: create company → configure accounting → set up COA from Retail template → create fiscal year → post manual journal → verify GL → post sales invoice event → verify AR → process payment → verify zero balance → generate balance sheet → verify equation holds
- [ ] T317 [P] Verify all 64-section acceptance criteria from `specs/008-accounting-finance/spec.md §64` — create checklist doc and mark each criterion as PASS or FAIL in `specs/008-accounting-finance/checklists/acceptance-criteria.md`
- [ ] T318 [P] Verify regression: run Epic 5, 6, 7 test suites — confirm 0 regressions introduced by accounting module in `backend/tests/`
- [ ] T319 Update `specs/008-accounting-finance/quickstart.md` with final confirmed import paths, actual migration numbers, APScheduler configuration, and any deviations from original plan in `specs/008-accounting-finance/quickstart.md`
- [ ] T320 [P] Update `CLAUDE.md` with Epic 8 completion note: "008-accounting-finance: Accounting & Finance module complete — Phases 1–18 done" in `CLAUDE.md`
- [ ] T321 [P] Create PHR for epic closure: run `.specify/scripts/bash/create-phr.sh --title "Epic 8 Accounting Finance Epic Closure" --stage misc --feature "008-accounting-finance" --json` in `history/prompts/008-accounting-finance/`

### Phase 18 Exit Criteria

- [ ] All 12 tasks (T310–T321) complete
- [ ] ALL unit tests PASS (0 failures)
- [ ] ALL integration tests PASS (0 failures)
- [ ] ALL security tests PASS (0 failures)
- [ ] ALL performance benchmarks met
- [ ] Docker full migration verified (up and down)
- [ ] All spec.md §64 acceptance criteria marked PASS
- [ ] Zero regressions in Epics 5–7

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 0 (Architecture Prep)
  └── Phase 1 (Foundation) — BLOCKS ALL
        └── Phase 2 (Chart of Accounts)
              └── Phase 3 (Fiscal Calendar)
                    └── Phase 4 (PostingEngine & GL) ← CRITICAL GATE
                          ├── Phase 5 (Journal Entries)
                          ├── Phase 6 (Accounts Receivable) ────┐
                          ├── Phase 7 (Accounts Payable) ───────┼── Phase 10 (Payments)
                          ├── Phase 8 (Banking) ────────────────┘
                          └── Phase 9 (Cash Management)
Phase 4 complete
  └── Phase 11 (Tax Engine & Cost Centers) ← can run parallel with Phases 5–9
Phase 11 + Multi-Currency (Phase 12)
  └── Phase 13 (Financial Statements) ← needs GL, AR, AP, Tax, Currency
Phase 5–13 complete
  └── Phase 14 (Financial Controls & Audit)
  └── Phase 15 (KPI Dashboard)
Phase 1–15 complete
  └── Phase 16 (Integration & Contracts)
  └── Phase 17 (AI Readiness)
Phase 16 + Phase 17 complete
  └── Phase 18 (Testing, Validation & Documentation)
```

### User Story Dependencies

- **US1 (Foundation)**: No dependencies — starts first
- **US2 (COA)**: Depends on US1
- **US3 (Fiscal Calendar)**: Depends on US2
- **US4 (PostingEngine)**: Depends on US3 — BLOCKS US5–US13
- **US5–US9**: All depend on US4; can proceed in parallel after US4
- **US10 (Payments)**: Depends on US6 (AR) + US7 (AP) + US8 (Banking)
- **US11–US12 (Tax, Currency)**: Depend on US4; can proceed in parallel with US5–US9
- **US13 (Statements)**: Depends on US5–US12 all complete
- **US14 (Controls)**: Depends on US4–US13
- **US15 (KPIs)**: Depends on US13
- **US16 (Closure)**: Depends on all prior stories complete

### Within Each Phase

- [P] tasks can be worked on in parallel (different files)
- Domain model tasks before service tasks
- Service tasks before API endpoint tasks
- API endpoint tasks before frontend tasks
- All tasks before Docker verification

---

## Parallel Execution Examples

### Phase 4 (PostingEngine) — Critical parallel setup

```
Parallel: T089 (JournalEntry model) + T090 (JournalLine model) + T091 (JournalApproval model) + T092 (AuditLog model)
  ↓
Sequential: T093 (PostingEngine — depends on all models)
  ↓
Parallel: T094 (StateMachine) + T096 (JournalRepository) + T097 (GLReportRepository) + T098 (AuditLogService)
  ↓
Sequential: T099 (Event handlers — depends on PostingEngine)
  ↓
Parallel: T103 (frontend list) + T104 (frontend create) + T105 (frontend approval queue) + T106 (frontend GL report)
```

### Phase 6+7+8+9 (AR/AP/Banking/Cash) — Can run in parallel after Phase 4

```
After Phase 4 completes:
  Team A: Phase 6 (AR: T132–T155)
  Team B: Phase 7 (AP: T156–T174)
  Team C: Phase 8 (Banking: T175–T191)
  Team D: Phase 9 (Cash: T192–T203)
```

---

## Implementation Strategy

### MVP Scope (US1–US4: Foundation → PostingEngine)

1. Complete Phase 0: Architecture Preparation
2. Complete Phase 1: Foundation & Scaffolding
3. Complete Phase 2: Chart of Accounts
4. Complete Phase 3: Fiscal Calendar
5. Complete Phase 4: PostingEngine & GL ← **STOP AND VALIDATE**
   - Manual journal posting works end-to-end
   - Unbalanced journal rejected
   - Period lock enforced
   - Sales invoice event creates correct GL entry
   - Deploy/demo to financial stakeholders

### Full Delivery Sequence

1. MVP (US1–US4) → validated → demo
2. Add AR (US6) → validate Sales-to-Cash flow → demo
3. Add AP (US7) → validate Purchase-to-Pay flow → demo
4. Add Banking (US8) + Cash (US9) + Payments (US10) → validate full payment cycle → demo
5. Add Tax (US11) + Currency (US12) → validate tax and FX flows → demo
6. Add Financial Statements (US13) → CFO can view all reports → **major milestone demo**
7. Add Controls (US14) + KPIs (US15) + Closure (US16) → production ready

---

## Notes

- [P] tasks = different files; no dependencies on incomplete tasks in same phase
- [Story] label maps task to specific user story for traceability
- Each phase should be independently completable and testable before proceeding
- NEVER bypass PostingEngine — direct GL writes are not permitted
- NEVER use `float` for monetary amounts — always `Decimal`
- Always verify AR/AP control account reconciliation after every AR/AP integration test
- Commit after each logical task group
- Docker verify after every migration phase

**Total Task Count**: T001–T321 = **321 tasks**

| Phase | Story | Tasks | Complexity |
|-------|-------|-------|------------|
| Phase 0 | Architecture Prep | T001–T015 (15) | Low |
| Phase 1 | US1 Foundation | T016–T049 (34) | Medium |
| Phase 2 | US2 COA | T050–T067 (18) | Medium |
| Phase 3 | US3 Fiscal | T068–T088 (21) | Medium |
| Phase 4 | US4 PostingEngine | T089–T114 (26) | Very High |
| Phase 5 | US5 Journal Entries | T115–T131 (17) | Medium |
| Phase 6 | US6 AR | T132–T155 (24) | High |
| Phase 7 | US7 AP | T156–T174 (19) | Medium-High |
| Phase 8 | US8 Banking | T175–T191 (17) | High |
| Phase 9 | US9 Cash | T192–T203 (12) | Medium |
| Phase 10 | US10 Payments | T204–T223 (20) | High |
| Phase 11 | US11 Tax/Cost | T224–T246 (23) | Medium-High |
| Phase 12 | US12 FX | T247–T254 (8) | Medium |
| Phase 13 | US13 Statements | T255–T271 (17) | High |
| Phase 14 | US14 Controls | T272–T285 (14) | Medium |
| Phase 15 | US15 KPIs | T286–T293 (8) | Medium |
| Phase 16 | US16 Integration | T294–T302 (9) | Medium |
| Phase 17 | AI Readiness | T303–T309 (7) | Low |
| Phase 18 | Testing & Closure | T310–T321 (12) | Medium |
| **TOTAL** | | **321** | |
