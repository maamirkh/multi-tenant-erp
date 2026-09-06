# Epic 6 — Purchase Management: Official Business Specification

**Document Type**: Official Enterprise Business Specification (SSOT)
**Epic Number**: 006
**Feature Branch**: `006-purchase-management`
**Version**: 1.0
**Status**: Draft — Pending Approval
**Created**: 2026-07-25
**Compatible With**: Epic 0 (Constitution), Epic 1 (Foundation), Epic 2 (Authentication), Epic 3 (Companies), Epic 4 (Users & Roles), Epic 5 (Inventory Management)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Epic Overview](#2-epic-overview)
3. [Business Vision](#3-business-vision)
4. [Business Goals](#4-business-goals)
5. [Business Scope](#5-business-scope)
6. [Out of Scope](#6-out-of-scope)
7. [Procurement Terminology](#7-procurement-terminology)
8. [Domain Philosophy](#8-domain-philosophy)
9. [Domain Boundaries](#9-domain-boundaries)
10. [Bounded Context](#10-bounded-context)
11. [Stakeholders](#11-stakeholders)
12. [User Personas](#12-user-personas)
13. [Business Capabilities](#13-business-capabilities)
14. [Supplier Master](#14-supplier-master)
15. [Procurement](#15-procurement)
16. [Purchase Orders](#16-purchase-orders)
17. [Goods Receiving](#17-goods-receiving)
18. [Vendor Returns](#18-vendor-returns)
19. [Purchase Costing](#19-purchase-costing)
20. [Purchase Lifecycle](#20-purchase-lifecycle)
21. [Supplier Lifecycle](#21-supplier-lifecycle)
22. [Business Workflows](#22-business-workflows)
23. [Functional Requirements](#23-functional-requirements)
24. [Non-Functional Requirements](#24-non-functional-requirements)
25. [Business Rules](#25-business-rules)
26. [Business Invariants](#26-business-invariants)
27. [Validation Rules](#27-validation-rules)
28. [Permission Matrix](#28-permission-matrix)
29. [Feature Matrix](#29-feature-matrix)
30. [Procurement Governance](#30-procurement-governance)
31. [Conceptual Domain Model](#31-conceptual-domain-model)
32. [Aggregate Roots](#32-aggregate-roots)
33. [Domain Events](#33-domain-events)
34. [Reporting Requirements](#34-reporting-requirements)
35. [KPI Requirements](#35-kpi-requirements)
36. [Search Requirements](#36-search-requirements)
37. [Import and Export](#37-import-and-export)
38. [Notifications](#38-notifications)
39. [Audit Requirements](#39-audit-requirements)
40. [Security Requirements](#40-security-requirements)
41. [Compliance Requirements](#41-compliance-requirements)
42. [Data Retention](#42-data-retention)
43. [Disaster Recovery](#43-disaster-recovery)
44. [Performance Targets](#44-performance-targets)
45. [Scalability Targets](#45-scalability-targets)
46. [Cross-Module Dependencies](#46-cross-module-dependencies)
47. [Cross-Module Contracts](#47-cross-module-contracts)
48. [Integration Readiness](#48-integration-readiness)
49. [AI Readiness](#49-ai-readiness)
50. [Analytics Readiness](#50-analytics-readiness)
51. [Extensibility Strategy](#51-extensibility-strategy)
52. [Versioning Strategy](#52-versioning-strategy)
53. [Risks](#53-risks)
54. [Assumptions](#54-assumptions)
55. [Constraints](#55-constraints)
56. [Success Metrics](#56-success-metrics)
57. [Glossary](#57-glossary)
58. [Acceptance Criteria](#58-acceptance-criteria)
59. [Epic Completion Criteria](#59-epic-completion-criteria)
60. [Future Roadmap](#60-future-roadmap)

---

## 1. Executive Summary

Purchase Management is Epic 6 of the DevSphere ERP platform. It delivers the complete **Procurement Domain** — the end-to-end capability that enables organisations to source, acquire, and receive goods and services from external suppliers under full governance, cost control, and audit accountability.

This epic is not merely a Purchase Order module. It establishes the enterprise-grade procurement foundation upon which future capabilities — Accounts Payable, Landed Cost, Import Purchasing, RFQ, Multi-Currency, and Supplier Portal — will be built without architectural rework.

The module serves every industry sector that DevSphere ERP targets: retail, wholesale, construction, manufacturing, distribution, medical, electrical, trading, and general commerce. Industry-specific behaviour is achieved through configuration and feature flags, not code changes.

Upon completion of Epic 6, DevSphere ERP will provide:

- A fully governed **Supplier Master** with lifecycle, rating, and compliance tracking
- A structured **Procurement workflow** from purchase request through to approval
- A complete **Purchase Order** lifecycle with status-driven state management
- A **Goods Receiving** capability supporting partial, full, and discrepancy handling
- A **Vendor Returns** process with replacement and credit note readiness
- **Purchase Costing** with additional charges, discounts, and future tax and landed cost hooks
- **Purchase Intelligence** via 14+ reports, 10+ KPIs, and AI readiness
- Full **multi-tenant isolation**, **RBAC enforcement**, **soft-delete**, and **audit trail**

---

## 2. Epic Overview

| Attribute | Value |
|-----------|-------|
| Epic Number | 006 |
| Epic Name | Purchase Management |
| Domain | Procurement |
| Module Slug | `purchase` |
| Priority | P1 — Core ERP |
| Predecessor Epics | 001, 002, 003, 004, 005 |
| Successor Epics | 007 (Sales), 008 (Accounts Payable — Future) |
| Estimated Phases | 12 |
| Architecture Pattern | Modular Monolith, Clean Architecture, DDD-Inspired |
| Multi-Tenancy | Required — every entity is company-scoped |
| RBAC | Required — integrates with Epic 4 role system |
| Audit Trail | Required — all state changes recorded |
| Soft Delete | Required — no hard deletes |
| Feature Flags | Required — granular capability enablement |

---

## 3. Business Vision

### 3.1 The Procurement Domain

Procurement is not the act of creating a purchase order. Procurement is the **complete business process** by which an organisation:

1. Identifies a need for goods or services
2. Sources and evaluates suppliers
3. Requests internal approval to purchase
4. Issues a formal order to a supplier
5. Receives the goods or services
6. Validates receipt against the order
7. Handles discrepancies, returns, and rejections
8. Records purchase cost for financial reporting
9. Continuously monitors supplier performance

Purchase Management in DevSphere ERP implements this complete value chain.

### 3.2 Strategic Positioning

Purchase Management is the **procurement backbone** of DevSphere ERP. It sits upstream of inventory (replenishment), downstream of accounts payable (payment), and adjacent to sales (demand planning). Its data quality directly affects:

- **Inventory accuracy**: received quantities update stock positions
- **Cost of goods**: purchase cost informs product costing
- **Cash flow**: purchase commitments are visible to finance
- **Supplier relationships**: performance data drives strategic sourcing decisions

### 3.3 Industry Neutrality

The module is designed to serve multiple industry verticals without architectural modification. Industry-specific behaviour — such as quality inspection requirements in medical/pharmaceutical, project-based purchasing in construction, or import purchasing in trading — is accommodated through feature flags and configuration, not separate code paths.

### 3.4 Long-Term Capability Platform

Every design decision in this epic must preserve forward compatibility with:

- **Request for Quotation (RFQ)**: multi-supplier competitive bidding
- **Quotation Comparison**: side-by-side vendor offer analysis
- **Accounts Payable**: invoice matching and payment scheduling
- **Landed Cost**: freight, duty, and handling allocation to received goods
- **Import Purchasing**: multi-currency, customs, and duty management
- **Supplier Portal**: self-service supplier collaboration
- **Multi-Branch**: purchase orders issued and received at branch level
- **Multi-Currency**: purchase orders in supplier currency with exchange rate capture

---

## 4. Business Goals

### 4.1 Primary Goals (Epic 6 Scope)

| Goal ID | Goal | Measurable Outcome |
|---------|------|--------------------|
| BG-01 | Establish a governed Supplier Master | All supplier data centralised, rated, and lifecycle-managed |
| BG-02 | Enable structured Purchase Requests | All procurement initiated through formal internal request |
| BG-03 | Deliver a compliant Purchase Order workflow | POs issued only after approval; full state audit trail |
| BG-04 | Automate Goods Receiving against POs | Received quantities validated against ordered quantities |
| BG-05 | Support Vendor Return processing | Returns tracked with reason codes; credit readiness achieved |
| BG-06 | Capture complete Purchase Cost | Unit cost, additional charges, and discounts recorded per PO |
| BG-07 | Provide Purchase Intelligence | 14+ reports and 10+ KPIs available to authorised users |
| BG-08 | Enforce procurement governance | Approval matrices, spend policies, and audit trail enforced |

### 4.2 Strategic Goals (Future Capability Enablement)

| Goal ID | Goal | Target Epic |
|---------|------|-------------|
| BG-09 | RFQ and quotation comparison readiness | Epic 6.x |
| BG-10 | Accounts Payable integration readiness | Epic 8 |
| BG-11 | Landed cost computation readiness | Epic 8.x |
| BG-12 | Import purchasing readiness | Epic 9 |
| BG-13 | Multi-currency purchase readiness | Epic 10 |
| BG-14 | Supplier portal readiness | Epic 11 |

---

## 5. Business Scope

### 5.1 In Scope — Epic 6

**Supplier Master**
- Supplier creation, update, lifecycle management (Active, Inactive, Blocked, Archived)
- Supplier categories and classification
- Supplier contacts (multiple contacts per supplier)
- Supplier addresses (billing, shipping, multiple)
- Payment terms definition and assignment
- Credit limits and payment behaviour
- Tax information and tax registration numbers
- Lead time configuration per supplier or product
- Supplier rating and performance scoring
- Preferred supplier designation
- Internal vendor codes
- Bank details (for future AP)
- Custom fields per company
- Internal notes and document attachments
- Supplier search and advanced filtering

**Procurement (Purchase Requests)**
- Purchase Request creation by authorised users
- Multi-level approval workflow for Purchase Requests
- Purchase Request line items with product, quantity, estimated cost
- Approval matrix configuration per company
- Request status lifecycle: Draft, Submitted, Under Review, Approved, Rejected, Cancelled
- Conversion of approved Request to Purchase Order
- Purchase policy enforcement (spend limits, supplier restrictions)

**Purchase Orders**
- PO creation from approved Purchase Request or directly (with permission)
- PO line items with product, quantity, unit cost, discount
- PO status lifecycle: Draft, Pending Approval, Approved, Partially Received, Fully Received, Closed, Cancelled
- PO approval workflow (configurable multi-level)
- PO number auto-generation with configurable prefix/format
- Delivery date and expected arrival tracking
- Supplier reference number capture
- PO amendment workflow (amendment triggers re-approval)
- PO cancellation with reason code
- PO print/export to PDF

**Goods Receiving**
- Goods Receipt creation against an approved PO
- Partial receipt support (multiple GR against one PO)
- Receipt quantity validation against ordered quantity
- Over-receipt policy (block/warn/allow per company setting)
- Under-receipt tracking and open quantity management
- Item rejection with reason codes
- Inventory stock update on receipt confirmation
- GR reference number auto-generation
- Discrepancy recording and supplier notification readiness

**Vendor Returns**
- Return Merchandise Authorisation (RMA) creation against a received GR
- Return reasons and classification
- Return quantity validation (cannot exceed received quantity)
- Return workflow: Draft, Submitted, Approved, Dispatched, Completed
- Replacement order readiness (link return to replacement PO)
- Credit note readiness (return triggers credit note flag for AP)
- Inventory deduction on return confirmation

**Purchase Costing**
- Unit cost capture on PO lines
- Additional charges at PO or GR level: freight, handling, insurance
- Line-level and header-level discounts
- Tax readiness fields (tax code, tax amount — calculation in future AP scope)
- Cost summary per PO: subtotal, charges, discounts, estimated total
- Purchase price variance tracking (ordered vs received cost)

**Purchase Intelligence**
- 14 standard reports (see section 34)
- 10 KPIs (see section 35)
- Supplier performance dashboard
- Purchase trend analysis

**Governance and Compliance**
- Audit trail on all procurement events
- Soft delete on all entities
- Multi-tenant isolation
- RBAC enforcement per operation
- Feature flags for all optional capabilities

### 5.2 Configuration Scope

The following behaviours are configurable per company via feature flags or settings:

- Approval required for Purchase Requests (on/off)
- Approval required for Purchase Orders (on/off)
- Over-receipt policy (Block / Warn / Allow)
- Direct PO creation without PR (on/off)
- Supplier rating method (manual / computed / hybrid)
- PO number format and prefix
- Required fields for supplier creation
- Credit limit enforcement (block / warn / off)

---

## 6. Out of Scope

The following capabilities are **explicitly excluded** from Epic 6. They are documented here to prevent scope creep and to signal their intended future placement.

| Capability | Target |
|------------|--------|
| Request for Quotation (RFQ) | Epic 6.x — Future |
| Quotation Comparison (multi-vendor) | Epic 6.x — Future |
| Accounts Payable (invoice matching, payment) | Epic 8 |
| Landed Cost computation | Epic 8.x |
| Import Purchasing (customs, duties, forex) | Epic 9 |
| Multi-Currency purchase orders | Epic 10 |
| Supplier Portal (self-service supplier web access) | Epic 11 |
| EDI integration | Epic 11 |
| Budget validation and spend controls | Epic 6.x — Future |
| Quality inspection workflow | Epic 6.x — Future |
| Consignment purchasing | Future |
| Blanket / Frame purchase orders | Epic 6.x — Future |
| Drop-ship purchasing (direct to customer) | Future |
| Three-way matching (PO, GR, Invoice) | Epic 8 |
| Purchase forecasting (demand-driven PO) | Future |
| Sales module integration | Epic 7 |
| CRM supplier contact sync | Future |
| General Ledger posting | Epic 8 |

---

## 7. Procurement Terminology

| Term | Definition |
|------|------------|
| **Supplier** | An external party that provides goods or services to the company in exchange for payment |
| **Vendor** | Used interchangeably with Supplier in this document |
| **Purchase Request (PR)** | An internal document raised by a department to request the purchase of goods or services, subject to internal approval |
| **Purchase Order (PO)** | A legally binding external document issued to a supplier authorising the purchase of specific goods or services at agreed terms |
| **Goods Receipt (GR)** | A document recording the actual physical receipt of goods from a supplier against a PO |
| **Return Merchandise Authorisation (RMA)** | A formal document authorising the return of received goods back to the supplier |
| **Vendor Return** | The physical act of sending previously received goods back to the supplier |
| **Lead Time** | The number of days expected between placing an order and receiving the goods |
| **Payment Terms** | The agreed conditions under which a supplier expects to receive payment (e.g., Net 30, COD, 2/10 Net 30) |
| **Credit Limit** | The maximum outstanding payable balance allowed with a supplier before further orders are blocked or warned |
| **Preferred Supplier** | A supplier designated as the primary or recommended source for specific products or categories |
| **Supplier Category** | A classification grouping suppliers by type, industry, or commodity |
| **Vendor Code** | An internal code assigned to a supplier for referencing in accounting, ERP, and legacy systems |
| **Purchase Price Variance (PPV)** | The difference between the cost on the Purchase Order and the cost on the Goods Receipt |
| **Over-Receipt** | A Goods Receipt where the received quantity exceeds the ordered quantity |
| **Under-Receipt** | A Goods Receipt where the received quantity is less than the ordered quantity |
| **Open Quantity** | The remaining quantity on a PO line yet to be received |
| **Approval Matrix** | A configurable set of rules defining who must approve Purchase Requests or Purchase Orders based on amount, department, or category |
| **Landed Cost** | The total cost of a purchased item including freight, insurance, customs, and handling (future scope) |
| **Credit Note** | A document issued by the supplier crediting the company for returned goods or disputed charges (future AP scope) |
| **GRN** | Goods Received Note — alternative term for Goods Receipt document |
| **RFQ** | Request for Quotation — a competitive bidding process sent to multiple suppliers (future scope) |
| **Three-Way Match** | The process of matching PO, GR, and supplier invoice before approving payment (future AP scope) |

---

## 8. Domain Philosophy

### 8.1 Procurement as a Domain, Not a Transaction

Purchase Management is modelled as a **domain** with clear sub-domains, not as a collection of transaction screens. Each sub-domain has its own aggregate root, lifecycle, invariants, and events. This separation ensures that changes to one sub-domain do not inadvertently affect another.

### 8.2 Sub-Domain Separation

| Sub-Domain | Responsibility |
|------------|---------------|
| **Supplier Master** | All information about who the company buys from |
| **Procurement** | The internal process of deciding what to buy and getting approval |
| **Purchase Orders** | The external formal commitment to a supplier |
| **Goods Receiving** | The physical and documentary receipt of goods |
| **Vendor Returns** | The reversal of receipt and return of goods to the supplier |
| **Purchase Costing** | The financial dimension of procurement (cost capture, charges, discounts) |
| **Purchase Intelligence** | Reporting, KPIs, and analytics derived from procurement data |
| **Purchase Governance** | Policies, approval matrices, audit, and compliance |

### 8.3 Separation of Concerns

- The **Supplier Master** sub-domain knows nothing about purchase orders; it provides supplier references
- The **Procurement** sub-domain knows nothing about inventory; it expresses intent to purchase
- The **Purchase Orders** sub-domain is the authoritative record of what was ordered, at what price, from whom
- The **Goods Receiving** sub-domain is the authoritative record of what was actually received
- The **Vendor Returns** sub-domain reverses goods receipt events in a controlled manner
- **Purchase Intelligence** only reads data; it never writes to operational records

### 8.4 Immutability of Key Records

Once a Purchase Order transitions to **Approved** status, its core terms (supplier, line items, total) become immutable. Any change requires a formal **PO Amendment** which resets the approval workflow. This preserves the integrity of the external supplier commitment.

Goods Receipts are **append-only** once confirmed. Corrections must be made via Vendor Returns, not by editing receipt records.

---

## 9. Domain Boundaries

The Purchase Management domain interacts with adjacent domains through well-defined contracts:

**Internal Sub-Domains**: Supplier Master, Procurement, Purchase Orders, Goods Receiving, Vendor Returns, Purchase Costing, Purchase Intelligence, Purchase Governance.

**Upstream Providers**:
- Epic 2 (Authentication): user identity and session management
- Epic 3 (Companies): company isolation and configuration
- Epic 4 (Users and Roles): RBAC enforcement and approval identity
- Epic 5 (Inventory): product reference; stock update on GR confirmation

**Downstream Consumers**:
- Epic 7 (Sales — Future): supplier cost for margin calculation
- Epic 8 (Accounts Payable — Future): PO/GR reference for invoice matching; supplier bank details

---

## 10. Bounded Context

The Purchase Management bounded context owns and is the **single source of truth** for:

| Entity | Owned By | External References |
|--------|----------|---------------------|
| Supplier | Purchase | Referenced by Inventory (preferred supplier), AP (payment) |
| SupplierCategory | Purchase | — |
| SupplierContact | Purchase | — |
| SupplierAddress | Purchase | — |
| PurchaseRequest | Purchase | References User (Epic 4), Product (Epic 5) |
| PurchaseOrder | Purchase | References Supplier, User, Product |
| PurchaseOrderLine | Purchase | References Product (Epic 5) |
| GoodsReceipt | Purchase | References PO, updates Inventory |
| GoodsReceiptLine | Purchase | References PO Line, Product |
| VendorReturn | Purchase | References GR, Product |
| PurchaseCostEntry | Purchase | References PO, GR |
| ApprovalMatrix | Purchase | References User Roles (Epic 4) |
| PurchasePolicy | Purchase | — |

The Purchase module **reads** but does not own:
- Products/SKUs — owned by Inventory (Epic 5)
- Users — owned by Authentication (Epic 2) / Users and Roles (Epic 4)
- Company Settings — owned by Companies (Epic 3)

---

## 11. Stakeholders

| Stakeholder | Role | Primary Interest |
|-------------|------|-----------------|
| Company Owner | Business decision maker | Cost control, supplier relationships, compliance |
| Finance Director | Financial governance | Purchase commitments, cost accuracy, payment terms |
| Procurement Manager | Operational ownership | Workflow efficiency, supplier performance, policy compliance |
| Store Keeper / Warehouse Manager | Receipt and returns | Goods receiving accuracy, discrepancy handling |
| Purchase Officer | Operational user | PO creation, order tracking, receipt recording |
| IT Administrator | System configuration | Feature flags, approval matrix setup, data integrity |
| Auditor | Compliance verification | Audit trail completeness, approval record integrity |
| Supplier (External) | Business partner | Order accuracy, payment terms, return handling |
| DevSphere Product Team | Platform evolution | Extensibility, API readiness, forward compatibility |

---

## 12. User Personas

### 12.1 Super Admin

**Profile**: DevSphere platform administrator with cross-company access.

**Purchase-Specific Needs**:
- Ability to view any company's procurement data for support purposes
- Feature flag control per company (e.g., enabling RFQ for specific tenants)
- No operational purchase actions (creates no POs, GRs, etc.)

---

### 12.2 Company Owner

**Profile**: Business owner or C-level executive. Strategic, not operational.

**Purchase-Specific Needs**:
- Executive KPI dashboard (total spend, open commitments, supplier count)
- Top-level approval authority (final approver in multi-level matrix)
- Access to all reports without creation rights
- Supplier performance overview

---

### 12.3 Purchase Manager

**Profile**: Head of procurement. Responsible for supplier relationships, policy, and team management.

**Purchase-Specific Needs**:
- Full access to Supplier Master management
- Ability to configure approval matrices and procurement policies
- Approve or reject PRs and POs
- Access to all purchase reports and KPIs
- Override capabilities (e.g., allow over-receipt in exceptional cases)

---

### 12.4 Purchase Officer

**Profile**: Operational procurement staff. Day-to-day purchase execution.

**Purchase-Specific Needs**:
- Create and submit Purchase Requests
- Convert approved PRs to POs (if policy allows)
- View supplier catalogue and pricing history
- Monitor open POs and pending deliveries
- Cannot approve their own requests

---

### 12.5 Store Keeper

**Profile**: Warehouse or stores staff responsible for physical receipt and storage of goods.

**Purchase-Specific Needs**:
- Create Goods Receipts against approved POs
- Record partial receipts with remaining quantities
- Flag rejected items with reason codes
- Initiate vendor return (RMA) requests
- Cannot create POs or approve anything

---

### 12.6 Warehouse Manager

**Profile**: Senior warehouse/logistics manager. Oversees receiving operations.

**Purchase-Specific Needs**:
- All Store Keeper capabilities
- Approve vendor return requests
- View receiving reports and discrepancy analytics
- Override over-receipt warnings (if policy permits)

---

### 12.7 Finance Manager

**Profile**: Financial controller or CFO. Concerned with cost and commitment tracking.

**Purchase-Specific Needs**:
- Read access to all POs and costs
- View purchase commitment reports
- Approve POs above financial threshold
- Access to cost analysis and PPV reports
- Cannot create operational documents

---

### 12.8 Approver

**Profile**: A designated approver at any level in the approval matrix.

**Purchase-Specific Needs**:
- Approval inbox / pending approvals dashboard
- Ability to approve, reject, or request changes with comments
- Notification of new approval requests
- Cannot create the documents they approve

---

### 12.9 Auditor

**Profile**: Internal or external auditor. Read-only access.

**Purchase-Specific Needs**:
- Complete read access to all procurement records
- Access to audit trail reports
- Cannot create, edit, or approve anything
- Access to soft-deleted records visible in audit view

---

### 12.10 Read-Only User / Viewer

**Profile**: Staff with a need to view procurement data without operational capability.

**Purchase-Specific Needs**:
- Read access to approved/published records
- No creation, editing, approval, or deletion capability

---

## 13. Business Capabilities

### 13.1 Capability Map

```
PURCHASE MANAGEMENT
|
|-- C1: Supplier Relationship Management
|   |-- C1.1  Supplier Master Maintenance
|   |-- C1.2  Supplier Classification and Segmentation
|   |-- C1.3  Supplier Contact and Address Management
|   |-- C1.4  Supplier Financial Terms Management
|   |-- C1.5  Supplier Rating and Performance Scoring
|   |-- C1.6  Supplier Compliance and Document Management
|   `-- C1.7  Supplier Lifecycle Management
|
|-- C2: Procurement Process Management
|   |-- C2.1  Purchase Request Creation and Submission
|   |-- C2.2  Procurement Approval Workflow
|   |-- C2.3  Approval Matrix Configuration
|   |-- C2.4  Purchase Policy Enforcement
|   `-- C2.5  PR-to-PO Conversion
|
|-- C3: Purchase Order Management
|   |-- C3.1  Purchase Order Authoring
|   |-- C3.2  PO Approval Workflow
|   |-- C3.3  PO Lifecycle Management
|   |-- C3.4  PO Amendment Management
|   |-- C3.5  Delivery and Lead Time Tracking
|   `-- C3.6  PO Communication Readiness
|
|-- C4: Goods Receiving Management
|   |-- C4.1  Goods Receipt Recording
|   |-- C4.2  Partial Receipt Management
|   |-- C4.3  Over/Under Receipt Handling
|   |-- C4.4  Rejection and Quality Hold Recording
|   `-- C4.5  Inventory Stock Update on Receipt
|
|-- C5: Vendor Returns Management
|   |-- C5.1  Return Request Initiation
|   |-- C5.2  Return Approval and Authorisation
|   |-- C5.3  Return Dispatch and Completion
|   |-- C5.4  Replacement Order Linkage
|   `-- C5.5  Credit Note Readiness
|
|-- C6: Purchase Cost Management
|   |-- C6.1  Purchase Cost Capture
|   |-- C6.2  Additional Charges Management
|   |-- C6.3  Discount Management
|   |-- C6.4  Tax Readiness
|   `-- C6.5  Purchase Price Variance Tracking
|
`-- C7: Purchase Intelligence
    |-- C7.1  Standard Purchase Reports
    |-- C7.2  Supplier Performance Analytics
    |-- C7.3  KPI Dashboard
    |-- C7.4  Purchase Trend Analysis
    `-- C7.5  Cost Analysis
```

---

## 14. Supplier Master

### 14.1 Supplier Entity

A **Supplier** represents an external business entity from which the company procures goods or services. It is the master record for all supplier-related information and is referenced by Purchase Orders, Goods Receipts, and future Accounts Payable records.

Each Supplier record belongs to exactly one company (`company_id`) and is isolated from all other tenants.

### 14.2 Supplier Core Attributes

| Attribute | Description | Notes |
|-----------|-------------|-------|
| Supplier Code | System-generated or manually assigned unique code | Immutable once confirmed |
| Vendor Code | Internal accounting/legacy reference code | Optional; editable |
| Legal Name | Full registered legal name | Required |
| Trading Name | Name used in day-to-day communication | Optional |
| Supplier Type | Goods / Services / Both | Required |
| Status | Active / Inactive / Blocked / Archived | Governs eligibility for new orders |
| Currency | Default transaction currency | Required; future multi-currency use |
| Tax Registration | Tax ID / VAT number as applicable | Optional |
| Website | Supplier website | Optional |
| Industry | Supplier's industry classification | Optional |
| Internal Notes | Free-text internal notes | Not visible to supplier |
| Is Preferred | Flag for preferred supplier designation | Per product category (future) |
| Rating | Numeric score 1–5 | Manual or computed |

### 14.3 Supplier Categories

Suppliers are classified into **Supplier Categories** to enable segmented reporting, policy assignment, and preferred supplier routing.

- A company maintains its own category list (not shared across tenants)
- A supplier can belong to one primary category and multiple secondary categories
- Categories are hierarchical (parent/child) for granular segmentation
- Example categories: Raw Materials, Finished Goods, Packaging, Services, Equipment, Utilities, IT

### 14.4 Supplier Status Lifecycle

| Status | Description | Allowed Actions |
|--------|-------------|-----------------|
| **Draft** | Supplier record being completed | Edit; cannot be selected on POs |
| **Active** | Approved and eligible for orders | All operations permitted |
| **Inactive** | Temporarily not in use | Cannot be selected on new POs; existing POs unaffected |
| **Blocked** | Suspended due to dispute, compliance issue, or non-payment | Cannot be selected on any document; existing open POs flagged |
| **Archived** | Permanently decommissioned | Read-only; soft-deleted from active lists |

### 14.5 Supplier Contacts

Each supplier may have multiple contacts with distinct roles:

| Contact Attribute | Description |
|-------------------|-------------|
| Contact Name | Full name |
| Role / Title | e.g., Sales Representative, Account Manager |
| Email | Primary email address |
| Phone | Direct phone / mobile |
| Is Primary | The default contact for PO communication |
| Department | Optional department within supplier organisation |
| Notes | Contact-specific notes |

### 14.6 Supplier Addresses

Each supplier may have multiple addresses of distinct types: Registered, Billing, Shipping/Dispatch, Warehouse. One address per type may be designated as default.

### 14.7 Payment Terms

Payment terms define the financial conditions under which the company is expected to settle invoices with the supplier.

| Term Attribute | Description |
|----------------|-------------|
| Term Code | Unique identifier (e.g., NET30, COD, 2/10NET30) |
| Term Name | Human-readable name |
| Due Days | Number of days from invoice date until payment due |
| Discount Days | Days within which early payment discount applies |
| Discount Percentage | Percentage discount for early payment |
| Is Default | Default term applied to new POs for this supplier |

### 14.8 Credit Limit

The credit limit represents the maximum outstanding payable balance permitted with a supplier before the system restricts or warns on new orders.

| Attribute | Description |
|-----------|-------------|
| Credit Limit Amount | Maximum allowable outstanding balance |
| Credit Limit Currency | Currency of the limit |
| Enforcement Mode | Block / Warn / Off |
| Current Exposure | Computed — sum of approved open PO values not yet settled |

### 14.9 Tax Information

| Field | Description |
|-------|-------------|
| Tax Category | Classification for purchase tax treatment |
| Tax Registration Number | Supplier's official tax registration |
| Withholding Tax Code | Code for applicable withholding tax |
| Tax Exempt | Boolean flag for tax-exempt suppliers |

Tax amounts are computed by a future tax engine (Epic 8). Fields are captured here for forward compatibility.

### 14.10 Lead Time

| Attribute | Description |
|-----------|-------------|
| Default Lead Time (Days) | Standard number of days from PO to expected delivery |
| Lead Time by Product | Override lead time per product category or SKU |
| Lead Time Variance | Acceptable variance in days |

### 14.11 Supplier Rating

Supplier Rating is a composite performance indicator:

| Component | Weight | Source |
|-----------|--------|--------|
| On-Time Delivery Rate | 30% | Computed from GR vs expected date |
| Order Fulfilment Rate | 25% | Computed from received vs ordered quantity |
| Quality / Rejection Rate | 25% | Computed from GR rejection lines |
| Price Variance Rate | 20% | Computed from PO vs GR cost variance |

Rating is computed as a 1–5 numeric score, updated whenever a GR is confirmed. Manual override by Purchase Manager is permitted with a note.

### 14.12 Bank Details

Bank details are captured for future Accounts Payable integration. Access is restricted to Finance Manager level.

| Attribute | Description |
|-----------|-------------|
| Bank Name | Name of the supplier's bank |
| Account Title | Name on the bank account |
| Account Number | Bank account number |
| IBAN | International Bank Account Number |
| SWIFT/BIC | Bank identifier code |
| Is Primary | Default bank account for payments |

### 14.13 Custom Fields

Each company may define up to 20 custom fields on the Supplier entity supporting: Text, Number, Date, Boolean, and List (dropdown) types. Custom fields can be marked as required, searchable, and filterable.

### 14.14 Documents and Attachments

Suppliers may have document attachments for compliance and reference: contracts, trade licences, tax certificates, quality certifications, insurance certificates, bank letters. Documents are categorised, carry an optional expiry date, and trigger alerts when approaching expiry (configurable).

---

## 15. Procurement

### 15.1 Purchase Requests

A **Purchase Request (PR)** is an internal procurement document raised by any authorised user to express a business need for goods or services. It initiates the procurement process before any external commitment is made.

#### 15.1.1 PR Header Attributes

| Attribute | Description |
|-----------|-------------|
| PR Number | System-generated unique reference |
| Request Title | Brief description of the purchase need |
| Requested By | User who created the request |
| Department | Requesting department |
| Request Date | Date request was raised |
| Required By Date | Date by which goods/services are needed |
| Priority | Normal / Urgent / Critical |
| Preferred Supplier | Optional — requesting user's preferred supplier |
| Justification | Business reason for the purchase |
| Status | Draft / Submitted / Under Review / Approved / Rejected / Cancelled |

#### 15.1.2 PR Line Items

| Attribute | Description |
|-----------|-------------|
| Product / SKU | Reference to product in Inventory |
| Description | Free-text description (for non-catalogued items) |
| Requested Quantity | How many units are needed |
| Unit of Measure | UOM from Inventory |
| Estimated Unit Cost | Requestor's estimated cost (informational) |
| Notes | Line-specific notes |

### 15.2 Purchase Request Lifecycle

```
DRAFT -> SUBMITTED -> UNDER REVIEW -> APPROVED -> [Converted to PO]
                    |
                  REJECTED -> [New PR may be raised]
       |
     CANCELLED
```

### 15.3 Purchase Approval Workflow

The approval workflow is multi-level and configurable per company, driven by an **Approval Matrix**.

#### 15.3.1 Approval Matrix Dimensions

| Dimension | Options |
|-----------|---------|
| Document Type | Purchase Request / Purchase Order |
| Amount Range | e.g., 0–5,000 / 5,001–25,000 / 25,001+ |
| Department | Any / Specific departments |
| Category | Any / Specific supplier categories |

Approval modes: **Sequential** (Approver 1 must approve before Approver 2 is notified), **Parallel** (all must approve), **Any-of** (any one from a group can approve).

#### 15.3.2 Approval Governance Rules

| Rule | Description |
|------|-------------|
| Self-Approval Prevention | A user cannot approve their own PR or PO |
| Delegation | Approvers can delegate to a substitute with time limits |
| Escalation | Un-actioned approvals escalate after a configurable number of days |
| Override | Purchase Manager can override a rejection with documented justification |
| Bypass | Emergency bypass permitted for Purchase Manager (fully audited) |

### 15.4 Purchase Policies

| Policy | Description | Enforcement |
|--------|-------------|-------------|
| Minimum PR Amount | PRs below this amount are auto-approved | Configurable |
| Maximum PO without PR | Allow PO creation without a PR up to this amount | Configurable |
| Supplier Restriction | Only Active suppliers can be selected | Always enforced |
| Preferred Supplier Priority | Warn if non-preferred supplier selected for a category | Warn / Block |
| Duplicate PR Detection | Warn if similar PR exists in last N days | Configurable |
| Budget Check | Validate against departmental budget | Future |

---

## 16. Purchase Orders

### 16.1 Overview

A **Purchase Order (PO)** is the formal external document that commits the company to purchasing specified goods or services from a named supplier at agreed prices and terms. Once approved, a PO is a binding procurement commitment.

### 16.2 PO Header Attributes

| Attribute | Description |
|-----------|-------------|
| PO Number | System-generated unique reference (configurable format) |
| PO Date | Date the PO was created |
| Supplier | Reference to Supplier Master |
| Supplier Reference | Supplier's own order/quotation reference |
| Source PR | Reference to originating Purchase Request (if applicable) |
| Expected Delivery Date | Computed from lead time or manually entered |
| Delivery Address | Where goods should be delivered |
| Payment Terms | Inherited from supplier; overridable per PO |
| Currency | Transaction currency (default: company base currency) |
| Notes to Supplier | Free-text message for the supplier |
| Internal Notes | Internal-only notes |
| Status | Draft / Pending Approval / Approved / Partially Received / Fully Received / Closed / Cancelled |

### 16.3 PO Line Attributes

| Attribute | Description |
|-----------|-------------|
| Line Number | Sequential line reference |
| Product / SKU | Reference to product in Inventory |
| Description | Line description (auto-filled from product; editable) |
| Ordered Quantity | Quantity committed to the supplier |
| Unit of Measure | UOM |
| Unit Cost | Agreed cost per unit |
| Discount % | Line-level discount percentage |
| Line Total | Computed: (Quantity x Unit Cost) minus Discount |
| Received Quantity | Running total of confirmed received quantity |
| Remaining Quantity | Ordered minus Received |
| Status | Open / Partially Received / Fully Received / Cancelled |

### 16.4 PO Totals

| Component | Description |
|-----------|-------------|
| Subtotal | Sum of all line totals |
| Additional Charges | Freight, handling, insurance |
| Header Discount | Discount applied at PO level |
| Tax Amount | Computed by future tax engine; captured here |
| Grand Total | Subtotal plus Charges minus Header Discount plus Tax |

### 16.5 PO Status Lifecycle

| Status | Description | Inventory Impact |
|--------|-------------|-----------------|
| **Draft** | PO being authored; no commitment | None |
| **Pending Approval** | Submitted for approval | None |
| **Approved** | Formally committed to supplier | Creates open purchase commitment |
| **Partially Received** | At least one GR line confirmed | Stock increased per received lines |
| **Fully Received** | All ordered quantities received | All stock updated |
| **Closed** | PO closed (with possible under-receipt) | No further GRs permitted |
| **Cancelled** | PO void | No stock impact; commitment reversed |

### 16.6 PO Number Format

PO numbers are system-generated with a configurable format per company: `[PREFIX]-[YEAR]-[SEQUENCE]`

Example: `PO-2026-000147`

Configurable: prefix, year/month inclusion, sequence length (4–8 digits), separator.

### 16.7 PO Amendment

When an approved PO requires modification:

1. Purchase Officer initiates an amendment request
2. PO transitions to Amendment in Progress sub-status
3. Changes are recorded in an amendment record
4. Amended PO resubmitted for approval (matrix re-evaluated)
5. On approval: changes applied; amendment record locked

Immutable fields after approval: Supplier, PO Date, PO Number.
Amendable fields: Line quantities, unit costs, delivery date, payment terms, notes.

### 16.8 PO Cancellation

| Scenario | Process |
|----------|---------|
| Cancel before approval | Soft-delete; no impact |
| Cancel after approval | Requires cancellation reason; supplier notification flag |
| Partial cancellation | Cancel specific lines; recompute totals |
| Cancel after partial receipt | Not permitted for received lines; only open lines cancellable |

---

## 17. Goods Receiving

### 17.1 Overview

A **Goods Receipt (GR)** is the documentary record of goods physically received from a supplier, always created against an approved Purchase Order. The GR is the event that triggers inventory stock update.

### 17.2 GR Header Attributes

| Attribute | Description |
|-----------|-------------|
| GR Number | System-generated reference |
| GR Date | Date goods were physically received |
| Reference PO | The PO against which goods are received |
| Supplier | Inherited from PO |
| Received By | User who recorded the receipt |
| Delivery Note Reference | Supplier's delivery note / challan number |
| Warehouse | Warehouse where goods are received |
| Status | Draft / Confirmed |
| Notes | Receipt notes |

### 17.3 GR Line Attributes

| Attribute | Description |
|-----------|-------------|
| PO Line Reference | Links to the specific PO line |
| Product / SKU | Inherited from PO line |
| Ordered Quantity | What was ordered |
| Previously Received | Cumulative quantity from prior GRs |
| Received Quantity | Quantity received in this GR |
| Accepted Quantity | Quantity accepted into stock |
| Rejected Quantity | Quantity rejected (not accepted) |
| Rejection Reason | Reason code for rejection |
| Unit Cost | Cost at time of receipt (may differ from PO) |

### 17.4 GR Workflow

A GR in **Draft** state has no inventory impact. Only **Confirmed** GRs update stock. GRs are immutable after confirmation. Corrections are made via Vendor Returns.

### 17.5 Partial Receipt

Multiple GRs may be created against a single PO. Each GR captures its own received quantity. PO tracks cumulative received quantity per line and auto-updates status accordingly.

### 17.6 Over-Receipt Policy

| Policy Setting | System Behaviour |
|---------------|-----------------|
| **Block** | GR cannot be confirmed; user must reduce quantity |
| **Warn** | Warning displayed; Warehouse Manager can override and confirm |
| **Allow** | Over-receipt permitted without restriction |

Over-receipts are always flagged in audit trail regardless of policy.

### 17.7 Rejected Items

Items that fail physical inspection at receiving are recorded on GR line as Rejected Quantity with a mandatory Rejection Reason. Rejected items do **not** enter inventory stock and automatically trigger a Vendor Return suggestion.

Rejection reasons are configurable per company: Damaged, Wrong Item, Wrong Quantity, Expired, Specification Mismatch, and others.

### 17.8 Inventory Integration

On GR confirmation:

- **Accepted Quantity** triggers a `StockIncreased` event in the Inventory module (Epic 5)
- Stock position updated: `qty_on_hand` increases by accepted quantity
- Unit cost feeds into weighted average cost calculation
- Movement record created in stock ledger (movement type: PURCHASE_RECEIPT)

---

## 18. Vendor Returns

### 18.1 Overview

A **Vendor Return** (RMA) is the formal process of returning previously received goods to the supplier, always initiated against a confirmed Goods Receipt.

### 18.2 RMA Header Attributes

| Attribute | Description |
|-----------|-------------|
| RMA Number | System-generated reference |
| Return Date | Date return is initiated |
| Reference GR | The GR from which goods are being returned |
| Reference PO | Inherited from GR |
| Supplier | Inherited from GR |
| Return Reason | Category-level reason |
| Return Method | Pickup / Courier / Hand-carry |
| Status | Draft / Submitted / Approved / Dispatched / Completed / Cancelled |
| Credit Expected | Whether a supplier credit is expected |
| Replacement Expected | Whether a replacement shipment is expected |
| Replacement PO Reference | Link to replacement PO (if raised) |

### 18.3 Return Line Attributes

| Attribute | Description |
|-----------|-------------|
| GR Line Reference | The specific GR line being returned |
| Product / SKU | Inherited |
| Return Quantity | Quantity being returned (cannot exceed accepted quantity on GR line) |
| Return Reason Detail | Free-text detail for this line |

### 18.4 Return Workflow

```
DRAFT -> SUBMITTED -> APPROVED -> DISPATCHED -> COMPLETED
                          |
                      CANCELLED
```

### 18.5 Return Reasons

Standard configurable reasons: Damaged in Transit, Manufacturing Defect, Wrong Item Delivered, Wrong Quantity Delivered, Expired/Near-Expired, Cancelled Order, Quality Failure, Specification Mismatch, Duplicate Delivery.

### 18.6 Replacement Workflow

If a replacement is expected: RMA is raised and approved; Purchase Officer creates a new PO linked to the RMA; normal PO/GR workflow applies for the replacement.

### 18.7 Inventory Impact

| Event | Inventory Effect |
|-------|-----------------|
| RMA Draft through Approved | No inventory impact |
| RMA Dispatched | `StockReduced` event; qty_on_hand decreases |
| RMA Cancelled after Dispatched | `StockIncreased` event to reverse |

### 18.8 Credit Note Readiness

When a return is completed and Credit Expected is True, a **Credit Note Flag** is set on the return record. The future AP module (Epic 8) will use this to match against supplier credit notes.

---

## 19. Purchase Costing

### 19.1 Purchase Cost Capture

| Cost Component | Captured On | Description |
|----------------|-------------|-------------|
| Unit Cost | PO Line | Agreed price per unit at order time |
| Received Unit Cost | GR Line | Actual cost on receipt (may differ from PO) |
| Line Total | PO / GR | Quantity x Unit Cost |
| Purchase Price Variance | GR | Difference between PO cost and GR cost |

### 19.2 Additional Charges

| Charge Type | Description | Allocation |
|-------------|-------------|------------|
| **Freight** | Transportation/shipping cost | Header level; apportioned to lines |
| **Handling** | Warehouse or third-party handling fees | Header level |
| **Insurance** | Cargo insurance cost | Header level |
| **Other** | Miscellaneous charges with description | Header level |

Apportionment methods (configurable): By Line Value, By Line Quantity, By Line Weight (future), Manual.

### 19.3 Discounts

| Discount Type | Applied On |
|---------------|------------|
| Line Discount % | PO Line |
| Line Discount Amount | PO Line |
| Header Discount % | PO Header |
| Header Discount Amount | PO Header |
| Trade Discount | Configurable at supplier level |

### 19.4 Tax Readiness

Tax fields are captured but not computed in Epic 6. Tax computation engine is in scope for Epic 8.

| Field | Description |
|-------|-------------|
| Tax Category | Applied to supplier or per line |
| Tax Code | Specific tax rule reference |
| Tax Rate | Percentage (informational) |
| Tax Amount | Computed by future tax engine |
| Tax Inclusive | Whether unit cost is tax-inclusive |

### 19.5 Purchase Price Variance (PPV)

PPV = (GR Unit Cost minus PO Unit Cost) x Received Quantity

PPV is computed for each GR line and tracked as a separate cost entry. Significant variances (above a configurable threshold) generate a notification to the Finance Manager.

### 19.6 Future Landed Cost

Epic 6 establishes data model hooks for future landed cost processing:

- Additional charges on GR captured but not yet allocated to unit cost
- A `landed_cost_ready` flag on GR records marks records eligible for landed cost processing
- Landed cost allocation will be performed in Epic 8.x

---

## 20. Purchase Lifecycle

The end-to-end procurement lifecycle:

1. **Need Identification** — Purchase Request raised by requesting department
2. **Internal Approval** — PR routed through Approval Matrix (Approved / Rejected)
3. **Supplier Selection** — Purchase Officer selects supplier using Supplier Master data
4. **Purchase Order Creation** — PO created from approved PR or directly (if policy permits)
5. **PO Approval** — PO routed through Approval Matrix; commitment created on approval
6. **PO Communication** — PO transmitted to supplier (email when enabled; portal in future)
7. **Goods Receiving** — GR created on physical receipt; quantities validated against PO
8. **Discrepancy Handling** — Over-receipt policy enforced; rejections trigger RMA suggestions
9. **Vendor Returns** (if applicable) — RMA raised, approved, dispatched, completed
10. **PO Closure** — Fully Received auto-closes; manual close available with under-receipt justification
11. **Supplier Performance Update** — Rating recomputed after GR confirmation

---

## 21. Supplier Lifecycle

1. **Onboarding Request** — Purchase Officer creates supplier in DRAFT
2. **Supplier Qualification** — Contacts, addresses, tax, bank details populated; documents uploaded
3. **Activation** — Purchase Manager reviews and activates (ACTIVE); supplier eligible for POs
4. **Operational Phase** — Supplier receives POs, delivers goods; performance rating continuously updated
5. **Review and Rating** — Periodic performance review; preferred status assigned or removed
6. **Deactivation (Temporary)** — INACTIVE status; not available for new POs; can be re-activated
7. **Blocking (Dispute/Compliance)** ��� BLOCKED status; purchase operations suspended; open POs flagged
8. **Reactivation** — Block resolved; ACTIVE status restored with reason required
9. **Archival** — ARCHIVED — permanently decommissioned; soft-deleted; historical data retained

---

## 22. Business Workflows

### 22.1 Standard Purchase Workflow (With PR Approval)

```
Requestor -> [Create PR] -> Approver -> [Approve PR]
-> Purchase Officer -> [Create PO] -> Approver -> [Approve PO]
-> Supplier -> [Deliver Goods]
-> Store Keeper -> [Create and Confirm GR]
-> [Inventory Updated] -> [PO Status Updated]
```

### 22.2 Direct PO Workflow (Without PR — if policy permits)

Purchase Officer directly creates PO, submits for PO approval, approved, delivery, GR.

### 22.3 Vendor Return Workflow

```
Store Keeper -> [Create RMA] -> Warehouse Manager -> [Approve RMA]
-> Store Keeper -> [Dispatch Goods] -> [Mark Dispatched]
-> Purchase Officer -> [Mark Completed on Supplier Confirmation]
-> [Inventory Reduced] -> [Credit Note Flag Set]
```

### 22.4 Supplier Onboarding Workflow

```
Purchase Officer -> [Create Supplier in DRAFT] -> [Add Contacts, Addresses, Tax Info] -> [Upload Documents]
-> Purchase Manager -> [Review and Add Bank Details (Finance Manager)]
-> Purchase Manager -> [Activate Supplier]
-> Supplier now ACTIVE for purchase operations
```

---

## 23. Functional Requirements

### 23.1 Supplier Master Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-SM-01 | System MUST allow creation of supplier records with all standard attributes | P1 |
| FR-SM-02 | Each supplier MUST have a unique supplier code per company | P1 |
| FR-SM-03 | System MUST enforce supplier status lifecycle transitions with audit | P1 |
| FR-SM-04 | Blocked suppliers MUST NOT be selectable on new purchase documents | P1 |
| FR-SM-05 | System MUST support multiple contacts per supplier with role designation | P1 |
| FR-SM-06 | System MUST support multiple addresses per supplier with type designation | P1 |
| FR-SM-07 | System MUST allow payment term assignment per supplier with PO-level override | P1 |
| FR-SM-08 | System MUST capture and enforce credit limits with configurable enforcement mode | P1 |
| FR-SM-09 | System MUST compute and display supplier rating based on GR performance data | P1 |
| FR-SM-10 | System MUST support supplier document attachments with expiry tracking | P1 |
| FR-SM-11 | System MUST support company-defined custom fields on supplier records | P2 |
| FR-SM-12 | System MUST soft-delete suppliers; no hard deletes permitted | P1 |
| FR-SM-13 | System MUST record all supplier record changes in audit trail | P1 |
| FR-SM-14 | System MUST prevent activation of suppliers with missing required fields | P1 |

### 23.2 Procurement Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-PR-01 | System MUST allow authorised users to create Purchase Requests | P1 |
| FR-PR-02 | PRs MUST contain one or more line items with product, quantity, and estimated cost | P1 |
| FR-PR-03 | System MUST route PRs through the Approval Matrix on submission | P1 |
| FR-PR-04 | System MUST prevent a user from approving their own PR | P1 |
| FR-PR-05 | Approved PRs MUST be convertible to Purchase Orders | P1 |
| FR-PR-06 | Rejected PRs MUST capture rejection reason and notify the requestor | P1 |
| FR-PR-07 | System MUST enforce configurable approval matrices per company | P1 |
| FR-PR-08 | System MUST support multi-level sequential and parallel approval | P1 |
| FR-PR-09 | System MUST support approval delegation with time limits | P2 |
| FR-PR-10 | System MUST escalate un-actioned approvals after configured days | P2 |

### 23.3 Purchase Order Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-PO-01 | System MUST allow PO creation from approved PR or directly (per policy) | P1 |
| FR-PO-02 | POs MUST support one or more line items with product, quantity, unit cost | P1 |
| FR-PO-03 | System MUST enforce PO approval workflow before PO can trigger GR | P1 |
| FR-PO-04 | System MUST prevent PO creation against a Blocked supplier | P1 |
| FR-PO-05 | System MUST auto-generate PO numbers in company-configured format | P1 |
| FR-PO-06 | System MUST track PO status through all defined lifecycle states | P1 |
| FR-PO-07 | System MUST prevent editing of approved POs without an amendment request | P1 |
| FR-PO-08 | PO amendments MUST trigger re-approval through the Approval Matrix | P1 |
| FR-PO-09 | System MUST compute PO totals including charges, discounts, and taxes | P1 |
| FR-PO-10 | System MUST allow PO cancellation with reason code at any pre-receipt state | P1 |
| FR-PO-11 | System MUST track expected delivery date and highlight overdue POs | P1 |
| FR-PO-12 | Closed POs MUST be immutable; no further GRs permitted | P1 |

### 23.4 Goods Receiving Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-GR-01 | System MUST allow GR creation only against approved POs | P1 |
| FR-GR-02 | GR MUST display ordered quantity, previously received, and open quantity per line | P1 |
| FR-GR-03 | System MUST support partial receipt across multiple GRs per PO | P1 |
| FR-GR-04 | System MUST enforce the company's over-receipt policy | P1 |
| FR-GR-05 | Confirmed GRs MUST trigger inventory stock update via Epic 5 | P1 |
| FR-GR-06 | System MUST support line-level rejection with reason codes | P1 |
| FR-GR-07 | Confirmed GRs MUST be immutable; corrections via Vendor Returns only | P1 |
| FR-GR-08 | System MUST auto-update PO status on GR confirmation | P1 |
| FR-GR-09 | System MUST record all GR events in audit trail | P1 |

### 23.5 Vendor Returns Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-VR-01 | System MUST allow RMA creation against a confirmed GR | P1 |
| FR-VR-02 | Return quantity MUST NOT exceed accepted quantity on the referenced GR line | P1 |
| FR-VR-03 | RMAs MUST route through a configurable approval workflow | P1 |
| FR-VR-04 | Inventory MUST be reduced on RMA dispatch confirmation | P1 |
| FR-VR-05 | System MUST support credit note flagging on completed RMAs | P1 |
| FR-VR-06 | System MUST support linkage of RMA to a replacement PO | P2 |
| FR-VR-07 | System MUST record all RMA state changes in audit trail | P1 |

### 23.6 Purchase Costing Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-PC-01 | System MUST capture unit cost at PO line level | P1 |
| FR-PC-02 | System MUST support additional charges at PO header level | P1 |
| FR-PC-03 | System MUST support line-level and header-level discounts | P1 |
| FR-PC-04 | System MUST compute and display PO totals: subtotal, charges, discounts, total | P1 |
| FR-PC-05 | System MUST compute and display PPV (GR cost vs PO cost) per line | P1 |
| FR-PC-06 | System MUST capture tax fields for future AP integration | P2 |

---

## 24. Non-Functional Requirements

### 24.1 Performance

| Requirement | Target |
|-------------|--------|
| Supplier list page load | < 500ms at p95 |
| PO list with filters | < 500ms at p95 |
| GR creation and confirmation | < 2 seconds |
| Approval workflow notification | < 1 second |
| Standard report generation | < 5 seconds |
| Search results | < 300ms at p95 |
| Bulk import (1,000 suppliers) | < 60 seconds |

### 24.2 Scalability

| Dimension | Target |
|-----------|--------|
| Suppliers per company | 100,000 |
| POs per company per year | 500,000 |
| GRs per company per year | 1,000,000 |
| Concurrent users per company | 500 |
| Total companies | 10,000 |

### 24.3 Availability

| Requirement | Target |
|-------------|--------|
| Service availability | 99.9% uptime |
| RTO | < 1 hour |
| RPO | < 15 minutes |

### 24.4 Reliability

- All procurement state transitions are ACID-compliant
- No purchase order can be lost once submitted
- Inventory updates from GR are transactional (all-or-nothing)
- Audit trail is write-once (no updates or deletes on audit records)

---

## 25. Business Rules

### 25.1 Supplier Rules

| Rule ID | Rule |
|---------|------|
| BR-SM-01 | A supplier must be in ACTIVE status to be selected on any purchase document |
| BR-SM-02 | A supplier code must be unique within a company |
| BR-SM-03 | A supplier with open (Approved/Partially Received) POs cannot be archived |
| BR-SM-04 | Blocking a supplier must generate a notification to open PO owners |
| BR-SM-05 | Supplier rating is recomputed after every GR confirmation for that supplier |
| BR-SM-06 | Preferred supplier designation can only be changed by a Purchase Manager |
| BR-SM-07 | Credit limit enforcement is evaluated at PO approval, not at PO creation |

### 25.2 Procurement Rules

| Rule ID | Rule |
|---------|------|
| BR-PR-01 | A PR must be in APPROVED status before it can be converted to a PO |
| BR-PR-02 | A user cannot approve a PR they created |
| BR-PR-03 | A PR can only be converted to one PO (one-to-one) |
| BR-PR-04 | Cancelling an approved PR does not cancel any PO already created from it |
| BR-PR-05 | The approval matrix must always have at least one active approver at each level |

### 25.3 Purchase Order Rules

| Rule ID | Rule |
|---------|------|
| BR-PO-01 | A PO must reference a valid, active supplier |
| BR-PO-02 | A PO must have at least one line item |
| BR-PO-03 | All PO line quantities must be greater than zero |
| BR-PO-04 | An approved PO can only be modified via the PO Amendment workflow |
| BR-PO-05 | A cancelled PO cannot be reopened; a new PO must be created |
| BR-PO-06 | A PO can only be closed when all lines are Fully Received or Cancelled |
| BR-PO-07 | A PO expected delivery date less than the supplier's lead time triggers a warning |

### 25.4 Goods Receiving Rules

| Rule ID | Rule |
|---------|------|
| BR-GR-01 | A GR can only be created against a PO in APPROVED or PARTIALLY RECEIVED status |
| BR-GR-02 | Received quantity per GR line cannot be negative |
| BR-GR-03 | A confirmed GR cannot be edited, amended, or deleted |
| BR-GR-04 | Over-receipt is only permitted when company policy is Warn or Allow |
| BR-GR-05 | GR confirmation must be atomic — all lines confirmed or none |
| BR-GR-06 | A GR against a closed or cancelled PO is not permitted |

### 25.5 Vendor Return Rules

| Rule ID | Rule |
|---------|------|
| BR-VR-01 | Return quantity cannot exceed the accepted quantity on the referenced GR line |
| BR-VR-02 | A return can only be initiated against a confirmed (not Draft) GR |
| BR-VR-03 | Inventory deduction occurs on dispatch, not on RMA approval |
| BR-VR-04 | A completed RMA cannot be reversed; a new PO (replacement) must be created |
| BR-VR-05 | An RMA against a blocked supplier must be flagged for Finance review |

---

## 26. Business Invariants

| Invariant | Description |
|-----------|-------------|
| INV-01 | A PO's total received quantity can never exceed its ordered quantity when over-receipt policy is BLOCK |
| INV-02 | A return quantity can never exceed the accepted received quantity for that GR line |
| INV-03 | A purchase document can never reference a soft-deleted supplier |
| INV-04 | Every purchase document must have a valid company_id — cross-tenant access is impossible |
| INV-05 | Audit trail records are append-only — no modification or deletion is permitted |
| INV-06 | A PO in APPROVED or later status must have at least one approval record |
| INV-07 | A GR's confirmed inventory update is always paired with a stock movement record in Epic 5 |
| INV-08 | Supplier rating is always in the range 1.00 to 5.00 |

---

## 27. Validation Rules

### 27.1 Supplier Validation

| Field | Rule |
|-------|------|
| Legal Name | Required; minimum 2 characters; maximum 200 characters |
| Supplier Code | Required; unique per company; alphanumeric + hyphen; max 30 chars |
| Supplier Type | Required; must be Goods / Services / Both |
| Email (Contact) | Must be valid email format if provided |
| Credit Limit | Must be >= 0 |
| Lead Time | Must be >= 0 days |
| Rating | Must be between 1.00 and 5.00 if provided |

### 27.2 Purchase Request Validation

| Field | Rule |
|-------|------|
| Title | Required; max 500 characters |
| Requested By | Must be a valid, active user in the company |
| Required By Date | Must be >= today's date |
| Line Product | Must be a valid, active product in Inventory (Epic 5) |
| Line Quantity | Required; must be > 0 |
| Estimated Cost | Must be >= 0 if provided |

### 27.3 Purchase Order Validation

| Field | Rule |
|-------|------|
| Supplier | Required; must be ACTIVE |
| PO Date | Required |
| Expected Delivery Date | Must be >= PO Date |
| Line Quantity | Required; must be > 0 |
| Unit Cost | Required; must be >= 0 |
| Discount % | Must be between 0 and 100 |

### 27.4 Goods Receipt Validation

| Field | Rule |
|-------|------|
| Reference PO | Must be APPROVED or PARTIALLY RECEIVED |
| GR Date | Cannot be before PO Approved Date |
| Received Quantity | Must be > 0 |
| Received Quantity | Must not exceed ordered quantity when over-receipt policy is BLOCK |
| Rejection Reason | Required when Rejected Quantity > 0 |

### 27.5 Vendor Return Validation

| Field | Rule |
|-------|------|
| Reference GR | Must be CONFIRMED |
| Return Quantity | Must be > 0 |
| Return Quantity | Cannot exceed accepted quantity on referenced GR line |
| Return Reason | Required |

---

## 28. Permission Matrix

The Permission Matrix defines which roles (from Epic 4) have access to which purchase operations.

### 28.1 Supplier Master Permissions

| Operation | Super Admin | Owner | Purchase Mgr | Purchase Officer | Store Keeper | Warehouse Mgr | Finance Mgr | Approver | Auditor | Viewer |
|-----------|:-----------:|:-----:|:------------:|:----------------:|:------------:|:-------------:|:-----------:|:--------:|:-------:|:------:|
| View Supplier | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Create Supplier | Yes | Yes | Yes | Yes | No | No | No | No | No | No |
| Edit Supplier | Yes | Yes | Yes | Limited | No | No | No | No | No | No |
| Activate / Deactivate | Yes | Yes | Yes | No | No | No | No | No | No | No |
| Block / Unblock | Yes | Yes | Yes | No | No | No | No | No | No | No |
| Archive Supplier | Yes | Yes | Yes | No | No | No | No | No | No | No |
| View Bank Details | Yes | Yes | Yes | No | No | No | Yes | No | Yes | No |
| Edit Bank Details | Yes | Yes | Yes | No | No | No | Yes | No | No | No |

### 28.2 Purchase Request Permissions

| Operation | Super Admin | Owner | Purchase Mgr | Purchase Officer | Store Keeper | Warehouse Mgr | Finance Mgr | Approver | Auditor | Viewer |
|-----------|:-----------:|:-----:|:------------:|:----------------:|:------------:|:-------------:|:-----------:|:--------:|:-------:|:------:|
| View PR | Yes | Yes | Yes | Yes | Yes (own) | Yes | Yes | Yes (assigned) | Yes | Yes |
| Create PR | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes | No | No |
| Approve / Reject PR | Yes | Yes | Yes | No | No | No | Yes | Yes (if assigned) | No | No |
| Cancel PR | Yes | Yes | Yes | Yes (own) | Yes (own) | No | No | No | No | No |
| Convert PR to PO | Yes | Yes | Yes | Yes | No | No | No | No | No | No |

### 28.3 Purchase Order Permissions

| Operation | Super Admin | Owner | Purchase Mgr | Purchase Officer | Store Keeper | Warehouse Mgr | Finance Mgr | Approver | Auditor | Viewer |
|-----------|:-----------:|:-----:|:------------:|:----------------:|:------------:|:-------------:|:-----------:|:--------:|:-------:|:------:|
| View PO | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes (assigned) | Yes | Yes |
| Create PO | Yes | Yes | Yes | Yes | No | No | No | No | No | No |
| Edit PO (Draft) | Yes | Yes | Yes | Yes | No | No | No | No | No | No |
| Approve / Reject PO | Yes | Yes | Yes | No | No | No | Yes | Yes (if assigned) | No | No |
| Amend Approved PO | Yes | Yes | Yes | Yes | No | No | No | No | No | No |
| Cancel PO | Yes | Yes | Yes | Yes | No | No | No | No | No | No |

### 28.4 Goods Receiving Permissions

| Operation | Super Admin | Owner | Purchase Mgr | Purchase Officer | Store Keeper | Warehouse Mgr | Finance Mgr | Approver | Auditor | Viewer |
|-----------|:-----------:|:-----:|:------------:|:----------------:|:------------:|:-------------:|:-----------:|:--------:|:-------:|:------:|
| View GR | Yes | Yes | Yes | Yes | Yes | Yes | Yes | No | Yes | Yes |
| Create GR | Yes | Yes | Yes | Yes | Yes | Yes | No | No | No | No |
| Confirm GR | Yes | Yes | Yes | Yes | Yes | Yes | No | No | No | No |
| Override Over-Receipt | Yes | Yes | Yes | No | No | Yes | No | No | No | No |

### 28.5 Vendor Return Permissions

| Operation | Super Admin | Owner | Purchase Mgr | Purchase Officer | Store Keeper | Warehouse Mgr | Finance Mgr | Approver | Auditor | Viewer |
|-----------|:-----------:|:-----:|:------------:|:----------------:|:------------:|:-------------:|:-----------:|:--------:|:-------:|:------:|
| View RMA | Yes | Yes | Yes | Yes | Yes | Yes | Yes | No | Yes | Yes |
| Create RMA | Yes | Yes | Yes | Yes | Yes | Yes | No | No | No | No |
| Approve RMA | Yes | Yes | Yes | No | No | Yes | No | No | No | No |
| Mark Dispatched | Yes | Yes | Yes | Yes | Yes | Yes | No | No | No | No |
| Mark Completed | Yes | Yes | Yes | Yes | No | Yes | No | No | No | No |

---

## 29. Feature Matrix

### 29.1 Supplier Master Features

| Feature | State | Flag Key |
|---------|-------|----------|
| Supplier creation and management | Ready and Enabled | — |
| Supplier categories | Ready and Enabled | — |
| Supplier contacts and addresses | Ready and Enabled | — |
| Payment terms | Ready and Enabled | — |
| Credit limit enforcement | Ready and Disabled | `purchase.credit_limit_enforcement` |
| Supplier rating (computed) | Ready and Enabled | — |
| Supplier documents | Ready and Enabled | — |
| Custom fields | Ready and Enabled | — |
| Bank details capture | Ready and Enabled | — |
| Lead time configuration | Ready and Enabled | — |
| Preferred supplier designation | Ready and Enabled | — |
| Document expiry alerts | Ready and Disabled | `purchase.supplier_document_alerts` |
| Supplier portal access | Future | — |

### 29.2 Procurement Features

| Feature | State | Flag Key |
|---------|-------|----------|
| Purchase Request creation | Ready and Enabled | — |
| PR approval workflow | Ready and Enabled | — |
| PR approval required (gate) | Ready and Disabled | `purchase.pr_approval_required` |
| Multi-level approval matrix | Ready and Enabled | — |
| Approval delegation | Ready and Disabled | `purchase.approval_delegation` |
| Approval escalation | Ready and Disabled | `purchase.approval_escalation_days` |
| Budget validation | Future | — |
| RFQ from PR | Future | — |

### 29.3 Purchase Order Features

| Feature | State | Flag Key |
|---------|-------|----------|
| Purchase Order creation | Ready and Enabled | — |
| PO approval workflow | Ready and Enabled | — |
| PO approval required (gate) | Ready and Disabled | `purchase.po_approval_required` |
| Direct PO without PR | Ready and Enabled | `purchase.direct_po_allowed` |
| PO amendment workflow | Ready and Enabled | — |
| Auto PO number generation | Ready and Enabled | — |
| PO cancellation | Ready and Enabled | — |
| PO PDF export | Ready and Enabled | — |
| Email PO to supplier | Ready and Disabled | `purchase.po_email_supplier` |
| Blanket / Frame POs | Future | — |

### 29.4 Goods Receiving Features

| Feature | State | Flag Key |
|---------|-------|----------|
| Goods Receipt recording | Ready and Enabled | — |
| Partial receipt | Ready and Enabled | — |
| Over-receipt policy enforcement | Ready and Enabled | `purchase.over_receipt_policy` |
| Rejection recording | Ready and Enabled | — |
| Inventory update on GR | Ready and Enabled | — |
| Quality hold | Future | — |
| Barcode scanning on GR | Ready and Disabled | `purchase.gr_barcode_scan` |

### 29.5 Vendor Returns Features

| Feature | State | Flag Key |
|---------|-------|----------|
| Vendor Return (RMA) creation | Ready and Enabled | — |
| Return approval workflow | Ready and Enabled | — |
| Credit note flag | Ready and Enabled | — |
| Replacement PO linkage | Ready and Enabled | — |
| Supplier credit note matching | Future | — |

### 29.6 Purchase Costing Features

| Feature | State | Flag Key |
|---------|-------|----------|
| Unit cost capture | Ready and Enabled | — |
| Additional charges | Ready and Enabled | — |
| Discounts (line and header) | Ready and Enabled | — |
| PPV tracking | Ready and Enabled | — |
| Tax readiness fields | Ready and Enabled | — |
| Tax computation | Future | — |
| Landed cost computation | Future | — |
| Multi-currency pricing | Future | — |

### 29.7 Intelligence Features

| Feature | State | Flag Key |
|---------|-------|----------|
| Standard purchase reports (14) | Ready and Enabled | — |
| Supplier performance KPIs | Ready and Enabled | — |
| Purchase KPI dashboard | Ready and Enabled | — |
| AI purchase forecasting | Future | — |
| AI supplier risk scoring | Future | — |
| AI reorder suggestions | Ready and Disabled | `purchase.ai_reorder_suggestions` |

---

## 30. Procurement Governance

### 30.1 Approval Governance

- No purchase commitment can be made to a supplier without at least one authorised approver confirming the purchase
- Approval records are immutable once submitted
- All approval decisions (approve, reject, abstain) are recorded with timestamp and user identity
- Purchase Manager may audit all approval history at any time

### 30.2 Spending Governance

- **Single-sourcing justification**: If a non-preferred supplier is selected for a category where a preferred supplier exists, a justification note is required
- **Repeat supplier validation**: When the same supplier receives POs exceeding a configurable monthly/annual threshold, a notification is sent to Purchase Manager and Finance Manager
- **Emergency procurement**: Purchase Manager may bypass the normal approval workflow for emergency purchases, but must document the justification. All bypasses are audited and reported

### 30.3 Supplier Governance

- Supplier onboarding requires review and activation by a Purchase Manager or higher
- Supplier blocking and archiving are restricted to Purchase Manager level
- Supplier bank details can only be entered and modified by Finance Manager level
- Supplier performance reviews must be conducted at configurable intervals

### 30.4 Audit Governance

- Every state transition on every procurement document is recorded with actor identity and timestamp
- All field-level changes to supplier records are recorded (old value to new value)
- Audit records cannot be modified, deleted, or hidden from Auditor role
- Audit data is retained per the Data Retention Policy (section 42)

---

## 31. Conceptual Domain Model

The following relationships define the key entities in the Purchase Management domain:

- **Company** contains: SupplierCategories, Suppliers, ApprovalMatrix, PurchasePolicy, PurchaseRequests, PurchaseOrders, GoodsReceipts, VendorReturns
- **Supplier** has: SupplierContacts (1..N), SupplierAddresses (1..N), PaymentTerms, CreditLimit, SupplierDocuments, SupplierRating, BankDetails
- **SupplierCategory** classifies Suppliers (hierarchical parent/child)
- **PurchaseRequest** has: PRLines (1..N referencing Products from Epic 5), ApprovalRecords, converts to one PurchaseOrder
- **PurchaseOrder** references Supplier, has: POLines (1..N referencing Products), POAdditionalCharges, ApprovalRecords, POAmendments, GoodsReceipts (1..N)
- **GoodsReceipt** references PurchaseOrder, has: GRLines (1..N referencing POLines), triggers Inventory events, has VendorReturns (0..N)
- **VendorReturn** references GoodsReceipt, has: ReturnLines (1..N), optionally links to Replacement PurchaseOrder

---

## 32. Aggregate Roots

| Aggregate Root | Owned Entities | Invariants Enforced |
|----------------|----------------|---------------------|
| **Supplier** | SupplierContact, SupplierAddress, BankDetails, SupplierDocument, SupplierRating, CreditLimit | Status lifecycle; unique code; credit limit range |
| **PurchaseRequest** | PRLine, ApprovalRecord | Self-approval prevention; at least one line; approved-before-convert |
| **PurchaseOrder** | POLine, POAdditionalCharge, ApprovalRecord, POAmendment | Immutability after approval; unique PO number; valid supplier |
| **GoodsReceipt** | GRLine | Confirmed equals immutable; over-receipt policy; quantity constraints |
| **VendorReturn** | ReturnLine | Return quantity <= accepted quantity; against confirmed GR only |
| **ApprovalMatrix** | MatrixRule, ApprovalLevel | At least one approver per level; no circular assignments |

---

## 33. Domain Events

Domain events are published whenever a significant procurement state change occurs. All services subscribe via the platform `InProcessEventBus` (consistent with Epic 5's event architecture).

### 33.1 Supplier Events (9)

| Event | Trigger |
|-------|---------|
| `SupplierCreated` | Supplier record created |
| `SupplierUpdated` | Supplier attributes modified |
| `SupplierActivated` | Supplier status changed to ACTIVE |
| `SupplierDeactivated` | Supplier status changed to INACTIVE |
| `SupplierBlocked` | Supplier status changed to BLOCKED |
| `SupplierReactivated` | Supplier status changed from BLOCKED/INACTIVE to ACTIVE |
| `SupplierArchived` | Supplier soft-deleted |
| `SupplierRatingUpdated` | Rating recomputed after GR |
| `PreferredSupplierDesignated` | Preferred flag set or unset |

### 33.2 Purchase Request Events (5)

| Event | Trigger |
|-------|---------|
| `PurchaseRequested` | PR submitted for approval |
| `PurchaseRequestApproved` | PR reaches final approval |
| `PurchaseRequestRejected` | Any approver rejects PR |
| `PurchaseRequestCancelled` | PR cancelled |
| `PurchaseRequestConverted` | PR converted to PO |

### 33.3 Purchase Order Events (7)

| Event | Trigger |
|-------|---------|
| `PurchaseOrdered` | PO approved and committed |
| `PurchaseOrderApproved` | PO receives final approval |
| `PurchaseOrderRejected` | PO rejected in approval |
| `PurchaseOrderAmended` | PO amendment approved |
| `PurchaseOrderCancelled` | PO cancelled |
| `PurchaseOrderClosed` | PO manually closed |
| `PurchaseOrderFullyReceived` | All lines received |

### 33.4 Goods Receiving Events (4)

| Event | Trigger |
|-------|---------|
| `GoodsReceived` | GR confirmed |
| `GoodsRejected` | GR line has rejection quantity > 0 |
| `GoodsPartiallyReceived` | GR confirmed with under-receipt on at least one line |
| `OverReceiptDetected` | Received quantity exceeds ordered quantity |

### 33.5 Vendor Return Events (4)

| Event | Trigger |
|-------|---------|
| `GoodsReturnInitiated` | RMA submitted |
| `GoodsReturnApproved` | RMA approved |
| `GoodsReturned` | RMA dispatched |
| `GoodsReturnCompleted` | RMA completed |

### 33.6 Cost Events (3)

| Event | Trigger |
|-------|---------|
| `PurchaseCostRecorded` | GR confirmed with cost data |
| `PurchasePriceVarianceDetected` | PPV exceeds configured threshold |
| `AdditionalChargeRecorded` | Freight/handling/insurance recorded on PO or GR |

**Total Domain Events: 32**

---

## 34. Reporting Requirements

The Purchase Management module provides a minimum of 14 standard reports. All reports are:
- Scoped by company_id (multi-tenant isolation)
- Filterable by date range, supplier, category, status, and user
- Exportable to CSV and PDF
- Access-controlled by RBAC

| Report # | Report Name | Description | Primary Audience |
|----------|-------------|-------------|-----------------|
| RPT-01 | Purchase Order Summary | All POs with status, supplier, value, and dates | Purchase Manager, Finance |
| RPT-02 | Pending Purchase Orders | Open POs not yet fully received, sorted by expected delivery | Purchase Officer, Warehouse |
| RPT-03 | Overdue Deliveries | POs past expected delivery date with no GR | Purchase Manager |
| RPT-04 | Goods Receipt Report | All GRs in period with quantities and cost | Store Keeper, Finance |
| RPT-05 | Purchase Request Status | All PRs with status and age | Purchase Officer, Manager |
| RPT-06 | Supplier Performance Report | Per-supplier: on-time rate, fill rate, rejection rate, rating | Purchase Manager |
| RPT-07 | Vendor Return Report | All RMAs in period with status and amounts | Purchase Manager, Finance |
| RPT-08 | Purchase by Supplier | Total spend per supplier in period | Finance Manager, Owner |
| RPT-09 | Purchase by Category | Total spend per category in period | Finance Manager, Owner |
| RPT-10 | Purchase Price Variance | PO cost vs GR cost variance per line | Finance Manager |
| RPT-11 | Open Purchase Commitments | All approved POs with open value (not yet received) | Finance Manager |
| RPT-12 | Purchase Trend Analysis | Monthly/quarterly purchase volume and value trends | Owner, Finance Manager |
| RPT-13 | Goods Rejection Analysis | Rejected items by supplier, reason, and value | Purchase Manager, Warehouse |
| RPT-14 | Procurement Audit Trail | Complete event history per document or supplier | Auditor |

---

## 35. KPI Requirements

| KPI # | KPI Name | Calculation | Target |
|-------|----------|-------------|--------|
| KPI-01 | **Purchase Cycle Time** | Avg days from PR creation to PO approval | <= 5 days |
| KPI-02 | **Supplier On-Time Delivery Rate** | GRs confirmed on/before expected date / total GRs | >= 90% |
| KPI-03 | **Order Fulfilment Rate** | Received quantity / ordered quantity across all POs | >= 95% |
| KPI-04 | **Supplier Rejection Rate** | Rejected GR lines / total GR lines | <= 2% |
| KPI-05 | **Purchase Price Variance %** | Avg PPV as % of PO value | <= 3% |
| KPI-06 | **Open Purchase Commitments** | Total value of approved, un-received POs | Monitored |
| KPI-07 | **Total Purchase Value (Period)** | Sum of confirmed GR values in period | Trended |
| KPI-08 | **Average PO Processing Time** | Avg days from PO creation to approval | <= 2 days |
| KPI-09 | **Vendor Return Rate** | RMA quantity / GR quantity | <= 3% |
| KPI-10 | **Preferred Supplier Utilisation** | POs to preferred suppliers / total POs | >= 70% |

---

## 36. Search Requirements

### 36.1 Global Purchase Search

A unified search across all purchase entities from a single input: Supplier name/code/contact, PO number/supplier reference, PR number/title, GR number/delivery note, RMA number.

### 36.2 Supplier Search Dimensions

Full-text name search; exact/prefix code search; category, status, city/country, rating range, preferred supplier, custom field filters.

### 36.3 Purchase Order Search Dimensions

PO number, supplier (autocomplete), date range, status (multi-select), amount range, created by (user filter), delivery date range.

### 36.4 Advanced Filters and Sorting

- All list views support multi-column sorting (ascending/descending)
- Saved filter sets per user (up to 10 per entity type)
- Filter state persisted in URL for sharing
- Results pagination: 10 / 25 / 50 / 100 per page
- Export filtered results to CSV or PDF

---

## 37. Import and Export

### 37.1 Supplier Import

| Capability | Format | Max Records | Notes |
|------------|--------|-------------|-------|
| Bulk supplier import | CSV, Excel (.xlsx) | 10,000 per batch | With validation report |
| Import template download | CSV, Excel | — | Pre-formatted with required/optional columns |
| Import result report | CSV | — | Row-level success/failure with error details |
| Duplicate detection | — | — | Warns on matching supplier code or name |

### 37.2 Data Export

| Entity | Formats | Scope |
|--------|---------|-------|
| Suppliers | CSV, Excel, PDF | Full list or filtered |
| Purchase Orders | CSV, Excel, PDF | Full list or filtered |
| Goods Receipts | CSV, Excel | Full list or filtered |
| All 14 reports | CSV, Excel, PDF | Per report |

### 37.3 PO Document Export

Each PO can be exported/printed as a formatted PDF including company header, supplier details, line items, terms, and totals. Suitable for sending to supplier as a formal order document.

---

## 38. Notifications

### 38.1 In-App Notifications

| Event | Recipients |
|-------|-----------|
| New PR submitted for approval | Assigned approver(s) |
| PR approved or rejected | Requestor |
| New PO submitted for approval | Assigned approver(s) |
| PO approved or rejected | Purchase Officer who created it |
| PO delivery date approaching (3 days) | Purchase Officer |
| PO delivery overdue | Purchase Officer, Purchase Manager |
| GR confirmed | Purchase Officer |
| Over-receipt detected | Warehouse Manager, Purchase Manager |
| Supplier blocked | Purchase Officer, Finance Manager |
| RMA submitted for approval | Warehouse Manager |
| Document expiry approaching | Purchase Manager |
| High PPV detected | Finance Manager |

### 38.2 Email Notifications

Sent for high-importance events (configurable per company): PR/PO pending approval, PR/PO approved/rejected, PO overdue delivery, supplier blocked, high-value PPV detection.

### 38.3 SMS and WhatsApp Notifications

Ready and Disabled. Requires `purchase.sms_notifications` and `purchase.whatsapp_notifications` feature flags. Supported events: PO approval required (urgent), overdue PO delivery alert.

### 38.4 Push Notifications

Future — requires mobile application.

---

## 39. Audit Requirements

### 39.1 Audit Trail Coverage

| Entity | Audited Events |
|--------|---------------|
| Supplier | Create, all field updates, status transitions, document uploads, bank detail changes |
| Purchase Request | Create, submit, approve, reject, cancel, convert |
| Purchase Order | Create, submit, approve, reject, amend, cancel, close, all line changes |
| Goods Receipt | Create, confirm (with quantities) |
| Vendor Return | Create, submit, approve, dispatch, complete, cancel |
| Approval Matrix | Configuration changes |
| Purchase Policy | Configuration changes |

### 39.2 Audit Record Content

Each record contains: event_type, entity_type, entity_id, company_id, actor_id, actor_name, timestamp, before_state, after_state, ip_address, notes.

### 39.3 Audit Access

- Auditor role: Full read access to all audit records
- Finance Manager: Read access to cost-related audit events
- Purchase Manager: Read access to procurement audit events
- No role can modify or delete audit records

---

## 40. Security Requirements

| Requirement | Detail |
|-------------|--------|
| Authentication | All endpoints require valid JWT token (Epic 2) |
| Authorisation | All operations enforce RBAC role check (Epic 4) |
| Tenant Isolation | company_id enforced on every query; cross-tenant access impossible |
| Sensitive Data | Supplier bank details encrypted at rest; access logged |
| Input Validation | All user inputs validated server-side for type, length, format |
| SQL Injection | Parameterised queries enforced by ORM; no dynamic SQL |
| XSS Prevention | All rendered content sanitised |
| CSRF Protection | CSRF tokens on all state-changing operations |
| Mass Assignment | Only explicitly permitted fields are writable per operation |
| Audit Immutability | Audit records protected by database-level constraints |
| HTTPS | All traffic encrypted in transit (TLS 1.2+) |
| Document Storage | Uploaded documents scanned for malware before storage |

---

## 41. Compliance Requirements

| Requirement | Detail |
|-------------|--------|
| GDPR (EU) | Supplier contact personal data handled per GDPR; deletion/export on request |
| Tax Record Retention | Purchase records retained for legally required period per jurisdiction |
| Financial Audit Trail | Complete, tamper-proof audit trail required for financial compliance |
| Separation of Duties | Creator and approver must be different users on all documents |
| Three-Way Match Readiness | Data structures ready for PO/GR/Invoice matching (future AP) |
| Document Authenticity | PO documents include creation timestamp and approver identity |

---

## 42. Data Retention

| Data Category | Retention Period | Notes |
|---------------|-----------------|-------|
| Purchase Orders | Minimum 7 years | Regulatory minimum in most jurisdictions |
| Goods Receipts | Minimum 7 years | Links to inventory and cost records |
| Vendor Returns | Minimum 7 years | — |
| Audit Trail | Minimum 7 years | Cannot be deleted within retention period |
| Supplier Records | 7 years after last transaction | Soft-deleted but retained |
| Approval Records | Minimum 7 years | Required for financial audit |
| Uploaded Documents | 7 years or document expiry + 1 year (whichever is later) | — |

---

## 43. Disaster Recovery

| Scenario | Recovery Mechanism | RTO | RPO |
|----------|-------------------|-----|-----|
| Database failure | Automated failover to hot standby | < 1 minute | < 1 minute |
| Application server failure | Container orchestration restart | < 2 minutes | Zero (stateless) |
| Data corruption | Point-in-time recovery from WAL | < 1 hour | < 15 minutes |
| Full region outage | Cross-region backup restore | < 4 hours | < 1 hour |
| Accidental data deletion | Soft-delete + 30-day recycle bin | Immediate | Zero |

---

## 44. Performance Targets

All targets are measured at p95 under normal operating load (<= 500 concurrent users per company).

| Operation | Target |
|-----------|--------|
| Supplier list page load | < 500ms |
| Supplier search (full-text) | < 300ms |
| PO list with standard filters | < 500ms |
| PO creation and validation | < 1 second |
| GR confirmation + inventory update | < 2 seconds |
| Approval workflow notification dispatch | < 1 second |
| Standard report generation | < 5 seconds |
| Complex report generation | < 15 seconds |
| Bulk supplier import (1,000 records) | < 60 seconds |
| Dashboard KPI load | < 2 seconds |

---

## 45. Scalability Targets

| Dimension | Target |
|-----------|--------|
| Suppliers per company | 100,000 |
| Purchase Orders per company per year | 500,000 |
| PO Lines per PO | Up to 500 |
| Goods Receipts per company per year | 1,000,000 |
| Concurrent active users per company | 500 |
| Total tenants (companies) on platform | 10,000 |
| Document storage per company | 50 GB |
| Audit trail records per company | Unlimited (partitioned) |

---

## 46. Cross-Module Dependencies

### 46.1 Authentication (Epic 2)

All purchase endpoints require a valid authenticated session. JWT token validated; user identity passed to all purchase operations.

### 46.2 Companies (Epic 3)

`company_id` sourced from company record; company settings (currency, timezone) used. Company must be ACTIVE for functional purchase operations.

### 46.3 Users and Roles (Epic 4)

All RBAC enforcement references Epic 4 roles and permissions. System roles used: owner, admin, purchase-manager, purchase-officer, store-keeper, warehouse-manager, finance-manager, approver, auditor, viewer.

### 46.4 Inventory Management (Epic 5)

- Product/SKU references on PR lines, PO lines, GR lines
- Stock updated on GR confirmation via `GoodsReceived` event consumed by Inventory
- UOM validation: UOM on PO line must be valid in Inventory

### 46.5 Sales (Epic 7 — Future)

Sales module will reference supplier cost for margin calculations.

### 46.6 Accounts Payable (Epic 8 — Future)

AP will use PO reference, GR reference, and supplier bank details for three-way invoice matching.

---

## 47. Cross-Module Contracts

### 47.1 Purchase to Inventory Contract

| Contract | Direction | Trigger | Payload |
|----------|-----------|---------|---------|
| `GoodsReceived` event | Purchase to Inventory | GR confirmed | gr_id, company_id, warehouse_id, lines (product_id, accepted_qty, unit_cost, uom_id) |
| `GoodsReturnDispatched` event | Purchase to Inventory | RMA dispatched | rma_id, company_id, warehouse_id, lines (product_id, return_qty) |
| Product lookup | Purchase to Inventory | PO/PR/GR line creation | Returns name, uom_id, status, is_purchasable |

### 47.2 Purchase to Authentication Contract

Every request validates JWT against Epic 2 auth service. User identity extracted from token; no user data stored in Purchase module.

### 47.3 Purchase to Companies Contract

Purchase reads company currency, timezone, and purchase policy overrides. All queries include `WHERE company_id = ?` enforced at repository layer.

### 47.4 Purchase to Users and Roles Contract

Purchase calls permission check service: `has_permission(user_id, company_id, permission_key)`. Approval matrix references user_id and role names from Epic 4.

---

## 48. Integration Readiness

### 48.1 Barcode Scanning

- Barcode scan on GR line (product identification): Ready and Disabled — `purchase.gr_barcode_scan`
- Barcode scan on RMA line: Ready and Disabled
- QR code generation on PO document: Ready and Disabled — `purchase.po_qr_code`

Integration uses Epic 5's barcode lookup endpoint.

### 48.2 Email Integration

- Email notifications to internal users: Ready and Enabled
- Email PO document to supplier: Ready and Disabled — `purchase.po_email_supplier`
- Email GR confirmation to supplier: Future
- Inbound email parsing (supplier reply): Future

### 48.3 Supplier Portal (Future)

A future self-service portal will allow suppliers to view POs, acknowledge receipt, update delivery status, submit invoices, and manage their profile. The data model in Epic 6 supports supplier portal integration without schema changes.

### 48.4 EDI Integration (Future)

Electronic Data Interchange for automated PO transmission and GR confirmation. Targeted for Epic 11. PO data model includes supplier reference fields required for EDI mapping.

### 48.5 Mobile App (Future)

A future mobile application will support GR recording with barcode scanning, approval workflow from mobile, and delivery tracking.

---

## 49. AI Readiness

### 49.1 Supplier Risk Analysis

Predict supplier reliability risk based on historical performance. Required data: on-time delivery history, rejection rate history, PPV patterns, supplier status history. All data captured in Epic 6. AI scoring engine is Future scope.

### 49.2 Purchase Forecasting

Predict future purchase volumes based on historical patterns and seasonality. Required data: historical GR volumes by product and supplier, seasonal patterns, current inventory levels. Forecasting engine is Future scope.

### 49.3 Demand Prediction

Predict when reorder points will be triggered and pre-generate Purchase Requests. Cross-module integration with Epic 5 reorder data in place.

### 49.4 Reorder Suggestions

Automatically suggest Purchase Requests based on inventory levels and reorder rules. Ready and Disabled — `purchase.ai_reorder_suggestions`.

### 49.5 AI Procurement Assistant

Natural language interface for procurement queries. NLP integration is Future scope. All data is structured and indexed for AI consumption.

---

## 50. Analytics Readiness

### 50.1 Real-Time Analytics

- Live KPI dashboard
- Purchase commitment tracker
- Open PO aging by supplier
- Supplier performance scorecards

### 50.2 Historical Analytics

- Purchase trend analysis (monthly/quarterly/annual)
- Year-over-year spend comparison
- Supplier spend evolution and category spend evolution
- PPV trending

### 50.3 Data Warehouse Readiness

Fact tables: PurchaseOrder, GoodsReceipt, VendorReturn.
Dimension tables: Supplier, Product, User, Date, Category.
SCD (Slowly Changing Dimensions) support for supplier and product name/category changes.
Event log available for real-time streaming to analytics platforms.

---

## 51. Extensibility Strategy

### 51.1 Custom Fields

Every major entity supports company-defined custom fields. Custom fields do not require schema migration; support text/number/date/boolean/list types; can be marked required, searchable, filterable.

### 51.2 Configurable Workflows

Approval matrices, notification rules, and procurement policies are fully configurable per company without code changes. New workflow steps, approval thresholds, and escalation rules are data-driven.

### 51.3 Plugin-Ready Events

All 32 domain events are published via the platform event bus. External systems and future modules can subscribe without modifying the Purchase module.

### 51.4 Feature Flag Architecture

Every optional capability is controlled by a feature flag. New capabilities introduced as Ready and Disabled can be enabled per tenant without deployment.

### 51.5 Version-Tolerant Data Model

All entities use UUIDs as primary keys, soft-delete patterns, and carry forward-compatibility fields. The model is designed to accommodate future attributes without breaking existing integrations.

---

## 52. Versioning Strategy

### 52.1 API Versioning

All purchase API endpoints versioned under `/api/v1/companies/{company_id}/purchase/`. Future breaking changes use `/api/v2/`. Backward compatibility maintained for minimum 12 months after new version publication.

### 52.2 Document Versioning

Purchase Orders and Purchase Requests carry a `version` counter incremented on each amendment. Full change history preserved in amendment/audit records.

### 52.3 Schema Evolution

Additive migrations only (no column renames or drops in active versions). New columns default to NULL or a safe default. Deprecation period of 6 months before column removal.

### 52.4 Feature Flag Versioning

Feature flags namespaced: `purchase.<capability>`. Deprecated flags retained for 12 months with deprecation warning before removal.

---

## 53. Risks

| Risk ID | Risk | Probability | Impact | Mitigation |
|---------|------|-------------|--------|------------|
| R-01 | Approval matrix complexity causes performance bottleneck at high concurrent volumes | Medium | High | Cache approval matrix; evaluate only on submit; benchmark at design time |
| R-02 | Inventory update on GR fails mid-transaction, creating stock inconsistency | Low | Critical | Transactional GR confirmation; compensating events on failure; idempotent stock update |
| R-03 | Scope creep from AP-adjacent features (invoice, payment) bleeding into Epic 6 | High | Medium | Strict out-of-scope enforcement; redirect AP requests to Epic 8 backlog |
| R-04 | Supplier rating algorithm produces unintuitive results, reducing adoption | Medium | Medium | Expose rating components individually; allow manual override; document algorithm |
| R-05 | Multi-currency requirements surface during Epic 6 implementation | Medium | High | Base currency only in Epic 6; currency field captured but single-currency enforced |
| R-06 | Large PO imports or batch GRs cause timeout for users | Medium | Medium | Async processing with progress notification; background job queue for bulk operations |
| R-07 | Data migration from legacy procurement systems reveals missing supplier data | Medium | Medium | Import validation with detailed error reporting; flexible required field enforcement during migration mode |

---

## 54. Assumptions

| ID | Assumption | Rationale |
|----|------------|-----------|
| A-01 | All procurement operates in a single base currency per company in Epic 6 | Simplifies costing; multi-currency is Epic 10 |
| A-02 | Product master is maintained in Epic 5 (Inventory); Purchase module references but does not own products | Consistent with domain boundaries |
| A-03 | Inventory stock positions are managed by Epic 5; Purchase publishes events; Inventory consumes them | Event-driven integration reduces coupling |
| A-04 | Tax computation is out of scope for Epic 6; tax fields captured for future AP use | Tax engines vary by jurisdiction; dedicated Epic 8 scope |
| A-05 | A single approval matrix configuration applies per company; branch-level matrices are Future scope | Reduces configuration complexity in MVP |
| A-06 | Supplier portal and EDI are Future; suppliers receive POs via email (when enabled) or manual communication | Reduces Epic 6 scope without blocking core procurement |
| A-07 | Budget/spend controls are Future; purchase amounts are tracked but not validated against budget allocations | Budget module requires GL integration not available until Epic 8 |
| A-08 | The platform's notification infrastructure (email, SMS) is available from Epic 1/2 | Email infrastructure assumed in-place |

---

## 55. Constraints

| Constraint | Description |
|------------|-------------|
| C-01 | All entities must include company_id for multi-tenant isolation |
| C-02 | No hard deletes — all deletions must use soft-delete pattern |
| C-03 | Audit trail must be append-only; no record modification or deletion permitted |
| C-04 | PO approvals require human action; no fully automated approval chains |
| C-05 | GRs cannot be edited after confirmation; corrections via RMA only |
| C-06 | Purchase module must not own product/inventory data; it references but does not duplicate |
| C-07 | Performance targets in section 44 must be met without sacrificing data consistency |
| C-08 | Feature flags must be per-company; one company's flag state does not affect another |
| C-09 | Bank detail access must be restricted to Finance-level roles; no exceptions |
| C-10 | All domain events must be JSON-serialisable for event bus compatibility with Epic 5's architecture |

---

## 56. Success Metrics

| Metric | Target |
|--------|--------|
| All P1 functional requirements implemented and tested | 100% |
| Purchase request-to-PO cycle time | <= 5 business days (end-to-end) |
| GR confirmation-to-inventory update | < 2 seconds (p95) |
| Supplier search response time | < 300ms (p95) |
| Zero cross-tenant data incidents | 0 incidents |
| Approval workflow adoption rate | >= 90% of POs processed through approval |
| Audit trail completeness | 100% of state transitions recorded |
| Test coverage | >= 90% |
| 14 standard reports available | 100% |
| 10 KPIs operational | 100% |
| Import/export functional | 100% |
| All 32 domain events fired and serialisable | 100% |
| Multi-tenancy isolation verified | 100% |
| RBAC permission matrix verified | 100% |
| Docker Compose startup succeeds | 100% |

---

## 57. Glossary

| Term | Definition |
|------|------------|
| AP | Accounts Payable |
| EDI | Electronic Data Interchange |
| GR / GRN | Goods Receipt / Goods Received Note |
| IBAN | International Bank Account Number |
| KPI | Key Performance Indicator |
| MVP | Minimum Viable Product |
| P1/P2/P3 | Priority levels: P1 = Must Have, P2 = Should Have, P3 = Nice to Have |
| PO | Purchase Order |
| PPV | Purchase Price Variance |
| PR | Purchase Request |
| RBAC | Role-Based Access Control |
| RFQ | Request for Quotation |
| RMA | Return Merchandise Authorisation |
| RPO | Recovery Point Objective |
| RTO | Recovery Time Objective |
| SSOT | Single Source of Truth |
| TLS | Transport Layer Security |
| UOM | Unit of Measure |
| UUID | Universally Unique Identifier |
| VAT | Value Added Tax |
| WAL | Write-Ahead Log (PostgreSQL) |

---

## 58. Acceptance Criteria

Epic 6 is accepted when all of the following criteria are met:

| AC # | Criterion |
|------|-----------|
| AC-01 | Supplier can be created, activated, edited, blocked, reactivated, and archived with full audit trail |
| AC-02 | Purchase Request can be created, submitted, approved (multi-level), rejected, and converted to PO |
| AC-03 | Purchase Order lifecycle (Draft through Closed) including amendment operates correctly |
| AC-04 | PO amendment workflow triggers re-approval |
| AC-05 | Goods Receipt confirmed against a PO triggers inventory stock update in Epic 5 |
| AC-06 | Partial receipt across multiple GRs correctly tracks open quantity per PO line |
| AC-07 | Over-receipt policy enforced per company setting (Block/Warn/Allow) |
| AC-08 | Vendor Return (RMA) reduces inventory on dispatch |
| AC-09 | Credit note flag set on completed RMA |
| AC-10 | Purchase Price Variance computed and visible per GR line |
| AC-11 | Approval matrix with multi-level sequential and parallel approvers functioning correctly |
| AC-12 | Self-approval prevented on all document types |
| AC-13 | Blocked supplier cannot be selected on new purchase documents |
| AC-14 | Credit limit warning/block enforced at PO approval |
| AC-15 | All 14 standard reports return correct data |
| AC-16 | All 10 KPIs display accurate computed values |
| AC-17 | Zero cross-tenant data access (automated tenant isolation tests) |
| AC-18 | Permission matrix enforced — all roles verified against all operations |
| AC-19 | All 32 domain events fired on appropriate triggers and JSON-serialisable |
| AC-20 | Soft-delete verified on all entities (data retained; not visible in operational lists) |
| AC-21 | Audit trail complete for all state transitions |
| AC-22 | Bulk supplier import processes 1,000 records in < 60 seconds with error report |
| AC-23 | Performance targets in section 44 met under normal load |
| AC-24 | Docker Compose build, startup, migrations, and health checks all pass |
| AC-25 | Test coverage >= 90% on all purchase module code |

---

## 59. Epic Completion Criteria

All 15 completion gates must achieve PASS status before Epic 6 is declared complete:

| Gate | Description |
|------|-------------|
| EC-01 | All P1 functional requirements (section 23) implemented and tested |
| EC-02 | All P1 acceptance criteria (section 58) pass in automated test suite |
| EC-03 | Supplier Master: create, activate, block, reactivate, archive working end-to-end |
| EC-04 | Procurement: PR creation, multi-level approval, and PR-to-PO conversion verified |
| EC-05 | Purchase Orders: full lifecycle including amendment verified |
| EC-06 | Goods Receiving: partial receipt, over-receipt policy, inventory update verified |
| EC-07 | Vendor Returns: full RMA workflow (initiate through complete) verified |
| EC-08 | Purchase Costing: PPV computed; additional charges captured; totals correct |
| EC-09 | Reporting: all 14 reports return correct data; all 10 KPIs operational |
| EC-10 | Domain Events: all 32 events fired on correct triggers; JSON-serialisable |
| EC-11 | Multi-tenancy: zero cross-company data incidents across all endpoints |
| EC-12 | RBAC: all roles enforce correct permission boundaries per section 28 |
| EC-13 | Performance: all section 44 p95 targets met under simulated load |
| EC-14 | Audit Trail: every write operation produces audit record |
| EC-15 | Docker: docker compose up, full smoke test, all pass |

---

## 60. Future Roadmap

### 60.1 Epic 6.x — Purchase Management Extensions

| Capability | Description |
|------------|-------------|
| Request for Quotation (RFQ) | Send competitive bids to multiple suppliers; compare quotations |
| Quotation Comparison | Side-by-side supplier quote evaluation matrix |
| Budget Validation | Validate purchase requests against departmental budget allocations |
| Blanket / Frame Purchase Orders | Standing orders for recurring purchases with call-off capability |
| Quality Inspection Workflow | Pre-acceptance quality hold and inspection process |
| Approval Delegation | Time-bound approval delegation to substitute approvers |
| Approval Escalation | Automatic escalation of un-actioned approvals |
| Supplier Document Expiry Alerts | Automated alerts for expiring compliance documents |

### 60.2 Epic 8 — Accounts Payable

| Capability | Description |
|------------|-------------|
| Three-Way Matching | PO, GR, and Supplier Invoice automated matching |
| Invoice Processing | Supplier invoice capture and validation |
| Payment Scheduling | Payment terms enforcement and payment run generation |
| Landed Cost Computation | Allocation of freight, duty, and handling to received goods unit cost |
| Credit Note Processing | Matching supplier credit notes to Vendor Returns |
| Tax Computation Engine | Full purchase tax calculation and reporting |

### 60.3 Epic 9 — Import Purchasing

| Capability | Description |
|------------|-------------|
| Import PO | Purchase orders in foreign currency with customs and duty fields |
| Customs Declaration | Duty, tax, and customs clearance tracking |
| Letter of Credit | LC-based import payment workflow |
| Duty Drawback | Export duty refund tracking |

### 60.4 Epic 10 — Multi-Currency

| Capability | Description |
|------------|-------------|
| Multi-Currency PO | Purchase orders in supplier currency with exchange rate capture |
| Currency Revaluation | Mark-to-market revaluation of open purchase commitments |
| Forex Gain/Loss | Realised forex gain/loss on GR vs PO currency |

### 60.5 Epic 11 — Supplier Collaboration

| Capability | Description |
|------------|-------------|
| Supplier Portal | Self-service supplier web access: PO viewing, delivery updates, invoice submission |
| EDI Integration | Automated PO transmission and order acknowledgement via EDI standards |
| Supplier Onboarding Portal | Self-registration and document submission for new suppliers |

---

*End of Epic 6 — Purchase Management Business Specification*

---

**Document Control**

| Field | Value |
|-------|-------|
| Version | 1.0 |
| Status | Draft — Pending Approval |
| Author | DevSphere ERP Architecture Team |
| Reviewed By | — |
| Approved By | — |
| Approval Date | — |
| Next Review | Prior to Epic 6 planning initiation |
