# Developer Quickstart: Epic 8 — Accounting & Finance

**Branch**: `008-accounting-finance`
**Date**: 2026-08-05

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

## References

- Business Specification: `specs/008-accounting-finance/spec.md`
- Research Decisions: `specs/008-accounting-finance/research.md`
- Data Model: `specs/008-accounting-finance/data-model.md`
- Domain Events: `specs/008-accounting-finance/contracts/events.md`
- Engineering Constitution: `.specify/memory/constitution.md`
- Prior Epic Pattern: `backend/modules/sales/` (Epic 7)
- Prior Epic Pattern: `backend/modules/purchase/` (Epic 6)
