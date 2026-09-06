# Implementation Plan: Epic 6 – Purchase Management

**Branch**: `006-purchase-management` | **Date**: 2026-07-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-purchase-management/spec.md` (v1.0)
**Research**: [research.md](./research.md) | **Data Model**: [data-model.md](./data-model.md)

---

## Summary

Epic 6 implements the **complete Procurement Domain** — the end-to-end capability by which organisations source, acquire, and receive goods and services from external suppliers under full governance, cost control, and audit accountability.

The implementation strategy is **vertical slice delivery** across 12 sequential phases, progressing from module scaffolding through supplier master, procurement workflow, purchase orders, goods receiving, vendor returns, purchase costing, and intelligence. Every phase is independently testable. No phase begins until the previous phase passes its exit criteria.

The architecture mirrors Epic 5 (Inventory): Clean Architecture with strict layer separation, Repository Pattern with mandatory `company_id` isolation, domain events via `InProcessEventBus`, and feature flags for all optional capabilities. The critical integration contract is the **Goods Receipt → Inventory Stock Update** link, which calls Epic 5's stock movement interface on GR confirmation.

The approval engine is the most architecturally significant new component: a configurable multi-level workflow that serves both Purchase Requests and Purchase Orders. It is implemented as a general-purpose approval sub-system within the purchase module, designed to be reusable for future PO amendments and RMA approvals.

---

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI 0.115+, Pydantic v2, SQLAlchemy 2.x (async), Alembic, Next.js 15 (App Router), TailwindCSS, shadcn/ui
**Storage**: PostgreSQL 16 LTS (Docker Compose in dev; Neon PostgreSQL in production)
**Testing**: pytest + pytest-asyncio (backend), Jest + React Testing Library (frontend)
**Target Platform**: Linux server (Docker), browser (Next.js SSR + CSR)
**Project Type**: Web application — FastAPI backend + Next.js frontend
**Performance Goals**: Supplier search p95 < 300ms; PO list p95 < 500ms; GR confirmation < 2s; report generation < 5s; all standard reads p95 < 200ms
**Constraints**: company_id isolation on every query; soft-delete everywhere; approved POs immutable without amendment; GRs immutable once confirmed; audit trail on every write; self-approval prevention
**Scale/Scope**: 100,000 suppliers per company; 500,000 POs/year per company; 1,000,000 GRs/year; 10,000 concurrent tenants

---

## Constitution Check

*GATE: Must pass before Phase 1 implementation. Re-checked after design phase.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Clean Architecture layering | PASS | Domain / Application / Infrastructure / API — zero cross-layer dependency violations |
| Multi-tenancy (company_id everywhere) | PASS | Repository base class enforces company_id on every query, consistent with Epics 2–5 |
| Soft delete on all entities | PASS | is_deleted + deleted_at + deleted_by on every purchase table |
| Audit trail completeness | PASS | Synchronous write within same DB transaction on every state change |
| Repository Pattern | PASS | No direct DB access from Application or Domain layers |
| DDD Aggregate Roots | PASS | 6 Aggregate Roots: Supplier, PurchaseRequest, PurchaseOrder, GoodsReceipt, VendorReturn, ApprovalMatrix |
| Feature Flag strategy | PASS | Company-scoped DB table; reuses FeatureFlagService from Epic 5 pattern |
| No hardcoded secrets | PASS | All config via environment variables |
| No circular dependencies | PASS | Domain has zero framework dependencies |
| Immutability of approved POs | PASS | No PO update endpoints after approval; amendment workflow required |
| GR append-only | PASS | Confirmed GRs: no edit endpoints; corrections via Vendor Return only |
| Epic 4 RBAC integration | PASS | Permission identifiers follow `purchase:resource:action` pattern |
| Epic 5 stock integration | PASS | GR confirmation calls Epic 5's PURCHASE_RECEIPT stock movement interface |
| Self-approval prevention | PASS | Domain invariant: approver_id ≠ requestor_id enforced at domain layer |
| Backward compatibility | PASS | Epic 5 product/stock interfaces consumed read-only; no modifications |

**Constitution Check Result: ALL PASS — Phase 1 implementation approved to proceed.**

---

## Project Structure

### Documentation (this feature)

```text
specs/006-purchase-management/
├── spec.md              # Official SSOT — Epic 6 specification v1.0
├── plan.md              # This file — implementation blueprint
├── research.md          # Architecture decisions resolved (generated below)
├── data-model.md        # Aggregate roots, state machines, entity relationships
├── contracts/           # OpenAPI contracts (generated in Phase 11)
│   ├── purchase-v1.yaml
│   └── events.md
├── checklists/
│   └── requirements.md  # Spec quality checklist — all items PASS
└── tasks.md             # /sp.tasks output — NOT created by /sp.plan
```

### Source Code (repository root)

```text
backend/
├── modules/
│   └── purchase/
│       ├── models/               # SQLAlchemy ORM models (all purchase entities)
│       ├── schemas/              # Pydantic request/response schemas
│       ├── repositories/         # Concrete repository implementations
│       ├── services/             # Application services (one per sub-domain)
│       ├── router.py             # FastAPI router — purchase endpoints
│       └── events/               # 32 domain event classes
│
└── migrations/
    └── versions/
        └── [0xx]_purchase_*.py   # Alembic migrations for purchase tables

frontend/
├── src/
│   └── app/
│       └── (protected)/
│           └── (purchase)/
│               ├── suppliers/             # Supplier management pages
│               ├── purchase-requests/     # PR management pages
│               ├── purchase-orders/       # PO management pages
│               ├── goods-receipts/        # GR management pages
│               ├── vendor-returns/        # RMA management pages
│               └── reports/              # Purchase report pages
│   └── components/
│       └── purchase/                     # Reusable purchase UI components
│   └── lib/
│       └── api/
│           └── purchase.ts               # API client for purchase endpoints

backend/tests/
├── unit/modules/purchase/                # Domain + application layer unit tests
├── integration/repositories/purchase/   # Repository + service integration tests
├── integration/api/v1/purchase/          # FastAPI endpoint tests
├── security/purchase/                    # Security review tests
└── performance/purchase/                 # Performance benchmarks
```

**Structure Decision**: Modular monolith pattern consistent with Epics 1–5. Purchase module isolated within `backend/modules/purchase/` following the same structure as `backend/modules/inventory/`. No new infrastructure components required — reuses the auth, company context, RBAC, audit logging, and FeatureFlagService established in Epics 1–5.

---

## Complexity Tracking

| Decision | Why Needed | Simpler Alternative Rejected Because |
|----------|------------|--------------------------------------|
| General-purpose approval engine | Serves both PR and PO approvals; also needed for RMA and future PO amendments | Separate approval logic per document type would duplicate code and diverge over time |
| Immutable PO after approval | Preserves integrity of supplier commitment; any change is a formal amendment | Allow-edit approach creates audit gaps and compliance risks |
| GR append-only + Vendor Return correction | Prevents post-hoc receipt manipulation; creates clear correction audit trail | Allow-edit approach breaks financial audit requirements |
| GR → Inventory via Epic 5 stock movement interface | Maintains Epic 5 as single source of truth for stock | Duplicating stock management in Epic 6 would create two sources of truth |
| Supplier rating as computed aggregate | Accurate, tamper-resistant performance measurement | Manual rating allows bias; no automatic update means stale data |
| PPV computation on GR confirmation | Instant variance visibility for Finance; enables timely action | Batch computation delays detection; finance loses real-time control |

---

## Implementation Strategy

Epic 6 follows **12 sequential phases** organised by domain dependency order. Each phase delivers a complete working slice: domain entity → repository → service → API → frontend → tests. No phase begins until the previous phase passes its exit criteria.

### Delivery Philosophy

1. **Vertical Slice First**: Every phase is independently demonstrable to the business
2. **Test-Driven Thinking**: Every use case defined by acceptance criteria before implementation
3. **Feature Toggle Wrapping**: All Ready-but-Disabled and Future capabilities gated from day 1
4. **Immutability by Design**: Approved POs and confirmed GRs never modified — amendment and return workflows provide the correction path
5. **Epic 5 Contract Respect**: GR confirmation is the only cross-module write; all other Epic 5 interactions are read-only
6. **Approval Engine First**: The approval sub-system is built in Phase 3 before any document workflow begins, ensuring both PRs and POs share the same engine

### Phase Dependencies

```
Phase 1 (Module Foundation)
  └── Phase 2 (Supplier Master Core)
        └── Phase 3 (Supplier Enrichment)
Phase 1
  └── Phase 4 (Procurement Foundation — Approval Engine)
        └── Phase 5 (Purchase Requests)
              └── Phase 6 (Purchase Orders)
                    └── Phase 7 (Goods Receiving)
                          └── Phase 8 (Vendor Returns)
                          └── Phase 9 (Purchase Costing)
Phase 5–9 (all complete)
  └── Phase 10 (Purchase Intelligence & Reporting)
Phase 7 (GR confirmed)
  └── Phase 11 (Integration Foundation, Import/Export, Contracts)
Phase 1–11 (all complete)
  └── Phase 12 (Performance, Security, Testing & Epic Closure)
```

---

## Implementation Phases

---

### Phase 1: Module Foundation & Scaffolding

**Objective**: Establish the purchase module infrastructure, feature flag registry, number sequencing, and shared foundation components that all subsequent phases depend on.

**Business Value**: No direct user-visible business value; enables all subsequent phases without which the module cannot function.

**Scope**:
- Purchase module scaffolding: directory structure, router registration, base schema classes
- Purchase feature flag registry: all 12+ feature flags registered with system defaults
- Document number sequencing: configurable auto-generation for PO numbers, GR numbers, PR numbers, RMA numbers
- Payment Terms master data (30-day, COD, etc.) — company-scoped
- Supplier Category tree (parent/child hierarchy, depth limit, soft-delete)
- Reason Code registry (purchase-specific: return reasons, cancellation reasons, rejection reasons)
- Purchase-specific audit logging integration (reuses Epic 5 audit pattern)
- API router registered at `/api/v1/companies/{company_id}/purchase/`

**Prerequisites**: Epics 1–5 complete; PostgreSQL 16 running; `modules/inventory/` stable

**Dependencies**: Epic 1 (FastAPI scaffold), Epic 3 (company context), Epic 4 (RBAC), Epic 5 (FeatureFlagService pattern)

**Deliverables**:
- Purchase module registered in main router
- Feature flag table extended with all purchase flags (reuses Epic 5's `company_feature_flags` table)
- Number sequence service: configurable format, prefix, auto-increment, reset policy
- Payment Terms CRUD: create, update, list, soft-delete
- Supplier Category CRUD: hierarchical, code-unique per company
- Reason Code CRUD: type-scoped (RETURN / CANCELLATION / REJECTION / GENERAL)
- Alembic migrations: supplier_categories, payment_terms, purchase_reason_codes, purchase_sequences
- API endpoints: `/payment-terms`, `/supplier-categories`, `/reason-codes`
- Frontend: Payment Terms and Supplier Category management pages
- Tests: All master data invariants, feature flag resolution, number sequence generation

**Acceptance Criteria**:
- [ ] Purchase module router responds at `/api/v1/companies/{company_id}/purchase/`
- [ ] Feature flag resolution works for all 12 purchase flags with fallback to defaults
- [ ] PO number generation produces sequential, company-unique, prefix-formatted numbers
- [ ] Supplier Category tree supports parent/child with circular reference prevention
- [ ] Payment term code unique per company enforced
- [ ] All entities have company_id, soft-delete, and audit fields

**Exit Criteria**: All unit, integration, and API tests pass; migrations run clean; Docker compose up with no errors

**Risks**:
- Number sequence contention under concurrent PO creation — mitigate with SELECT FOR UPDATE on sequence record
- Category depth explosion — enforce configurable depth limit (default: 5 levels)

**Estimated Complexity**: Low

---

### Phase 2: Supplier Master Core

**Objective**: Implement the Supplier entity, its lifecycle, and all core attributes.

**Business Value**: Companies can create, manage, and search suppliers. Procurement team can qualify and activate new vendors.

**Scope**:
- Supplier aggregate root (all core attributes per spec §14.2)
- Supplier status lifecycle state machine: DRAFT → ACTIVE → INACTIVE → BLOCKED → ARCHIVED
- Supplier code uniqueness per company (auto-generated or manual)
- Supplier contacts (multiple per supplier; primary contact designation)
- Supplier addresses (billing/shipping/other; multiple per supplier)
- Supplier search: full-text on name/code/contact, exact code search, category/status filters
- Blocked supplier guard: BLOCKED and ARCHIVED suppliers blocked from purchase document selection
- Supplier import (CSV/Excel bulk — up to 10,000 records)

**Prerequisites**: Phase 1 complete

**Deliverables**:
- Domain entities: Supplier, SupplierContact, SupplierAddress
- Supplier aggregate with all invariants enforced
- Supplier repository: FTS search, status filter, category filter, pagination
- Application services: CreateSupplier, UpdateSupplier, ActivateSupplier, DeactivateSupplier, BlockSupplier, ReactivateSupplier, ArchiveSupplier, SearchSuppliers, BulkImportSuppliers
- API endpoints: `/api/v1/companies/{id}/purchase/suppliers` (full lifecycle + search + import/export)
- Background task: supplier bulk import with row-level validation report
- Publish domain events: SupplierCreated, SupplierUpdated, SupplierActivated, SupplierDeactivated, SupplierBlocked, SupplierReactivated, SupplierArchived
- Frontend: Supplier list (with search/filter), Supplier detail, Supplier create/edit, Bulk import UI
- Tests: All status transitions, uniqueness enforcement, search accuracy, import validation, blocked supplier guard

**Acceptance Criteria**:
- [ ] Supplier code unique per company enforced at domain level
- [ ] Status transitions follow defined state machine only (invalid transitions rejected)
- [ ] Blocked/Archived suppliers cannot be selected on purchase documents (enforced at service layer)
- [ ] Supplier with open approved POs cannot be archived
- [ ] Blocking a supplier triggers SupplierBlocked event with notification hook
- [ ] Supplier FTS search returns results in < 300ms p95
- [ ] Bulk import 10,000 suppliers completes in < 60 seconds with row-level error reporting
- [ ] All supplier operations scoped to company_id (zero cross-tenant leakage)

**Exit Criteria**: All tests pass; supplier lifecycle fully exercisable via API; FTS search verified; bulk import tested with 10K dataset

**Risks**:
- Bulk import memory at 10K rows — streaming CSV parser with 500-row batch writes
- FTS index staleness — synchronous tsvector update on every supplier write

**Estimated Complexity**: High

---

### Phase 3: Supplier Master Enrichment

**Objective**: Add all enrichment layers to the Supplier: financial terms, credit limits, ratings, bank details, documents, and custom fields.

**Business Value**: Finance team can capture payment terms and credit limits. Purchase Manager can rate suppliers and designate preferred vendors. Compliance documents tracked with expiry warnings.

**Scope**:
- Payment term assignment per supplier (references Phase 1 PaymentTerms)
- Credit limit definition and enforcement modes (BLOCK / WARN / OFF — feature-flagged)
- Supplier rating entity: components (on-time %, fill rate, rejection rate), composite score, manual override
- Rating recomputation trigger: recomputes after every GR confirmation for that supplier
- Preferred supplier designation (Purchase Manager restricted)
- Vendor code (internal accounting reference)
- Bank details (Finance Manager restricted edit)
- Tax information: tax registration number, tax category, tax region
- Lead time configuration: per supplier (default) and per product-supplier combination
- Supplier documents: file attachment, document type, issue date, expiry date, expiry alert
- Custom field values (per company custom field definitions)
- Internal notes: append-only notes with author and timestamp

**Prerequisites**: Phase 2 complete

**Deliverables**:
- Domain entities: CreditLimit, SupplierRating, BankDetails, SupplierDocument, SupplierLeadTime, CustomFieldValue, InternalNote
- Rating service: computes weighted composite score from GR performance data
- Document expiry alert service: runs on schedule; notifies Purchase Manager
- Application services: SetCreditLimit, UpdateRating, SetPreferred, ManageBankDetails, AttachDocument, SetLeadTime
- API endpoints: extended supplier endpoints for all enrichment operations
- Publish domain events: SupplierRatingUpdated, PreferredSupplierDesignated
- Frontend: Supplier detail page with all enrichment tabs (Financial, Rating, Documents, Custom Fields)
- Tests: Credit limit enforcement (BLOCK / WARN / OFF), rating formula verification, preferred flag restriction, document expiry

**Acceptance Criteria**:
- [ ] Credit limit enforcement evaluated at PO approval time (not at PO creation)
- [ ] Credit limit in BLOCK mode prevents PO approval when outstanding balance exceeds limit
- [ ] Preferred supplier flag change restricted to Purchase Manager and above
- [ ] Bank detail fields restricted to Finance Manager and above
- [ ] Supplier rating recomputed after every GR confirmation
- [ ] Document expiry alert generated N days before expiry (configurable, default 30)
- [ ] `purchase.credit_limit_enforcement` feature flag gates enforcement (default: WARN)

**Exit Criteria**: All tests pass; credit limit enforcement tested in all three modes; rating computation verified with known GR dataset; document expiry alert verified

**Risks**:
- Rating computation performance at high GR volume — cache computed rating; invalidate on new GR; recompute asynchronously

**Estimated Complexity**: Medium

---

### Phase 4: Procurement Foundation — Approval Engine

**Objective**: Build the general-purpose approval engine and purchase policy framework that powers all document approval workflows in Epic 6.

**Business Value**: Companies can configure who approves what, at what thresholds, in what sequence. Without this phase, neither Purchase Requests nor Purchase Orders can be approved.

**Scope**:
- ApprovalMatrix aggregate: multi-level sequential and parallel approval configuration
- Approval levels: Level 1, 2, 3 ... N (unlimited)
- Approval rules: condition-based routing (by amount range, category, department)
- Approver assignment: by role or specific user; supports delegation with time limits
- Approval record: immutable once submitted (approve / reject / abstain + comment + timestamp)
- Self-approval prevention: domain invariant — requestor cannot be an approver on the same document
- Approval delegation: temporary delegate assignment with expiry
- Escalation: un-actioned approval after N days escalates to next level or manager
- Emergency bypass: Purchase Manager can bypass approval with documented justification (audited)
- Purchase Policy entity: direct PO allowed (yes/no), over-receipt policy, approval thresholds
- Policy configuration API: company-level settings for all procurement policies

**Prerequisites**: Phase 1 complete

**Deliverables**:
- Domain entities: ApprovalMatrix, MatrixRule, ApprovalLevel, ApprovalRecord, ApprovalDelegate, PurchasePolicy
- Approval service: route document to correct approver(s) based on matrix rules; track approval state
- Delegation service: assign/revoke delegates; route to delegate when active
- Escalation service: detect stale approvals; escalate after configured duration
- Application services: ConfigureApprovalMatrix, SubmitForApproval, ApproveDocument, RejectDocument, DelegateApproval, EscalateApproval, BypassApproval
- API endpoints: `/approval-matrix`, `/purchase-policies`, `/approvals` (pending approvals inbox)
- Frontend: Approval Matrix configuration UI, Purchase Policy settings page, Pending Approvals dashboard
- Tests: All approval scenarios (approve, reject, multi-level, delegation, escalation, bypass), self-approval prevention, emergency bypass audit

**Acceptance Criteria**:
- [ ] Approval matrix supports sequential and parallel approval at each level
- [ ] Self-approval prevention enforced — requestor cannot approve own document
- [ ] Delegation routes approvals to delegate when delegate is active
- [ ] Escalation creates notification after configured days of inaction
- [ ] Emergency bypass creates immutable bypass audit record
- [ ] `purchase.pr_approval_required` and `purchase.po_approval_required` flags gate approval workflows
- [ ] When approval not required (flag off), documents auto-approve on submission
- [ ] Approval records are immutable once submitted

**Exit Criteria**: All approval scenarios tested; self-approval prevention verified; delegation and escalation tested; bypass audit verified; both feature flags tested on/off

**Risks**:
- Multi-level approval race condition — use optimistic locking (version field) on approval document
- Delegate chain loops — validate no circular delegation before saving

**Estimated Complexity**: High

---

### Phase 5: Purchase Requests

**Objective**: Implement the Purchase Request lifecycle — the internal procurement intent document from creation through approval to PO conversion.

**Business Value**: All procurement now begins with a formal internal request. Finance and management gain visibility into spending intent before commitment. PR-to-PO conversion establishes lineage traceability.

**Scope**:
- PurchaseRequest aggregate: header + PR lines (product reference, quantity, estimated cost)
- PR status state machine: DRAFT → SUBMITTED → UNDER_REVIEW → APPROVED / REJECTED → CANCELLED
- PR number auto-generation (via Phase 1 sequence service)
- PR submission routes to ApprovalMatrix (from Phase 4)
- PR rejection: reason required; requestor notified
- PR-to-PO conversion: creates draft PO referencing approved PR; preserves PR line linkage
- Direct PO bypass: if `purchase.direct_po_allowed` is enabled, PO creation does not require a PR
- PR cancellation: allowed in DRAFT and SUBMITTED states; not after approval
- Requestor notification: in-app on approval/rejection

**Prerequisites**: Phases 2 (Supplier Master), 4 (Approval Engine) complete; Epic 5 Product API available

**Deliverables**:
- Domain entity: PurchaseRequest, PRLine, PRApprovalRecord
- PR aggregate with all state machine invariants
- PR repository with status/date/user filters
- Application services: CreatePR, SubmitPR, ApprovePR, RejectPR, CancelPR, ConvertPRtoPO
- Domain events: PurchaseRequested, PurchaseRequestApproved, PurchaseRequestRejected, PurchaseRequestCancelled, PurchaseRequestConverted
- API endpoints: `/purchase-requests` (full lifecycle + search)
- Frontend: PR list, PR create/edit, PR detail (with approval timeline), PR-to-PO conversion button
- Tests: All PR state machine transitions, self-approval prevention, PR-to-PO conversion, direct PO bypass flag

**Acceptance Criteria**:
- [ ] PR state machine enforces defined transitions only
- [ ] Requestor cannot approve their own PR
- [ ] Approved PR converts to a Draft PO preserving all line item linkages
- [ ] Rejected PR captures rejection reason and notifies requestor
- [ ] `purchase.pr_approval_required` flag: when OFF, PR auto-approves on submission
- [ ] `purchase.direct_po_allowed` flag: when ON, PO creation does not require a PR reference
- [ ] PR cancellation blocked after approval
- [ ] All PR events published with correct payloads

**Exit Criteria**: All PR state transitions tested; PR-to-PO conversion verified; both feature flags tested on/off; approval integration tested end-to-end

**Risks**:
- Product reference currency at PR creation time vs PO creation time — PR stores estimated cost only; PO captures actual contracted cost

**Estimated Complexity**: Medium

---

### Phase 6: Purchase Orders

**Objective**: Implement the Purchase Order lifecycle — the external supplier commitment document from draft through approval to receipt-ready status.

**Business Value**: Purchase team can issue formal, governed, audited purchase commitments to suppliers. Finance gains real-time commitment visibility. PO is the anchor document for all downstream receiving and costing.

**Scope**:
- PurchaseOrder aggregate: header + PO lines (product, quantity, unit cost, discount) + POAdditionalCharges
- PO status state machine: DRAFT → PENDING_APPROVAL → APPROVED → PARTIALLY_RECEIVED → FULLY_RECEIVED → CLOSED / CANCELLED
- PO number auto-generation (configurable format/prefix)
- PO approval routes through ApprovalMatrix (from Phase 4)
- PO immutability after approval: no direct edits; amendment workflow required
- PO amendment: creates POAmendment record; resets PO to PENDING_APPROVAL for re-approval
- PO cancellation: reason code required; blocked after any GR exists against the PO
- PO-to-GR linkage: auto-updates PO status on GR confirmation
- Expected delivery date tracking; overdue detection
- Supplier reference number capture (supplier's own order acknowledgement number)
- Supplier eligibility check: BLOCKED/ARCHIVED supplier selection prevented
- Credit limit check at PO approval
- PO document export to PDF
- PO email to supplier (when `purchase.po_email_supplier` flag enabled)

**Prerequisites**: Phases 2 (Supplier), 4 (Approval Engine), 5 (PR — for PR-to-PO linkage) complete

**Deliverables**:
- Domain entities: PurchaseOrder, POLine, POAdditionalCharge, POAmendment, POApprovalRecord
- PO aggregate with all invariants enforced (immutability, supplier eligibility, credit limit)
- PO repository: multi-status filter, supplier filter, date range, overdue detection
- Application services: CreatePO, CreatePOFromPR, SubmitPO, ApprovePO, RejectPO, AmendPO, CancelPO, ClosePO, ExportPOtoPDF
- Domain events: PurchaseOrdered, PurchaseOrderApproved, PurchaseOrderRejected, PurchaseOrderAmended, PurchaseOrderCancelled, PurchaseOrderClosed, PurchaseOrderFullyReceived
- API endpoints: `/purchase-orders` (full lifecycle + search + PDF export + email)
- Frontend: PO list, PO create/edit (with line items, charges, discounts), PO detail, PO approval timeline, PO PDF preview
- Tests: All PO state transitions, immutability enforcement, amendment workflow, cancellation guard (no cancel after GR), credit limit enforcement, overdue detection

**Acceptance Criteria**:
- [ ] PO state machine enforces defined transitions only
- [ ] Approved PO cannot be edited without an amendment; amendment resets to PENDING_APPROVAL
- [ ] BLOCKED/ARCHIVED supplier cannot be selected on a PO
- [ ] Credit limit checked at PO approval time (not creation time)
- [ ] PO cancelled only if no GR exists; blocked otherwise
- [ ] Auto-update PO status to PARTIALLY_RECEIVED / FULLY_RECEIVED on GR confirmation
- [ ] `purchase.po_approval_required` flag: when OFF, PO auto-approves on submission
- [ ] PO PDF export includes company header, supplier details, line items, terms, and totals
- [ ] All 7 PO domain events published with correct payloads

**Exit Criteria**: All PO state transitions tested; immutability and amendment workflow tested; credit limit enforcement verified; PDF export verified; all domain events verified

**Risks**:
- PO total computation rounding (discounts + charges + taxes) — use Python Decimal for all monetary arithmetic; store as NUMERIC in PostgreSQL
- Amendment race condition — optimistic lock on PO (version field) prevents concurrent amendments

**Estimated Complexity**: High

---

### Phase 7: Goods Receiving

**Objective**: Implement the Goods Receipt lifecycle — the document recording physical receipt of goods against a PO, and the trigger for inventory stock update.

**Business Value**: Warehouse team can record what was actually received. Stock levels update automatically. Over/under receipts are tracked. The PO is marked as partially or fully received. The company's inventory remains accurate.

**Scope**:
- GoodsReceipt aggregate: header + GR lines (PO line reference, received quantity, rejected quantity, unit cost)
- GR status state machine: DRAFT → CONFIRMED (two-step: create then confirm)
- GR number auto-generation
- GR only against APPROVED or PARTIALLY_RECEIVED POs (not DRAFT/PENDING/CANCELLED/CLOSED)
- Open quantity display: ordered − previously received = open quantity per line
- Partial receipt: multiple GRs against one PO; running total tracked
- Over-receipt policy enforcement: BLOCK / WARN / ALLOW (per company setting, feature-flagged)
- Under-receipt: open quantity tracked; PO remains PARTIALLY_RECEIVED
- Line-level rejection: rejected quantity + reason code (separate from received quantity)
- GR confirmation triggers:
  1. Inventory stock update via Epic 5 PURCHASE_RECEIPT stock movement (transactional)
  2. PO status update (APPROVED → PARTIALLY_RECEIVED or FULLY_RECEIVED)
  3. Supplier rating recomputation
  4. PPV computation (if GR cost differs from PO cost)
- Confirmed GR immutability: no edits after confirmation; corrections via Vendor Return only
- GR barcode scan integration readiness: barcode lookup endpoint for GR item entry

**Prerequisites**: Phases 2 (Supplier), 6 (Purchase Orders) complete; Epic 5 stock movement interface available

**Deliverables**:
- Domain entities: GoodsReceipt, GRLine
- GR aggregate with all invariants (over-receipt policy, confirmed = immutable)
- GR repository: PO-linked filter, date filter, supplier filter, status filter
- Application services: CreateGR, AddGRLines, ConfirmGR, CalculatePPV, UpdatePOStatusOnGR, TriggerInventoryUpdate, TriggerRatingUpdate
- Cross-module integration: `InventoryStockService.record_purchase_receipt()` called within GR confirmation transaction
- Domain events: GoodsReceived, GoodsRejected, GoodsPartiallyReceived, OverReceiptDetected
- API endpoints: `/goods-receipts` (create, update lines, confirm, view)
- Frontend: GR list, GR create (PO selection + line entry with open quantity display), GR confirmation, GR detail
- Tests: All GR scenarios (partial, full, over-receipt in all policy modes, rejection, confirmed immutability), Epic 5 stock integration (transaction rollback test), PPV computation

**Acceptance Criteria**:
- [ ] GR cannot be created against a non-APPROVED/PARTIALLY_RECEIVED PO
- [ ] Open quantity correctly calculated: ordered − previously received − current receipt
- [ ] Over-receipt BLOCK mode prevents confirmation; WARN mode allows with notification; ALLOW mode silent
- [ ] GR confirmation and inventory stock update committed in same database transaction (rollback if either fails)
- [ ] Confirmed GR is immutable (no edit endpoints after confirmation)
- [ ] PO status auto-updates to PARTIALLY_RECEIVED / FULLY_RECEIVED on confirmation
- [ ] Supplier rating recomputed after every confirmed GR
- [ ] PPV computed per GR line if GR unit cost differs from PO unit cost
- [ ] `purchase.gr_barcode_scan` flag enables barcode-driven line entry

**Exit Criteria**: All GR scenarios tested; Epic 5 inventory integration tested transactionally; rollback test passes; over-receipt in all three modes verified; PPV computation verified

**Risks**:
- Cross-module transaction failure (GR commit + inventory update) — use Unit of Work pattern; both operations in single SQLAlchemy session; rollback if either fails
- Concurrent GRs against same PO line (race to full receipt) — SELECT FOR UPDATE on PO open-quantity state

**Estimated Complexity**: High

---

### Phase 8: Vendor Returns

**Objective**: Implement the Return Merchandise Authorisation (RMA) workflow — the process for returning received goods to a supplier and updating inventory.

**Business Value**: Warehouse team can formally initiate and track vendor returns. Inventory is accurately reduced on dispatch. Finance is alerted when credit notes are expected from the supplier.

**Scope**:
- VendorReturn aggregate: RMA header + return lines (GR line reference, return quantity, return reason)
- RMA status state machine: DRAFT → SUBMITTED → APPROVED → DISPATCHED → COMPLETED / CANCELLED
- Return quantity validation: cannot exceed accepted (received − rejected) quantity on referenced GR line
- RMA approval: routes through Approval Matrix (uses Phase 4 engine)
- Inventory reduction on dispatch: calls Epic 5 PURCHASE_RETURN_OUTBOUND stock movement
- Credit note flag: `credit_note_pending` set on COMPLETED RMA (future AP integration hook)
- Replacement PO linkage: optional reference to a new PO created to replace returned goods
- Return reason codes (from Phase 1 reason code registry)
- Notification: supplier to be informed of return dispatch (in-app; email via flag)

**Prerequisites**: Phases 4 (Approval), 7 (GR) complete; Epic 5 stock movement interface available

**Deliverables**:
- Domain entities: VendorReturn, ReturnLine
- VendorReturn aggregate with return quantity validation and state machine
- Application services: CreateRMA, SubmitRMA, ApproveRMA, DispatchRMA, CompleteRMA, CancelRMA, LinkReplacementPO
- Cross-module integration: `InventoryStockService.record_purchase_return()` on dispatch confirmation
- Domain events: GoodsReturnInitiated, GoodsReturnApproved, GoodsReturned, GoodsReturnCompleted
- API endpoints: `/vendor-returns` (full lifecycle)
- Frontend: RMA list, RMA create (GR selection + return quantity entry), RMA detail, approval flow
- Tests: All RMA state transitions, return quantity validation, inventory reduction on dispatch, credit note flag, replacement PO linkage

**Acceptance Criteria**:
- [ ] Return quantity per line ≤ accepted quantity on referenced GR line
- [ ] RMA cannot be created against a non-CONFIRMED GR
- [ ] RMA state machine enforces defined transitions only
- [ ] Inventory reduced when RMA transitions to DISPATCHED (transactional)
- [ ] `credit_note_pending` flag set to TRUE on COMPLETED RMA
- [ ] Replacement PO linkage is optional and does not affect RMA state
- [ ] All 4 Vendor Return domain events published

**Exit Criteria**: All RMA state transitions tested; inventory reduction on dispatch verified transactionally; credit note flag verified; replacement PO linkage tested

**Risks**:
- Dispatch inventory update failure — same Unit of Work pattern as Phase 7 GR confirmation

**Estimated Complexity**: Medium

---

### Phase 9: Purchase Costing

**Objective**: Implement comprehensive purchase costing: additional charges, discounts, PPV tracking, tax readiness, and cost summary computation.

**Business Value**: Finance team gets complete cost visibility per PO. Price variance is detected automatically. Additional costs (freight, handling, insurance) are captured for future landed cost processing.

**Scope**:
- PO cost summary computation: subtotal, total charges, total discounts, estimated total
- Additional charges at PO header level: freight, handling, insurance (code + amount + notes)
- Line-level discount: percentage or fixed amount per PO line
- Header-level discount: percentage or fixed amount on PO total
- Trade discount: configurable at supplier level, auto-applied to PO
- Tax readiness fields: tax category, tax code, tax rate, tax amount, tax inclusive flag (not computed — future AP scope)
- PPV service: compute (GR unit cost − PO unit cost) × received quantity per GR line
- PPV threshold notification: notify Finance Manager when PPV exceeds configurable threshold
- Landed cost hook: `landed_cost_ready` flag on confirmed GR records; additional charges on GR captured but not allocated
- Cost summary per PO and per GR available via API
- PurchaseCostEntry: one record per GR confirmation (cost data snapshot for AP)

**Prerequisites**: Phases 6 (PO) and 7 (GR) complete

**Deliverables**:
- Domain entities: POAdditionalCharge (extended), DiscountRule, PurchaseCostEntry
- Cost computation service: subtotal, discounts, charges, total — using Python Decimal throughout
- PPV service: computes and records variance on GR confirmation
- Tax readiness schema: fields present on PO line and GR line (no computation logic)
- Domain events: PurchaseCostRecorded, PurchasePriceVarianceDetected, AdditionalChargeRecorded
- API endpoints: PO cost endpoints extended; GR cost summary; PPV report data endpoint
- Frontend: PO cost breakdown panel (charges, discounts, totals), PPV display on GR detail
- Tests: Cost computation accuracy (known values), discount precedence rules, PPV formula, threshold notification, tax field presence

**Acceptance Criteria**:
- [ ] PO total computed correctly: subtotal + charges − discounts (using Decimal arithmetic)
- [ ] Line discount and header discount applied in correct precedence
- [ ] PPV = (GR unit cost − PO unit cost) × received quantity (formula verified with known values)
- [ ] PPV > threshold triggers PurchasePriceVarianceDetected event and in-app notification to Finance Manager
- [ ] Tax fields present on PO line and GR line (zero computation; ready for EP 8)
- [ ] `landed_cost_ready` flag present on all confirmed GRs (always true; activates in EP 8)
- [ ] All 3 cost domain events published with correct payloads

**Exit Criteria**: Cost computation verified with known datasets; PPV formula verified; tax field presence confirmed in migration; domain events verified

**Risks**:
- Floating-point rounding on large POs — enforce Python Decimal and NUMERIC(15,4) PostgreSQL type throughout; never use float

**Estimated Complexity**: Medium

---

### Phase 10: Purchase Intelligence & Reporting

**Objective**: Implement all 14 standard purchase reports, 10 KPIs, and the KPI dashboard.

**Business Value**: Management and Finance gain full procurement visibility. Supplier performance is measurable. Cost trends are visible. Procurement efficiency can be tracked and improved.

**Scope**:
- All 14 reports from spec §34:
  - RPT-01: Purchase Order Summary
  - RPT-02: Pending Purchase Orders
  - RPT-03: Overdue Deliveries
  - RPT-04: Goods Receipt Report
  - RPT-05: Purchase Request Status
  - RPT-06: Supplier Performance Report
  - RPT-07: Vendor Return Report
  - RPT-08: Purchase by Supplier
  - RPT-09: Purchase by Category
  - RPT-10: Purchase Price Variance
  - RPT-11: Open Purchase Commitments
  - RPT-12: Purchase Trend Analysis
  - RPT-13: Goods Rejection Analysis
  - RPT-14: Procurement Audit Trail
- All 10 KPIs from spec §35: Purchase Cycle Time, On-Time Delivery Rate, Order Fulfilment Rate, Rejection Rate, PPV%, Open Commitments, Total Purchase Value, PO Processing Time, Vendor Return Rate, Preferred Supplier Utilisation
- KPI dashboard endpoint
- CSV and Excel export for all reports
- All reports scoped by company_id; all RBAC-protected

**Prerequisites**: Phases 5–9 complete (all operational data available)

**Deliverables**:
- Report query services (read-only; no domain mutations)
- Report API endpoints: `/purchase/reports/{report_type}` with filter parameters
- KPI API endpoint: `/purchase/kpis`
- Export service: CSV + Excel generation per report
- Frontend: Report pages with date/supplier/status filters; KPI dashboard with charts; export buttons
- Tests: Report accuracy against known datasets; KPI formula verification; export tested; tenant isolation on all reports

**Acceptance Criteria**:
- [ ] All 14 reports return data scoped to company_id
- [ ] All 14 reports support date range, supplier, status, and category filters
- [ ] All 14 reports export to CSV and Excel correctly
- [ ] All 10 KPIs computed correctly against known test datasets
- [ ] Supplier Performance report (RPT-06) reflects on-time rate, fill rate, rejection rate from GR data
- [ ] Purchase Trend Analysis (RPT-12) covers monthly/quarterly aggregation
- [ ] All report endpoints respond within p95 < 5 seconds
- [ ] No cross-tenant data in any report

**Exit Criteria**: All 14 reports tested with realistic dataset; all 10 KPI formulas verified; export tested; cross-tenant isolation verified on all reports

**Risks**:
- Open Purchase Commitments report (RPT-11) performance at high PO volume — use materialised summary view; refresh on PO status change

**Estimated Complexity**: Medium

---

### Phase 11: Integration Foundation, Import/Export & Contracts

**Objective**: Formalise the Epic 5 integration contract, complete domain event publishing, generate OpenAPI specifications, and deliver all bulk import/export capabilities.

**Business Value**: Integration consumers (future Accounts Payable, Sales) have stable contracts. Domain events enable future event-driven enhancements. Bulk import accelerates supplier and PO data migration.

**Scope**:
- Verify all 32 domain events are published on their correct triggers
- Event serialisation verification: all events JSON-serialisable
- `InProcessEventBus` integration (same pattern as Epic 5)
- Epic 5 integration contract documentation: `GoodsReceived` → triggers `StockMovement.PURCHASE_RECEIPT`; `VendorReturn.DISPATCHED` → triggers `StockMovement.PURCHASE_RETURN_OUTBOUND`
- Supplier bulk import (finalized with full validation report)
- PO document export to PDF (complete)
- PO email to supplier (`purchase.po_email_supplier` flag)
- OpenAPI specification generation: `specs/006-purchase-management/contracts/purchase-v1.yaml`
- Domain event contract documentation: `specs/006-purchase-management/contracts/events.md`
- Quickstart developer guide: `specs/006-purchase-management/quickstart.md`
- Agent context update

**Prerequisites**: All Phases 1–10 complete

**Deliverables**:
- Event publication verified for all 32 domain events
- EventBus integration (reuses Epic 5 InProcessEventBus)
- OpenAPI contract: `contracts/purchase-v1.yaml`
- Event contract: `contracts/events.md`
- Quickstart guide: developer onboarding for purchase module
- Tests: Event firing verified for all write operations; serialisation verified for all 32 events

**Acceptance Criteria**:
- [ ] All 32 domain events published on correct triggers
- [ ] All 32 events JSON-serialisable (verified in tests)
- [ ] EventBus interface is abstract — transport swappable without domain changes
- [ ] OpenAPI contract is complete, accurate, and matches all API endpoints
- [ ] `contracts/events.md` documents all 32 events with payload structure
- [ ] `quickstart.md` enables a new developer to create a supplier, create a PO, and confirm a GR from scratch

**Exit Criteria**: All 32 events verified; OpenAPI contract generated; quickstart guide reviewed

**Risks**:
- Event schema breaking changes as payloads evolve — include `event_version` field on all events from day 1

**Estimated Complexity**: Low

---

### Phase 12: Performance, Security, Testing & Epic Closure

**Objective**: Validate all performance targets, conduct security review, execute full regression and tenant isolation tests, and close the epic.

**Business Value**: Production readiness assured. All Epic Completion Criteria verified. Branch ready for merge.

**Scope**:
- Performance validation against all spec §44 targets:
  - Supplier search p95 < 300ms
  - PO list p95 < 500ms
  - GR confirmation < 2 seconds
  - Report generation p95 < 5 seconds
  - All standard reads p95 < 200ms
- Database index audit: verify indexes on all foreign keys, status columns, date columns, FTS columns
- N+1 query elimination: audit all list endpoints
- Security review: SQL injection, XSS, mass-assignment, BOLA on all purchase endpoints
- Full tenant isolation test: zero cross-company data leakage across all entities
- RBAC permission matrix test: all 10 roles × all purchase operations
- End-to-end business workflow tests: all 4 workflows from spec §22
- Soft-delete completeness test: all entities
- Audit trail completeness test: all document state changes
- Docker Compose production-readiness verification
- Epic Completion Criteria verification: all 15 gates from spec §59
- Branch PR preparation

**Prerequisites**: All Phases 1–11 complete and passing

**Deliverables**:
- Performance test results against all spec targets
- Index optimisations applied (documented)
- Security review findings and remediations
- Tenant isolation test results: zero incidents
- Permission matrix test results: all roles correct
- End-to-end test suite covering all 4 business workflows
- Docker verification result
- Epic 6 Completion Checklist (all 15 EC gates verified)
- PR for `006-purchase-management` → `main`

**Acceptance Criteria**:
- [ ] All spec §44 performance targets met
- [ ] No N+1 queries on any list endpoint
- [ ] Zero security vulnerabilities found (or all found ones remediated)
- [ ] Zero cross-company data leakage across all entities
- [ ] All 10 RBAC roles operate with correct permission boundaries
- [ ] All 4 business workflows complete end-to-end without errors
- [ ] Docker Compose up → migrate → seed → API smoke test: all pass
- [ ] All 15 Epic Completion Criteria from spec §59 verified PASS
- [ ] Zero critical bugs open

**Exit Criteria**: All 15 Epic Completion Criteria PASS; PR approved; branch merged to main

**Estimated Complexity**: Medium

---

## Technical Architecture Plan

### Domain Layer Design

The domain layer has zero dependencies on FastAPI, SQLAlchemy, or any external framework. It contains:

- **Entities**: Supplier, SupplierContact, SupplierAddress, BankDetails, SupplierDocument, SupplierRating, CreditLimit, PurchaseRequest, PRLine, PurchaseOrder, POLine, POAdditionalCharge, POAmendment, GoodsReceipt, GRLine, VendorReturn, ReturnLine, ApprovalMatrix, MatrixRule, ApprovalRecord, PurchaseCostEntry
- **Aggregate Roots**: Supplier, PurchaseRequest, PurchaseOrder, GoodsReceipt, VendorReturn, ApprovalMatrix
- **Domain Events**: 32 events across 6 sub-domains (per spec §33)
- **Repository Interfaces**: Abstract contracts implemented by the infrastructure layer

**Key Invariants enforced at Domain Layer**:
- Supplier code unique per company (Supplier aggregate)
- Approved PO is immutable — no field updates without amendment (PurchaseOrder aggregate)
- Confirmed GR is immutable — no edits after confirmation (GoodsReceipt aggregate)
- Return quantity ≤ accepted quantity on referenced GR line (VendorReturn aggregate)
- Requestor cannot be approver of their own document (ApprovalRecord value object)
- PO cannot be created against BLOCKED/ARCHIVED supplier (PurchaseOrder aggregate)

### Application Layer Design

The application layer orchestrates domain operations. It:

- Contains one Application Service per sub-domain (SupplierService, PRService, POService, GRService, RMAService, CostService, ApprovalService)
- Receives Pydantic schemas (not domain entities) from the API layer
- Calls repository interfaces (not concrete implementations)
- Publishes domain events via the EventBus interface
- Manages database transaction boundaries
- Never accesses PostgreSQL directly

**Key Application Services**:
- `SupplierService`: supplier lifecycle, rating recomputation, preferred designation
- `ApprovalService`: route documents through approval matrix; handle delegation and escalation
- `POService`: PO lifecycle, amendment workflow, PO-from-PR creation
- `GRService`: GR confirmation, over-receipt enforcement, Epic 5 integration trigger, PPV computation
- `RMAService`: RMA workflow, return quantity validation, inventory dispatch trigger
- `CostService`: cost summary computation, PPV detection and notification
- `ReportService`: read-only report queries, KPI computations, export generation
- `FeatureFlagService`: reused from Epic 5 pattern — company-scoped flag resolution

### Repository Layer Design

The base repository class (consistent with Epic 5) enforces `company_id` on every query. No repository method exists without `company_id` as a mandatory first-class argument.

**Key patterns**:
- `BaseRepository(company_id)` — all purchase repositories inherit from this
- `PORepository` — read/write; no update endpoints after PO reaches APPROVED status (enforced at service layer)
- `GRRepository` — write on creation; no update after CONFIRMED status
- `SupplierRepository` — full CRUD with FTS search support
- `ApprovalRecordRepository` — append-only; approval records never updated or deleted

### Validation Layer Design

Validation operates at three layers:

1. **API Layer (Pydantic v2)**: Request schema validation — type, format, required fields
2. **Application Layer**: Business rule validation — credit limit check, approval matrix routing, over-receipt policy
3. **Domain Layer**: Invariant enforcement — immutability, self-approval prevention, quantity constraints

### Approval Engine Design

The approval engine is a **general-purpose sub-system** within the purchase module:

- `ApprovalMatrix` defines: levels, rules (amount/category/department conditions), approvers per level
- `ApprovalService.route_for_approval(document_type, document_id, amount, category)` → determines approver(s) based on active matrix rules
- Each approval level: sequential (Level 1 must approve before Level 2 is notified) or parallel (all level approvers notified simultaneously; any one can approve)
- `ApprovalRecord` created per approval action — immutable once submitted
- Same engine used for PRs, POs, RMAs, and future PO amendments

### Authorization Design

Authorization follows the Epic 4 RBAC model with purchase-specific permission identifiers:

| Module | Resource | Actions |
|--------|----------|---------|
| purchase | supplier | create, read, update, activate, deactivate, block, archive, import, export |
| purchase | supplier.bank_details | read, update (Finance Manager only) |
| purchase | supplier.preferred | update (Purchase Manager only) |
| purchase | purchase_request | create, read, update, submit, approve, reject, cancel, convert |
| purchase | purchase_order | create, read, update, submit, approve, reject, amend, cancel, close, export |
| purchase | goods_receipt | create, read, confirm |
| purchase | vendor_return | create, read, submit, approve, dispatch, complete, cancel |
| purchase | approval_matrix | read, configure (Purchase Manager only) |
| purchase | report | read, export |
| purchase | cost_entry | read |

### Audit Logging Design

Every write operation produces an audit record within the same database transaction. Consistent with Epic 5 pattern:

- Table: `audit_logs` (shared schema from Epic 2/3)
- Fields: `entity_type`, `entity_id`, `action`, `old_value` (JSON), `new_value` (JSON), `user_id`, `company_id`, `performed_at`, `ip_address`
- GR lines are themselves an audit trail of what was received — no separate audit record for line quantities

### Feature Toggle Design

Feature flags resolve in order: company-level override → system default. Reuses `FeatureFlagService` from Epic 5.

| Flag Key | Default | Controls |
|----------|---------|---------|
| `purchase.pr_approval_required` | true | Requires approval workflow for Purchase Requests |
| `purchase.po_approval_required` | true | Requires approval workflow for Purchase Orders |
| `purchase.direct_po_allowed` | false | Allows PO creation without a PR |
| `purchase.credit_limit_enforcement` | WARN | BLOCK / WARN / OFF — enforced at PO approval |
| `purchase.over_receipt_policy` | WARN | BLOCK / WARN / ALLOW — enforced at GR confirmation |
| `purchase.po_email_supplier` | false | Sends PO to supplier via email on approval |
| `purchase.gr_barcode_scan` | false | Enables barcode-driven GR line entry |
| `purchase.sms_notifications` | false | SMS notifications for high-priority events |
| `purchase.whatsapp_notifications` | false | WhatsApp notifications for high-priority events |
| `purchase.ai_reorder_suggestions` | false | AI-driven reorder suggestions (future) |
| `purchase.supplier_portal` | false | Supplier self-service portal (future) |
| `purchase.edi_integration` | false | EDI supplier integration (future) |

---

## Data Strategy

### Ownership Map

| Data Domain | Owner in Epic 6 | Future Owner |
|-------------|----------------|--------------|
| Supplier Master | Epic 6 (Purchase) | Permanent — never transferred |
| Payment Terms | Epic 6 (Purchase) | Permanent — shared with AP |
| Supplier Categories | Epic 6 (Purchase) | Permanent |
| Purchase Requests | Epic 6 (Purchase) | Permanent |
| Purchase Orders | Epic 6 (Purchase) | Permanent |
| Goods Receipts | Epic 6 (Purchase) | Permanent — referenced by Epic 8 AP |
| Vendor Returns | Epic 6 (Purchase) | Permanent |
| Purchase Cost Entries | Epic 6 (Purchase) | Referenced by Epic 8 AP for invoice matching |
| Approval Records | Epic 6 (Purchase) | Permanent — used by AP for three-way match audit |
| Bank Details | Epic 6 (Purchase, read-write) | Epic 8 AP will use for payment routing |
| Tax Fields (capture only) | Epic 6 (Purchase) | Epic 8 AP will activate computation |
| Landed Cost Hooks | Epic 6 (stub fields) | Epic 8.x Landed Cost will populate |
| Stock Impact (PURCHASE_RECEIPT) | Epic 5 (Inventory) | Epic 6 creates movements; Epic 5 owns the table |

### Immutability Guarantees

- **ApprovalRecord**: append-only once submitted; no update or delete operations
- **GoodsReceipt** (confirmed): no edit endpoint exists after status = CONFIRMED
- **PurchaseOrder** (approved): no direct edit endpoint after approval; amendment workflow required
- **PurchaseCostEntry**: append-only cost snapshot; corrections via new entries only

### Migration Strategy

- All Alembic migrations are additive
- No destructive migrations in Epic 6
- Future Epics will add columns (invoice_id, currency_exchange_rate) — they will NOT rename or remove Epic 6 columns
- `landed_cost_ready` flag reserved as boolean on GoodsReceipt from day 1 (always TRUE in Epic 6; activated in Epic 8.x)
- `bank_details` fully captured in Epic 6; payment processing columns added in Epic 8

---

## Dependency Planning

### Internal Dependencies (within Epic 6)

| Phase | Depends On |
|-------|-----------|
| Phase 2 | Phase 1 (Module foundation, Supplier Categories, Payment Terms) |
| Phase 3 | Phase 2 (Supplier entity, GR trigger for rating recompute) |
| Phase 4 | Phase 1 (Module foundation) |
| Phase 5 | Phase 2 (Supplier), Phase 4 (Approval Engine) |
| Phase 6 | Phase 2 (Supplier), Phase 4 (Approval Engine), Phase 5 (PR-to-PO linkage) |
| Phase 7 | Phase 6 (Purchase Orders), Phase 3 (Supplier rating recompute on GR) |
| Phase 8 | Phase 7 (GR, for RMA against confirmed GR) |
| Phase 9 | Phase 6 (PO cost), Phase 7 (GR cost, PPV) |
| Phase 10 | Phases 5–9 (all operational data) |
| Phase 11 | All Phases 1–10 |
| Phase 12 | All Phases 1–11 |

### Cross-Epic Dependencies (upstream — already complete)

| Epic | Component Needed | Status |
|------|-----------------|--------|
| Epic 1 | FastAPI app scaffold, SQLAlchemy setup, Docker Compose, Alembic | Complete |
| Epic 2 | JWT authentication, auth middleware, user context extraction | Complete |
| Epic 3 | Company context resolution, company settings | Complete |
| Epic 4 | RBAC permission system, role resolver, permission checker middleware | Complete |
| Epic 5 | Product Master stable read API; StockMovement INSERT interface (PURCHASE_RECEIPT, PURCHASE_RETURN_OUTBOUND); FeatureFlagService | Complete |

### Cross-Epic Dependencies (downstream — to be provided by Epic 6)

| Future Epic | What Epic 6 Provides |
|------------|---------------------|
| Epic 7 (Sales) | Supplier Master read API (preferred suppliers for sales sourcing) |
| Epic 8 (AP) | PurchaseOrder + GoodsReceipt + PurchaseCostEntry APIs for three-way match; Supplier bank details |
| Epic 8.x (Landed Cost) | GoodsReceipt with landed_cost_ready flag; POAdditionalCharges |
| Epic 9 (Import Purchasing) | PurchaseOrder currency fields (stub), multi-currency readiness hooks |
| Epic 11 (Supplier Portal) | Supplier entity stable read API; PO transmission events |
| Reports Epic | All purchase read APIs (reports, KPIs) |
| AI Epic | Historical GR and PO data for demand forecasting and supplier risk |

### Blocked / Deferred Items

| Item | Status | Activation |
|------|--------|-----------|
| RFQ (Request for Quotation) | Deferred — domain stub reserved | Epic 6.x |
| Quotation Comparison | Deferred | Epic 6.x |
| Budget Validation | Deferred | Epic 6.x |
| Quality Inspection Workflow | Deferred | Epic 6.x |
| Multi-Currency PO | Deferred — currency_code field present on PO | Epic 10 |
| Multi-Branch PO | Deferred — branch_id nullable field reserved | Branch Management Epic |
| Tax Computation | Deferred — fields present; computation absent | Epic 8 |
| Landed Cost Allocation | Deferred — `landed_cost_ready` flag reserved | Epic 8.x |
| Three-Way Match | Deferred | Epic 8 |
| Accounts Payable | Deferred | Epic 8 |
| EDI Integration | Deferred | Epic 11 |
| Supplier Portal | Deferred | Epic 11 |
| Email/SMS/WhatsApp Notifications (non-PR/PO) | Ready/Disabled — behind feature flags | Notification Module |
| Push Notifications | Deferred — requires mobile app | Mobile App Epic |

---

## Testing Strategy

### Unit Testing

**Scope**: Domain entities, aggregate root invariants, state machine transitions, cost computation, approval routing logic, PPV formula

**Approach**:
- Zero infrastructure dependencies — all domain tests run in-memory
- One test class per aggregate root (Supplier, PO, GR, VendorReturn, PR, ApprovalMatrix)
- Test every valid state transition
- Test every invalid state transition (expect domain exception)
- Test approval engine: single-level, multi-level, self-approval prevention
- Test cost formulas with known values (e.g., 10 units @ $50, 5% line discount, $20 freight = verify total)
- Test PPV formula: GR cost − PO cost × quantity

**Coverage Target**: > 95% domain layer

### Integration Testing

**Scope**: Repository implementations, database queries, transaction boundaries, Epic 5 stock interface

**Approach**:
- Test database (PostgreSQL in Docker)
- Test every repository method with real SQL
- Test company_id isolation: no data returned for wrong company
- Test soft-delete: deleted records excluded from all queries
- Test transactional GR confirmation: verify rollback leaves both GR and stock movement absent
- Test concurrent PO creation (sequence uniqueness under load)

**Coverage Target**: > 90% repository layer

### API Testing

**Scope**: All FastAPI endpoints, request/response schemas, authentication enforcement, permission enforcement

**Approach**:
- FastAPI TestClient for all endpoints
- Test authenticated + unauthenticated requests
- Test permission enforcement for each operation × each role (10 roles)
- Test pagination, filtering, sorting on all list endpoints
- Test error responses (400, 401, 403, 404, 409, 422)

**Coverage Target**: > 90% API layer

### Workflow Testing

**Scope**: All 4 business workflows from spec §22 (end-to-end)

1. Standard Purchase Workflow: PR → Approval → PO → Approval → GR → Inventory Updated
2. Direct PO Workflow (flag enabled): PO → Approval → GR → Inventory Updated
3. Vendor Return Workflow: RMA → Approval → Dispatch → Inventory Reduced → Credit Note Flag
4. Supplier Onboarding Workflow: DRAFT → Enrichment → Activation

### Approval Engine Testing

**Scope**: All approval scenarios
- Single-level approval (approve, reject)
- Multi-level sequential approval
- Multi-level parallel approval
- Self-approval prevention
- Approval delegation (active delegate, expired delegate)
- Escalation after N days
- Emergency bypass with audit
- Feature flag: approval required ON vs OFF

### Permission Testing

**Scope**: Full permission matrix — all 10 roles × all purchase operations

**Approach**: One test matrix per endpoint group; assert HTTP 200 for allowed, 403 for denied, 401 for unauthenticated

### Tenant Isolation Testing

**Scope**: Zero cross-company data leakage across all purchase entities

**Approach**:
- Create two companies with overlapping supplier codes and PO numbers
- Execute every read and write operation as Company A
- Verify zero data from Company B is returned or affected

### Business Rule Validation

Key business rules to test explicitly:
- Blocked supplier cannot be selected on PO (domain + API)
- PO immutable after approval — edit attempt returns 409
- GR confirmed immutable — edit attempt returns 409
- Return quantity ≤ accepted GR quantity
- Self-approval prevention
- Credit limit enforcement in all three modes
- Over-receipt policy in all three modes

### Performance Testing

**Scope**: All spec §44 performance targets

**Approach**:
- Seed database with realistic volumes (50K suppliers, 100K POs, 200K GRs)
- Supplier search benchmark (FTS + filters)
- PO list benchmark with multi-status filter
- GR confirmation benchmark (includes Epic 5 stock update)
- Report generation benchmark for all 14 reports
- Bulk supplier import (10K rows)

### Docker Validation

All tests must pass in Docker environment:
1. `docker compose build`
2. `docker compose up -d`
3. `alembic upgrade head`
4. `pytest --cov`
5. Docker smoke test: create supplier → create PO → confirm GR → check stock
6. `docker compose down`

---

## Quality Gates

Quality gates are mandatory checkpoints. No subsequent phase begins until the gate passes.

| Gate | Trigger | Criteria |
|------|---------|---------|
| G1: Architecture Review | Before Phase 1 | Clean Architecture layers verified; Epic 5 integration contract defined |
| G2: Phase 1 Exit | Phase 1 complete | Module foundation tests pass; migrations clean; feature flags resolvable |
| G3: Phase 2 Exit | Phase 2 complete | Supplier lifecycle fully tested; FTS search verified; bulk import tested |
| G4: Phase 4 Exit | Phase 4 complete | Approval engine tested: single/multi-level, delegation, self-approval prevention |
| G5: Phase 6 Exit | Phase 6 complete | PO lifecycle, immutability, amendment, credit limit enforcement tested |
| G6: Phase 7 Exit | Phase 7 complete | GR confirmed immutable; Epic 5 integration transactional; over-receipt in all modes |
| G7: Phase 10 Exit | Phase 10 complete | All 14 reports correct; all 10 KPIs verified |
| G8: Performance Gate | Phase 12 | All spec §44 performance targets met; no slow queries; N+1 eliminated |
| G9: Security Review | Phase 12 | No injection vulnerabilities; auth on all endpoints; no data leakage |
| G10: Tenant Isolation | Phase 12 | Zero cross-company data incidents in all tests |
| G11: Epic Completion | Phase 12 | All 15 Epic Completion Criteria from spec §59 verified PASS |

---

## Risk Management

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| GR + inventory update transaction failure | Medium | High | Unit of Work pattern; both in single SQLAlchemy session; rollback tested |
| Concurrent PO creation duplicate sequence | Low | Medium | SELECT FOR UPDATE on sequence record |
| Approval engine performance at high volume | Low | Medium | Cache resolved matrix rules per company; invalidate on matrix change |
| Cost computation rounding errors | Medium | High | Python Decimal throughout; NUMERIC(15,4) in DB; never use float |
| PPV false-positive on minor cost differences | Low | Low | Configurable PPV threshold (default: > 5%); below threshold is informational |
| Concurrent GRs over-receiving same PO | Medium | High | SELECT FOR UPDATE on PO open-quantity state per line |

### Business Risks

| Risk | Mitigation |
|------|-----------|
| Approval matrix misconfiguration blocks all procurement | Provide default "no approval required" fallback; document matrix configuration |
| Blocked supplier disrupts open POs | Notification to open PO owners on block; POs continue to GR; only new POs blocked |
| Supplier rating gaming | Rating computed from objective GR data only; manual override flagged in audit |

### Architecture Risks

| Risk | Mitigation |
|------|-----------|
| Epic 5 stock interface changes | Pin to Epic 5 PURCHASE_RECEIPT movement type; create integration test that verifies interface contract |
| Approval engine scope creep | Approval engine is purchase-module-internal; not exposed as shared infrastructure in Epic 6 |
| Data model locked by AP requirements | Reserve AP fields (invoice_id, payment_terms_override) as nullable from day 1 |

### Security Risks

| Risk | Mitigation |
|------|-----------|
| Bank detail exposure (Finance Manager only) | Explicit permission gate `purchase:supplier.bank_details:read`; audit all access |
| BOLA on PO approval (approve another company's PO) | company_id scoping on all repository queries; company_id validated at service entry |
| Self-approval bypass | Domain invariant at domain layer + application layer double-check |

### Future Compatibility Risks

| Risk | Mitigation |
|------|-----------|
| Multi-currency PO requires schema change | Reserve `currency_code` and `exchange_rate` as nullable fields on PO from Phase 6 |
| Multi-branch PO requires schema change | Reserve `branch_id` as nullable field on PO from Phase 6 |
| RFQ requires pre-PO stage | PR state machine has extensibility point for QUOTATION_PENDING state (not implemented in Epic 6) |

---

## Success Metrics

| KPI | Target | Measurement |
|-----|--------|-------------|
| Implementation completion | 100% | All 12 phases delivered |
| Test pass rate | 100% | pytest with zero failures |
| Code coverage | ≥ 90% | `modules/purchase/` via pytest-cov |
| Workflow success rate | 100% | All 4 E2E workflows tested |
| Performance targets met | 100% | All spec §44 benchmarks pass |
| Security vulnerabilities | 0 critical | Security review phase |
| Architecture compliance | PASS | Constitution check |
| Documentation completion | 100% | spec, plan, data-model, contracts, quickstart all current |
| Docker verification | PASS | Compose up → migrate → smoke test |
| Epic Completion Criteria | 15/15 | All EC gates from spec §59 PASS |
| Cross-tenant data incidents | 0 | Tenant isolation tests |
| Critical bugs | 0 | No P1 bugs open at PR creation |

---

## Final Implementation Roadmap

```
Epic 6 Specification (spec.md — SSOT)
↓
Architecture Review (Constitution Check — ALL PASS)
↓
Implementation Plan (plan.md — this document)
↓
Research (research.md — architecture decisions)
↓
Data Model (data-model.md — entities, relationships, state machines)
↓
Task Breakdown (tasks.md — /sp.tasks command)
↓
Phase 1: Module Foundation & Scaffolding
↓ [Tests + G2 Gate]
Phase 2: Supplier Master Core
↓ [Tests + G3 Gate]
Phase 3: Supplier Master Enrichment
↓ [Tests]
Phase 4: Procurement Foundation — Approval Engine
↓ [Tests + G4 Gate]
Phase 5: Purchase Requests
↓ [Tests]
Phase 6: Purchase Orders
↓ [Tests + G5 Gate]
Phase 7: Goods Receiving
↓ [Tests + G6 Gate]
Phase 8: Vendor Returns
↓ [Tests]
Phase 9: Purchase Costing
↓ [Tests]
Phase 10: Purchase Intelligence & Reporting
↓ [Tests + G7 Gate]
Phase 11: Integration Foundation, Import/Export & Contracts
↓ [Tests]
Phase 12: Performance, Security, Testing & Epic Closure
↓ [Performance Gate + Security Gate + Tenant Isolation + G8–G11]
Epic 6 PR → Main
```
