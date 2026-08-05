# Research: Epic 7 – Sales Management

**Generated**: 2026-07-30
**Feature**: 007-sales-management
**Purpose**: Phase 0 architecture decisions — all NEEDS CLARIFICATION resolved before Phase 1

---

## Decision 1: Approval Engine Reuse from Epic 6

**Decision**: Reuse the approval pattern established in Epic 6 (Purchase Management) by building an analogous approval sub-system internal to the sales module. The sales module owns its approval workflow; the approval matrix configuration, approval records, and self-approval prevention follow the same design as Epic 6.

**Rationale**: Epic 6 demonstrated the approval engine pattern successfully for Purchase Requests and Purchase Orders. The Sales Order approval requirement is structurally identical: configurable multi-level approval based on document value and customer category. Building the sales approval as an internal sub-system (not importing Epic 6's approval engine) maintains module independence while preserving pattern consistency. If a shared approval platform service is needed in the future, both implementations share the same contract.

**Alternatives Considered**:
- Import Epic 6 approval engine: Rejected — creates tight coupling between purchase and sales modules; the modules should remain independently deployable
- Shared approval microservice: Rejected — premature extraction; only two modules need approval at this point
- No approval (auto-approve everything): Rejected — spec mandates configurable approval workflow with credit check integration

---

## Decision 2: Inventory Integration Strategy (Sales → Epic 5)

**Decision**: Delivery Note dispatch and Sales Return receipt call Epic 5's `InventoryStockService` within the same SQLAlchemy session (Unit of Work). Both the sales document state change and the StockMovement INSERT are committed atomically or both rolled back.

**Rationale**: Inventory accuracy is a hard requirement. If delivery dispatch succeeds but stock deduction fails, inventory becomes overstated. Epic 5 already provides stock movement types for sales: `SALES_RESERVATION`, `SALES_DISPATCH`, `SALES_RESERVATION_RELEASE`, and `SALES_RETURN_INBOUND`. This mirrors the transactional pattern established in Epic 6 for Goods Receipt confirmation.

**Alternatives Considered**:
- Async event-driven stock update: Rejected — introduces window of inconsistency; same reasoning as Epic 6 Decision 2
- Eventual consistency: Rejected — Epic 5 spec mandates atomic consistency for all stock writes
- Saga pattern: Rejected — unnecessary complexity at current scale; monolith architecture permits transactional consistency

**Implementation Note**: The sales module imports `InventoryStockService` for three cross-module writes: (1) stock reservation on DN creation, (2) stock deduction on DN dispatch, (3) stock restock on Sales Return receipt. Product lookups (availability check, price lookup) are read-only calls.

---

## Decision 3: Price Resolution Architecture

**Decision**: Implement the 7-level price resolution as a `PricingService` within the sales module. The service evaluates prices in priority order (Manual Override → Customer-Specific → Customer Group → Customer Category → Active Price List → Default Price List → Product Base Price) and returns the resolved price with source metadata. Prices are captured at document creation time and are immutable thereafter.

**Rationale**: The "price at point-of-sale" principle from the spec means that the resolved price is stored on the document line and never recalculated. The `PricingService` is called only during document creation or line addition — not on retrieval. This ensures historical document accuracy regardless of subsequent price list changes.

**Alternatives Considered**:
- Dynamic price recalculation on every read: Rejected — violates "price at point-of-sale" invariant; breaks audit trail
- Store only price list reference, resolve at display time: Rejected — same problem as above; also introduces performance overhead
- Separate pricing microservice: Rejected — premature extraction; pricing is intrinsic to sales domain

---

## Decision 4: Invoice Sequencing Under Concurrency

**Decision**: Invoice numbers use a database-level advisory lock (SELECT FOR UPDATE on a per-company sequence record in `sales_sequences` table) to ensure gap-free sequential numbering under concurrent invoice generation. Cancelled invoices retain their number with void status — no number is ever reused.

**Rationale**: Regulatory compliance in many jurisdictions requires gap-free invoice sequences. Under concurrent invoice generation by multiple users, a simple auto-increment could produce gaps if a transaction rolls back. The advisory lock ensures only one invoice number is generated at a time per company, and the number is committed only when the invoice is successfully created.

**Alternatives Considered**:
- PostgreSQL SEQUENCE: Rejected — sequences do not roll back with transactions; a failed insert would create a gap
- Application-level counter with retry: Rejected — race conditions under high concurrency; less reliable than DB-level lock
- UUID-based invoicing: Rejected — invoices require human-readable sequential numbers for regulatory compliance

---

## Decision 5: Credit Check Timing

**Decision**: Credit check is evaluated at order approval time, not at order creation time. The credit evaluation considers: customer credit limit, current outstanding balance (sum of issued unpaid invoices — future AR), and sum of all pending approved orders. If the total exceeds the credit limit, approval is blocked.

**Rationale**: Creating an order in DRAFT status should be frictionless — the sales representative may need to prepare the order before seeking customer approval. The credit control gate is at the approval step, where a manager or the system makes the commitment decision. This matches the spec's credit hold behaviour (§14.7) and is consistent with SAP/Oracle ERP credit management patterns.

**Alternatives Considered**:
- Credit check at order creation: Rejected — blocks draft orders unnecessarily; sales reps need to prepare orders for customers who may resolve credit issues before submission
- Credit check at delivery: Rejected — too late; commitment is made at approval; changing course after approval wastes resources
- No credit check (future): Rejected — spec mandates credit control in Epic 7

**Implementation Note**: Since Accounts Receivable (Epic 8+) does not exist yet, the "outstanding balance" in the initial implementation is the sum of all issued (unpaid) invoices for the customer. Once AR is implemented, the credit check service will be extended to use the AR balance.

---

## Decision 6: Number Sequencing Strategy

**Decision**: All sales document numbers (SQ, SO, DN, SI, SR) are generated by a shared `SalesSequenceService` that maintains a `sales_sequences` table with per-company, per-document-type counters. SELECT FOR UPDATE ensures uniqueness under concurrency. Invoice sequences use advisory locks for gap-free guarantee.

**Format**: `{PREFIX}-{YYYYMMDD}-{SEQUENCE}` (e.g., `SO-20260730-0001`). Prefix and format are company-configurable.

**Rationale**: Consistent with Epic 6's `PurchaseSequenceService` pattern. Document numbers must be human-readable, sequential, and company-unique. The daily-date format provides natural chronological grouping and prevents sequence number overflow across years.

**Alternatives Considered**:
- Shared sequence service across Purchase + Sales: Rejected — modules should own their numbering; different format requirements
- UUID-only: Rejected — sales documents require human-readable numbers for customer-facing use

---

## Decision 7: Delivery Note → Invoice Relationship

**Decision**: Multiple delivery notes for the same sales order can be consolidated into a single invoice, or invoiced individually. The invoice line references the DN line it covers. This supports both "invoice per delivery" and "consolidated monthly invoice" patterns.

**Rationale**: Enterprise customers often prefer consolidated invoicing (one invoice per month covering all deliveries). Retail customers may prefer per-delivery invoicing. The many-to-one relationship (DN → Invoice) accommodates both patterns. The spec supports this in §18.3.

**Alternatives Considered**:
- One-to-one DN-to-Invoice: Rejected — forces one invoice per delivery; excessive paperwork for high-volume customers
- Invoice directly from SO (no DN reference): Supported as secondary mode — for services and advance billing where no physical delivery occurs

---

## Decision 8: Sales Return → Inventory Restock Strategy

**Decision**: When a Sales Return transitions to RECEIVED status, accepted items are restocked via Epic 5 `StockMovement(SALES_RETURN_INBOUND)` within the same transaction. Rejected items (damaged, defective) are recorded but not restocked. A future quarantine workflow may handle rejected items.

**Rationale**: Restocking on receipt (not on approval) ensures physical verification before inventory update. This mirrors Epic 6's Vendor Return pattern where inventory is reduced on dispatch confirmation.

**Alternatives Considered**:
- Restock on approval (before receipt): Rejected — inventory would reflect stock not yet physically received
- Restock on completion: Rejected — delays inventory accuracy; receipt is the physical confirmation point
- Manual restock (no auto-restock): Rejected — error-prone; inconsistent with the automated inventory integration pattern
