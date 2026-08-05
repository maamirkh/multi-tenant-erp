# Epic 7 — Sales Management: Official Business Specification

**Document Type**: Official Enterprise Business Specification (SSOT)
**Epic Number**: 007
**Feature Branch**: `007-sales-management`
**Version**: 1.0
**Status**: Draft — Pending Approval
**Created**: 2026-07-30
**Compatible With**: Epic 0 (Constitution), Epic 1 (Foundation), Epic 2 (Authentication), Epic 3 (Companies), Epic 4 (Users & Roles), Epic 5 (Inventory Management), Epic 6 (Purchase Management)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Epic Overview](#2-epic-overview)
3. [Business Vision](#3-business-vision)
4. [Business Goals](#4-business-goals)
5. [Business Scope](#5-business-scope)
6. [Out of Scope](#6-out-of-scope)
7. [Sales Terminology](#7-sales-terminology)
8. [Domain Philosophy](#8-domain-philosophy)
9. [Domain Boundaries](#9-domain-boundaries)
10. [Bounded Context](#10-bounded-context)
11. [Stakeholders](#11-stakeholders)
12. [User Personas](#12-user-personas)
13. [Business Capabilities](#13-business-capabilities)
14. [Customer Master](#14-customer-master)
15. [Sales Quotations](#15-sales-quotations)
16. [Sales Orders](#16-sales-orders)
17. [Order Fulfillment](#17-order-fulfillment)
18. [Sales Invoicing](#18-sales-invoicing)
19. [Sales Returns](#19-sales-returns)
20. [Pricing Engine](#20-pricing-engine)
21. [Sales Lifecycle](#21-sales-lifecycle)
22. [Customer Lifecycle](#22-customer-lifecycle)
23. [Business Workflows](#23-business-workflows)
24. [Functional Requirements](#24-functional-requirements)
25. [Non-Functional Requirements](#25-non-functional-requirements)
26. [Business Rules](#26-business-rules)
27. [Business Invariants](#27-business-invariants)
28. [Validation Rules](#28-validation-rules)
29. [Permission Matrix](#29-permission-matrix)
30. [Feature Matrix](#30-feature-matrix)
31. [Sales Governance](#31-sales-governance)
32. [Conceptual Domain Model](#32-conceptual-domain-model)
33. [Aggregate Roots](#33-aggregate-roots)
34. [Domain Events](#34-domain-events)
35. [Reporting Requirements](#35-reporting-requirements)
36. [KPI Requirements](#36-kpi-requirements)
37. [Search Requirements](#37-search-requirements)
38. [Import and Export](#38-import-and-export)
39. [Notifications](#39-notifications)
40. [Audit Requirements](#40-audit-requirements)
41. [Security Requirements](#41-security-requirements)
42. [Compliance Requirements](#42-compliance-requirements)
43. [Data Retention](#43-data-retention)
44. [Disaster Recovery](#44-disaster-recovery)
45. [Performance Targets](#45-performance-targets)
46. [Scalability Targets](#46-scalability-targets)
47. [Cross-Module Dependencies](#47-cross-module-dependencies)
48. [Cross-Module Contracts](#48-cross-module-contracts)
49. [Integration Readiness](#49-integration-readiness)
50. [AI Readiness](#50-ai-readiness)
51. [Analytics Readiness](#51-analytics-readiness)
52. [Extensibility Strategy](#52-extensibility-strategy)
53. [Versioning Strategy](#53-versioning-strategy)
54. [Risks](#54-risks)
55. [Assumptions](#55-assumptions)
56. [Constraints](#56-constraints)
57. [Success Metrics](#57-success-metrics)
58. [Glossary](#58-glossary)
59. [Acceptance Criteria](#59-acceptance-criteria)
60. [Epic Completion Criteria](#60-epic-completion-criteria)
61. [Future Roadmap](#61-future-roadmap)

---

## 1. Executive Summary

Sales Management is Epic 7 of the DevSphere ERP platform. It delivers the complete **Order-to-Cash (O2C) Domain** — the end-to-end capability that enables organisations to manage customer relationships, create quotations, process sales orders, fulfil deliveries, generate invoices, handle returns, and govern pricing under full audit accountability and multi-tenant isolation.

This is NOT a simple invoicing module. Sales Management encompasses the entire revenue-generating lifecycle from the moment a customer is onboarded through quotation, order placement, approval, inventory allocation, delivery, invoicing, and post-sale returns. It mirrors the commercial capabilities found in SAP S/4HANA Sales & Distribution, Oracle NetSuite Order Management, and Microsoft Dynamics 365 Sales.

The module integrates with Epic 5 (Inventory Management) for stock allocation and fulfilment, with Epic 6 (Purchase Management) for procurement-triggered reorder scenarios, and with Epic 4 (Users & Roles) for role-based access control across all sales operations.

**Key Deliverables:**

- Customer Master with full lifecycle management, credit control, and categorisation
- Sales Quotation engine with revision tracking, validity management, and order conversion
- Sales Order processing with configurable approval workflows and status lifecycle
- Order Fulfilment with inventory reservation, allocation, and delivery note generation
- Sales Invoicing with tax calculation readiness, discount application, and charge management
- Sales Return Management with RMA workflow, credit note readiness, and inventory restock
- Pricing Engine with price lists, customer-specific pricing, discount rules, and promotion readiness
- Sales Intelligence with 12+ KPI formulas, 15+ report types, and analytics-ready data model
- 38 domain events for cross-module integration and future event-driven architecture
- Full RBAC integration with 11 user roles and granular permission boundaries
- Complete multi-tenant isolation with zero cross-company data leakage

---

## 2. Epic Overview

| Attribute | Detail |
|-----------|--------|
| Epic Number | 007 |
| Epic Name | Sales Management |
| Domain | Order-to-Cash (O2C) |
| Module Path | `modules/sales` |
| Priority | P1 — Core Revenue Module |
| Estimated Complexity | Very High |
| Dependencies | Epic 1 (Foundation), Epic 2 (Auth), Epic 3 (Companies), Epic 4 (Users & Roles), Epic 5 (Inventory) |
| Optional Dependencies | Epic 6 (Purchase — for reorder triggers) |
| Compatibility | All Epics 0–6 |

---

## 3. Business Vision

Sales Management is the revenue engine of the ERP platform. Every business — regardless of industry — must sell goods or services to generate revenue. This module must:

1. **Serve as the single source of truth** for all customer-facing commercial transactions
2. **Support the complete Order-to-Cash cycle** from customer onboarding through cash collection readiness
3. **Provide enterprise-grade governance** with approval workflows, credit control, and audit trails
4. **Enable multi-industry deployment** without requiring code changes — only configuration
5. **Lay the foundation** for future modules including Accounts Receivable, Point of Sale, E-commerce, and Mobile Sales

### 3.1 Long-Term Vision

The Sales Management module must support the following industries through configuration alone:

- **Retail**: Walk-in customers, cash sales, barcode scanning
- **Wholesale**: Bulk pricing, volume discounts, credit terms
- **Construction**: Project-based orders, progressive billing readiness
- **Electrical/Medical**: Regulated items, lot/serial tracking via Epic 5 integration
- **Manufacturing**: Make-to-order readiness, BOM-linked sales
- **Distribution**: Multi-warehouse fulfilment, route-based delivery readiness
- **Trading**: Import/export readiness, multi-currency foundation
- **General Commerce**: Standard retail and service-based operations

---

## 4. Business Goals

| ID | Goal | Measurable Target |
|----|------|-------------------|
| BG-01 | Digitise the complete Order-to-Cash process | 100% of O2C steps — from quotation to return — managed within the system |
| BG-02 | Reduce order processing time | Users complete a sales order (with lines and approval) in under 5 minutes |
| BG-03 | Enforce financial governance | Zero unapproved orders exceeding configurable approval thresholds |
| BG-04 | Maintain customer data integrity | Single customer record per company with full contact, address, and credit history |
| BG-05 | Enable revenue visibility | Real-time dashboards showing sales pipeline, revenue, and outstanding orders |
| BG-06 | Ensure regulatory readiness | Tax calculation hooks, invoice sequencing, and audit trail for compliance |
| BG-07 | Support multi-tenant isolation | Zero cross-company data leakage across all sales entities |
| BG-08 | Enable growth through integration | Event-driven architecture ready for POS, E-commerce, and mobile channels |

---

## 5. Business Scope

### 5.1 In Scope (Epic 7 — P1)

| Domain | Capabilities |
|--------|-------------|
| Customer Master | Customer onboarding, categorisation, grouping, contact management, address management (billing/shipping), payment terms, credit limits, status lifecycle, rating, tax information, bank details, custom fields, documents, internal notes |
| Sales Quotations | Quotation creation, line items, revision history, validity management, approval readiness, conversion to sales order, quotation expiry handling |
| Sales Orders | Order creation (from quotation or direct), line items with product/description, approval workflow, status lifecycle (Draft → Approved → Delivered → Invoiced → Closed), partial delivery tracking, cancellation with reason |
| Order Fulfilment | Inventory availability check (via Epic 5), stock reservation, allocation, delivery note generation, partial delivery, dispatch confirmation |
| Sales Invoicing | Invoice generation from delivery notes or orders, line-level detail, tax calculation readiness, discount application, additional charges (freight, handling), invoice status lifecycle, credit note generation readiness |
| Sales Returns | Return Merchandise Authorisation (RMA) workflow, return reason capture, inspection readiness, credit note linkage, inventory restock via Epic 5 |
| Pricing | Price list management, customer-specific pricing, quantity-based discounts, line-level and document-level discounts, promotion readiness |
| Reporting | Sales reports, customer reports, quotation conversion, order pipeline, delivery performance, revenue analysis, profitability readiness |
| Integration | Inventory allocation events, purchase reorder triggers, domain event publication |
| Governance | Approval matrices, credit hold enforcement, configurable policies, feature flags |

### 5.2 In Scope — Ready but Disabled (Feature Flags)

| Capability | Feature Flag | Status |
|------------|-------------|--------|
| Customer bulk import (CSV/Excel) | `sales.customer_bulk_import` | Ready, disabled by default |
| Sales order email to customer | `sales.so_email_customer` | Ready, disabled by default |
| Invoice PDF export | `sales.invoice_pdf_export` | Ready, disabled by default |
| Barcode scanning for order lines | `sales.so_barcode_scan` | Ready, disabled by default |
| Delivery note PDF export | `sales.dn_pdf_export` | Ready, disabled by default |
| Customer portal readiness | `sales.customer_portal` | Ready, disabled by default |

### 5.3 Out of Scope (Future Epics)

See [§6 Out of Scope](#6-out-of-scope).

---

## 6. Out of Scope

The following capabilities are explicitly excluded from Epic 7. They are acknowledged as future requirements and the data model, events, and extension points are designed to accommodate them without breaking changes.

| Capability | Reason | Future Epic |
|------------|--------|-------------|
| Accounts Receivable | Requires separate financial ledger architecture | Epic 8+ |
| Payment Collection & Receipts | Financial domain, not sales domain | Epic 8+ |
| Instalment Plans | Complex financial instrument, requires AR foundation | Epic 9+ |
| Point of Sale (POS) | Requires real-time terminal integration, offline mode | Epic 10+ |
| E-commerce Integration | Requires storefront, cart, checkout | Epic 11+ |
| Mobile Sales App | Requires mobile-first UI, offline sync | Future |
| Multi-Currency Transactions | Requires exchange rate service, currency conversion engine | Future |
| Multi-Branch / Multi-Warehouse Routing | Requires branch management module | Future |
| Customer Loyalty & Rewards | Marketing domain | Future |
| Commission Calculation | HR/Payroll domain | Future |
| Advanced Tax Engine (GST/VAT/Sales Tax) | Requires tax jurisdiction management | Future |
| E-Invoicing (ZATCA, Peppol, FatturaPA) | Regulatory domain, country-specific | Future |
| Customer Relationship Management (CRM) | Separate module — leads, opportunities, campaigns | Future |
| Dunning & Collection | AR domain | Future |
| Revenue Recognition | Accounting domain | Future |
| Subscription & Recurring Billing | Requires billing engine | Future |
| Dynamic / AI-Driven Pricing | Requires ML pipeline | Future |
| Warehouse Picking/Packing UI | Warehouse Management System (WMS) domain | Future |

---

## 7. Sales Terminology

| Term | Definition |
|------|-----------|
| **Customer** | A legal entity or individual who purchases goods or services from the company. Distinguished from a "contact" (person) or "address" (location). |
| **Customer Category** | A classification grouping (e.g., Retail, Wholesale, Government, Internal) that determines default pricing, terms, and policies. |
| **Customer Group** | A logical grouping for reporting and discount eligibility (e.g., VIP, Preferred, Standard). |
| **Sales Quotation (SQ)** | A formal offer to a customer specifying products, quantities, prices, and validity. Non-binding until converted to a Sales Order. |
| **Sales Order (SO)** | A binding commercial commitment to deliver goods or services to a customer at agreed prices and terms. The primary transactional document of the sales process. |
| **Order Line** | A single item entry on a Sales Order specifying product, quantity, unit price, discount, and extended amount. |
| **Delivery Note (DN)** | A document confirming the physical dispatch of goods to the customer. Links to SO lines and triggers inventory deduction. |
| **Sales Invoice (SI)** | A financial document requesting payment from the customer for delivered goods or services. May be generated from DN or SO. |
| **Sales Return (SR)** | A document authorising the return of goods from a customer, with reason, inspection status, and resolution (credit note, replacement, refund readiness). |
| **Return Merchandise Authorisation (RMA)** | A formal approval to accept returned goods. Governs the return workflow. |
| **Credit Note** | A document reducing the customer's outstanding balance. Issued against a sales return or invoice adjustment. |
| **Price List** | A named collection of item prices effective for a date range. Multiple price lists may coexist (e.g., Retail, Wholesale, Promotional). |
| **Approval Matrix** | A configurable rule set defining who may approve orders based on value thresholds, customer category, or other criteria. |
| **Credit Limit** | The maximum outstanding receivable balance allowed for a customer before new orders are placed on credit hold. |
| **Credit Hold** | A system-enforced block preventing order approval when the customer's outstanding balance plus pending orders exceeds their credit limit. |
| **Fulfilment** | The process of reserving inventory, picking, packing, and dispatching goods against a sales order. |
| **Backorder** | An order line that cannot be fulfilled from current stock and is placed on a waiting queue until inventory is replenished. |
| **Pro Forma Invoice** | A preliminary invoice sent before delivery, typically for advance payment or customs purposes. Future capability. |
| **Order-to-Cash (O2C)** | The end-to-end business process from receiving a customer order through to collecting payment. |
| **Gross Margin** | The difference between selling price and cost price, expressed as a percentage of selling price. |
| **Average Order Value (AOV)** | Total revenue divided by number of orders in a period. |

---

## 8. Domain Philosophy

The Sales Management domain follows the principle of **Separation of Commercial Concerns**. Each subdomain has a distinct responsibility, its own aggregate root, and publishes domain events that other subdomains may consume.

### 8.1 Subdomain Responsibilities

| Subdomain | Responsibility | Aggregate Root |
|-----------|---------------|----------------|
| Customer Master | Customer identity, classification, credit, contacts, addresses | Customer |
| Sales Quotations | Commercial offers, revisions, validity, conversion | SalesQuotation |
| Sales Orders | Binding commitments, approval, status lifecycle | SalesOrder |
| Order Fulfilment | Inventory reservation, allocation, delivery notes | DeliveryNote |
| Sales Invoicing | Financial documents, tax hooks, charges | SalesInvoice |
| Sales Returns | RMA workflow, credit note readiness, restock | SalesReturn |
| Pricing | Price lists, customer pricing, discounts, promotions | PriceList |
| Sales Intelligence | KPIs, reports, analytics data | (Read Model) |
| Customer Intelligence | Customer analytics, segmentation, lifetime value | (Read Model) |

### 8.2 Design Principles

1. **Customer-Centric**: The customer is the anchor entity. All transactional documents reference a customer.
2. **Document-Driven**: Every commercial interaction produces a numbered, auditable document (SQ, SO, DN, SI, SR).
3. **Status-Governed**: All documents follow explicit status machines with defined transitions and guards.
4. **Price-at-Point-of-Sale**: Prices are captured on the document at creation time. Subsequent price list changes do not retroactively affect existing documents.
5. **Inventory-Aware**: Sales Orders consume inventory through reservations; Delivery Notes confirm physical dispatch; Returns restock inventory.
6. **Credit-Controlled**: Configurable credit limits prevent order approval when financial exposure exceeds thresholds.
7. **Event-Sourced Ready**: Every state transition publishes a domain event. The system can replay events for audit, analytics, or integration.

---

## 9. Domain Boundaries

### 9.1 What Sales Management Owns

- Customer master data (within company scope)
- Sales quotations, orders, delivery notes, invoices, and returns
- Pricing rules, price lists, and discount configuration
- Sales-specific approval workflows
- Sales reporting and KPI calculation
- Sales-specific feature flags and configuration

### 9.2 What Sales Management Does NOT Own

| Concern | Owner |
|---------|-------|
| User identity and authentication | Epic 2 (Authentication) |
| Company setup and configuration | Epic 3 (Companies) |
| Role definitions and permissions | Epic 4 (Users & Roles) |
| Product catalogue and stock levels | Epic 5 (Inventory Management) |
| Supplier and procurement data | Epic 6 (Purchase Management) |
| General ledger and financial accounts | Future Accounting Epic |
| Payment collection and bank reconciliation | Future AR/Payments Epic |

### 9.3 Shared Kernel

Sales Management shares the following kernel components with other modules:

- **TenantBaseModel**: Base entity with `company_id`, `created_by`, `updated_by`, `is_deleted`, audit timestamps
- **SequenceService**: Document number generation (SQ-YYYYMMDD-NNNN, SO-YYYYMMDD-NNNN, etc.)
- **FeatureFlagService**: Runtime feature toggle evaluation
- **InProcessEventBus**: Domain event publication and subscription
- **ApprovalService**: Configurable approval matrix evaluation (shared pattern with Epic 6)

---

## 10. Bounded Context

```
+---------------------------------------------------------------------------+
|                     Sales Management Bounded Context                      |
|                                                                           |
|  +----------------+  +----------------+  +----------------+               |
|  |   Customer     |  |    Sales       |  |    Sales       |               |
|  |    Master      |  |  Quotation     |  |    Order       |               |
|  |                |  |                |  |                |               |
|  |  Customer      |  |  Quotation     |  |  Order         |               |
|  |  Category      |  |  Line          |  |  Line          |               |
|  |  Group         |  |  Revision      |  |  Approval      |               |
|  |  Contact       |  |                |  |                |               |
|  |  Address       |  |                |  |                |               |
|  |  PaymentTerm   |  |                |  |                |               |
|  +-------+--------+  +-------+--------+  +-------+--------+              |
|          |                    |                    |                       |
|          |     +--------------+--------------------+                      |
|          |     |                                                          |
|  +-------+-----+----+  +----------------+  +----------------+            |
|  |   Delivery       |  |    Sales       |  |    Sales       |            |
|  |    Note           |  |   Invoice     |  |   Return       |            |
|  |                   |  |               |  |                |            |
|  |  DN Line          |  |  Invoice      |  |  Return        |            |
|  |                   |  |  Line         |  |  Line          |            |
|  |                   |  |  Charge       |  |                |            |
|  +-------------------+  +---------------+  +----------------+            |
|                                                                           |
|  +----------------+  +----------------+                                   |
|  |   Pricing      |  |    Sales       |                                   |
|  |   Engine       |  | Intelligence   |                                   |
|  |                |  |                |                                   |
|  |  PriceList     |  |  KPIs          |                                   |
|  |  PriceEntry    |  |  Reports       |                                   |
|  |  DiscountRule  |  |  Dashboards    |                                   |
|  +----------------+  +----------------+                                   |
|                                                                           |
|  ==================  Integration Layer  ==================                |
|  Epic 5: Inventory (stock check, reserve, deduct, restock)                |
|  Epic 6: Purchase (reorder triggers on low stock)                         |
|  Epic 4: RBAC (permission checks on every operation)                      |
|  Epic 2: Auth (JWT token validation)                                      |
+---------------------------------------------------------------------------+
```

---

## 11. Stakeholders

| Stakeholder | Interest |
|-------------|----------|
| Company Owners | Revenue visibility, customer management, financial governance |
| Sales Managers | Team performance, pipeline management, approval authority |
| Sales Executives / Representatives | Day-to-day order processing, quotation management, customer interaction |
| Warehouse / Store Keepers | Fulfilment instructions, delivery note processing, stock updates |
| Finance Managers | Invoice accuracy, credit control, revenue reporting |
| Auditors | Complete audit trail of all commercial transactions and approvals |
| System Administrators | Configuration, feature flags, user permissions |
| Customers (indirect) | Accurate quotations, timely deliveries, correct invoices |

---

## 12. User Personas

### 12.1 Super Admin

Full system access across all companies. Manages platform-wide sales configuration, feature flags, and can impersonate any role for troubleshooting. Does not typically process day-to-day sales transactions.

### 12.2 Company Owner

Full access to all sales operations within their company. Reviews sales performance dashboards, approves high-value orders, manages customer credit limits, and configures sales policies. Primary consumer of revenue and profitability reports.

### 12.3 Sales Manager

Manages a sales team. Creates and approves quotations, reviews and approves sales orders above their threshold, manages customer relationships, monitors team performance, and configures approval matrices. Has visibility into all sales operations within their scope.

### 12.4 Sales Executive

Senior individual contributor. Creates quotations, converts quotations to orders, manages key customer accounts, processes returns, and generates reports. May have approval authority for orders below a configurable threshold.

### 12.5 Sales Representative

Front-line sales operator. Creates quotations and sales orders, looks up customer information, checks product availability, and processes standard transactions. Cannot approve orders above their limit or modify pricing below minimum margins.

### 12.6 Cashier

Processes cash sales and walk-in transactions (future POS readiness). Creates direct sales orders for immediate fulfilment. Limited to cash/immediate payment terms. Cannot extend credit or modify payment terms.

### 12.7 Warehouse Manager

Processes delivery notes, confirms dispatch, manages inventory allocations. Views sales orders for fulfilment planning. Cannot modify order pricing or approve orders. Responsible for delivery note accuracy.

### 12.8 Finance Manager

Manages sales invoicing, monitors customer credit, reviews outstanding balances, and generates financial sales reports. Can place or release credit holds. Approves credit limit changes. Does not typically create sales orders.

### 12.9 Approver

Designated approval authority based on the approval matrix. Reviews and approves/rejects sales orders, quotations, credit limit changes, and returns based on configured thresholds. May be any role with approval delegation.

### 12.10 Auditor

Read-only access to all sales data, audit logs, document history, and approval trails. Cannot create, modify, or delete any sales records. Generates compliance and audit reports.

### 12.11 Read Only User

View-only access to sales data within their permission scope. Cannot create, modify, or approve any transactions. Useful for external consultants, temporary staff, or reporting-only users.

---

## 13. Business Capabilities

### 13.1 Capability Map

| # | Capability | Subdomain | Priority |
|---|-----------|-----------|----------|
| CAP-01 | Customer Onboarding & Lifecycle Management | Customer Master | P1 |
| CAP-02 | Customer Classification & Grouping | Customer Master | P1 |
| CAP-03 | Customer Credit Control | Customer Master | P1 |
| CAP-04 | Contact & Address Management | Customer Master | P1 |
| CAP-05 | Sales Quotation Management | Sales Quotations | P1 |
| CAP-06 | Quotation-to-Order Conversion | Sales Quotations | P1 |
| CAP-07 | Sales Order Processing | Sales Orders | P1 |
| CAP-08 | Sales Order Approval Workflow | Sales Orders | P1 |
| CAP-09 | Inventory Reservation & Allocation | Order Fulfilment | P1 |
| CAP-10 | Delivery Note Generation & Dispatch | Order Fulfilment | P1 |
| CAP-11 | Sales Invoice Generation | Sales Invoicing | P1 |
| CAP-12 | Tax Calculation Readiness | Sales Invoicing | P1 |
| CAP-13 | Discount & Charge Management | Sales Invoicing | P1 |
| CAP-14 | Sales Return / RMA Processing | Sales Returns | P1 |
| CAP-15 | Credit Note Readiness | Sales Returns | P1 |
| CAP-16 | Price List Management | Pricing Engine | P1 |
| CAP-17 | Customer-Specific Pricing | Pricing Engine | P1 |
| CAP-18 | Discount Rules & Promotions | Pricing Engine | P1 |
| CAP-19 | Sales KPI Dashboard | Sales Intelligence | P1 |
| CAP-20 | Sales Reporting & Analytics | Sales Intelligence | P1 |
| CAP-21 | Customer Analytics | Customer Intelligence | P1 |
| CAP-22 | Document Sequencing & Numbering | Cross-Cutting | P1 |
| CAP-23 | Sales Audit Trail | Cross-Cutting | P1 |
| CAP-24 | Sales Feature Flags | Cross-Cutting | P1 |

---

## 14. Customer Master

### 14.1 Customer Entity

The Customer is the central entity of the Sales domain. Each customer record represents a unique legal entity or individual within a single company's tenant scope.

**Core Attributes:**

- **Legal Name**: Official registered name of the customer (required)
- **Trading Name**: Business name used in day-to-day operations (optional)
- **Customer Code**: Unique alphanumeric identifier within the company (system-generated or user-defined, immutable after creation)
- **Customer Type**: INDIVIDUAL | COMPANY | GOVERNMENT | INTERNAL (required)
- **Customer Category**: Reference to a customer category for classification
- **Customer Group**: Reference to a customer group for reporting and discount eligibility
- **Status**: DRAFT | ACTIVE | ON_HOLD | BLOCKED | INACTIVE (status machine governed)
- **Currency Code**: Default transaction currency (ISO 4217, e.g., USD, EUR, PKR)
- **Tax Registration Number**: Tax identification (format varies by jurisdiction)
- **Tax Exempt**: Boolean flag indicating tax-exempt status
- **Website**: Customer's website URL (optional)
- **Industry**: Industry classification (optional, free-text or configurable list)
- **Annual Revenue Range**: Indicative revenue bracket for segmentation (optional)
- **Notes**: Internal notes visible only to company staff

### 14.2 Customer Categories

Categories provide a top-level classification that determines default business behaviour.

**Standard Categories (configurable per company):**

| Category | Description | Default Payment Terms | Default Credit Limit |
|----------|-------------|----------------------|---------------------|
| RETAIL | Individual end-consumers | Immediate | 0 (no credit) |
| WHOLESALE | Bulk buyers and resellers | Net 30 | Company-defined |
| GOVERNMENT | Government entities and agencies | Net 60 | Company-defined |
| CORPORATE | Corporate accounts | Net 30 | Company-defined |
| INTERNAL | Inter-company or internal departments | Net 0 | Unlimited |

- Categories are company-scoped and configurable
- Each category defines default payment terms, credit limit, and pricing tier
- A customer must belong to exactly one category
- Category changes trigger re-evaluation of applicable pricing and terms

### 14.3 Customer Groups

Groups provide a secondary classification for reporting, discount eligibility, and analytics.

- Groups are company-scoped and user-definable (e.g., VIP, Preferred, Standard, New)
- A customer may belong to zero or one group
- Groups can be linked to discount rules in the pricing engine
- Group membership affects reporting segmentation and dashboard filtering

### 14.4 Contacts

Each customer may have multiple contact persons:

- **Contact Name**: Full name of the contact person (required)
- **Title/Designation**: Job title or role (optional)
- **Email**: Email address (validated format)
- **Phone**: Primary phone number (optional)
- **Mobile**: Mobile number (optional)
- **Is Primary**: Boolean — exactly one contact must be marked as primary
- **Is Billing Contact**: Boolean — receives invoices and financial correspondence
- **Is Shipping Contact**: Boolean — receives delivery notifications
- **Department**: Department within the customer organisation (optional)
- **Notes**: Internal notes about this contact (optional)

**Rules:**
- At least one contact is required before a customer can be activated
- Exactly one contact must be marked as primary at all times
- Contacts are soft-deleted, not hard-deleted

### 14.5 Addresses

Each customer may have multiple addresses with type designation:

- **Address Type**: BILLING | SHIPPING | BOTH (required)
- **Address Label**: User-friendly name (e.g., "Head Office", "Warehouse 2")
- **Address Line 1**: Street address (required)
- **Address Line 2**: Additional address detail (optional)
- **City**: City name (required)
- **State/Province**: State or province (optional)
- **Postal Code**: ZIP or postal code (optional)
- **Country Code**: ISO 3166-1 alpha-2 country code (required)
- **Is Default Billing**: Boolean — default address for invoices
- **Is Default Shipping**: Boolean — default address for deliveries

**Rules:**
- At least one billing address is required before a customer can be activated
- At least one shipping address is required before delivery notes can be issued
- Exactly one address must be marked as default billing; exactly one as default shipping
- Addresses are soft-deleted, not hard-deleted

### 14.6 Payment Terms

Payment terms define when payment is expected:

- **Payment Term Code**: Unique identifier (e.g., NET30, NET60, IMMEDIATE, COD)
- **Description**: Human-readable description (e.g., "Net 30 Days")
- **Due Days**: Number of days from invoice date until payment is due
- **Discount Percentage**: Early payment discount percentage (optional)
- **Discount Days**: Number of days within which early payment discount applies (optional)
- **Is Active**: Boolean

Payment terms are company-scoped master data, reusable across customers. Each customer references a default payment term; individual orders may override.

### 14.7 Credit Management

**Credit Limit:**
- Each customer has a configurable credit limit (monetary value in company base currency)
- Default credit limit is determined by customer category
- Credit limit changes require Finance Manager or Company Owner approval
- Credit limit of zero means no credit is extended (cash/advance only)

**Credit Status:**
- **GOOD**: Outstanding balance + pending orders below credit limit
- **WARNING**: Outstanding balance + pending orders at 80–100% of credit limit
- **EXCEEDED**: Outstanding balance + pending orders exceeds credit limit — new order approval blocked
- **HOLD**: Manually placed credit hold by Finance Manager — all new orders blocked regardless of limit

**Credit Hold Behaviour:**
- When a customer is on credit hold, new sales orders cannot transition from DRAFT to PENDING_APPROVAL
- Existing approved orders are not retroactively cancelled
- Credit hold can be released by Finance Manager or Company Owner
- Credit check is evaluated at order approval time, not at order creation time

### 14.8 Customer Rating

A qualitative assessment of the customer relationship:

- **Rating Values**: A (Excellent) | B (Good) | C (Average) | D (Below Average) | F (Poor)
- Rating is manually assigned by Sales Manager or auto-calculated based on configurable criteria (future)
- Rating does not enforce business rules but is visible on reports and dashboards
- Rating history is maintained for trend analysis

### 14.9 Tax Information

- Tax Registration Number (TRN / GSTIN / VAT ID — format varies by jurisdiction)
- Tax Exempt flag (boolean)
- Tax Exempt Certificate Number (optional, when tax exempt is true)
- Tax Exempt Expiry Date (optional)
- Tax Category (future — for jurisdiction-specific tax rules)

### 14.10 Bank Details

- Bank Name
- Branch Name
- Account Number
- IBAN (optional)
- SWIFT/BIC Code (optional)
- Account Holder Name
- Is Default: Boolean

Bank details are used for future payment processing and refund operations. Multiple bank accounts per customer are supported.

### 14.11 Custom Fields

The customer entity supports a flexible custom fields mechanism:

- Company-scoped custom field definitions (field name, type, required flag)
- Field types: TEXT, NUMBER, DATE, BOOLEAN, SELECT (with options)
- Custom fields are stored as structured JSON within the customer record
- Custom fields are searchable and filterable
- Maximum of 20 custom fields per company

### 14.12 Documents

File attachments associated with the customer record:

- Trade license, tax certificate, contracts, correspondence
- Document metadata: name, type, uploaded_by, uploaded_at, file_size
- Documents are soft-deleted, not hard-deleted
- File storage uses the platform's file storage service (Epic 1)

### 14.13 Internal Notes

- Free-text notes attached to the customer record
- Each note records: author, timestamp, content
- Notes are append-only (cannot be edited after creation, can be soft-deleted)
- Visible to all users with customer read permission within the company

---

## 15. Sales Quotations

### 15.1 Quotation Lifecycle

```
                +----------+
                |  DRAFT   |
                +----+-----+
                     | submit
                     v
            +----------------+
            |SENT_TO_CUSTOMER|
            +--------+-------+
                     |
              +------+------+
              |             |
              v             v
     +----------+    +----------+
     | ACCEPTED |    | REJECTED |
     +-----+----+    +----------+
           | convert
           v
    +-----------+
    | CONVERTED | --> Sales Order created
    +-----------+

    (Any non-terminal state) --> EXPIRED (when validity_date passes)
    (Any non-terminal state) --> CANCELLED (manual cancellation)
```

**Status Definitions:**

| Status | Description | Allowed Transitions |
|--------|-------------|-------------------|
| DRAFT | Quotation being prepared, not yet sent | SENT_TO_CUSTOMER, CANCELLED |
| SENT_TO_CUSTOMER | Quotation sent/shared with customer | ACCEPTED, REJECTED, EXPIRED, CANCELLED |
| ACCEPTED | Customer has accepted the quotation | CONVERTED, CANCELLED |
| REJECTED | Customer has rejected the quotation | (terminal) |
| CONVERTED | Quotation converted to a Sales Order | (terminal) |
| EXPIRED | Validity date has passed without acceptance | (terminal) |
| CANCELLED | Quotation cancelled before conversion | (terminal) |

### 15.2 Quotation Structure

**Header:**
- Quotation Number (auto-generated: SQ-YYYYMMDD-NNNN)
- Customer reference
- Quotation Date
- Validity Date (expiry)
- Currency Code
- Payment Terms
- Shipping Address
- Billing Address
- Sales Representative
- Revision Number (starts at 1, increments on each revision)
- Internal Notes
- Customer-Facing Notes

**Lines:**
- Line Number (sequential within quotation)
- Product reference (from Epic 5 Inventory) or free-text description
- Quantity
- Unit of Measure
- Unit Price (from price list or manual entry)
- Discount Percentage (line-level)
- Discount Amount (line-level, mutually exclusive with percentage)
- Tax Category (for future tax calculation)
- Extended Amount (calculated: quantity x unit price - discount)
- Notes

**Totals:**
- Subtotal (sum of line extended amounts)
- Document-Level Discount (percentage or amount)
- Tax Amount (future — placeholder at zero)
- Additional Charges (future)
- Grand Total

### 15.3 Revision History

- Each modification to a DRAFT quotation increments the revision number
- Previous revisions are retained as snapshots (read-only)
- Only the latest revision is active and editable
- Revision history includes: revision number, modified_by, modified_at, change summary
- Customers always see only the latest revision

### 15.4 Validity Management

- Validity date is required and must be on or after the quotation date
- Default validity period is configurable per company (e.g., 30 days)
- System publishes a `sales.quotation.expiring_soon` event when validity is within configurable threshold (e.g., 3 days)
- Expired quotations transition to EXPIRED status automatically (via scheduled job or on-access check)

### 15.5 Conversion to Sales Order

- Only ACCEPTED quotations can be converted to a Sales Order
- Conversion creates a new Sales Order with all lines, prices, and terms copied
- The Sales Order references the originating quotation (traceability)
- The quotation transitions to CONVERTED status
- A single quotation can produce exactly one Sales Order (1:1 relationship)
- If the customer requests changes after conversion, a new quotation revision or a new quotation must be created

---

## 16. Sales Orders

### 16.1 Sales Order Lifecycle

```
         +----------+
         |  DRAFT   |
         +----+-----+
              | submit
              v
     +-----------------+        +----------+
     |PENDING_APPROVAL |------->| REJECTED |
     +--------+--------+ reject +----------+
              | approve
              v
         +----------+
         | APPROVED |
         +----+-----+
              | begin fulfilment
              v
    +---------------------+
    |PARTIALLY_DELIVERED  |
    +----------+----------+
              | all lines delivered
              v
        +-----------+
        | DELIVERED |
        +-----+-----+
              | invoice generated
              v
        +-----------+
        | INVOICED  |
        +-----+-----+
              | close
              v
         +----------+
         |  CLOSED  |
         +----------+

    (DRAFT, PENDING_APPROVAL, APPROVED) --> CANCELLED (with reason)
```

**Status Definitions:**

| Status | Description | Allowed Transitions |
|--------|-------------|-------------------|
| DRAFT | Order being created, can be modified freely | PENDING_APPROVAL, CANCELLED |
| PENDING_APPROVAL | Submitted for approval, immutable | APPROVED, REJECTED |
| APPROVED | Approved, ready for fulfilment | PARTIALLY_DELIVERED, DELIVERED, CANCELLED |
| REJECTED | Approval rejected, can be revised | DRAFT (for revision) |
| PARTIALLY_DELIVERED | Some lines delivered, some pending | DELIVERED |
| DELIVERED | All lines fully delivered | INVOICED |
| INVOICED | Invoice generated for this order | CLOSED |
| CLOSED | Order completed, no further action | (terminal) |
| CANCELLED | Order cancelled with documented reason | (terminal) |

### 16.2 Sales Order Structure

**Header:**
- Order Number (auto-generated: SO-YYYYMMDD-NNNN)
- Customer reference
- Quotation reference (optional — null for direct orders)
- Order Date
- Required Delivery Date
- Currency Code
- Payment Terms (defaulted from customer, overridable)
- Shipping Address (defaulted from customer default, overridable)
- Billing Address (defaulted from customer default, overridable)
- Sales Representative
- Priority (LOW | NORMAL | HIGH | URGENT)
- Internal Notes
- Customer-Facing Notes (printed on order confirmation)
- Cancellation Reason (required when status = CANCELLED)

**Lines:**
- Line Number (sequential)
- Product reference (from Epic 5 Inventory) or free-text description
- Quantity Ordered
- Quantity Delivered (updated as delivery notes are created)
- Quantity Remaining (calculated: ordered - delivered)
- Unit of Measure
- Unit Price
- Discount Percentage
- Discount Amount
- Tax Category
- Extended Amount
- Delivery Status per line (PENDING | PARTIALLY_DELIVERED | DELIVERED)
- Notes

**Totals:**
- Subtotal
- Document-Level Discount
- Tax Amount (future)
- Freight / Handling Charges
- Grand Total

### 16.3 Approval Workflow

The sales order approval workflow mirrors the pattern established in Epic 6 (Purchase Management):

**Approval Matrix Configuration:**
- Company-scoped approval rules
- Configurable thresholds based on order total value
- Multiple approval levels (e.g., Manager for orders > $5,000; Director for orders > $50,000)
- Approval by customer category (e.g., Government orders always require Manager approval)
- Auto-approval below configurable threshold (e.g., orders < $1,000 auto-approve)

**Approval Rules:**
- Orders in DRAFT status can be freely modified
- Submitting an order transitions it to PENDING_APPROVAL and makes it immutable
- Approvers are determined by the approval matrix at submission time
- Approval/rejection records include: approver, timestamp, decision, comments
- Rejected orders return to DRAFT for revision (a new submission increments version)
- Approval history is maintained for audit trail

**Credit Check at Approval:**
- When an approver approves an order, the system evaluates the customer's credit status
- If the customer's outstanding balance + all pending orders + this order exceeds the credit limit, the approval is blocked
- The approver is notified of the credit hold reason
- Finance Manager can override the credit check via credit hold release

### 16.4 Direct Orders (Skip Quotation)

- Sales orders can be created directly without a preceding quotation
- Direct orders follow the same approval workflow
- A configurable policy flag (`sales.require_quotation_before_order`) can enforce that all orders must originate from a quotation
- When this flag is enabled, direct order creation is blocked

---

## 17. Order Fulfillment

### 17.1 Fulfilment Process

Order fulfilment is the physical process of delivering goods against an approved sales order. It bridges the Sales domain (commercial commitment) with the Inventory domain (physical stock).

```
APPROVED Sales Order
        |
        v
   Inventory Check ---- Insufficient? --> Backorder / Notify
        |
        | Sufficient
        v
   Reserve Stock (Epic 5: StockMovement SALES_RESERVATION)
        |
        v
   Create Delivery Note (DRAFT)
        |
        v
   Confirm Dispatch (DN --> DISPATCHED)
        |
        v
   Update SO line quantities delivered
        |
        v
   Deduct Stock (Epic 5: StockMovement SALES_DISPATCH)
        |
        v
   SO transitions to PARTIALLY_DELIVERED or DELIVERED
```

### 17.2 Inventory Availability Check

Before creating a delivery note, the system checks available stock via Epic 5 Inventory:

- **Available Quantity** = On-Hand - Reserved - Committed
- If available quantity >= order line quantity: proceed to reservation
- If available quantity < order line quantity and partial delivery is allowed: reserve what is available, place remainder on backorder
- If available quantity = 0: notify sales representative, place on backorder queue
- Availability check considers the specific warehouse (if multi-warehouse is enabled via feature flag)

### 17.3 Stock Reservation

- Upon delivery note creation, stock is reserved via Epic 5 `StockMovement` with type `SALES_RESERVATION`
- Reservation reduces available stock but does not reduce on-hand quantity
- Reservations have an expiry period (configurable, e.g., 48 hours) after which they auto-release
- Reservation can be manually released by cancelling the delivery note

### 17.4 Delivery Note

**Delivery Note Lifecycle:**

```
   +----------+
   |  DRAFT   |
   +----+-----+
        | confirm dispatch
        v
  +------------+
  | DISPATCHED |
  +-----+------+
        | customer confirms receipt (future)
        v
  +------------+
  | DELIVERED  | (confirmation optional — auto after configurable period)
  +------------+

  (DRAFT) --> CANCELLED
```

**Delivery Note Structure:**
- DN Number (auto-generated: DN-YYYYMMDD-NNNN)
- Sales Order reference
- Customer reference
- Shipping Address
- Dispatch Date
- Expected Delivery Date (optional)
- Carrier / Transporter (optional)
- Tracking Number (optional)
- Lines: SO Line reference, product, quantity dispatched, quantity rejected (inspection), notes
- Total Packages / Weight (optional)
- Dispatch Confirmed By

### 17.5 Partial Delivery

- The system supports delivering part of an order across multiple delivery notes
- Each delivery note references specific SO lines and quantities
- The SO line tracks cumulative quantity delivered
- When sum of all DN quantities = SO ordered quantity for all lines, SO transitions to DELIVERED
- Partial deliveries cannot exceed the ordered quantity per line

### 17.6 Backorder Management

- When stock is insufficient for full fulfilment, remaining quantities are placed on a backorder queue
- Backorder queue is visible to sales representatives and warehouse managers
- When new stock arrives (Epic 5 inventory receipt), the system can notify users of fulfilable backorders
- Backorder auto-fulfilment is a future capability (disabled by default)

---

## 18. Sales Invoicing

### 18.1 Invoice Lifecycle

```
   +----------+
   |  DRAFT   |
   +----+-----+
        | finalise
        v
   +----------+
   |  ISSUED  |
   +----+-----+
        | (future: payment received)
        v
   +----------+
   |   PAID   | (future — Accounts Receivable)
   +----------+

   (DRAFT) --> CANCELLED
   (ISSUED) --> CREDIT_NOTE_ISSUED (partial or full credit)
```

**Status Definitions:**

| Status | Description | Allowed Transitions |
|--------|-------------|-------------------|
| DRAFT | Invoice being prepared | ISSUED, CANCELLED |
| ISSUED | Invoice finalised and sent to customer | PAID (future), CREDIT_NOTE_ISSUED |
| PAID | Full payment received (future AR) | (terminal) |
| CANCELLED | Invoice voided before issuance | (terminal) |
| CREDIT_NOTE_ISSUED | Credit note generated against this invoice | (terminal or PAID with adjustment) |

### 18.2 Invoice Structure

**Header:**
- Invoice Number (auto-generated: SI-YYYYMMDD-NNNN, sequential, gap-free within company)
- Customer reference
- Sales Order reference (optional — for direct invoicing)
- Delivery Note reference (optional — for delivery-based invoicing)
- Invoice Date
- Due Date (calculated from payment terms)
- Currency Code
- Payment Terms
- Billing Address
- Internal Notes
- Customer-Facing Notes

**Lines:**
- Line Number
- Product reference or description
- Quantity
- Unit of Measure
- Unit Price
- Discount Percentage
- Discount Amount
- Tax Rate (percentage, for future tax calculation)
- Tax Amount (calculated, for future tax engine)
- Extended Amount (net of discount, before tax)

**Charges:**
- Charge Type (FREIGHT, HANDLING, INSURANCE, OTHER)
- Description
- Amount
- Tax Applicable (boolean)

**Totals:**
- Subtotal (sum of line amounts)
- Total Discount
- Subtotal After Discount
- Tax Amount (future)
- Total Charges
- Grand Total
- Amount in Words (generated from grand total)

### 18.3 Invoice Generation Modes

1. **From Delivery Note**: Invoice is created for delivered quantities. One DN may produce one invoice. Multiple DNs for the same SO may be consolidated into one invoice.
2. **From Sales Order**: Invoice is created directly from an approved SO (for services or advance billing). All ordered quantities are invoiced.
3. **Manual / Direct Invoice**: Invoice created without a preceding SO or DN (for ad-hoc billing, service charges). Requires specific permission.

### 18.4 Tax Calculation Readiness

Epic 7 provides the structural foundation for tax calculation without implementing a tax engine:

- Each invoice line has `tax_rate` and `tax_amount` fields (defaulting to 0)
- Tax categories and tax groups are modelled as master data entities
- The system provides hooks for a future tax engine to calculate taxes based on:
  - Seller jurisdiction
  - Buyer jurisdiction
  - Product tax category
  - Transaction type
  - Customer tax exemption status
- Tax amounts are stored at the line level and summed at the document level
- Tax-inclusive and tax-exclusive pricing modes are supported via company configuration

### 18.5 Discounts

**Line-Level Discounts:**
- Percentage or fixed amount (mutually exclusive per line)
- Applied before tax calculation
- Sourced from price list, customer-specific pricing, or manual entry

**Document-Level Discounts:**
- Percentage or fixed amount applied to the subtotal
- Distributed proportionally across lines for tax calculation purposes
- Requires specific permission to apply (configurable minimum margin guard)

**Discount Governance:**
- Maximum discount percentage configurable per user role
- Discounts below minimum margin trigger approval workflow
- Discount history maintained for audit trail

### 18.6 Invoice Sequencing

- Invoice numbers are strictly sequential within a company (gap-free)
- Cancelled invoices retain their number but are marked as void
- Invoice numbers cannot be reused
- Sequence format is configurable per company (prefix, separator, year inclusion)

---

## 19. Sales Returns

### 19.1 Return Workflow

```
   +----------+
   |  DRAFT   |
   +----+-----+
        | submit
        v
  +------------------+        +----------+
  |PENDING_APPROVAL  |------->| REJECTED |
  +--------+---------+ reject +----------+
           | approve
           v
      +----------+
      | APPROVED |
      +----+-----+
           | receive goods
           v
      +----------+
      | RECEIVED | (goods received from customer)
      +----+-----+
           | inspect (future)
           v
      +----------+
      | INSPECTED| (future — quality check)
      +----+-----+
           | resolve
           v
      +-----------+
      | COMPLETED |
      +-----------+

  (DRAFT, PENDING_APPROVAL) --> CANCELLED
```

### 19.2 Sales Return Structure

**Header:**
- Return Number (auto-generated: SR-YYYYMMDD-NNNN)
- Customer reference
- Original Sales Order reference (optional)
- Original Invoice reference (optional)
- Return Date
- Return Reason Code (required — from configurable list)
- Return Reason Description (free text)
- Resolution Type: CREDIT_NOTE | REPLACEMENT | REFUND_READINESS
- Status
- Received By (warehouse staff who received returned goods)
- Inspected By (future)
- Internal Notes

**Lines:**
- Product reference
- Quantity Returned
- Quantity Accepted (after inspection)
- Quantity Rejected (after inspection)
- Unit Price (from original document)
- Extended Amount
- Reason per line (optional — if different from header)
- Condition: NEW | USED | DAMAGED | DEFECTIVE

**Return Reason Codes (configurable per company):**

| Code | Description |
|------|-------------|
| DEFECTIVE | Product is defective or damaged |
| WRONG_ITEM | Wrong product was delivered |
| WRONG_QTY | Incorrect quantity delivered |
| NOT_AS_DESCRIBED | Product does not match description/specification |
| DUPLICATE_ORDER | Order was placed in error (duplicate) |
| CUSTOMER_CHANGED_MIND | Customer no longer wants the product |
| QUALITY_ISSUE | Product quality does not meet expectations |
| LATE_DELIVERY | Delivery was delayed beyond acceptable limit |
| OTHER | Other reason (description required) |

### 19.3 Return Resolution

**Credit Note:**
- When resolution type is CREDIT_NOTE, the system generates a credit note document
- Credit note reduces the customer's outstanding balance (future AR integration)
- Credit note references the original invoice and return

**Replacement:**
- When resolution type is REPLACEMENT, the system creates a new Sales Order for replacement items
- The replacement SO is linked to the return for traceability
- No additional charge to the customer (price = 0 with reference to return)

**Refund Readiness:**
- When resolution type is REFUND_READINESS, the system marks the return for future payment refund processing
- Actual refund processing is in the Accounts Receivable domain (future)
- A `sales.return.refund_ready` event is published

### 19.4 Inventory Restock

- When returned goods are received and accepted, inventory is restocked via Epic 5
- Stock movement type: `SALES_RETURN_INBOUND`
- Rejected items (damaged, defective) are moved to a quarantine location (if configured) or written off
- Stock movement type for rejected items: `SALES_RETURN_QUARANTINE` (future)

---

## 20. Pricing Engine

### 20.1 Price List Management

A Price List is a named collection of item prices with an effective date range.

**Price List Attributes:**
- Name (unique within company)
- Description
- Currency Code
- Effective From Date
- Effective To Date (optional — null = indefinite)
- Is Default (boolean — exactly one price list must be default)
- Is Active (boolean)
- Priority (integer — used for resolution when multiple lists apply)

**Price Entry Attributes:**
- Product reference (from Epic 5)
- Unit Price
- Minimum Quantity (for quantity-based pricing)
- Unit of Measure

**Rules:**
- Multiple price entries per product are allowed (quantity breaks)
- Exactly one price list must be marked as default per company
- Price lists are company-scoped
- Price entries are soft-deleted, not hard-deleted

### 20.2 Price Resolution Order

When determining the price for a product on a sales document, the system resolves prices in this priority:

1. **Manual Override**: User explicitly enters a price on the document line (highest priority)
2. **Customer-Specific Price**: Price defined for this specific customer and product
3. **Customer Group Price**: Price defined for the customer's group and product
4. **Customer Category Price**: Price defined for the customer's category and product
5. **Active Price List**: Price from the highest-priority active price list that contains the product and is within its effective date range
6. **Default Price List**: Price from the default price list
7. **Product Base Price**: The product's standard selling price from Epic 5 Inventory (lowest priority)

At each level, quantity breaks are evaluated: the price entry with the highest `minimum_quantity` <= ordered quantity is selected.

### 20.3 Customer-Specific Pricing

- Per-customer price overrides for specific products
- Effective date range (from/to)
- Links customer + product + price
- Takes priority over price list prices (but below manual override)

### 20.4 Discount Rules

**Rule Types:**
- **Percentage Discount**: X% off the line price
- **Fixed Amount Discount**: $X off the line price
- **Buy X Get Y**: Purchase X units, receive Y additional units free (future, feature flag)
- **Volume Discount**: Graduated discount based on total order quantity or value
- **Promotional Discount**: Time-limited discount with code or automatic application

**Discount Rule Structure:**
- Rule Name
- Rule Type
- Applicability: ALL_CUSTOMERS | SPECIFIC_CATEGORY | SPECIFIC_GROUP | SPECIFIC_CUSTOMER
- Product Scope: ALL_PRODUCTS | SPECIFIC_CATEGORY | SPECIFIC_PRODUCT
- Minimum Quantity (optional)
- Minimum Order Value (optional)
- Effective From / To dates
- Discount Value (percentage or amount)
- Is Active
- Priority (for conflict resolution — highest priority wins)
- Is Stackable (boolean — can this discount combine with others?)

**Rules:**
- Only one non-stackable discount applies per line (highest priority)
- Stackable discounts accumulate (future)
- Discount application is audited (which rule, who applied, original price, discounted price)

### 20.5 Minimum Margin Guard

- Configurable minimum gross margin percentage per company
- When a sales document line's margin falls below the minimum, the system:
  - Warns the user
  - Requires manager approval to proceed
  - Records the override in audit log
- Margin calculation: `(unit_price - cost_price) / unit_price x 100`
- Cost price is sourced from Epic 5 Inventory (latest purchase cost or weighted average cost)

---

## 21. Sales Lifecycle

The complete Order-to-Cash lifecycle within the Sales Management module:

```
+-----------------------------------------------------------------+
|                    ORDER-TO-CASH LIFECYCLE                       |
|                                                                 |
|  Customer     Sales        Sales       Delivery     Sales       |
|  Onboarding > Quotation > Order     > Note       > Invoice     |
|                                                                 |
|  [Customer]   [SQ-001]    [SO-001]   [DN-001]    [SI-001]      |
|  DRAFT        DRAFT       DRAFT      DRAFT       DRAFT         |
|    |            |           |          |           |            |
|  ACTIVE       SENT        PENDING    DISPATCHED  ISSUED        |
|                |          APPROVAL      |                       |
|              ACCEPTED       |        DELIVERED                  |
|                |          APPROVED                              |
|              CONVERTED      |                                   |
|                           PARTIALLY                             |
|                           DELIVERED                             |
|                              |                                  |
|                           DELIVERED                             |
|                              |                                  |
|                           INVOICED                              |
|                              |                                  |
|                            CLOSED                               |
|                                                                 |
|  ---------- Returns Channel ----------                          |
|  [SR-001]                                                       |
|  DRAFT > APPROVED > RECEIVED > COMPLETED                       |
|  Credit Note / Replacement / Refund Readiness                   |
+-----------------------------------------------------------------+
```

---

## 22. Customer Lifecycle

```
   +----------+
   |  DRAFT   |  (Customer created, data entry in progress)
   +----+-----+
        | complete required fields + activate
        v
   +----------+
   |  ACTIVE  |  (Eligible for transactions)
   +----+-----+
        |
   +----+---------------------+
   |                          |
   v                          v
+----------+            +----------+
| ON_HOLD  |            | BLOCKED  |  (Credit issues, disputes)
+----+-----+            +----+-----+
     | release                | unblock
     +--------+---------------+
              v
         +----------+
         |  ACTIVE  |
         +----+-----+
              | deactivate
              v
         +----------+
         | INACTIVE |  (No longer trading, can be reactivated)
         +----------+
```

**Transition Rules:**

| From | To | Guard |
|------|----|-------|
| DRAFT | ACTIVE | At least one contact, one billing address, payment terms set |
| ACTIVE | ON_HOLD | Manual action by Sales Manager or Finance Manager |
| ACTIVE | BLOCKED | Credit limit exceeded or manual action by Finance Manager |
| ON_HOLD | ACTIVE | Manual release by Sales Manager or Finance Manager |
| BLOCKED | ACTIVE | Credit issue resolved + manual unblock by Finance Manager |
| ACTIVE | INACTIVE | Manual deactivation; no open orders required |
| INACTIVE | ACTIVE | Manual reactivation by Sales Manager |

**Constraints:**
- DRAFT customers cannot be referenced on sales documents
- ON_HOLD customers: existing orders continue, new orders blocked
- BLOCKED customers: existing orders continue, new orders blocked, warning displayed
- INACTIVE customers: no new transactions allowed; historical data retained

---

## 23. Business Workflows

### Workflow 1: Standard Sales (Quotation to Order to Delivery to Invoice)

1. Sales Representative creates a Sales Quotation for a customer
2. Quotation is sent to the customer (status: SENT_TO_CUSTOMER)
3. Customer accepts the quotation (status: ACCEPTED)
4. Sales Representative converts the quotation to a Sales Order (SQ to CONVERTED, SO created in DRAFT)
5. Sales Representative submits the SO for approval (SO to PENDING_APPROVAL)
6. Sales Manager approves the SO (SO to APPROVED; credit check passes)
7. Warehouse Manager creates a Delivery Note against the SO (DN to DRAFT)
8. Stock is reserved (Epic 5: StockMovement SALES_RESERVATION)
9. Warehouse Manager confirms dispatch (DN to DISPATCHED; stock deducted)
10. SO transitions to DELIVERED (all lines fulfilled)
11. Finance Manager generates a Sales Invoice from the DN (SI to DRAFT)
12. Finance Manager finalises the invoice (SI to ISSUED)
13. SO transitions to INVOICED, then CLOSED

### Workflow 2: Direct Sales Order (No Quotation)

1. Sales Representative creates a Sales Order directly (DRAFT)
2. Adds lines, applies pricing from price list
3. Submits for approval, then Approved, Delivery, Invoice, Close
4. Same as steps 6–13 of Workflow 1

### Workflow 3: Cash Sale (Immediate Fulfilment)

1. Cashier creates a direct Sales Order with immediate payment terms
2. Order auto-approves (below auto-approval threshold)
3. Delivery Note created and dispatched immediately
4. Invoice generated and issued in the same session
5. Order closes

### Workflow 4: Sales Return

1. Customer requests return (contacts Sales Representative)
2. Sales Representative creates a Sales Return (SR to DRAFT)
3. Specifies original SO/Invoice, return reason, lines, quantities
4. Submits for approval (SR to PENDING_APPROVAL)
5. Sales Manager approves (SR to APPROVED)
6. Customer ships goods back; Warehouse Manager receives (SR to RECEIVED)
7. Resolution applied:
   - CREDIT_NOTE: Credit note generated, customer balance adjusted (future AR)
   - REPLACEMENT: New SO created for replacement items
   - REFUND_READINESS: Marked for refund processing (future)
8. Accepted items restocked (Epic 5: StockMovement SALES_RETURN_INBOUND)
9. SR to COMPLETED

### Workflow 5: Partial Delivery

1. Sales Order approved with 3 lines (100 units each)
2. DN-001 created: Line 1 = 100 units (fully delivered), Line 2 = 50 units (partial)
3. SO to PARTIALLY_DELIVERED
4. DN-002 created: Line 2 = 50 units (remaining), Line 3 = 100 units (full)
5. SO to DELIVERED (all lines fulfilled)
6. Invoice may be generated per DN or consolidated

### Workflow 6: Customer Onboarding

1. Sales Executive creates a Customer record (DRAFT)
2. Adds legal name, customer type, category
3. Adds at least one contact (primary)
4. Adds at least one billing address
5. Sets payment terms and credit limit
6. Activates the customer (DRAFT to ACTIVE)
7. Customer is now eligible for quotations and orders

---

## 24. Functional Requirements

### 24.1 Customer Management

- **FR-C01**: System MUST allow creation of customer records with legal name, customer code, customer type, and category
- **FR-C02**: System MUST enforce unique customer codes within each company
- **FR-C03**: System MUST support the customer status lifecycle: DRAFT to ACTIVE to ON_HOLD to BLOCKED to INACTIVE with defined transition guards
- **FR-C04**: System MUST require at least one primary contact and one billing address before customer activation
- **FR-C05**: System MUST support multiple contacts per customer with primary/billing/shipping designation
- **FR-C06**: System MUST support multiple addresses per customer with billing/shipping type
- **FR-C07**: System MUST enforce exactly one default billing address and one default shipping address per customer
- **FR-C08**: System MUST manage customer credit limits with category-based defaults
- **FR-C09**: System MUST calculate and maintain credit status (GOOD, WARNING, EXCEEDED, HOLD) based on configurable thresholds
- **FR-C10**: System MUST support customer groups for reporting and discount eligibility
- **FR-C11**: System MUST support up to 20 custom fields per company
- **FR-C12**: System MUST support document attachments on customer records
- **FR-C13**: System MUST support append-only internal notes on customer records
- **FR-C14**: System MUST support customer search by name, code, category, group, status, and custom fields
- **FR-C15**: System MUST support customer bulk import from CSV and Excel files (feature flag: `sales.customer_bulk_import`)
- **FR-C16**: System MUST support customer data export to CSV and Excel

### 24.2 Sales Quotations

- **FR-Q01**: System MUST allow creation of sales quotations with customer, lines, pricing, and validity date
- **FR-Q02**: System MUST auto-generate sequential quotation numbers (SQ-YYYYMMDD-NNNN)
- **FR-Q03**: System MUST support the quotation status lifecycle: DRAFT to SENT_TO_CUSTOMER to ACCEPTED/REJECTED to CONVERTED/EXPIRED/CANCELLED
- **FR-Q04**: System MUST track revision history with snapshot preservation
- **FR-Q05**: System MUST support validity date management with automatic expiry
- **FR-Q06**: System MUST allow conversion of ACCEPTED quotations to Sales Orders (1:1 conversion)
- **FR-Q07**: System MUST resolve pricing using the price resolution hierarchy (§20.2)
- **FR-Q08**: System MUST support line-level and document-level discounts on quotations
- **FR-Q09**: System MUST prevent modification of quotations in non-DRAFT status

### 24.3 Sales Orders

- **FR-O01**: System MUST allow creation of sales orders directly or from quotation conversion
- **FR-O02**: System MUST auto-generate sequential order numbers (SO-YYYYMMDD-NNNN)
- **FR-O03**: System MUST support the full sales order status lifecycle (§16.1)
- **FR-O04**: System MUST enforce approval workflow based on configurable approval matrix
- **FR-O05**: System MUST perform credit check at order approval time
- **FR-O06**: System MUST block approval when customer credit is exceeded or on hold
- **FR-O07**: System MUST support order cancellation with mandatory reason capture
- **FR-O08**: System MUST track per-line delivery status (quantity ordered, delivered, remaining)
- **FR-O09**: System MUST support order priority levels (LOW, NORMAL, HIGH, URGENT)
- **FR-O10**: System MUST enforce immutability of orders in PENDING_APPROVAL status
- **FR-O11**: System MUST support configurable policy to require quotation before order (`sales.require_quotation_before_order`)
- **FR-O12**: System MUST auto-approve orders below configurable threshold

### 24.4 Order Fulfilment

- **FR-F01**: System MUST check inventory availability via Epic 5 before delivery note creation
- **FR-F02**: System MUST reserve stock upon delivery note creation
- **FR-F03**: System MUST deduct stock upon delivery dispatch confirmation
- **FR-F04**: System MUST support partial delivery across multiple delivery notes
- **FR-F05**: System MUST prevent delivery quantities from exceeding ordered quantities
- **FR-F06**: System MUST auto-generate delivery note numbers (DN-YYYYMMDD-NNNN)
- **FR-F07**: System MUST track delivery note lifecycle (DRAFT to DISPATCHED to DELIVERED)
- **FR-F08**: System MUST update sales order line delivery status after each delivery note dispatch
- **FR-F09**: System MUST support backorder queue for unfulfillable lines

### 24.5 Sales Invoicing

- **FR-I01**: System MUST generate invoices from delivery notes or directly from sales orders
- **FR-I02**: System MUST auto-generate strictly sequential, gap-free invoice numbers (SI-YYYYMMDD-NNNN)
- **FR-I03**: System MUST support the invoice lifecycle (DRAFT to ISSUED to PAID [future])
- **FR-I04**: System MUST calculate due dates from payment terms
- **FR-I05**: System MUST support line-level and document-level discounts
- **FR-I06**: System MUST support additional charges (freight, handling, insurance)
- **FR-I07**: System MUST provide tax calculation hooks (tax_rate, tax_amount fields)
- **FR-I08**: System MUST support invoice cancellation (void) with number preservation
- **FR-I09**: System MUST prevent modification of ISSUED invoices
- **FR-I10**: System MUST support amount-in-words generation for invoice totals
- **FR-I11**: System MUST support invoice PDF export (feature flag: `sales.invoice_pdf_export`)
- **FR-I12**: System MUST support consolidating multiple delivery notes into one invoice

### 24.6 Sales Returns

- **FR-R01**: System MUST support sales return creation with mandatory return reason
- **FR-R02**: System MUST auto-generate return numbers (SR-YYYYMMDD-NNNN)
- **FR-R03**: System MUST enforce return approval workflow
- **FR-R04**: System MUST support resolution types: CREDIT_NOTE, REPLACEMENT, REFUND_READINESS
- **FR-R05**: System MUST restock accepted returned items via Epic 5
- **FR-R06**: System MUST generate credit notes for CREDIT_NOTE resolution type
- **FR-R07**: System MUST create replacement sales orders for REPLACEMENT resolution type
- **FR-R08**: System MUST track item condition on return lines (NEW, USED, DAMAGED, DEFECTIVE)

### 24.7 Pricing

- **FR-P01**: System MUST support multiple active price lists with effective date ranges
- **FR-P02**: System MUST resolve prices using the defined priority hierarchy (§20.2)
- **FR-P03**: System MUST support quantity-based pricing (price breaks)
- **FR-P04**: System MUST support customer-specific price overrides
- **FR-P05**: System MUST support customer group and category-based pricing
- **FR-P06**: System MUST support discount rules with applicability filters
- **FR-P07**: System MUST enforce minimum margin guards with configurable thresholds
- **FR-P08**: System MUST audit all price overrides and discount applications

---

## 25. Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-01 | Customer search response time | p95 < 300ms for 100,000 customers |
| NFR-02 | Sales order list response time | p95 < 500ms for 50,000 orders |
| NFR-03 | Invoice generation time | < 2 seconds per invoice |
| NFR-04 | Delivery note confirmation time | < 2 seconds (including stock update) |
| NFR-05 | Report generation time | p95 < 5 seconds for 100,000 transactions |
| NFR-06 | Concurrent users | 200 concurrent users per tenant without degradation |
| NFR-07 | Data integrity | Zero data loss during concurrent order processing |
| NFR-08 | Audit completeness | 100% of state transitions logged with actor and timestamp |
| NFR-09 | Tenant isolation | Zero cross-company data leakage verified by test suite |
| NFR-10 | Availability | 99.5% uptime for sales operations |
| NFR-11 | Bulk import throughput | 10,000 customer records imported within 60 seconds |
| NFR-12 | Export throughput | 50,000 records exported to CSV within 30 seconds |

---

## 26. Business Rules

### 26.1 Customer Rules

- **BR-C01**: Customer code must be unique within a company and immutable after creation
- **BR-C02**: Customer cannot be activated without at least one primary contact and one billing address
- **BR-C03**: Exactly one contact must be designated as primary at all times
- **BR-C04**: Exactly one address must be designated as default billing; exactly one as default shipping
- **BR-C05**: Customer credit limit changes require Finance Manager or Company Owner approval
- **BR-C06**: DRAFT or INACTIVE customers cannot be referenced on new sales documents
- **BR-C07**: ON_HOLD or BLOCKED customers: existing orders continue; new orders are blocked
- **BR-C08**: Customer cannot be deactivated while open (non-closed, non-cancelled) orders exist

### 26.2 Quotation Rules

- **BR-Q01**: Quotation validity date must be on or after the quotation date
- **BR-Q02**: Only ACCEPTED quotations can be converted to Sales Orders
- **BR-Q03**: One quotation produces exactly one Sales Order (1:1)
- **BR-Q04**: Quotations in non-DRAFT status are immutable
- **BR-Q05**: Expired quotations cannot be accepted or converted

### 26.3 Sales Order Rules

- **BR-O01**: Orders in PENDING_APPROVAL status are immutable
- **BR-O02**: Credit check is evaluated at approval time; exceeded credit blocks approval
- **BR-O03**: Order cancellation requires a documented reason
- **BR-O04**: Cancelled orders release any associated inventory reservations
- **BR-O05**: Orders can only transition to DELIVERED when all lines are fully delivered
- **BR-O06**: Rejected orders return to DRAFT for revision (approval history preserved)
- **BR-O07**: Auto-approval applies only when order total is below the configured threshold and customer credit is GOOD

### 26.4 Delivery Rules

- **BR-D01**: Delivery note can only be created for APPROVED or PARTIALLY_DELIVERED orders
- **BR-D02**: Delivery quantity per line cannot exceed remaining undelivered quantity
- **BR-D03**: Delivery dispatch confirmation deducts stock and is irreversible
- **BR-D04**: Delivery note cancellation (DRAFT only) releases reserved stock

### 26.5 Invoice Rules

- **BR-I01**: Invoice numbers are strictly sequential and gap-free per company
- **BR-I02**: Cancelled invoice numbers cannot be reused; the invoice is marked void
- **BR-I03**: ISSUED invoices cannot be modified; only credit notes can adjust them
- **BR-I04**: Invoice can only be generated for delivered or approved (services) orders
- **BR-I05**: Invoice due date is calculated from invoice date + payment terms due days

### 26.6 Return Rules

- **BR-R01**: Returns require a valid return reason code
- **BR-R02**: Return quantities cannot exceed the originally delivered quantities
- **BR-R03**: Replacement resolution creates a new SO with zero-value lines referencing the return
- **BR-R04**: Accepted return items are restocked; rejected items are quarantined or written off
- **BR-R05**: Returns require approval before goods can be received

### 26.7 Pricing Rules

- **BR-P01**: Exactly one price list must be marked as default per company
- **BR-P02**: Price at point-of-sale: prices are captured on the document at creation time; subsequent price list changes do not affect existing documents
- **BR-P03**: Manual price overrides are audited with original price, override price, and user
- **BR-P04**: Discounts below minimum margin percentage require manager approval
- **BR-P05**: Only one non-stackable discount applies per line (highest priority wins)

---

## 27. Business Invariants

These are conditions that must ALWAYS be true in the system:

- **INV-01**: Every sales document (SQ, SO, DN, SI, SR) must reference exactly one company_id
- **INV-02**: Every sales document must reference exactly one customer
- **INV-03**: Document numbers are unique within their type and company scope
- **INV-04**: Invoice numbers are strictly sequential and gap-free within a company
- **INV-05**: Total delivered quantity <= ordered quantity for every SO line
- **INV-06**: Total returned quantity <= total delivered quantity for every product/customer combination
- **INV-07**: Customer credit status accurately reflects outstanding balance + pending orders relative to credit limit
- **INV-08**: Every state transition is recorded in the audit log with actor, timestamp, and reason
- **INV-09**: Soft-deleted records are excluded from all list queries and business operations
- **INV-10**: No sales document references a customer belonging to a different company
- **INV-11**: Sum of delivery note line quantities for an SO line = SO line's delivered quantity
- **INV-12**: Every price on a document is captured at creation time and immutable thereafter

---

## 28. Validation Rules

### 28.1 Customer Validation

| Field | Rule |
|-------|------|
| legal_name | Required, 2-200 characters, trimmed |
| customer_code | Required, 2-30 characters, alphanumeric + hyphens, unique per company, immutable after creation |
| customer_type | Required, enum: INDIVIDUAL, COMPANY, GOVERNMENT, INTERNAL |
| currency_code | Required, ISO 4217 (3 uppercase letters) |
| email (contact) | Valid email format when provided |
| phone (contact) | Valid phone format when provided (E.164 recommended) |
| country_code (address) | ISO 3166-1 alpha-2 when provided |
| credit_limit | Non-negative decimal, max 15 digits with 2 decimal places |
| payment_terms_days | Non-negative integer, 0-365 |

### 28.2 Sales Document Validation

| Field | Rule |
|-------|------|
| quantity | Positive decimal, max 12 digits with 3 decimal places |
| unit_price | Non-negative decimal, max 15 digits with 4 decimal places |
| discount_percentage | 0-100 decimal with 2 decimal places |
| discount_amount | Non-negative, cannot exceed line extended amount |
| currency_code | ISO 4217, must match document header currency |
| required_delivery_date | Must be on or after order date |
| validity_date (quotation) | Must be on or after quotation date |
| cancellation_reason | Required when transitioning to CANCELLED status, min 3 characters |
| return_reason_code | Required on sales return, must be a valid configured code |
| tax_rate | 0-100 decimal with 4 decimal places |

---

## 29. Permission Matrix

Integrated with Epic 4 (Users & Roles) RBAC system. Permissions follow the pattern: `sales.<resource>.<action>`.

### 29.1 Customer Permissions

| Permission | Super Admin | Company Owner | Sales Manager | Sales Exec | Sales Rep | Cashier | Warehouse Mgr | Finance Mgr | Approver | Auditor | Read Only |
|------------|:-----------:|:-------------:|:-------------:|:----------:|:---------:|:-------:|:--------------:|:-----------:|:--------:|:-------:|:---------:|
| sales.customer.create | Y | Y | Y | Y | Y | N | N | N | N | N | N |
| sales.customer.read | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| sales.customer.update | Y | Y | Y | Y | N | N | N | N | N | N | N |
| sales.customer.activate | Y | Y | Y | N | N | N | N | N | N | N | N |
| sales.customer.deactivate | Y | Y | Y | N | N | N | N | N | N | N | N |
| sales.customer.block | Y | Y | N | N | N | N | N | Y | N | N | N |
| sales.customer.unblock | Y | Y | N | N | N | N | N | Y | N | N | N |
| sales.customer.credit_limit | Y | Y | N | N | N | N | N | Y | N | N | N |
| sales.customer.import | Y | Y | Y | N | N | N | N | N | N | N | N |
| sales.customer.export | Y | Y | Y | Y | Y | N | N | Y | N | Y | N |

### 29.2 Quotation Permissions

| Permission | Super Admin | Company Owner | Sales Manager | Sales Exec | Sales Rep | Cashier | Warehouse Mgr | Finance Mgr | Approver | Auditor | Read Only |
|------------|:-----------:|:-------------:|:-------------:|:----------:|:---------:|:-------:|:--------------:|:-----------:|:--------:|:-------:|:---------:|
| sales.quotation.create | Y | Y | Y | Y | Y | N | N | N | N | N | N |
| sales.quotation.read | Y | Y | Y | Y | Y | N | N | Y | Y | Y | Y |
| sales.quotation.update | Y | Y | Y | Y | Y | N | N | N | N | N | N |
| sales.quotation.send | Y | Y | Y | Y | Y | N | N | N | N | N | N |
| sales.quotation.accept | Y | Y | Y | Y | N | N | N | N | N | N | N |
| sales.quotation.reject | Y | Y | Y | Y | N | N | N | N | N | N | N |
| sales.quotation.convert | Y | Y | Y | Y | N | N | N | N | N | N | N |
| sales.quotation.cancel | Y | Y | Y | N | N | N | N | N | N | N | N |

### 29.3 Sales Order Permissions

| Permission | Super Admin | Company Owner | Sales Manager | Sales Exec | Sales Rep | Cashier | Warehouse Mgr | Finance Mgr | Approver | Auditor | Read Only |
|------------|:-----------:|:-------------:|:-------------:|:----------:|:---------:|:-------:|:--------------:|:-----------:|:--------:|:-------:|:---------:|
| sales.order.create | Y | Y | Y | Y | Y | Y | N | N | N | N | N |
| sales.order.read | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| sales.order.update | Y | Y | Y | Y | Y | N | N | N | N | N | N |
| sales.order.submit | Y | Y | Y | Y | Y | Y | N | N | N | N | N |
| sales.order.approve | Y | Y | Y | N | N | N | N | N | Y | N | N |
| sales.order.reject | Y | Y | Y | N | N | N | N | N | Y | N | N |
| sales.order.cancel | Y | Y | Y | N | N | N | N | N | N | N | N |

### 29.4 Delivery Note Permissions

| Permission | Super Admin | Company Owner | Sales Manager | Sales Exec | Sales Rep | Cashier | Warehouse Mgr | Finance Mgr | Approver | Auditor | Read Only |
|------------|:-----------:|:-------------:|:-------------:|:----------:|:---------:|:-------:|:--------------:|:-----------:|:--------:|:-------:|:---------:|
| sales.delivery.create | Y | Y | Y | N | N | N | Y | N | N | N | N |
| sales.delivery.read | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| sales.delivery.dispatch | Y | Y | N | N | N | N | Y | N | N | N | N |
| sales.delivery.cancel | Y | Y | Y | N | N | N | Y | N | N | N | N |

### 29.5 Invoice Permissions

| Permission | Super Admin | Company Owner | Sales Manager | Sales Exec | Sales Rep | Cashier | Warehouse Mgr | Finance Mgr | Approver | Auditor | Read Only |
|------------|:-----------:|:-------------:|:-------------:|:----------:|:---------:|:-------:|:--------------:|:-----------:|:--------:|:-------:|:---------:|
| sales.invoice.create | Y | Y | N | N | N | N | N | Y | N | N | N |
| sales.invoice.read | Y | Y | Y | Y | Y | Y | N | Y | Y | Y | Y |
| sales.invoice.issue | Y | Y | N | N | N | N | N | Y | N | N | N |
| sales.invoice.cancel | Y | Y | N | N | N | N | N | Y | N | N | N |
| sales.invoice.export | Y | Y | Y | Y | N | N | N | Y | N | Y | N |

### 29.6 Return Permissions

| Permission | Super Admin | Company Owner | Sales Manager | Sales Exec | Sales Rep | Cashier | Warehouse Mgr | Finance Mgr | Approver | Auditor | Read Only |
|------------|:-----------:|:-------------:|:-------------:|:----------:|:---------:|:-------:|:--------------:|:-----------:|:--------:|:-------:|:---------:|
| sales.return.create | Y | Y | Y | Y | Y | N | N | N | N | N | N |
| sales.return.read | Y | Y | Y | Y | Y | N | Y | Y | Y | Y | Y |
| sales.return.submit | Y | Y | Y | Y | Y | N | N | N | N | N | N |
| sales.return.approve | Y | Y | Y | N | N | N | N | N | Y | N | N |
| sales.return.receive | Y | Y | N | N | N | N | Y | N | N | N | N |
| sales.return.complete | Y | Y | Y | N | N | N | N | Y | N | N | N |

### 29.7 Pricing Permissions

| Permission | Super Admin | Company Owner | Sales Manager | Sales Exec | Sales Rep | Cashier | Warehouse Mgr | Finance Mgr | Approver | Auditor | Read Only |
|------------|:-----------:|:-------------:|:-------------:|:----------:|:---------:|:-------:|:--------------:|:-----------:|:--------:|:-------:|:---------:|
| sales.pricing.manage | Y | Y | Y | N | N | N | N | N | N | N | N |
| sales.pricing.read | Y | Y | Y | Y | Y | Y | N | Y | N | Y | Y |
| sales.pricing.override | Y | Y | Y | Y | N | N | N | N | N | N | N |
| sales.discount.manage | Y | Y | Y | N | N | N | N | N | N | N | N |

### 29.8 Report & Config Permissions

| Permission | Super Admin | Company Owner | Sales Manager | Sales Exec | Sales Rep | Cashier | Warehouse Mgr | Finance Mgr | Approver | Auditor | Read Only |
|------------|:-----------:|:-------------:|:-------------:|:----------:|:---------:|:-------:|:--------------:|:-----------:|:--------:|:-------:|:---------:|
| sales.report.read | Y | Y | Y | Y | Y | N | N | Y | N | Y | Y |
| sales.report.export | Y | Y | Y | Y | N | N | N | Y | N | Y | N |
| sales.config.manage | Y | Y | N | N | N | N | N | N | N | N | N |
| sales.approval.manage | Y | Y | Y | N | N | N | N | N | N | N | N |
| sales.feature_flag.manage | Y | Y | N | N | N | N | N | N | N | N | N |

---

## 30. Feature Matrix

### 30.1 Ready & Enabled (Epic 7 — P1)

| Feature | Description |
|---------|-------------|
| Customer Master | Full customer lifecycle management with contacts, addresses, credit control |
| Customer Categories & Groups | Configurable classification and grouping |
| Payment Terms | Company-scoped payment term master data |
| Sales Quotations | Full quotation lifecycle with revision history |
| Sales Orders | Full order lifecycle with approval workflow |
| Delivery Notes | Stock reservation, dispatch, and delivery tracking |
| Sales Invoices | Invoice generation, sequencing, discount/charge management |
| Sales Returns | RMA workflow with credit note and replacement resolution |
| Price Lists | Multiple price lists with effective dates |
| Customer-Specific Pricing | Per-customer price overrides |
| Discount Rules | Percentage and fixed amount discounts with applicability |
| Minimum Margin Guard | Configurable margin threshold with approval override |
| Approval Matrix | Configurable value-based approval workflow |
| Credit Control | Credit limit, credit status, credit hold |
| Sales Reporting | 15+ report types with CSV/Excel export |
| Sales KPIs | 12+ KPI formulas with dashboard readiness |
| Customer Search | Full-text search with advanced filters |
| Audit Trail | Complete audit log for all state transitions |

### 30.2 Ready but Disabled (Feature Flags)

| Feature | Flag Key | Description |
|---------|----------|-------------|
| Customer Bulk Import | `sales.customer_bulk_import` | CSV and Excel import with validation |
| SO Email to Customer | `sales.so_email_customer` | Email order confirmation to customer |
| Invoice PDF Export | `sales.invoice_pdf_export` | Generate PDF from invoice data |
| Barcode Scan for Order Lines | `sales.so_barcode_scan` | Scan barcodes to add items to SO |
| DN PDF Export | `sales.dn_pdf_export` | Generate PDF delivery note |
| Customer Portal | `sales.customer_portal` | Read-only customer access to orders/invoices |
| Require Quotation Before Order | `sales.require_quotation_before_order` | Enforce quotation to order flow |
| Auto-Approve Below Threshold | `sales.auto_approve_orders` | Auto-approve orders below value threshold |
| Backorder Auto-Fulfil | `sales.backorder_auto_fulfil` | Auto-create DN when backorder stock arrives |
| Direct Invoice (No SO) | `sales.direct_invoice` | Create invoices without sales order |
| Buy X Get Y Promotions | `sales.buy_x_get_y` | Promotional discount type |
| Multi-Warehouse Fulfilment | `sales.multi_warehouse` | Route fulfilment to specific warehouses |
| Quotation Approval | `sales.quotation_approval` | Require approval before sending quotations |
| Customer Rating Auto-Calculate | `sales.customer_rating_auto` | Auto-calculate rating from transaction data |

### 30.3 Future (Not Implemented)

| Feature | Description | Target |
|---------|-------------|--------|
| Accounts Receivable | Payment tracking, ageing, collections | Epic 8+ |
| POS Integration | Real-time terminal, barcode scanning, receipt | Epic 10+ |
| E-commerce | Storefront, cart, online checkout | Epic 11+ |
| Multi-Currency | Exchange rates, currency conversion | Future |
| E-Invoicing | ZATCA, Peppol, FatturaPA compliance | Future |
| Dynamic Pricing | AI-driven pricing optimisation | Future |
| Subscription Billing | Recurring invoices, subscription management | Future |
| Commission Calculation | Sales representative commission | Future |
| Customer Loyalty | Points, rewards, tiers | Future |

---

## 31. Sales Governance

### 31.1 Approval Governance

- All approval matrices are company-scoped and configurable by Company Owner or Sales Manager
- Approval thresholds are based on document total value (in company base currency)
- Approval rules can be differentiated by customer category (e.g., Government orders always require Director approval)
- Approval history is immutable and includes: approver, decision, timestamp, comments
- Delegation of approval authority is not supported in Epic 7 (future capability)

### 31.2 Credit Governance

- Credit limits are set per customer and default from customer category
- Credit check is performed at order approval (not at order creation)
- Credit hold can be manually placed/released by Finance Manager
- Credit status is recalculated when:
  - A new order is approved
  - An invoice is issued
  - A payment is received (future AR)
  - A credit note is issued

### 31.3 Pricing Governance

- Price overrides are audited (original price, override price, user, reason)
- Minimum margin violations require manager approval
- Discount application is logged with rule reference
- Price list changes do not retroactively affect existing documents

### 31.4 Document Governance

- All document numbers are system-generated, sequential, and immutable
- Invoice numbers are gap-free (cancelled invoices retain their number as void)
- All documents support soft-delete only (no hard-delete of commercial records)
- All state transitions are audited

---

## 32. Conceptual Domain Model

```
+---------------+     1:N      +---------------+
|   Customer    |------------->|   Contact     |
|               |              +---------------+
|  category ----|--- N:1 ----->+---------------+
|  group -------|--- N:1 ----->|CustomerGroup  |
|  payment_term |--- N:1 --+  +---------------+
|               |          |   +---------------+
|               |----------+-->| PaymentTerm   |
|               |   1:N        +---------------+
|               |------------->+---------------+
|               |              |   Address     |
|               |              +---------------+
|               |   1:N
|               |------------->+---------------+
|               |              |  BankDetail   |
|               |              +---------------+
+-------+-------+
        | 1:N
        v
+---------------+  1:1  +---------------+
|SalesQuotation |------->|  SalesOrder   |
|               |        |               |
|  quotation_   |        |  order_lines  |---- 1:N --> OrderLine
|  lines        |        |  approvals    |---- 1:N --> ApprovalRecord
|  revisions    |        |               |
+---------------+        +-------+-------+
                                 | 1:N
                                 v
                         +---------------+
                         | DeliveryNote  |
                         |               |
                         |  dn_lines ----|---- 1:N --> DNLine
                         +-------+-------+
                                 | N:1
                                 v
                         +---------------+
                         | SalesInvoice  |
                         |               |
                         |  inv_lines ---|---- 1:N --> InvoiceLine
                         |  charges  ----|---- 1:N --> InvoiceCharge
                         +---------------+

+---------------+
| SalesReturn   |
|               |
|  return_lines |---- 1:N --> ReturnLine
|  resolution   |
+---------------+

+---------------+   1:N   +---------------+
|  PriceList    |--------->|  PriceEntry   |
+---------------+          +---------------+

+---------------+
| DiscountRule  |
+---------------+

+---------------+
|CustomerCategory|
+---------------+

+---------------+
|ApprovalMatrix |
+---------------+
```

---

## 33. Aggregate Roots

| Aggregate Root | Owned Entities | Repository Boundary |
|---------------|---------------|---------------------|
| **Customer** | Contact, Address, BankDetail, CustomerNote, CustomFieldValue | CustomerRepository |
| **SalesQuotation** | QuotationLine, QuotationRevision | SalesQuotationRepository |
| **SalesOrder** | OrderLine, ApprovalRecord | SalesOrderRepository |
| **DeliveryNote** | DNLine | DeliveryNoteRepository |
| **SalesInvoice** | InvoiceLine, InvoiceCharge | SalesInvoiceRepository |
| **SalesReturn** | ReturnLine | SalesReturnRepository |
| **PriceList** | PriceEntry | PriceListRepository |
| **DiscountRule** | — | DiscountRuleRepository |
| **CustomerCategory** | — | CustomerCategoryRepository |
| **CustomerGroup** | — | CustomerGroupRepository |
| **PaymentTerm** | — | PaymentTermRepository |
| **ApprovalMatrix** | ApprovalMatrixRule | ApprovalMatrixRepository |
| **SalesCostEntry** | — | SalesCostEntryRepository |

---

## 34. Domain Events

### 34.1 Customer Events

| Event | Trigger | Payload |
|-------|---------|---------|
| `customer.created` | Customer record created | customer_id, company_id, customer_code, customer_type |
| `customer.updated` | Customer record modified | customer_id, company_id, changed_fields |
| `customer.activated` | Customer transitions to ACTIVE | customer_id, company_id |
| `customer.deactivated` | Customer transitions to INACTIVE | customer_id, company_id |
| `customer.blocked` | Customer transitions to BLOCKED | customer_id, company_id, reason |
| `customer.unblocked` | Customer transitions from BLOCKED to ACTIVE | customer_id, company_id |
| `customer.credit_limit_changed` | Credit limit modified | customer_id, company_id, old_limit, new_limit |
| `customer.credit_hold_placed` | Manual credit hold applied | customer_id, company_id |
| `customer.credit_hold_released` | Credit hold removed | customer_id, company_id |

### 34.2 Quotation Events

| Event | Trigger | Payload |
|-------|---------|---------|
| `sales.quotation.created` | Quotation created | quotation_id, company_id, customer_id |
| `sales.quotation.sent` | Quotation sent to customer | quotation_id, company_id |
| `sales.quotation.accepted` | Customer accepts quotation | quotation_id, company_id |
| `sales.quotation.rejected` | Customer rejects quotation | quotation_id, company_id |
| `sales.quotation.converted` | Quotation converted to SO | quotation_id, company_id, sales_order_id |
| `sales.quotation.expired` | Quotation validity expired | quotation_id, company_id |
| `sales.quotation.cancelled` | Quotation cancelled | quotation_id, company_id |
| `sales.quotation.expiring_soon` | Quotation validity approaching | quotation_id, company_id, expiry_date |

### 34.3 Sales Order Events

| Event | Trigger | Payload |
|-------|---------|---------|
| `sales.order.created` | SO created | order_id, company_id, customer_id |
| `sales.order.submitted` | SO submitted for approval | order_id, company_id, total_amount |
| `sales.order.approved` | SO approved | order_id, company_id, approved_by |
| `sales.order.rejected` | SO rejected | order_id, company_id, rejected_by, reason |
| `sales.order.cancelled` | SO cancelled | order_id, company_id, reason |
| `sales.order.partially_delivered` | Partial delivery made | order_id, company_id |
| `sales.order.delivered` | All lines fully delivered | order_id, company_id |
| `sales.order.invoiced` | Invoice generated for SO | order_id, company_id, invoice_id |
| `sales.order.closed` | SO closed | order_id, company_id |
| `sales.order.credit_hold` | Approval blocked by credit | order_id, company_id, customer_id |

### 34.4 Delivery Events

| Event | Trigger | Payload |
|-------|---------|---------|
| `sales.delivery.created` | DN created | delivery_id, company_id, order_id |
| `sales.delivery.dispatched` | DN dispatched (stock deducted) | delivery_id, company_id, order_id |
| `sales.delivery.delivered` | Delivery confirmed received | delivery_id, company_id |
| `sales.delivery.cancelled` | DN cancelled (stock released) | delivery_id, company_id |

### 34.5 Invoice Events

| Event | Trigger | Payload |
|-------|---------|---------|
| `sales.invoice.created` | Invoice created | invoice_id, company_id, customer_id |
| `sales.invoice.issued` | Invoice finalised and issued | invoice_id, company_id, total_amount, due_date |
| `sales.invoice.cancelled` | Invoice voided | invoice_id, company_id |
| `sales.invoice.credit_note_issued` | Credit note against invoice | invoice_id, company_id, credit_note_amount |

### 34.6 Return Events

| Event | Trigger | Payload |
|-------|---------|---------|
| `sales.return.created` | Return created | return_id, company_id, customer_id |
| `sales.return.submitted` | Return submitted for approval | return_id, company_id |
| `sales.return.approved` | Return approved | return_id, company_id |
| `sales.return.rejected` | Return rejected | return_id, company_id |
| `sales.return.received` | Returned goods received | return_id, company_id |
| `sales.return.completed` | Return resolved | return_id, company_id, resolution_type |
| `sales.return.refund_ready` | Return marked for refund | return_id, company_id |

**Total: 38 domain events**

---

## 35. Reporting Requirements

### 35.1 Sales Reports

| Report | Description | Filters |
|--------|-------------|---------|
| Sales Summary | Total sales by period (daily, weekly, monthly, yearly) | Date range, currency |
| Sales by Customer | Revenue per customer with ranking | Date range, category, group |
| Sales by Product | Revenue per product with quantity and margin | Date range, product category |
| Sales by Representative | Revenue per sales representative | Date range, team |
| Sales Order Pipeline | Open orders by status with estimated value | Status, date range, priority |
| Sales vs Target | Actual sales compared to target (configurable) | Period, representative, territory |
| Top Customers | Pareto analysis of customer revenue contribution | Date range, top N |
| Sales Trend | Month-over-month and year-over-year comparison | Date range |

### 35.2 Customer Reports

| Report | Description | Filters |
|--------|-------------|---------|
| Customer List | All customers with status, category, credit info | Status, category, group |
| Customer Ageing | Outstanding balance by ageing bucket (future AR) | Customer, date |
| Customer Activity | Transaction history per customer | Customer, date range |
| New Customers | Customers created in period | Date range, category |
| Customer Credit Report | Credit limit utilisation across customers | Category, credit status |

### 35.3 Quotation Reports

| Report | Description | Filters |
|--------|-------------|---------|
| Quotation Conversion Rate | Percentage of quotations converted to orders | Date range, representative |
| Quotation Pipeline | Open quotations by status and value | Status, validity, customer |
| Expired Quotations | Quotations that expired without conversion | Date range |

### 35.4 Delivery Reports

| Report | Description | Filters |
|--------|-------------|---------|
| Pending Deliveries | Approved orders awaiting fulfilment | Priority, date range |
| Delivery Performance | On-time delivery rate | Date range, customer |
| Backorder Report | Unfulfilled order lines awaiting stock | Product, customer |

### 35.5 Profitability Reports

| Report | Description | Filters |
|--------|-------------|---------|
| Gross Margin by Product | Margin analysis per product | Date range, category |
| Gross Margin by Customer | Margin analysis per customer | Date range, group |
| Discount Analysis | Discounts applied, by rule, by user | Date range, rule, user |

### 35.6 Audit Reports

| Report | Description | Filters |
|--------|-------------|---------|
| Sales Audit Trail | All state transitions with actor and timestamp | Document type, date range |
| Price Override Report | All manual price overrides with justification | Date range, user |
| Credit Limit Change Report | All credit limit modifications | Date range, customer |
| Approval History | All approval/rejection decisions | Date range, approver |

---

## 36. KPI Requirements

| KPI ID | KPI Name | Formula | Target |
|--------|----------|---------|--------|
| KPI-01 | Total Sales Revenue | Sum of all issued invoice totals in period | Upward trend |
| KPI-02 | Gross Margin % | (Revenue - COGS) / Revenue x 100 | > 25% (configurable) |
| KPI-03 | Quotation Conversion Rate | Converted quotations / Total quotations x 100 | > 30% |
| KPI-04 | Average Order Value (AOV) | Total revenue / Number of orders in period | Upward trend |
| KPI-05 | Sales Growth Rate | (Current period - Previous period) / Previous period x 100 | > 0% |
| KPI-06 | Customer Retention Rate | Repeat customers / Total customers x 100 | > 70% |
| KPI-07 | On-Time Delivery Rate | On-time deliveries / Total deliveries x 100 | > 95% |
| KPI-08 | Outstanding Orders Value | Sum of approved but undelivered order values | Monitor |
| KPI-09 | Return Rate | Returned value / Total sales value x 100 | < 5% |
| KPI-10 | Average Days to Fulfil | Avg days from order approval to delivery dispatch | < 3 days |
| KPI-11 | Credit Utilisation | Avg outstanding / Avg credit limit x 100 | < 80% |
| KPI-12 | Invoice Cycle Time | Avg days from delivery to invoice issuance | < 2 days |

---

## 37. Search Requirements

### 37.1 Customer Search

- Full-text search across: legal_name, trading_name, customer_code, contact email, contact phone
- Filters: status, category, group, credit_status, customer_type, country
- Sorting: name, code, created_date, credit_limit, outstanding_balance
- Pagination: configurable page size (default 20, max 100)
- Saved filters: users can save and recall filter combinations

### 37.2 Sales Document Search

- Full-text search across: document number, customer name, product description, notes
- Filters: status, date range, customer, sales representative, priority, currency
- Sorting: document number, date, total_amount, customer_name, status
- Pagination: configurable page size
- Saved filters: users can save and recall filter combinations

### 37.3 Product Search (via Epic 5)

- When adding lines to sales documents, users can search products from Epic 5 Inventory
- Search by: product name, SKU, barcode (when barcode scan flag enabled)
- Results include: available quantity, unit price (from applicable price list), unit of measure

---

## 38. Import and Export

### 38.1 Customer Import

- **Format**: CSV and Excel (.xlsx)
- **Feature Flag**: `sales.customer_bulk_import`
- **Validation**: Row-level validation with error report (row number, field, error message)
- **Duplicate Detection**: Match on customer_code within company
- **Behaviour**: Create new customers; optionally update existing (configurable)
- **Capacity**: 10,000 records per import batch
- **Error Handling**: Partial import — valid rows imported, invalid rows reported

### 38.2 Data Export

- All list views support export to CSV and Excel
- Export respects current filters and sorting
- Export includes all visible columns plus configurable additional fields
- Maximum export size: 50,000 records per export
- Export generates a downloadable file (not streamed)

### 38.3 Document Export

- Invoice PDF export (feature flag: `sales.invoice_pdf_export`)
- Delivery Note PDF export (feature flag: `sales.dn_pdf_export`)
- PDF includes: company header, document details, line items, totals, terms
- PDF template is company-configurable (future)

---

## 39. Notifications

### 39.1 Notification Events

| Event | Notification | Channel |
|-------|-------------|---------|
| Order submitted for approval | Notify approver(s) | In-app, Email (future) |
| Order approved | Notify sales representative | In-app, Email (future) |
| Order rejected | Notify sales representative with reason | In-app, Email (future) |
| Credit hold triggered | Notify sales representative and finance manager | In-app, Email (future) |
| Quotation expiring soon | Notify sales representative | In-app |
| Delivery dispatched | Notify customer (future) | Email (future) |
| Invoice issued | Notify customer (future) | Email (future) |
| Return approved | Notify customer and warehouse | In-app |
| Backorder fulfilable | Notify sales representative | In-app |

### 39.2 Notification Channels

- **In-App**: Notification centre within the ERP application (Epic 7 — P1)
- **Email**: SMTP-based email notifications (future — ready via domain events)
- **SMS**: SMS gateway integration (future)
- **WhatsApp**: WhatsApp Business API integration (future)
- **Push Notifications**: Mobile push notifications (future)

---

## 40. Audit Requirements

- Every state transition on every sales document is logged with:
  - Actor (user_id, user_name)
  - Timestamp (UTC)
  - Action (created, updated, submitted, approved, rejected, cancelled, etc.)
  - Previous state and new state
  - Reason (when applicable — cancellation, rejection)
  - IP address of the actor
- Price overrides are logged with original price, override price, and justification
- Credit limit changes are logged with old value, new value, and approver
- Discount applications are logged with rule reference and discount value
- Customer data changes are logged with changed fields and old/new values
- Audit logs are immutable (append-only, no updates, no deletes)
- Audit logs are retained per company data retention policy (default: 7 years)
- Audit logs are queryable by document type, date range, actor, and action

---

## 41. Security Requirements

- **Authentication**: All sales endpoints require valid JWT authentication (Epic 2)
- **Authorisation**: All operations enforce RBAC permissions per §29 Permission Matrix
- **Tenant Isolation**: All queries include `company_id` filter; no cross-tenant data access
- **Input Validation**: All user inputs validated against §28 Validation Rules
- **SQL Injection Prevention**: Parameterised queries for all database operations
- **XSS Prevention**: All user-generated content is sanitised before storage and output
- **Mass Assignment Prevention**: Only whitelisted fields accepted in create/update operations
- **Rate Limiting**: Sales endpoints subject to platform rate limiting (Epic 1)
- **BOLA Prevention**: Object-level authorisation on every record access (company_id + user permission)
- **Sensitive Data**: Credit card numbers, if ever captured, must be masked (not applicable in Epic 7, but the pattern must not permit storage)
- **Session Management**: Token expiry and refresh per Epic 2 configuration

---

## 42. Compliance Requirements

- **Invoice Sequencing**: Gap-free sequential numbering for regulatory compliance
- **Document Immutability**: Issued invoices and dispatched delivery notes cannot be modified
- **Audit Trail**: Complete transaction audit trail for financial and regulatory audits
- **Data Residency**: All data stored in the company's designated data region (future multi-region)
- **Right to Erasure**: Customer personal data can be anonymised on request while preserving transactional integrity (future GDPR compliance)
- **Tax Readiness**: Tax rate and tax amount fields present on all financial documents for future tax engine integration

---

## 43. Data Retention

| Data Type | Retention Period | Policy |
|-----------|-----------------|--------|
| Active customer records | Indefinite while active | Retained until deactivated |
| Inactive customer records | 7 years after last transaction | Soft-deleted, then anonymised |
| Sales documents (SQ, SO, DN, SI, SR) | 10 years | Retained for regulatory compliance |
| Audit logs | 10 years | Immutable, compressed after 2 years |
| Price lists and pricing data | 5 years after expiry | Retained for historical analysis |
| Deleted records (soft-delete) | 90 days before permanent purge readiness | Recoverable during retention period |
| Document attachments | Same as parent record | Follows parent retention policy |

---

## 44. Disaster Recovery

- **RPO (Recovery Point Objective)**: Maximum 15 minutes of data loss
- **RTO (Recovery Time Objective)**: Maximum 4 hours to full service restoration
- **Backup Strategy**: Continuous database replication with point-in-time recovery
- **Backup Frequency**: Transaction log backups every 15 minutes; full backup daily
- **Backup Verification**: Monthly restore test from backup
- **Document Recovery**: Individual document recovery from audit log replay
- **Failover**: Database failover to standby replica (future — cloud deployment)

---

## 45. Performance Targets

| Operation | Target | Measurement |
|-----------|--------|-------------|
| Customer search | p95 < 300ms | 100,000 customers in the database |
| Customer detail view | p95 < 200ms | With contacts, addresses, and credit info |
| Sales order list | p95 < 500ms | 50,000 orders in the database |
| Sales order creation | p95 < 1s | Including price resolution |
| Sales order approval | p95 < 1s | Including credit check |
| Delivery note confirmation | p95 < 2s | Including stock reservation/deduction |
| Invoice generation | p95 < 2s | From DN or SO |
| Report generation | p95 < 5s | Up to 100,000 transactions |
| Customer bulk import | < 60s | 10,000 records |
| CSV/Excel export | < 30s | 50,000 records |
| Price resolution | p95 < 100ms | 7-level priority hierarchy |
| Concurrent users | No degradation | 200 concurrent users per tenant |

---

## 46. Scalability Targets

| Metric | Target |
|--------|--------|
| Customers per tenant | 100,000 |
| Sales orders per tenant | 500,000 |
| Invoices per tenant | 500,000 |
| Order lines per order | 500 |
| Price lists per tenant | 50 |
| Price entries per list | 50,000 |
| Discount rules per tenant | 200 |
| Concurrent tenants | 1,000 |
| Concurrent users per tenant | 200 |

---

## 47. Cross-Module Dependencies

### 47.1 Required Dependencies

| Module | Dependency | Direction |
|--------|-----------|-----------|
| Epic 1 (Foundation) | Base models, utilities, file storage | Sales uses Foundation |
| Epic 2 (Authentication) | JWT validation, user context | Sales uses Auth |
| Epic 3 (Companies) | Company context, company_id | Sales uses Companies |
| Epic 4 (Users & Roles) | RBAC permission checks, user roles | Sales uses Users & Roles |
| Epic 5 (Inventory) | Product catalogue, stock check, reservation, deduction, restock | Sales and Inventory bidirectional |

### 47.2 Optional Dependencies

| Module | Dependency | Direction |
|--------|-----------|-----------|
| Epic 6 (Purchase) | Reorder trigger when stock falls below reorder point after sales dispatch | Sales notifies Purchase (event) |

### 47.3 Future Dependencies

| Module | Dependency | Direction |
|--------|-----------|-----------|
| Accounts Receivable | Invoice to payment tracking, ageing | Sales to AR |
| Accounting | Invoice to journal entries, revenue recognition | Sales to Accounting |
| CRM | Customer to leads, opportunities | Sales and CRM bidirectional |
| POS | Direct sales, receipt generation | POS to Sales |
| E-commerce | Online orders to sales orders | E-commerce to Sales |

---

## 48. Cross-Module Contracts

### 48.1 Sales to Inventory (Epic 5) Contracts

| Event | Trigger | Inventory Action |
|-------|---------|-----------------|
| Delivery Note Created (DRAFT) | DN created for SO lines | `StockMovement(SALES_RESERVATION)` — reserve stock |
| Delivery Note Dispatched | DN confirmed dispatched | `StockMovement(SALES_DISPATCH)` — deduct on-hand stock |
| Delivery Note Cancelled | DN cancelled in DRAFT | `StockMovement(SALES_RESERVATION_RELEASE)` — release reservation |
| Sales Return Received | Returned goods accepted | `StockMovement(SALES_RETURN_INBOUND)` — restock accepted items |
| Sales Order Cancelled | Approved SO cancelled | Release any associated reservations |

### 48.2 Sales to Purchase (Epic 6) Contracts

| Event | Trigger | Purchase Action |
|-------|---------|----------------|
| Stock Below Reorder Point | Sales dispatch reduces stock below reorder | `purchase.reorder.suggested` event — suggest purchase requisition |

### 48.3 Inventory to Sales Contracts

| Event | Trigger | Sales Action |
|-------|---------|-------------|
| Stock Received | Goods receipt confirmed | Check backorder queue, notify users of fulfilable backorders |
| Product Updated | Product details changed | Update cached product info on open drafts (advisory) |

---

## 49. Integration Readiness

### 49.1 Current (Epic 7)

| Integration | Status | Description |
|-------------|--------|-------------|
| Epic 5 Inventory | Active | Stock check, reservation, deduction, restock |
| Epic 4 RBAC | Active | Permission enforcement on all operations |
| Epic 2 Auth | Active | JWT token validation |
| Domain Events | Active | 38 events published via InProcessEventBus |

### 49.2 Ready (Feature-Flagged)

| Integration | Flag | Description |
|-------------|------|-------------|
| Barcode Scanning | `sales.so_barcode_scan` | Product lookup by barcode via Epic 5 |
| Email (SO Confirmation) | `sales.so_email_customer` | Send order confirmation to customer email |
| PDF Export | `sales.invoice_pdf_export`, `sales.dn_pdf_export` | Generate PDF documents |

### 49.3 Future

| Integration | Description |
|-------------|-------------|
| POS Terminal | Real-time sales via POS hardware |
| E-commerce Platform | Online storefront order sync |
| Payment Gateway | Credit card, bank transfer processing |
| Mobile Sales App | Offline-capable mobile order entry |
| Customer Portal | Self-service order tracking and invoice viewing |
| QR Code | QR-based product lookup and order sharing |
| Webhooks | External system notification on sales events |
| EDI | Electronic Data Interchange for B2B |

---

## 50. AI Readiness

The data model and event architecture are designed to support future AI capabilities:

| Capability | Data Required | Status |
|------------|--------------|--------|
| Sales Forecasting | Historical sales data, seasonal patterns | Data model ready |
| Demand Forecasting | Sales velocity, inventory levels, lead times | Cross-module data ready |
| Cross-Sell Suggestions | Customer purchase history, product affinity | Data model ready |
| Upsell Suggestions | Customer order history, product tiers | Data model ready |
| Customer Churn Prediction | Customer activity frequency, recency, value | Data model ready |
| AI Sales Assistant | All transactional data, customer interactions | Event stream ready |
| Smart Pricing | Competitor data (external), demand elasticity | Price list structure ready |
| Next Best Offer | Customer segment, purchase patterns | Customer group/category ready |
| Sentiment Analysis | Customer notes, return reasons | Free-text fields ready |

---

## 51. Analytics Readiness

### 51.1 Analytics Data Model

All entities include analytics-enabling fields:

- `company_id` (tenant dimension)
- `created_at`, `updated_at` (time dimension)
- `created_by`, `updated_by` (user dimension)
- Customer category, group, type (customer dimensions)
- Product reference (product dimension — via Epic 5)
- Currency, amount, quantity (measure fields)
- Status (lifecycle dimension)

### 51.2 Pre-Computed Metrics

The following metrics are available for real-time dashboards:

- Total revenue (period-based)
- Order count and value (by status)
- Quotation conversion funnel
- Delivery pipeline
- Customer credit utilisation
- Top products by revenue and margin
- Sales representative performance

### 51.3 Future Analytics Platform

- Data warehouse export readiness (structured events)
- ETL-friendly event payloads (JSON, timestamp, aggregate_id)
- Dimensional model alignment (star schema ready)

---

## 52. Extensibility Strategy

### 52.1 Extension Points

| Extension Point | Mechanism | Example |
|----------------|-----------|---------|
| Custom Fields | JSON-based custom field storage on Customer entity | Company-specific customer attributes |
| Configurable Categories | Company-scoped master data tables | Custom customer categories, return reasons |
| Feature Flags | Runtime toggle for optional capabilities | Enable/disable barcode scanning |
| Approval Rules | Configurable approval matrix per company | Different thresholds per industry |
| Price Resolution | Pluggable pricing hierarchy | Add currency conversion layer |
| Document Templates | Configurable print templates (future) | Company-branded invoice format |
| Event Handlers | Subscribe to domain events | Add custom post-processing |
| Discount Types | Extensible discount rule engine | Add loyalty discount type |

### 52.2 Non-Breaking Extension Rules

- New fields are always optional or have defaults
- New status values are additive (never removed)
- New events are additive (never removed or renamed)
- API versions are maintained for backward compatibility
- Database migrations are forward-only and reversible

---

## 53. Versioning Strategy

- **Entities**: Optimistic concurrency via `version` field on all aggregate roots
- **Documents**: Revision tracking on quotations; version tracking on orders (resubmission increments version)
- **API**: Versioned endpoints (v1, v2, etc.) with deprecation policy
- **Events**: Event payloads include `event_version` field for schema evolution
- **Price Lists**: Effective date ranges for temporal versioning
- **Approval Matrix**: Versioned rules with effective dates

---

## 54. Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Inventory integration complexity | High | Medium | Use established cross-module contract pattern from Epic 6 |
| Credit check performance bottleneck | Medium | Low | Cache credit status; recalculate asynchronously on balance changes |
| Invoice sequencing under concurrency | High | Medium | Database-level sequence with advisory locks |
| Price resolution complexity | Medium | Medium | Well-defined priority hierarchy; cache resolved prices |
| Large order line count performance | Medium | Low | Pagination on lines; lazy loading; database indexing |
| Multi-currency readiness without implementation | Low | High | Design currency fields now; defer conversion logic |
| Tax calculation placeholder accuracy | Medium | Medium | Clear documentation that tax fields are placeholder; validation rules prevent incorrect totals |
| Scope creep into AR/CRM territory | High | Medium | Strict bounded context enforcement; explicit Out of Scope list |

---

## 55. Assumptions

- **A01**: Epic 5 (Inventory) provides a stable product catalogue and stock movement API
- **A02**: Epic 4 (Users & Roles) RBAC system supports the permission matrix defined in §29
- **A03**: Epic 2 (Authentication) JWT tokens include `user_id` and `company_id` claims
- **A04**: The shared `SequenceService` supports configurable sequence formats per document type
- **A05**: The `InProcessEventBus` from Epic 6 is reusable for sales domain events
- **A06**: The `ApprovalService` pattern from Epic 6 is reusable for sales approval workflows
- **A07**: All monetary amounts are stored in the company's base currency (multi-currency is future)
- **A08**: Tax calculation is deferred to a future tax engine; Epic 7 provides field placeholders only
- **A09**: Payment collection is not part of Epic 7; invoices represent financial claims only
- **A10**: The platform file storage service (Epic 1) supports document attachments
- **A11**: Customer categories, groups, payment terms, and return reason codes are seeded per company on first use or via configuration

---

## 56. Constraints

- **C01**: Must maintain full backward compatibility with Epics 0-6
- **C02**: Must use the same technology stack (FastAPI, SQLAlchemy, PostgreSQL, Next.js)
- **C03**: Must follow the Modular Monolith architecture established in Epic 0
- **C04**: Must follow Clean Architecture patterns established in previous Epics
- **C05**: Must use the TenantBaseModel for all entities (company_id isolation)
- **C06**: Must use soft-delete for all entities (no hard-delete of business records)
- **C07**: All monetary values must use Decimal type with appropriate precision (15,4 for unit prices, 15,2 for totals)
- **C08**: Must not store actual payment information (credit cards, bank account numbers for payment processing)
- **C09**: Must not implement general ledger or accounting entries (future epic)
- **C10**: Database migrations must be forward-only and compatible with Alembic

---

## 57. Success Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| O2C Process Coverage | 100% of steps from quotation to return managed in system | Feature checklist verification |
| Order Processing Time | < 5 minutes for a complete order with lines and approval | End-to-end workflow test |
| Test Pass Rate | 100% of all test suites passing | Automated test execution |
| Code Coverage | > 80% across sales module | Coverage tool measurement |
| Zero Cross-Tenant Leakage | 0 cross-company data access violations | Tenant isolation test suite |
| RBAC Compliance | 100% of operations enforce correct permissions | Permission matrix test suite |
| Performance Targets Met | All §45 targets met | Performance benchmark suite |
| Docker Verification | Build, migrate, and smoke test all pass | Docker Compose verification |
| Domain Event Coverage | All 38 events published and verified | Event coverage test suite |
| Invoice Sequencing Integrity | Zero gaps in invoice sequences under concurrent load | Concurrency test |

---

## 58. Glossary

| Term | Definition |
|------|-----------|
| AOV | Average Order Value — total revenue / number of orders |
| AR | Accounts Receivable — money owed to the company by customers |
| BOLA | Broken Object-Level Authorisation — security vulnerability |
| COGS | Cost of Goods Sold — direct costs of producing goods sold |
| CRM | Customer Relationship Management |
| DN | Delivery Note — document confirming goods dispatch |
| EDI | Electronic Data Interchange — B2B document exchange |
| FIFO | First In, First Out — inventory valuation method |
| GSTIN | Goods and Services Tax Identification Number |
| O2C | Order-to-Cash — end-to-end sales business process |
| POS | Point of Sale — retail transaction processing |
| RBAC | Role-Based Access Control |
| RMA | Return Merchandise Authorisation |
| SI | Sales Invoice |
| SO | Sales Order |
| SQ | Sales Quotation |
| SR | Sales Return |
| TRN | Tax Registration Number |
| UOM | Unit of Measure |
| VAT | Value Added Tax |

---

## 59. Acceptance Criteria

### 59.1 Customer Management Acceptance

- AC-01: Users can create, activate, and manage customers through the full status lifecycle
- AC-02: Customer search returns results within p95 < 300ms with 100,000 records
- AC-03: Credit limits are enforced at order approval time
- AC-04: Customer categories and groups correctly influence pricing and reporting
- AC-05: Customer bulk import processes 10,000 records within 60 seconds (when enabled)

### 59.2 Sales Quotation Acceptance

- AC-06: Quotations follow the complete lifecycle from DRAFT through CONVERTED
- AC-07: Revision history is preserved and previous revisions are read-only
- AC-08: Expired quotations automatically transition to EXPIRED status
- AC-09: Conversion creates a correctly populated Sales Order with traceability

### 59.3 Sales Order Acceptance

- AC-10: Orders follow the complete lifecycle from DRAFT through CLOSED
- AC-11: Approval workflow correctly evaluates the approval matrix
- AC-12: Credit check blocks approval when customer credit is exceeded
- AC-13: Auto-approval works for orders below the configured threshold
- AC-14: Order cancellation captures and stores the reason

### 59.4 Order Fulfilment Acceptance

- AC-15: Inventory availability is checked before delivery note creation
- AC-16: Stock is reserved on DN creation and deducted on dispatch
- AC-17: Partial delivery correctly tracks quantities across multiple DNs
- AC-18: Delivery quantities cannot exceed ordered quantities

### 59.5 Sales Invoicing Acceptance

- AC-19: Invoices can be generated from delivery notes or sales orders
- AC-20: Invoice numbers are strictly sequential and gap-free
- AC-21: Issued invoices are immutable
- AC-22: Tax, discount, and charge fields are correctly calculated

### 59.6 Sales Returns Acceptance

- AC-23: Returns follow the complete lifecycle from DRAFT through COMPLETED
- AC-24: Returned goods are restocked via Epic 5 when accepted
- AC-25: Credit notes are generated for CREDIT_NOTE resolution type
- AC-26: Replacement orders are created for REPLACEMENT resolution type

### 59.7 Pricing Acceptance

- AC-27: Price resolution follows the 7-level priority hierarchy correctly
- AC-28: Quantity-based pricing (price breaks) resolves correctly
- AC-29: Minimum margin guard triggers approval when violated
- AC-30: Discount rules are correctly applied based on applicability filters

---

## 60. Epic Completion Criteria

Epic 7 is COMPLETE only when ALL of the following criteria are verified:

| EC | Criterion | Verification |
|----|-----------|-------------|
| EC-01 | Customer Master fully operational with status lifecycle | Integration test: create, activate, block, unblock, deactivate |
| EC-02 | Sales Quotation lifecycle complete with conversion | Integration test: create, send, accept, convert to SO |
| EC-03 | Sales Order lifecycle complete with approval | Integration test: create, submit, approve, deliver, invoice, close |
| EC-04 | Credit check enforcement operational | Integration test: exceed credit limit, approval blocked |
| EC-05 | Delivery Note lifecycle with inventory integration | Integration test: create DN, dispatch, verify stock deducted (Epic 5) |
| EC-06 | Sales Invoice generation and sequencing | Integration test: generate invoice, verify gap-free sequence |
| EC-07 | Sales Return workflow with restock | Integration test: create return, approve, receive, verify restock (Epic 5) |
| EC-08 | Pricing engine with 7-level resolution | Unit test: all 7 price resolution levels return correct prices |
| EC-09 | RBAC enforcement across all operations | Permission matrix test: all 11 roles x all operations |
| EC-10 | Multi-tenant isolation verified | Isolation test: zero cross-company data leakage across all entities |
| EC-11 | All 38 domain events published and verified | Event coverage test: all events published on correct triggers |
| EC-12 | Performance targets met (§45) | Benchmark test: all p95 targets pass |
| EC-13 | All reports and KPIs operational | Report test: all 15+ report types return correct data |
| EC-14 | Docker verification passes | Docker Compose: build, migrate, smoke test |
| EC-15 | Full regression suite passes (Epics 1-7) | pytest: zero failures across all modules |

---

## 61. Future Roadmap

### 61.1 Near-Term (Next 2 Epics)

| Feature | Estimated Epic | Dependency |
|---------|---------------|-----------|
| Accounts Receivable | Epic 8 | Sales Invoicing |
| Payment Collection | Epic 8 | Accounts Receivable |
| Accounting & General Ledger | Epic 9 | AR, AP, Sales, Purchase |

### 61.2 Medium-Term (3-5 Epics)

| Feature | Estimated Epic | Dependency |
|---------|---------------|-----------|
| Point of Sale (POS) | Epic 10 | Sales, Inventory |
| E-commerce Integration | Epic 11 | Sales, Inventory, Payments |
| Multi-Currency | Epic 12 | All financial modules |
| Advanced Tax Engine | Epic 13 | Sales, Purchase, Accounting |

### 61.3 Long-Term (6+ Epics)

| Feature | Description |
|---------|-------------|
| CRM | Leads, opportunities, campaigns |
| Mobile Sales App | Offline-capable mobile order entry |
| Customer Portal | Self-service order/invoice viewing |
| Subscription Billing | Recurring invoices and subscriptions |
| Commission Management | Sales representative commission calculation |
| Customer Loyalty | Points, rewards, tiers |
| Dynamic Pricing | AI-driven price optimisation |
| E-Invoicing | Regulatory compliance (ZATCA, Peppol, etc.) |
| Multi-Branch | Branch-level order routing and fulfilment |
| Warehouse Management (WMS) | Advanced picking, packing, routing |

---

*This specification is the permanent Single Source of Truth (SSOT) for Epic 7 — Sales Management. All implementation plans, task breakdowns, and code must align with this document. Any deviations require formal specification amendment with version increment.*
