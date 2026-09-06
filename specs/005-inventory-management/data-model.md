# Data Model: Epic 5 – Inventory Management

**Phase**: Phase 1 — Design & Contracts
**Date**: 2026-07-20
**Branch**: `005-inventory-management`
**Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

---

> **Note**: This is a **conceptual data model** — entity definitions, relationships, and state machines. No SQL DDL, no ORM class names, no migration scripts.

---

## 1. Aggregate Roots and Their Entities

### 1.1 Product Aggregate

**Root**: Product

| Entity | Role | Key Relationships |
| --- | --- | --- |
| Product | Aggregate Root | owns Variants, Images, CustomFieldValues, Tags, Barcodes |
| ProductVariant | Child entity | belongs to Product; has own Barcodes, Images |
| ProductImage | Value Object | belongs to Product or Variant |
| ProductBarcode | Value Object | belongs to Product or Variant; unique per company |
| ProductTag | Association | many-to-many with Tag |
| Tag | Shared entity | shared across all products in company |
| CustomFieldValue | Value Object | belongs to Product |
| InternalNote | Child entity | append-only child of Product |
| SearchKeyword | Value Object | belongs to Product |

**Invariants enforced by Product Aggregate Root**:
- SKU unique per company
- Barcode unique per company
- Status transitions follow defined lifecycle
- Mandatory fields complete before activation

---

### 1.2 Category Aggregate

**Root**: Category

| Entity | Role | Key Relationships |
| --- | --- | --- |
| Category | Aggregate Root | may have parent Category (tree) |
| SubCategory | Child or alias | same entity as Category with parent_id set |

**Invariants**:
- Code unique per company
- No circular parent references
- Deactivation blocked when assigned to Active products

---

### 1.3 Brand Aggregate

**Root**: Brand

| Entity | Role |
| --- | --- |
| Brand | Aggregate Root |

**Invariants**: Code unique per company; deactivation blocked when assigned to Active products

---

### 1.4 Unit of Measure Aggregate

**Root**: UOM

| Entity | Role |
| --- | --- |
| UOM | Aggregate Root |
| UOMConversion | Child entity — conversion factor between two UOM within same product |

**Invariants**: Conversion factor > 0; base UOM cannot be deleted if product references it

---

### 1.5 Attribute Aggregate

**Root**: AttributeDefinition

| Entity | Role | Key Relationships |
| --- | --- | --- |
| AttributeDefinition | Aggregate Root | defines name, type, options |
| AttributeSet | Child group | groups multiple AttributeDefinitions |
| AttributeSetMembership | Association | links AttributeDefinition to AttributeSet |

---

### 1.6 Warehouse Aggregate

**Root**: Warehouse

| Entity | Role | Key Relationships |
| --- | --- | --- |
| Warehouse | Aggregate Root | has many WarehouseLocations |
| WarehouseLocation | Child entity | belongs to Warehouse |

**Future extension point**: A `branch_id` field is reserved on Warehouse (nullable) per spec §16.10. When Branch Management is introduced, this field will be populated without schema change.

**Invariants**:
- Code unique per company
- Cannot be archived with non-zero stock

---

### 1.7 Stock Position Aggregate

**Root**: StockPosition (per product/variant × warehouse)

| Property | Description |
| --- | --- |
| current_quantity | Materialised total quantity (atomic with ledger) |
| reserved_quantity | Quantity committed to open orders |
| damaged_quantity | Quantity classified as damaged |
| available_quantity | Derived: current − reserved − damaged |
| safety_stock | Threshold for Safety Stock alert |
| minimum_stock | Lower bound threshold |
| maximum_stock | Upper bound threshold |
| reorder_level | Trigger level for reorder suggestion |
| unit_cost | Current unit cost (WAC value or last FIFO layer cost) |
| currency_code | Always Base Currency in Epic 5; field present for future multi-currency (per spec §15.18) |

**Invariants**: available_quantity ≥ 0 (unless negative stock policy allows otherwise); reserved ≤ current; damaged ≤ current

---

### 1.8 Stock Movement Aggregate (Ledger Entry)

**Root**: StockMovement — **immutable** once created

| Property | Description |
| --- | --- |
| movement_type | OPENING / PURCHASE_RECEIPT / SALE_DISPATCH / ADJUSTMENT / TRANSFER_OUT / TRANSFER_IN / RETURN_INBOUND / RETURN_OUTBOUND / REVALUATION |
| quantity | Always positive; direction implied by movement_type |
| direction | IN or OUT |
| unit_cost | Cost at time of movement; currency_code accompanies (spec §15.18 / BR-029) |
| currency_code | Base Currency in Epic 5 |
| reference_type | PURCHASE_ORDER / SALE_ORDER / ADJUSTMENT / TRANSFER / MANUAL |
| reference_id | Nullable FK to the source document (populated in future Epics) |
| warehouse_id | The warehouse where the movement occurred |
| product_id / variant_id | The product or variant affected |
| user_id | The operator who performed or triggered the movement |
| performed_at | UTC timestamp with full precision |

**Invariant**: This entity has no update or delete operations — it is append-only.

---

### 1.9 Inventory Adjustment Aggregate

**Root**: InventoryAdjustment

| Property | Description |
| --- | --- |
| product_id / variant_id | Product being adjusted |
| warehouse_id | Warehouse where adjustment applies |
| adjustment_type | INCREASE / DECREASE |
| quantity | Absolute quantity change |
| reason_code | From approved reason code registry |
| notes | Free text from submitter |
| status | DRAFT / PENDING_APPROVAL / APPROVED / REJECTED |
| submitted_by | user_id |
| approved_by | user_id (nullable if approval not required) |
| old_quantity | Quantity before adjustment (recorded at submission) |
| new_quantity | Quantity after adjustment (calculated at approval) |

**State machine**: DRAFT → PENDING_APPROVAL (if approval enabled) → APPROVED / REJECTED; or DRAFT → APPROVED (if direct adjustment enabled)

---

### 1.10 Stock Transfer Aggregate

**Root**: StockTransfer

| Property | Description |
| --- | --- |
| source_warehouse_id | Where stock is dispatched from |
| destination_warehouse_id | Where stock is received |
| status | DRAFT / IN_TRANSIT / COMPLETED / CANCELLED |
| initiated_by / dispatched_by / received_by | user_id at each step |
| Transfer Lines | child collection: product/variant × quantity pairs |

**State machine**: DRAFT → IN_TRANSIT → COMPLETED; DRAFT → CANCELLED; IN_TRANSIT → CANCELLED (with reversal movement)

---

### 1.11 Inventory Snapshot Aggregate

**Root**: InventorySnapshot — **immutable** once generated

| Entity | Role |
| --- | --- |
| InventorySnapshot | Root: timestamp, triggered_by, company_id |
| InventorySnapshotLine | Child: product, variant, warehouse, quantity, unit_cost, total_value, currency_code |

---

### 1.12 Reorder Rule

| Property | Description |
| --- | --- |
| product_id / variant_id | Product this rule applies to |
| warehouse_id | Nullable — if null, applies to all warehouses for this product |
| reorder_level | Stock level at which suggestion is generated |
| reorder_quantity | Default quantity to suggest |
| is_active | Boolean |

---

### 1.13 Low Stock Alert

| Property | Description |
| --- | --- |
| product_id / variant_id | Product triggering the alert |
| warehouse_id | Warehouse where the threshold was breached |
| alert_type | LOW_STOCK / OUT_OF_STOCK / SAFETY_STOCK_BREACH / OVERSTOCK |
| status | OPEN / ACKNOWLEDGED / RESOLVED |
| current_quantity | Stock level at alert time |
| threshold_quantity | The threshold that was breached |
| raised_at / resolved_at | Timestamps |

---

## 2. Master Data Entities

| Entity | Key Properties | Uniqueness |
| --- | --- | --- |
| Category | code, name, parent_id (nullable), status, sort_order | code per company |
| Brand | code, name, country_of_origin (optional), logo_url, status | code per company |
| UOM | code, name, uom_type, status | code per company |
| AttributeDefinition | name, data_type, options (JSON for dropdown/multiselect), is_required | name per company |
| AttributeSet | name, product_type_scope or category_scope | name per company |
| CustomFieldDefinition | entity_type, field_key, field_label, data_type, options, scope | field_key per company per scope |
| ReasonCode | code, label, applies_to (ADJUSTMENT/DAMAGE/RETURN), is_active | code per company |

---

## 3. Entity Relationship Summary (Conceptual)

```
Company
  ├── has many → Category (tree)
  ├── has many → Brand
  ├── has many → UOM
  ├── has many → AttributeDefinition → AttributeSet
  ├── has many → CustomFieldDefinition
  ├── has many → Tag
  ├── has many → ReasonCode
  ├── has many → Warehouse → WarehouseLocation
  │                └── (future: belongs to Branch)
  ├── has many → Product
  │     ├── belongs to Category, Brand
  │     ├── has Base UOM (from UOM)
  │     ├── has many → ProductVariant
  │     │     └── has SKU, Barcode(s), Images, AttributeValues
  │     ├── has many → ProductImage
  │     ├── has many → ProductBarcode
  │     ├── has many → CustomFieldValue
  │     ├── has many → InternalNote
  │     ├── has many → SearchKeyword
  │     └── has many → ProductTag → Tag
  ├── has many → StockPosition (product/variant × warehouse)
  ├── has many → StockMovement (immutable ledger)
  ├── has many → InventoryAdjustment
  ├── has many → StockTransfer → StockTransferLine
  ├── has many → InventorySnapshot → InventorySnapshotLine
  ├── has many → ReorderRule
  └── has many → LowStockAlert
```

---

## 4. State Machines

### 4.1 Product Status

```
DRAFT ──(activate)──► ACTIVE ──(deactivate)──► INACTIVE
                          │                        │
                          │ (discontinue)          │ (reactivate)
                          ▼                        ▼
                    DISCONTINUED              ACTIVE (again)
                          │
                          ▼ (archive) ← any inactive/discontinued state
                       ARCHIVED (terminal)
```

### 4.2 Inventory Adjustment Status

```
DRAFT ──(submit)──► PENDING_APPROVAL ──(approve)──► APPROVED
                            │                            │
                            │ (reject)                   │ (creates ledger entry)
                            ▼                            ▼
                        REJECTED                   StockMovement created
```

*If adjustment approval feature flag is disabled: DRAFT → APPROVED directly*

### 4.3 Stock Transfer Status

```
DRAFT ──(dispatch)──► IN_TRANSIT ──(receive)──► COMPLETED
  │                       │
  │ (cancel)              │ (cancel with reversal)
  ▼                       ▼
CANCELLED            CANCELLED (reversal movement created at source)
```

### 4.4 Low Stock Alert Status

```
OPEN ──(acknowledged)──► ACKNOWLEDGED ──(resolved)──► RESOLVED
  └──(auto-resolve when stock restocked)──────────────► RESOLVED
```

---

## 5. Audit Fields (All Entities)

Every entity includes the following audit fields as a shared pattern:

| Field | Type | Description |
| --- | --- | --- |
| id | UUID | Primary key |
| company_id | UUID | Tenant isolation key — mandatory on every record |
| created_at | TimestampTZ | UTC creation timestamp |
| updated_at | TimestampTZ | UTC last update timestamp |
| created_by | UUID | User who created the record |
| updated_by | UUID | User who last updated the record |
| is_deleted | Boolean | Soft delete flag (default: false) |
| deleted_at | TimestampTZ | Nullable — set when soft-deleted |
| deleted_by | UUID | Nullable — set when soft-deleted |

---

## 6. Currency Readiness Fields

Per spec §15.18 (BR-029), all monetary values carry a currency code:

| Monetary Field | Accompanies | Value in Epic 5 |
| --- | --- | --- |
| unit_cost | currency_code | Base Currency of company |
| total_value | currency_code | Base Currency of company |
| valuation_amount | currency_code | Base Currency of company |

The `currency_code` field is populated from the company's base_currency at write time. No conversion logic exists in Epic 5 — this field enables future multi-currency reporting without schema migration.

---

## 7. Future Extension Points

| Extension | Reserved Field / Pattern | Activated By |
| --- | --- | --- |
| Branch Hierarchy | `branch_id` (nullable) on Warehouse | Branch Management Epic |
| Multi-Currency | `currency_code` on all monetary fields | Accounting/International Epic |
| Procurement Metadata | 13 reserved fields on Product (per §14.16) | Purchase Epic |
| Lot/Batch Tracking | `lot_id` FK (nullable) on StockMovement | Traceability Module |
| Serial Number | `serial_number` (nullable) on StockMovement | Traceability Module |
| Expiry Date | `expiry_date` (nullable) on StockPosition | Traceability Module |
| Bin Location | `bin_id` FK (nullable) on WarehouseLocation | Phase 2 |
| Rack | `rack_id` FK (nullable) on WarehouseLocation | Phase 2 |
