# Implementation Plan: Epic 5 – Inventory Management

**Branch**: `005-inventory-management` | **Date**: 2026-07-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-inventory-management/spec.md` (v1.1.0)
**Research**: [research.md](./research.md) | **Data Model**: [data-model.md](./data-model.md)

---

## Summary

Epic 5 implements the Inventory Management domain — the permanent Product Master and Inventory foundation of DevSphere ERP. All downstream modules (Purchase, Sales, Accounting, CRM, Reports, AI) depend on this Epic.

The implementation strategy is **vertical slice delivery** across 10 sequential phases, progressing from master data through inventory intelligence. The stock ledger uses a **hybrid architecture**: an immutable append-only ledger (source of truth) plus a materialised position table updated atomically within the same database transaction. Costing is implemented via the **Strategy Pattern** (WAC / FIFO), selectable per company. The architecture is designed for branch readiness, multi-currency readiness, and procurement metadata readiness without schema changes.

---

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI 0.115+, Pydantic v2, SQLAlchemy 2.x (async), Alembic, Next.js 15 (App Router), TailwindCSS, shadcn/ui
**Storage**: PostgreSQL 16 LTS (Docker Compose in dev; Neon PostgreSQL in production)
**Testing**: pytest + pytest-asyncio (backend), Jest + React Testing Library (frontend)
**Target Platform**: Linux server (Docker), browser (Next.js SSR + CSR)
**Project Type**: Web application — FastAPI backend + Next.js frontend
**Performance Goals**: Product search p95 < 500ms; stock query p95 < 300ms; bulk import 10k rows < 60s; all read endpoints p95 < 200ms
**Constraints**: company_id isolation on every query; soft-delete everywhere; immutable ledger (no UPDATE/DELETE on StockMovement); audit trail on every write
**Scale/Scope**: 500K products per company; 100K stock movements/day; 10K concurrent tenants

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Clean Architecture layering | PASS | Domain / Application / Infrastructure / API — zero cross-layer dependency violations |
| Multi-tenancy (company_id everywhere) | PASS | Repository base class enforces company_id on every query |
| Soft delete on all entities | PASS | is_deleted + deleted_at + deleted_by on every table |
| Audit trail completeness | PASS | Synchronous write within same DB transaction |
| Repository Pattern | PASS | No direct DB access from Application or Domain layers |
| DDD Aggregate Roots | PASS | 13 Aggregate Roots defined in data-model.md |
| Feature Flag strategy | PASS | Company-scoped DB table; defaults defined in code |
| No hardcoded secrets | PASS | All config via environment variables |
| No circular dependencies | PASS | Domain has zero framework dependencies |
| Immutable ledger | PASS | StockMovement: append-only; no UPDATE or DELETE operations |
| Backward compatibility | PASS | Branch/currency/procurement fields reserved as nullable |
| Epic 4 RBAC integration | PASS | Permission identifiers follow `module:resource:action` pattern |

**Constitution Check Result: ALL PASS — Phase 1 design approved to proceed.**

---

## Project Structure

### Documentation (this feature)

```text
specs/005-inventory-management/
├── spec.md              # Official SSOT — Epic 5 specification v1.1.0
├── plan.md              # This file — implementation blueprint
├── research.md          # Phase 0 — 10 architecture decisions resolved
├── data-model.md        # Phase 1 — 13 Aggregate Roots, state machines, audit fields
├── contracts/           # Phase 1 — OpenAPI contracts (generated in Phase 8)
│   ├── inventory-v1.yaml
│   └── events.md
├── checklists/
│   └── requirements.md  # Spec quality checklist — all 15 items PASS
└── tasks.md             # Phase 2 output — /sp.tasks command (not created here)
```

### Source Code (repository root)

```text
backend/
├── app/
│   └── modules/
│       └── inventory/
│           ├── domain/
│           │   ├── entities/         # Product, Variant, Warehouse, StockPosition, etc.
│           │   ├── value_objects/    # ProductBarcode, ProductImage, etc.
│           │   ├── events/           # 31 domain events
│           │   └── repositories/     # Repository interfaces (abstract)
│           ├── application/
│           │   ├── use_cases/        # One use case per business operation
│           │   ├── dtos/             # Request / Response DTOs
│           │   └── services/         # Application services, costing strategies
│           ├── infrastructure/
│           │   ├── models/           # SQLAlchemy ORM models
│           │   ├── repositories/     # Concrete repository implementations
│           │   ├── migrations/       # Alembic migration scripts
│           │   └── storage/          # S3 adapter for images
│           └── api/
│               ├── v1/
│               │   ├── routers/      # FastAPI routers per sub-domain
│               │   ├── schemas/      # Pydantic request/response schemas
│               │   └── dependencies/ # Auth, company context, pagination
│               └── middleware/       # Rate limiting, logging
│
frontend/
├── app/
│   └── (dashboard)/
│       └── inventory/
│           ├── products/             # Product management pages
│           ├── warehouses/           # Warehouse management pages
│           ├── stock/                # Stock operations pages
│           ├── adjustments/          # Inventory adjustment pages
│           └── reports/              # Inventory report pages
├── components/
│   └── inventory/                    # Reusable inventory UI components
└── lib/
    └── api/
        └── inventory/                # API client for inventory endpoints

tests/
├── unit/
│   └── inventory/                    # Domain + application layer unit tests
├── integration/
│   └── inventory/                    # Repository + service integration tests
└── api/
    └── inventory/                    # FastAPI endpoint tests
```

**Structure Decision**: Web application (Option 2) — FastAPI backend with modular Clean Architecture; Next.js App Router frontend. Inventory module is isolated within `backend/app/modules/inventory/` following the modular monolith pattern established in Epics 1–4.

---

## Complexity Tracking

| Decision | Why Needed | Simpler Alternative Rejected Because |
|----------|------------|--------------------------------------|
| Hybrid ledger (materialised + immutable) | p95 < 300ms at 100K movements/day | Pure ledger sum too slow; pure materialised risks inconsistency |
| Strategy Pattern for costing | WAC + FIFO both required per company | Single-method approach would require code changes to add FIFO or future methods |
| PostgreSQL FTS + pg_trgm | p95 < 500ms for 500K products | External search (Elasticsearch) premature; pure LIKE too slow at scale |
| Synchronous in-process event bus | Epic 5 has no downstream consumers yet | Async broker (Redis Streams) premature; no event consumers in scope |

---

## Implementation Strategy

Epic 5 implementation follows **10 sequential phases** organised by domain dependency order. Each phase is independently testable and deployable. No phase begins until the previous phase passes its exit criteria.

### Delivery Philosophy

1. **Vertical Slice First**: Each phase delivers a complete, working slice — domain entity → repository → application service → API endpoint → frontend component → tests
2. **Test-Driven Thinking**: Every use case is defined by its acceptance criteria before implementation begins
3. **Feature Toggle Wrapping**: All "Ready but Disabled" and "Future" features are gated behind company-scoped feature flags from day 1
4. **Immutability Enforcement**: StockMovement is append-only by design — no UPDATE or DELETE routes are ever created
5. **Atomic Consistency**: Every stock-modifying operation updates both the ledger and the materialised position in the same database transaction

### Phase Dependencies

```
Phase 1 (Master Data Foundation)
  └── Phase 2 (Product Master Core)
        └── Phase 3 (Warehouse Management)
              └── Phase 4 (Inventory Core & Stock Ledger)
                    ├── Phase 5 (Stock Operations)
                    │     └── Phase 6 (Inventory Intelligence)
                    └── Phase 7 (Reporting Foundation)
Phase 8 (Integration Foundation) — runs after Phase 4
Phase 9 (Performance & Optimisation) — runs after Phase 7
Phase 10 (Final Testing & Epic Review) — runs after all phases
```

---

## Implementation Phases

---

### Phase 1: Master Data Foundation

**Objective**: Establish the reusable master data entities that all inventory operations depend on.

**Scope**:
- Category tree (parent/child, soft-delete, deactivation guard)
- Brand management (code unique per company, logo via S3)
- Unit of Measure (5 types: UNIT, WEIGHT, VOLUME, LENGTH, AREA) + UOM Conversions
- Attribute Definitions + Attribute Sets
- Custom Field Definitions (entity-scoped)
- Reason Code registry (for Adjustment/Damage/Return)
- Tag management (shared across products)
- Company-scoped feature flag table + default registry
- FTS search indexes for all master data entities

**Prerequisites**: Epics 1–4 complete; PostgreSQL 16 with pg_trgm extension enabled

**Deliverables**:
- Domain entities: Category, Brand, UOM, UOMConversion, AttributeDefinition, AttributeSet, CustomFieldDefinition, ReasonCode, Tag
- Repository interfaces + concrete implementations for all master data
- Application services with full CRUD use cases
- API endpoints: `/api/v1/inventory/categories`, `/brands`, `/uom`, `/attributes`, `/attribute-sets`, `/custom-fields`, `/reason-codes`, `/tags`
- Feature flag service: `FeatureFlagService` with company-scoped resolution
- Frontend pages: Category, Brand, UOM, Attribute management
- Tests: Unit (domain invariants), integration (repository + service), API (all endpoints)
- Alembic migrations for all master data tables

**Acceptance Criteria**:
- [ ] Category tree supports unlimited depth with circular reference prevention
- [ ] Code uniqueness enforced per company for Category, Brand, UOM, ReasonCode
- [ ] Deactivation blocked when entity is referenced by Active products
- [ ] UOM conversion factor > 0 enforced
- [ ] Feature flags load correctly per company with fallback to system defaults
- [ ] All entities have company_id, soft-delete, audit fields
- [ ] FTS search returns results for Category, Brand in < 500ms

**Exit Criteria**: All unit, integration, and API tests pass; migrations run clean; Docker compose up with no errors

**Risks**:
- Category tree performance at deep nesting — mitigate with recursive CTE + depth limit (configurable, default 5)
- UOM conversion chain complexity — limit to direct conversions only in Epic 5; compound chains deferred

**Estimated Complexity**: Medium

---

### Phase 2: Product Master Core

**Objective**: Implement the Product entity and all its child entities, lifecycle management, and search.

**Scope**:
- Product aggregate (with Variants, Images, Barcodes, Tags, CustomFieldValues, SearchKeywords, InternalNotes)
- Product Types: STANDARD, VARIANT, SERVICE, BUNDLE (SERVICE + BUNDLE are feature-flagged for Epic 5)
- Product lifecycle state machine: DRAFT → ACTIVE → INACTIVE → DISCONTINUED → ARCHIVED
- SKU generation and uniqueness enforcement per company
- Barcode uniqueness enforcement per company
- Product images via S3 (primary + gallery; thumbnail generation on upload)
- Full-text search: tsvector on name, code, SKU, description, keywords; pg_trgm for partial/typo
- Bulk import (up to 10,000 rows via background task + job tracking)
- Excel/CSV export

**Prerequisites**: Phase 1 complete (Categories, Brands, UOM, Attributes, Tags available)

**Deliverables**:
- Domain entities: Product, ProductVariant, ProductImage, ProductBarcode, ProductTag, CustomFieldValue, InternalNote, SearchKeyword
- Product aggregate root with all invariants enforced
- Product repository with FTS search, barcode lookup, SKU lookup
- Application services: CreateProduct, UpdateProduct, ActivateProduct, DeactivateProduct, DiscontinueProduct, ArchiveProduct, SearchProducts, BulkImportProducts
- API endpoints: `/api/v1/inventory/products` (full CRUD + search + lifecycle transitions + import/export)
- Background task worker for bulk import with job status tracking
- S3 adapter for image upload/delete; thumbnail generation
- Frontend: Product list, Product detail, Product create/edit, Variant management, Bulk import UI
- Tests: All domain invariants, all lifecycle transitions, search accuracy, import validation

**Acceptance Criteria**:
- [ ] SKU unique per company enforced at domain level
- [ ] Barcode unique per company enforced at domain level
- [ ] Product cannot be activated without mandatory fields
- [ ] Status transitions follow defined state machine only
- [ ] Product search returns results in < 500ms (p95)
- [ ] Barcode/SKU exact lookup returns in < 100ms (p95)
- [ ] Bulk import of 10K rows completes in < 60 seconds
- [ ] Row-level errors collected and returned in import job result
- [ ] Images stored in S3 with thumbnail generated at upload
- [ ] All 13 procurement metadata fields present as nullable (reserved for future Epics)

**Exit Criteria**: All tests pass; product lifecycle fully exercisable via API; import tested with 10K row dataset; FTS search verified with realistic product data

**Risks**:
- Bulk import memory usage at 10K rows — mitigate with streaming CSV parser and chunked DB writes (batch size: 500)
- FTS index staleness on large datasets — update tsvector synchronously on write; schedule periodic refresh for production
- Variant explosion for high-attribute products — limit variant count per product (default 500; configurable)

**Estimated Complexity**: High

---

### Phase 3: Warehouse Management

**Objective**: Implement multi-warehouse support, warehouse locations, and the foundation for stock operations.

**Scope**:
- Warehouse entity with Types: MAIN, BRANCH, TRANSIT, VIRTUAL, CONSIGNMENT
- Warehouse Locations (aisle/zone/shelf groupings)
- Warehouse status lifecycle: ACTIVE → INACTIVE → ARCHIVED (with non-zero stock guard)
- Multi-warehouse query patterns (cross-warehouse stock summary)
- Branch readiness: `branch_id` nullable field reserved on Warehouse
- Warehouse permission assignment (per Epic 4 RBAC)

**Prerequisites**: Phase 1 complete

**Deliverables**:
- Domain entities: Warehouse, WarehouseLocation
- Warehouse repository with full CRUD + soft-delete
- Application services: CreateWarehouse, UpdateWarehouse, ActivateWarehouse, ArchiveWarehouse, ManageWarehouseLocations
- API endpoints: `/api/v1/inventory/warehouses`, `/warehouses/{id}/locations`
- Permission guard: warehouse-level access control per RBAC role
- Frontend: Warehouse list, Warehouse detail, Location management
- Tests: All warehouse invariants, deactivation guard, permission enforcement

**Acceptance Criteria**:
- [ ] Code unique per company enforced
- [ ] Warehouse cannot be archived when non-zero stock exists
- [ ] `branch_id` field present as nullable (reserved for Branch Management epic)
- [ ] Warehouse locations belong to exactly one warehouse
- [ ] Multi-warehouse stock query works correctly across all company warehouses
- [ ] Warehouse RBAC permissions enforced correctly per role

**Exit Criteria**: All tests pass; multi-warehouse scenario tested end-to-end; branch_id nullable field confirmed in migration

**Risks**:
- Warehouse permission complexity at high warehouse count — design permission check as warehouse-set query, not per-warehouse loop

**Estimated Complexity**: Medium

---

### Phase 4: Inventory Core & Stock Ledger

**Objective**: Implement the stock position system and the immutable stock movement ledger — the heart of Epic 5.

**Scope**:
- StockPosition aggregate (materialised current/reserved/damaged/available quantities + cost)
- StockMovement aggregate (immutable ledger, append-only)
- Opening stock entry workflow (OPENING movement type)
- Costing engine: WAC strategy + FIFO strategy (Strategy Pattern)
- WAC: recalculates and stores unit cost on every stock-in movement
- FIFO: maintains cost queue per product per warehouse; pops oldest layer on stock-out
- Atomic write guarantee: ledger entry + position update in single DB transaction
- Currency readiness: all monetary fields carry `currency_code` (Base Currency in Epic 5)
- Inventory Snapshot: immutable point-in-time snapshot of all positions (with snapshot lines)
- Negative stock policy enforcement: STRICT / WARN / SILENT (company-level setting)

**Prerequisites**: Phases 1–3 complete; costing strategy selected per company

**Deliverables**:
- Domain entities: StockPosition, StockMovement, InventorySnapshot, InventorySnapshotLine
- CostingStrategy interface: WACCostingStrategy, FIFOCostingStrategy
- Ledger service: atomic write of (movement + position update) in one transaction
- Snapshot service: generate and store immutable inventory snapshot
- Repository: StockPositionRepository (upsert-or-create pattern), StockMovementRepository (append-only), SnapshotRepository
- API endpoints: `/api/v1/inventory/stock-positions`, `/stock-movements`, `/snapshots`
- Frontend: Stock overview (per product × warehouse), Ledger view (read-only), Snapshot management
- Tests: Atomic write verified (transaction rollback test), WAC calculation accuracy, FIFO queue correctness, negative stock enforcement

**Acceptance Criteria**:
- [ ] StockMovement has NO update or delete endpoints
- [ ] Ledger entry + position update committed atomically (rollback test passes)
- [ ] WAC unit cost recalculated correctly on every stock-in
- [ ] FIFO cost queue pops oldest layer correctly on stock-out
- [ ] available_quantity = current − reserved − damaged (derived, never stored independently)
- [ ] Negative stock blocked when policy is STRICT
- [ ] Inventory Snapshot is immutable once generated
- [ ] All monetary fields carry `currency_code` field
- [ ] Stock position query (single product × warehouse) returns in < 300ms (p95)

**Exit Criteria**: All tests pass; WAC and FIFO costing verified with known datasets; atomic write verified via DB transaction rollback test; snapshot generation tested with multi-product, multi-warehouse data

**Risks**:
- FIFO cost layer management under concurrent writes — use row-level locking (SELECT FOR UPDATE) on FIFO queue entries
- WAC precision under float arithmetic — use Python Decimal type for all cost calculations; store as NUMERIC in PostgreSQL
- Transaction deadlock under high concurrency — access StockPosition rows in deterministic order (by product_id then warehouse_id)

**Estimated Complexity**: High

---

### Phase 5: Stock Operations

**Objective**: Implement all active stock-changing workflows on top of the Phase 4 ledger.

**Scope**:
- Inventory Adjustment workflow: DRAFT → PENDING_APPROVAL → APPROVED / REJECTED (or DRAFT → APPROVED if flag disabled)
- Stock Transfer workflow: DRAFT → IN_TRANSIT → COMPLETED / CANCELLED (with reversal movement on IN_TRANSIT cancel)
- Stock Reservation: Reserve/release quantity for downstream modules (Sales, Production)
- Return Inbound / Return Outbound movement types
- Damaged stock classification
- Adjustment approval feature flag (`inventory.adjustment_approval`)

**Prerequisites**: Phase 4 complete

**Deliverables**:
- Domain entities: InventoryAdjustment, StockTransfer, StockTransferLine
- Application services: SubmitAdjustment, ApproveAdjustment, RejectAdjustment, CreateTransfer, DispatchTransfer, ReceiveTransfer, CancelTransfer, ReserveStock, ReleaseReservation
- State machine enforcement for Adjustment and Transfer in domain layer
- API endpoints: `/api/v1/inventory/adjustments`, `/stock-transfers`, `/reservations`
- Frontend: Adjustment create/approve/reject flow, Transfer create/dispatch/receive flow
- Tests: All state machine transitions, cancellation reversal, reservation/release cycle, approval workflow with and without flag

**Acceptance Criteria**:
- [ ] Adjustment state machine enforces DRAFT → PENDING_APPROVAL → APPROVED/REJECTED only
- [ ] Adjustment approval bypass works when `inventory.adjustment_approval` flag is disabled
- [ ] Transfer cancellation from IN_TRANSIT creates reversal StockMovement at source warehouse
- [ ] Stock reservation does not exceed available_quantity
- [ ] Stock release correctly decrements reserved_quantity
- [ ] Reason code required on all adjustments
- [ ] Submitter and approver recorded on adjustment (cannot be same user)
- [ ] All adjustment and transfer operations create immutable ledger entries

**Exit Criteria**: All state machine transitions tested; cancellation + reversal verified; approval workflow tested with flag on and off

**Risks**:
- Concurrent transfers reducing same product stock — mitigate with SELECT FOR UPDATE on StockPosition
- Approval workflow race (double approval) — use optimistic lock (version field) on InventoryAdjustment

**Estimated Complexity**: High

---

### Phase 6: Inventory Intelligence & Alerts

**Objective**: Implement reorder rules, low stock alerts, and overstock alerts.

**Scope**:
- ReorderRule entity: per-product / per-warehouse rules with reorder_level and reorder_quantity
- LowStockAlert: raised when available_quantity ≤ safety_stock or reorder_level
- OutOfStockAlert: raised when available_quantity = 0
- OverstockAlert: raised when current_quantity ≥ maximum_stock (feature-flagged: `inventory.overstock_alerts`)
- Alert lifecycle: OPEN → ACKNOWLEDGED → RESOLVED (auto-resolve on stock replenishment)
- Alert evaluation: triggered synchronously on every stock-modifying write
- Reorder suggestion generation (creates a suggestion record, not an actual purchase order)
- Notification hooks: in-app notification on alert creation (email/SMS are deferred feature flags)

**Prerequisites**: Phase 4 complete (stock positions available)

**Deliverables**:
- Domain entities: ReorderRule, LowStockAlert
- Alert evaluation service: invoked within stock write transaction
- Reorder suggestion service
- Notification dispatch (in-app only for Epic 5)
- API endpoints: `/api/v1/inventory/reorder-rules`, `/alerts`, `/suggestions`
- Frontend: Alert dashboard, Reorder rule management, Suggestion list
- Tests: Alert raised correctly at each threshold, auto-resolve on restock, overstock alert behind feature flag

**Acceptance Criteria**:
- [ ] Low stock alert created when available_quantity ≤ safety_stock
- [ ] Out-of-stock alert created when available_quantity = 0
- [ ] Overstock alert only fires when `inventory.overstock_alerts` flag is enabled
- [ ] Alert auto-resolves when stock is replenished above threshold
- [ ] Reorder suggestion generated when reorder_level breached
- [ ] In-app notification dispatched on alert creation
- [ ] Alerts filtered by warehouse, product, alert type via API

**Exit Criteria**: All alert scenarios tested; auto-resolve verified; feature flag gate tested on/off

**Risks**:
- Alert storm under rapid stock fluctuations — deduplicate: only create new alert if no OPEN alert of same type exists for same product × warehouse

**Estimated Complexity**: Medium

---

### Phase 7: Reporting Foundation

**Objective**: Implement the 14 standard inventory reports and 10 KPI calculations defined in the spec.

**Scope**:
- Report 1: Inventory Summary (per warehouse, per category, per brand)
- Report 2: Stock Ledger (all movements for product × warehouse × date range)
- Report 3: Inventory Valuation Report (WAC/FIFO value per product)
- Report 4: Stock Position Report (current/reserved/damaged/available per product × warehouse)
- Report 5: Warehouse Utilisation Report
- Report 6: Category Performance Report
- Report 7: Brand Report
- Report 8: Dead Stock Report (no movement in N days; configurable)
- Report 9: Fast-Moving Products Report
- Report 10: Slow-Moving Products Report
- Report 11: Stock Aging Report (age of current stock by purchase date)
- Report 12: Inventory Adjustment Report
- Report 13: Stock Transfer Report
- Report 14: Inventory Trend Analysis
- KPI Dashboard: 10 KPIs (Inventory Turnover, Average Inventory, Inventory Accuracy, Dead Stock %, Stock Accuracy %, Warehouse Efficiency, Inventory Value, Reorder Frequency, Stockout Rate, Overstock Rate)
- CSV/Excel export for all reports

**Prerequisites**: Phases 4–6 complete (stock data available)

**Deliverables**:
- Report query services (read-only, no domain mutations)
- Report API endpoints: `/api/v1/inventory/reports/{report_type}`
- KPI API endpoint: `/api/v1/inventory/kpis`
- Export service: CSV + Excel generation
- Frontend: Report pages with filters, charts, and export buttons
- Tests: Report accuracy against known datasets; KPI formula verification

**Acceptance Criteria**:
- [ ] All 14 reports return data within p95 < 500ms for typical dataset sizes
- [ ] All 10 KPIs calculated correctly against known test datasets
- [ ] Stock Ledger report includes all movement types with correct direction
- [ ] Inventory Valuation Report reflects the company's selected costing method (WAC/FIFO)
- [ ] Dead Stock report correctly identifies products with no movement in N days
- [ ] CSV and Excel export work for all reports
- [ ] All reports are company-scoped (no cross-tenant data leakage)

**Exit Criteria**: All reports tested with realistic dataset; KPI formulas verified; export tested; tenant isolation verified

**Risks**:
- Valuation report performance at 500K products — use materialised summary table; refresh on stock write; full recalculation on demand

**Estimated Complexity**: Medium

---

### Phase 8: Integration Foundation

**Objective**: Establish the event bus, domain events, and scanner/external device API readiness.

**Scope**:
- Domain event publishing for all 31 events defined in spec §31
- Synchronous in-process event bus with async-ready interface (EventBus abstraction)
- Event serialisation to JSON (all events serialisable from day 1)
- Barcode scanner API endpoint: resolve barcode → product (for POS/scanner integration)
- QR code lookup endpoint
- Label print data endpoint (returns product label data; printer rendering is client-side)
- OpenAPI contract generation: `contracts/inventory-v1.yaml`
- Domain event contract documentation: `contracts/events.md`

**Prerequisites**: Phases 4–5 complete (all stock events available)

**Deliverables**:
- EventBus interface + InProcessEventBus implementation
- Domain event classes for all 31 events (serialisable to JSON)
- Event subscriber registry
- Scanner/lookup API endpoints: `/api/v1/inventory/lookup/barcode/{code}`, `/lookup/sku/{sku}`
- OpenAPI specification: `specs/005-inventory-management/contracts/inventory-v1.yaml`
- Event contract documentation: `specs/005-inventory-management/contracts/events.md`
- Tests: Event firing verified for all write operations; barcode lookup accuracy

**Acceptance Criteria**:
- [ ] All 31 domain events are published on the correct triggers
- [ ] Events are JSON-serialisable (verified in tests)
- [ ] EventBus interface is abstract — concrete transport (in-process vs Redis Streams) is swappable without domain changes
- [ ] Barcode lookup returns product in < 100ms (p95)
- [ ] OpenAPI contract is complete and accurate

**Exit Criteria**: All 31 events verified; contract generated; barcode lookup tested

**Risks**:
- Event contract breaking changes — establish event versioning pattern from day 1 (include `event_version` field on all events)

**Estimated Complexity**: Medium

---

### Phase 9: Performance & Optimisation

**Objective**: Validate and tune all performance targets from the spec before final review.

**Scope**:
- Database index audit and optimisation for all inventory tables
- PostgreSQL FTS index validation at scale (simulate 500K product dataset)
- pg_trgm similarity search tuning
- N+1 query elimination audit (all list endpoints)
- Connection pool configuration review
- Slow query identification and remediation
- Response caching strategy for master data (Categories, Brands, UOM, Attributes)
- Inventory summary caching (Redis-ready architecture; Redis not required in Epic 5)
- Load simulation: 100K stock movements/day throughput test
- p95 latency verification for all specified performance targets

**Prerequisites**: Phases 1–8 complete

**Deliverables**:
- Index audit report (documented findings)
- Performance test results against all spec §42 targets
- Query optimisations applied
- Caching layer designed (implementation deferred to cache-enabling Epic if Redis not yet available)
- Load test results

**Acceptance Criteria**:
- [ ] Product search p95 < 500ms at 500K products
- [ ] Stock position query p95 < 300ms at 100K daily movements
- [ ] Bulk import 10K rows < 60 seconds
- [ ] All read endpoints p95 < 200ms
- [ ] No N+1 queries on any list endpoint
- [ ] No slow queries (> 1 second) under typical load

**Exit Criteria**: All spec performance targets met; load test passed; slow query log clean

**Risks**:
- FTS performance degradation at extreme scale — implement hybrid index (tsvector + B-tree on code/SKU) to isolate slow queries
- Materialised position lock contention under concurrent writes — measure and set lock timeout; escalate if contention rate > 1%

**Estimated Complexity**: Medium

---

### Phase 10: Final Testing & Epic Review

**Objective**: Comprehensive validation, documentation completion, and Epic closure.

**Scope**:
- Full end-to-end scenario testing (all 7 business workflows from spec §20)
- Tenant isolation verification (cross-company data leakage test)
- Permission matrix validation (all 10 roles × all inventory operations)
- Security review: injection, authorisation, data exposure
- Docker Compose production-readiness verification
- Epic Completion Criteria verification (all 15 gates from spec §57)
- Documentation review: quickstart.md, contracts/, data-model.md all current
- PHR creation + branch PR preparation

**Prerequisites**: All Phases 1–9 complete and passing

**Deliverables**:
- End-to-end test suite covering all business workflows
- Tenant isolation test results
- Permission matrix test results
- Security review findings (and remediations if any)
- Docker verification result
- Epic 5 Completion Checklist (all 15 gates verified)
- `quickstart.md` — developer onboarding guide for inventory module
- PR for `005-inventory-management` → `main`

**Acceptance Criteria**:
- [ ] All 7 business workflows complete end-to-end without errors
- [ ] Cross-company data leakage: zero incidents across all test cases
- [ ] All 10 RBAC roles operate with correct permission boundaries
- [ ] Docker Compose up → migrate → seed → API smoke test: all pass
- [ ] All 15 Epic Completion Criteria from spec §57 verified PASS
- [ ] Zero Critical bugs open

**Exit Criteria**: All 15 Epic Completion Criteria PASS; PR approved; branch merged to main

**Estimated Complexity**: Medium

---

## Technical Architecture Plan

### Domain Layer Design

The domain layer has zero dependencies on FastAPI, SQLAlchemy, or any external framework. It contains:

- **Entities**: Stateful objects with identity (Product, Warehouse, StockPosition, etc.)
- **Value Objects**: Immutable, identity-less objects (ProductBarcode, ProductImage, etc.)
- **Aggregate Roots**: Enforce invariants and own child entities (13 aggregate roots per data-model.md)
- **Domain Events**: Serialisable records of significant business occurrences (31 events per spec §31)
- **Repository Interfaces**: Abstract contracts that the infrastructure layer implements

**Key Invariants enforced at Domain Layer**:
- SKU unique per company (enforced by Product aggregate)
- Barcode unique per company (enforced by Product aggregate)
- Costing strategy is immutable mid-period (REVALUATION event required)
- StockMovement is append-only (no update/delete methods exist on entity)
- StockPosition.available_quantity ≥ 0 when STRICT negative stock policy active

### Application Layer Design

The application layer orchestrates domain operations. It:

- Contains one Use Case class per business operation
- Receives DTOs (not domain entities) from the API layer
- Calls repository interfaces (not concrete implementations)
- Publishes domain events via the EventBus interface
- Applies the costing strategy (loaded from company context)
- Manages database transaction boundaries
- Never accesses PostgreSQL directly

**Key Application Services**:
- `ProductService`: orchestrates product lifecycle and search
- `StockLedgerService`: orchestrates the atomic ledger + position write
- `CostingService`: selects and applies WAC or FIFO strategy per company
- `AdjustmentService`: orchestrates adjustment approval workflow
- `TransferService`: orchestrates two-step stock transfer
- `AlertService`: evaluates thresholds and creates alerts
- `FeatureFlagService`: resolves company-scoped flags with system defaults

### Repository Layer Design

The base repository class enforces company_id on every query. No repository method exists without company_id as a mandatory first-class argument.

**Key patterns**:
- `BaseRepository(company_id)` — all repositories inherit from this
- `StockMovementRepository` — append-only; INSERT only; no update/delete methods
- `StockPositionRepository` — upsert pattern; position record created on first stock movement
- `FIFOCostLayerRepository` — ordered queue per product × warehouse; pop oldest on stock-out

### Validation Layer Design

Validation operates at three layers:

1. **API Layer (Pydantic v2)**: Request schema validation — type, format, required fields
2. **Application Layer**: Business rule validation — e.g., "adjustment quantity > 0", "reason code required"
3. **Domain Layer**: Invariant enforcement — e.g., "SKU must be unique per company", "status transition is valid"

### Authorization Design

Authorization follows the Epic 4 RBAC model with inventory-specific permission identifiers:

| Module | Resource | Actions |
|--------|----------|---------|
| inventory | product | create, read, update, delete, activate, archive, import, export |
| inventory | category | create, read, update, delete |
| inventory | brand | create, read, update, delete |
| inventory | warehouse | create, read, update, archive |
| inventory | stock | read, adjust, transfer, reserve |
| inventory | adjustment | create, approve, reject |
| inventory | report | read, export |
| inventory | alert | read, acknowledge |
| inventory | snapshot | create, read |

### Audit Logging Design

Every write operation produces an audit record within the same database transaction. The audit schema follows the pattern established in Epics 2–4:

- Table: `audit_logs` (shared schema)
- Fields: `entity_type`, `entity_id`, `action`, `old_value` (JSON), `new_value` (JSON), `user_id`, `company_id`, `performed_at`
- StockMovement is itself an audit trail — no separate audit record is created for stock movements

### Feature Toggle Design

Feature flags resolve in order: company-level override → system default

| Flag Key | Default | Controls |
|----------|---------|---------|
| `inventory.adjustment_approval` | false | Requires approval workflow for adjustments |
| `inventory.overstock_alerts` | false | Enables overstock alert creation |
| `inventory.negative_stock_policy` | STRICT | STRICT / WARN / SILENT per company |
| `inventory.service_products` | false | Enables SERVICE product type |
| `inventory.bundle_products` | false | Enables BUNDLE product type |
| `inventory.fifo_costing` | false | Selects FIFO costing (default: WAC) |

---

## Data Strategy

### Ownership Map

| Data Domain | Owner in Epic 5 | Future Owner |
|-------------|----------------|--------------|
| Product Master | Epic 5 (Inventory) | Permanent — never transferred |
| Warehouse Master | Epic 5 (Inventory) | Permanent — never transferred |
| Stock Ledger | Epic 5 (Inventory) | Permanent — never transferred |
| Stock Position | Epic 5 (Inventory) | Permanent — never transferred |
| Inventory Adjustments | Epic 5 (Inventory) | Permanent — never transferred |
| Stock Transfers | Epic 5 (Inventory) | Permanent — never transferred |
| Procurement Metadata | Epic 5 (reserved fields) | Epic 6 (Purchase) will populate |
| Purchase Receipts (PURCHASE_RECEIPT) | Epic 5 (movement type reserved) | Epic 6 (Purchase) will create these movements |
| Sale Dispatches (SALE_DISPATCH) | Epic 5 (movement type reserved) | Epic 7 (Sales) will create these movements |
| Inventory Valuation (accounting view) | Epic 5 (unit_cost + currency) | Epic 8 (Accounting) will consume |
| Branch Hierarchy | Epic 5 (branch_id nullable field) | Branch Management Epic will populate |
| Currency Exchange Rates | Epic 5 (currency_code field) | Accounting/International Epic will activate |

### Immutability Guarantee

The StockMovement table is the permanent stock audit trail. It will never be modified or deleted. All future modules (Purchase, Sales) that create stock movements will INSERT new records — they will never UPDATE or DELETE existing records.

### Migration Strategy

- All Alembic migrations are additive in Phase 1
- No destructive migrations in Epic 5
- Future Epics will ADD columns (branch_id, lot_id, serial_number) — they will NOT rename or remove Epic 5 columns
- The `currency_code` field is populated at write time from company's base_currency — no migration needed when multi-currency is activated

---

## Dependency Planning

### Internal Dependencies (within Epic 5)

| Phase | Depends On |
|-------|-----------|
| Phase 2 | Phase 1 (Categories, Brands, UOM, Attributes, Feature Flags) |
| Phase 3 | Phase 1 (Company context, Audit fields) |
| Phase 4 | Phases 1, 2, 3 |
| Phase 5 | Phase 4 |
| Phase 6 | Phase 4 |
| Phase 7 | Phases 4, 5, 6 |
| Phase 8 | Phases 4, 5 |
| Phase 9 | All phases |
| Phase 10 | All phases |

### Cross-Epic Dependencies (upstream — already complete)

| Epic | Component Needed | Status |
|------|-----------------|--------|
| Epic 1 | FastAPI app scaffold, SQLAlchemy setup, Docker Compose, Alembic | Complete |
| Epic 2 | JWT authentication, auth middleware, user context extraction | Complete |
| Epic 3 | Company context resolution, S3 adapter, company settings | Complete |
| Epic 4 | RBAC permission system, role resolver, permission checker middleware | Complete |

### Cross-Epic Dependencies (downstream — to be provided by Epic 5)

| Future Epic | What Epic 5 Provides |
|------------|---------------------|
| Epic 6 (Purchase) | Product Master stable API, StockMovement INSERT interface (PURCHASE_RECEIPT), 13 procurement metadata fields |
| Epic 7 (Sales) | Product Master stable API, StockMovement INSERT interface (SALE_DISPATCH), Stock Reservation/Release API |
| Epic 8 (Accounting) | Inventory Valuation API, StockPosition with unit_cost + currency_code, COGS calculation data |
| Epic 9 (CRM) | Product Master read API (product details for quotes, orders) |
| Reports Epic | All inventory read APIs (reports, KPIs, snapshots) |
| AI Epic | Historical StockMovement data for demand forecasting |

### Blocked / Deferred Items

| Item | Status | Activation |
|------|--------|-----------|
| Branch Management | Deferred — branch_id reserved as nullable | Branch Management Epic |
| Multi-Currency | Deferred — currency_code field present, conversion logic absent | Accounting/International Epic |
| Physical Count / Cycle Count | Deferred | Inventory Intelligence Phase 2 |
| Inventory Freeze | Deferred | Inventory Intelligence Phase 2 |
| Lot/Batch Tracking | Deferred — lot_id reserved as nullable | Traceability Module |
| Serial Number Tracking | Deferred — serial_number reserved as nullable | Traceability Module |
| Bin/Rack Management | Deferred — bin_id reserved as nullable | Warehouse Phase 2 |
| Email/SMS/WhatsApp Notifications | Deferred — notification service to be established | Notification Module |
| Elasticsearch/OpenSearch | Deferred — PostgreSQL FTS sufficient at current scale | Future optimisation if > 200K products |

---

## Testing Strategy

### Unit Testing

**Scope**: Domain entities, value objects, aggregate root invariants, costing strategies, state machines

**Approach**:
- Zero infrastructure dependencies — all domain tests run in-memory
- One test class per aggregate root
- Test every valid state transition
- Test every invalid state transition (expect domain exception)
- Test WAC formula with known values (e.g., 10 units @ $5 + 20 units @ $8 = WAC $7)
- Test FIFO queue ordering with known datasets

**Coverage Target**: > 95% domain layer

### Integration Testing

**Scope**: Repository implementations, database queries, transaction atomicity

**Approach**:
- Use test database (PostgreSQL in Docker)
- Test every repository method with real SQL
- Test atomic write: verify rollback leaves both ledger and position unchanged
- Test company_id isolation: verify repository returns no data for wrong company_id
- Test soft-delete: verify deleted records excluded from all queries

**Coverage Target**: > 90% repository layer

### API Testing

**Scope**: All FastAPI endpoints, request/response schemas, auth enforcement

**Approach**:
- FastAPI TestClient for all endpoints
- Test authenticated + unauthenticated requests
- Test permission enforcement for each operation × each role
- Test pagination, filtering, sorting
- Test error responses (400, 401, 403, 404, 422)

**Coverage Target**: > 90% API layer

### Authorization Testing

**Scope**: Permission matrix from spec §26 — all 10 roles × all inventory operations

**Approach**: One test matrix covering all role × operation combinations; assert allowed/denied for each

### Tenant Isolation Testing

**Scope**: Verify that no inventory operation can return or modify data belonging to a different company

**Approach**:
- Create two companies with overlapping product codes and SKUs
- Execute every read and write operation as Company A
- Verify zero data from Company B is returned or affected

### Performance Testing

**Scope**: All spec §42 performance targets

**Approach**:
- Seed database with 500K products (using test data generator)
- Run product search benchmark against all search types
- Run stock position query benchmark at 100K movements/day
- Run bulk import with 10K row CSV

**Tools**: pytest-benchmark (backend), k6 or Locust (load testing)

### Docker Validation

All tests must pass in Docker environment. CI pipeline runs:
1. `docker compose up -d`
2. `alembic upgrade head`
3. `pytest --cov` (full suite)
4. `docker compose down`

---

## Quality Gates

Quality gates are mandatory checkpoints. No subsequent phase begins until the gate passes.

| Gate | Trigger | Criteria |
|------|---------|---------|
| G1: Architecture Review | Before Phase 1 implementation | Clean Architecture layers verified; no cross-layer violations |
| G2: Phase 1 Exit | After Phase 1 complete | All master data tests pass; migrations clean; Docker verified |
| G3: Phase 2 Exit | After Phase 2 complete | All product tests pass; FTS search verified; bulk import tested |
| G4: Phase 4 Exit | After Phase 4 complete | Atomic write verified; costing accuracy verified; no ledger mutation endpoints exist |
| G5: Phase 5 Exit | After Phase 5 complete | All state machine transitions tested; reversal movements verified |
| G6: Phase 7 Exit | After Phase 7 complete | All 14 reports return correct data; all 10 KPIs verified |
| G7: Performance Gate | Phase 9 | All p95 targets met; no slow queries; N+1 queries eliminated |
| G8: Security Review | Phase 10 | No injection vulnerabilities; auth enforced on all endpoints; no data leakage |
| G9: Tenant Isolation | Phase 10 | Zero cross-company data incidents |
| G10: Epic Completion | Phase 10 | All 15 spec §57 gates PASS |

---

## Risk Management

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| FIFO cost queue concurrency (double-pop) | Medium | High | SELECT FOR UPDATE on FIFO queue; integration test with concurrent writes |
| WAC decimal precision drift | Low | High | Python Decimal; PostgreSQL NUMERIC; never use float for monetary values |
| FTS performance at 500K products | Medium | Medium | pg_trgm + GIN index; benchmark during Phase 2; fallback to Elasticsearch if needed |
| Bulk import memory at 10K rows | Low | Medium | Streaming parser; batch 500; monitor RSS during Phase 2 testing |
| Stock position lock contention | Medium | Medium | Deterministic lock order; timeout; measure contention rate in Phase 9 |

### Architecture Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| Event interface coupling | Low | High | EventBus abstraction in domain — transport is infrastructure detail |
| Costing method change mid-period | Low | Critical | Block costing change at application layer; require REVALUATION event |
| Procurement metadata fields overwritten by Epic 6 | Low | Medium | Define explicit Epic 5 → Epic 6 ownership handover protocol in data-model.md |

### Business Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| Negative stock allowed in error | Low | High | Default policy is STRICT; must be explicitly changed by Company Admin |
| Audit trail gaps | Low | Critical | Audit write is synchronous in same transaction; cannot be skipped |
| Cross-tenant data exposure | Low | Critical | Repository base class enforces company_id; tenant isolation test suite |

### Future Compatibility Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| Branch activation requires schema change | Low | High | branch_id nullable field reserved in Warehouse from day 1 |
| Multi-currency requires ledger redesign | Low | High | currency_code on all monetary fields from day 1 |
| Serial/Lot tracking disrupts movement model | Low | High | serial_number + lot_id reserved as nullable on StockMovement from day 1 |

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|------------|
| Unit Test Coverage — Domain Layer | > 95% | pytest-cov |
| Unit Test Coverage — Application Layer | > 90% | pytest-cov |
| Integration Test Coverage — Repository Layer | > 90% | pytest-cov |
| API Test Coverage — All Endpoints | > 90% | pytest-cov |
| Product Search p95 Latency | < 500ms | pytest-benchmark |
| Stock Position Query p95 Latency | < 300ms | pytest-benchmark |
| Bulk Import 10K Rows | < 60 seconds | timed test |
| All Read Endpoints p95 | < 200ms | pytest-benchmark |
| Critical Bugs at Epic Close | 0 | bug tracker |
| Epic Completion Criteria | 15/15 PASS | manual checklist |
| Docker Compose Verification | PASS | CI pipeline |
| Tenant Isolation Incidents | 0 | isolation test suite |
| Permission Matrix Test Coverage | 100% of roles × operations | test matrix |

---

## Implementation Roadmap

```
Approved Spec (v1.1.0)
         │
         ▼
Architecture Research (research.md) ✓
         │
         ▼
Data Model & Contracts (data-model.md) ✓
         │
         ▼
Implementation Plan (this document) ✓
         │
         ▼
Tasks Breakdown (/sp.tasks)
         │
         ▼
   ┌─────────────────┐
   │ Phase 1         │  Master Data Foundation
   │ G2 Exit Gate    │
   └────────┬────────┘
            │
   ┌─────────────────┐
   │ Phase 2         │  Product Master Core
   │ G3 Exit Gate    │
   └────────┬────────┘
            │
   ┌─────────────────┐
   │ Phase 3         │  Warehouse Management
   └────────┬────────┘
            │
   ┌─────────────────┐
   │ Phase 4         │  Inventory Core & Stock Ledger
   │ G4 Exit Gate    │
   └────────┬────────┘
            │
   ┌─────────────────┐
   │ Phase 5         │  Stock Operations
   │ G5 Exit Gate    │
   └────────┬────────┘
            │
       ┌────┴────┐
       │         │
  Phase 6    Phase 7
  Alerts    Reporting
       │         │
  Phase 8    Phase 9
  Events    Performance
       │    G7 Gate  │
       └────┬────────┘
            │
   ┌─────────────────┐
   │ Phase 10        │  Final Testing & Epic Review
   │ G8–G10 Gates    │
   └────────┬────────┘
            │
   ┌─────────────────┐
   │ Epic 5          │  COMPLETE
   │ PR Merged       │
   └─────────────────┘
            │
            ▼
   Epic 6 (Purchase) — enabled by Product Master + Ledger
   Epic 7 (Sales)    — enabled by Product Master + Stock Reservation
   Epic 8 (Accounting) — enabled by Valuation + Currency fields
```

---

## Pre-Implementation Checklist

Before generating tasks.md (via `/sp.tasks`), verify:

- [ ] `specs/005-inventory-management/spec.md` (v1.1.0) reviewed and approved
- [ ] `specs/005-inventory-management/research.md` — all 10 decisions resolved
- [ ] `specs/005-inventory-management/data-model.md` — all 13 aggregate roots defined
- [ ] `specs/005-inventory-management/plan.md` (this file) — reviewed and approved
- [ ] Architecture Review Gate G1 passed
- [ ] Epic 4 (Users & Roles) fully merged and stable on main

**When all items are checked: proceed with `/sp.tasks` to generate the actionable task breakdown.**
