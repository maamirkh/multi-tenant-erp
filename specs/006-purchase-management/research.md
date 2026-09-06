# Research: Epic 6 – Purchase Management

**Generated**: 2026-07-25
**Feature**: 006-purchase-management
**Purpose**: Phase 0 architecture decisions — all NEEDS CLARIFICATION resolved before Phase 1

---

## Decision 1: Approval Engine Architecture

**Decision**: Build a general-purpose approval sub-system internal to the purchase module, not a shared platform service.

**Rationale**: The approval engine serves Purchase Requests, Purchase Orders, Vendor Returns (RMAs), and future PO Amendments — all within the purchase domain. A shared cross-module service would require Epic 6 to expose infrastructure that other epics don't yet need. The purchase module owns its approval workflow; if a future epic (Sales, HR) requires approval, it will either reuse the pattern or request extraction at that time.

**Alternatives Considered**:
- Shared approval microservice: Rejected — premature extraction; no other module needs it in Epic 6 scope
- Per-document approval logic: Rejected — code duplication; approval rule changes would need to be made in multiple places

---

## Decision 2: Epic 5 Stock Integration Strategy

**Decision**: GR confirmation calls `InventoryStockService.record_purchase_receipt()` within the same SQLAlchemy session (Unit of Work). Both the GoodsReceipt confirm and the StockMovement INSERT are committed atomically or both rolled back.

**Rationale**: Stock accuracy is a hard requirement. If GR confirmation succeeds but stock update fails (or vice versa), inventory becomes inconsistent. The Epic 5 stock movement interface is designed for exactly this use case (PURCHASE_RECEIPT movement type was reserved in Epic 5 planning).

**Alternatives Considered**:
- Async event-driven stock update: Rejected — introduces window of inconsistency between GR confirm and stock update; saga/compensation adds significant complexity with no benefit at current scale
- Eventual consistency: Rejected — Epic 5 spec mandates atomic consistency for all stock writes

**Implementation Note**: The `InventoryStockService` is imported into the purchase module as a cross-module service call. This is the only cross-module write in Epic 6. All other Epic 5 interactions (product lookups) are read-only.

---

## Decision 3: GR Immutability + Correction Mechanism

**Decision**: Confirmed GoodsReceipts are immutable. Corrections are made exclusively via Vendor Returns (RMA). No GR edit endpoint is created after confirmation.

**Rationale**: Once goods receipt is confirmed, it may have already updated inventory and triggered supplier rating recomputation. Editing a confirmed GR would require retroactive inventory adjustments, rating re-computations, and cost entry updates — creating a cascade of compensating actions. The Vendor Return workflow provides a clean, auditable correction path.

**Alternatives Considered**:
- Allow GR edits before invoice: Rejected — creates audit gap; Finance cannot rely on GR as fixed reference point
- Reversible GR with re-confirmation: Rejected — more complex than creating an RMA; adds no business value

---

## Decision 4: PO Immutability + Amendment Workflow

**Decision**: POs are immutable after approval. Any change requires a PO Amendment, which creates a `POAmendment` record and resets the PO to PENDING_APPROVAL for re-approval through the same approval matrix.

**Rationale**: The Purchase Order is a legal commitment to the supplier. Allowing silent edits after approval would undermine the approval governance. The amendment workflow ensures every material change is approved by the same authority that approved the original.

**Alternatives Considered**:
- Allow minor edits (delivery date, notes) without re-approval: Considered — but "minor" is subjective; simpler to require amendment for all post-approval changes
- Draft-and-replace amendment: Rejected — creates two PO records for the same supplier commitment; confuses receiving

---

## Decision 5: Supplier Rating Architecture

**Decision**: Supplier rating is computed as a weighted composite score from GR performance data (on-time delivery rate, fill rate, rejection rate). It is recalculated automatically after every GR confirmation. Manual override is allowed with an audit trail.

**Computation**:
- On-Time Delivery Rate = GRs confirmed on/before expected delivery ÷ total GRs (last N confirmations)
- Fill Rate = total received quantity ÷ total ordered quantity (last N POs)
- Rejection Rate = rejected GR lines ÷ total GR lines (last N confirmations)
- Composite Score = weighted average (weights configurable per company; default: 40% on-time, 40% fill rate, 20% rejection)

**Alternatives Considered**:
- Manual-only rating: Rejected — prone to bias; not data-driven; stale without updates
- Real-time streaming computation: Rejected — overkill; per-GR recomputation is sufficient at current scale

---

## Decision 6: Number Sequencing Strategy

**Decision**: All purchase document numbers (PR, PO, GR, RMA) are generated by a shared `PurchaseSequenceService` that maintains a `purchase_sequences` table with per-company, per-document-type counters. SELECT FOR UPDATE ensures uniqueness under concurrency.

**Format**: `{PREFIX}-{YEAR}-{SEQUENCE}` (e.g., `PO-2026-000147`). Prefix and year-reset policy are company-configurable.

**Alternatives Considered**:
- UUID as document number: Rejected — not human-readable; suppliers cannot reference by number
- Application-layer timestamp-based numbering: Rejected — race condition under concurrent creation
- Database sequence per table: Considered — simpler, but loses company-specific prefix/format configurability

---

## Decision 7: Feature Flag Reuse Strategy

**Decision**: Epic 6 reuses the `company_feature_flags` table and `FeatureFlagService` established in Epic 5. No new feature flag infrastructure is required. Purchase flags are added as new rows with the `purchase.` prefix convention.

**Rationale**: Epic 5 designed the feature flag system to be extensible across all modules. Adding purchase flags requires only inserting new default records — no schema changes, no new services.

**Flag defaults**: All approval-required flags default to TRUE (safe default — won't accidentally bypass approvals). All channel and AI flags default to FALSE (opt-in). Over-receipt policy defaults to WARN (balanced: warns without blocking operations).

---

## Decision 8: PPV Threshold and Notification

**Decision**: PPV is computed per GR line at confirmation time. If the absolute PPV percentage exceeds a configurable threshold (default: 5%), a `PurchasePriceVarianceDetected` event is published and an in-app notification is sent to the Finance Manager role.

**Rationale**: Small cost differences are normal (rounding, minor price adjustments). Only significant variances warrant Finance attention. The threshold approach prevents notification noise while surfacing genuine cost control issues.

**Formula**: PPV = (GR_unit_cost − PO_unit_cost) × received_quantity. PPV% = PPV ÷ (PO_unit_cost × received_quantity) × 100.

---

## Decision 9: Credit Limit Enforcement Timing

**Decision**: Credit limit is evaluated at **PO approval time**, not at PO creation time.

**Rationale**: The credit limit represents a control on financial commitment, not on intent. A PO in DRAFT state is not yet a commitment. The formal commitment occurs at approval. Evaluating at creation time would prevent users from drafting POs for review, even when credit is available by approval time.

**Enforcement Modes**: BLOCK (prevents approval until outstanding balance + new PO value ≤ limit), WARN (notifies but allows approval), OFF (no check). Configurable per company via `purchase.credit_limit_enforcement` flag.

---

## Decision 10: Procurement Policies Storage

**Decision**: Purchase policies (direct PO allowed, over-receipt policy, approval thresholds) are stored in a `purchase_policies` table (one record per company) rather than in the feature flag table.

**Rationale**: Feature flags are binary (on/off). Policies have richer values (BLOCK/WARN/ALLOW, numeric thresholds, date ranges). Separate storage keeps the feature flag table clean and policies queryable with type safety.

---

## Summary

All 10 architecture decisions are resolved. No NEEDS CLARIFICATION markers remain.

| # | Decision | Chosen Approach |
|---|----------|----------------|
| 1 | Approval Engine | Purchase-module-internal general-purpose engine |
| 2 | Epic 5 Stock Integration | Synchronous Unit of Work — same session, atomic commit |
| 3 | GR Immutability | Confirmed GR = immutable; Vendor Return = correction path |
| 4 | PO Immutability | Approved PO = immutable; Amendment = re-approval trigger |
| 5 | Supplier Rating | Computed from GR data; auto-recompute on GR confirmation |
| 6 | Number Sequencing | `purchase_sequences` table with SELECT FOR UPDATE |
| 7 | Feature Flags | Reuse Epic 5 FeatureFlagService; add `purchase.*` prefix flags |
| 8 | PPV Notification | Compute at GR confirm; threshold-based notification to Finance |
| 9 | Credit Limit Timing | Evaluated at PO approval, not PO creation |
| 10 | Policy Storage | Separate `purchase_policies` table (not feature flags) |
