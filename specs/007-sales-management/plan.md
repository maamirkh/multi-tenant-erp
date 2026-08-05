# Implementation Plan: Epic 7 – Sales Management

**Branch**: `007-sales-management` | **Date**: 2026-07-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-sales-management/spec.md` (v1.0)
**Research**: [research.md](./research.md) | **Data Model**: [data-model.md](./data-model.md)

---

## Summary

Epic 7 implements the **complete Order-to-Cash (O2C) Domain** — the end-to-end capability by which organisations manage customers, create quotations, process sales orders, fulfil deliveries through inventory integration, generate invoices, handle returns, and govern pricing under full audit accountability and multi-tenant isolation.

The implementation strategy is **vertical slice delivery** across 11 sequential phases, progressing from module scaffolding through customer master, pricing engine, quotations, sales orders with approval, delivery with inventory integration, invoicing, returns, sales intelligence, integration contracts, and epic closure. Every phase is independently testable. No phase begins until the previous phase passes its exit criteria.

The architecture mirrors Epics 5 (Inventory) and 6 (Purchase): Clean Architecture with strict layer separation, Repository Pattern with mandatory `company_id` isolation, domain events via `InProcessEventBus`, and feature flags for all optional capabilities. The critical integration contracts are: (1) **Delivery Note dispatch → Epic 5 stock deduction**, (2) **Sales Return receipt → Epic 5 stock restock**, and (3) **Sales dispatch low stock → Epic 6 purchase reorder suggestion**. All cross-module stock writes are transactional (Unit of Work).

The pricing engine is the most architecturally significant new component: a 7-level price resolution hierarchy that determines the correct price for any product-customer combination. The approval engine follows the proven pattern from Epic 6, built as an internal sub-system within the sales module.

---

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI 0.115+, Pydantic v2, SQLAlchemy 2.x (async), Alembic, Next.js 15 (App Router), TailwindCSS, shadcn/ui
**Storage**: PostgreSQL 16 LTS (Docker Compose in dev; Neon PostgreSQL in production)
**Testing**: pytest + pytest-asyncio (backend), Jest + React Testing Library (frontend)
**Target Platform**: Linux server (Docker), browser (Next.js SSR + CSR)
**Project Type**: Web application — FastAPI backend + Next.js frontend
**Performance Goals**: Customer search p95 < 300ms; SO list p95 < 500ms; DN confirmation < 2s; invoice generation < 2s; price resolution p95 < 100ms; report generation < 5s; all standard reads p95 < 200ms
**Constraints**: company_id isolation on every query; soft-delete everywhere; issued invoices immutable; dispatched DNs immutable; audit trail on every write; gap-free invoice sequencing; self-approval prevention; price-at-point-of-sale immutability
**Scale/Scope**: 100,000 customers per tenant; 500,000 orders/year per tenant; 500,000 invoices/year; 200 concurrent users per tenant; 1,000 concurrent tenants

---

## Constitution Check

*GATE: Must pass before Phase 1 implementation. Re-checked after design phase.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Clean Architecture layering | PASS | Domain / Application / Infrastructure / API — zero cross-layer dependency violations |
| Multi-tenancy (company_id everywhere) | PASS | Repository base class enforces company_id on every query, consistent with Epics 2–6 |
| Soft delete on all entities | PASS | is_deleted + deleted_at + deleted_by on every sales table |
| Audit trail completeness | PASS | Synchronous write within same DB transaction on every state change |
| Repository Pattern | PASS | No direct DB access from Application or Domain layers |
| DDD Aggregate Roots | PASS | 12 Aggregate Roots: Customer, CustomerCategory, CustomerGroup, PaymentTerm, SalesQuotation, SalesOrder, DeliveryNote, SalesInvoice, SalesReturn, PriceList, DiscountRule, SalesApprovalMatrix |
| Feature Flag strategy | PASS | Company-scoped DB table; reuses FeatureFlagService from Epic 5 pattern |
| No hardcoded secrets | PASS | All config via environment variables |
| No circular dependencies | PASS | Domain has zero framework dependencies |
| Immutability of issued invoices | PASS | No invoice update endpoints after issuance; credit notes provide correction path |
| DN append-only after dispatch | PASS | Dispatched DNs: no edit endpoints; corrections via Sales Return only |
| Epic 4 RBAC integration | PASS | Permission identifiers follow `sales.<resource>.<action>` pattern |
| Epic 5 stock integration | PASS | DN dispatch calls Epic 5's SALES_DISPATCH stock movement; Return receipt calls SALES_RETURN_INBOUND |
| Self-approval prevention | PASS | Domain invariant: approver_id != requestor_id enforced at domain layer |
| Backward compatibility | PASS | Epic 5 product/stock interfaces consumed; no modifications to Epics 1–6 |
| Gap-free invoice sequencing | PASS | Advisory lock on per-company sequence record ensures gap-free numbers |
| Price-at-point-of-sale | PASS | Prices captured on document lines at creation time; immutable thereafter |

**Constitution Check Result: ALL PASS — Phase 1 implementation approved to proceed.**

---

## Project Structure

### Documentation (this feature)

```text
specs/007-sales-management/
├── spec.md              # Official SSOT — Epic 7 specification v1.0
├── plan.md              # This file — implementation blueprint
├── research.md          # Architecture decisions resolved (generated below)
├── data-model.md        # Aggregate roots, state machines, entity relationships
├── contracts/           # OpenAPI contracts (generated in Phase 10)
│   ├── sales-v1.yaml
│   └── events.md
├── checklists/
│   └── requirements.md  # Spec quality checklist — all items PASS
├── quickstart.md        # Developer quickstart guide
└── tasks.md             # /sp.tasks output — NOT created by /sp.plan
```

### Source Code (repository root)

```text
backend/
├── modules/
│   └── sales/
│       ├── models/               # SQLAlchemy ORM models (all sales entities)
│       ├── schemas/              # Pydantic request/response schemas
│       ├── repositories/         # Concrete repository implementations
│       ├── services/             # Application services (one per sub-domain)
│       ├── router.py             # FastAPI router — sales endpoints
│       └── events/               # 38 domain event classes
│
└── migrations/
    └── versions/
        └── [0xx]_sales_*.py      # Alembic migrations for sales tables

frontend/
├── src/
│   └── app/
│       └── (protected)/
│           └── (sales)/
│               ├── customers/             # Customer management pages
│               ├── quotations/            # Quotation management pages
│               ├── sales-orders/          # Sales order management pages
│               ├── delivery-notes/        # Delivery note management pages
│               ├── invoices/              # Invoice management pages
│               ├── returns/               # Sales return management pages
│               ├── pricing/               # Price list and discount management
│               └── reports/               # Sales report and KPI pages
│   └── components/
│       └── sales/                         # Reusable sales UI components
│   └── lib/
│       └── api/
│           └── sales.ts                   # API client for sales endpoints

backend/tests/
├── unit/modules/sales/                    # Domain + application layer unit tests
├── integration/repositories/sales/        # Repository + service integration tests
├── integration/api/v1/sales/              # FastAPI endpoint tests
├── security/sales/                        # Security review tests
└── performance/sales/                     # Performance benchmarks
```

**Structure Decision**: Modular monolith pattern consistent with Epics 1–6. Sales module isolated within `backend/modules/sales/` following the same structure as `backend/modules/purchase/` and `backend/modules/inventory/`. No new infrastructure components required — reuses the auth, company context, RBAC, audit logging, and FeatureFlagService established in Epics 1–6.

---

## Complexity Tracking

| Decision | Why Needed | Simpler Alternative Rejected Because |
|----------|------------|--------------------------------------|
| 7-level price resolution hierarchy | Serves retail, wholesale, corporate, government pricing from single engine | Per-customer-type pricing logic would duplicate resolution code and diverge |
| Separate approval engine (sales-internal) | Serves both SO and Sales Return approvals; reuses Epic 6 pattern | Importing Epic 6's engine creates tight coupling; shared service is premature |
| Gap-free invoice sequencing with advisory locks | Regulatory compliance in many jurisdictions | PostgreSQL SEQUENCE doesn't roll back with transactions; would create gaps |
| DN → Inventory transactional write | Prevents inventory inconsistency on delivery | Async update creates window of incorrect stock levels |
| Credit check at approval (not creation) | Sales reps need to prepare orders freely before commitment decision | Creation-time check blocks drafts unnecessarily |
| Quotation revision snapshots | Customers always see latest; company retains history for audit | In-place edit loses history; version column alone doesn't capture line-level changes |

---

## Implementation Strategy

Epic 7 follows **11 sequential phases** organised by domain dependency order. Each phase delivers a complete working slice: domain entity → repository → service → API → frontend → tests. No phase begins until the previous phase passes its exit criteria.

### Delivery Philosophy

1. **Vertical Slice First**: Every phase is independently demonstrable to the business
2. **Test-Driven Thinking**: Every use case defined by acceptance criteria before implementation
3. **Feature Toggle Wrapping**: All Ready-but-Disabled and Future capabilities gated from day 1
4. **Price-at-Point-of-Sale**: Prices captured on documents at creation time and never recalculated
5. **Epic 5 Contract Respect**: DN dispatch and Return receipt are the only cross-module writes; all other Epic 5 interactions are read-only
6. **Pricing Engine First**: The pricing sub-system is built in Phase 3 before any transactional document workflow begins, ensuring quotations, orders, and invoices share the same resolution logic
7. **Credit Control Foundation**: Customer credit management is built with the Customer Master (Phase 2) and enforced at order approval (Phase 5)

### Phase Dependencies

```
Phase 1 (Sales Foundation)
  └── Phase 2 (Customer Master Core)
        └── Phase 3 (Pricing Engine)
Phase 1
  └── Phase 3 (Pricing Engine)
Phase 2 + Phase 3
  └── Phase 4 (Sales Quotations)
        └── Phase 5 (Sales Orders + Approval)
              └── Phase 6 (Order Fulfilment + Delivery)
                    └── Phase 7 (Sales Invoicing)
                    └── Phase 8 (Sales Returns)
Phase 5–8 (all complete)
  └── Phase 9 (Sales Intelligence & Reporting)
Phase 1–9 (all complete)
  └── Phase 10 (Integration, Contracts & Import/Export)
Phase 1–10 (all complete)
  └── Phase 11 (Performance, Security, Testing & Epic Closure)
```

---

## Implementation Phases

---

### Phase 1: Sales Module Foundation & Scaffolding

**Objective**: Establish the sales module infrastructure, feature flag registry, number sequencing, and shared foundation components that all subsequent phases depend on.

**Business Value**: No direct user-visible business value; enables all subsequent phases without which the module cannot function.

**Scope**:
- Sales module scaffolding: directory structure, router registration, base schema classes, base repository
- Sales feature flag registry: all 14 feature flags registered with system defaults
- Document number sequencing: configurable auto-generation for SQ, SO, DN, SI, SR numbers
- Customer Category master data (company-scoped, configurable)
- Customer Group master data (company-scoped, configurable)
- Payment Terms master data (company-scoped — reuse Epic 6 pattern or shared table)
- Sales Reason Code registry (return reasons, cancellation reasons)
- Sales Configuration entity (company-level settings: validity days, margin threshold, etc.)
- Sales-specific audit logging integration (reuses Epic 5 audit pattern)
- API router registered at `/api/v1/companies/{company_id}/sales/`

**Prerequisites**: Epics 1–6 complete; PostgreSQL 16 running; `modules/inventory/` and `modules/purchase/` stable

**Dependencies**: Epic 1 (FastAPI scaffold), Epic 3 (company context), Epic 4 (RBAC), Epic 5 (FeatureFlagService pattern)

**Deliverables**:
- Sales module registered in main router
- Feature flag table extended with all 14 sales flags (reuses Epic 5's `company_feature_flags` table)
- Number sequence service: configurable format, prefix, auto-increment
- Customer Category CRUD: code-unique per company
- Customer Group CRUD: code-unique per company
- Payment Terms CRUD (or reuse from Epic 6 if shared)
- Sales Reason Code CRUD: type-scoped (RETURN / CANCELLATION / REJECTION)
- Sales Configuration CRUD: company-level settings
- Alembic migrations: sales_sequences, customer_categories, customer_groups, sales_reason_codes, sales_configuration
- API endpoints: `/customer-categories`, `/customer-groups`, `/payment-terms`, `/reason-codes`, `/configuration`
- Frontend: Category, Group, Payment Terms, and Configuration management pages
- Tests: All master data invariants, feature flag resolution, number sequence generation

**Acceptance Criteria**:
- [ ] Sales module router responds at `/api/v1/companies/{company_id}/sales/`
- [ ] Feature flag resolution works for all 14 sales flags with fallback to defaults
- [ ] SQ/SO/DN/SI/SR number generation produces sequential, company-unique, prefix-formatted numbers
- [ ] Customer Category code unique per company enforced
- [ ] Customer Group code unique per company enforced
- [ ] All entities have company_id, soft-delete, and audit fields

**Exit Criteria**: All unit, integration, and API tests pass; migrations run clean; Docker compose up with no errors

**Risks**:
- Number sequence contention under concurrent document creation — mitigate with SELECT FOR UPDATE on sequence record
- Payment Terms shared vs sales-scoped — verify if Epic 6's payment_terms can be reused or if separate sales-scoped terms are needed

**Estimated Complexity**: Low

---

### Phase 2: Customer Master

**Objective**: Implement the Customer entity, its lifecycle, all core attributes, contacts, addresses, bank details, credit management, custom fields, documents, and notes.

**Business Value**: Companies can create, manage, and search customers. Sales team can onboard new customers and manage the full customer lifecycle. Finance can manage credit limits and credit holds.

**Scope**:
- Customer aggregate root (all attributes per spec §14)
- Customer status lifecycle state machine: DRAFT → ACTIVE → ON_HOLD → BLOCKED → INACTIVE
- Customer code uniqueness per company (auto-generated or manual, immutable after creation)
- Customer contacts (multiple; primary designation; billing/shipping contact flags)
- Customer addresses (billing/shipping types; default billing and default shipping enforcement)
- Customer bank details (Finance Manager restricted)
- Customer credit management: credit limit, credit status (GOOD/WARNING/EXCEEDED/HOLD), credit hold
- Customer rating (A–F, manual assignment)
- Tax information (TRN, tax exempt flag, certificate)
- Custom fields (JSON-based, up to 20 per company)
- Customer documents (file attachments via Epic 1 file storage)
- Customer notes (append-only)
- Customer search: full-text on name/code/contact, filters by status/category/group/type
- Customer bulk import from CSV/Excel (feature flag: `sales.customer_bulk_import`)
- Customer data export to CSV/Excel

**Prerequisites**: Phase 1 complete

**Deliverables**:
- Domain entities: Customer, CustomerContact, CustomerAddress, CustomerBankDetail, CustomerNote, CustomFieldValue
- Customer aggregate with all invariants enforced
- Customer repository: FTS search, status filter, category/group filter, pagination
- Application services: CreateCustomer, UpdateCustomer, ActivateCustomer, DeactivateCustomer, PlaceOnHold, BlockCustomer, UnblockCustomer, ReleaseHold, ManageContacts, ManageAddresses, ManageBankDetails, SetCreditLimit, SearchCustomers, BulkImportCustomers, ExportCustomers
- API endpoints: `/api/v1/companies/{id}/sales/customers` (full lifecycle + search + contacts + addresses + import/export)
- Publish domain events: customer.created, customer.updated, customer.activated, customer.deactivated, customer.blocked, customer.unblocked, customer.credit_limit_changed, customer.credit_hold_placed, customer.credit_hold_released (9 events)
- Frontend: Customer list (with search/filter), Customer detail (tabs: General, Contacts, Addresses, Financial, Documents, Notes), Customer create/edit, Bulk import UI
- Tests: All status transitions, uniqueness enforcement, search accuracy, import validation, credit management, contact/address invariants, tenant isolation

**Acceptance Criteria**:
- [ ] Customer code unique per company enforced at domain level, immutable after creation
- [ ] Status transitions follow defined state machine only (invalid transitions rejected)
- [ ] DRAFT/INACTIVE customers cannot be referenced on sales documents
- [ ] ON_HOLD/BLOCKED customers block new order creation
- [ ] Customer cannot be activated without at least one primary contact and one billing address
- [ ] Exactly one default billing address and one default shipping address enforced
- [ ] Credit limit changes require Finance Manager or Company Owner permission
- [ ] Credit status auto-calculated: GOOD/WARNING/EXCEEDED based on configurable threshold (default 80%)
- [ ] Credit hold manually placed/released by Finance Manager
- [ ] Customer FTS search returns results in < 300ms p95
- [ ] Bulk import 10,000 customers completes in < 60 seconds with row-level error reporting
- [ ] All customer operations scoped to company_id (zero cross-tenant leakage)
- [ ] All 9 customer domain events published with correct payloads

**Exit Criteria**: All tests pass; customer lifecycle fully exercisable via API; FTS search verified; bulk import tested with 10K dataset; credit management verified

**Risks**:
- Bulk import memory at 10K rows — streaming CSV parser with 500-row batch writes
- FTS index staleness — synchronous tsvector update on every customer write

**Estimated Complexity**: High

---

### Phase 3: Pricing Engine

**Objective**: Implement the complete pricing sub-system: price lists, price entries, customer-specific pricing, discount rules, and the 7-level price resolution service.

**Business Value**: Sales team can manage product pricing with multiple price lists, quantity breaks, and customer-specific overrides. Discount rules automate promotional and volume discounts. Minimum margin guard prevents below-cost sales.

**Scope**:
- PriceList aggregate: name, currency, effective dates, default flag, priority, active flag
- PriceEntry: product reference (Epic 5), unit price, minimum quantity (price breaks), UOM
- CustomerSpecificPrice: per-customer per-product price overrides with effective dates
- DiscountRule: percentage/fixed/volume/promotional with applicability filters (customer scope, product scope)
- PricingService: 7-level price resolution (Manual → Customer-Specific → Group → Category → Active List → Default List → Base Price)
- Minimum margin guard: warn/block when margin falls below configurable threshold
- Price override audit: log original price, override price, user, reason
- Discount application audit: log rule reference, discount value

**Prerequisites**: Phase 1 complete; Epic 5 Product API available (for product reference and base price)

**Deliverables**:
- Domain entities: PriceList, PriceEntry, CustomerSpecificPrice, DiscountRule
- PricingService: resolve_price(company_id, customer_id, product_id, quantity) → PriceResolution
- DiscountService: evaluate_discounts(company_id, customer_id, product_id, quantity, order_value) → applicable discounts
- MarginGuardService: check_margin(unit_price, cost_price, min_margin_pct) → MarginResult
- API endpoints: `/price-lists` (CRUD + entries), `/customer-prices` (CRUD), `/discount-rules` (CRUD), `/pricing/resolve` (price resolution endpoint for testing)
- Frontend: Price List management (with inline entry editing), Customer-Specific Price management, Discount Rule management
- Tests: All 7 resolution levels, quantity break resolution, discount applicability, margin guard, priority ordering, effective date filtering

**Acceptance Criteria**:
- [ ] Price resolution returns correct price at each of the 7 hierarchy levels
- [ ] Quantity breaks: the price entry with highest min_quantity <= ordered quantity is selected
- [ ] Exactly one price list marked as default per company (enforced at domain level)
- [ ] Customer-specific prices override price list prices
- [ ] Discount rules filter correctly by customer scope and product scope
- [ ] Only one non-stackable discount applies per line (highest priority wins)
- [ ] Minimum margin guard warns when margin < threshold
- [ ] Price resolution completes in p95 < 100ms
- [ ] All pricing operations scoped to company_id

**Exit Criteria**: All 7 resolution levels tested with known values; discount rules tested; margin guard tested; performance benchmark passes

**Risks**:
- Price resolution performance with large price lists (50,000 entries) — index on (company_id, price_list_id, product_id); cache hot price lists
- Discount rule conflict resolution — enforce priority ordering; document that highest priority wins

**Estimated Complexity**: High

---

### Phase 4: Sales Quotations

**Objective**: Implement the Sales Quotation lifecycle — the commercial offer document from creation through customer acceptance to Sales Order conversion.

**Business Value**: Sales team can create formal quotations with accurate pricing, track quotation status, manage revisions, and convert accepted quotations to sales orders.

**Scope**:
- SalesQuotation aggregate: header + quotation lines + revision history
- Quotation status state machine: DRAFT → SENT_TO_CUSTOMER → ACCEPTED/REJECTED → CONVERTED/EXPIRED/CANCELLED
- Quotation number auto-generation (SQ-YYYYMMDD-NNNN)
- Pricing integration: line prices resolved via Phase 3 PricingService
- Revision history: snapshot of quotation + lines on each revision; read-only previous revisions
- Validity management: expiry date, configurable default validity, expiry warning event
- Quotation-to-Order conversion: creates draft SO with lines, prices, and terms copied; 1:1 relationship
- Line-level and document-level discounts
- Customer-facing notes and internal notes

**Prerequisites**: Phases 2 (Customer Master) and 3 (Pricing Engine) complete

**Deliverables**:
- Domain entities: SalesQuotation, QuotationLine, QuotationRevision
- SalesQuotation aggregate with state machine invariants
- Application services: CreateQuotation, UpdateQuotation, SendQuotation, AcceptQuotation, RejectQuotation, ConvertToOrder, CancelQuotation, ExpireQuotation, ReviseQuotation
- Domain events: sales.quotation.created, .sent, .accepted, .rejected, .converted, .expired, .cancelled, .expiring_soon (8 events)
- API endpoints: `/quotations` (full lifecycle + revision history + conversion)
- Frontend: Quotation list, Quotation create/edit (with product search, price resolution), Quotation detail (revision timeline), Convert-to-Order button
- Tests: All state transitions, revision snapshots, validity management, conversion accuracy, pricing integration

**Acceptance Criteria**:
- [ ] Quotation state machine enforces defined transitions only
- [ ] Quotations in non-DRAFT status are immutable
- [ ] Revision history preserved as JSON snapshots (read-only previous revisions)
- [ ] Validity date required and >= quotation date
- [ ] Expired quotations automatically transition to EXPIRED status
- [ ] Only ACCEPTED quotations can be converted (1:1 conversion)
- [ ] Converted SO references originating quotation for traceability
- [ ] Prices resolved via PricingService on line addition
- [ ] All 8 quotation domain events published

**Exit Criteria**: All state transitions tested; revision history verified; conversion tested end-to-end; pricing integration verified; expiry tested

**Risks**:
- Revision snapshot size for large quotations (500 lines) — JSONB with compression; lazy-load revisions on demand

**Estimated Complexity**: Medium

---

### Phase 5: Sales Orders & Approval Workflow

**Objective**: Implement the Sales Order lifecycle, configurable approval workflow with credit check integration, and the approval matrix sub-system.

**Business Value**: Companies can process formal sales commitments with governed approval workflows. Credit control prevents overexposure. Auto-approval accelerates low-value transactions.

**Scope**:
- SalesOrder aggregate: header + order lines (with delivery tracking fields)
- SO status state machine: DRAFT → PENDING_APPROVAL → APPROVED/REJECTED → PARTIALLY_DELIVERED → DELIVERED → INVOICED → CLOSED / CANCELLED
- SO number auto-generation (SO-YYYYMMDD-NNNN)
- SO creation from quotation conversion (Phase 4 integration) and direct creation
- SalesApprovalMatrix: configurable multi-level approval based on order value and customer category
- Approval workflow: submit → route to approver(s) → approve/reject → re-submit on rejection
- Credit check at approval time: outstanding + pending > credit_limit → block approval
- Auto-approval below configurable threshold (feature flag: `sales.auto_approve_orders`)
- Self-approval prevention: requestor cannot approve own order
- Order cancellation with mandatory reason; release inventory reservations (Phase 6)
- Configurable policy: require quotation before order (`sales.require_quotation_before_order`)
- Order priority levels: LOW, NORMAL, HIGH, URGENT
- Approval history (immutable records)

**Prerequisites**: Phases 2 (Customer, credit management) and 3 (Pricing) complete

**Deliverables**:
- Domain entities: SalesOrder, OrderLine, SalesApprovalMatrix, SalesMatrixRule, SalesApprovalRecord
- SalesOrder aggregate with all invariants (immutability in PENDING_APPROVAL, credit check guard)
- Approval service: route to approvers, evaluate matrix rules, self-approval prevention
- Credit check service: evaluate customer credit status at approval
- Application services: CreateSO, CreateSOFromQuotation, UpdateSO, SubmitSO, ApproveSO, RejectSO, CancelSO, CloseSO, ConfigureApprovalMatrix
- Domain events: sales.order.created, .submitted, .approved, .rejected, .cancelled, .partially_delivered, .delivered, .invoiced, .closed, .credit_hold (10 events)
- API endpoints: `/sales-orders` (full lifecycle + search), `/sales-approval-matrix` (configure)
- Frontend: SO list (pipeline view), SO create/edit (with product search, pricing), SO detail (approval timeline), Approval Matrix configuration, Pending Approvals inbox
- Tests: All state transitions, approval workflow (single/multi-level), credit check blocking, auto-approval, self-approval prevention, quotation-to-order linkage

**Acceptance Criteria**:
- [ ] SO state machine enforces defined transitions only
- [ ] Orders in PENDING_APPROVAL status are immutable
- [ ] Credit check at approval: exceeded credit blocks approval
- [ ] Credit hold manually placed/released by Finance Manager blocks/unblocks new orders
- [ ] Auto-approval works for orders below configured threshold when customer credit is GOOD
- [ ] Self-approval prevention enforced — requestor cannot approve own order
- [ ] Rejected orders return to DRAFT for revision (approval version incremented)
- [ ] `sales.require_quotation_before_order` flag blocks direct order creation when enabled
- [ ] Cancellation requires reason; cancellation of approved orders releases any reservations
- [ ] All 10 SO domain events published

**Exit Criteria**: All state transitions tested; approval workflow end-to-end; credit check verified; auto-approval tested; self-approval prevention verified

**Risks**:
- Concurrent approval race condition — optimistic locking (version field) on approval document
- Credit check performance — cache credit status; recalculate asynchronously on balance changes

**Estimated Complexity**: High

---

### Phase 6: Order Fulfilment & Delivery Notes

**Objective**: Implement the Delivery Note lifecycle — the document recording physical dispatch of goods and triggering inventory deduction via Epic 5.

**Business Value**: Warehouse team can record what was dispatched. Stock levels update automatically. Partial delivery is tracked. Sales orders reflect accurate delivery status.

**Scope**:
- DeliveryNote aggregate: header + DN lines (SO line reference, quantity dispatched)
- DN status state machine: DRAFT → DISPATCHED → DELIVERED / CANCELLED
- DN number auto-generation (DN-YYYYMMDD-NNNN)
- DN only against APPROVED or PARTIALLY_DELIVERED orders
- Inventory availability check via Epic 5 before DN creation
- Stock reservation on DN creation: Epic 5 `StockMovement(SALES_RESERVATION)`
- Stock deduction on DN dispatch: Epic 5 `StockMovement(SALES_DISPATCH)` — transactional
- Reservation release on DN cancellation: Epic 5 `StockMovement(SALES_RESERVATION_RELEASE)`
- Partial delivery: multiple DNs against one SO; cumulative quantity tracking per SO line
- Delivery quantity validation: dispatched cannot exceed remaining ordered quantity
- SO status auto-update: APPROVED → PARTIALLY_DELIVERED → DELIVERED
- Backorder queue: unfulfilled lines tracked for future fulfilment notification
- Carrier and tracking number capture (optional)

**Prerequisites**: Phase 5 (Sales Orders) complete; Epic 5 stock movement interface available

**Deliverables**:
- Domain entities: DeliveryNote, DeliveryNoteLine
- DeliveryNote aggregate with quantity validation and state machine
- Application services: CreateDN, DispatchDN, CancelDN, CheckAvailability, ReserveStock, DeductStock, UpdateSODeliveryStatus
- Cross-module integration: `InventoryStockService.reserve_stock()`, `.deduct_stock()`, `.release_reservation()` called within DN operations
- Domain events: sales.delivery.created, .dispatched, .delivered, .cancelled (4 events)
- API endpoints: `/delivery-notes` (create, dispatch, cancel, view)
- Frontend: DN list, DN create (SO selection + line quantity entry with availability display), DN detail, dispatch confirmation
- Tests: All DN scenarios (partial, full, quantity validation), Epic 5 stock integration (transactional rollback test), SO status auto-update, backorder tracking

**Acceptance Criteria**:
- [ ] DN cannot be created against a non-APPROVED/PARTIALLY_DELIVERED order
- [ ] Delivery quantity per line cannot exceed remaining undelivered quantity
- [ ] DN creation reserves stock via Epic 5 (SALES_RESERVATION)
- [ ] DN dispatch deducts stock via Epic 5 (SALES_DISPATCH) — transactional with DN status update
- [ ] DN cancellation releases reserved stock (SALES_RESERVATION_RELEASE)
- [ ] DN dispatch and stock deduction committed in same database transaction (rollback if either fails)
- [ ] SO status auto-updates to PARTIALLY_DELIVERED / DELIVERED on dispatch confirmation
- [ ] Dispatched DN is immutable (no edit endpoints after dispatch)
- [ ] Low stock after dispatch publishes notification for backorder tracking
- [ ] All 4 delivery domain events published

**Exit Criteria**: All DN scenarios tested; Epic 5 inventory integration tested transactionally; rollback test passes; partial delivery verified; SO status auto-update verified

**Risks**:
- Cross-module transaction failure (DN dispatch + inventory update) — use Unit of Work pattern; both operations in single SQLAlchemy session; rollback if either fails
- Concurrent DNs against same SO line (race to full delivery) — SELECT FOR UPDATE on SO open-quantity state

**Estimated Complexity**: High

---

### Phase 7: Sales Invoicing

**Objective**: Implement the Sales Invoice lifecycle — the financial document requesting payment from the customer, with gap-free sequential numbering.

**Business Value**: Finance team can generate invoices from deliveries or orders. Invoice numbering is regulatory-compliant. Discounts and charges are accurately captured. Credit notes are ready for future AR.

**Scope**:
- SalesInvoice aggregate: header + invoice lines + invoice charges
- Invoice status state machine: DRAFT → ISSUED → PAID (future) / CANCELLED / CREDIT_NOTE_ISSUED
- Invoice number auto-generation (SI-YYYYMMDD-NNNN) — gap-free via advisory lock
- Invoice generation modes: from Delivery Note, from Sales Order, or manual/direct
- DN consolidation: multiple DNs for same SO → single invoice
- Due date calculation from payment terms
- Line-level and document-level discounts
- Additional charges: freight, handling, insurance
- Tax readiness: tax_rate and tax_amount fields (defaulting to 0; future tax engine hooks)
- Amount-in-words generation
- Invoice cancellation: void with number preserved; no number reuse
- Issued invoice immutability: no edits after issuance; credit notes for adjustments
- SO status auto-update: DELIVERED → INVOICED after invoice generation
- Invoice PDF export (feature flag: `sales.invoice_pdf_export`)

**Prerequisites**: Phase 6 (Delivery Notes) complete for delivery-based invoicing; Phase 5 (Sales Orders) for order-based invoicing

**Deliverables**:
- Domain entities: SalesInvoice, InvoiceLine, InvoiceCharge
- SalesInvoice aggregate with gap-free sequencing and immutability invariants
- Invoice sequence service: advisory lock for gap-free numbering
- Application services: CreateInvoiceFromDN, CreateInvoiceFromSO, CreateDirectInvoice, IssueInvoice, CancelInvoice, GenerateCreditNote, ExportInvoicePDF
- Domain events: sales.invoice.created, .issued, .cancelled, .credit_note_issued (4 events)
- API endpoints: `/invoices` (create, issue, cancel, view, export)
- Frontend: Invoice list, Invoice create (from DN/SO selection), Invoice detail, Issue confirmation, PDF preview
- Tests: Gap-free sequencing under concurrent generation, DN-to-invoice mapping, SO status update, immutability enforcement, charge/discount computation, amount-in-words

**Acceptance Criteria**:
- [ ] Invoice numbers are strictly sequential and gap-free per company
- [ ] Cancelled invoices retain their number; number never reused
- [ ] ISSUED invoices are immutable (no edit endpoints)
- [ ] Invoice generated from DN correctly maps DN lines to invoice lines
- [ ] Multiple DNs consolidated into single invoice
- [ ] Due date calculated from payment terms (invoice_date + due_days)
- [ ] Tax, discount, and charge fields correctly computed
- [ ] Amount-in-words generated for invoice total
- [ ] SO status auto-updates to INVOICED after invoice generation
- [ ] `sales.invoice_pdf_export` flag enables PDF generation
- [ ] All 4 invoice domain events published

**Exit Criteria**: Gap-free sequencing verified under concurrent load; all invoice generation modes tested; immutability enforced; PDF export tested

**Risks**:
- Gap-free sequencing contention under high concurrent invoice generation — advisory lock serialises per company; acceptable at current scale
- Amount-in-words for multi-currency — implement for base currency only; extend in multi-currency epic

**Estimated Complexity**: High

---

### Phase 8: Sales Returns

**Objective**: Implement the Sales Return / RMA workflow — the process for accepting returned goods from customers, restocking inventory, and generating credit notes or replacements.

**Business Value**: Sales and warehouse teams can formally process customer returns. Inventory is accurately restocked for accepted items. Credit notes reduce customer balances. Replacement orders maintain customer satisfaction.

**Scope**:
- SalesReturn aggregate: header + return lines (product, quantity, condition, reason)
- Return status state machine: DRAFT → PENDING_APPROVAL → APPROVED → RECEIVED → COMPLETED / CANCELLED
- Return number auto-generation (SR-YYYYMMDD-NNNN)
- Return approval: routes through SalesApprovalMatrix (from Phase 5)
- Return reason codes (from Phase 1)
- Return quantity validation: cannot exceed delivered quantities
- Goods receipt: warehouse confirms receipt of returned items (APPROVED → RECEIVED)
- Inventory restock on receipt: Epic 5 `StockMovement(SALES_RETURN_INBOUND)` for accepted items
- Resolution types:
  - CREDIT_NOTE: generates credit note document
  - REPLACEMENT: creates new SO with zero-value lines
  - REFUND_READINESS: marks for future refund processing
- Item condition tracking: NEW, USED, DAMAGED, DEFECTIVE
- Credit note generation (references original invoice and return)

**Prerequisites**: Phases 5 (Approval), 6 (Delivery — for delivered quantities), 7 (Invoice — for credit note reference) complete; Epic 5 stock movement interface available

**Deliverables**:
- Domain entities: SalesReturn, ReturnLine
- SalesReturn aggregate with return quantity validation and state machine
- Application services: CreateReturn, SubmitReturn, ApproveReturn, RejectReturn, ReceiveReturn, CompleteReturn, CancelReturn, GenerateCreditNote, CreateReplacementOrder
- Cross-module integration: `InventoryStockService.restock_sales_return()` on receipt confirmation
- Domain events: sales.return.created, .submitted, .approved, .rejected, .received, .completed, .refund_ready (7 events)
- API endpoints: `/sales-returns` (full lifecycle)
- Frontend: Return list, Return create (SO/Invoice selection + line entry), Return detail (approval flow), Receipt confirmation
- Tests: All state transitions, return quantity validation, inventory restock on receipt, credit note generation, replacement order creation

**Acceptance Criteria**:
- [ ] Return quantity per line <= delivered quantity on referenced SO/DN
- [ ] Return state machine enforces defined transitions only
- [ ] Return approval routes through SalesApprovalMatrix
- [ ] Inventory restocked when return transitions to RECEIVED (transactional)
- [ ] CREDIT_NOTE resolution generates a credit note document
- [ ] REPLACEMENT resolution creates a new zero-value SO linked to the return
- [ ] REFUND_READINESS publishes `sales.return.refund_ready` event
- [ ] Item condition tracked per return line
- [ ] All 7 return domain events published

**Exit Criteria**: All return state transitions tested; inventory restock verified transactionally; credit note generation verified; replacement order creation verified

**Risks**:
- Restock transaction failure — same Unit of Work pattern as Phase 6 DN dispatch

**Estimated Complexity**: Medium

---

### Phase 9: Sales Intelligence & Reporting

**Objective**: Implement all 15+ sales reports, 12 KPIs, and the KPI dashboard.

**Business Value**: Management gains full sales visibility. Revenue, margin, and performance are measurable. Quotation conversion and delivery performance are trackable.

**Scope**:
- All reports from spec §35:
  - Sales Summary (daily/weekly/monthly/yearly)
  - Sales by Customer
  - Sales by Product
  - Sales by Representative
  - Sales Order Pipeline
  - Sales vs Target
  - Top Customers
  - Sales Trend
  - Customer List
  - Customer Activity
  - New Customers
  - Customer Credit Report
  - Quotation Conversion Rate
  - Quotation Pipeline
  - Expired Quotations
  - Pending Deliveries
  - Delivery Performance
  - Backorder Report
  - Gross Margin by Product
  - Gross Margin by Customer
  - Discount Analysis
  - Sales Audit Trail
  - Price Override Report
  - Credit Limit Change Report
  - Approval History
- All 12 KPIs from spec §36: Revenue, Gross Margin %, Quotation Conversion Rate, AOV, Sales Growth, Customer Retention, On-Time Delivery, Outstanding Orders, Return Rate, Avg Days to Fulfil, Credit Utilisation, Invoice Cycle Time
- KPI dashboard endpoint
- CSV and Excel export for all reports
- All reports scoped by company_id; all RBAC-protected

**Prerequisites**: Phases 2–8 complete (all operational data available)

**Deliverables**:
- Report query services (read-only; no domain mutations)
- Report API endpoints: `/sales/reports/{report_type}` with filter parameters
- KPI API endpoint: `/sales/kpis`
- Export service: CSV + Excel generation per report
- Frontend: Report pages with date/customer/status filters; KPI dashboard with charts; export buttons
- Tests: Report accuracy against known datasets; KPI formula verification; export tested; tenant isolation on all reports

**Acceptance Criteria**:
- [ ] All 25 reports return data scoped to company_id
- [ ] All reports support date range, customer, status, and category filters
- [ ] All reports export to CSV and Excel correctly
- [ ] All 12 KPIs computed correctly against known test datasets
- [ ] Quotation Conversion Rate = converted / total quotations × 100
- [ ] Gross Margin = (revenue - COGS) / revenue × 100
- [ ] All report endpoints respond within p95 < 5 seconds
- [ ] No cross-tenant data in any report

**Exit Criteria**: All reports tested with realistic dataset; all 12 KPI formulas verified; export tested; cross-tenant isolation verified

**Risks**:
- Report performance at high transaction volume — use materialised summary views; refresh on document state changes

**Estimated Complexity**: Medium

---

### Phase 10: Integration, Contracts & Import/Export

**Objective**: Formalise all cross-module integration contracts, complete domain event publishing, generate OpenAPI specifications, and deliver the quickstart guide.

**Business Value**: Integration consumers (future Accounts Receivable, POS, E-commerce) have stable contracts. Domain events enable future event-driven enhancements.

**Scope**:
- Verify all 38 domain events are published on their correct triggers
- Event serialisation verification: all events JSON-serialisable with `event_version` field
- `InProcessEventBus` integration (same pattern as Epics 5 and 6)
- Epic 5 integration contract documentation: DN dispatch → StockMovement.SALES_DISPATCH; Return receipt → StockMovement.SALES_RETURN_INBOUND
- Epic 6 integration contract documentation: Low stock → purchase.reorder.suggested event
- Customer bulk import (finalised with full validation report)
- Invoice PDF export complete
- Delivery Note PDF export complete
- SO email to customer (`sales.so_email_customer` flag)
- OpenAPI specification generation: `specs/007-sales-management/contracts/sales-v1.yaml`
- Domain event contract documentation: `specs/007-sales-management/contracts/events.md`
- Quickstart developer guide: `specs/007-sales-management/quickstart.md`
- Agent context update

**Prerequisites**: All Phases 1–9 complete

**Deliverables**:
- Event publication verified for all 38 domain events
- EventBus integration (reuses Epic 5/6 InProcessEventBus)
- OpenAPI contract: `contracts/sales-v1.yaml`
- Event contract: `contracts/events.md`
- Quickstart guide: developer onboarding for sales module
- Tests: Event firing verified for all write operations; serialisation verified for all 38 events

**Acceptance Criteria**:
- [ ] All 38 domain events published on correct triggers
- [ ] All 38 events JSON-serialisable (verified in tests)
- [ ] EventBus interface is abstract — transport swappable without domain changes
- [ ] OpenAPI contract is complete, accurate, and matches all API endpoints
- [ ] `contracts/events.md` documents all 38 events with payload structure
- [ ] `quickstart.md` enables a new developer to create a customer, create an SO, dispatch a DN, and generate an invoice from scratch

**Exit Criteria**: All 38 events verified; OpenAPI contract generated; quickstart guide reviewed

**Risks**:
- Event schema breaking changes — include `event_version` field on all events from day 1

**Estimated Complexity**: Low

---

### Phase 11: Performance, Security, Testing & Epic Closure

**Objective**: Validate all performance targets, conduct security review, execute full regression and tenant isolation tests, and close the epic.

**Business Value**: Production readiness assured. All Epic Completion Criteria verified. Branch ready for merge.

**Scope**:
- Performance validation against all spec §45 targets:
  - Customer search p95 < 300ms
  - SO list p95 < 500ms
  - DN confirmation < 2 seconds
  - Invoice generation < 2 seconds
  - Price resolution p95 < 100ms
  - Report generation p95 < 5 seconds
  - All standard reads p95 < 200ms
- Database index audit: verify indexes on all foreign keys, status columns, date columns, FTS columns
- N+1 query elimination: audit all list endpoints
- Security review: SQL injection, XSS, mass-assignment, BOLA on all sales endpoints
- Full tenant isolation test: zero cross-company data leakage across all entities
- RBAC permission matrix test: all 11 roles × all sales operations
- End-to-end business workflow tests: all 6 workflows from spec §23
- Soft-delete completeness test: all entities
- Audit trail completeness test: all document state changes
- Docker Compose production-readiness verification
- Epic Completion Criteria verification: all 15 gates from spec §60
- Branch PR preparation

**Prerequisites**: All Phases 1–10 complete and passing

**Deliverables**:
- Performance test results against all spec targets
- Index optimisations applied (documented)
- Security review findings and remediations
- Tenant isolation test results: zero incidents
- Permission matrix test results: all 11 roles correct
- End-to-end test suite covering all 6 business workflows
- Docker verification result
- Epic 7 Completion Checklist (all 15 EC gates verified)
- PR for `007-sales-management` → `main`

**Acceptance Criteria**:
- [ ] All spec §45 performance targets met
- [ ] No N+1 queries on any list endpoint
- [ ] Zero security vulnerabilities found (or all found ones remediated)
- [ ] Zero cross-company data leakage across all entities
- [ ] All 11 RBAC roles operate with correct permission boundaries
- [ ] All 6 business workflows complete end-to-end without errors
- [ ] Docker Compose up → migrate → seed → API smoke test: all pass
- [ ] All 15 Epic Completion Criteria from spec §60 verified PASS
- [ ] Zero critical bugs open

**Exit Criteria**: All 15 Epic Completion Criteria PASS; PR approved; branch merged to main

**Estimated Complexity**: Medium

---

## Technical Architecture Plan

### Domain Layer Design

The domain layer has zero dependencies on FastAPI, SQLAlchemy, or any external framework. It contains:

- **Entities**: Customer, CustomerContact, CustomerAddress, CustomerBankDetail, CustomerNote, CustomerCategory, CustomerGroup, PaymentTerm, SalesQuotation, QuotationLine, QuotationRevision, SalesOrder, OrderLine, DeliveryNote, DeliveryNoteLine, SalesInvoice, InvoiceLine, InvoiceCharge, SalesReturn, ReturnLine, PriceList, PriceEntry, CustomerSpecificPrice, DiscountRule, SalesApprovalMatrix, SalesMatrixRule, SalesApprovalRecord, SalesConfiguration
- **Aggregate Roots**: Customer, CustomerCategory, CustomerGroup, PaymentTerm, SalesQuotation, SalesOrder, DeliveryNote, SalesInvoice, SalesReturn, PriceList, DiscountRule, SalesApprovalMatrix
- **Domain Events**: 38 events across 6 sub-domains (per spec §34)
- **Repository Interfaces**: Abstract contracts implemented by the infrastructure layer

**Key Invariants enforced at Domain Layer**:
- Customer code unique per company and immutable after creation (Customer aggregate)
- Issued invoices are immutable — no field updates; credit notes provide correction (SalesInvoice aggregate)
- Dispatched DNs are immutable — corrections via Sales Return only (DeliveryNote aggregate)
- Delivery quantity <= ordered quantity per SO line (DeliveryNote aggregate)
- Return quantity <= delivered quantity (SalesReturn aggregate)
- Requestor cannot be approver of their own document (SalesApprovalRecord)
- DRAFT/INACTIVE customers cannot be on sales documents (SalesOrder, SalesQuotation aggregates)
- Invoice numbers are gap-free per company (SalesInvoice aggregate)
- Prices are captured at document creation time and immutable thereafter (all document aggregates)
- Exactly one default price list per company (PriceList aggregate)

### Application Layer Design

The application layer orchestrates domain operations. It:

- Contains one Application Service per sub-domain (CustomerService, QuotationService, SalesOrderService, DeliveryService, InvoiceService, ReturnService, PricingService, ApprovalService, ReportService)
- Receives Pydantic schemas (not domain entities) from the API layer
- Calls repository interfaces (not concrete implementations)
- Publishes domain events via the EventBus interface
- Manages database transaction boundaries
- Never accesses PostgreSQL directly

**Key Application Services**:
- `CustomerService`: customer lifecycle, credit management, contact/address management, search, bulk import
- `PricingService`: 7-level price resolution, discount evaluation, margin guard
- `QuotationService`: quotation lifecycle, revision management, validity tracking, order conversion
- `SalesOrderService`: order lifecycle, quotation-to-order conversion, cancellation with reason
- `ApprovalService`: route documents through approval matrix; credit check at approval; self-approval prevention
- `DeliveryService`: DN lifecycle, availability check, stock reservation/deduction via Epic 5, SO status update
- `InvoiceService`: invoice lifecycle, gap-free sequencing, DN-to-invoice mapping, charge/discount computation
- `ReturnService`: return lifecycle, receipt, restock via Epic 5, credit note generation, replacement order creation
- `ReportService`: read-only report queries, KPI computations, export generation
- `FeatureFlagService`: reused from Epic 5 pattern — company-scoped flag resolution

### Repository Layer Design

The base repository class (consistent with Epics 5 and 6) enforces `company_id` on every query. No repository method exists without `company_id` as a mandatory first-class argument.

**Key patterns**:
- `BaseSalesRepository(company_id)` — all sales repositories inherit from this
- `CustomerRepository` — full CRUD with FTS search support
- `SalesOrderRepository` — read/write; orders in PENDING_APPROVAL are immutable (enforced at service layer)
- `DeliveryNoteRepository` — write on creation; no update after DISPATCHED status
- `SalesInvoiceRepository` — write on creation; no update after ISSUED status
- `SalesReturnRepository` — write with approval workflow
- `PriceListRepository` — CRUD with default flag enforcement
- `SalesApprovalRecordRepository` — append-only; records never updated or deleted

### Validation Layer Design

Validation operates at three layers:

1. **API Layer (Pydantic v2)**: Request schema validation — type, format, required fields
2. **Application Layer**: Business rule validation — credit limit check, approval matrix routing, delivery quantity validation, margin guard
3. **Domain Layer**: Invariant enforcement — immutability, self-approval prevention, quantity constraints, gap-free sequencing

### Pricing Engine Design

The pricing engine is a **resolution-based service** within the sales module:

- `PricingService.resolve_price(company_id, customer_id, product_id, quantity)` returns the resolved price with source metadata
- Resolution order: Manual Override → Customer-Specific → Customer Group → Customer Category → Active Price List → Default Price List → Product Base Price
- At each level, quantity breaks are evaluated (highest min_quantity <= requested quantity)
- The resolved price is stored on the document line at creation time — never recalculated
- `DiscountService.evaluate_discounts(...)` applies applicable discount rules with priority ordering
- `MarginGuardService.check_margin(...)` enforces minimum margin with warn/block behaviour

### Approval Engine Design

The approval engine follows the proven Epic 6 pattern as an **internal sub-system** within the sales module:

- `SalesApprovalMatrix` defines: rules (amount range, customer category conditions), approvers per level
- `ApprovalService.route_for_approval(document_type, document_id, amount, customer_category)` → determines approver(s)
- `SalesApprovalRecord` created per approval action — immutable once submitted
- Credit check integrated at approval: `CreditCheckService.evaluate(customer_id, order_total)` called during approval
- Same engine used for Sales Orders and Sales Returns
- Auto-approval: when order total < configured threshold AND customer credit = GOOD

### Authorization Design

Authorization follows the Epic 4 RBAC model with sales-specific permission identifiers:

| Module | Resource | Actions |
|--------|----------|---------|
| sales | customer | create, read, update, activate, deactivate, block, unblock, credit_limit, import, export |
| sales | quotation | create, read, update, send, accept, reject, convert, cancel |
| sales | order | create, read, update, submit, approve, reject, cancel |
| sales | delivery | create, read, dispatch, cancel |
| sales | invoice | create, read, issue, cancel, export |
| sales | return | create, read, submit, approve, receive, complete |
| sales | pricing | manage, read, override |
| sales | discount | manage |
| sales | report | read, export |
| sales | config | manage |
| sales | approval | manage |
| sales | feature_flag | manage |

### Audit Logging Design

Every write operation produces an audit record within the same database transaction. Consistent with Epics 5 and 6 pattern:

- Table: `audit_logs` (shared schema from Epic 2/3)
- Fields: `entity_type`, `entity_id`, `action`, `old_value` (JSON), `new_value` (JSON), `user_id`, `company_id`, `performed_at`, `ip_address`
- Price overrides logged: original price, override price, user, reason
- Credit limit changes logged: old limit, new limit, approver
- Discount applications logged: rule reference, discount value

### Feature Toggle Design

Feature flags resolve in order: company-level override → system default. Reuses `FeatureFlagService` from Epic 5.

| Flag Key | Default | Controls |
|----------|---------|---------|
| `sales.customer_bulk_import` | false | Enables CSV/Excel customer import |
| `sales.so_email_customer` | false | Sends order confirmation email to customer |
| `sales.invoice_pdf_export` | false | Generates PDF invoices |
| `sales.so_barcode_scan` | false | Barcode-driven line entry on sales orders |
| `sales.dn_pdf_export` | false | Generates PDF delivery notes |
| `sales.customer_portal` | false | Customer self-service portal (future) |
| `sales.require_quotation_before_order` | false | Enforces quotation-to-order flow |
| `sales.auto_approve_orders` | false | Auto-approves orders below threshold |
| `sales.backorder_auto_fulfil` | false | Auto-creates DN when backorder stock arrives |
| `sales.direct_invoice` | false | Allows invoices without sales order |
| `sales.buy_x_get_y` | false | Buy X Get Y promotional discounts |
| `sales.multi_warehouse` | false | Routes fulfilment to specific warehouses |
| `sales.quotation_approval` | false | Requires approval before sending quotations |
| `sales.customer_rating_auto` | false | Auto-calculates customer rating from data |

---

## Data Strategy

### Ownership Map

| Data Domain | Owner in Epic 7 | Future Owner |
|-------------|----------------|--------------|
| Customer Master | Epic 7 (Sales) | Permanent — never transferred |
| Customer Categories & Groups | Epic 7 (Sales) | Permanent |
| Sales Quotations | Epic 7 (Sales) | Permanent |
| Sales Orders | Epic 7 (Sales) | Permanent |
| Delivery Notes | Epic 7 (Sales) | Permanent — referenced by future WMS |
| Sales Invoices | Epic 7 (Sales) | Permanent — referenced by Epic 8 AR |
| Sales Returns | Epic 7 (Sales) | Permanent |
| Price Lists & Entries | Epic 7 (Sales) | Permanent |
| Discount Rules | Epic 7 (Sales) | Permanent |
| Approval Records | Epic 7 (Sales) | Permanent — used by audit reports |
| Tax Fields (capture only) | Epic 7 (Sales) | Future Tax Engine will activate computation |
| Stock Impact (SALES_*) | Epic 5 (Inventory) | Epic 7 creates movements; Epic 5 owns the table |

### Immutability Guarantees

- **SalesApprovalRecord**: append-only once submitted; no update or delete operations
- **SalesInvoice** (issued): no edit endpoint exists after status = ISSUED
- **DeliveryNote** (dispatched): no edit endpoint after status = DISPATCHED
- **QuotationRevision**: read-only historical snapshots; never modified
- **All document prices**: captured at creation time; never recalculated

### Migration Strategy

- All Alembic migrations are additive
- No destructive migrations in Epic 7
- Future Epics will add columns (payment_id, ar_balance) — they will NOT rename or remove Epic 7 columns
- Tax fields present from day 1 (defaulting to 0); activated in future Tax Engine epic
- Currency_code captured on all documents; multi-currency conversion deferred to future epic

---

## Dependency Planning

### Internal Dependencies (within Epic 7)

| Phase | Depends On |
|-------|-----------|
| Phase 2 | Phase 1 (Module foundation, Categories, Groups, Payment Terms) |
| Phase 3 | Phase 1 (Module foundation); Epic 5 Product API (for base price) |
| Phase 4 | Phase 2 (Customer), Phase 3 (Pricing Engine) |
| Phase 5 | Phase 2 (Customer, credit management), Phase 3 (Pricing) |
| Phase 6 | Phase 5 (Sales Orders) |
| Phase 7 | Phase 6 (Delivery Notes for delivery-based invoicing) |
| Phase 8 | Phase 5 (Approval), Phase 6 (Delivery — for delivered quantities), Phase 7 (Invoice — for credit notes) |
| Phase 9 | Phases 2–8 (all operational data) |
| Phase 10 | All Phases 1–9 |
| Phase 11 | All Phases 1–10 |

### Cross-Epic Dependencies (upstream — already complete)

| Epic | Component Needed | Status |
|------|-----------------|--------|
| Epic 1 | FastAPI app scaffold, SQLAlchemy setup, Docker Compose, Alembic, file storage | Complete |
| Epic 2 | JWT authentication, auth middleware, user context extraction | Complete |
| Epic 3 | Company context resolution, company settings | Complete |
| Epic 4 | RBAC permission system, role resolver, permission checker middleware | Complete |
| Epic 5 | Product Master stable read API; StockMovement INSERT interface (SALES_RESERVATION, SALES_DISPATCH, SALES_RESERVATION_RELEASE, SALES_RETURN_INBOUND); FeatureFlagService; product base price | Complete |
| Epic 6 | InProcessEventBus pattern; Approval engine pattern reference; PurchaseSequenceService pattern | Complete |

### Cross-Epic Dependencies (downstream — to be provided by Epic 7)

| Future Epic | What Epic 7 Provides |
|------------|---------------------|
| Epic 8 (AR) | SalesInvoice APIs for payment tracking, ageing; Customer credit data |
| Epic 8 (Accounting) | Invoice and Credit Note data for journal entries |
| Epic 10 (POS) | Customer Master read API; SalesOrder + Invoice creation API |
| Epic 11 (E-commerce) | Customer and Order APIs for online storefront integration |
| Epic 9 (CRM) | Customer Master shared read API |
| Reports Epic | All sales read APIs (reports, KPIs) |
| AI Epic | Historical sales and customer data for forecasting |

### Blocked / Deferred Items

| Item | Status | Activation |
|------|--------|-----------|
| Accounts Receivable | Deferred | Epic 8 |
| Payment Collection | Deferred | Epic 8 |
| Multi-Currency | Deferred — currency_code field present on all documents | Future Epic |
| Multi-Branch | Deferred — branch_id nullable field reserved | Branch Management Epic |
| Tax Computation | Deferred — fields present; computation absent | Future Tax Engine |
| POS Integration | Deferred | Epic 10 |
| E-commerce Integration | Deferred | Epic 11 |
| Dynamic/AI Pricing | Deferred | AI Epic |
| Customer Portal | Ready/Disabled — behind feature flag | Future |
| Subscription Billing | Deferred | Future |
| Commission Calculation | Deferred | HR/Payroll Epic |

---

## Testing Strategy

### Unit Testing

**Scope**: Domain entities, aggregate root invariants, state machine transitions, price resolution, discount evaluation, margin guard, approval routing logic, credit check formula

**Approach**:
- Zero infrastructure dependencies — all domain tests run in-memory
- One test class per aggregate root
- Test every valid state transition
- Test every invalid state transition (expect domain exception)
- Test approval engine: single-level, multi-level, self-approval prevention
- Test price resolution: all 7 levels with known values
- Test credit check: GOOD, WARNING, EXCEEDED, HOLD scenarios

**Coverage Target**: > 95% domain layer

### Integration Testing

**Scope**: Repository implementations, database queries, transaction boundaries, Epic 5 stock interface

**Approach**:
- Test database (PostgreSQL in Docker)
- Test every repository method with real SQL
- Test company_id isolation: no data returned for wrong company
- Test soft-delete: deleted records excluded from all queries
- Test transactional DN dispatch: verify rollback leaves both DN and stock movement absent
- Test concurrent invoice generation (gap-free sequence uniqueness under load)
- Test concurrent SO creation (sequence uniqueness)

**Coverage Target**: > 90% repository layer

### API Testing

**Scope**: All FastAPI endpoints; authentication; permission enforcement; validation

**Approach**:
- TestClient with real database (PostgreSQL in Docker)
- Test each endpoint for correct status codes, response schemas, and side effects
- Test RBAC: each of 11 roles × each permission
- Test invalid inputs (Pydantic validation rejection)
- Test pagination, filtering, sorting on all list endpoints

**Coverage Target**: > 90% API layer

### Business Workflow Testing

**Scope**: End-to-end tests covering all 6 business workflows from spec §23

**Approach**:
- Workflow 1: Standard O2C — Quotation → Order → Approval → Delivery → Invoice
- Workflow 2: Direct Order — Skip quotation
- Workflow 3: Cash Sale — Auto-approve + immediate delivery + invoice
- Workflow 4: Sales Return — Create → Approve → Receive → Complete (credit note/replacement)
- Workflow 5: Partial Delivery — Multiple DNs, SO status tracking
- Workflow 6: Customer Onboarding — Create → Activate → First order

**Coverage Target**: All 6 workflows passing

### Performance Testing

**Scope**: All spec §45 performance targets

**Approach**:
- Seed database with realistic volumes (100K customers, 500K orders)
- Measure p95 latency for each target operation
- Verify price resolution < 100ms
- Verify gap-free invoice sequence under concurrent generation

### Security Testing

**Scope**: OWASP Top 10 coverage on all sales endpoints

**Approach**:
- SQL injection testing on all search/filter parameters
- XSS testing on all text fields (notes, descriptions)
- Mass assignment testing (whitelisted fields only)
- BOLA testing (cross-tenant, cross-user access)
- Rate limiting verification

---

## Risk Analysis

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Inventory integration complexity | High | Medium | Use established cross-module contract pattern from Epic 6; transactional Unit of Work |
| Credit check performance bottleneck | Medium | Low | Cache credit status; recalculate asynchronously on balance changes |
| Invoice sequencing under concurrency | High | Medium | Database-level advisory lock; verified with concurrent test |
| Price resolution complexity (7 levels) | Medium | Medium | Well-defined priority hierarchy; comprehensive test suite; cache hot price lists |
| Large order line count performance | Medium | Low | Pagination on lines; lazy loading; database indexing |
| Quotation revision storage growth | Low | Medium | JSONB compression; lazy-load revisions; retention policy |
| Scope creep into AR/Accounting | High | Medium | Strict bounded context; explicit Out of Scope list |
| Multi-currency readiness without implementation | Low | High | Currency fields present; conversion logic deferred |

---

## Quality Gates

Every phase must pass these gates before the next phase begins:

| Gate | Verification |
|------|-------------|
| Architecture Review | Layer separation, dependency direction, aggregate boundaries |
| Code Review Strategy | PR review with checklist; no direct commits to feature branch |
| Testing Strategy | Unit + integration + API tests all pass; coverage targets met |
| Security Review | No OWASP Top 10 vulnerabilities; company_id isolation verified |
| Performance Review | Relevant endpoints meet p95 targets from spec §45 |
| Docker Verification | `docker compose build && docker compose up` succeeds; migrations run; health check passes |
| Epic Review | Acceptance criteria for the phase verified |

---

## Epic Completion Criteria

Epic 7 is COMPLETE only when ALL of the following criteria are verified:

| EC | Criterion | Verification |
|----|-----------|-------------|
| EC-01 | Customer Master fully operational | Integration test: create, activate, block, unblock, deactivate |
| EC-02 | Sales Quotation lifecycle complete | Integration test: create, send, accept, convert to SO |
| EC-03 | Sales Order lifecycle complete with approval | Integration test: create, submit, approve, deliver, invoice, close |
| EC-04 | Credit check enforcement operational | Integration test: exceed credit limit, approval blocked |
| EC-05 | Delivery Note lifecycle with inventory integration | Integration test: create DN, dispatch, verify stock deducted (Epic 5) |
| EC-06 | Sales Invoice with gap-free sequencing | Integration test: concurrent invoice generation, verify gap-free |
| EC-07 | Sales Return with inventory restock | Integration test: create return, approve, receive, verify restock (Epic 5) |
| EC-08 | Pricing engine with 7-level resolution | Unit test: all 7 levels return correct prices |
| EC-09 | RBAC enforcement across all operations | Permission matrix test: all 11 roles × all operations |
| EC-10 | Multi-tenant isolation verified | Isolation test: zero cross-company data leakage |
| EC-11 | All 38 domain events published | Event coverage test: all events on correct triggers |
| EC-12 | Performance targets met (§45) | Benchmark test: all p95 targets pass |
| EC-13 | All reports and KPIs operational | Report test: all 25+ report types return correct data |
| EC-14 | Docker verification passes | Docker Compose: build, migrate, smoke test |
| EC-15 | Full regression suite passes (Epics 1–7) | pytest: zero failures across all modules |

---

*This implementation plan is the permanent technical blueprint for Epic 7 — Sales Management. All task breakdowns and implementation code must align with this document. Any deviations require plan amendment with version increment.*
