# Data Model: Epic 7 – Sales Management

**Generated**: 2026-07-30
**Feature**: 007-sales-management
**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)

---

## Aggregate Roots

Epic 7 defines **12 Aggregate Roots**. Each aggregate root is the sole entry point for mutations to its owned entities.

| # | Aggregate Root | Owned Entities |
|---|---------------|----------------|
| 1 | **Customer** | CustomerContact, CustomerAddress, CustomerBankDetail, CustomerNote, CustomFieldValue |
| 2 | **CustomerCategory** | — |
| 3 | **CustomerGroup** | — |
| 4 | **PaymentTerm** | — |
| 5 | **SalesQuotation** | QuotationLine, QuotationRevision |
| 6 | **SalesOrder** | OrderLine, SalesApprovalRecord |
| 7 | **DeliveryNote** | DeliveryNoteLine |
| 8 | **SalesInvoice** | InvoiceLine, InvoiceCharge |
| 9 | **SalesReturn** | ReturnLine |
| 10 | **PriceList** | PriceEntry |
| 11 | **DiscountRule** | — |
| 12 | **SalesApprovalMatrix** | SalesMatrixRule |

---

## Entity Definitions

### Master Data Entities (Phase 1)

---

#### CustomerCategory

Classification for customers. Determines default pricing, payment terms, and credit limits.

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | FK Company; NOT NULL; indexed |
| code | String(20) | Unique per company; NOT NULL |
| name | String(200) | NOT NULL |
| description | Text | nullable |
| default_payment_term_id | UUID | FK PaymentTerm; nullable |
| default_credit_limit | Numeric(15,2) | nullable; default 0 |
| is_active | Boolean | NOT NULL; default true |
| is_deleted | Boolean | NOT NULL; default false |
| deleted_at | DateTime | nullable |
| deleted_by | UUID | nullable |
| created_by | UUID | NOT NULL |
| created_at | DateTime | NOT NULL |
| updated_by | UUID | nullable |
| updated_at | DateTime | nullable |

**Invariants**: Code unique per company. At least one category must exist per company.

---

#### CustomerGroup

Secondary classification for reporting and discount eligibility.

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | FK Company; NOT NULL; indexed |
| code | String(20) | Unique per company; NOT NULL |
| name | String(200) | NOT NULL |
| description | Text | nullable |
| is_active | Boolean | NOT NULL; default true |
| is_deleted | Boolean | NOT NULL; default false |
| Standard audit fields | | |

**Invariants**: Code unique per company.

---

#### PaymentTerm

Payment terms master data. Reused for both sales and purchase (same pattern as Epic 6 but sales-scoped).

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | FK Company; NOT NULL |
| code | String(20) | Unique per company |
| name | String(100) | NOT NULL |
| due_days | Integer | >= 0 |
| discount_days | Integer | nullable |
| discount_percent | Numeric(5,2) | nullable |
| description | Text | nullable |
| is_active | Boolean | default true |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

**Note**: If Epic 6 already created a shared PaymentTerms table, the sales module references it. Otherwise, sales-scoped payment terms are created following the same schema.

---

#### SalesReasonCode

Return reason codes for sales returns.

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

#### SalesSequence

Auto-numbering sequences for sales documents.

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| document_type | Enum | SQ / SO / DN / SI / SR |
| prefix | String(10) | company-configurable |
| current_value | BigInteger | >= 0 |
| format_pattern | String(50) | default: '{PREFIX}-{YYYYMMDD}-{SEQ:04d}' |
| last_reset_date | Date | nullable |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

**Invariants**: Unique (company_id, document_type). Invoice sequences enforce gap-free via advisory lock.

---

### Customer Aggregate (Phase 2)

---

#### Customer

Central entity of the Sales domain.

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | FK Company; NOT NULL; indexed |
| customer_code | String(30) | Unique per company; NOT NULL; immutable after creation |
| legal_name | String(200) | NOT NULL |
| trading_name | String(200) | nullable |
| customer_type | Enum | INDIVIDUAL / COMPANY / GOVERNMENT / INTERNAL |
| category_id | UUID | FK CustomerCategory; NOT NULL |
| group_id | UUID | FK CustomerGroup; nullable |
| status | Enum | DRAFT / ACTIVE / ON_HOLD / BLOCKED / INACTIVE |
| payment_term_id | UUID | FK PaymentTerm; nullable |
| credit_limit | Numeric(15,2) | NOT NULL; default 0 |
| credit_status | Enum | GOOD / WARNING / EXCEEDED / HOLD |
| rating | Enum | A / B / C / D / F; nullable |
| currency_code | String(3) | NOT NULL; ISO 4217 |
| tax_registration_number | String(50) | nullable |
| tax_exempt | Boolean | NOT NULL; default false |
| tax_exempt_certificate | String(100) | nullable |
| tax_exempt_expiry | Date | nullable |
| website | String(500) | nullable |
| industry | String(100) | nullable |
| annual_revenue_range | String(50) | nullable |
| custom_fields | JSONB | nullable; max 20 fields |
| notes | Text | nullable; internal notes |
| version | Integer | NOT NULL; default 1; optimistic locking |
| is_deleted | Boolean | NOT NULL; default false |
| deleted_at | DateTime | nullable |
| deleted_by | UUID | nullable |
| created_by | UUID | NOT NULL |
| created_at | DateTime | NOT NULL |
| updated_by | UUID | nullable |
| updated_at | DateTime | nullable |

**State Machine**:
```
DRAFT → ACTIVE (requires: >=1 contact, >=1 billing address, payment_term set)
ACTIVE → ON_HOLD (manual by Sales/Finance Manager)
ACTIVE → BLOCKED (credit exceeded or manual by Finance Manager)
ON_HOLD → ACTIVE (manual release)
BLOCKED → ACTIVE (credit resolved + manual unblock)
ACTIVE → INACTIVE (no open orders required)
INACTIVE → ACTIVE (manual reactivation)
```

**Invariants**: customer_code unique per company and immutable. DRAFT/INACTIVE customers cannot be on sales documents. ON_HOLD/BLOCKED customers block new orders.

---

#### CustomerContact

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| customer_id | UUID | FK Customer; NOT NULL |
| contact_name | String(200) | NOT NULL |
| title | String(100) | nullable |
| email | String(254) | nullable; valid email |
| phone | String(30) | nullable |
| mobile | String(30) | nullable |
| department | String(100) | nullable |
| is_primary | Boolean | NOT NULL; default false |
| is_billing_contact | Boolean | NOT NULL; default false |
| is_shipping_contact | Boolean | NOT NULL; default false |
| notes | Text | nullable |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

**Invariants**: Exactly one primary contact per customer. At least one contact before activation.

---

#### CustomerAddress

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| customer_id | UUID | FK Customer; NOT NULL |
| address_type | Enum | BILLING / SHIPPING / BOTH |
| address_label | String(100) | nullable |
| address_line_1 | String(300) | NOT NULL |
| address_line_2 | String(300) | nullable |
| city | String(100) | NOT NULL |
| state_province | String(100) | nullable |
| postal_code | String(20) | nullable |
| country_code | String(2) | NOT NULL; ISO 3166-1 alpha-2 |
| is_default_billing | Boolean | NOT NULL; default false |
| is_default_shipping | Boolean | NOT NULL; default false |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

**Invariants**: Exactly one default billing, exactly one default shipping per customer. At least one billing address before activation.

---

#### CustomerBankDetail

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| customer_id | UUID | FK Customer; NOT NULL |
| bank_name | String(200) | NOT NULL |
| branch_name | String(200) | nullable |
| account_number | String(50) | NOT NULL |
| iban | String(34) | nullable |
| swift_bic | String(11) | nullable |
| account_holder_name | String(200) | NOT NULL |
| is_default | Boolean | NOT NULL; default false |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

---

#### CustomerNote

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| customer_id | UUID | FK Customer; NOT NULL |
| content | Text | NOT NULL |
| author_id | UUID | NOT NULL |
| author_name | String(200) | NOT NULL |
| is_deleted | Boolean | default false |
| created_at | DateTime | NOT NULL |

**Invariants**: Append-only. Cannot be edited after creation.

---

### Sales Quotation Aggregate (Phase 4)

---

#### SalesQuotation

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL; indexed |
| quotation_number | String(30) | Unique per company; auto-generated |
| customer_id | UUID | FK Customer; NOT NULL |
| quotation_date | Date | NOT NULL |
| validity_date | Date | NOT NULL; >= quotation_date |
| currency_code | String(3) | NOT NULL |
| payment_term_id | UUID | FK PaymentTerm; nullable |
| shipping_address_id | UUID | FK CustomerAddress; nullable |
| billing_address_id | UUID | FK CustomerAddress; nullable |
| sales_rep_id | UUID | NOT NULL |
| revision_number | Integer | NOT NULL; default 1 |
| status | Enum | DRAFT / SENT_TO_CUSTOMER / ACCEPTED / REJECTED / CONVERTED / EXPIRED / CANCELLED |
| subtotal | Numeric(15,2) | NOT NULL; default 0 |
| discount_type | Enum | PERCENTAGE / AMOUNT; nullable |
| discount_value | Numeric(15,4) | nullable |
| discount_amount | Numeric(15,2) | default 0 |
| tax_amount | Numeric(15,2) | default 0 |
| total_amount | Numeric(15,2) | NOT NULL; default 0 |
| internal_notes | Text | nullable |
| customer_notes | Text | nullable |
| converted_order_id | UUID | FK SalesOrder; nullable |
| version | Integer | default 1 |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

**State Machine**:
```
DRAFT → SENT_TO_CUSTOMER, CANCELLED
SENT_TO_CUSTOMER → ACCEPTED, REJECTED, EXPIRED, CANCELLED
ACCEPTED → CONVERTED, CANCELLED
REJECTED → (terminal)
CONVERTED → (terminal)
EXPIRED → (terminal)
CANCELLED → (terminal)
```

---

#### QuotationLine

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| quotation_id | UUID | FK SalesQuotation; NOT NULL |
| line_number | Integer | NOT NULL |
| product_id | UUID | nullable; FK to Epic 5 Product |
| description | String(500) | NOT NULL |
| quantity | Numeric(12,3) | NOT NULL; > 0 |
| unit_of_measure | String(20) | NOT NULL |
| unit_price | Numeric(15,4) | NOT NULL; >= 0 |
| discount_percentage | Numeric(5,2) | nullable; 0-100 |
| discount_amount | Numeric(15,2) | nullable |
| tax_category | String(20) | nullable |
| extended_amount | Numeric(15,2) | NOT NULL |
| notes | Text | nullable |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

---

#### QuotationRevision

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| quotation_id | UUID | FK SalesQuotation; NOT NULL |
| revision_number | Integer | NOT NULL |
| snapshot | JSONB | NOT NULL; full quotation + lines snapshot |
| modified_by | UUID | NOT NULL |
| modified_at | DateTime | NOT NULL |
| change_summary | Text | nullable |

---

### Sales Order Aggregate (Phase 5)

---

#### SalesOrder

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL; indexed |
| order_number | String(30) | Unique per company; auto-generated |
| customer_id | UUID | FK Customer; NOT NULL |
| quotation_id | UUID | FK SalesQuotation; nullable |
| order_date | Date | NOT NULL |
| required_delivery_date | Date | nullable |
| currency_code | String(3) | NOT NULL |
| payment_term_id | UUID | FK PaymentTerm; nullable |
| shipping_address_id | UUID | FK CustomerAddress; nullable |
| billing_address_id | UUID | FK CustomerAddress; nullable |
| sales_rep_id | UUID | NOT NULL |
| priority | Enum | LOW / NORMAL / HIGH / URGENT |
| status | Enum | DRAFT / PENDING_APPROVAL / APPROVED / REJECTED / PARTIALLY_DELIVERED / DELIVERED / INVOICED / CLOSED / CANCELLED |
| subtotal | Numeric(15,2) | NOT NULL; default 0 |
| discount_type | Enum | PERCENTAGE / AMOUNT; nullable |
| discount_value | Numeric(15,4) | nullable |
| discount_amount | Numeric(15,2) | default 0 |
| tax_amount | Numeric(15,2) | default 0 |
| charges_amount | Numeric(15,2) | default 0 |
| total_amount | Numeric(15,2) | NOT NULL; default 0 |
| internal_notes | Text | nullable |
| customer_notes | Text | nullable |
| cancellation_reason | Text | nullable; required when CANCELLED |
| approval_version | Integer | default 1; increments on resubmission |
| version | Integer | default 1 |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

**State Machine**:
```
DRAFT → PENDING_APPROVAL, CANCELLED
PENDING_APPROVAL → APPROVED, REJECTED
APPROVED → PARTIALLY_DELIVERED, DELIVERED, CANCELLED
REJECTED → DRAFT (revision)
PARTIALLY_DELIVERED → DELIVERED
DELIVERED → INVOICED
INVOICED → CLOSED
CLOSED → (terminal)
CANCELLED → (terminal)
```

---

#### OrderLine

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| order_id | UUID | FK SalesOrder; NOT NULL |
| line_number | Integer | NOT NULL |
| product_id | UUID | nullable; FK Epic 5 Product |
| description | String(500) | NOT NULL |
| quantity_ordered | Numeric(12,3) | NOT NULL; > 0 |
| quantity_delivered | Numeric(12,3) | NOT NULL; default 0 |
| quantity_remaining | Numeric(12,3) | Computed: ordered - delivered |
| unit_of_measure | String(20) | NOT NULL |
| unit_price | Numeric(15,4) | NOT NULL; >= 0 |
| cost_price | Numeric(15,4) | nullable; from Epic 5 for margin calc |
| discount_percentage | Numeric(5,2) | nullable |
| discount_amount | Numeric(15,2) | nullable |
| tax_category | String(20) | nullable |
| tax_rate | Numeric(5,4) | nullable; default 0 |
| tax_amount | Numeric(15,2) | default 0 |
| extended_amount | Numeric(15,2) | NOT NULL |
| delivery_status | Enum | PENDING / PARTIALLY_DELIVERED / DELIVERED |
| price_source | Enum | MANUAL / CUSTOMER_SPECIFIC / GROUP / CATEGORY / PRICE_LIST / DEFAULT_LIST / BASE_PRICE |
| notes | Text | nullable |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

---

#### SalesApprovalRecord

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| document_type | Enum | SALES_ORDER / SALES_RETURN |
| document_id | UUID | NOT NULL |
| approval_level | Integer | NOT NULL |
| approver_id | UUID | NOT NULL |
| decision | Enum | PENDING / APPROVED / REJECTED |
| comments | Text | nullable |
| decided_at | DateTime | nullable |
| is_deleted | Boolean | default false |
| created_at | DateTime | NOT NULL |

**Invariants**: Immutable after decision. Approver != requestor (self-approval prevention).

---

### Delivery Note Aggregate (Phase 6)

---

#### DeliveryNote

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL; indexed |
| delivery_number | String(30) | Unique per company; auto-generated |
| order_id | UUID | FK SalesOrder; NOT NULL |
| customer_id | UUID | FK Customer; NOT NULL |
| shipping_address_id | UUID | FK CustomerAddress; nullable |
| dispatch_date | Date | nullable |
| expected_delivery_date | Date | nullable |
| carrier | String(200) | nullable |
| tracking_number | String(100) | nullable |
| status | Enum | DRAFT / DISPATCHED / DELIVERED / CANCELLED |
| total_packages | Integer | nullable |
| total_weight | Numeric(10,3) | nullable |
| dispatched_by | UUID | nullable |
| internal_notes | Text | nullable |
| version | Integer | default 1 |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

**State Machine**:
```
DRAFT → DISPATCHED, CANCELLED
DISPATCHED → DELIVERED
DELIVERED → (terminal)
CANCELLED → (terminal)
```

---

#### DeliveryNoteLine

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| delivery_note_id | UUID | FK DeliveryNote; NOT NULL |
| order_line_id | UUID | FK OrderLine; NOT NULL |
| product_id | UUID | nullable |
| description | String(500) | NOT NULL |
| quantity_dispatched | Numeric(12,3) | NOT NULL; > 0 |
| unit_of_measure | String(20) | NOT NULL |
| notes | Text | nullable |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

**Invariants**: Sum of dispatched quantities across all DNs for an order line <= ordered quantity.

---

### Sales Invoice Aggregate (Phase 7)

---

#### SalesInvoice

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL; indexed |
| invoice_number | String(30) | Unique per company; auto-generated; gap-free |
| customer_id | UUID | FK Customer; NOT NULL |
| order_id | UUID | FK SalesOrder; nullable |
| delivery_note_id | UUID | FK DeliveryNote; nullable |
| invoice_date | Date | NOT NULL |
| due_date | Date | NOT NULL; calculated from payment terms |
| currency_code | String(3) | NOT NULL |
| payment_term_id | UUID | FK PaymentTerm; nullable |
| billing_address_id | UUID | FK CustomerAddress; nullable |
| status | Enum | DRAFT / ISSUED / PAID / CANCELLED / CREDIT_NOTE_ISSUED |
| subtotal | Numeric(15,2) | NOT NULL; default 0 |
| discount_amount | Numeric(15,2) | default 0 |
| tax_amount | Numeric(15,2) | default 0 |
| charges_amount | Numeric(15,2) | default 0 |
| total_amount | Numeric(15,2) | NOT NULL; default 0 |
| amount_in_words | String(500) | nullable; generated |
| internal_notes | Text | nullable |
| customer_notes | Text | nullable |
| credit_note_amount | Numeric(15,2) | nullable; populated on credit note |
| version | Integer | default 1 |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

**State Machine**:
```
DRAFT → ISSUED, CANCELLED
ISSUED → PAID (future), CREDIT_NOTE_ISSUED
PAID → (terminal)
CANCELLED → (terminal)
CREDIT_NOTE_ISSUED → (terminal or PAID with adjustment)
```

**Invariants**: Invoice numbers gap-free per company. ISSUED invoices immutable.

---

#### InvoiceLine

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| invoice_id | UUID | FK SalesInvoice; NOT NULL |
| line_number | Integer | NOT NULL |
| product_id | UUID | nullable |
| description | String(500) | NOT NULL |
| quantity | Numeric(12,3) | NOT NULL; > 0 |
| unit_of_measure | String(20) | NOT NULL |
| unit_price | Numeric(15,4) | NOT NULL |
| discount_percentage | Numeric(5,2) | nullable |
| discount_amount | Numeric(15,2) | nullable |
| tax_rate | Numeric(5,4) | nullable; default 0 |
| tax_amount | Numeric(15,2) | default 0 |
| extended_amount | Numeric(15,2) | NOT NULL |
| delivery_note_line_id | UUID | nullable; FK DeliveryNoteLine |
| order_line_id | UUID | nullable; FK OrderLine |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

---

#### InvoiceCharge

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| invoice_id | UUID | FK SalesInvoice; NOT NULL |
| charge_type | Enum | FREIGHT / HANDLING / INSURANCE / OTHER |
| description | String(300) | NOT NULL |
| amount | Numeric(15,2) | NOT NULL; > 0 |
| tax_applicable | Boolean | NOT NULL; default false |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

---

### Sales Return Aggregate (Phase 8)

---

#### SalesReturn

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL; indexed |
| return_number | String(30) | Unique per company; auto-generated |
| customer_id | UUID | FK Customer; NOT NULL |
| order_id | UUID | FK SalesOrder; nullable |
| invoice_id | UUID | FK SalesInvoice; nullable |
| return_date | Date | NOT NULL |
| reason_code_id | UUID | FK SalesReasonCode; NOT NULL |
| reason_description | Text | nullable |
| resolution_type | Enum | CREDIT_NOTE / REPLACEMENT / REFUND_READINESS |
| status | Enum | DRAFT / PENDING_APPROVAL / APPROVED / REJECTED / RECEIVED / INSPECTED / COMPLETED / CANCELLED |
| received_by | UUID | nullable |
| received_at | DateTime | nullable |
| credit_note_amount | Numeric(15,2) | nullable |
| replacement_order_id | UUID | FK SalesOrder; nullable |
| internal_notes | Text | nullable |
| version | Integer | default 1 |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

**State Machine**:
```
DRAFT → PENDING_APPROVAL, CANCELLED
PENDING_APPROVAL → APPROVED, REJECTED, CANCELLED
APPROVED → RECEIVED
RECEIVED → INSPECTED (future)
INSPECTED → COMPLETED (future)
RECEIVED → COMPLETED (current — skip INSPECTED)
COMPLETED → (terminal)
REJECTED → (terminal)
CANCELLED → (terminal)
```

---

#### ReturnLine

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| return_id | UUID | FK SalesReturn; NOT NULL |
| product_id | UUID | nullable |
| description | String(500) | NOT NULL |
| quantity_returned | Numeric(12,3) | NOT NULL; > 0 |
| quantity_accepted | Numeric(12,3) | default 0 |
| quantity_rejected | Numeric(12,3) | default 0 |
| unit_price | Numeric(15,4) | NOT NULL; from original document |
| extended_amount | Numeric(15,2) | NOT NULL |
| condition | Enum | NEW / USED / DAMAGED / DEFECTIVE |
| reason_code_id | UUID | nullable; FK SalesReasonCode |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

**Invariants**: Return quantity <= originally delivered quantity.

---

### Pricing Aggregate (Phase 3)

---

#### PriceList

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL; indexed |
| name | String(200) | Unique per company; NOT NULL |
| description | Text | nullable |
| currency_code | String(3) | NOT NULL |
| effective_from | Date | NOT NULL |
| effective_to | Date | nullable |
| is_default | Boolean | NOT NULL; default false |
| is_active | Boolean | NOT NULL; default true |
| priority | Integer | NOT NULL; default 0 |
| version | Integer | default 1 |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

**Invariants**: Exactly one default price list per company.

---

#### PriceEntry

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| price_list_id | UUID | FK PriceList; NOT NULL |
| product_id | UUID | NOT NULL; FK Epic 5 Product |
| unit_price | Numeric(15,4) | NOT NULL; >= 0 |
| minimum_quantity | Numeric(12,3) | NOT NULL; default 1 |
| unit_of_measure | String(20) | NOT NULL |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

---

#### CustomerSpecificPrice

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| customer_id | UUID | FK Customer; NOT NULL |
| product_id | UUID | NOT NULL |
| unit_price | Numeric(15,4) | NOT NULL |
| effective_from | Date | NOT NULL |
| effective_to | Date | nullable |
| minimum_quantity | Numeric(12,3) | default 1 |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

---

#### DiscountRule

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| name | String(200) | NOT NULL |
| rule_type | Enum | PERCENTAGE / FIXED_AMOUNT / VOLUME / PROMOTIONAL |
| applicability | Enum | ALL_CUSTOMERS / SPECIFIC_CATEGORY / SPECIFIC_GROUP / SPECIFIC_CUSTOMER |
| applicability_id | UUID | nullable; FK to category/group/customer |
| product_scope | Enum | ALL_PRODUCTS / SPECIFIC_CATEGORY / SPECIFIC_PRODUCT |
| product_scope_id | UUID | nullable |
| minimum_quantity | Numeric(12,3) | nullable |
| minimum_order_value | Numeric(15,2) | nullable |
| discount_value | Numeric(15,4) | NOT NULL |
| effective_from | Date | NOT NULL |
| effective_to | Date | nullable |
| is_active | Boolean | default true |
| priority | Integer | NOT NULL; default 0 |
| is_stackable | Boolean | default false |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

---

### Approval Aggregate (Phase 5)

---

#### SalesApprovalMatrix

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL; indexed |
| name | String(200) | NOT NULL |
| document_type | Enum | SALES_ORDER / SALES_RETURN |
| is_active | Boolean | default true |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

---

#### SalesMatrixRule

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL |
| matrix_id | UUID | FK SalesApprovalMatrix; NOT NULL |
| approval_level | Integer | NOT NULL |
| min_amount | Numeric(15,2) | NOT NULL |
| max_amount | Numeric(15,2) | nullable |
| approver_role | String(50) | nullable |
| approver_user_id | UUID | nullable |
| customer_category_id | UUID | nullable; FK CustomerCategory |
| auto_approve | Boolean | default false |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

---

### Sales Configuration (Phase 1)

---

#### SalesConfiguration

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | PK |
| company_id | UUID | NOT NULL; unique |
| default_quotation_validity_days | Integer | default 30 |
| quotation_expiry_warning_days | Integer | default 3 |
| auto_approve_threshold | Numeric(15,2) | nullable; orders below this auto-approve |
| minimum_margin_percentage | Numeric(5,2) | nullable |
| credit_warning_threshold | Numeric(5,2) | default 80; percentage |
| reservation_expiry_hours | Integer | default 48 |
| require_quotation_before_order | Boolean | default false |
| tax_inclusive_pricing | Boolean | default false |
| is_deleted | Boolean | default false |
| Standard audit fields | | |

---

## Index Strategy

| Table | Index | Type | Purpose |
|-------|-------|------|---------|
| customer | (company_id, customer_code) | Unique | Code lookup |
| customer | (company_id, status) | B-tree | Status filtering |
| customer | (company_id, legal_name) gin trgm | GIN | Full-text search |
| customer | (company_id, category_id) | B-tree | Category filtering |
| sales_quotation | (company_id, quotation_number) | Unique | Number lookup |
| sales_quotation | (company_id, customer_id, status) | B-tree | Customer quotation list |
| sales_order | (company_id, order_number) | Unique | Number lookup |
| sales_order | (company_id, customer_id, status) | B-tree | Customer order list |
| sales_order | (company_id, status) | B-tree | Status pipeline |
| delivery_note | (company_id, delivery_number) | Unique | Number lookup |
| delivery_note | (company_id, order_id) | B-tree | Order deliveries |
| sales_invoice | (company_id, invoice_number) | Unique | Number lookup |
| sales_invoice | (company_id, customer_id, status) | B-tree | Customer invoice list |
| sales_return | (company_id, return_number) | Unique | Number lookup |
| price_entry | (company_id, price_list_id, product_id) | B-tree | Price lookup |
| customer_specific_price | (company_id, customer_id, product_id) | B-tree | Customer price lookup |
| discount_rule | (company_id, is_active, effective_from) | B-tree | Active rules |

---

## Migration Strategy

Sales module migrations are numbered sequentially from the last Epic 6 migration number. Each phase produces its own migration file(s).

| Phase | Migration | Tables Created |
|-------|-----------|---------------|
| Phase 1 | 0xx_sales_foundation | sales_sequences, customer_categories, customer_groups, payment_terms (if not shared), sales_reason_codes, sales_configuration |
| Phase 2 | 0xx_sales_customers | customers, customer_contacts, customer_addresses, customer_bank_details, customer_notes |
| Phase 3 | 0xx_sales_pricing | price_lists, price_entries, customer_specific_prices, discount_rules |
| Phase 4 | 0xx_sales_quotations | sales_quotations, quotation_lines, quotation_revisions |
| Phase 5 | 0xx_sales_orders | sales_orders, order_lines, sales_approval_matrices, sales_matrix_rules, sales_approval_records |
| Phase 6 | 0xx_sales_delivery | delivery_notes, delivery_note_lines |
| Phase 7 | 0xx_sales_invoices | sales_invoices, invoice_lines, invoice_charges |
| Phase 8 | 0xx_sales_returns | sales_returns, return_lines |
