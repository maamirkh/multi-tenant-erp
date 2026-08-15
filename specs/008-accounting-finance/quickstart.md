# Developer Quickstart: Epic 8 — Accounting & Finance

**Branch**: `008-accounting-finance`
**Date**: 2026-08-05 (Phase 0) — **updated 2026-08-14 (Phase 18, epic closure, T319)**

**Epic status: COMPLETE.** All 18 phases shipped; migrations 001–050 (accounting: 034–050, 17 migrations); see "Final State (Epic Closure)" below for the authoritative confirmed state — it supersedes any phase-count/migration-count references elsewhere in this document that predate it.

---

## Prerequisites

Ensure the following are complete and running before beginning Epic 8 implementation:

- Epics 1–7 merged to main and stable
- Docker Compose running (`docker compose up -d`)
- PostgreSQL 16 accessible at `localhost:5432`
- All prior migrations applied: `alembic upgrade head` (migrations 001–033 must pass)
- Python 3.12+ virtual environment active
- Node.js 20+ installed (for frontend)

---

## Module Location

```
backend/modules/accounting/         ← New module (created in Phase 1)
```

Follows the exact same structure as:
- `backend/modules/inventory/`
- `backend/modules/purchase/`
- `backend/modules/sales/`

---

## Key Architectural Decisions (Read Research.md First)

Before writing any code, read `research.md`. The 15 decisions documented there govern every implementation choice. The most critical:

1. **PostingEngine is the ONLY path to GL** — never write to `accounting_journal_lines` directly
2. **GL entries are append-only** — no UPDATE or DELETE on `accounting_journal_lines` ever
3. **Balance validation is dual-layer** — application (PostingEngine) + database (constraint/trigger)
4. **All event handlers call PostingEngine** — Sales/Purchase/Inventory events trigger posting via the engine
5. **Period lock = immediate enforcement** — PostingEngine checks period status on every posting

---

## Phase Delivery Order

Implement phases in dependency order:

```
Phase 1:  Foundation & Scaffolding (currencies, config, sequences, feature flags)
Phase 2:  Chart of Accounts (account hierarchy, COA templates)
Phase 3:  Fiscal Calendar (fiscal years, periods, opening balances)
Phase 4:  General Ledger & Journal Entries (PostingEngine core)
Phase 5:  Accounts Receivable (customer ledger, aging, credit management)
Phase 6:  Accounts Payable (supplier ledger, aging, reconciliation)
Phase 7:  Banking (bank accounts, bank reconciliation, cheques)
Phase 8:  Cash Management (cash accounts, petty cash)
Phase 9:  Payments (customer receipts, supplier payments, allocation)
Phase 10: Tax Engine & Cost Centers (tax codes, groups, cost centers, projects)
Phase 11: Financial Reporting (all financial statements and reports)
Phase 12: Integration Contracts, Performance & Epic Closure
```

---

## Environment Setup

```bash
# Start Docker services
docker compose up -d

# Apply migrations (run after each migration phase)
cd backend
alembic upgrade head

# Run accounting-specific tests
pytest backend/tests/unit/modules/accounting/ -v
pytest backend/tests/integration/repositories/accounting/ -v
pytest backend/tests/integration/api/v1/accounting/ -v

# Run all tests (ensure no regression)
pytest backend/tests/ -v --tb=short

# Frontend dev server
cd frontend
npm run dev
```

---

## Module Registration

Register the accounting router in `backend/api/v1/router.py`:

```
# Pattern (same as sales module):
router.include_router(
    accounting_router,
    prefix="/companies/{company_id}/accounting",
    tags=["accounting"]
)
```

All accounting endpoints are nested under:
```
/api/v1/companies/{company_id}/accounting/
```

---

## Feature Flags

The accounting module registers its feature flags in the `company_feature_flags` table during Phase 1. Default values are set at module initialization.

| Flag | Default | Description |
|------|---------|-------------|
| `accounting.multicurrency.enabled` | false | Enable multi-currency operations |
| `accounting.costcenters.enabled` | false | Enable cost center accounting |
| `accounting.approvalworkflow.enabled` | false | Enable journal/payment approval workflows |
| `accounting.taxwithholding.enabled` | false | Enable WHT calculations |
| `accounting.ai.enabled` | false | Enable AI financial assistant (future) |
| `accounting.bankreconciliation.enabled` | true | Enable bank reconciliation module |
| `accounting.recurringjournals.enabled` | true | Enable recurring journal entries |
| `accounting.bulkimport.enabled` | true | Enable bulk COA import |

---

## PostingEngine Usage Contract

**Every GL posting must go through PostingEngine. No exceptions.**

The PostingEngine contract:

```
Input:
  - journal_type: JournalType enum
  - source: PostingSource enum
  - posting_date: date
  - fiscal_period_id: UUID (resolved from posting_date by the engine)
  - description: str
  - reference: str
  - source_document_type: str | None
  - source_document_id: UUID | None
  - currency_code: str (base currency for simple entries)
  - lines: list[PostingLineRequest]
    - account_id: UUID
    - debit_amount: Decimal (0 if credit)
    - credit_amount: Decimal (0 if debit)
    - currency_code: str
    - exchange_rate: Decimal (1.0 for base currency)
    - cost_center_id: UUID | None
    - department_id: UUID | None
    - project_id: UUID | None
    - description: str | None

Output:
  - PostingResult(journal_entry_id, journal_number, posted_at)

Raises:
  - PostingValidationError (unbalanced, inactive account, locked period, missing cost center, unapproved)
```

---

## Testing Strategy for Accounting

### Unit Tests (test isolation from DB)

Test domain invariants and domain service logic:
- PostingEngine: balanced entry passes; unbalanced entry raises PostingValidationError
- PostingEngine: inactive account raises error
- PostingEngine: locked period raises error
- AllocationEngine: over-allocation raises error
- TaxCalculator: correct rate for transaction date
- AgingCalculator: correct bucket assignment
- JournalEntry state machine: invalid transitions raise error

### Integration Tests (real DB, test tenant)

Test repositories and application services with real SQLAlchemy session:
- COA CRUD and hierarchy traversal
- FiscalPeriod lock enforcement
- Journal posting and GL balance aggregation
- AR/AP allocation accuracy
- Bank reconciliation matching
- Currency revaluation journal posting

### API Tests (FastAPI TestClient)

Test endpoints with real tenant/company context:
- Journal entry create/submit/approve/post/reverse lifecycle
- Customer payment processing with allocation
- Bank reconciliation session lifecycle
- Financial statement endpoints return correct totals

### Security Tests

- Cross-tenant isolation: company A cannot access company B GL
- RBAC: Accountant cannot approve journals; Controller cannot override CFO-only actions
- Period lock enforcement: posting to locked period returns 422
- Immutability: PUT/DELETE on journal_lines returns 405

### Performance Tests

- Trial balance generation for 500K GL entries < 10 seconds
- Customer aging for 10K customers < 5 seconds
- GL search with date range filter < 5 seconds
- Journal posting throughput: 100 concurrent postings complete without deadlock

---

## Critical Invariants to Test First

Before any other tests, verify these invariants never break:

1. **Double-entry balance**: Post a manual journal; verify `SUM(debit) == SUM(credit)` in `accounting_journal_lines`
2. **AR control reconciliation**: Post a sales invoice; verify AR control account GL balance == sum of all customer ledger open balances
3. **AP control reconciliation**: Post a purchase bill; verify AP control account GL balance == sum of all supplier ledger open balances
4. **Period lock propagation**: Lock a period; verify PostingEngine rejects any new journal with that period date
5. **Immutability**: Attempt UPDATE on `accounting_journal_lines`; verify DB constraint rejects it

---

## Integration Event Testing

Test the full Sales-to-Cash workflow end-to-end in integration tests:

1. Publish `sales.invoice.posted` event → verify GL entry created (DR AR / CR Revenue)
2. Post customer payment via PaymentService → verify GL entry (DR Bank / CR AR)
3. Verify customer ledger balance = 0 (fully allocated)
4. Verify AR control account GL balance matches customer ledger sum

---

## Frontend Screens (Phase Order)

| Phase | Screens |
|-------|---------|
| Phase 1 | Accounting Configuration, Currency Management |
| Phase 2 | Chart of Accounts (tree view + CRUD) |
| Phase 3 | Fiscal Year & Period management |
| Phase 4 | Journal Entry list, create/edit, approval queue, GL report |
| Phase 5 | Customer Ledger, AR Aging, Customer Statement, Credit Management |
| Phase 6 | Supplier Ledger, AP Aging, Supplier Statement |
| Phase 7 | Bank Accounts, Bank Reconciliation workspace |
| Phase 8 | Cash Accounts, Petty Cash management |
| Phase 9 | Customer Payments, Supplier Payments, Payment Allocation |
| Phase 10 | Tax Codes, Tax Groups, Cost Centers, Projects |
| Phase 11 | Trial Balance, Balance Sheet, P&L, Cash Flow, KPI Dashboard |
| Phase 12 | Integration verification, export/import screens |

---

## Common Pitfalls to Avoid

1. **Never bypass PostingEngine** — even for "simple" entries; all validation and audit must run
2. **Never use `float` for monetary amounts** — always use `Decimal` (Python) / `numeric(20,6)` (DB)
3. **Never assume base currency** — every amount must carry its currency code
4. **Always include `company_id` in every repository query** — same rule as Epics 5–7
5. **Never delete or update posted journal lines** — use reversal pattern
6. **Always test period lock enforcement** after implementing any posting path
7. **Recurring journals run in a background scheduler** — do not run them synchronously in API requests
8. **AR/AP control account reconciliation must be verified** after every posting test — do not defer this check

---

## Phase 0 Verification Findings (confirmed 2026-08-05)

The following was confirmed by direct inspection of `backend/modules/{inventory,purchase,sales}/` during Phase 0 (T006–T011, T014). Where it corrects an assumption in `spec.md` / `data-model.md` / `research.md` / `contracts/events.md`, the correction is called out explicitly — those documents are not edited here.

### Confirmed import paths and shared infrastructure (T006)

- **`BaseRepository`**: `core.repositories.base.BaseRepository` (generic, lives in shared `backend/core/`, not module-specific). Accounting repositories subclass this directly, same as Epics 5–7.
- **EventBus**: there is no single shared bus. Each module defines its own `<Module>DomainEvent` base dataclass + `EventBus` ABC + `InProcessEventBus` singleton in its own `events` package (`modules/inventory/events.py`; `modules/purchase/events/__init__.py`; `modules/sales/events/__init__.py`) — each is an independent instance. Accounting must add an equivalent `AccountingDomainEvent` + `InProcessEventBus` in `backend/modules/accounting/events/__init__.py` per T026. **Open item**: how Accounting's handlers subscribe to Sales/Purchase/Inventory's *separate* bus instances (e.g. `modules.sales.events.get_event_bus().subscribe(...)`) is not yet decided — needed before Phase 4 handler wiring (T099).
- **`FeatureFlagService`**: module-specific, not shared. Inventory's is `modules.inventory.services.feature_flag_service.FeatureFlagService`, backed by its own `inventory_feature_flags` table and `InventoryFeatureFlag(TenantBaseModel)` model — confirmed by `modules/purchase/models/feature_flag.py` and `modules/sales/models/feature_flag.py` following the identical per-module pattern. **Correction**: plan.md/data-model.md describe a shared `company_feature_flags` table — no such table exists. Accounting must create its own `accounting_feature_flags` table + `AccountingFeatureFlag` model + `AccountingFeatureFlagService`, consistent with the established per-module convention.
- **DB session**: actual pattern is synchronous SQLAlchemy `Session` (`core.database.session.SessionLocal`, `sqlalchemy.orm.Session`) throughout Epics 1–7. **Correction**: plan.md's Technical Context lists "SQLAlchemy 2.x (async)" — the existing codebase is sync. Accounting should follow the established sync pattern for consistency (Constitution §7) unless directed otherwise.
- **No `tenant_id` column exists anywhere** — only `company_id` (`TenantBaseModel`). References to `tenant_id` alongside `company_id` in contracts/events.md's event envelope and elsewhere in the Epic 8 docs don't correspond to an actual field; Accounting models/events should use `company_id` only.

### Confirmed router mount point (T014)

No conflict. `backend/api/v1/router.py` already registers `/companies/{company_id}/purchase` (Epic 6) and `/companies/{company_id}/sales` (Epic 7) with the same nesting pattern; `/companies/{company_id}/accounting` is free.

### CRITICAL — actual integration event contract differs from `contracts/events.md` (T007, T008, T010)

`contracts/events.md` §"Events Consumed by Accounting (Inbound)" and `data-model.md` §7.2 do not match Epic 5/6/7's actual published events:

| Documented inbound event | Actual state |
|---|---|
| `sales.invoice.posted` | Actual: `sales.invoice.issued` (class `InvoiceIssued`, `modules/sales/events/invoice_events.py`). Payload is `invoice_id, invoice_number, customer_id, due_date, total_amount, currency_code, issued_by` — **no line-level breakdown, no tax split, no `ar_account_id`/`revenue_account_id`/`tax_liability_account_id`**. |
| `sales.creditnote.posted` | Actual: `sales.invoice.credit_note_issued` (class `InvoiceCreditNoteIssued`). Name differs. |
| `sales.payment.received` | **Does not exist.** Sales spec 007 §6 "Out of Scope" explicitly lists "Accounts Receivable" and "Payment Collection & Receipts" as deferred to "Epic 8+" — Sales never built this. This is actually one of *Accounting's own* Phase 9 outbound events, not an inbound one. |
| `purchase.bill.posted` | **Does not exist — Purchase has no Bill/Invoice/AP entity at all.** Purchase spec 006 §60.2 lists "Invoice Processing", "Three-Way Matching", and "Accounts Payable" as **Epic 8's own future scope**, not already-built Epic 6 capability. Purchase's real events are PO/GR/RMA/cost-based (`purchase.po.*`, `purchase.gr.*`, `purchase.cost.recorded`, `purchase.rma.*`) — none represent a posted supplier bill. |
| `purchase.creditnote.posted` | **Does not exist**, same reason. |
| `purchase.payment.made` | **Does not exist**, same reason as `sales.payment.received` — this is Accounting's own outbound event. |
| `inventory.adjustment.posted` | Closest actual events (PascalCase, `modules/inventory/domain_events.py`): `InventoryAdjustmentSubmitted`, `InventoryAdjustmentApproved`, `StockAdjusted`. No dotted `inventory.*` naming convention exists in Inventory at all, and none carry GL account fields. |
| `inventory.cost.updated` | **Does not exist** — Inventory has no cost/valuation event. |

**Root cause**: Sales and Purchase (Epics 6–7) were built before the Chart of Accounts existed and have zero awareness of GL accounts by design. The documented contract assumed the opposite — that upstream modules already resolve and embed GL account IDs in their event payloads — which is backwards for a system where Accounting is the first module to introduce COA.

**Consequence (not implemented in Phase 0 — informational for Phase 4–6)**: `IntegrationEventHandlerService` handlers must subscribe to the *real* event names/payloads above and independently resolve which GL account to post to. **Resolved in [ADR-0004](../../history/adr/0004-gl-account-resolution-for-sales-purchase-inventory-integration-events.md)**: single default control accounts on `AccountingConfiguration` (extends T027 with `default_revenue_account_id`, `default_expense_account_id`, `default_tax_liability_account_id`, `default_input_tax_account_id`); Sales invoice detail fetched via a new public `SalesInvoiceReadService` method (not embedded in the event); Accounts Payable bill capture built inside Accounting itself in Phase 6 (Purchase never built a Bill/AP concept — spec 006 §60.2); Inventory GL-value sufficiency left as an open Phase 4 implementation item.

### Confirmed outbound event envelope (T009)

Accounting's 17 outbound events (`accounting.*`, listed in `contracts/events.md` §"Events Published by Accounting") are new — nothing in the codebase to reconcile against yet. However, the envelope shape shown in `contracts/events.md` (`event_id, event_type, event_version, tenant_id, company_id, occurred_at, raised_by_user_id, payload{}`) does not match the actual base-dataclass pattern used by Inventory/Purchase/Sales — flat fields (`event_type, aggregate_type, aggregate_id, company_id, occurred_at, event_id, actor_id, correlation_id`), no nested `payload`, no `tenant_id`. Per tasks.md T026, `AccountingDomainEvent` should mirror `SalesDomainEvent`'s actual shape (flat dataclass + `to_dict()`) for consistency with Epics 5–7, not the abstract envelope described in contracts/events.md.

### Confirmed feature flag registry (T011)

The 8 flags and defaults documented above (§Feature Flags) are unchanged and correct. Storage: a dedicated `accounting_feature_flags` table + `AccountingFeatureFlag(TenantBaseModel)` model + `AccountingFeatureFlagService`, following Inventory/Purchase/Sales's per-module convention (see T006 correction above) — not a shared `company_feature_flags` table.

### Docker / test environment (T012, T013)

- Docker Compose was found in a broken state this session (Docker Desktop container-index corruption unrelated to Epic 8; plus a non-compose orphan `erp-db-standalone` container). Left untouched per explicit direction — not verified this session. Re-run `docker compose up -d && alembic upgrade head` locally once Docker Desktop is restarted, before Phase 1 begins.
- The backend test suite was instead verified locally via `poetry run pytest tests/` against the suite's existing in-memory SQLite fixtures (no Docker required for this). See session record for the pass/fail result.

---

## Final State (Epic Closure — Phase 18, T319)

Confirmed by direct inspection at epic closure, 2026-08-14. Supersedes any earlier phase-count or migration-count reference in this document (those sections are left as historical record of Phase 0's original plan, not edited in place).

### Actual phase count and names (tasks.md is authoritative — 18 phases, not 12)

The "Phase Delivery Order" section above reflects plan.md's original 12-phase estimate. The approved `tasks.md` that was actually executed split this into 18 phases:

```
Phase 0:  Architecture Preparation
Phase 1:  Module Foundation & Scaffolding (US1)
Phase 2:  Chart of Accounts (US2)
Phase 3:  Fiscal Calendar (US3)
Phase 4:  PostingEngine & General Ledger — CRITICAL (US4)
Phase 5:  Journal Entries — Manual, Recurring & Reversal (US5)
Phase 6:  Accounts Receivable (US6)
Phase 7:  Accounts Payable (US7)
Phase 8:  Banking (US8)
Phase 9:  Cash Management (US9)
Phase 10: Payment Processing & Allocation (US10)
Phase 11: Tax Engine & Cost Centers (US11, US12)
Phase 12: Multi-Currency & Exchange Rates (US12)
Phase 13: Financial Statements & Reports (US13)
Phase 14: Financial Controls & Audit Trail (US14)
Phase 15: Financial Intelligence & KPI Dashboard (US15)
Phase 16: Integration Readiness & Contracts (US16)
Phase 17: AI ERP Readiness (US16)
Phase 18: Testing, Validation & Documentation (US16)
```

### Actual migration numbers

Accounting owns migrations **034 through 050** (17 migrations total), chained onto Epics 1–7's 001–033:

| Migration | Phase | Adds |
|---|---|---|
| 034 | 1 | `accounting_configurations`, `accounting_sequences`, `accounting_feature_flags` |
| 035 | 1 | `accounting_currencies` (12 seeded ISO 4217 currencies), `accounting_exchange_rates` |
| 036 | 2 | `accounting_account_groups`, `accounting_accounts` |
| 037 | 3 | `accounting_fiscal_years`, `accounting_fiscal_periods`, `accounting_opening_balances` |
| 038 | 4 | `accounting_journal_entries`, `accounting_journal_lines` (+ immutability trigger), `accounting_journal_approvals`, `accounting_audit_log` |
| 039 | 5 | `accounting_recurring_journal_templates` (+ lines), `accounting_recurring_journal_instances` |
| 040 | 6 | `accounting_customer_ledgers`, `accounting_ar_transactions`, `accounting_ar_payment_allocations`, `accounting_customer_credit_history` |
| 041 | 7 | `accounting_supplier_ledgers`, `accounting_ap_transactions`, `accounting_ap_payment_allocations`, `accounting_supplier_statement_reconciliations` (+ items) |
| 042 | 8 | `accounting_bank_accounts`, `accounting_bank_transactions`, `accounting_bank_statement_lines`, `accounting_bank_reconciliations` (+ matches), `accounting_cheques` |
| 043 | 9 | `accounting_cash_accounts`, `accounting_cash_transactions`, `accounting_petty_cash_vouchers`, `accounting_cash_reconciliations` |
| 044 | 10 | `accounting_payments`, `accounting_payment_allocation_lines`, `accounting_payment_refunds` |
| 045 | 11 | `accounting_tax_codes`, `accounting_tax_rates`, `accounting_tax_groups` (+ lines) |
| 046 | 11 | `accounting_cost_centers`, `accounting_departments`, `accounting_projects` |
| 047 | 12 | `accounting_currency_revaluations` |
| 048 | 13 | GL report performance indexes (account_id, company+posting_date on journal_lines/entries) — **fixed at Phase 18/T315**: originally also re-created an index migration 038 already defines; the duplicate was only caught running the full 001→050 chain against a genuinely empty database (`alembic upgrade head` from scratch), not against the incrementally-migrated dev database, since Alembic only replays the delta from the current revision forward |
| 049 | 14 | 20 `accounting.*` RBAC permissions + role mappings; payment approval-workflow columns; audit-log indexes — **fixed at Phase 18/T315**: `downgrade()` had a stray `drop_index` for an index `upgrade()` never creates (a leftover from a design decision documented inline in the migration); removed |
| 050 | 17 | `accounting_anomaly_flags` (AI readiness stub) |

Both Phase 18 migration fixes were verified with a full bi-directional cycle (`alembic upgrade head` from empty → `alembic downgrade base` → `alembic upgrade head` again) against an isolated, throwaway PostgreSQL 16 container — not against the shared persistent dev database, to avoid destructive `docker compose down -v` against real accumulated dev data.

### APScheduler configuration (confirmed, `modules/accounting/services/scheduler.py`)

- In-process `BackgroundScheduler` (APScheduler), no Redis/Celery — matches `InProcessEventBus`'s in-process-only convention (research.md Decision 13).
- 3 daily cron jobs, all at **01:00** server time by default (`start_scheduler(hour=1, minute=0)`):
  - `recurring_journal_job` → `RecurringJournalService.execute_due_templates()` (Phase 5)
  - `ar_ap_overdue_check_job` → `AccountsReceivableService.run_overdue_check()` (Phase 6; AP half is a documented no-op — no AP "overdue" job was ever specced, only the due-*soon* reminder below)
  - `ap_bill_due_reminder_job` → `AccountsPayableService.run_bill_due_reminder_check()` (Phase 7)
- Gated off entirely when `settings.ENVIRONMENT == "testing"` (`main.py` lifespan) — the flagged risk plan.md called out ("APScheduler conflicts with test isolation") never materialized because of this gate; confirmed still correct at epic closure.
- Each job opens its own `SessionLocal()` session (outside any request's DI scope, mirroring `handlers/integration_handlers.py`'s pattern) and always closes it, even on failure; a single template/transaction's failure never stops the others.

### Confirmed deviations from the original plan (cumulative, all phases)

All deviations already called out under "Phase 0 Verification Findings" below held for the entire epic — none were later reversed. Additional deviations discovered in later phases, confirmed still accurate at closure:

- **Feature flags**: stored in `accounting_feature_flags` (per-module table), never the `company_feature_flags` table this document's own "Feature Flags" section header text above still references — that header line predates the Phase 0 correction and was intentionally left as-is (historical record) rather than silently rewritten.
- **AP bill capture**: Purchase never gained a Bill/AP concept — confirmed through to epic closure. Accounting's own `POST /ap/bills` / `POST /ap/credit-notes` (Phase 7) remain the only entry point; `handle_purchase_bill_posted`/`handle_purchase_credit_note_posted` remain permanently-unsubscribed stubs (see `modules/accounting/handlers/integration_handlers.py`'s module docstring for the full accounting of all 8 originally-speced inbound handlers' real status).
- **Inventory GL integration**: still an open item (ADR-0004) at epic closure — `handle_inventory_adjustment_posted` remains an unsubscribed stub; Phase 16's `test_e2e_inventory_gl.py` documents this as a deliberate tripwire test, not a silent gap.
- **`accounting.journal.posted` event payload**: verified at Phase 17 (T303) against 6 ML-readiness fields — `reference` is not included in the actual event payload (though it IS on the `JournalEntry` model and the Phase 17 GL event-stream read-model); `account_type` cannot be added without a payload shape change (it's a per-line, not per-entry, attribute). See `contracts/events.md`'s `accounting.journal.posted` section for the full verification table.
- **Bank statement import / bulk COA import**: both accept pre-parsed JSON rows, not raw CSV file upload — the client (frontend or test) parses CSV before POSTing. Confirmed consistent across Phase 2 (COA) and Phase 8 (bank statements).

---

## References

- Business Specification: `specs/008-accounting-finance/spec.md`
- Research Decisions: `specs/008-accounting-finance/research.md`
- Data Model: `specs/008-accounting-finance/data-model.md`
- Domain Events: `specs/008-accounting-finance/contracts/events.md`
- OpenAPI Contract: `specs/008-accounting-finance/contracts/accounting-v1.yaml` (Phase 16, T294)
- Acceptance Criteria Verification: `specs/008-accounting-finance/checklists/acceptance-criteria.md` (Phase 18, T317)
- Engineering Constitution: `.specify/memory/constitution.md`
- Prior Epic Pattern: `backend/modules/sales/` (Epic 7)
- Prior Epic Pattern: `backend/modules/purchase/` (Epic 6)
