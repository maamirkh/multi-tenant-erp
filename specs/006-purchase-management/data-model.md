# Data Model: Epic 6 – Purchase Management

**Generated**: 2026-07-25
**Feature**: 006-purchase-management
**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)

---

## Aggregate Roots

Epic 6 defines **6 Aggregate Roots**. Each aggregate root is the sole entry point for mutations to its owned entities.

| # | Aggregate Root | Owned Entities |
|---|---------------|----------------|
| 1 | **Supplier** | SupplierContact, SupplierAddress, BankDetails, SupplierDocument, SupplierRating, CreditLimit, SupplierLeadTime |
| 2 | **PurchaseRequest** | PRLine, PRApprovalRecord |
| 3 | **PurchaseOrder** | POLine, POAdditionalCharge, POAmendment, POApprovalRecord |
| 4 | **GoodsReceipt** | GRLine, PurchaseCostEntry |
| 5 | **VendorReturn** | ReturnLine |
| 6 | **ApprovalMatrix** | MatrixRule, ApprovalLevel, ApprovalDelegate |

---

## Entity Definitions

### Master Data Entities (Phase 1)

---

#### SupplierCategory

Classification tree for grouping suppliers. Hierarchical (parent/child). Max depth: 5 (configurable).

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | FK Company; NOT NULL; indexed |
| code | String(20) | Unique per company; NOT NULL |
| name | String(200) | NOT NULL |
| parent_id | UUID | FK SupplierCategory (nullable — root categories) |
| description | Text | nullable |
| is_deleted | Boolean | NOT NULL; default false |
| deleted_at | DateTime | nullable |
| deleted_by | UUID | nullable |
| created_by | UUID | NOT NULL |
| created_at | DateTime | NOT NULL |
| updated_by | UUID | nullable |
| updated_at | DateTime | nullable |

**Invariants**: Code unique per company. Parent must belong to same company. No circular parent reference. Depth ≤ 5.

---

#### PaymentTerms

Master list of payment terms available to suppliers.

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | FK Company; NOT NULL |
| code | String(20) | Unique per company |
| name | String(100) | NOT NULL |
| net_days | Integer | ≥ 0 |
| discount_days | Integer | nullable |
| discount_percent | Numeric(5,2) | nullable |
| description | Text | nullable |
| is_deleted | Boolean | default false |
| created_by, created_at, updated_by, updated_at | Standard audit fields | |

---

#### PurchaseReasonCode

Typed reason codes for returns, cancellations, rejections.

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| code | String(20) | Unique per company per type |
| name | String(200) | NOT NULL |
| reason_type | Enum | RETURN / CANCELLATION / REJECTION / GENERAL |
| is_active | Boolean | default true |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

---

#### PurchaseSequence

Auto-numbering sequences for purchase documents.

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| document_type | Enum | PO / PR / GR / RMA |
| prefix | String(10) | company-configurable |
| current_value | Integer | NOT NULL; default 0 |
| year | Integer | nullable — if year-based reset enabled |
| reset_yearly | Boolean | default true |
| format_pattern | String(50) | e.g., `{PREFIX}-{YEAR}-{SEQ:06d}` |

**Invariants**: Incremented with SELECT FOR UPDATE. Unique (company_id, document_type, year).

---

#### PurchasePolicy

Company-level procurement policy configuration.

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | Unique; one policy per company |
| direct_po_allowed | Boolean | default false |
| over_receipt_policy | Enum | BLOCK / WARN / ALLOW; default WARN |
| credit_limit_mode | Enum | BLOCK / WARN / OFF; default WARN |
| pr_approval_required | Boolean | default true |
| po_approval_required | Boolean | default true |
| ppv_alert_threshold_percent | Numeric(5,2) | default 5.00 |
| supplier_rating_window | Integer | GR count for rating; default 20 |
| Standard audit fields | | |

---

### Supplier Aggregate (Phases 2–3)

---

#### Supplier (Aggregate Root)

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | FK Company; NOT NULL; indexed |
| supplier_code | String(30) | Unique per company; NOT NULL |
| vendor_code | String(30) | nullable; internal accounting reference |
| legal_name | String(300) | NOT NULL |
| trading_name | String(300) | nullable |
| supplier_type | Enum | GOODS / SERVICES / BOTH |
| status | Enum | DRAFT / ACTIVE / INACTIVE / BLOCKED / ARCHIVED |
| category_id | UUID | FK SupplierCategory; nullable |
| payment_terms_id | UUID | FK PaymentTerms; nullable |
| currency_code | String(3) | default company base currency; future multi-currency |
| tax_registration_number | String(50) | nullable |
| tax_category | String(50) | nullable |
| tax_region | String(100) | nullable |
| website | String(500) | nullable |
| notes | Text | nullable |
| is_preferred | Boolean | default false |
| rating_score | Numeric(3,1) | nullable; 0.0–10.0; computed |
| lead_time_days | Integer | nullable; default supplier lead time |
| branch_id | UUID | nullable; reserved for Branch Management Epic |
| tsvector_search | TSVector | FTS on legal_name, trading_name, supplier_code, vendor_code |
| is_deleted | Boolean | NOT NULL; default false |
| deleted_at, deleted_by | Standard soft-delete fields | |
| created_by, created_at, updated_by, updated_at | Standard audit fields | |

**Invariants**: Code unique per company. Status transitions follow state machine. BLOCKED/ARCHIVED suppliers ineligible for new purchase documents. Preferred flag change restricted to Purchase Manager role.

**Status State Machine**:
```
DRAFT → ACTIVE (activation)
ACTIVE → INACTIVE (deactivation)
ACTIVE → BLOCKED (dispute/compliance block)
INACTIVE → ACTIVE (reactivation)
BLOCKED → ACTIVE (block resolved with reason)
ACTIVE → ARCHIVED (decommission — only when no open POs)
INACTIVE → ARCHIVED
```

---

#### SupplierContact

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| supplier_id | UUID | FK Supplier |
| first_name | String(100) | NOT NULL |
| last_name | String(100) | NOT NULL |
| role | String(100) | nullable (e.g., "Accounts Receivable") |
| email | String(255) | nullable |
| phone | String(50) | nullable |
| mobile | String(50) | nullable |
| is_primary | Boolean | default false |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

---

#### SupplierAddress

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| supplier_id | UUID | FK Supplier |
| address_type | Enum | BILLING / SHIPPING / REGISTERED / OTHER |
| address_line_1 | String(300) | NOT NULL |
| address_line_2 | String(300) | nullable |
| city | String(100) | NOT NULL |
| state | String(100) | nullable |
| postal_code | String(20) | nullable |
| country_code | String(2) | ISO 3166-1 alpha-2 |
| is_default | Boolean | default false |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

---

#### BankDetails

Finance Manager restricted. One record per banking relationship per supplier.

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| supplier_id | UUID | FK Supplier |
| bank_name | String(200) | NOT NULL |
| account_name | String(200) | NOT NULL |
| account_number | String(50) | NOT NULL |
| iban | String(34) | nullable |
| swift_bic | String(11) | nullable |
| routing_number | String(20) | nullable |
| bank_country | String(2) | NOT NULL |
| currency_code | String(3) | default supplier currency |
| is_primary | Boolean | default false |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

---

#### SupplierRating

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| supplier_id | UUID | FK Supplier; Unique (one active rating per supplier) |
| on_time_rate | Numeric(5,2) | 0.00–100.00 |
| fill_rate | Numeric(5,2) | 0.00–100.00 |
| rejection_rate | Numeric(5,2) | 0.00–100.00 |
| composite_score | Numeric(3,1) | 0.0–10.0 |
| gr_count_window | Integer | number of GRs used for computation |
| manual_override_score | Numeric(3,1) | nullable; set by Purchase Manager |
| manual_override_reason | Text | nullable |
| last_computed_at | DateTime | NOT NULL |
| Standard audit fields | | |

---

#### CreditLimit

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| supplier_id | UUID | FK Supplier; Unique |
| credit_limit_amount | Numeric(15,2) | ≥ 0 |
| currency_code | String(3) | default company base currency |
| enforcement_mode | Enum | BLOCK / WARN / OFF (overrides company policy for this supplier) |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

---

#### SupplierDocument

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| supplier_id | UUID | FK Supplier |
| document_type | String(100) | e.g., "Trade License", "ISO Certificate" |
| document_number | String(100) | nullable |
| issue_date | Date | nullable |
| expiry_date | Date | nullable |
| file_url | String(1000) | S3/storage path |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

---

### Approval Aggregate (Phase 4)

---

#### ApprovalMatrix (Aggregate Root)

One matrix per document type per company.

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| document_type | Enum | PURCHASE_REQUEST / PURCHASE_ORDER / VENDOR_RETURN |
| name | String(200) | NOT NULL |
| is_active | Boolean | default true |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

---

#### MatrixRule

A condition that routes documents to a specific approval level.

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| matrix_id | UUID | FK ApprovalMatrix |
| company_id | UUID | NOT NULL |
| condition_type | Enum | AMOUNT_RANGE / CATEGORY / DEPARTMENT / ALWAYS |
| min_amount | Numeric(15,2) | nullable |
| max_amount | Numeric(15,2) | nullable |
| category_id | UUID | nullable; FK SupplierCategory |
| approval_level | Integer | 1, 2, 3... |
| approval_mode | Enum | SEQUENTIAL / PARALLEL |
| Standard audit fields | | |

---

#### ApprovalLevel

The approvers assigned to a specific level in the matrix.

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| rule_id | UUID | FK MatrixRule |
| company_id | UUID | NOT NULL |
| level_number | Integer | NOT NULL |
| approver_type | Enum | ROLE / USER |
| approver_role | String(50) | nullable (role identifier) |
| approver_user_id | UUID | nullable |
| escalation_days | Integer | default 3 |
| is_deleted | Boolean | default false |

---

#### ApprovalRecord

Immutable once submitted. One record per approval action.

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| document_type | Enum | PURCHASE_REQUEST / PURCHASE_ORDER / VENDOR_RETURN |
| document_id | UUID | NOT NULL |
| level_number | Integer | NOT NULL |
| approver_id | UUID | NOT NULL (must ≠ requestor_id) |
| action | Enum | APPROVED / REJECTED / ABSTAINED |
| comment | Text | nullable; required on REJECTED |
| is_emergency_bypass | Boolean | default false |
| bypass_justification | Text | nullable |
| actioned_at | DateTime | NOT NULL |
| company_id, created_at | Audit fields | |

**Invariants**: approver_id ≠ requestor_id (self-approval prevention — enforced at domain layer). Record is immutable once created.

---

#### ApprovalDelegate

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| delegator_id | UUID | FK User |
| delegate_id | UUID | FK User |
| valid_from | DateTime | NOT NULL |
| valid_until | DateTime | NOT NULL |
| document_type | Enum | nullable (ALL if null) |
| is_active | Boolean | default true |
| Standard audit fields | | |

---

### Purchase Request Aggregate (Phase 5)

---

#### PurchaseRequest (Aggregate Root)

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL; indexed |
| pr_number | String(30) | NOT NULL; unique per company |
| title | String(300) | NOT NULL |
| status | Enum | DRAFT / SUBMITTED / UNDER_REVIEW / APPROVED / REJECTED / CANCELLED |
| requestor_id | UUID | FK User |
| department | String(100) | nullable |
| required_by_date | Date | nullable |
| notes | Text | nullable |
| total_estimated_cost | Numeric(15,2) | computed from lines |
| currency_code | String(3) | default company base currency |
| converted_to_po_id | UUID | nullable; FK PurchaseOrder |
| branch_id | UUID | nullable; reserved |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

**Status State Machine**:
```
DRAFT → SUBMITTED
SUBMITTED → UNDER_REVIEW (approval routing)
UNDER_REVIEW → APPROVED
UNDER_REVIEW → REJECTED
SUBMITTED → CANCELLED (before approval starts)
DRAFT → CANCELLED
```

---

#### PRLine

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| pr_id | UUID | FK PurchaseRequest |
| line_number | Integer | NOT NULL |
| product_id | UUID | FK Product (Epic 5); nullable (free-text item allowed) |
| product_description | String(500) | NOT NULL |
| quantity | Numeric(15,3) | > 0 |
| uom_id | UUID | FK UOM (Epic 5) |
| estimated_unit_cost | Numeric(15,4) | ≥ 0 |
| estimated_line_total | Numeric(15,2) | computed |
| notes | Text | nullable |
| is_deleted | Boolean | default false |

---

### Purchase Order Aggregate (Phase 6)

---

#### PurchaseOrder (Aggregate Root)

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL; indexed |
| po_number | String(30) | NOT NULL; unique per company |
| status | Enum | DRAFT / PENDING_APPROVAL / APPROVED / PARTIALLY_RECEIVED / FULLY_RECEIVED / CLOSED / CANCELLED |
| supplier_id | UUID | FK Supplier; NOT NULL |
| purchase_request_id | UUID | FK PurchaseRequest; nullable |
| created_by | UUID | FK User |
| payment_terms_id | UUID | FK PaymentTerms; nullable |
| delivery_address_id | UUID | FK SupplierAddress; nullable |
| expected_delivery_date | Date | nullable |
| supplier_reference | String(100) | nullable |
| currency_code | String(3) | default company base currency; future multi-currency |
| exchange_rate | Numeric(15,6) | nullable; reserved for Epic 10 |
| subtotal | Numeric(15,2) | computed from lines |
| total_charges | Numeric(15,2) | computed from charges |
| total_discounts | Numeric(15,2) | computed from discounts |
| tax_amount | Numeric(15,2) | captured only; not computed |
| total | Numeric(15,2) | computed |
| notes | Text | nullable |
| branch_id | UUID | nullable; reserved |
| version | Integer | NOT NULL; default 1; optimistic lock |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

**Status State Machine**:
```
DRAFT → PENDING_APPROVAL
PENDING_APPROVAL → APPROVED
PENDING_APPROVAL → REJECTED → DRAFT (revise and resubmit)
APPROVED → PARTIALLY_RECEIVED (first GR confirmed)
APPROVED / PARTIALLY_RECEIVED → FULLY_RECEIVED (all lines received)
FULLY_RECEIVED → CLOSED
APPROVED / PARTIALLY_RECEIVED → CLOSED (manual close)
DRAFT / PENDING_APPROVAL / APPROVED → CANCELLED
```

**Invariants**: APPROVED+ status = immutable (no direct field edits). Supplier must be ACTIVE. Amendment required for any post-approval change.

---

#### POLine

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| po_id | UUID | FK PurchaseOrder |
| pr_line_id | UUID | FK PRLine; nullable |
| line_number | Integer | NOT NULL |
| product_id | UUID | FK Product (Epic 5) |
| product_description | String(500) | NOT NULL |
| quantity_ordered | Numeric(15,3) | > 0 |
| quantity_received | Numeric(15,3) | default 0; updated on GR confirmation |
| quantity_rejected | Numeric(15,3) | default 0 |
| open_quantity | Numeric(15,3) | computed: ordered − received |
| uom_id | UUID | FK UOM (Epic 5) |
| unit_cost | Numeric(15,4) | ≥ 0 |
| line_discount_percent | Numeric(5,2) | nullable |
| line_discount_amount | Numeric(15,2) | nullable |
| line_total | Numeric(15,2) | computed |
| tax_code | String(50) | nullable; tax readiness |
| tax_rate | Numeric(5,2) | nullable |
| tax_amount | Numeric(15,2) | nullable; captured not computed |
| tax_inclusive | Boolean | default false |
| notes | Text | nullable |
| is_deleted | Boolean | default false |

---

#### POAdditionalCharge

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| po_id | UUID | FK PurchaseOrder |
| charge_type | Enum | FREIGHT / HANDLING / INSURANCE / OTHER |
| description | String(200) | NOT NULL |
| amount | Numeric(15,2) | ≥ 0 |
| is_deleted | Boolean | default false |

---

#### POAmendment

Immutable record of each amendment applied to a PO.

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| po_id | UUID | FK PurchaseOrder |
| amendment_number | Integer | sequential per PO |
| reason | Text | NOT NULL |
| change_summary | JSON | before/after field diff |
| requested_by | UUID | FK User |
| approved_by | UUID | nullable |
| approved_at | DateTime | nullable |
| status | Enum | PENDING / APPROVED / REJECTED |
| created_at | DateTime | NOT NULL |

---

### Goods Receipt Aggregate (Phase 7)

---

#### GoodsReceipt (Aggregate Root)

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL; indexed |
| gr_number | String(30) | NOT NULL; unique per company |
| status | Enum | DRAFT / CONFIRMED |
| po_id | UUID | FK PurchaseOrder; NOT NULL |
| supplier_id | UUID | FK Supplier; NOT NULL |
| received_by | UUID | FK User |
| received_at | DateTime | nullable |
| delivery_note_number | String(100) | nullable |
| notes | Text | nullable |
| landed_cost_ready | Boolean | NOT NULL; default true; hook for Epic 8.x |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

**Invariants**: GR only against APPROVED or PARTIALLY_RECEIVED PO. CONFIRMED = immutable. Confirmation is atomic with Epic 5 stock movement write.

---

#### GRLine

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| gr_id | UUID | FK GoodsReceipt |
| po_line_id | UUID | FK POLine |
| product_id | UUID | FK Product (Epic 5) |
| quantity_received | Numeric(15,3) | ≥ 0 |
| quantity_rejected | Numeric(15,3) | default 0 |
| rejection_reason_id | UUID | FK PurchaseReasonCode; nullable |
| unit_cost | Numeric(15,4) | captured at GR; may differ from PO unit cost |
| ppv_amount | Numeric(15,2) | computed: (gr_cost − po_cost) × qty_received |
| ppv_percentage | Numeric(6,2) | computed |
| notes | Text | nullable |
| is_deleted | Boolean | default false |

---

#### PurchaseCostEntry

Immutable cost snapshot created on GR confirmation. One per GR.

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| gr_id | UUID | FK GoodsReceipt; Unique |
| po_id | UUID | FK PurchaseOrder |
| supplier_id | UUID | FK Supplier |
| cost_date | Date | date of GR confirmation |
| subtotal | Numeric(15,2) | |
| total_charges | Numeric(15,2) | |
| total_discounts | Numeric(15,2) | |
| tax_amount | Numeric(15,2) | |
| total | Numeric(15,2) | |
| credit_note_pending | Boolean | default false; set on RMA completion |
| invoice_id | UUID | nullable; reserved for Epic 8 AP |
| created_at | DateTime | NOT NULL |

---

### Vendor Return Aggregate (Phase 8)

---

#### VendorReturn (Aggregate Root)

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL; indexed |
| rma_number | String(30) | NOT NULL; unique per company |
| status | Enum | DRAFT / SUBMITTED / APPROVED / DISPATCHED / COMPLETED / CANCELLED |
| gr_id | UUID | FK GoodsReceipt; NOT NULL |
| supplier_id | UUID | FK Supplier |
| initiated_by | UUID | FK User |
| reason_id | UUID | FK PurchaseReasonCode |
| notes | Text | nullable |
| replacement_po_id | UUID | FK PurchaseOrder; nullable |
| credit_note_pending | Boolean | default false |
| dispatched_at | DateTime | nullable |
| completed_at | DateTime | nullable |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

**Status State Machine**:
```
DRAFT → SUBMITTED
SUBMITTED → APPROVED
SUBMITTED → CANCELLED
APPROVED → DISPATCHED (triggers inventory deduction)
DISPATCHED → COMPLETED
APPROVED → CANCELLED
```

**Invariants**: Return quantity per line ≤ accepted quantity on referenced GR line. RMA only against CONFIRMED GR.

---

#### ReturnLine

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| return_id | UUID | FK VendorReturn |
| gr_line_id | UUID | FK GRLine |
| product_id | UUID | FK Product (Epic 5) |
| quantity_returned | Numeric(15,3) | > 0; ≤ gr_line.accepted_quantity |
| reason_id | UUID | FK PurchaseReasonCode; nullable |
| notes | Text | nullable |
| is_deleted | Boolean | default false |

---

## State Machines Summary

| Document | States | Key Invariants |
|----------|--------|---------------|
| Supplier | DRAFT → ACTIVE → INACTIVE / BLOCKED → ACTIVE → ARCHIVED | Approved by manager; open PO guard on archive |
| PurchaseRequest | DRAFT → SUBMITTED → UNDER_REVIEW → APPROVED / REJECTED | Self-approval prevention; approved required for conversion |
| PurchaseOrder | DRAFT → PENDING → APPROVED → PARTIALLY/FULLY RECEIVED → CLOSED / CANCELLED | Immutable after APPROVED; no cancel after GR |
| GoodsReceipt | DRAFT → CONFIRMED | Immutable after CONFIRMED; atomic stock update |
| VendorReturn | DRAFT → SUBMITTED → APPROVED → DISPATCHED → COMPLETED | Return qty ≤ GR accepted qty; inventory reduced on DISPATCHED |

---

## Cross-Module References

| Field | Owned By | Referenced In |
|-------|----------|---------------|
| Product.id | Epic 5 (Inventory) | PRLine, POLine, GRLine, ReturnLine |
| UOM.id | Epic 5 (Inventory) | PRLine, POLine |
| StockMovement.INSERT (PURCHASE_RECEIPT) | Epic 5 (Inventory) | GoodsReceipt confirmation |
| StockMovement.INSERT (PURCHASE_RETURN_OUTBOUND) | Epic 5 (Inventory) | VendorReturn dispatch |
| User.id | Epic 2/4 | All created_by, approver_id, requestor_id fields |
| Company.id | Epic 3 | All company_id fields |

---

## Reserved Fields for Future Epics

| Field | Entity | Reserved For |
|-------|--------|-------------|
| branch_id | Supplier, PO, PR, GR | Branch Management Epic |
| currency_code | PO, GR | Epic 10 (Multi-Currency) |
| exchange_rate | PO | Epic 10 (Multi-Currency) |
| invoice_id | PurchaseCostEntry | Epic 8 (Accounts Payable) |
| landed_cost_ready | GoodsReceipt | Epic 8.x (Landed Cost) |
| tax_code, tax_rate, tax_amount | POLine, GRLine | Epic 8 (Tax Computation) |
| credit_note_pending | VendorReturn, PurchaseCostEntry | Epic 8 (AP credit note matching) |
