# Official Enterprise Business Specification: Inventory Management (Epic 5)

**Feature Branch**: `005-inventory-management`
**Created**: 2026-07-20
**Status**: Draft — Pending Approval
**Epic**: 5 — Inventory Management
**Classification**: Core Business Domain — Foundation Layer
**Version**: 1.1.0
**Change Log**: v1.1.0 — Added Branch Readiness (§16.10), Multi-Currency Readiness (§15.18), Procurement Metadata Readiness (§14.16), expanded Cross-Epic Compatibility (§44), additional Business Rules (BR-024–BR-029), and ERP Evolution Roadmap (§58, Phase 7).

---

> **SSOT NOTICE**: This document is the Single Source of Truth (SSOT) for the Inventory Management domain of DevSphere ERP. All subsequent planning, implementation, and testing artifacts must align with and reference this specification. Any contradiction between this document and a downstream artifact must be resolved in favour of this document unless a formal change is approved and reflected here.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Epic Overview](#2-epic-overview)
3. [Business Vision](#3-business-vision)
4. [Business Goals](#4-business-goals)
5. [Business Scope](#5-business-scope)
6. [Out of Scope](#6-out-of-scope)
7. [Business Terminology](#7-business-terminology)
8. [Domain Philosophy](#8-domain-philosophy)
9. [Domain Boundaries](#9-domain-boundaries)
10. [Bounded Context](#10-bounded-context)
11. [Stakeholders](#11-stakeholders)
12. [User Personas](#12-user-personas)
13. [Business Capabilities](#13-business-capabilities)
14. [Product Master](#14-product-master)
15. [Inventory Operations](#15-inventory-operations)
16. [Warehouse Management](#16-warehouse-management)
17. [Product Lifecycle](#17-product-lifecycle)
18. [Stock Lifecycle](#18-stock-lifecycle)
19. [Inventory Lifecycle](#19-inventory-lifecycle)
20. [Business Workflows](#20-business-workflows)
21. [Functional Requirements](#21-functional-requirements)
22. [Non-Functional Requirements](#22-non-functional-requirements)
23. [Business Rules](#23-business-rules)
24. [Business Invariants](#24-business-invariants)
25. [Validation Rules](#25-validation-rules)
26. [Permission Matrix](#26-permission-matrix)
27. [Feature Matrix](#27-feature-matrix)
28. [Master Data Governance](#28-master-data-governance)
29. [Conceptual Domain Model](#29-conceptual-domain-model)
30. [Aggregate Roots](#30-aggregate-roots)
31. [Domain Events](#31-domain-events)
32. [Reporting Requirements](#32-reporting-requirements)
33. [KPI Requirements](#33-kpi-requirements)
34. [Search Requirements](#34-search-requirements)
35. [Import & Export](#35-import--export)
36. [Notifications](#36-notifications)
37. [Audit Requirements](#37-audit-requirements)
38. [Security Requirements](#38-security-requirements)
39. [Compliance Requirements](#39-compliance-requirements)
40. [Data Retention Policy](#40-data-retention-policy)
41. [Disaster Recovery](#41-disaster-recovery)
42. [Performance Targets](#42-performance-targets)
43. [Scalability Targets](#43-scalability-targets)
44. [Cross-Module Dependencies](#44-cross-module-dependencies)
45. [Cross-Module Contracts](#45-cross-module-contracts)
46. [Integration Readiness](#46-integration-readiness)
47. [AI Readiness](#47-ai-readiness)
48. [Analytics Readiness](#48-analytics-readiness)
49. [Extensibility Strategy](#49-extensibility-strategy)
50. [Versioning Strategy](#50-versioning-strategy)
51. [Risks](#51-risks)
52. [Assumptions](#52-assumptions)
53. [Constraints](#53-constraints)
54. [Success Metrics](#54-success-metrics)
55. [Glossary](#55-glossary)
56. [Acceptance Criteria](#56-acceptance-criteria)
57. [Epic Completion Criteria](#57-epic-completion-criteria)
58. [Future Roadmap](#58-future-roadmap)

---

## 1. Executive Summary

Epic 5 – Inventory Management establishes the **Product Master and Inventory Domain** of DevSphere ERP — the first core business domain and the foundational layer upon which all commercial modules depend.

Every subsequent business capability — Purchase, Sales, Accounting, CRM, Warranty, Installments, Reports, AI, and Analytics — requires a stable, authoritative inventory foundation. This specification defines that foundation in a manner that is industry-agnostic, multi-tenant, extensible, and production-grade.

The Inventory domain is architected around five distinct sub-domains:

| Sub-Domain | Responsibility |
| --- | --- |
| **Product Master** | Authoritative catalogue of all products, attributes, variants, and metadata |
| **Inventory Operations** | Stock levels, movements, valuations, and controls |
| **Warehouse Management** | Physical and logical storage locations and transfers |
| **Inventory Intelligence** | Alerts, reorder logic, dead stock detection, and business rules |
| **Inventory Analytics** | Trends, KPIs, forecasting readiness, and reporting data |

This specification covers all aspects of the Inventory domain from business goals through domain events, permission matrices, audit requirements, and future roadmap. It is designed to serve businesses across retail, wholesale, trading, construction, electrical, hardware, medical, sanitary, distribution, and manufacturing verticals without architectural modification.

---

## 2. Epic Overview

| Attribute | Value |
| --- | --- |
| **Epic Number** | 005 |
| **Epic Name** | Inventory Management |
| **Domain Classification** | Core Business Domain — Layer 1 |
| **Dependency Tier** | Foundation (all business domains depend on this) |
| **Business Priority** | Critical |
| **Multi-Tenant** | Yes — company-scoped isolation |
| **RBAC Integration** | Yes — Epic 4 role and permission system |
| **Audit Required** | Yes — full lifecycle audit trail |
| **Feature Flags** | Yes — modular capability activation |
| **SaaS Readiness** | Yes — per-tenant configuration |

### 2.1 Position in the ERP Ecosystem

```
Epic 0: Engineering Constitution    ← Platform Standards
Epic 1: Foundation Platform         ← Infrastructure
Epic 2: Authentication & Identity   ← Security Layer
Epic 3: Companies                   ← Tenant Management
Epic 4: Users & Roles               ← Identity & RBAC
                    ↓
        ══════════════════════════
        Epic 5: INVENTORY MANAGEMENT   ← THIS DOCUMENT
        ══════════════════════════
                    ↓
Epic 6: Purchase Management         ← Depends on Inventory
Epic 7: Sales Management            ← Depends on Inventory
Epic 8: Accounting                  ← Depends on Inventory Valuation
Epic 9: CRM                         ← Depends on Product Catalogue
Epic 10: Warranty & Service         ← Depends on Product Master
Epic 11: Installments               ← Depends on Sales + Inventory
Epic 12: Reports & Analytics        ← Depends on Inventory Data
Epic 13: AI & Forecasting           ← Depends on Inventory History
```

---

## 3. Business Vision

DevSphere ERP's Inventory domain aspires to be the **most complete, extensible, and business-friendly product and inventory management system** available to small and medium enterprises in any commercial vertical.

The vision is built on three pillars:

**1. Universal Product Intelligence**
Every business sells or manages something. The Product Master must be capable of representing any product in any industry — from a refrigerator to a medical device, from a construction material to a packaged consumable — through configurable attributes, flexible categorisation, and rich metadata without requiring schema changes.

**2. Operational Accuracy**
Inventory inaccuracy is one of the most expensive operational problems a business can face — leading to stockouts, overstocking, write-offs, and poor customer experience. The Inventory Operations sub-domain must provide real-time, authoritative stock positions that every downstream module can trust.

**3. Foundation for Intelligence**
Raw inventory data must be structured so that future AI, forecasting, and analytics capabilities can be layered on top without redesign. Every stock movement, valuation event, and lifecycle transition must be recorded in a form that supports retrospective analysis and predictive modelling.

---

## 4. Business Goals

### 4.1 Primary Business Goals

| ID | Goal | Measurable Outcome |
| --- | --- | --- |
| BG-001 | Establish authoritative Product Master | All products across the business are managed in a single, structured catalogue |
| BG-002 | Provide real-time stock visibility | Authorised users can see current, available, and reserved stock at any moment |
| BG-003 | Support multi-warehouse operations | Stock is tracked independently per warehouse and transferable between locations |
| BG-004 | Enable accurate inventory valuation | The financial value of inventory is always derivable from recorded stock movements |
| BG-005 | Prevent revenue loss from stockouts | Low stock and reorder alerts enable proactive replenishment |
| BG-006 | Serve all commercial verticals | No industry-specific assumptions restrict the product model |
| BG-007 | Establish the downstream data contract | Purchase, Sales, Accounting, and other modules have a reliable inventory API |

### 4.2 Strategic Goals

| ID | Goal |
| --- | --- |
| SG-001 | Design inventory as a business domain, not a CRUD module |
| SG-002 | Enable future AI demand forecasting without architectural changes |
| SG-003 | Support future mobile, POS, and public API integrations through contract-stable interfaces |
| SG-004 | Provide the data foundation for financial reporting and compliance |
| SG-005 | Reduce inventory management time for operators by at least 60% compared to manual methods |

---

## 5. Business Scope

### 5.1 In Scope

**Product Master**
- Product creation, categorisation, and full lifecycle management
- Multi-level category and sub-category hierarchy
- Brand management
- Unit of measure (UOM) management including base and alternate units
- Product variants (by colour, size, weight, grade, or any custom attribute)
- Product attributes — structured, configurable, industry-agnostic
- Product images (primary, gallery)
- SKU management and barcode / QR code association
- Product types (stockable, service, consumable, asset)
- Product status lifecycle (draft, active, inactive, archived, discontinued)
- Custom fields per product type or category
- Internal notes and search keywords
- Tag management

**Inventory Operations**
- Opening stock recording
- Current stock tracking across all warehouses
- Available stock calculation (current minus reserved minus damaged)
- Reserved stock management
- Damaged and returned stock tracking
- Safety stock, minimum stock, and maximum stock thresholds
- Reorder level configuration and reorder suggestions
- Negative stock policy per company
- Inventory valuation (FIFO, Weighted Average Cost)
- Inventory snapshot capability

**Warehouse Management**
- Warehouse creation and configuration
- Multi-warehouse support per company
- Warehouse location management (zones/areas)
- Stock transfer between warehouses (two-step confirmation)
- Warehouse status management

**Stock Movement Ledger**
- Immutable recording of all stock-in and stock-out transactions
- Movement categorisation by source type
- Audit trail for every stock movement

**Inventory Intelligence**
- Low stock, out-of-stock, and overstock alert generation
- Reorder suggestion generation

**Master Data**
- Category, sub-category, brand, UOM, and attribute set governance
- Duplicate detection for codes and SKUs
- Bulk import and export of product master data

### 5.2 Industries Supported Without Modification

| Industry | Example Use Cases |
| --- | --- |
| Retail | Consumer goods, clothing, electronics |
| Wholesale | Bulk products, distribution |
| Trading | Import/export commodities |
| Construction | Building materials, cement, steel |
| Electrical | Wires, panels, switches, cables |
| Hardware | Tools, fasteners, fittings |
| Medical | Pharmaceuticals, medical devices, consumables |
| Sanitary | Plumbing, fittings, pipes |
| General Commerce | Any product-based business |
| Manufacturing (basic) | Bill-of-materials awareness without production scheduling |

---

## 6. Out of Scope

| Excluded Capability | Rationale / Future Epic |
| --- | --- |
| Purchase Order creation and management | Epic 6 — Purchase Management |
| Sales Order creation and management | Epic 7 — Sales Management |
| Invoice and payment processing | Epic 8 — Accounting |
| Customer management | Epic 9 — CRM |
| Warranty claim management | Epic 10 — Warranty & Service |
| Installment plans | Epic 11 — Installments |
| Manufacturing production scheduling | Future — Manufacturing Module |
| Bill of Materials (BOM) production | Future — Manufacturing Module |
| Point-of-Sale terminal operations | Future — POS Module |
| Physical stock counting (Cycle Count, Physical Count) | Defined here as Future capability |
| Inventory Freeze | Defined here as Future capability |
| Bin-level and Rack-level warehouse locations | Defined here as Future capability |
| Lot / Batch / Serial Number tracking | Future — Traceability Module |
| Expiry date management | Future — Traceability Module |
| Barcode label printing engine | Integration layer only; print formatting is Future |
| AI demand forecasting engine | Epic 13 — AI & Forecasting |
| Mobile application | Future — Mobile Module |
| Multi-currency inventory valuation | Future — International Module |
| Tax classification per product | Epic 8 — Accounting |
| Customer-facing product catalogue / storefront | Future — eCommerce Module |
| Branch Management (organisational hierarchy between Company and Warehouse) | Future — Branch Management Module; architectural readiness defined in §16.10 |
| Procurement metadata on Product Master (supplier, lead time, EOQ, shelf life, hazard) | Future — Purchase & Supply Chain Module; conceptual readiness defined in §14.16 |
| Multi-currency inventory valuation and exchange rate integration | Future — Accounting & International Module; conceptual readiness defined in §15.18 |

---

## 7. Business Terminology

| Term | Definition |
| --- | --- |
| **Product** | A distinct item that a company buys, sells, stores, or manages. The atomic unit of the Product Master. |
| **Product Master** | The authoritative catalogue of all products, their attributes, classifications, and metadata within a company. |
| **Variant** | A specific version of a product distinguished by one or more configurable attributes (e.g., colour, size). Each variant is a distinct stockable unit with its own SKU. |
| **SKU** | Stock Keeping Unit. A unique alphanumeric identifier assigned to a product or variant for inventory tracking. |
| **Barcode** | A machine-readable representation of a product code (EAN-13, UPC-A, Code 128, etc.). |
| **QR Code** | A two-dimensional barcode associated with a product for scanning and identification. |
| **UOM** | Unit of Measure. The standard unit in which a product is counted, sold, or purchased (e.g., piece, kg, litre, metre, box). |
| **Category** | A primary classification grouping of products (e.g., Electronics, Plumbing). |
| **Sub-Category** | A secondary classification within a Category. |
| **Brand** | The manufacturer or brand name associated with a product. |
| **Attribute** | A configurable product property describing a characteristic (e.g., colour, voltage, material, weight). |
| **Opening Stock** | The initial recorded quantity of a product at a warehouse at system go-live or first product introduction. |
| **Current Stock** | Total quantity of a product present at a warehouse as derived from the cumulative sum of all movements. |
| **Available Stock** | Current Stock minus Reserved Stock minus Damaged Stock. The quantity free for new commitments. |
| **Reserved Stock** | Quantity committed to an unfulfilled Sales Order or outbound transfer, not yet dispatched. |
| **Safety Stock** | A minimum buffer quantity that must always remain available to absorb supply delays. |
| **Minimum Stock** | The lowest acceptable quantity threshold, triggering an alert when breached. |
| **Maximum Stock** | The upper inventory limit to prevent overstocking. |
| **Reorder Level** | The stock quantity at which a replenishment action must be initiated. |
| **Damaged Stock** | Quantity recorded as damaged, excluded from Available Stock. |
| **Returned Stock** | Quantity returned from customers or vendors, pending inspection. |
| **Stock Ledger** | The immutable chronological record of all stock movements for a product at a warehouse. |
| **Inventory Adjustment** | A formal correction to recorded stock quantities, requiring a reason code and authorisation. |
| **Stock Transfer** | A movement of stock from one warehouse to another within the same company. |
| **Inventory Valuation** | The monetary value of on-hand inventory, calculated using a defined cost method (FIFO, WAC). |
| **Weighted Average Cost (WAC)** | Unit cost recalculated as a weighted average with each stock receipt. |
| **FIFO** | First In, First Out. The oldest stock cost is applied to the first units sold. |
| **Dead Stock** | Products with no stock movement over a defined period, indicating obsolescence risk. |
| **Fast Moving** | Products with high stock movement frequency. |
| **Slow Moving** | Products with infrequent stock movement, indicating low demand. |
| **Stock Aging** | Analysis of how long current stock has been held without movement. |
| **Warehouse** | A physical or logical storage location within which stock is managed. |
| **Warehouse Location** | A designated zone or area within a warehouse for organising physical stock. |
| **Bin** | (Future) The smallest discrete storage unit within a warehouse location. |
| **Rack** | (Future) A shelving structure within a warehouse location containing bins. |
| **Inventory Snapshot** | A point-in-time record of all stock positions, used for reporting and reconciliation. |
| **Negative Stock Policy** | A company-level configuration determining whether stock quantities may go below zero. |
| **Product Type** | A classification that determines the inventory behaviour of a product. |
| **Tenant** | A company using DevSphere ERP. All inventory data is scoped to a single tenant. |
| **Branch** | (Future) An organisational subdivision of a Company, positioned between the Company and its Warehouses in the operational hierarchy. Enables a business to manage multiple operational locations (e.g., city branches, regional offices) independently under one company. Inventory architecture is Branch-aware by design. |
| **Base Currency** | The primary currency in which a company records all financial transactions. Inventory valuation in Epic 5 is denominated in the Base Currency as configured in the Company profile (Epic 3). |
| **Transaction Currency** | (Future) A currency other than the Base Currency in which a specific purchase or sale may be recorded. Requires exchange rate integration via the Accounting module. |
| **Reporting Currency** | (Future) A secondary currency used for consolidated financial reporting, particularly relevant for international or multi-branch operations. |
| **Preferred Supplier** | (Future) The designated primary vendor for sourcing a specific product, stored as procurement metadata on the Product Master. |
| **Lead Time** | (Future) The anticipated duration between placing a purchase order and receiving stock into the warehouse. Stored per product/supplier for use in reorder planning. |
| **Economic Order Quantity (EOQ)** | (Future) The mathematically optimal order quantity that minimises total inventory holding and ordering costs for a given product. Calculated and stored as procurement advisory metadata. |
| **Purchase UOM** | (Future) The unit of measure in which a product is procured from a supplier, which may differ from the Base UOM used for stock tracking. |
| **Sales UOM** | (Future) The unit of measure in which a product is sold to customers, which may differ from the Base UOM. |
| **Storage Conditions** | (Future) Environmental requirements for a product during warehousing (e.g., temperature-controlled, humidity-controlled, shaded). Defined on the Product Master. |
| **Hazard Classification** | (Future) A product's classification under hazardous material standards (e.g., flammable, corrosive, toxic), governing storage and handling requirements. |

---

## 8. Domain Philosophy

### 8.1 Inventory Is a Business Domain

Inventory management is not a data entry or cataloguing exercise. It is the intersection of commercial intent, physical reality, and financial value. The Inventory domain answers three fundamental business questions:

1. **What do we have?** — Product Master and stock positions
2. **Where do we have it?** — Warehouse and location management
3. **What is it worth?** — Inventory valuation and financial reporting

### 8.2 Separation of Conceptual Responsibilities

```
┌─────────────────────────────────────────────────┐
│              INVENTORY DOMAIN                   │
│                                                 │
│  ┌──────────────┐    ┌──────────────────────┐   │
│  │ PRODUCT      │    │ INVENTORY OPERATIONS │   │
│  │ MASTER       │    │ (Stock Positions &   │   │
│  │ (What exists)│    │  Movements)          │   │
│  └──────────────┘    └──────────────────────┘   │
│                                                 │
│  ┌──────────────┐    ┌──────────────────────┐   │
│  │ WAREHOUSE    │    │ INVENTORY            │   │
│  │ MANAGEMENT   │    │ INTELLIGENCE         │   │
│  │ (Where it is)│    │ (Alerts & Rules)     │   │
│  └──────────────┘    └──────────────────────┘   │
│                                                 │
│  ┌──────────────────────────────────────────┐   │
│  │          INVENTORY ANALYTICS             │   │
│  │     (Trends, KPIs, Forecasting Data)     │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

### 8.3 Industry Neutrality

This domain must never encode assumptions about a specific industry. Attributes, categories, units of measure, and product types are all configurable — never hardcoded. A company selling refrigerators and a company selling construction steel must both operate within the same data model without compromise.

### 8.4 Data Integrity Over Convenience

Stock accuracy is non-negotiable:
- All stock changes are recorded as movements, never silent overwrites
- Adjustments require authorisation and reason codes
- Deletions of inventory records are never permitted; only archival is allowed
- Every state change is traceable through the domain event system

---

## 9. Domain Boundaries

### 9.1 What the Inventory Domain Owns

| Owned Entity | Notes |
| --- | --- |
| Product | Complete product lifecycle |
| Product Variant | Variant creation and management |
| Category / Sub-Category | Product classification hierarchy |
| Brand | Brand registry |
| Unit of Measure | UOM catalogue and conversions |
| Attribute / Attribute Set | Configurable product properties |
| Product Image | Product media assets |
| Stock Position | Per-product, per-warehouse stock levels |
| Stock Movement | All ledger entries for stock changes |
| Inventory Adjustment | Formal corrections to stock quantities |
| Warehouse | Warehouse registry and configuration |
| Warehouse Location | Sub-areas within a warehouse |
| Stock Transfer | Inter-warehouse movements |
| Inventory Snapshot | Point-in-time stock records |
| Reorder Rule | Per-product replenishment configuration |
| Low Stock Alert | Generated alerts for threshold breaches |

### 9.2 What the Inventory Domain Consumes

| Source Domain | What Is Consumed |
| --- | --- |
| Authentication (Epic 2) | User identity for audit trail attribution |
| Companies (Epic 3) | company_id for tenant isolation |
| Users & Roles (Epic 4) | Permission checks, role context |

### 9.3 What Other Domains Consume from Inventory

| Consuming Domain | What Is Consumed |
| --- | --- |
| Purchase (Epic 6) | Product list, warehouse list, stock receipt events |
| Sales (Epic 7) | Product list, available stock, stock reservation events |
| Accounting (Epic 8) | Inventory valuation, stock movement costs |
| CRM (Epic 9) | Product catalogue reference |
| Warranty (Epic 10) | Product and variant identity |
| Reports (Epic 12) | All inventory data for reporting |
| AI (Epic 13) | Stock history for forecasting |

---

## 10. Bounded Context

The Inventory domain forms a **distinct Bounded Context** within the DevSphere ERP modular monolith. It publishes a stable, version-controlled internal API and raises domain events that other bounded contexts consume.

### 10.1 Context Map

```
[Authentication BC] ──identity──▶ [Inventory BC]
[Companies BC] ──tenant scope──▶   [Inventory BC]
[Users & Roles BC] ──permissions▶  [Inventory BC]
                                        │
                          ┌─────────────┴──────────────┐
                          │     INVENTORY BC            │
                          │  ─ Product Master           │
                          │  ─ Stock Positions          │
                          │  ─ Warehouse Registry       │
                          │  ─ Stock Ledger             │
                          │  ─ Inventory Intelligence   │
                          └─────────────┬──────────────┘
                                        │ publishes events & APIs
              ┌─────────────────────────┼────────────────────────┐
     [Purchase BC]            [Sales BC]             [Accounting BC]
              └────[CRM BC]────[Warranty BC]────[Reports BC]──────┘
```

### 10.2 Context Integration Principles

- All cross-context communication occurs through **published domain events** or **query APIs** — never direct table access
- The Inventory domain is the **single source of truth** for product and stock data
- Other bounded contexts hold only **references** (product_id, warehouse_id) — never copies of inventory master data
- The Inventory domain never imports business logic from downstream domains

---

## 11. Stakeholders

| Stakeholder | Primary Concern |
| --- | --- |
| **Company Owner** | Inventory value, profitability, stockout risk |
| **Company Administrator** | Product catalogue setup, warehouse configuration |
| **Inventory Manager** | Stock accuracy, alerts, adjustments |
| **Warehouse Manager** | Transfer management, warehouse organisation |
| **Store Keeper** | Stock receipts, issues, physical handling |
| **Purchase User** | Product master reference, reorder suggestions |
| **Sales User** | Available stock, product catalogue |
| **Accountant** | Inventory valuation, write-offs |
| **Auditor** | Audit trail, stock reconciliation |
| **DevSphere Platform Admin** | System health, tenant configuration |
| **IT Administrator** | Integration, import/export, API access |

---

## 12. User Personas

### 12.1 Super Admin (Platform Level)

Platform operator. Cross-tenant visibility for support only. Cannot manipulate business inventory data of any tenant. Can enable/disable feature flags per tenant.

---

### 12.2 Company Owner

Principal business operator. Needs: complete visibility of all inventory across all warehouses; inventory valuation at any time; business intelligence (fast-moving, slow-moving, dead stock); approval authority for significant adjustments.

---

### 12.3 Company Admin

Trusted operational manager. Needs: configure product catalogue (categories, brands, UOM, attributes); create and manage warehouses; manage bulk product imports; define RBAC boundaries.

---

### 12.4 Inventory Manager

Primary owner of inventory accuracy. Needs: real-time stock dashboard; low stock and reorder alerts; adjustment authorisation; variance reports; stock aging and dead stock identification.

---

### 12.5 Warehouse Manager

Responsible for physical warehouse operations. Needs: initiate and confirm stock transfers; manage warehouse locations; receive goods into a specific warehouse; track damaged and returned stock.

---

### 12.6 Store Keeper

On-the-ground warehouse operative. Needs: scan barcode/QR to look up products; record stock received; record stock issued; report damaged or missing items.

---

### 12.7 Purchase User

Procurement specialist. Needs: full product catalogue when creating POs; real-time stock levels to avoid over-ordering; reorder suggestions from the system; confirmation of goods received.

---

### 12.8 Sales User

Sales representative. Needs: available stock visibility per product per warehouse; product details (images, attributes, UOM) for quotations; stock reservation confirmation; restock notifications.

---

### 12.9 Auditor

Internal or external reviewer. Needs: complete read-only access to all inventory data; full audit trail of every stock movement and adjustment; inventory valuation history. **No write access.**

---

### 12.10 Read-Only User (Viewer)

Any user with viewing rights only. Can browse the product catalogue and view stock levels and reports.

---

## 13. Business Capabilities

### 13.1 Capability Map

| Capability Group | Capabilities |
| --- | --- |
| **Product Master Management** | Create/manage products, variants, categories, brands, UOM, attributes, images, barcodes, tags |
| **Stock Position Management** | Real-time stock tracking, opening stock, available/reserved calculations |
| **Stock Movement Control** | Inbound, outbound, adjustment, transfer — all as ledger events |
| **Warehouse Operations** | Multi-warehouse management, location tracking, inter-warehouse transfers |
| **Inventory Intelligence** | Threshold monitoring, alert generation, reorder suggestion |
| **Inventory Valuation** | WAC and FIFO cost calculations, valuation reports |
| **Master Data Governance** | Duplicate prevention, category standards, UOM management |
| **Audit & Compliance** | Full audit trail, adjustment history, user attribution |
| **Reporting & Analytics** | Standard inventory reports, KPI dashboards |
| **Search & Discovery** | Barcode, SKU, keyword, advanced filter-based product discovery |
| **Import & Export** | Bulk product import, stock import, catalogue export |
| **Notifications & Alerts** | Low stock, out of stock, overstock, reorder, event notifications |
| **Integration Surface** | Barcode/QR scanner input, label printer output, future POS and API |

### 13.2 Capability Maturity in Epic 5

| Capability | Status |
| --- | --- |
| Product Master | Full implementation |
| Stock Position Management | Full implementation |
| Warehouse Management | Full (without Bin/Rack) |
| Inventory Valuation | Full (WAC + FIFO) |
| Inventory Intelligence | Basic alerts and reorder logic |
| Audit Trail | Full implementation |
| Search & Discovery | Full implementation |
| Import/Export | Excel and CSV |
| Reporting | Standard reports |
| AI Readiness | Data foundation only |
| Physical Count / Freeze / Bin-Rack | Future |

---

## 14. Product Master

### 14.1 Overview

The Product Master is the authoritative catalogue of all items a company buys, sells, stores, or tracks. It is a shared reference domain — every other module that references a product must resolve it through the Product Master.

### 14.2 Products

**Core Product Properties**:

| Property | Description |
| --- | --- |
| Product Name | Primary business name |
| Product Code | Unique internal reference code |
| SKU | Unique Stock Keeping Unit identifier |
| Product Type | Classification that determines inventory behaviour |
| Category | Primary classification |
| Sub-Category | Secondary classification |
| Brand | Associated manufacturer or brand |
| Base UOM | Default unit for stock tracking |
| Description | Rich text description |
| Internal Notes | Private notes for authorised users |
| Tags | Flexible labels for filtering |
| Search Keywords | Additional discovery terms |
| Status | Current lifecycle status |
| Barcode | Associated barcode value(s) |
| QR Code | Associated QR code value(s) |
| Custom Fields | Configurable additional fields |
| Audit Fields | Created by, updated by, timestamps, soft-delete flag |

### 14.3 Product Types

| Product Type | Stock Tracked | Affects Inventory |
| --- | --- | --- |
| **Stockable** | Yes | Yes |
| **Service** | No | No |
| **Consumable** | Optional | Optional |
| **Asset** | Yes | Separately |

### 14.4 Product Status

| Status | Can Be Sold | Can Be Purchased | In Stock Reports |
| --- | --- | --- | --- |
| **Draft** | No | No | No |
| **Active** | Yes | Yes | Yes |
| **Inactive** | No | No | Yes (historical) |
| **Archived** | No | No | Historical only |
| **Discontinued** | No | No | Historical only |

### 14.5 Categories and Sub-Categories

**Hierarchy**: Category (Level 1) → Sub-Category (Level 2) → (Further nesting: Future)

- A product must belong to exactly one category; sub-category assignment is optional
- Categories are tenant-scoped
- Inactive categories may not be assigned to new products
- Category deactivation is blocked if Active products are assigned to it

### 14.6 Brands

- Brand assignment to a product is optional
- Inactive brands may not be assigned to new products
- Brands are tenant-scoped

### 14.7 Units of Measure

| UOM Type | Examples |
| --- | --- |
| Count | Piece (PCS), Box (BOX), Pack (PACK), Dozen (DZN) |
| Weight | Kilogram (KG), Gram (G), Tonne (TON) |
| Volume | Litre (L), Millilitre (ML) |
| Length | Metre (M), Centimetre (CM), Foot (FT) |
| Area | Square Metre (SQM) |
| Time | Hour (HR), Day (DAY) — for service products |

**UOM Conversion**: Each product has a Base UOM. Alternate UOM (e.g., purchase in cartons, sell in pieces) may be configured with a conversion factor.

### 14.8 Variants

A **Product Variant** is a specific version of a product differing in one or more attribute values. Example: Fan (product) → White 36", White 48", Black 36" (variants). Each variant has an independent SKU and stock position.

**Business Rules**:
- If a product has variants, stock is tracked at the variant level, not the product level
- Variants share the parent product's category and brand
- Each variant has its own barcode(s) and images (optional overrides)

### 14.9 Attributes

**Attribute Types**:

| Type | Example |
| --- | --- |
| Text | Material: "Stainless Steel" |
| Number | Weight: 1.5 |
| Boolean | Waterproof: Yes |
| Dropdown | Voltage: "220V" |
| Multi-Select | Compatible OS: ["Android", "iOS"] |
| Colour | Colour: Blue |

**Attribute Sets**: A bundle of attributes applied to a product type or category for consistent data capture.

### 14.10 Product Images

- Primary image and gallery (up to 10 images per product)
- Variants may have distinct images
- Stored in company's S3-compatible bucket (consistent with Epic 3 patterns)
- Image formats: JPG, PNG, WEBP; max 10 MB per image

### 14.11 Barcode and QR Code

- Each product/variant may have one or more associated barcodes or QR codes
- Barcode uniqueness enforced within the company
- Supported formats: EAN-13, EAN-8, UPC-A, UPC-E, Code 128, Code 39

### 14.12 Custom Fields

- Defined per product type or per category
- Field types: text, number, date, boolean, dropdown
- Included in product export

### 14.13 Internal Notes

- Private rich-text field visible only to authorised users
- Timestamped and append-only (historical notes retained)

### 14.14 Search Keywords

- Synonyms and alternative terms for improved search recall
- Not displayed to end users
- Example: Product "MCB" → Keywords "circuit breaker, miniature circuit breaker, fuse"

### 14.15 Tags

- User-defined labels applied to any product
- Enable cross-category grouping and filtering
- Tenant-scoped
- Example uses: "New Arrival", "Clearance", "Import Item", "Flagship"

### 14.16 Procurement Metadata Readiness (Future)

*Capability defined architecturally; implementation deferred to the Purchase and Supply Chain modules (Epic 6 and beyond). The Product Master data model is designed to accommodate these fields without structural change when the relevant Epics are activated.*

The following procurement metadata properties are reserved as first-class Product Master extensions. They are not implemented in Epic 5 but are documented here to ensure the Product Master architecture can accommodate them without redesign:

| Property | Description | Future Owner |
| --- | --- | --- |
| **Preferred Supplier** | The primary vendor from whom this product is typically purchased | Epic 6 — Purchase |
| **Supplier Product Code** | The supplier's own reference code for this product | Epic 6 — Purchase |
| **Lead Time** | Expected days from purchase order placement to warehouse receipt | Epic 6 — Purchase |
| **Purchase UOM** | The unit in which this product is ordered from suppliers (may differ from Base UOM) | Epic 6 — Purchase |
| **Sales UOM** | The unit in which this product is sold to customers (may differ from Base UOM) | Epic 7 — Sales |
| **Reorder Quantity** | The standard quantity to order when the Reorder Level is triggered | Epic 6 — Purchase |
| **Reorder Point** | An alternate product-level reorder threshold (complements the warehouse-level Reorder Level) | Epic 6 — Purchase |
| **Economic Order Quantity (EOQ)** | The calculated optimal order quantity based on demand, ordering cost, and holding cost | Epic 13 — AI |
| **Tax Category** | The tax classification governing purchase and sales tax treatment for this product | Epic 8 — Accounting |
| **Storage Conditions** | Environmental requirements for warehousing (temperature, humidity, light) | Epic 5 Phase 2 |
| **Shelf Life** | Maximum duration a product may be stored before it is no longer fit for sale (in days) | Future — Traceability Module |
| **Hazard Classification** | Hazardous material designation governing handling, storage, and transport | Future — Compliance Module |
| **Country of Origin** | The country in which the product was manufactured or produced | Future — International Module |

**Governance Principle**: Procurement metadata belongs to the Product Master SSOT. The Purchase, Sales, and Accounting modules will read this data from the Inventory domain — they will not maintain their own copies of product-level procurement properties.

---

## 15. Inventory Operations

### 15.1 Overview

Inventory Operations governs all aspects of stock position management and movement recording. **Core Principle**: Stock quantity is never directly modified. All changes are recorded as **Stock Movements** in an immutable ledger. The current stock position is always derived from the cumulative sum of all movements.

### 15.2 Opening Stock

Initial stock quantity for a product at a warehouse when a company goes live or a new product is introduced.

- Requires: product, warehouse, quantity (> 0), unit cost, reference date
- One-time event per product per warehouse at system go-live
- Recorded as movement type: OPENING
- May only be recorded by Inventory Manager, Admin, or Owner

### 15.3 Current Stock

**Formula**:
```
Current Stock = Opening Stock + All Stock-In Movements − All Stock-Out Movements
```

- Calculated value — derived from ledger, not stored as a static field
- Available at: company level (all warehouses), warehouse level, variant level
- Real-time — reflects the most recent confirmed movement

### 15.4 Available Stock

```
Available Stock = Current Stock − Reserved Stock − Damaged Stock
```

- This is the operative quantity for sales order acceptance
- Out-of-stock alerts trigger when Available Stock reaches zero

### 15.5 Reserved Stock

- Reserved when a Sales Order is confirmed
- Released if the Sales Order is cancelled
- Converted to a stock-out movement when the order is dispatched
- Included in Current Stock but excluded from Available Stock

### 15.6 Damaged Stock

- Recorded through a formal Inventory Adjustment with reason code "Damage"
- Excluded from Available Stock
- Can be: repaired and reclassified, sold at discount, or written off
- All damage events logged in audit trail

### 15.7 Returned Stock

- Recorded through a Return Movement event
- Initially held in "Pending Inspection" state
- After inspection: reclassified as good stock (increases current stock) or confirmed as damaged

### 15.8 Safety Stock

- Set per product, optionally per warehouse
- When Available Stock falls below Safety Stock, a "Safety Stock Breach" alert is generated
- Advisory threshold only — does not block transactions

### 15.9 Minimum Stock

- Harder threshold than Safety Stock (Safety Stock ≥ Minimum Stock in a well-configured system)
- Breach triggers "Minimum Stock Breach" alert

### 15.10 Maximum Stock

- When exceeded, triggers an "Overstock" alert
- Used by Purchase module to prevent over-ordering

### 15.11 Reorder Level

- When Available Stock falls to or below this level, a Reorder Suggestion is generated
- Suggests replenishment quantity up to Maximum Stock

### 15.12 Negative Stock Policy

| Setting | Behaviour |
| --- | --- |
| **Strict (Recommended)** | System prevents any transaction causing negative stock |
| **Allow with Warning** | System warns but allows the transaction |
| **Allow Silently** | System allows negative stock without warning (not recommended) |

Default: Strict. Changing to a permissive mode requires admin confirmation.

### 15.13 Inventory Freeze (Future)

*Capability defined; implementation deferred.* Locks all stock at a warehouse during a count or audit. No inbound/outbound movements or adjustments permitted during freeze.

### 15.14 Physical Count (Future)

*Capability defined; implementation deferred.* Formal reconciliation of physical stock against system quantities. Discrepancies resolved through authorised adjustments.

### 15.15 Cycle Count (Future)

*Capability defined; implementation deferred.* Rolling partial-count process where subsets of inventory are counted on a rotating schedule.

### 15.16 Inventory Valuation

**Supported Cost Methods**:

| Method | Description | Best For |
| --- | --- | --- |
| **Weighted Average Cost (WAC)** | Unit cost recalculated as weighted average with each receipt | Most general-purpose businesses |
| **FIFO** | Oldest stock cost applied to sales first | Perishables, time-sensitive goods |

- Each company selects one method at configuration time
- The method applies consistently to all products and cannot be changed mid-period without a formal revaluation event
- Inventory valuation feeds into the Accounting module's balance sheet

### 15.17 Inventory Snapshot

- Point-in-time record of all stock positions across all products, variants, and warehouses
- Generated on demand or on a scheduled basis
- Immutable once created
- Includes: product, variant, warehouse, quantity, unit cost, total value, timestamp

### 15.18 Multi-Currency Readiness (Future)

*Epic 5 does NOT implement multi-currency inventory valuation. The Inventory domain is, however, architecturally designed to remain fully compatible with future multi-currency requirements introduced by the Accounting module (Epic 8) and the International module. The following currency concepts are documented here to define the architectural contract.*

**Currency Model for the Inventory Domain**:

| Currency Concept | Epic 5 Status | Future Behaviour |
| --- | --- | --- |
| **Base Currency** | Active — all valuations recorded in base currency | Set in the Company profile (Epic 3); inventory values denominated in this currency in Epic 5 |
| **Transaction Currency** | Not active | Future: enables purchase and sales transactions to be recorded in a foreign currency; unit cost converted to base currency at the point of stock receipt |
| **Inventory Valuation Currency** | Always Base Currency in Epic 5 | Future: can be reported in any enabled currency via exchange rate conversion |
| **Reporting Currency** | Not active | Future: a secondary currency for consolidated financial reporting across branches or entities |
| **Exchange Rate Integration** | Not active | Future: managed by the Accounting module; Inventory domain will consume exchange rates as a dependency, never own them |

**Architectural Commitments**:
- All monetary values in the Inventory domain (unit cost, valuation totals) are stored alongside the currency code identifier, even in Epic 5 — enabling future multi-currency reporting without schema migration
- The Inventory domain will never own or define exchange rates; it will consume them from the Accounting module when multi-currency is activated
- Inventory Valuation reports must remain queryable by currency in future releases without requiring structural changes to the stock ledger

---

## 16. Warehouse Management

### 16.1 Overview

Warehouse Management governs the physical and logical structure within which inventory is held.

### 16.2 Warehouses

| Property | Description |
| --- | --- |
| Name | Human-readable name |
| Code | Unique short code (e.g., WH-01, MAIN) |
| Type | Physical location type |
| Address | Physical address |
| Contact | Responsible contact person and details |
| Status | Active, Inactive, Archived |
| Is Default | Whether this is the default for new transactions |
| Notes | Internal operational notes |

**Warehouse Types**:

| Type | Description |
| --- | --- |
| **Main** | Primary storage and fulfilment warehouse |
| **Showroom** | Display or retail-adjacent stock location |
| **Transit** | Intermediate location for in-transit stock |
| **Return** | Dedicated area for returned goods pending inspection |
| **Damage** | Segregated area for confirmed damaged goods |

### 16.3 Multi-Warehouse Support

- A company may have an unlimited number of warehouses
- Stock positions are maintained independently per warehouse
- Reports can aggregate across all warehouses or filter to a specific one
- A default warehouse may be set per company or per user session

### 16.4 Warehouse Assignment

- Every stock movement is assigned to a specific warehouse
- Every purchase receipt is received into a specific warehouse
- Every sales dispatch deducts from a specific warehouse

### 16.5 Warehouse Locations

- Named zones/areas within a warehouse (e.g., Zone A, Ground Floor, Cold Storage)
- Properties: name, code, warehouse reference, capacity indicator (optional), status
- Location assignment is optional — strict bin-level tracking is a Future capability

### 16.6 Bin Support (Future)

*Defined; implementation deferred.* Smallest discrete physical storage units within a warehouse location.

### 16.7 Rack Support (Future)

*Defined; implementation deferred.* Shelving or racking structures within a warehouse location.

### 16.8 Stock Transfer

**Two-Step Transfer Workflow**:

```
[Initiate Transfer] → [In Transit] → [Confirm Receipt] → [Completed]
                           ↓
                    [Cancel Transfer]  (only while In Transit or Draft)
```

- Source stock is decremented at dispatch (In Transit)
- Destination stock is incremented only upon confirmed receipt
- In-transit quantity is visible as "In Transit" stock — neither at source nor destination
- Transfers are reversible only while in "Draft" status

### 16.9 Warehouse Status

| Status | Accepts Inbound | Allows Outbound |
| --- | --- | --- |
| **Active** | Yes | Yes |
| **Inactive** | No | No |
| **Archived** | No | No |

- Inactivating a warehouse with current stock generates a warning but is permitted
- Archiving a warehouse with non-zero stock is blocked

### 16.10 Branch Hierarchy Readiness (Future)

*Branch Management is NOT implemented in Epic 5. This section documents the architectural intent to ensure that when Branch Management is introduced as a future Epic, the Inventory domain requires no redesign to accommodate it.*

**Current Architecture (Epic 5)**:

```
Company (Tenant)
    └── Warehouse(s)
            └── Stock Positions / Movements
```

**Future Architecture (Post-Branch Epic)**:

```
Company (Tenant)
    └── Branch (Operational Business Unit)
            └── Warehouse(s)
                    └── Stock Positions / Movements
```

**Architectural Readiness Principles**:

The Inventory domain is designed to be Branch-aware without implementing Branch in Epic 5. The following principles are established now:

| Principle | Implementation in Epic 5 | Behaviour When Branch is Introduced |
| --- | --- | --- |
| **Warehouse ownership** | Warehouse is owned by company_id | A branch_id field is reserved on the Warehouse entity; null means "no branch assignment" |
| **Stock reporting scope** | Reports filter by company or warehouse | Reports will additionally support filtering by branch (group of warehouses) |
| **Transfer boundaries** | Transfers are unrestricted within a company | Future: inter-branch transfer approval rules may be enforced |
| **Access control** | Warehouse access is role-based (company level) | Future: branch-scoped roles will be addable without breaking company-level roles |
| **Data isolation** | All data scoped to company_id | Future: branch_id will provide a sub-tenant isolation layer without replacing company_id |

**Non-Goals for Epic 5 (held for Branch Epic)**:
- Branch creation, management, and lifecycle
- Branch-level P&L and valuation reporting
- Warehouse-to-branch assignment UI
- Branch Manager role and branch-scoped permissions
- Inter-branch stock transfer approval workflows
- Branch-level reorder policies

**Compatibility Guarantee**: Any implementation of Branch Management in a future Epic must not require alteration of the stock ledger schema, the product master schema, or any existing domain events published by the Inventory domain in Epic 5.

---

## 17. Product Lifecycle

```
                   ┌─────────┐
                   │  DRAFT  │◄──────── Created by operator
                   └────┬────┘
                        │ Activated
                        ▼
                   ┌─────────┐
           ┌───────│  ACTIVE │──────────────────┐
           │       └────┬────┘                  │
           │            │ Disabled              │ Permanently stopped
           │            ▼                       ▼
           │       ┌──────────┐          ┌──────────────┐
           │       │ INACTIVE │          │ DISCONTINUED │
           │       └────┬─────┘          └──────┬───────┘
           │            │ Reactivated            │
           │            └──────────────┐         │
           └────────────────────────▶ [ACTIVE]   │
                                                 │
                   ┌──────────┐                  │
                   │ ARCHIVED │◄─────────────────┘
                   └──────────┘  (Terminal state)
```

**Transition Rules**:
- **Draft → Active**: Mandatory fields complete (Name, Code, SKU, Category, UOM, Product Type)
- **Active → Inactive**: No open order lines referencing this product
- **Inactive → Active**: Re-validation of mandatory fields
- **Any → Archived**: Must be Inactive or Discontinued first; terminal state — cannot be reversed
- **Archived → Any**: Not permitted

---

## 18. Stock Lifecycle

| State | Description |
| --- | --- |
| **On Hand** | Total physical quantity at a warehouse (including reserved and damaged) |
| **Available** | On Hand minus Reserved minus Damaged |
| **Reserved** | Committed to an order, not yet dispatched |
| **In Transit** | Dispatched from source; not yet received at destination |
| **Damaged** | Physically present but unavailable for sale |
| **Returned — Pending** | Returned goods awaiting inspection decision |

```
[OPENING STOCK] ──► [CURRENT STOCK]
                           │
          ┌────────────────┼────────────────┐
     [Purchase         [Adjustment     [Return
      Receipt]          +/-]           Inbound]
                           │
                    [CURRENT STOCK]
                           │
                 ┌─────────┴─────────┐
            [RESERVED]          [AVAILABLE]
                 │                   │
           [DISPATCHED]         [TRANSFERRED / SOLD]
                 │
           [STOCK-OUT Ledger Entry]
```

---

## 19. Inventory Lifecycle

```
Phase 1: SETUP
  └── Configure warehouses, categories, brands, UOM, attributes

Phase 2: CATALOGUE POPULATION
  └── Create products, define variants, assign attributes, upload images

Phase 3: OPENING STOCK
  └── Record initial stock positions per product per warehouse

Phase 4: OPERATIONAL
  └── Day-to-day stock movements: receipts, issues, adjustments, transfers

Phase 5: OPTIMISATION
  └── Alert management, reorder suggestions, dead stock reviews

Phase 6: REPORTING & AUDIT
  └── Periodic valuation, snapshot, reconciliation, compliance review
```

All six phases may be active simultaneously for different products within the same company.

---

## 20. Business Workflows

### 20.1 Product Creation Workflow

```
[Create product in Draft]
        │
[Complete mandatory fields: Name, Code, SKU, Category, UOM, Type]
        │
[Add optional fields: Brand, Description, Images, Barcode, Tags, Attributes]
        │
[Define Variants (if applicable)]
        │
[Activate Product]
        │
[ProductCreated + ProductActivated events published]
        │
[Product available for inventory and transactions]
```

### 20.2 Opening Stock Workflow

```
[Select product + warehouse]
        │
[Enter opening quantity, unit cost, reference date]
        │
[System validates: product active, warehouse active, qty > 0]
        │
[Opening stock movement created in ledger]
        │
[StockIncreased event published (movement_type = OPENING)]
        │
[Stock position updated in real time]
```

### 20.3 Generic Stock Movement Workflow

```
[Triggering Action: Purchase Receipt / Sales Dispatch / Adjustment / Transfer]
        │
[Inventory domain receives movement request]
        │
[Validation: product active, warehouse active, qty valid, policy check]
        │
[Ledger entry created (immutable)]
        │
[Stock position recalculated + valuation updated]
        │
[Domain event published: StockIncreased / StockReduced / StockAdjusted]
        │
[Alert engine evaluates thresholds]
        │
[Notifications triggered if thresholds breached]
```

### 20.4 Inventory Adjustment Workflow

```
[User identifies discrepancy]
        │
[Initiates Adjustment: product, warehouse, delta quantity or new quantity]
        │
[Selects Reason Code: Damage / Theft / Count Correction / Write-Off / Other]
        │
[Enters notes / reference document]
        │
[If approval enabled: submitted → Approver reviews → Approved / Rejected]
        │
[If approved: ledger entry created, stock position updated]
        │
[StockAdjusted event published]
        │
[Audit trail entry: old quantity, new quantity, reason, approver]
```

### 20.5 Warehouse Transfer Workflow

```
[Warehouse Manager initiates transfer]
        │
[Select: Source Warehouse, Destination Warehouse, Product, Quantity]
        │
[System validates: source has sufficient Available Stock]
        │
[Transfer created — In Transit status]
        │
[Source warehouse decremented (StockReduced — Transfer Out)]
        │
[Physical goods moved]
        │
[Receiving operator confirms receipt]
        │
[Destination warehouse incremented (StockIncreased — Transfer In)]
        │
[Transfer marked Completed]
        │
[StockTransferred event published]
```

### 20.6 Inventory Audit Workflow

```
[Auditor requests inventory snapshot]
        │
[System generates point-in-time snapshot]
        │
[Auditor reviews stock ledger: movements, adjustments, transfers]
        │
[Auditor exports audit trail for external review]
        │
[Auditor flags discrepancies]
        │
[Inventory Manager investigates; initiates adjustments if required]
        │
[Reconciliation report generated and archived]
```

---

## 21. Functional Requirements

### 21.1 Product Master

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-PM-001 | System MUST allow authorised users to create products with mandatory fields enforced | P1 |
| FR-PM-002 | System MUST enforce unique Product Code and SKU per company | P1 |
| FR-PM-003 | System MUST support multi-level product categorisation (Category → Sub-Category) | P1 |
| FR-PM-004 | System MUST allow unlimited product variants, each with an independent SKU | P1 |
| FR-PM-005 | System MUST support configurable product attributes and attribute sets | P1 |
| FR-PM-006 | System MUST support at least five UOM types (count, weight, volume, length, area) | P1 |
| FR-PM-007 | System MUST associate barcodes and QR codes with products and variants | P1 |
| FR-PM-008 | System MUST enforce barcode uniqueness within a company | P1 |
| FR-PM-009 | System MUST support four product types (Stockable, Service, Consumable, Asset) | P1 |
| FR-PM-010 | System MUST manage product lifecycle through defined status transitions | P1 |
| FR-PM-011 | System MUST prevent deletion of products with stock history; archival only | P1 |
| FR-PM-012 | System MUST support custom fields per product type and per category | P2 |
| FR-PM-013 | System MUST allow internal notes to be added to any product | P2 |
| FR-PM-014 | System MUST support product image upload (primary + gallery) | P2 |
| FR-PM-015 | System MUST support tag assignment and tag-based filtering | P2 |
| FR-PM-016 | System MUST support search keyword configuration per product | P2 |
| FR-PM-017 | System MUST support UOM conversion between base and alternate UOM | P2 |
| FR-PM-018 | System MUST support brand creation, assignment, and management | P2 |

### 21.2 Inventory Operations

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-IO-001 | System MUST allow recording of opening stock per product per warehouse | P1 |
| FR-IO-002 | System MUST calculate and display current stock in real time | P1 |
| FR-IO-003 | System MUST calculate available stock (current minus reserved minus damaged) | P1 |
| FR-IO-004 | System MUST maintain separate reserved stock quantity per product per warehouse | P1 |
| FR-IO-005 | System MUST track damaged stock as a distinct quantity | P1 |
| FR-IO-006 | System MUST track returned stock in a pending inspection state | P1 |
| FR-IO-007 | System MUST support safety stock, minimum stock, and maximum stock thresholds | P1 |
| FR-IO-008 | System MUST support configurable reorder level per product | P1 |
| FR-IO-009 | System MUST enforce the company's negative stock policy on all movements | P1 |
| FR-IO-010 | System MUST record all stock changes as immutable ledger entries | P1 |
| FR-IO-011 | System MUST support inventory valuation using WAC and FIFO methods | P1 |
| FR-IO-012 | System MUST support inventory adjustment with reason code and optional approver | P1 |
| FR-IO-013 | System MUST trigger alerts when stock falls below defined thresholds | P1 |
| FR-IO-014 | System MUST generate reorder suggestions when stock reaches the reorder level | P1 |
| FR-IO-015 | System MUST allow generation of inventory snapshots on demand | P2 |

### 21.3 Warehouse Management

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-WM-001 | System MUST allow a company to create and manage multiple warehouses | P1 |
| FR-WM-002 | System MUST maintain independent stock positions per product per warehouse | P1 |
| FR-WM-003 | System MUST support stock transfer between warehouses with two-step confirmation | P1 |
| FR-WM-004 | System MUST track in-transit stock during warehouse transfer | P1 |
| FR-WM-005 | System MUST enforce warehouse status constraints on transactions | P1 |
| FR-WM-006 | System MUST prevent archival of a warehouse with non-zero current stock | P1 |
| FR-WM-007 | System MUST support warehouse location management within each warehouse | P2 |
| FR-WM-008 | System MUST support at least five warehouse types | P2 |

### 21.4 Cross-Cutting

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-CC-001 | All inventory entities MUST be scoped to company_id (tenant isolation) | P1 |
| FR-CC-002 | All inventory data MUST support soft delete (logical deletion, not physical) | P1 |
| FR-CC-003 | All inventory operations MUST be logged in a full audit trail | P1 |
| FR-CC-004 | All mutations MUST be attributed to the authenticated user | P1 |
| FR-CC-005 | System MUST enforce RBAC permissions from Epic 4 on all inventory operations | P1 |
| FR-CC-006 | System MUST publish domain events for all significant state changes | P1 |
| FR-CC-007 | System MUST provide full-text search across the product catalogue | P1 |
| FR-CC-008 | System MUST support bulk import of products via Excel and CSV | P2 |
| FR-CC-009 | System MUST support bulk export of the product catalogue | P2 |
| FR-CC-010 | System MUST support barcode and QR scanner input for product lookup | P2 |

---

## 22. Non-Functional Requirements

### 22.1 Performance

| Requirement | Target |
| --- | --- |
| Product catalogue page load | Under 1 second (p95) |
| Stock position query response | Under 300ms per product, per warehouse |
| Product search results | Under 500ms including full-text search |
| Inventory snapshot generation | Under 5 seconds for up to 10,000 product lines |
| Bulk import processing | At least 1,000 rows per minute |
| Stock movement recording | Under 200ms for a single ledger entry |
| Concurrent user operations | No degradation up to 100 concurrent inventory users per tenant |

### 22.2 Security

- All inventory operations require authenticated sessions (Epic 2)
- All operations validated against RBAC (Epic 4)
- Tenant isolation — no cross-tenant data access under any operation
- Input validation on all inbound data to prevent injection and data corruption
- Bulk operations (import/export) rate-limited and logged

### 22.3 Scalability

| Dimension | Target |
| --- | --- |
| Products per company | 500,000 |
| Variants per product | 1,000 |
| Warehouses per company | 100 |
| Stock movements per day per company | 100,000 |
| Concurrent tenants on platform | 10,000 |
| Historical ledger retention | At least 7 years |

### 22.4 Availability

- Inventory domain SLO: 99.9% monthly
- Read operations available in degraded mode during partial write outage
- Planned maintenance: maximum 4 hours/month with 48-hour advance notice

### 22.5 Reliability

- Zero tolerance for stock quantity miscalculation — position must always match ledger sum
- Stock movement recording is transactional — fully committed or fully rolled back
- No orphaned stock positions — every quantity is traceable to a ledger entry

### 22.6 Maintainability

- All inventory business logic encapsulated in the service layer
- No business logic in the presentation or persistence layers
- Feature flags enable capability toggling without code deployment
- All domain events are versioned and backward-compatible

### 22.7 Logging, Monitoring, and Observability

- All operations produce structured log events with: user_id, company_id, operation, entity_id, timestamp
- Real-time monitoring of stock movement processing latency
- Distributed tracing for all cross-module inventory API calls
- Inventory domain health check endpoint for platform monitoring

### 22.8 Backup and Recovery

- Backed up with primary PostgreSQL database per Epic 1 backup policies
- Point-in-time recovery: last 30 days
- RTO: 4 hours | RPO: 1 hour
- Inventory ledger is highest-priority restore target

---

## 23. Business Rules

| ID | Rule |
| --- | --- |
| BR-001 | A product's SKU must be unique within a company |
| BR-002 | A product's barcode must be unique within a company |
| BR-003 | A product cannot be activated without: Name, Code, SKU, Category, Base UOM, and Product Type |
| BR-004 | Stock may only be moved to or from Active warehouses |
| BR-005 | If a product has variants, all inventory is tracked at the variant level |
| BR-006 | An inventory adjustment requires a reason code from the approved list |
| BR-007 | If adjustment approval is enabled, adjustments are pending until an authorised approver acts |
| BR-008 | A warehouse transfer must have sufficient Available Stock at source (subject to negative stock policy) |
| BR-009 | In-transit stock is not available for sale or further transfer until receiving warehouse confirms receipt |
| BR-010 | The inventory costing method (WAC or FIFO) is set once per company and applies to all products |
| BR-011 | Archived products cannot be assigned to new transactions |
| BR-012 | An archived warehouse cannot be used in any new transaction |
| BR-013 | Soft-deleted records are excluded from operational views but retained in audit queries |
| BR-014 | Inventory snapshots are immutable once generated |
| BR-015 | The Reorder Level must be ≥ Minimum Stock level if both are set |
| BR-016 | Safety Stock must be ≤ Reorder Level |
| BR-017 | A Category must be Active to be assigned to a new product |
| BR-018 | A Brand must be Active to be assigned to a new product |
| BR-019 | UOM conversion factors must be positive numbers greater than zero |
| BR-020 | Opening stock may not be recorded with a quantity of zero or less |
| BR-021 | Reserved stock cannot exceed current stock |
| BR-022 | Damaged stock quantity cannot exceed current stock |
| BR-023 | All stock-out movements are validated against available stock unless negative stock policy permits otherwise |
| BR-024 | A Warehouse belongs to exactly one Company. When Branch Management is introduced, a Warehouse may additionally belong to one Branch, but never to more than one Branch within the same Company |
| BR-025 | The Product Master is the authoritative owner of all product-level procurement metadata. Purchase, Sales, and Accounting modules may read procurement metadata but may not independently maintain a separate copy |
| BR-026 | Inventory valuation is always recorded in the Company's Base Currency. Future multi-currency support must convert to Base Currency at the point of stock receipt using exchange rates provided by the Accounting module — the Inventory domain never owns exchange rates |
| BR-027 | Product lifecycle governance is owned exclusively by the Inventory domain. No downstream module (Purchase, Sales, CRM) may unilaterally change a product's status; status changes must flow through the Inventory domain's defined transition rules |
| BR-028 | Procurement metadata fields on the Product Master (Preferred Supplier, Lead Time, EOQ, etc.) are non-operational in Epic 5. They are reserved fields that must not be used to drive any business logic until the corresponding downstream Epic (Purchase or Supply Chain) explicitly activates them |
| BR-029 | All monetary amounts stored in the Inventory domain must be accompanied by a currency code. In Epic 5 this is always the Company's Base Currency, but the architectural requirement for currency code presence enables future multi-currency reporting without schema migration |

---

## 24. Business Invariants

| ID | Invariant |
| --- | --- |
| INV-001 | For any product at any warehouse: `Current Stock = Σ Stock-In − Σ Stock-Out` (from inception) |
| INV-002 | `Available Stock ≤ Current Stock` always |
| INV-003 | `Reserved Stock + Available Stock ≤ Current Stock` always |
| INV-004 | All inventory entities carry a valid company_id matching the authenticated tenant |
| INV-005 | The stock ledger is append-only — no existing entry may be modified or deleted |
| INV-006 | Every stock movement has an attributed user_id — anonymous movements are not permitted |
| INV-007 | Every stock movement has a movement_type from the approved type list |
| INV-008 | A product's status may only advance through approved transitions |
| INV-009 | A warehouse may not be archived while its net stock position is non-zero |
| INV-010 | Inventory valuation is always calculable from the ledger — no separate valuation table may contradict the ledger |

---

## 25. Validation Rules

### 25.1 Product Validation

| Field | Rules |
| --- | --- |
| Product Name | Required; 1–500 characters; no HTML |
| Product Code | Required; unique per company; alphanumeric + hyphens; 1–100 chars |
| SKU | Required; unique per company; alphanumeric + hyphens/underscores; 1–100 chars |
| Category | Required; must reference an Active Category in the same company |
| Base UOM | Required; must reference a valid UOM in the same company |
| Product Type | Required; one of: Stockable, Service, Consumable, Asset |
| Description | Optional; max 5,000 characters |
| Barcode | Optional; unique per company; standard format validation |
| Images | Optional; max 10 images; each ≤ 10 MB; formats: JPG, PNG, WEBP |

### 25.2 Inventory Threshold Validation

| Field | Rules |
| --- | --- |
| Opening Stock Quantity | Required; must be > 0 |
| Opening Stock Unit Cost | Required; must be ≥ 0 |
| Safety Stock | Optional; must be ≥ 0 |
| Minimum Stock | Optional; must be ≥ 0; if Safety Stock is set: Min ≤ Safety Stock |
| Maximum Stock | Optional; must be > 0 and > Minimum Stock |
| Reorder Level | Optional; must be ≥ 0; must be ≥ Minimum Stock if set |

### 25.3 Warehouse Validation

| Field | Rules |
| --- | --- |
| Warehouse Name | Required; unique per company; 1–200 chars |
| Warehouse Code | Required; unique per company; alphanumeric; 1–20 chars |
| Warehouse Type | Required; one of: Main, Showroom, Transit, Return, Damage |
| Status | Required; one of: Active, Inactive, Archived |

### 25.4 Stock Movement Validation

| Field | Rules |
| --- | --- |
| Quantity | Required; must be > 0 |
| Movement Type | Required; must be from approved type list |
| Warehouse | Required; must be Active |
| Product / Variant | Required; must be Active |
| User Attribution | Required; system-provided from authenticated session |

---

## 26. Permission Matrix

All permission identifiers follow the `module:resource:action` convention from the Engineering Constitution and integrate with the RBAC system from Epic 4.

### 26.1 Product Master Permissions

| Permission | Owner | Admin | Inv. Mgr | WH Mgr | Store Keeper | Purchase | Sales | Auditor | Viewer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `inventory:product:create` | ✓ | ✓ | ✓ | — | — | — | — | — | — |
| `inventory:product:read` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `inventory:product:update` | ✓ | ✓ | ✓ | — | — | — | — | — | — |
| `inventory:product:archive` | ✓ | ✓ | ✓ | — | — | — | — | — | — |
| `inventory:category:manage` | ✓ | ✓ | ✓ | — | — | — | — | — | — |
| `inventory:brand:manage` | ✓ | ✓ | ✓ | — | — | — | — | — | — |
| `inventory:uom:manage` | ✓ | ✓ | — | — | — | — | — | — | — |
| `inventory:attribute:manage` | ✓ | ✓ | — | — | — | — | — | — | — |

### 26.2 Inventory Operations Permissions

| Permission | Owner | Admin | Inv. Mgr | WH Mgr | Store Keeper | Purchase | Sales | Auditor | Viewer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `inventory:stock:read` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `inventory:stock:opening` | ✓ | ✓ | ✓ | — | — | — | — | — | — |
| `inventory:stock:adjust` | ✓ | ✓ | ✓ | — | — | — | — | — | — |
| `inventory:stock:adjust:approve` | ✓ | ✓ | ✓ | — | — | — | — | — | — |
| `inventory:stock:reserve` | ✓ | ✓ | ✓ | — | — | ✓ | ✓ | — | — |
| `inventory:valuation:read` | ✓ | ✓ | ✓ | — | — | — | — | ✓ | — |
| `inventory:snapshot:create` | ✓ | ✓ | ✓ | — | — | — | — | — | — |
| `inventory:snapshot:read` | ✓ | ✓ | ✓ | — | — | — | — | ✓ | — |

### 26.3 Warehouse Permissions

| Permission | Owner | Admin | Inv. Mgr | WH Mgr | Store Keeper | Purchase | Sales | Auditor | Viewer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `inventory:warehouse:create` | ✓ | ✓ | — | — | — | — | — | — | — |
| `inventory:warehouse:read` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `inventory:warehouse:update` | ✓ | ✓ | — | — | — | — | — | — | — |
| `inventory:warehouse:archive` | ✓ | ✓ | — | — | — | — | — | — | — |
| `inventory:transfer:create` | ✓ | ✓ | ✓ | ✓ | — | — | — | — | — |
| `inventory:transfer:receive` | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | — | — |
| `inventory:transfer:cancel` | ✓ | ✓ | ✓ | ✓ | — | — | — | — | — |

### 26.4 Reporting and Audit Permissions

| Permission | Owner | Admin | Inv. Mgr | WH Mgr | Store Keeper | Purchase | Sales | Auditor | Viewer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `inventory:report:view` | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | — |
| `inventory:report:export` | ✓ | ✓ | ✓ | — | — | ✓ | ✓ | ✓ | — |
| `inventory:audit:read` | ✓ | ✓ | ✓ | — | — | — | — | ✓ | — |
| `inventory:import` | ✓ | ✓ | ✓ | — | — | — | — | — | — |
| `inventory:export` | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ |

---

## 27. Feature Matrix

### 27.1 Ready and Enabled

| Feature | Description |
| --- | --- |
| Product Master | Full product, variant, category, brand, UOM, attribute management |
| Product Lifecycle | Draft → Active → Inactive → Archived → Discontinued |
| Barcode & QR Association | Associate multiple codes per product/variant |
| Custom Fields | Configurable fields per product type and category |
| Product Images | Primary and gallery images per product/variant |
| Product Tags | Flexible tagging and tag-based filtering |
| Opening Stock | Initial stock recording per product per warehouse |
| Current / Available / Reserved Stock | Real-time stock position management |
| Damaged & Returned Stock | Separate tracking for damaged and returned quantities |
| Inventory Thresholds | Safety stock, min, max, reorder level |
| Negative Stock Policy | Company-level policy configuration |
| Inventory Adjustment | Formal adjustments with reason codes |
| Inventory Valuation (WAC + FIFO) | Cost method calculations |
| Inventory Snapshot | Point-in-time snapshot generation |
| Multi-Warehouse | Unlimited warehouses per company |
| Warehouse Locations | Sub-areas within a warehouse |
| Stock Transfer | Two-step inter-warehouse transfer with in-transit tracking |
| Low Stock / Reorder Alerts | Threshold-based alert and suggestion generation |
| Full-Text Product Search | Search by name, code, SKU, keywords |
| Barcode Search | Scan-to-search product lookup |
| Advanced Filters | Filter by category, brand, warehouse, status, type |
| Bulk Import | Excel and CSV |
| Bulk Export | Product catalogue and stock |
| Audit Trail | Complete audit log for all inventory operations |
| Domain Events | All significant events published to the event bus |
| RBAC Integration | Full permission enforcement via Epic 4 |

### 27.2 Ready but Disabled

| Feature | Disabled By Default Because |
| --- | --- |
| Adjustment Approval Workflow | Optional; many businesses prefer direct adjustments |
| Overstock Alerts | Generates noise if max stock not configured |
| Email/SMS Notifications for Alerts | Requires provider configuration |
| Saved Search Filters | Enabled when user first saves a filter |

### 27.3 Future

| Feature | Target |
| --- | --- |
| Physical Stock Count | Future Phase 2 |
| Cycle Count | Future Phase 2 |
| Inventory Freeze | Future Phase 2 |
| Bin & Rack Tracking | Future Phase 2 |
| Lot / Batch / Serial Number Tracking | Future Traceability Module |
| Expiry Date Management | Future Traceability Module |
| Barcode Label Printing Engine | Future Integration Module |
| AI Demand Forecasting | Epic 13 |
| Mobile App Inventory Management | Future Mobile Module |
| POS Integration | Future POS Module |
| Multi-Currency Valuation | Future International Module (readiness in §15.18) |
| Public Inventory API | Future API Module |
| Branch Management (Company → Branch → Warehouse hierarchy) | Future Branch Module (readiness in §16.10) |
| Procurement Metadata on Product Master (Supplier, Lead Time, EOQ, Tax Category, Storage Conditions, Shelf Life, Hazard, Country of Origin) | Future Purchase & Supply Chain Module (readiness in §14.16) |

---

## 28. Master Data Governance

### 28.1 Governance Principles

1. **Uniqueness Enforcement**: No two active master data records share the same code within a company
2. **Referential Integrity**: Master data in use cannot be deleted; only inactivated or archived
3. **Authorised Management**: Only Admin and above may create or modify master data
4. **Audit Trail**: All master data changes are logged with user attribution
5. **Soft Delete Only**: Physical removal is never permitted

### 28.2 Category Governance

- Managed exclusively by Admin and above
- Hierarchy must not be circular
- Category codes: 3–10 uppercase alphanumeric characters
- Deactivation blocked if Active products are assigned

### 28.3 Brand Governance

- Brand codes: 3–50 characters
- Deactivation blocked if Active products are assigned
- Tenant-scoped

### 28.4 UOM Governance

- System provides a standard UOM library at company setup
- Companies may add custom UOM definitions
- UOM deletion blocked if any product references it
- Conversion factors are immutable once used in a transaction; new conversions may be added

### 28.5 Attribute Governance

- Defined at the company level
- Cannot be modified in ways that invalidate existing product data
- Obsolete options can be deprecated but not deleted if used on existing products

### 28.6 Product Code Standards

The system supports:
- Auto-code generation (category prefix + sequential number)
- Manual code assignment
- Code uniqueness validation at point of assignment

---

## 29. Conceptual Domain Model

This is a conceptual representation — not a physical data model.

```
Company (Tenant)
  │
  ├── has many → Product
  │     ├── belongs to → Category → belongs to → Category (parent)
  │     ├── belongs to → Brand
  │     ├── has → Base UOM
  │     ├── has → Product Type
  │     ├── has → Product Status
  │     ├── has many → Product Variant
  │     │     ├── has → SKU
  │     │     ├── has many → Barcode / QR Code
  │     │     └── has many → Attribute Value
  │     ├── has many → Product Image
  │     ├── has many → Tag
  │     ├── has many → Custom Field Value
  │     └── has many → Internal Note
  │
  ├── has many → Warehouse
  │     ├── has → Warehouse Type
  │     ├── has → Warehouse Status
  │     └── has many → Warehouse Location
  │
  ├── has many → Stock Position (Product × Warehouse)
  │     ├── Current Stock (derived)
  │     ├── Reserved Stock
  │     ├── Damaged Stock
  │     ├── Available Stock (derived)
  │     ├── Safety Stock
  │     ├── Min / Max Stock
  │     └── Reorder Level
  │
  ├── has many → Stock Movement (Ledger — immutable)
  │     ├── belongs to → Product / Variant
  │     ├── belongs to → Warehouse
  │     ├── has → Movement Type
  │     ├── has → Quantity + Unit Cost
  │     └── attributed to → User
  │
  ├── has many → Stock Transfer
  │     ├── from → Source Warehouse
  │     ├── to → Destination Warehouse
  │     ├── has many → Transfer Line
  │     └── has → Transfer Status
  │
  ├── has many → Inventory Adjustment
  │     ├── belongs to → Product / Warehouse
  │     ├── has → Delta Quantity + Reason Code
  │     ├── submitted by → User
  │     └── approved by → User (optional)
  │
  ├── has many → Inventory Snapshot
  │     └── has many → Snapshot Line (Product × Warehouse × Qty × Cost)
  │
  ├── has many → Reorder Rule (Product × Warehouse)
  │
  └── has many → Low Stock Alert
        ├── belongs to → Product / Warehouse
        ├── has → Alert Type (Low Stock / Out of Stock / Overstock)
        └── has → Alert Status (Open / Acknowledged / Resolved)
```

---

## 30. Aggregate Roots

| Aggregate Root | Responsibility | Key Invariants Enforced |
| --- | --- | --- |
| **Product** | Product entity, variants, attributes, images, tags, lifecycle | SKU uniqueness, barcode uniqueness, mandatory fields, status transitions |
| **Stock Position** | Quantity state of a product at a warehouse | Ledger-derived consistency, available stock calculation, negative stock policy |
| **Stock Movement** | Immutable ledger entry for a stock change | Append-only, mandatory attribution, valid movement type, quantity > 0 |
| **Warehouse** | Warehouse identity, configuration, lifecycle | Code uniqueness, status constraints, archival protection |
| **Stock Transfer** | Two-warehouse transfer workflow | Source availability, in-transit tracking, receipt confirmation |
| **Inventory Adjustment** | Formal stock corrections | Reason code requirement, approval workflow, ledger consistency |
| **Category** | Product classification hierarchy | Code uniqueness, circular reference prevention, deactivation protection |

---

## 31. Domain Events

### 31.1 Product Events

| Event | Trigger | Key Payload |
| --- | --- | --- |
| `ProductCreated` | Product moves to Draft | product_id, company_id, product_code, sku, name, type, category_id |
| `ProductActivated` | Status → Active | product_id, activated_by, activated_at |
| `ProductUpdated` | Any product field modified | product_id, changed_fields, updated_by, updated_at |
| `ProductDeactivated` | Status → Inactive | product_id, deactivated_by, reason |
| `ProductArchived` | Status → Archived | product_id, archived_by, archived_at |
| `ProductDiscontinued` | Status → Discontinued | product_id, discontinued_by |
| `ProductVariantCreated` | New variant added | product_id, variant_id, sku, attributes |
| `ProductVariantUpdated` | Variant modified | product_id, variant_id, changed_fields |
| `BarcodeAssigned` | Barcode linked to product/variant | entity_id, entity_type, barcode, format |

### 31.2 Stock Events

| Event | Trigger | Key Payload |
| --- | --- | --- |
| `OpeningStockRecorded` | Opening stock entry created | product_id, variant_id, warehouse_id, quantity, unit_cost, date |
| `StockIncreased` | Any inbound movement | product_id, variant_id, warehouse_id, quantity, movement_type, reference_doc, unit_cost, user_id |
| `StockReduced` | Any outbound movement | product_id, variant_id, warehouse_id, quantity, movement_type, reference_doc, user_id |
| `StockReserved` | Stock reserved for Sales Order | product_id, variant_id, warehouse_id, quantity, order_reference, user_id |
| `StockReservationReleased` | Reservation cancelled | product_id, variant_id, warehouse_id, quantity, released_by, reason |
| `StockAdjusted` | Adjustment approved and applied | product_id, warehouse_id, old_quantity, new_quantity, delta, reason_code, adjusted_by, approved_by |
| `StockTransferred` | Transfer completed | transfer_id, source_warehouse_id, destination_warehouse_id, product_id, quantity, transferred_by |
| `DamagedStockRecorded` | Quantity classified as damaged | product_id, warehouse_id, quantity, reason, recorded_by |
| `ReturnedStockReceived` | Return stock recorded | product_id, warehouse_id, quantity, source_reference, received_by |
| `LowStockAlertRaised` | Available stock below threshold | product_id, warehouse_id, threshold_type, current_quantity, threshold_quantity |
| `ReorderSuggestionGenerated` | Reorder level reached | product_id, warehouse_id, current_quantity, reorder_level, suggested_quantity |
| `OutOfStockDetected` | Available stock = 0 | product_id, variant_id, warehouse_id |

### 31.3 Warehouse Events

| Event | Trigger | Key Payload |
| --- | --- | --- |
| `WarehouseCreated` | New warehouse added | warehouse_id, company_id, name, code, type, created_by |
| `WarehouseUpdated` | Configuration changed | warehouse_id, changed_fields, updated_by |
| `WarehouseDeactivated` | Status → Inactive | warehouse_id, deactivated_by, reason |
| `WarehouseArchived` | Status → Archived | warehouse_id, archived_by, archived_at |
| `StockTransferInitiated` | Transfer created | transfer_id, source_id, destination_id, initiated_by |
| `StockTransferDispatched` | Transfer → In Transit | transfer_id, dispatched_by, dispatched_at |
| `StockTransferReceived` | Transfer confirmed at destination | transfer_id, received_by, received_at |
| `StockTransferCancelled` | Transfer cancelled | transfer_id, cancelled_by, reason |

### 31.4 Adjustment Events

| Event | Trigger | Key Payload |
| --- | --- | --- |
| `InventoryAdjustmentSubmitted` | Adjustment created | adjustment_id, product_id, warehouse_id, delta, reason_code, submitted_by |
| `InventoryAdjustmentApproved` | Approver approves | adjustment_id, approved_by, approved_at |
| `InventoryAdjustmentRejected` | Approver rejects | adjustment_id, rejected_by, rejection_reason |

---

## 32. Reporting Requirements

### 32.1 Standard Reports

| Report | Description | Refresh |
| --- | --- | --- |
| **Inventory Summary** | Total current, available, and value per product across all/selected warehouses | Real-time |
| **Stock Ledger** | Chronological log of all movements for a product at a warehouse in a date range | Real-time |
| **Inventory Valuation Report** | Total inventory value by product, category, or warehouse | Real-time |
| **Warehouse Stock Report** | Stock position for all products at a selected warehouse | Real-time |
| **Category Stock Report** | Aggregated stock and valuation per category/sub-category | Real-time |
| **Brand Stock Report** | Aggregated stock and valuation per brand | Real-time |
| **Dead Stock Report** | Products with no movement in a configurable period (default 90 days) | Daily |
| **Fast-Moving Stock Report** | Products with highest movement frequency in selected period | Daily |
| **Slow-Moving Stock Report** | Products with lowest movement frequency in selected period | Daily |
| **Stock Aging Report** | Age of current stock categorised by receipt date | Daily |
| **Inventory Trend Analysis** | Month-over-month stock movement trends per product/category | Daily |
| **Low Stock Alert Report** | All active alerts (low stock, safety breach, reorder) | Real-time |
| **Transfer History Report** | All warehouse transfer transactions within a date range | Real-time |
| **Adjustment History Report** | All inventory adjustments with reason codes and approver details | Real-time |

### 32.2 Report Features

- All reports filterable by: date range, warehouse, category, brand, product type, status
- All reports exportable to Excel and CSV
- Drill-down from summary to transaction level
- Tenant-isolated — no cross-company data

---

## 33. KPI Requirements

| KPI | Definition | Target |
| --- | --- | --- |
| **Inventory Turnover Rate** | COGS ÷ Average Inventory Value | Industry-dependent (typically 4–12x/year) |
| **Average Inventory Value** | (Beginning + Ending Inventory) ÷ 2 | Informational |
| **Inventory Accuracy** | (Correctly Counted ÷ Total Counted) × 100% | ≥ 98% |
| **Dead Stock Percentage** | (Units with 0 movement in 90 days ÷ Total Units) × 100% | ≤ 5% |
| **Stock Accuracy Percentage** | (System matches Physical ÷ Total Items) × 100% | ≥ 99% |
| **Warehouse Efficiency** | Transactions per day per warehouse | Informational |
| **Inventory Value** | Σ (Current Stock × Weighted Average Cost) | Informational |
| **Stockout Rate** | (Products with 0 Available ÷ Total Active) × 100% | ≤ 2% |
| **Overstock Rate** | (Products exceeding Max Stock ÷ Total Active) × 100% | ≤ 5% |
| **Reorder Compliance Rate** | (Reorder Actions Taken ÷ Suggestions Generated) × 100% | ≥ 80% |

KPI dashboard displays real-time values with 30-day, 90-day, and 12-month trend sparklines, colour-coded against configurable targets (Red / Amber / Green).

---

## 34. Search Requirements

### 34.1 Search Capabilities

| Search Type | Description |
| --- | --- |
| **Global Search** | Across product names, codes, SKUs, descriptions, keywords, and tags |
| **Barcode Search** | Exact match on barcode value — returns product/variant instantly |
| **QR Code Search** | Exact match on QR code value |
| **SKU Search** | Exact or partial match on SKU |
| **Brand Search** | Filter or search by brand name |
| **Category Search** | Filter by category or sub-category |
| **Warehouse Search** | Filter stock positions by warehouse |
| **Tag Search** | Filter products by one or more tags |

### 34.2 Advanced Filters

Users may combine: product type, product status, category/sub-category, brand, warehouse, stock availability (In Stock / Out of Stock / Low Stock), date created/updated range, has images, has barcode, has variants.

### 34.3 Search UX Requirements

| Requirement | Detail |
| --- | --- |
| **Sorting** | By: Name, Code, SKU, Date Created/Updated, Current Stock, Category |
| **Pagination** | Server-side; configurable page size (10, 25, 50, 100) |
| **Saved Filters** | Users can save and name custom filter combinations |
| **Search Speed** | Results returned in under 500ms |
| **Typo Tolerance** | Minor spelling variations return relevant results |
| **Highlighting** | Search terms highlighted in results |

---

## 35. Import & Export

### 35.1 Product Import

| Capability | Detail |
| --- | --- |
| **Formats** | Excel (.xlsx), CSV (.csv) |
| **Template** | System provides downloadable import template |
| **Validation** | Row-level validation with error reporting before commit |
| **Partial Import** | Valid rows processed; invalid rows reported and skipped |
| **Duplicate Handling** | Skip duplicates or Update existing by Code/SKU |
| **Capacity** | Up to 10,000 rows per import file |
| **Fields** | All product fields including custom fields |
| **Image Import** | Images referenced by URL; downloaded and stored during import |

### 35.2 Opening Stock Import

- Requires: Product Code or SKU, Warehouse Code, Quantity, Unit Cost, Reference Date
- Product must be Active; Warehouse must be Active

### 35.3 Product Export

| Capability | Detail |
| --- | --- |
| **Formats** | Excel (.xlsx), CSV (.csv) |
| **Scope** | All products or filtered subset |
| **Fields** | All product fields including custom fields and current stock quantities |
| **Capacity** | Up to 100,000 rows per export |
| **PDF** | Future |

### 35.4 Stock Ledger Export

- Full or filtered movement history
- Includes: Product, Warehouse, Movement Type, Quantity, Unit Cost, Reference, User, Timestamp

---

## 36. Notifications

### 36.1 Notification Events

| Event | Recipients | Channels |
| --- | --- | --- |
| Low Stock Alert | Inventory Manager, Company Owner | In-app, Email |
| Out of Stock Alert | Inventory Manager, Sales User, Company Owner | In-app, Email, SMS (optional) |
| Reorder Suggestion | Inventory Manager, Purchase User | In-app, Email |
| Overstock Alert | Inventory Manager | In-app, Email |
| Adjustment Pending Approval | Inventory Manager, Admin | In-app, Email |
| Adjustment Approved / Rejected | Submitter | In-app, Email |
| Transfer Ready for Receipt | Destination Warehouse Manager | In-app, Email |
| Import Completed / Failed | Import initiator | In-app, Email |

### 36.2 Notification Channels

| Channel | Status |
| --- | --- |
| In-App Notification | Ready and Enabled |
| Email | Ready and Enabled (requires SMTP configuration) |
| SMS | Ready but Disabled (requires provider configuration) |
| WhatsApp | Future |
| Push Notification | Future (requires Mobile App) |

### 36.3 Notification Preferences

- Users configure preferences per event type
- Admins set company-wide defaults
- Frequency: Immediate, Hourly Digest, or Daily Digest

---

## 37. Audit Requirements

### 37.1 Audit Coverage

Every write operation in the Inventory domain produces an audit record.

| Field | Description |
| --- | --- |
| `audit_id` | Unique audit record identifier |
| `company_id` | Tenant identifier |
| `entity_type` | Entity being audited |
| `entity_id` | Identifier of the specific entity |
| `operation` | CREATE / UPDATE / STATUS_CHANGE / DELETE (soft) |
| `changed_fields` | JSON diff of before and after state for UPDATE operations |
| `performed_by` | user_id of the operator |
| `performed_at` | UTC timestamp |
| `ip_address` | IP address of requesting session |
| `session_id` | Session identifier |
| `reason` | Business reason (required for adjustments and status changes) |

### 37.2 Audit Immutability

- Audit records are append-only — no update or delete ever performed
- Stored in a separate audit schema
- Excluded from soft-delete operations

### 37.3 Audit Access

- Readable by: Super Admin, Company Owner, Admin, Inventory Manager, Auditor
- Exportable by: Super Admin, Auditor
- Tenant-isolated

### 37.4 Adjustment Audit (Enhanced)

Adjustment audit records also capture: Old Quantity, New Quantity, Delta, Reason Code, Notes, Approver user_id, and Approval Timestamp.

---

## 38. Security Requirements

| Requirement | Detail |
| --- | --- |
| **Authentication** | Valid JWT from Authentication domain (Epic 2) required for all operations |
| **Authorisation** | All operations validated against RBAC permissions from Epic 4 |
| **Tenant Isolation** | Every query and mutation scoped to the authenticated user's company_id |
| **Data in Transit** | All API communication over HTTPS/TLS 1.2 or higher |
| **Data at Rest** | PostgreSQL encryption at rest for production deployments |
| **Input Sanitisation** | All user inputs sanitised; no raw HTML stored in text fields |
| **Mass Assignment Protection** | Only permitted fields accepted per operation |
| **Rate Limiting** | Import and export endpoints rate-limited per tenant |
| **File Upload Security** | Uploaded images validated for type and size; stored in isolated S3 prefix per company |
| **Audit Tamper Protection** | Audit records have no update endpoints; write-once policy enforced at persistence layer |

---

## 39. Compliance Requirements

| Requirement | Description |
| --- | --- |
| **Data Sovereignty** | Inventory data stored within the tenant's designated region |
| **Audit Completeness** | 100% of write operations must have an audit record |
| **Financial Accuracy** | Inventory valuation must produce figures auditable for balance sheet purposes |
| **Traceability** | Every stock quantity change must be traceable to a user and a business event |
| **Data Privacy** | No personally identifiable information stored within inventory entities |
| **Record Retention** | Audit records and stock ledger entries retained for a minimum of 7 years |

---

## 40. Data Retention Policy

| Data Category | Retention Period | Policy |
| --- | --- | --- |
| Active product records | Indefinite while company is active | Retained until archival |
| Archived product records | 7 years from archival date | Compliance |
| Stock movement ledger | 7 years from movement date | Immutable; append-only |
| Audit trail records | 7 years from creation date | Immutable; append-only |
| Inventory snapshots | 3 years from creation | Reporting |
| Inventory adjustment records | 7 years | Immutable after approval |
| Import/export logs | 1 year | Operational log |
| Notification history | 90 days | Operational record |
| Soft-deleted records | 1 year from deletion date | Then permanently purged |

---

## 41. Disaster Recovery

| Metric | Target |
| --- | --- |
| **RTO** | 4 hours — system fully operational after incident |
| **RPO** | 1 hour — maximum data loss in a catastrophic event |
| **Backup Frequency** | Hourly incremental; daily full backup |
| **Backup Retention** | 30 days point-in-time recovery |

**Recovery Priority**: Tier 1. All other business modules depend on Inventory — its restoration is the highest priority after platform infrastructure.

**Post-Recovery Integrity**: The system must verify that the sum of all ledger entries matches stock positions. Discrepancies trigger an automatic alert to the Platform Admin.

---

## 42. Performance Targets

| Operation | Target (p95) |
| --- | --- |
| Product catalogue listing (100 results) | < 1 second |
| Product detail page load | < 500ms |
| Real-time stock position query | < 300ms (single product, single warehouse) |
| Stock movement recording | < 200ms per entry |
| Inventory snapshot (10,000 lines) | < 5 seconds |
| Barcode search (exact match) | < 100ms |
| Full-text product search | < 500ms |
| Bulk import (1,000 rows) | < 60 seconds end-to-end |
| Bulk export (10,000 rows) | < 30 seconds |
| Inventory valuation report | < 5 seconds (full company) |

---

## 43. Scalability Targets

| Dimension | Target |
| --- | --- |
| Products per company | 500,000 |
| Variants per product | 1,000 |
| Warehouses per company | 100 |
| Categories per company | 5,000 |
| Brands per company | 10,000 |
| Attributes per product | 50 |
| Stock movements per day per company | 100,000 |
| Concurrent inventory users per company | 100 |
| Simultaneous companies on platform | 10,000 |
| Historical ledger size | Unlimited (with archival strategy after 7 years) |
| Images per product | 10 (primary + 9 gallery) |

---

## 44. Cross-Module Dependencies

### 44.1 Upstream Dependencies (Inventory Depends On)

| Module | Dependency Type | Details |
| --- | --- | --- |
| **Authentication (Epic 2)** | Hard | JWT validation for all operations; session context for audit attribution |
| **Companies (Epic 3)** | Hard | company_id for tenant isolation; company configuration (costing method, negative stock policy) |
| **Users & Roles (Epic 4)** | Hard | RBAC permission checks; role-based access; user identity in audit trail |

### 44.2 Downstream Dependencies (Other Modules Depend On Inventory)

| Module | What It Consumes | Stability Requirement |
| --- | --- | --- |
| **Purchase (Epic 6)** | Product catalogue (with procurement metadata), warehouse list, stock receipt events, reorder suggestions | Product Master API must be stable before Epic 6 implementation begins |
| **Sales (Epic 7)** | Product catalogue, available stock per warehouse, stock reservation API, stock dispatch events, restock notifications | Available stock calculation and reservation API must be stable before Epic 7 implementation begins |
| **Accounting (Epic 8)** | Inventory valuation, stock movement unit costs, COGS events, write-off events | StockIncreased/StockReduced events with unit cost and total value must be stable; currency code on all monetary fields is required |
| **CRM (Epic 9)** | Product catalogue — name, description, images, attributes, category, brand | Product read API must be stable; CRM never modifies inventory data |
| **Warranty (Epic 10)** | Product and variant identity — product_id, variant_id, product name, SKU | Product identity must remain stable; archival must not invalidate Warranty references |
| **Installments (Epic 11)** | Product identity and current valuation reference for collateral tracking | Inherits from Sales and Accounting dependencies |
| **Reports (Epic 12)** | All inventory entities, events, and pre-aggregated summary data | Full data access; Inventory domain must never restrict read access to Reports |
| **AI & Forecasting (Epic 13)** | Full stock movement history with timestamps, movement types, quantities, product attributes | Stock ledger structure must not change; historical data must be preserved indefinitely |

### 44.3 Cross-Epic Architectural Compatibility Commitment

The following formal commitments are made by the Inventory domain to ensure all downstream Epics can be built without requiring redesign of the Product Master or Stock Operations:

**1. Product Master Stability**
The Product Master data model established in Epic 5 is the permanent foundation for all subsequent ERP modules. The following guarantees apply:
- Product identity (product_id, SKU, variant_id) will not change across the product lifecycle
- Product status transitions will not change without a formal spec amendment
- New fields added to the Product Master will be optional and backward-compatible
- No downstream Epic may alter the Product Master schema without an approved change to this SSOT

**2. Stock Ledger Immutability**
The stock ledger structure established in Epic 5 is append-only and permanent. Downstream Epics that depend on historical stock movements (Accounting, AI, Reports) are guaranteed that:
- All historical ledger entries remain accessible indefinitely
- Ledger entry schema is additive-only (new fields may be added; existing fields will not be removed or renamed)
- Movement type codes will not be reassigned or deleted

**3. Future Module Readiness Without Redesign**
Epic 5 is explicitly designed so that the following future capabilities require **configuration and additional implementation only** — no structural redesign of the Inventory domain:
- Branch Management (§16.10)
- Multi-Currency Valuation (§15.18)
- Procurement Metadata activation (§14.16)
- Bin and Rack tracking (§16.6, §16.7)
- Lot, Batch, and Serial Number tracking
- Physical Stock Count and Cycle Count

---

## 45. Cross-Module Contracts

### 45.1 Inventory → Purchase Contract

- Provides searchable, filterable product catalogue
- Provides real-time available stock per product per warehouse
- Provides active warehouse list
- Accepts stock receipt confirmations → creates StockIncreased ledger entries
- Provides reorder suggestions for Purchase module to act on

### 45.2 Inventory → Sales Contract

- Provides product catalogue with variant detail
- Provides real-time available stock per product per warehouse
- Provides stock reservation API (reserve / release / confirm dispatch)
- Raises OutOfStockDetected events for Sales to handle
- Accepts return stock events from Sales → creates ReturnedStockReceived entries

### 45.3 Inventory → Accounting Contract

- Publishes StockIncreased and StockReduced events with unit cost and total value
- Provides Inventory Valuation API for balance sheet integration
- Publishes InventoryAdjustment events with write-off values for P&L
- COGS is derivable from the stock ledger using the selected costing method

### 45.4 Inventory → Reports Contract

- All inventory entities and events are queryable through the Reports module's data layer
- Pre-aggregated summary tables available for report performance
- Snapshots available as point-in-time data sets

---

## 46. Integration Readiness

### 46.1 Hardware Integrations

| Device | Status | Details |
| --- | --- | --- |
| **Barcode Scanner** | Ready | System accepts barcode input at all product search points; USB HID and Bluetooth compatible via browser input |
| **QR Code Scanner** | Ready | QR scan triggers product lookup; camera-based scanning supported via web API |
| **Label Printer** | Ready (output data only) | System generates printable barcode/QR label data; label formatting engine is Future |
| **POS Terminal** | Future | Architecture defined; implementation deferred to POS Module |
| **IoT Sensors** | Future | RFID, smart shelves — event ingestion architecture defined; implementation Future |

### 46.2 Software Integrations

| Integration | Status |
| --- | --- |
| **Future Mobile App** | Domain events and query APIs designed for mobile consumption |
| **Future Public API** | Internal API structure mirrors the future public API contract |
| **Import from Legacy ERP** | Bulk Excel/CSV import supports migration from legacy systems |
| **Accounting Software** | Stock valuation events structured for accounting journal entry generation |

---

## 47. AI Readiness

### 47.1 Data Foundations for AI

| AI Capability | Data Required (laid in Epic 5) |
| --- | --- |
| **Demand Forecasting** | Full stock movement history with timestamps, movement types, and references |
| **Inventory Prediction** | Historical stock levels, seasonal patterns from movement data |
| **Auto Reorder** | Movement velocity, reorder levels, lead time (from Purchase) |
| **Dead Stock Detection** | Movement frequency and aging analysis data |
| **Inventory Insights** | Aggregated KPI trends, valuation history |
| **AI Assistant** | Structured domain data accessible via query API |

### 47.2 Design Principles for AI Readiness

- All stock movements recorded with full context for ML feature extraction
- Movement timestamps in UTC with full precision for time-series analysis
- Product attributes are structured (not free text) to enable feature engineering
- Historical snapshots provide point-in-time labels for supervised learning
- No AI logic embedded in Epic 5 — data structures are AI-ready but AI-agnostic

---

## 48. Analytics Readiness

| Analytics Requirement | How Epic 5 Supports It |
| --- | --- |
| Time-series stock analysis | All movements timestamped; snapshots provide point-in-time anchors |
| Multi-dimensional slicing | Dimensioned by product, category, brand, warehouse, and time |
| Aggregated KPI computation | Pre-aggregated summary tables alongside raw ledger |
| Cross-module analytics | Domain events provide integration points for joining with sales, purchase, and accounting |
| Data export for BI | Bulk export and structured event bus |
| Drill-down capability | All summary reports link to transaction-level ledger entries |

**Planned Analytics (Future Epic 12)**: Interactive dashboard, custom report builder, scheduled delivery, BI tool connectors, real-time analytics streaming.

---

## 49. Extensibility Strategy

### 49.1 Horizontal Extensibility (New Capabilities)

- **Feature Flags**: Every optional capability behind a flag, enabling per-tenant activation
- **Custom Fields**: Companies extend any entity without schema changes
- **Attribute Sets**: Product attribute vocabulary is user-configurable, not hardcoded
- **Event Bus**: New subscribers consume existing events without modifying the publisher
- **Plugin Points**: Defined extension points for reason codes, movement types, notification triggers

### 49.2 Vertical Extensibility (New Industries)

New industry requirements accommodated through configuration:
- New product types registered as variants of the base Product Type enum
- New UOM categories addable without schema changes
- New movement types registerable for industry-specific source documents
- Attribute sets capture any industry-specific product characterisation

### 49.3 API Versioning for Consumers

- Inventory domain exposes versioned internal APIs (v1, v2, etc.)
- Consuming bounded contexts declare the version they depend on
- Breaking changes require a new API version; the previous version remains available for a defined transition period

---

## 50. Versioning Strategy

### 50.1 Domain Event Versioning

- All domain events carry a `schema_version` field
- Event consumers declare the minimum schema version they support
- Backward-compatible changes (new optional fields) made in the same version
- Breaking changes (field removal, type change) require a new event version

### 50.2 API Versioning

- Internal Inventory API follows the DevSphere API versioning standard (Engineering Constitution)
- Version in URL path: `/api/v1/inventory/...`
- At least one previous major version supported for 6 months after a new version release

### 50.3 Master Data Versioning

- Changes to category, UOM, or attribute configuration versioned with timestamps
- Historical product data retains configuration values at the time of recording

---

## 51. Risks

| ID | Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- | --- |
| R-001 | Incorrect opening stock entry corrupts valuation from day one | Medium | High | Validation workflow; import preview before commit; snapshot before and after |
| R-002 | Performance degradation under high ledger volume (millions of movements) | Medium | High | Indexed queries; summary tables; archival strategy for old ledger |
| R-003 | Product master imported with duplicates from legacy ERP | High | Medium | Duplicate detection with configurable conflict resolution before commit |
| R-004 | Negative stock policy misconfigured allows deeply negative stock | Low | High | Default to Strict; admin confirmation required to change |
| R-005 | Inventory costing method mismatch with accounting expectations | Medium | High | Costing method selected and documented at company setup; change requires explicit revaluation event |
| R-006 | Scope creep — bin/rack tracking added prematurely | Medium | Medium | Strict YAGNI enforcement; bin/rack explicitly in Future feature flag |

---

## 52. Assumptions

| ID | Assumption |
| --- | --- |
| A-001 | Every company has at least one active warehouse configured before recording any stock |
| A-002 | Opening stock is a one-time event per product per warehouse; additional receipts come via Purchase (Epic 6) |
| A-003 | The inventory costing method is selected during company onboarding and does not change without a formal revaluation event |
| A-004 | User roles and permissions from Epic 4 are operational before Epic 5 is deployed |
| A-005 | Image storage is configured in S3-compatible storage as established in Epic 3 |
| A-006 | The domain event bus is operational from Epic 1's infrastructure |
| A-007 | Companies import historical stock data via bulk import rather than expecting automatic migration |
| A-008 | The base currency for inventory valuation is the company's primary currency configured in the Company profile (Epic 3) |
| A-009 | Serial number and lot tracking will not be requested during Epic 5 |

---

## 53. Constraints

| ID | Constraint | Source |
| --- | --- | --- |
| C-001 | All entities must carry `company_id` for tenant isolation | Engineering Constitution |
| C-002 | Soft delete only — no physical row deletion | Engineering Constitution |
| C-003 | All API endpoints follow the versioning strategy from the Engineering Constitution | Epic 0 |
| C-004 | No business logic in migration files | Engineering Constitution |
| C-005 | Inventory valuation must not bypass the stock ledger | Business Invariant INV-010 |
| C-006 | RBAC permissions must align with the permission categories established in Epic 4 | Epic 4 Spec |
| C-007 | Image uploads go to the S3 bucket prefix established for the company in Epic 3 | Epic 3 Contract |
| C-008 | Domain events must be backward-compatible within a version | Epic 1 Architecture |
| C-009 | The system must function correctly for a company with 1 warehouse and a company with 100 warehouses without code branching | Scalability requirement |

---

## 54. Success Metrics

### 54.1 Technical Success Metrics

| Metric | Target | Measurement Method |
| --- | --- | --- |
| Product creation (all fields) | < 3 seconds end-to-end | Performance test: p95 |
| Inventory search response time | < 500ms | Load test: 50 concurrent requests |
| Inventory reconciliation accuracy | 100% ledger-to-position match | Automated integrity test post-migration |
| Warehouse transfer completion time | < 30 seconds (initiation + dispatch confirmation) | Functional test |
| Low stock alert accuracy | 100% of threshold breaches generate exactly one alert | Functional + regression test |
| Inventory valuation accuracy | WAC and FIFO match manual calculation to 2 decimal places | Valuation regression test suite |
| Audit trail completeness | 100% of write operations have a corresponding audit record | Audit coverage test |
| Bulk import (1,000 products) | < 60 seconds | Performance test |
| Stock movement recording (100 concurrent) | Zero data loss | Concurrency test |
| Cross-tenant data access | Zero cross-tenant data access | Security penetration test |

### 54.2 Business Success Metrics

| Metric | Target | Timeline |
| --- | --- | --- |
| Time to create a full product with variants | Under 5 minutes | User acceptance testing |
| Stock position accuracy at go-live | 100% match to physical inventory during UAT | Measured at go-live |
| User adoption of alert system | ≥ 80% of alerts acted upon within 24 hours | 30 days post-launch |
| Import success rate | ≥ 95% of imported rows accepted without error | During onboarding |

---

## 55. Glossary

| Term | Full Definition |
| --- | --- |
| **SKU** | Stock Keeping Unit. A unique alphanumeric code assigned to each product or variant. No two active products in the same company share an SKU. |
| **Barcode** | A machine-readable optical representation of a product identifier. Supported formats: EAN-13, EAN-8, UPC-A, UPC-E, Code 128, Code 39. |
| **QR Code** | A two-dimensional matrix barcode encoding product identification data. Scannable by camera or dedicated QR scanner. |
| **Opening Stock** | The initial inventory quantity recorded for a product at a specific warehouse at system go-live or first product introduction. The baseline from which all subsequent movements are calculated. |
| **Current Stock** | Total quantity of a product at a warehouse, derived from the cumulative sum of all inbound and outbound movements from inception. |
| **Available Stock** | Current Stock − Reserved Stock − Damaged Stock. The operative figure for sales order acceptance. |
| **Reserved Stock** | Quantity committed to an unfulfilled Sales Order or outbound transfer. Included in Current Stock; excluded from Available Stock. |
| **Safety Stock** | A minimum inventory buffer configured per product. A breach triggers a Safety Stock Alert. |
| **Reorder Level** | The inventory threshold at which a replenishment suggestion is generated. |
| **Warehouse** | A physical or logical storage location where inventory is managed. A company may have multiple independent warehouses. |
| **Bin** | (Future) The smallest discrete storage unit within a warehouse location. |
| **Rack** | (Future) A shelving structure within a warehouse location organising bins. |
| **Stock Ledger** | The immutable chronological record of every stock movement event for a product at a warehouse. The authoritative source of truth. |
| **Inventory Adjustment** | A formal correction to recorded stock quantities. Requires a reason code; may require approval. Creates an immutable ledger entry. |
| **Stock Transfer** | A formal movement of stock from one warehouse to another within the same company. Executed in two steps: Dispatch (→ In Transit) and Confirmed Receipt (→ Completed). |
| **Dead Stock** | Products with no stock movement for a configurable period (default: 90 days). Indicates obsolescence risk. |
| **Fast Moving** | Products with high stock movement frequency — strong demand or high throughput. |
| **Slow Moving** | Products with infrequent stock movement — low demand. Distinct from Dead Stock in that some movement still occurs. |
| **Inventory Valuation** | Total monetary value of on-hand inventory, calculated using the company's selected cost method. Feeds into the Accounting balance sheet. |
| **Weighted Average Cost (WAC)** | Unit cost recalculated as a weighted average each time stock is received. New cost = (existing qty × existing cost + received qty × received cost) ÷ (existing qty + received qty). |
| **FIFO** | First In, First Out. Cost of the earliest inventory acquired is applied to goods sold first. |
| **Stock Aging** | Analysis of how long current inventory has been held, categorised in time buckets (0–30, 31–90, 91–180, 180+ days). |
| **Inventory Snapshot** | An immutable, point-in-time record of all stock positions. Used for audit, reporting, and reconciliation. |
| **Negative Stock Policy** | Company-level configuration. Options: Strict (blocked), Allow with Warning, Allow Silently. |
| **Domain Event** | A business-significant occurrence published to the event bus for consumption by other bounded contexts. |
| **Bounded Context** | A DDD boundary within which a domain model applies. The Inventory domain owns its model and publishes events for others. |
| **Aggregate Root** | The primary DDD entity through which all operations on a cluster pass. Enforces domain invariants. |
| **Tenant** | A company using DevSphere ERP. All Inventory data strictly scoped via company_id. |
| **RBAC** | Role-Based Access Control. The permission system from Epic 4 governing what each role may do in the Inventory domain. |

---

## 56. Acceptance Criteria

### 56.1 Product Master

- [ ] A user with `inventory:product:create` permission can create a product with all mandatory fields and activate it
- [ ] Creating a product with a duplicate SKU produces a clear validation error
- [ ] Creating a product with a duplicate barcode produces a clear validation error
- [ ] A product with variants tracks stock at the variant level, not the product level
- [ ] Archiving a product succeeds; the product is invisible in operational views but present in historical reports
- [ ] Full-text search returns a product when searching by name, code, SKU, or configured keyword
- [ ] A barcode scan returns the correct product or variant immediately

### 56.2 Inventory Operations

- [ ] Opening stock recorded for a product results in Current Stock matching the opening quantity
- [ ] Available Stock = Current Stock − Reserved Stock − Damaged Stock at all times (verified by automated test)
- [ ] A stock-out movement blocked when Negative Stock Policy is Strict and stock is insufficient
- [ ] An inventory adjustment with reason code creates an immutable ledger entry and updates stock position
- [ ] A low stock alert generated exactly once when Available Stock falls below the configured threshold
- [ ] Inventory valuation (WAC) matches manual calculation for a sequence of inbound and outbound movements

### 56.3 Warehouse Management

- [ ] A company can create multiple warehouses with independent stock tracked per warehouse
- [ ] A stock transfer creates a two-step process: dispatch reduces source; receipt increases destination
- [ ] In-transit stock is not available for sale during the transfer
- [ ] Archiving a warehouse with non-zero stock is blocked with a clear error message

### 56.4 RBAC and Security

- [ ] A Sales User can view product catalogue and available stock but cannot create or adjust products
- [ ] An Auditor can view all inventory data and audit records but cannot modify any entity
- [ ] A user from Company A cannot access any inventory data from Company B

### 56.5 Audit

- [ ] Every product creation, update, status change, stock movement, and adjustment produces a corresponding audit record
- [ ] Audit record includes: entity_id, operation, changed_fields, performed_by, performed_at

### 56.6 Import and Export

- [ ] Bulk product import of 1,000 rows via Excel completes within 60 seconds with row-level error reporting
- [ ] Product catalogue export returns all products with current stock quantities in correctly formatted Excel

### 56.7 Performance

- [ ] Product search with filters returns results in under 500ms under normal load
- [ ] Stock position query for a single product across all warehouses returns in under 300ms
- [ ] Inventory snapshot for 10,000 product lines generates in under 5 seconds

---

## 57. Epic Completion Criteria

Epic 5 is considered **complete** when all of the following conditions are satisfied:

| Criterion | Verification |
| --- | --- |
| All P1 Functional Requirements implemented | Verified against FR list in Section 21 |
| All P1 Acceptance Criteria pass | Test suite execution |
| Permission matrix fully enforced | Security test suite |
| Audit trail covers 100% of write operations | Audit coverage test |
| Inventory valuation accuracy confirmed | Valuation regression test |
| Bulk import/export functional | Functional test |
| All domain events published and documented | Event integration test |
| No cross-tenant data leak | Penetration test |
| Performance targets met at p95 | Load test |
| Security requirements satisfied | Security review |
| `spec.md` approved by Product Owner and Chief Architect | Formal sign-off |
| `plan.md` derived from this spec and approved | Follows this spec |
| `tasks.md` generated and assigned | Follows `plan.md` |
| All tasks in `tasks.md` in DONE state | Implementation verification |
| Git branch `005-inventory-management` merged to `main` | GitHub PR merged |

---

## 58. Future Roadmap

### Phase 2 — Inventory Completeness

| Capability | Description |
| --- | --- |
| Physical Stock Count | Full warehouse count with system-physical reconciliation |
| Cycle Count | Rolling subset count methodology |
| Inventory Freeze | Lock warehouse stock during count or audit |
| Bin & Rack Tracking | Sub-location precision within a warehouse |

### Phase 3 — Traceability

| Capability | Description |
| --- | --- |
| Lot / Batch Tracking | Group products by batch for recall and quality management |
| Serial Number Tracking | Individual unit tracking for high-value items |
| Expiry Date Management | Date-controlled FEFO (First Expired, First Out) picking |
| Chain of Custody | Full traceability from supplier to customer |

### Phase 4 — Intelligence & Automation

| Capability | Description |
| --- | --- |
| AI Demand Forecasting | ML-driven replenishment suggestions (Epic 13) |
| Auto Reorder | Automatic Purchase Order generation at reorder level |
| Inventory Optimisation | System-suggested safety stock and min/max levels based on movement patterns |
| Slow/Dead Stock Alerts | Proactive write-down recommendations |

### Phase 5 — Integration Expansion

| Capability | Description |
| --- | --- |
| POS Integration | Real-time stock deduction from point-of-sale terminal |
| IoT Sensor Integration | Smart shelf and RFID-based automated stock tracking |
| Mobile App | Mobile-first inventory management for warehouse operators |
| Public Inventory API | External system integration for e-commerce, B2B portals |
| Third-Party ERP Connectors | SAP, Oracle, Odoo connector templates |

### Phase 6 — Enterprise Extensions

| Capability | Description |
| --- | --- |
| Multi-Currency Valuation | Inventory value in multiple currencies for international operations (§15.18 readiness already established) |
| Cross-Company Transfers | Inventory movement between related company entities |
| Tax Classification per Product | HSN codes, HS codes, VAT categories for compliance (§14.16 readiness already established) |
| Bill of Materials (BOM) | Simple BOM for assembly/kitting operations |

### Phase 7 — ERP Domain Evolution

Epic 5 intentionally establishes the data foundation, architectural contracts, and domain boundaries that enable the complete DevSphere ERP ecosystem to evolve without structural redesign. The following map represents the planned build-out order and dependency chain from the Inventory foundation:

```
┌──────────────────────────────────────────────────────────────────────┐
│                    DEVSPHERE ERP EVOLUTION MAP                       │
│                  (Foundation → Domain Expansion)                     │
└──────────────────────────────────────────────────────────────────────┘

LAYER 0: PLATFORM
  Epic 0: Engineering Constitution (Standards, Patterns, Governance)
  Epic 1: Foundation Platform (Infrastructure, DevOps, Docker)
  Epic 2: Authentication & Identity (JWT, Sessions, Security)
  Epic 3: Companies (Multi-Tenant, Company Config, S3, Audit)
  Epic 4: Users & Roles (Membership, RBAC, Permissions, Profiles)

LAYER 1: PRODUCT & INVENTORY FOUNDATION  ← THIS EPIC
  Epic 5: Inventory Management
    ├── Product Master (the permanent product catalogue)
    ├── Stock Operations (the authoritative stock ledger)
    ├── Warehouse Management (the operational location layer)
    ├── Inventory Intelligence (alerts, reorder, analytics)
    └── Branch Readiness, Multi-Currency Readiness, Procurement Metadata Readiness

LAYER 2: COMMERCIAL TRANSACTIONS (depend on Layer 1)
  Epic 6: Purchase Management
    ├── Consumes: Product Master, Warehouse List, Reorder Suggestions
    ├── Produces: Stock Receipts → fed back to Inventory Ledger
    └── Activates: Preferred Supplier, Lead Time, Purchase UOM (from §14.16)

  Epic 7: Sales Management
    ├── Consumes: Product Catalogue, Available Stock, Stock Reservation API
    ├── Produces: Stock Reservations, Dispatches, Returns → fed to Inventory Ledger
    └── Activates: Sales UOM (from §14.16)

LAYER 3: FINANCIAL INTELLIGENCE (depends on Layers 1 + 2)
  Epic 8: Accounting
    ├── Consumes: Inventory Valuation, StockIncreased/Reduced events, COGS
    ├── Provides: Base Currency confirmation, Exchange Rates (for §15.18)
    └── Activates: Tax Category on Products (from §14.16)

  Epic 9: CRM
    ├── Consumes: Product Catalogue (read-only reference)
    └── Enriches: Customer-Product relationship data

LAYER 4: POST-SALE SERVICES (depends on Layers 1–3)
  Epic 10: Warranty & Service
    ├── Consumes: Product Identity, Variant Identity from Product Master
    └── Manages: Warranty claims tied to sold products

  Epic 11: Installments
    ├── Consumes: Sales Order data + Product Identity
    └── Manages: Payment schedule for credit-based sales

LAYER 5: INTELLIGENCE & OPERATIONS (depends on Layers 1–4)
  Epic 12: Reports & Analytics
    ├── Consumes: All inventory data, events, and pre-aggregated summaries
    └── Produces: Cross-module consolidated business intelligence

  Epic 13: AI & Forecasting
    ├── Consumes: Full stock movement history (the ledger from Epic 5)
    ├── Activates: EOQ calculations on Product Master (from §14.16)
    └── Produces: Demand forecasts, Auto Reorder suggestions

LAYER 6: ORGANISATIONAL EXPANSION (Future)
  Branch Management
    ├── Extends: Warehouse hierarchy (Company → Branch → Warehouse per §16.10)
    ├── Activates: Branch-scoped inventory reports and transfers
    └── Zero redesign required (readiness established in §16.10)

  International Module
    ├── Activates: Multi-currency valuation (per §15.18)
    ├── Activates: Country of Origin, Hazard Classification (per §14.16)
    └── Zero redesign of stock ledger required
```

**Strategic Principle**: Every layer is built on the stable contract published by Layer 1 (Inventory). The Product Master and Stock Ledger established in Epic 5 are the permanent foundations of the DevSphere ERP commercial ecosystem. No future Epic may require these foundations to be redesigned — they may only be extended.

---

*End of Official Enterprise Business Specification — Epic 5: Inventory Management*

*Document Version: 1.1.0 | Status: Draft — Pending Approval*
*Created: 2026-07-20 | Updated: 2026-07-20 | Branch: 005-inventory-management*
