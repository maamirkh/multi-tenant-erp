# Research: Epic 8 — Accounting & Finance

**Generated**: 2026-08-05
**Feature**: 008-accounting-finance
**Purpose**: Phase 0 architecture decisions — all NEEDS CLARIFICATION resolved before Phase 1

---

## Decision 1: General Ledger Storage Strategy — Append-Only Entry Model

**Decision**: The GL is implemented as an append-only table of journal entry lines. Every financial transaction (manual or automated) inserts rows; no row is ever updated or deleted. "Reversal" means inserting new rows with opposite sign. This guarantees ledger immutability without database-level triggers.

**Rationale**: Accounting immutability is a regulatory and auditing requirement. An append-only design makes it structurally impossible (not just policy-forbidden) to alter historical financial records. PostgreSQL's MVCC model is well-suited to high-concurrency inserts on an append-only table. Balance queries use SUM aggregation over the `gl_journal_lines` table — standard for all major accounting systems (QuickBooks, Sage, NetSuite all use this pattern).

**Alternatives Considered**:
- Soft-delete with immutable flag: Rejected — policy-enforced immutability can be bypassed at the DB level; structural immutability is stronger
- Event sourcing (separate event store): Rejected — overkill for a modular monolith; adds operational complexity without benefit at current scale
- Materialized balance table updated on every post: Rejected — creates a secondary consistency problem; balances must always be derived from GL lines

---

## Decision 2: Posting Engine as Internal Domain Service

**Decision**: A `PostingEngine` domain service is built within the Accounting module. All journal creation (manual journals, automated postings from Sales/Purchase/Inventory events) goes through this single service. The engine: validates balance, resolves accounts, applies posting rules, validates the open period, and creates the `JournalEntry` + `JournalLine` records atomically.

**Rationale**: A single posting gate ensures that every entry satisfies the same invariants (balanced, active accounts, open period, required cost center). If the Sales module raises an invoice, it calls the PostingEngine. If a manual journal is submitted, it goes through PostingEngine. This eliminates the risk of different code paths producing inconsistent GL entries. The pattern is used by all major ERP systems (SAP's FI posting document, Dynamics 365's ledger journal posting).

**Alternatives Considered**:
- Each module writes directly to GL: Rejected — multiplies invariant enforcement code; one bypass in any module breaks ledger integrity
- Async event-driven GL posting: Rejected — creates a window where the operational record exists but the GL entry does not; breaks real-time financial reporting
- External posting microservice: Rejected — premature extraction; the accounting module owns GL; no separate service needed at monolith scale

---

## Decision 3: AR/AP Subsidiary Ledger Design — Running Balance vs. Aggregation

**Decision**: AR and AP do NOT maintain a running balance column. Balances are always calculated by summing the open transaction amounts minus allocations from the `ar_allocations` / `ap_allocations` tables. A daily materialized summary view is maintained for reporting performance, refreshed on every posting.

**Rationale**: A running balance column creates a consistency problem: if balance updates are done in parallel, concurrent transactions can produce incorrect totals. Since PostgreSQL provides efficient aggregation over indexed tables, and customer ledger queries typically span a short period (current period or 30 days), aggregation is fast enough. The allocation table design (separate from transactions) is the industry-standard approach used by SAP and Dynamics 365: transactions remain immutable; allocations track matching.

**Alternatives Considered**:
- Running balance column with optimistic locking: Rejected — concurrent posting to the same customer account creates lock contention; also the column can diverge from reality
- Separate AR/AP balance table updated on every post: Rejected — two-table consistency problem; the balance table can drift from the transaction table
- Event-sourced balance reconstruction: Rejected — too slow for large customer histories; aggregation on indexed columns is sufficient

---

## Decision 4: Double-Entry Validation — Application Layer vs. Database Constraint

**Decision**: Double-entry balance validation is enforced at the application layer (within PostingEngine) before any INSERT occurs. A database-level CHECK constraint also validates that each `journal_entry` record has its `is_balanced` flag set to true, and a trigger fires on `gl_journal_lines` insert to verify the running balance equals zero at commit time. Both layers enforce the invariant.

**Rationale**: Application-layer validation provides human-readable error messages and supports complex validation logic (multi-currency, tax rounding). The database constraint provides a backstop in case of code bugs or direct DB access. This dual-layer approach mirrors the pattern from Epic 5 (stock quantity never goes negative: enforced at application layer AND via DB constraint). Financial integrity requires belt-and-suspenders.

**Alternatives Considered**:
- Application-layer only: Rejected — direct DB access (admin, migrations, bulk imports) could bypass
- Database trigger only: Rejected — triggers are hard to test, hard to debug, and produce non-user-friendly errors
- No enforcement (trust the code): Rejected — unacceptable for financial data

---

## Decision 5: Payment Allocation Strategy — Allocation Table Pattern

**Decision**: Payments and invoices are linked through a separate `ar_payment_allocations` table (and `ap_payment_allocations`). The allocation table records the relationship between a payment and the invoice(s) it settles, including the amount allocated. An allocation can be created, modified (re-allocation), or reversed (reversal creates a negative allocation row). Invoice balance = Invoice Amount − Sum(Allocations).

**Rationale**: Separating allocations from transactions is the standard accounting approach: it allows partial allocation, re-allocation, and reversal without modifying the original payment or invoice records. NetSuite, Dynamics 365, and QuickBooks all use this pattern. An allocation table also makes it straightforward to detect unapplied payments and generate aging accurately.

**Alternatives Considered**:
- Storing allocation state on the invoice (PAID_AMOUNT column): Rejected — makes re-allocation difficult; concurrent payments to the same invoice produce race conditions
- One-to-one payment-invoice linkage: Rejected — does not support partial payments applied to multiple invoices
- Journal-entry-based allocation (AR clearing account): Rejected — too complex for user-facing AR/AP management; the clearing account approach is used in full GL systems but not needed for subsidiary ledger management

---

## Decision 6: Bank Reconciliation — Statement-First Approach

**Decision**: Bank reconciliation uses a statement-first approach: the user imports (or manually enters) bank statement lines, which are stored in `bank_statement_lines`. The reconciliation engine matches statement lines to GL bank entries by amount, date, and reference. Matched pairs are recorded in `bank_reconciliation_matches`. Unmatched items remain as open items on both sides.

**Rationale**: The statement-first approach matches how accountants actually work — they receive a bank statement and reconcile it to their books. This approach is used by Xero, QuickBooks Online, and Dynamics 365 Business Central. Storing statement lines separately from GL entries allows the reconciliation to be done incrementally (partial reconciliation save) and supports audit trail for the reconciliation itself.

**Alternatives Considered**:
- GL-first (mark GL entries as reconciled): Rejected — the GL has many entries not on the bank statement (outstanding cheques, timing differences); GL-first makes it hard to see what's on the statement but not in the GL
- Automatic reconciliation only (no manual matching): Rejected — some transactions will always require manual matching (unusual references, partial amounts)

---

## Decision 7: Tax Engine Architecture — Pluggable Jurisdiction Adapters

**Decision**: The Tax Engine is designed with two layers: (1) a core `TaxCalculator` that applies a list of `TaxCode` records to a transaction amount, and (2) pluggable `JurisdictionAdapter` objects that determine which tax codes apply to a given transaction based on country, customer type, and product category. The initial implementation ships with a `GenericJurisdictionAdapter` that applies tax codes as explicitly configured, with no country-specific logic hardcoded.

**Rationale**: Country-specific tax rules change frequently (rate changes, new codes, special exemptions). By separating the calculation engine from jurisdiction logic, new jurisdictions can be added without modifying the core tax calculator. This is the architecture used by Vertex (tax compliance software) and Avalara. The generic adapter is sufficient for initial deployment; country-specific adapters are extension points.

**Alternatives Considered**:
- Hardcode VAT/GST rules: Rejected — rate changes require code deployments; breaks for jurisdictions with different rules
- Single configurable tax code table (current approach): This IS the current approach; the adapter pattern wraps it without breaking it, adding extensibility
- External tax API (Avalara/Vertex): Rejected — adds external dependency and cost; current scale does not require a dedicated tax engine

---

## Decision 8: Multi-Currency Exchange Gain/Loss — Transaction-Time Locking

**Decision**: When a foreign currency transaction is posted, the exchange rate is locked in the `gl_journal_lines` record at that moment. Realized gain/loss is calculated and posted automatically when a foreign currency invoice is settled: the PostingEngine calculates the difference between the booking rate and the settlement rate, and inserts a gain/loss journal entry atomically with the payment entry.

**Rationale**: Locking the rate at transaction time is the IFRS-compliant approach (IAS 21). Realized gain/loss must be recognized in the same period as settlement. Making the PostingEngine responsible for gain/loss calculation ensures it is always done correctly — developers building payment workflows do not need to implement gain/loss logic themselves.

**Alternatives Considered**:
- Store rate reference (look up at query time): Rejected — exchange rates can be updated retroactively; locking guarantees historical accuracy
- Deferred gain/loss (batch processing): Rejected — fails real-time P&L accuracy requirement; period-end batches introduce timing errors
- User-entered gain/loss: Rejected — error-prone; automatic calculation is both more accurate and required for efficiency

---

## Decision 9: Period Locking — Module-Level Enforcement Pattern

**Decision**: Period lock status is stored in `accounting_fiscal_periods` table with a `status` column (OPEN / LOCKED / CLOSED). The `PostingEngine` checks period status before every posting attempt. Additionally, an event `accounting.period.locked` is published via `InProcessEventBus` so consuming modules (Sales, Purchase, Inventory) can reject new postings to the locked period without requiring round-trips to the Accounting module.

**Rationale**: Period locks must be enforced across all modules in real-time. Caching the lock status in each module (via event) prevents Sales from creating invoices in a locked accounting period. This mirrors the design from Epic 6's event-driven pattern. The `InProcessEventBus` is sufficient for the monolith; if the system migrates to microservices, the same events become the message bus contract.

**Alternatives Considered**:
- Central API call from each module to check period status: Rejected — creates tight coupling and latency; a rejected invoice posting at the API level frustrates users
- Database-level lock enforcement via trigger: Rejected — triggers don't provide context about which module triggered the violation; hard to diagnose
- No module-level awareness (only enforce in Accounting module): Rejected — Sales and Purchase can still create documents in locked periods if they don't integrate the check

---

## Decision 10: Financial Statement Generation — Real-Time Aggregation vs. Pre-Computed

**Decision**: Financial statements (Balance Sheet, P&L, Cash Flow) are generated in real-time via SQL aggregation queries over the `gl_journal_lines` table. No pre-computed financial statement tables are maintained. A read-optimized database view with appropriate indexes is used to achieve the 15-second performance target.

**Rationale**: Pre-computed statements require invalidation logic when any GL entry is posted. At the volumes specified (500K GL entries per company per year), PostgreSQL can aggregate the P&L in under 5 seconds using a covering index on `(company_id, account_id, posting_date, debit_amount, credit_amount)`. Real-time generation ensures the CFO always sees the current state without cache staleness. This is the approach used by Xero and Sage Accounting.

**Alternatives Considered**:
- Materialized views refreshed on each post: Rejected — refresh under heavy posting load creates locking; the refresh is synchronous; performance degrades
- Daily batch generation: Rejected — fails real-time accuracy requirement; CFO needs current P&L at any time
- Pre-computed period summaries: Accepted as optimization for current + prior period (period summary table); future-period ranges always use real-time aggregation

---

## Decision 11: Audit Trail — Synchronous Write within Transaction

**Decision**: All accounting audit entries are written synchronously within the same database transaction as the event they record. There is no async audit queue. An audit entry either commits with the action or the entire action rolls back.

**Rationale**: Async audit creates a window where an action is committed but the audit entry is not yet written — this is unacceptable for financial records. The synchronous pattern is used consistently in Epics 5, 6, and 7. The additional overhead of one extra INSERT per financial action is negligible compared to the correctness guarantee.

**Alternatives Considered**:
- Async audit via event queue: Rejected — unacceptable audit gap; regulatory compliance requires real-time audit
- Separate audit database: Rejected — cross-database transactions are complex; PostgreSQL WAL provides sufficient durability for single-DB audit
- Application-level audit log (file-based): Rejected — not queryable; not transactional; insufficient for financial audit compliance

---

## Decision 12: COA Account Code Uniqueness — Company-Scoped

**Decision**: Account codes are unique per company, enforced by a unique index on `(tenant_id, company_id, account_code)`. Parent-child relationships in the COA hierarchy are managed by a `parent_account_id` self-referencing foreign key. The COA tree depth is not artificially limited (practical limit is ~5 levels).

**Rationale**: Each company has its own COA independently of other companies. Account code `1000` in Company A and `1000` in Company B are completely separate records. This is the standard multi-company accounting approach. The `parent_account_id` self-reference enables arbitrary hierarchy without a separate COA tree table.

**Alternatives Considered**:
- Global account codes across companies: Rejected — restricts companies to a shared taxonomy; violates industry-neutral design
- Fixed hierarchy depth (3 levels): Rejected — some COA structures (manufacturing, government) require deeper hierarchies
- Separate COA tree table: Rejected — adds complexity without benefit; self-referencing FK is standard for tree structures

---

## Decision 13: Recurring Journal Entries — Template + Instance Pattern

**Decision**: Recurring journal entries use a `recurring_journal_template` + `recurring_journal_instance` design. The template holds the schedule, accounts, and amounts. Each execution creates a new `JournalEntry` (an instance) via the PostingEngine and records the instance in `recurring_journal_instances` for audit and history. A background scheduler (APScheduler integrated into the FastAPI startup) triggers due recurring entries.

**Rationale**: Separating template from instance is the standard pattern (Dynamics 365 calls these "Periodic Journals"). The APScheduler approach is consistent with the monolith architecture — no additional message broker needed. Instances are standard journal entries; all posting rules apply.

**Alternatives Considered**:
- Celery for recurring job execution: Rejected — adds Redis dependency; APScheduler is sufficient for the job volume
- Manual trigger (no auto-execution): Rejected — spec requires automatic execution on schedule
- Cron job external to the application: Rejected — adds operational complexity; APScheduler runs in-process

---

## Decision 14: Cost Center Accounting — Optional Assignment per Account

**Decision**: Cost centers are optional on GL journal lines. Whether a cost center is required for a given account is controlled by the `requires_cost_center` flag on the `chart_of_accounts` record. The PostingEngine validates cost center assignment based on this flag. Cost center data is stored on `gl_journal_lines.cost_center_id` — denormalized for query performance.

**Rationale**: Some accounts (bank, AR, AP, tax) never need cost center assignment. Others (operating expenses) always do. Making it account-configurable balances completeness with user convenience. Storing cost_center_id directly on the journal line (not in a separate allocation table) is the most query-efficient approach for cost center P&L reports.

**Alternatives Considered**:
- Mandatory cost center on all postings: Rejected — bank, AR, AP postings do not logically belong to a cost center; would pollute cost center reports
- Separate cost center allocation table (split-coding): Deferred — useful for allocating one expense line to multiple cost centers proportionally; this is a future enhancement, not required in initial implementation
- Cost center as a separate GL dimension: Accepted as the correct design; stored as a column on journal lines

---

## Decision 15: Frontend State Management for Financial Screens

**Decision**: Financial screens use React Server Components (RSC) for data-heavy read views (GL report, trial balance, financial statements). Interactive screens (journal entry creation, payment processing, bank reconciliation) use Client Components with React Query for optimistic updates and cache management.

**Rationale**: Financial statements and GL reports are read-heavy with no real-time interactivity — RSC provides the best performance (no client-side JS for the initial render). Interactive workflows (payment allocation, bank reconciliation matching) require client-side state management — React Query with mutation hooks provides optimistic UI updates. This is consistent with the Next.js 15 App Router patterns established in Epics 5–7.

**Alternatives Considered**:
- Full client-side rendering for all screens: Rejected — degrades initial load time for large financial reports
- Full server-side rendering (no Client Components): Rejected — interactive workflows (reconciliation matching, journal line entry) require real-time UI state
- Redux for global financial state: Rejected — React Query is sufficient; Redux adds complexity without benefit for financial screens

---

*Phase 0 complete. All architecture decisions resolved. Phase 1 implementation approved to proceed.*
