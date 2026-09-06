# Epic 9 — CRM (Customer Relationship Management): Official Business Specification

**Feature Branch**: `009-crm`
**Created**: 2026-08-15
**Status**: Draft
**Input**: User description — DevSphere ERP Epic 9 CRM: lead management, opportunities/pipeline, activities, Customer 360, integrating with existing Sales/Accounting/Companies/RBAC domains without duplicating Customer, Sales Order, Invoice, Payment, or Accounting entities.

---

## Table of Contents

1. Executive Summary
2. Epic Overview
3. Business Vision
4. Business Goals
5. Business Scope
6. Out of Scope
7. CRM Terminology
8. Domain Philosophy
9. Domain Boundaries
10. Bounded Context
11. Stakeholders
12. User Personas
13. Business Capabilities
14. Lead Management
15. Lead Qualification
16. Lead Conversion
17. Opportunities / Deals
18. Sales Pipeline
19. CRM Activities
20. Customer 360
21. Sales Integration
22. Accounting Integration
23. Business Workflows
24. User Scenarios & Testing
25. Functional Requirements
26. Non-Functional Requirements
27. Business Rules
28. Business Invariants
29. Validation Rules
30. Multi-Tenancy
31. Permission Matrix (RBAC)
32. Feature Matrix
33. CRM Governance
34. Conceptual Domain Model
35. Aggregate Roots
36. Domain Events
37. Database Design
38. API Design
39. Frontend Requirements
40. Reporting Requirements
41. KPI Requirements
42. Search Requirements
43. Concurrency & Idempotency
44. Audit Requirements
45. Soft Delete & Data Retention
46. Security Requirements
47. Performance Targets
48. Testing Strategy
49. Cross-Module Dependencies
50. Cross-Module Contracts
51. AI Readiness
52. Multi-Tenant SaaS
53. Risks and Architectural Decisions
54. Assumptions
55. Constraints
56. Success Metrics
57. Glossary
58. Acceptance Criteria
59. Epic Completion (Exit) Criteria
60. Future Roadmap

---

## 1. Executive Summary

Epic 9 adds a Customer Relationship Management (CRM) module to DevSphere ERP: a company-scoped system for capturing leads, qualifying and converting them, tracking sales opportunities through a configurable pipeline, and logging customer-facing activities (calls, emails, meetings, tasks, notes, follow-ups). CRM is the pre-sales and relationship layer that sits in front of Epic 7 (Sales) — a Lead becomes a Customer and an Opportunity when qualified; an Opportunity becomes a Quotation and, eventually, a Sales Order, Invoice, and Payment inside the existing Sales and Accounting modules, which CRM does not duplicate.

This specification was written after inspecting the actual DevSphere ERP codebase (Epics 1–8, complete and hardened as of the pre-Epic-9 audit) — not from CRM conventions in the abstract. Every integration point below cites the real entity, service, or convention it reuses.

## 2. Epic Overview

| Attribute | Value |
|---|---|
| Epic Number | 9 |
| Epic Name | CRM (Customer Relationship Management) |
| Depends On | Epic 2 (Auth), Epic 3 (Companies), Epic 4 (Users & Roles/RBAC), Epic 7 (Sales — Customer, Quotation, Sales Order), Epic 8 (Accounting — AR/aging, read-only) |
| Feeds Into | Epic 7 (Quotation creation from a won Opportunity), future Epic 11 (Reporting/BI), future AI features |
| Architecture | Modular monolith module `backend/modules/crm/`, same shape as `modules/sales`, `modules/purchase`, `modules/accounting` |
| Feature Flag | `feature.crm.enabled` (named explicitly in `.specify/memory/constitution.md` §11 as a toggle-controlled optional module) |

## 3. Business Vision

DevSphere ERP customers currently manage the full order-to-cash cycle (Sales → Accounting) but have no structured way to track *how* a customer relationship began, *who* is pursuing it, or *what* is still in the pipeline before a Quotation exists. CRM closes that gap: a salesperson works a Lead through qualification, converts it into a Customer + Opportunity without ever leaving DevSphere ERP, and the deal then flows naturally into the existing Sales module once it is won — with zero duplicate data entry and zero duplicate customer records.

### 3.1 Long-Term Vision

CRM becomes the system of record for pre-sales relationship data (leads, opportunities, activities) while Sales/Accounting remain the systems of record for transactional and financial data. Over time, CRM's structured activity and outcome history (win/loss, source, cycle time) becomes the training data for future AI features (lead scoring, forecasting, next-best-action) — see §51.

## 4. Business Goals

- **BG-001**: Give sales teams a single place to capture and track leads from any source through to conversion.
- **BG-002**: Provide visibility into the sales pipeline (open opportunities, expected value, expected close date) without a spreadsheet.
- **BG-003**: Eliminate duplicate customer creation by making lead conversion match against existing Sales customers before creating a new one.
- **BG-004**: Preserve a complete, auditable history of customer-facing activity (calls, meetings, follow-ups) tied to the right lead, customer, or opportunity.
- **BG-005**: Give managers and executives pipeline and conversion KPIs without building a separate BI tool.
- **BG-006**: Keep CRM strictly additive to Epics 1–8 — no modification of existing Customer, Sales Order, Invoice, Payment, or GL entities/behavior.

## 5. Business Scope

### 5.1 In Scope (Epic 9 — P1)

- Lead capture, qualification, and conversion (to an existing or new Sales Customer + a new Opportunity)
- Lead sources (company-configurable) and source attribution
- Opportunities/deals with a configurable sales pipeline (stages, probability, weighted value)
- CRM activities: calls, emails, meetings, tasks, notes, follow-ups — linked to a lead, customer, and/or opportunity
- Customer 360 read-model view (CRM data + read-only Sales/Accounting data, via existing services)
- CRM-specific RBAC permission matrix, reusing the Epic 4 RBAC engine
- CRM domain events, reusing the per-module `InProcessEventBus` pattern
- CRM reporting/KPIs (pipeline value, conversion rate, win rate, activity completion, etc.)
- CRM audit trail for leads, opportunities, and significant activity changes

### 5.2 In Scope — Ready but Disabled (Feature Flags)

None at epic launch beyond the module-level `feature.crm.enabled` flag itself (see §32). Sub-feature flags may be added during planning if a capability proves risky to ship enabled-by-default (e.g., auto-assignment rules); none are pre-committed here to avoid speculative flags.

### 5.3 Out of Scope (Future Epics)

See §6 for the full list. Notably: campaign/marketing automation execution, external CRM sync, AI implementation, telephony/SMS/WhatsApp integration.

## 6. Out of Scope

Explicitly excluded from Epic 9 (documented as future extensions, not implemented speculatively):

- WhatsApp integration
- SMS gateway integration
- Email delivery infrastructure (CRM stores activity *records* of emails sent; it does not send email itself)
- Telephony/computer-telephony integration (call *logging* only, not call placing/recording)
- AI sales agent / AI implementation of any kind (only AI-*readiness*, see §51)
- Marketing automation engine
- Full campaign-management platform (a `crm_lead_sources` lookup table exists for attribution; a Campaign entity with budgets/channels/ROI tracking does not)
- Advanced BI platform (CRM ships its own reports/KPIs per §40–41 using existing reporting conventions; no separate BI product)
- External CRM synchronization (Salesforce, HubSpot, or any other third-party CRM)
- Microservices extraction, Kubernetes, or an event-sourcing rewrite of any kind
- A second RBAC system, a second audit system, or a second event bus
- Territory management, quota management, and commission calculation
- Contract/e-signature management
- Field-level opportunity forecasting categories beyond stage-derived probability (e.g., "Commit/Best Case/Pipeline" forecast categories are not modeled)

## 7. CRM Terminology

| Term | Definition |
|---|---|
| **Lead** | An unqualified prospect — a person and/or organization who has not yet been established as a Sales Customer. |
| **Qualification** | The process of determining whether a Lead is a viable sales prospect. |
| **Conversion** | The transactional act of turning a QUALIFIED Lead into a Sales Customer (existing or new) and a new Opportunity. |
| **Opportunity** (a.k.a. Deal) | A trackable, in-progress sales pursuit against a known Customer, with a monetary value, stage, and expected close date. |
| **Pipeline** | A named, ordered sequence of Stages that an Opportunity moves through. |
| **Stage** | A single step in a Pipeline, carrying a default win probability. |
| **Activity** | A single, dated interaction or task: a call, email, meeting, task, note, or follow-up, optionally linked to a Lead, Customer, and/or Opportunity. |
| **Owner** | The user assigned responsibility for a Lead or Opportunity. |
| **Weighted Value** | `opportunity.value × stage.probability`, used for pipeline forecasting. |
| **Win Rate** | Won Opportunities ÷ (Won + Lost Opportunities) in a period. |
| **Customer 360** | A read-only aggregated view of a Customer's CRM history plus Sales/Accounting summary data. |

## 8. Domain Philosophy

CRM is deliberately scoped as an **orchestration and relationship-tracking layer**, not a second transactional system. Every existing entity that already models a concern (Customer, Quotation, Sales Order, Invoice, Payment, GL) is reused by reference; CRM never re-derives or re-stores financial truth. This mirrors the Sales spec's own domain philosophy (§8 of `specs/007-sales-management/spec.md`) and the Accounting spec's insistence that only `PostingEngine` writes to the GL — CRM's equivalent invariant is: **only Sales/Accounting services compute and store transactional or financial data; CRM only reads it.**

### 8.1 Subdomain Responsibilities

- **Lead subdomain**: capture, qualification, conversion.
- **Opportunity subdomain**: pipeline tracking, forecasting metadata, win/loss.
- **Activity subdomain**: interaction history across leads, customers, and opportunities.
- **Customer 360 subdomain**: read-model composition across CRM + Sales + Accounting.

### 8.2 Design Principles

- Reuse before invention (Customer, User, Company, RBAC, event bus, audit pattern).
- Explicit nullable foreign keys over polymorphic association tables (per user's own instruction and consistent with how `DeliveryNoteLine`/`InvoiceLine` reference `order_line_id` elsewhere in Sales).
- Smallest safe footprint: no schema changes to Epic 1–8 tables.
- Every mutation is tenant-scoped, permission-checked, and — where significant — audited.

## 9. Domain Boundaries

### 9.1 What CRM Owns

- Leads and lead qualification/conversion state
- Lead sources (company-configurable lookup)
- Opportunities/deals and their pipeline position
- Pipelines and pipeline stages (company-configurable)
- CRM activities (calls, emails, meetings, tasks, notes, follow-ups)
- CRM-specific ownership/assignment metadata
- CRM audit log and CRM domain events

### 9.2 What CRM Does NOT Own

| Concern | Owner | Reused As |
|---|---|---|
| Customer master data | Epic 7 (Sales) — `modules.sales.models.customer.Customer` | CRM references `customer_id`; never duplicates fields |
| Customer contacts/addresses | Epic 7 (Sales) — `CustomerContact`, `CustomerAddress` | CRM does not create a second Contact entity |
| Sales Quotations, Orders, Deliveries, Invoices, Returns | Epic 7 (Sales) | CRM references `quotation_id` on Opportunity once created; never creates these documents itself |
| GL, journals, payments, AR/AP ledgers | Epic 8 (Accounting) | CRM reads via `AccountsReceivableService` (§22) for Customer 360; never writes |
| Inventory/stock | Epic 5 (Inventory) | Not referenced by CRM at all in this epic |
| User identity, sessions | Epic 2 (Auth) | CRM references `owner_id`/`assigned_to` as a plain user UUID, same convention as Sales' `sales_rep_id` |
| Company configuration, feature flags | Epic 3 (Companies) | CRM's own feature flag (`feature.crm.enabled`) is company-scoped the same way |
| Roles and permissions | Epic 4 (Users & Roles) | CRM registers new `crm.*` permission codes into the existing `Permission`/`RolePermission` tables — no second RBAC engine |

### 9.3 Shared Kernel

CRM reuses the following shared-kernel components, identical to every other module:

- **`TenantBaseModel`** (`core/database/models/tenant_base.py`): `id` (UUID, `server_default=gen_random_uuid()`), `company_id`, `created_by`, `is_deleted`/`deleted_at`, `created_at`/`updated_at` (`server_default=func.now()`, `updated_at` has `onupdate=func.now()`).
- **`StandardResponse[T]` / `PaginatedResponse[T]` / `PaginationParams`** (`core/schemas/response.py`, `core/schemas/pagination.py`) — the shared response envelope and 1-indexed `page`/`page_size` (max 100) pagination convention.
- **Per-module `InProcessEventBus`** pattern (`modules/sales/events/__init__.py`, `modules/accounting/events/__init__.py`) — CRM gets its own `modules/crm/events/__init__.py` with a module-level `get_event_bus()`.
- **`get_current_company_member`** dependency, applied at router-include time in `api/v1/router.py` — CRM's router is mounted the same way as Sales/Purchase/Accounting.
- **Permission catalog** (`modules/users_roles/constants.py`'s `INITIAL_PERMISSIONS` / `PermissionDefinition` tuple) — CRM adds `crm.*` entries here, seeded by the existing `RoleSeedService`.

## 10. Bounded Context

```
+---------------------------------------------------------------------------+
|                          CRM Bounded Context                              |
|                                                                            |
|  +-------------+   +----------------+   +----------------+                |
|  |    Lead     |-->|  Opportunity   |-->|   Activity     |                |
|  | (own state) |   | (own state)    |   | (own state)    |                |
|  +-------------+   +----------------+   +----------------+                |
|         |                  |                    |                        |
|         | converts to      | references         | references            |
|         v                  v                    v                        |
+---------|------------------|--------------------|------------------------+
          |                  |                    |
          v                  v                    v
 +----------------+  +----------------+   (lead_id / customer_id /
 |  Sales.Customer|  |Sales.Quotation |    opportunity_id — all
 |  (Epic 7, owned|  |(Epic 7, created|    nullable, explicit FKs)
 |   by Sales)    |  | when opp is won|
 +----------------+  +----------------+
          |
          v
 +----------------+
 |Accounting.AR    |  (read-only, via AccountsReceivableService,
 |(Epic 8, owned by|   never written by CRM)
 | Accounting)     |
 +----------------+
```

## 11. Stakeholders

| Stakeholder | Interest |
|---|---|
| Company Owner / Admin | Overall CRM configuration, pipeline setup, permission assignment |
| Sales Manager | Team pipeline visibility, lead/opportunity assignment, reporting |
| Salesperson | Working leads and opportunities assigned to them |
| Accountant | Read-only visibility into a customer's CRM history for credit/collection context |
| Auditor | Review of the CRM audit trail |
| Platform Architecture Team | Ensuring CRM does not violate the modular-monolith/shared-kernel constitution |

## 12. User Personas

Reuses the Sales spec's persona set (`specs/007-sales-management/spec.md` §12) where applicable, scoped to CRM:

### 12.1 Company Owner / Admin
Configures pipelines, lead sources, and CRM permissions for their company.

### 12.2 Sales Manager
Views the whole team's pipeline, reassigns leads/opportunities, reviews conversion and win-rate KPIs, unlocks stage changes that individual salespeople cannot make alone (e.g., marking an Opportunity Won).

### 12.3 Salesperson
Owns a personal queue of leads and opportunities; logs activities; converts qualified leads; moves their own opportunities through the pipeline.

### 12.4 Accountant
Views Customer 360 (read-only) for credit and collections context; has no CRM create/update rights.

### 12.5 Auditor / Read-Only User
Views CRM records and the CRM audit trail for compliance review; cannot mutate anything.

## 13. Business Capabilities

### 13.1 Capability Map

| Capability | Description |
|---|---|
| Lead Capture | Record a new Lead with contact/source information |
| Lead Qualification | Score and qualify/disqualify a Lead |
| Lead Conversion | Convert a Lead into a Customer + Opportunity, idempotently |
| Pipeline Management | Configure Pipelines and Stages per company |
| Opportunity Tracking | Track value, stage, probability, expected close date |
| Activity Logging | Log calls, emails, meetings, tasks, notes, follow-ups |
| Customer 360 | Aggregate CRM + read-only Sales/Accounting data per customer |
| CRM Reporting | Pipeline, conversion, activity, and salesperson performance reports |
| CRM Audit | Record who changed what and when for CRM entities |

## 14. Lead Management

### 14.1 Lead Entity

A Lead represents an unqualified prospect. Key attributes:

| Attribute | Notes |
|---|---|
| `id`, `company_id` | Standard `TenantBaseModel` fields |
| `first_name`, `last_name` | Person contact name (at least one required) |
| `lead_company_name` | The organization the lead represents (nullable — an individual/B2C lead may have none) |
| `email`, `phone`, `mobile` | Contact channels (at least one of email/phone required) |
| `address_line1/2`, `city`, `state`, `postal_code`, `country_code` | Optional address capture |
| `source_id` | FK to `crm_lead_sources` (nullable — source may be unknown at capture time) |
| `status` | Lifecycle state, see §14.2 |
| `score` | Nullable integer 0–100, manually or (future) AI-assigned |
| `owner_id` | Nullable UUID — assigned salesperson, same convention as `SalesOrder.sales_rep_id` |
| `notes` | Free text |
| `last_contact_date` | Nullable date, updated when a linked Activity is completed |
| `next_follow_up_date` | Nullable date, drives the "overdue follow-ups" report (§41) |
| `qualification_notes` | Free text captured at qualification time |
| `disqualification_reason` | Free text, required when status becomes `UNQUALIFIED` or `LOST` |
| `converted_customer_id` | Nullable UUID — set on conversion, references `sales.customers.id` |
| `converted_opportunity_id` | Nullable UUID — set on conversion, references `crm_opportunities.id` |
| `converted_at` | Nullable timestamp |
| `version` | Integer, optimistic locking (same pattern as `Customer.version`) |

### 14.2 Lead Lifecycle

```
NEW → CONTACTED → QUALIFIED → CONVERTED
 |         |            |
 |         |            +--> UNQUALIFIED
 |         +--> UNQUALIFIED
 +--> LOST
```

- **NEW**: default status on capture.
- **CONTACTED**: at least one Activity has been logged against the Lead.
- **QUALIFIED**: manager/salesperson has determined the Lead is a viable prospect (§15).
- **UNQUALIFIED**: determined not viable; terminal, but reopenable by a manager (transition back to `NEW`) if circumstances change — this is the one explicit exception to strict terminality, matching real sales practice, and is itself audited.
- **CONVERTED**: terminal — produced a Customer + Opportunity (§16).
- **LOST**: terminal — the Lead went cold/unresponsive without ever being disqualified on merit (distinct from `UNQUALIFIED`, which means "not a fit"; `LOST` means "was a fit, but did not respond/proceed").

This is a 6-state, explicitly-modeled lifecycle rather than the example lifecycle in the input brief taken verbatim — `UNQUALIFIED` and `LOST` are kept as two distinct terminal states (not merged) because they carry different reporting meaning (§41: "leads by status" must distinguish "not a fit" from "went cold" for accurate funnel analysis), and `CONTACTED` is derived from real activity rather than a manually-set flag, preventing status drift.

### 14.3 Validation Rules

- At least one of (`first_name`+`last_name`) or `lead_company_name` is required.
- At least one of `email` or `phone` is required.
- `email`, when present, must be a valid email format (reuse the Shared Kernel validation helper, constitution §48).
- `disqualification_reason` is required when transitioning to `UNQUALIFIED` or `LOST`.
- Invalid state transitions are rejected with a 409 Conflict (matching the Sales/Accounting pattern of `ConflictException`/`InvalidJournalStateTransitionError`-style typed exceptions).

## 15. Lead Qualification

Qualification is a status transition (`NEW`/`CONTACTED` → `QUALIFIED` or `UNQUALIFIED`), not a separate entity. It requires:

- `qualification_notes` to be set (or already present) at the time of the transition.
- A permission check: `crm.leads.update` at minimum; qualifying is not a separately-permissioned action from updating a lead, since it is just a constrained status change (unlike Opportunity win/loss, which — per §17.3 — does carry review implications and is not separately gated either, kept consistent).

Score (`score` field) may be set manually by the owner/manager at any point; automated/AI-assigned scoring is explicitly out of scope for Epic 9 (§51) — the field exists so a future scoring job has somewhere to write.

## 16. Lead Conversion

Conversion is the highest-risk operation in CRM and is designed carefully per the input brief's explicit requirements.

### 16.1 Conversion Targets

Converting a `QUALIFIED` Lead produces:

1. A Sales `Customer` — either:
   - **Matched to an existing Customer** in the same company, by (in order of preference) exact `email` match, then exact `phone` match, then exact `legal_name` match (case-insensitive) — all scoped to `company_id`. If matched, no new Customer is created; the existing `customer_id` is used.
   - **A new Customer** — created via the existing `modules.sales.services.customer_service.CustomerService.create()` (reused, not duplicated), populated from the Lead's contact fields. The new Customer is created in `DRAFT` status, matching Sales' own default lifecycle entry point (`specs/007-sales-management/spec.md` §14.1) — CRM does not invent a different default status for a Sales entity.
2. A new `Opportunity`, `status=OPEN`, `source_lead_id` set to the originating Lead, `customer_id` set to the matched/created Customer, in the company's default `Pipeline` at its first `Stage`.

### 16.2 Conversion Transaction Boundary

The entire conversion (customer match-or-create, opportunity create, lead status update to `CONVERTED` with `converted_customer_id`/`converted_opportunity_id`/`converted_at` set, audit record, event publication) executes in **one database transaction with exactly one commit** at the end. This is a direct, explicit application of the pre-Epic-9 hardening audit's central finding (missing-commit defects silently losing data across Inventory/Purchase/Sales write paths) — CRM's conversion service MUST NOT repeat that defect class. All intermediate writes use `flush()` only; the single `commit()` happens after every step succeeds, so a failure at any point (e.g., a permission or validation error) rolls back the entire conversion atomically, leaving the Lead untouched.

### 16.3 Idempotency & Duplicate Prevention

- **Idempotent by design**: the Lead's own `status` field is the idempotency guard. `convert_lead()` first checks `status == QUALIFIED`; if the Lead is already `CONVERTED`, the endpoint returns the existing `converted_customer_id`/`converted_opportunity_id` with a 200 (not an error) rather than attempting a second conversion — a duplicate/retried request is handled safely.
- **Race condition**: two concurrent conversion requests for the same Lead are resolved by the Lead's `version` column (optimistic locking, same pattern as `Customer.version`) — the second request's `UPDATE ... WHERE version = :expected_version` affects zero rows, and the service detects this and re-reads the Lead; if it is now `CONVERTED`, it returns the (now-existing) conversion result idempotently rather than erroring, avoiding a duplicate Customer/Opportunity from a genuine race.
- **No distributed locking** is introduced — the existing optimistic-locking + single-transaction pattern is sufficient, consistent with the input brief's explicit "do not add unnecessary distributed locking" instruction.

### 16.4 Failure / Rollback Behavior

If Customer creation fails validation (e.g., a required Sales-side field is missing), the entire conversion fails with a 422 and the Lead remains `QUALIFIED` — nothing is partially converted. This is enforced structurally by the single-transaction design in §16.2, not by manual compensating logic.

### 16.5 Conversion Audit Trail

A conversion audit record captures: lead_id, resulting customer_id (and whether it was matched or newly created), resulting opportunity_id, actor_user_id, timestamp. See §44.

## 17. Opportunities / Deals

### 17.1 Opportunity Entity

| Attribute | Notes |
|---|---|
| `id`, `company_id` | Standard fields |
| `name` | Short deal name, e.g. "Acme Corp — Q3 Equipment Order" |
| `customer_id` | **Required** UUID FK to `sales.customers.id` — an Opportunity always has a known Customer (a prospect without a Customer record is a Lead, not yet an Opportunity) |
| `owner_id` | UUID, required — assigned salesperson |
| `pipeline_id`, `stage_id` | Current position in the pipeline (§18) |
| `value` | `Numeric(15,2)`, matching the monetary-value convention used throughout Sales/Accounting |
| `currency_code` | ISO 4217, matching `Customer.currency_code`/`SalesOrder.currency_code` |
| `probability` | Integer 0–100; defaults to the current stage's probability but is independently overridable per opportunity |
| `weighted_value` | Computed, not stored redundantly as an editable field: `value × probability / 100` |
| `expected_close_date` | Date |
| `source_lead_id` | Nullable UUID — set when the Opportunity originated from a Lead conversion (§16); null for a manually-created Opportunity against an existing Customer |
| `description` | Free text |
| `status` | `OPEN`, `WON`, `LOST` |
| `lost_reason` | Required when `status=LOST` |
| `won_at`, `lost_at` | Nullable timestamps |
| `quotation_id` | Nullable UUID FK to `sales.sales_quotations.id` — set once a Quotation is created against this Opportunity (§21); CRM never creates the Quotation row itself |

### 17.2 Opportunity Lifecycle

```
OPEN --(stage progression within OPEN)--> OPEN
OPEN --win()--> WON   (terminal)
OPEN --lose(reason)--> LOST   (terminal)
```

- Stage changes are only valid while `status=OPEN`.
- `win()` requires the Opportunity to currently be in a stage flagged `is_won_stage=false` → transitions status to `WON`, sets `won_at`, and (if the target pipeline stage is itself a designated "Closed Won" stage) also moves `stage_id` to that stage — win/loss and final-stage placement happen atomically in one call, not as two separate client requests, to avoid an inconsistent intermediate state.
- `lose(reason)` is symmetric, requiring `lost_reason`.
- Once `WON` or `LOST`, no further stage or value changes are permitted (terminal, matching the Sales Order/Invoice "no backward transition from a terminal state" pattern already established in `posting_engine.py`'s `JournalEntryStateMachine`).

### 17.3 Business Rules

- `probability` MUST be between 0 and 100.
- `value` MUST be ≥ 0.
- `weighted_value` is always server-computed at read time (or denormalized on write for report-query performance, per §47) — never client-supplied.
- Reassigning `owner_id` does not change pipeline stage or value.
- An Opportunity's `customer_id` is immutable after creation (matching `Customer.customer_code`'s own immutability precedent) — correcting a wrong customer requires creating a new Opportunity, not repointing an existing one, to preserve pipeline/forecast history integrity.

## 18. Sales Pipeline

### 18.1 Pipeline Entity

| Attribute | Notes |
|---|---|
| `id`, `company_id` | Standard fields |
| `name` | e.g. "Standard Sales Pipeline" |
| `is_default` | Exactly one active Pipeline per company MUST be `is_default=true` (enforced via a partial unique index, §37) |
| `is_active` | Soft-disable without deleting |

### 18.2 Pipeline Stage Entity

| Attribute | Notes |
|---|---|
| `id`, `company_id`, `pipeline_id` | Standard + parent FK |
| `name` | e.g. "Qualification", "Proposal Sent", "Negotiation", "Closed Won", "Closed Lost" |
| `sequence` | Integer, defines display/progression order within the pipeline |
| `probability` | Integer 0–100, default probability an Opportunity inherits on entering this stage |
| `is_won_stage`, `is_lost_stage` | At most one stage per pipeline may be `is_won_stage=true`; at most one may be `is_lost_stage=true` |
| `is_active` | Soft-disable |

No workflow engine, stage-transition rule engine, or per-stage approval matrix is introduced — stage order is a simple `sequence` integer and any OPEN opportunity may move to any active stage in its pipeline (forward or backward), matching the input brief's explicit "avoid overengineering... do not introduce a complex workflow engine" instruction. Pipeline and Stage CRUD is a company-configuration concern (`crm.pipeline.manage` permission, §31), not a per-opportunity workflow.

## 19. CRM Activities

### 19.1 Activity Entity

A single, unified Activity entity (not one table per activity type) per the input brief's explicit instruction:

| Attribute | Notes |
|---|---|
| `id`, `company_id` | Standard fields |
| `activity_type` | `CALL`, `EMAIL`, `MEETING`, `TASK`, `NOTE`, `FOLLOW_UP` |
| `subject` | Required short text |
| `description` | Free text |
| `status` | `PLANNED`, `COMPLETED`, `CANCELLED` |
| `priority` | `LOW`, `MEDIUM`, `HIGH` |
| `due_date` | Nullable datetime |
| `completed_at` | Nullable timestamp, set when status → `COMPLETED` |
| `assigned_to` | UUID, required — same convention as `owner_id` elsewhere |
| `lead_id` | Nullable UUID FK to `crm_leads.id` |
| `customer_id` | Nullable UUID FK to `sales.customers.id` |
| `opportunity_id` | Nullable UUID FK to `crm_opportunities.id` |

**Design decision**: explicit nullable FK columns (`lead_id`, `customer_id`, `opportunity_id`), not a polymorphic `(related_type, related_id)` pair. This matches the input brief's explicit instruction ("avoid polymorphic database designs... prefer explicit nullable foreign keys") and is consistent with how `InvoiceLine.delivery_note_line_id`/`order_line_id` are modeled as separate explicit nullable columns rather than a generic polymorphic reference, elsewhere in this codebase.

### 19.2 Validation Rules

- At least one of `lead_id`, `customer_id`, `opportunity_id` MUST be set — an Activity must relate to something.
- `completed_at` is set automatically by the `complete` transition, never client-supplied directly.
- Completing an Activity linked to a Lead updates that Lead's `last_contact_date` (§14.1) — this is the mechanism by which a Lead transitions `NEW`→`CONTACTED` (§14.2): the first completed Activity against a `NEW` Lead auto-advances its status.

## 20. Customer 360

### 20.1 Purpose

A single read-model endpoint (`GET /crm/customers/{customer_id}/360`) that composes, for a given Sales Customer:

- Customer core fields (from `sales.customers`, read via the existing `CustomerService`/`CustomerRepository` — not duplicated)
- CRM history: originating Lead (if any), all Opportunities (open/won/lost) for this customer, recent Activities
- Sales history (counts/summaries only, via existing Sales repositories): quotations, orders, invoices, deliveries — CRM does not re-fetch or re-render full documents, only summary counts/links
- Accounting summary (read-only, via `AccountsReceivableService`, §22): `get_customer_ledger()` (`total_outstanding_base`, `credit_status`), `get_customer_aging()`
- `last_interaction` (most recent completed Activity date across all linked records) and `next_follow_up` (earliest open `due_date` across linked Activities/Leads)

### 20.2 Explicit Non-Duplication Rule

Customer 360 NEVER stores a cached/duplicated copy of financial values. Every financial figure is fetched live from Accounting's services on each request. This directly implements the input brief's instruction: "CRM should NOT duplicate financial values... CRM is primarily an orchestration/read-model layer."

## 21. Sales Integration

### 21.1 Relationship Chain

```
Lead → (convert) → Customer + Opportunity → (win) → Quotation → Sales Order → Delivery → Invoice → Payment
```

- **Lead → Customer + Opportunity**: synchronous, transactional, described in §16.
- **Opportunity → Quotation**: NOT automatic. Per the input brief's explicit instruction ("do not force automatic transitions unless explicitly justified"), winning an Opportunity does not itself create a Sales Quotation. Instead, the CRM UI provides a "Create Quotation" action from an OPEN or WON Opportunity that navigates to Sales' existing quotation-creation flow, pre-filled with `customer_id` and the Opportunity's line-level intent is NOT modeled by CRM (Opportunity has a single aggregate `value`, not lines — line-level detail belongs to the Quotation, avoiding duplication of Sales' own line-item model). Once a Quotation is created this way, its `id` is written back onto `Opportunity.quotation_id` for traceability.
- **Quotation → Sales Order → Delivery → Invoice → Payment**: entirely within Epic 7/8, unchanged; CRM has no involvement beyond having the initial `quotation_id` link for Customer 360 traceability.

### 21.2 Events Consumed

CRM subscribes (via its own module's handler registration function, `register_crm_integration_handlers()`, wired in `main.py` the same way `register_integration_handlers()` is for Accounting) to:

- `sales.quotation.accepted` — no state change forced on the Opportunity, but surfaced in Customer 360 timeline.
- `sales.order.credit_hold` (existing event, see `specs/007-sales-management/spec.md` §34.3) — optionally logged as a CRM Activity/note for salesperson visibility, not a blocking action.

No event subscription forces an automatic Opportunity stage change — a human always confirms pipeline movement, consistent with §18.1's "no workflow engine" decision.

## 22. Accounting Integration

CRM does not own accounting data and creates no financial ledgers. For Customer 360 (§20) and CRM reporting (§40), CRM calls, read-only:

- `modules.accounting.services.ar_service.AccountsReceivableService.get_customer_ledger(company_id, customer_id)` — outstanding balance, credit status
- `.get_customer_aging(company_id, customer_id, as_of_date)` — aging bucket summary
- `.get_customer_statement(company_id, customer_id, from_date, to_date)` — for a detailed Customer 360 drill-down, if needed

No new Accounting endpoints are required — these are existing, already-tested service methods (verified present as of the pre-Epic-9 hardening audit).

## 23. Business Workflows

### 23.1 Workflow: Web Lead to Won Deal

1. A Lead is captured (`NEW`, source = "Website").
2. A salesperson calls the Lead, logs a `CALL` Activity → Lead auto-advances to `CONTACTED`.
3. Salesperson qualifies the Lead (`QUALIFIED`, qualification notes recorded).
4. Salesperson converts the Lead → Customer (new, no match found) + Opportunity created in the default Pipeline's first Stage.
5. Salesperson progresses the Opportunity through stages, logging Activities (meetings, follow-ups) along the way.
6. Salesperson creates a Quotation from the Opportunity; Quotation is accepted in Sales; Opportunity is marked `WON`.
7. Sales converts the Quotation to a Sales Order, delivers, invoices, and collects payment — entirely in Epic 7/8.
8. Customer 360 for this customer now shows the full history: original lead source, activities, the won opportunity, and live financial summary.

### 23.2 Workflow: Duplicate-Safe Conversion

1. A Lead is captured with an email matching an existing Sales Customer.
2. Salesperson qualifies and converts the Lead.
3. Conversion matches the existing Customer by email (§16.1) — no duplicate Customer is created; the Opportunity is created against the existing Customer.

### 23.3 Workflow: Lost Deal

1. An OPEN Opportunity's prospect goes silent.
2. Manager or owner marks the Opportunity `LOST` with a reason.
3. Opportunity becomes read-only (terminal); appears in "lost value" and "lost reasons" reporting (§41).

## 24. User Scenarios & Testing

### User Story 1 - Capture and convert a qualified lead (Priority: P1)

A salesperson captures a new Lead, logs contact activity, qualifies it, and converts it into a Customer and Opportunity without creating a duplicate customer record.

**Why this priority**: This is the entry point of the entire CRM module — without it, nothing downstream (pipeline, activities, Customer 360) has data to operate on.

**Independent Test**: Can be fully tested by creating a Lead via the API, completing a Call activity against it, qualifying it, and calling convert — and delivers a verifiable Customer + Opportunity pair with correct traceability, independent of any pipeline or activity-reporting feature.

**Acceptance Scenarios**:

1. **Given** a NEW Lead with no matching existing Customer, **When** it is qualified and converted, **Then** a new Customer (status DRAFT) and a new OPEN Opportunity are created, and the Lead's status becomes CONVERTED with `converted_customer_id`/`converted_opportunity_id` populated.
2. **Given** a QUALIFIED Lead whose email matches an existing Customer, **When** it is converted, **Then** no new Customer is created — the existing `customer_id` is reused on the new Opportunity.
3. **Given** an already-CONVERTED Lead, **When** convert is called again, **Then** the endpoint returns 200 with the existing conversion result, not a duplicate.

---

### User Story 2 - Track opportunities through a pipeline (Priority: P1)

A salesperson and their manager track the value and stage of every open deal, and can see weighted pipeline totals.

**Why this priority**: This is CRM's core value proposition for sales management — pipeline visibility.

**Independent Test**: Can be fully tested by creating an Opportunity directly against an existing Customer (no Lead required), moving it through stages, and verifying the pipeline report reflects correct weighted values — independent of the lead-conversion flow.

**Acceptance Scenarios**:

1. **Given** an OPEN Opportunity in stage "Qualification" (probability 20%) with value 10,000, **When** queried, **Then** `weighted_value` = 2,000.
2. **Given** an OPEN Opportunity, **When** it is moved to a stage flagged `is_won_stage`, **Then** its status becomes WON, `won_at` is set, and further edits are rejected.
3. **Given** an OPEN Opportunity, **When** `lose()` is called without a `lost_reason`, **Then** the request is rejected with a validation error.

---

### User Story 3 - Log and complete activities (Priority: P2)

A salesperson logs calls, meetings, and follow-ups against leads, customers, and opportunities, and completes them to keep the relationship history current.

**Why this priority**: Activities are the evidentiary backbone of CRM but the module still delivers value (lead tracking, pipeline) even before activity logging is used team-wide.

**Independent Test**: Can be fully tested by creating an Activity linked to an existing Customer, completing it, and verifying it appears in that Customer's 360 view and in the "overdue follow-ups" report before/after completion.

**Acceptance Scenarios**:

1. **Given** a NEW Lead, **When** a CALL activity linked to it is completed, **Then** the Lead's status becomes CONTACTED and its `last_contact_date` is updated.
2. **Given** an Activity with `due_date` in the past and `status=PLANNED`, **When** the overdue-follow-ups report is queried, **Then** it appears in the results.

---

### User Story 4 - View Customer 360 (Priority: P2)

A manager or accountant views a single aggregated page for a customer: CRM history, sales history summary, and live financial standing.

**Why this priority**: High value for cross-functional users (accountant, manager) but depends on Stories 1–3 having produced data.

**Independent Test**: Can be fully tested by requesting Customer 360 for an existing Customer with no CRM history at all and verifying it degrades gracefully (empty CRM sections, correct live financial data) — independent of whether any lead/opportunity exists for that customer.

**Acceptance Scenarios**:

1. **Given** a Customer with an outstanding AR balance, **When** Customer 360 is requested, **Then** the returned `outstanding_balance` matches `AccountsReceivableService.get_customer_ledger()`'s live value exactly (never a cached CRM copy).
2. **Given** a Customer with zero CRM activity, **When** Customer 360 is requested, **Then** the response succeeds (200) with empty leads/opportunities/activities arrays, not an error.

---

### User Story 5 - Configure pipeline and RBAC (Priority: P3)

A company owner configures their sales pipeline stages and confirms only appropriate roles can manage it.

**Why this priority**: Necessary for a production-ready company setup but pipelines ship with a sensible default, so this is not on the critical path for MVP usage.

**Independent Test**: Can be fully tested by attempting pipeline-stage mutation as a Salesperson (expect 403) and as an Owner (expect success) — independent of lead/opportunity/activity data existing.

**Acceptance Scenarios**:

1. **Given** a user with only `crm.opportunities.*` permissions, **When** they attempt to create a Pipeline Stage, **Then** the request is rejected with 403.
2. **Given** a company with no pipeline configured, **When** CRM is first enabled, **Then** a default Pipeline with a sensible default stage set is provisioned automatically.

### Edge Cases

- What happens when a Lead is converted but the matched existing Customer is soft-deleted (`is_deleted=true`)? → Conversion MUST treat a soft-deleted Customer as non-matching (excluded from the match query) and create a new Customer instead, never resurrecting or attaching to a deleted record.
- What happens when an Opportunity's Pipeline or Stage is soft-disabled (`is_active=false`) while the Opportunity is still OPEN? → The Opportunity keeps its current `stage_id` (no forced migration); only *new* stage-change requests are prevented from selecting an inactive stage.
- What happens when two Activities are completed simultaneously for the same Lead? → Both complete independently (Activities are independent rows); `last_contact_date` is set to `GREATEST(current value, this completion's timestamp)`, so out-of-order completion never regresses the date.
- What happens when a company deletes (soft-deletes) a Pipeline that has OPEN Opportunities referencing it? → Rejected — a Pipeline with any OPEN Opportunity cannot be deactivated (mirrors the Sales `SupplierArchiveBlockedError`-style guard pattern for "cannot archive while in-use").
- What happens when `crm.leads.convert` is attempted on an `UNQUALIFIED` or already-`LOST` Lead? → Rejected with 409, matching §14.3's invalid-transition rule.

## 25. Functional Requirements

- **FR-001**: System MUST allow authorized users to create, read, update, and soft-delete Leads within their company.
- **FR-002**: System MUST enforce the Lead status lifecycle in §14.2, rejecting invalid transitions.
- **FR-003**: System MUST allow qualifying or disqualifying a Lead, requiring a reason on disqualification.
- **FR-004**: System MUST convert a QUALIFIED Lead into a Customer (matched or newly created) and a new Opportunity in one atomic transaction.
- **FR-005**: System MUST detect and reuse an existing Customer during conversion by email, then phone, then legal name (case-insensitive), scoped to `company_id`, excluding soft-deleted Customers.
- **FR-006**: System MUST make lead conversion idempotent — a repeated conversion request against an already-CONVERTED Lead returns the existing result rather than creating duplicates.
- **FR-007**: System MUST allow creating and managing Opportunities against an existing Customer, independent of Lead conversion.
- **FR-008**: System MUST enforce the Opportunity lifecycle in §17.2 (OPEN → WON | LOST, terminal).
- **FR-009**: System MUST compute `weighted_value` from `value` and `probability` and never accept it as client-supplied input.
- **FR-010**: System MUST allow companies to configure one or more Pipelines, each with one or more Stages, with exactly one default Pipeline.
- **FR-011**: System MUST provide a unified Activity entity supporting CALL/EMAIL/MEETING/TASK/NOTE/FOLLOW_UP types, each optionally linked to a Lead, Customer, and/or Opportunity (at least one required).
- **FR-012**: System MUST auto-advance a NEW Lead to CONTACTED when its first linked Activity is completed, and update `last_contact_date`.
- **FR-013**: System MUST provide a Customer 360 read endpoint composing CRM data with live (never cached) Sales and Accounting summary data.
- **FR-014**: System MUST enforce company/tenant isolation on every CRM entity at the repository, service, and API layers — not the frontend alone.
- **FR-015**: System MUST enforce RBAC permission checks (`crm.*` codes) on every CRM mutation, reusing the Epic 4 permission engine.
- **FR-016**: System MUST record an audit entry for lead creation, lead assignment, lead status change, lead conversion, opportunity creation, opportunity stage change, opportunity assignment, and opportunity won/lost — per the input brief's explicit list.
- **FR-017**: System MUST publish domain events for the significant lifecycle transitions listed in §36, via CRM's own `InProcessEventBus` instance.
- **FR-018**: System MUST provide paginated, filtered list endpoints for Leads, Opportunities, and Activities using the shared `PaginationParams`/`PaginatedResponse[T]` convention (max page size 100).
- **FR-019**: System MUST provide the CRM reports/KPIs enumerated in §40–41.
- **FR-020**: System MUST gate the entire CRM module behind the `feature.crm.enabled` company-level feature flag; when disabled, all CRM endpoints return a consistent, documented error response (matching the constitution §11 rule).
- **FR-021**: System MUST prevent deactivating a Pipeline or Stage that has any OPEN Opportunity currently positioned on it.
- **FR-022**: System MUST treat a soft-deleted Customer as non-matching during lead-conversion duplicate detection.

### Key Entities

- **Lead**: An unqualified prospect captured with contact info, source, and status; converts into a Customer + Opportunity.
- **LeadSource**: A company-configurable lookup value describing how a Lead was acquired.
- **Opportunity**: A trackable sales pursuit against a known Customer, with value, pipeline position, and win/loss outcome.
- **Pipeline**: A named, company-configurable ordered sequence of Stages.
- **PipelineStage**: A single step in a Pipeline carrying a default win probability.
- **Activity**: A single dated interaction or task (call/email/meeting/task/note/follow-up), linked to a Lead, Customer, and/or Opportunity.
- **Customer** *(reused, not owned)*: Sales' existing customer master (`modules.sales.models.customer.Customer`).

## 26. Non-Functional Requirements

- **NFR-001**: List endpoints (Leads, Opportunities, Activities) MUST return within 300ms p95 for a company with 100,000 records, matching the Sales spec's own customer-search target (§59.1 AC-02 of `specs/007-sales-management/spec.md`).
- **NFR-002**: Lead conversion MUST complete within 2 seconds p95 (comparable to Accounting's payment-processing target).
- **NFR-003**: Customer 360 composition MUST complete within 1 second p95 for a customer with up to 500 combined CRM/Sales/Accounting records (bounded by pagination on each sub-section, §37/§42).
- **NFR-004**: The pipeline/forecast report (§40) MUST return within 2 seconds p95 for a company with 10,000 open Opportunities.
- **NFR-005**: All monetary fields MUST use `Numeric(15,2)` (never floating point), matching every existing Sales/Accounting/Purchase monetary column.

## 27. Business Rules

- **BR-001**: A Lead cannot be converted unless its status is `QUALIFIED`.
- **BR-002**: An Opportunity's `customer_id` is immutable after creation.
- **BR-003**: An Opportunity cannot be edited (value, stage, probability) once `WON` or `LOST`.
- **BR-004**: `lost_reason` is mandatory when an Opportunity is marked `LOST`.
- **BR-005**: `disqualification_reason` is mandatory when a Lead is marked `UNQUALIFIED` or `LOST`.
- **BR-006**: An Activity must be linked to at least one of Lead, Customer, or Opportunity.
- **BR-007**: A Pipeline Stage cannot be deactivated while any OPEN Opportunity currently occupies it.
- **BR-008**: Exactly one Pipeline per company may be `is_default=true` at any time.
- **BR-009**: Lead-conversion duplicate matching never attaches to a soft-deleted Customer.
- **BR-010**: `weighted_value` is always derived (`value × probability / 100`), never independently editable.

## 28. Business Invariants

- **INV-001**: Every CRM-owned row has a non-null `company_id` matching the authenticated caller's company at write time.
- **INV-002**: A CONVERTED Lead always has both `converted_customer_id` and `converted_opportunity_id` populated — never one without the other.
- **INV-003**: A WON or LOST Opportunity always has its corresponding `won_at`/`lost_at` timestamp populated.
- **INV-004**: An Opportunity's `stage_id` always belongs to its own `pipeline_id` (never a stage from a different pipeline).

## 29. Validation Rules

- Lead: see §14.3.
- Opportunity: `value >= 0`; `probability` between 0–100; `expected_close_date` optional but, if present, MUST NOT be in the past at creation time (a warning, not a hard block, since legitimate backdated data entry occurs — reject only genuinely malformed dates, not "past" dates, matching how Sales does not hard-block backdated documents either).
- Pipeline Stage: `sequence >= 1`; at most one `is_won_stage=true` and at most one `is_lost_stage=true` per pipeline.
- Activity: `subject` required, 1–300 characters; at least one relation FK set (BR-006); `due_date` required when `activity_type=TASK` or `FOLLOW_UP` (a call/email/meeting/note may be logged after the fact with no future due date, but a task/follow-up is inherently forward-looking).

## 30. Multi-Tenancy

### 30.1 Tenant Isolation

Every CRM-owned table includes `company_id` (via `TenantBaseModel`). Every repository method accepting an entity `id` MUST also accept and filter by `company_id` in the same query — the established codebase pattern (`BaseRepository.get_by_id_or_none(id, company_id)`), not a two-step "fetch then check" pattern (which the pre-Epic-9 hardening audit flagged as latent-risk elsewhere in this codebase, e.g. `JournalLineRepository.find_by_journal_entry` — CRM must not repeat that gap).

### 30.2 Cross-Tenant Access Prevention

- `GET`/`PUT`/`DELETE` on a CRM resource by `id` MUST filter by the caller's `company_id`; a resource belonging to another company returns 404 (matching the existing convention across Sales/Purchase/Accounting — not 403, to avoid confirming existence to an unauthorized caller).
- The router-level `get_current_company_member` dependency (applied at `include_router()` time, same as every other module) confirms the caller belongs to the `company_id` in the URL path before any CRM handler runs.

### 30.3 Ownership Validation

- `owner_id` / `assigned_to` on Lead/Opportunity/Activity is validated at write time to be an active member of the same company (via `CompanyMemberRepository`) — assigning a lead to a user with no membership in that company is rejected with 422.

### 30.4 Foreign-Entity Company Validation

- Every cross-module reference (`customer_id` on Opportunity/Activity, `source_lead_id`, `quotation_id`) MUST be validated, at write time, to belong to the SAME `company_id` as the CRM record referencing it — a direct, explicit application of the pre-Epic-9 hardening audit's Finding 2 (the cross-tenant `payment_term_id` lookup bug in `invoice_service.py`, now fixed). CRM's own conversion and opportunity-creation services MUST scope every such lookup by `company_id`, not merely by the foreign entity's raw `id`.

## 31. Permission Matrix (RBAC)

CRM reuses the Epic 4 RBAC engine exactly: permission codes are registered in `modules/users_roles/constants.py`'s permission catalog (the `PermissionDefinition(code, label, module, action, description)` tuple, seeded idempotently by the existing `RoleSeedService`) and checked via a new, CRM-local `user_has_crm_permission(db, company_id, user_id, permission_code)` helper — the same generic-on-`permission_code` shape as Accounting's `user_has_accounting_permission` (`modules/accounting/services/permission_check.py`), reused as a pattern, not literally imported cross-module (each module owns its own thin wrapper, matching the codebase's existing per-module convention — there is no shared cross-module permission-check function today).

**Architectural decision** (see §53): CRM follows Accounting's *real, enforced* fine-grained RBAC pattern, not Sales/Purchase's current auth-only pattern (confirmed during research for this spec: Sales and Purchase routers only apply `Depends(require_authenticated)`, with no per-permission checks anywhere). This is justified because CRM introduces owner-based, assignable records containing customer-relationship and deal-value data across multiple roles with genuinely different access needs (a Salesperson should not see another Salesperson's private pipeline by default in a mature CRM, though Epic 9 does not go that far — see §53 for the explicit decision *not* to implement per-record ownership filtering in this epic, only role-based access).

### 31.1 Permission Codes

| Permission | Description |
|---|---|
| `crm.leads.view` | View leads |
| `crm.leads.create` | Create leads |
| `crm.leads.update` | Update leads, including qualify/disqualify |
| `crm.leads.delete` | Soft-delete leads |
| `crm.leads.assign` | Reassign lead ownership |
| `crm.leads.convert` | Convert a qualified lead |
| `crm.opportunities.view` | View opportunities |
| `crm.opportunities.create` | Create opportunities |
| `crm.opportunities.update` | Update opportunities, including stage changes |
| `crm.opportunities.delete` | Soft-delete opportunities |
| `crm.opportunities.assign` | Reassign opportunity ownership |
| `crm.opportunities.close` | Mark an opportunity WON or LOST |
| `crm.activities.view` | View activities |
| `crm.activities.create` | Create activities |
| `crm.activities.update` | Update/complete activities |
| `crm.activities.delete` | Soft-delete activities |
| `crm.pipeline.view` | View pipelines/stages |
| `crm.pipeline.manage` | Create/update/deactivate pipelines and stages |
| `crm.reports.view` | View CRM reports/KPIs/dashboard |

Only 19 permission codes are introduced — no permission is created without a justified, distinct access-control need (e.g., `close` is separated from `update` because closing is typically a manager-reviewed action for higher-value deals in real sales practice, even though Epic 9 does not enforce a value threshold on this distinction — the permission exists so a company can restrict it via role configuration without a schema change later).

### 31.2 Role Access Matrix

Roles are the actual system role slugs defined in `modules/users_roles/constants.py::SYSTEM_ROLES` (owner, admin, manager, accountant, salesperson, cashier, store-keeper, viewer) — not an invented role set.

| Permission | Owner | Admin | Manager | Accountant | Salesperson | Cashier | Store Keeper | Viewer |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| crm.leads.view | Y | Y | Y | Y | Y | N | N | Y |
| crm.leads.create | Y | Y | Y | N | Y | N | N | N |
| crm.leads.update | Y | Y | Y | N | Y | N | N | N |
| crm.leads.delete | Y | Y | Y | N | N | N | N | N |
| crm.leads.assign | Y | Y | Y | N | N | N | N | N |
| crm.leads.convert | Y | Y | Y | N | Y | N | N | N |
| crm.opportunities.view | Y | Y | Y | Y | Y | N | N | Y |
| crm.opportunities.create | Y | Y | Y | N | Y | N | N | N |
| crm.opportunities.update | Y | Y | Y | N | Y | N | N | N |
| crm.opportunities.delete | Y | Y | Y | N | N | N | N | N |
| crm.opportunities.assign | Y | Y | Y | N | N | N | N | N |
| crm.opportunities.close | Y | Y | Y | N | N | N | N | N |
| crm.activities.view | Y | Y | Y | Y | Y | N | N | Y |
| crm.activities.create | Y | Y | Y | N | Y | N | N | N |
| crm.activities.update | Y | Y | Y | N | Y | N | N | N |
| crm.activities.delete | Y | Y | Y | N | N | N | N | N |
| crm.pipeline.view | Y | Y | Y | Y | Y | N | N | Y |
| crm.pipeline.manage | Y | Y | N | N | N | N | N | N |
| crm.reports.view | Y | Y | Y | Y | N | N | N | Y |

**Separation of duties reasoning**:

- **Salesperson** can create/update/convert leads and opportunities and log activities (their day-to-day work) but cannot delete, reassign to others, close (win/lose) an opportunity, or manage pipeline configuration — closing and reassignment are kept at Manager+ to prevent unilateral pipeline manipulation, matching the same instinct that makes Sales Order approval a Manager-level action.
- **Accountant** is view-only across leads/opportunities/activities/pipeline (context for credit/collections decisions) plus reports, with zero mutation rights — CRM is not an accounting workflow.
- **Cashier** and **Store Keeper** have no CRM access at all — neither role has a plausible CRM need (confirmed: neither appears in the Sales spec's own CRM-adjacent permission areas either).
- **Viewer** is read-only everywhere, consistent with its meaning across every other module's permission matrix in this codebase.
- No role is granted every CRM permission automatically — even Owner/Admin's "full access" is because they hold every individual permission explicitly in the seed data, not because of a role-name special case, matching the existing RBAC engine's design (no hardcoded role-name bypass exists in `user_has_accounting_permission`, and CRM's equivalent helper follows the same pattern).

## 32. Feature Matrix

| Feature | Flag Key | Default | Notes |
|---|---|---|---|
| CRM module (all of it) | `feature.crm.enabled` | Off at platform level until a company opts in; company-level toggle | Named explicitly in the project constitution §11 as an example toggle-controlled module |

No sub-feature flags are introduced at epic launch (§5.2) — CRM ships as a single cohesive unit behind one flag, consistent with how Sales/Accounting's own more granular flags (e.g. `accounting.multicurrency.enabled`) were added only for genuinely optional sub-capabilities, not for core CRUD flows.

## 33. CRM Governance

- Pipeline and Stage configuration changes are restricted to `crm.pipeline.manage` (Owner/Admin only, §31.2) to prevent a Salesperson from silently altering forecast math for the whole team.
- Opportunity `close` (win/loss) is restricted to Manager+ as a lightweight review checkpoint on deal outcomes, without introducing a full approval-workflow engine (§18.1's explicit "no workflow engine" decision still holds — this is a permission check, not a multi-step approval).
- Lead/Opportunity reassignment (`assign`) is restricted to Manager+ to keep territory/ownership changes auditable and deliberate.

## 34. Conceptual Domain Model

```
Company (1) ──< (N) Lead
Company (1) ──< (N) LeadSource
Company (1) ──< (N) Pipeline (1) ──< (N) PipelineStage
Company (1) ──< (N) Opportunity >── (1) Customer [Sales, reused]
Company (1) ──< (N) Activity

Lead (0..1) ──> (0..1) Opportunity        [source_lead_id, one-directional traceability]
Lead (0..1) ──> (0..1) Customer           [converted_customer_id]
Opportunity (N) ──> (1) Pipeline
Opportunity (N) ──> (1) PipelineStage
Opportunity (0..1) ──> (0..1) Quotation   [quotation_id, Sales, reused]
Activity (0..1) ──> (0..1) Lead
Activity (0..1) ──> (0..1) Customer       [Sales, reused]
Activity (0..1) ──> (0..1) Opportunity
```

## 35. Aggregate Roots

- **Lead** — aggregate root; no child entities in Epic 9 (no per-lead line items).
- **Opportunity** — aggregate root; no child entities in Epic 9 (opportunity value is a single aggregate figure, not lines — line detail lives in the eventual Sales Quotation).
- **Pipeline** — aggregate root; **PipelineStage** is its child entity (created/updated only through the Pipeline's own management endpoints).
- **Activity** — aggregate root; standalone.

This mirrors the Sales spec's own aggregate-root declarations (§33 of `specs/007-sales-management/spec.md`), where `SalesOrder` is a root and `OrderLine` is its child — Opportunity intentionally has NO line-item child, keeping CRM's model simple and avoiding duplication of Quotation's own line model.

## 36. Domain Events

All events follow the same envelope convention documented in `specs/008-accounting-finance/contracts/events.md` (event_id, event_type, company_id, occurred_at, actor_user_id, payload) and are published via CRM's own `InProcessEventBus` instance (`modules/crm/events/__init__.py`, mirroring `modules/sales/events/__init__.py`).

### 36.1 Lead Events

| Event | Trigger | Payload |
|---|---|---|
| `crm.lead.created` | Lead captured | lead_id, company_id, source_id |
| `crm.lead.status_changed` | Any status transition | lead_id, company_id, from_status, to_status |
| `crm.lead.qualified` | Status → QUALIFIED | lead_id, company_id |
| `crm.lead.assigned` | owner_id changed | lead_id, company_id, owner_id |
| `crm.lead.converted` | Successful conversion | lead_id, company_id, customer_id, opportunity_id, customer_matched (bool) |

### 36.2 Opportunity Events

| Event | Trigger | Payload |
|---|---|---|
| `crm.opportunity.created` | Opportunity created | opportunity_id, company_id, customer_id, source_lead_id |
| `crm.opportunity.stage_changed` | Stage change within OPEN | opportunity_id, company_id, from_stage_id, to_stage_id |
| `crm.opportunity.assigned` | owner_id changed | opportunity_id, company_id, owner_id |
| `crm.opportunity.won` | status → WON | opportunity_id, company_id, value, currency_code |
| `crm.opportunity.lost` | status → LOST | opportunity_id, company_id, lost_reason |

### 36.3 Activity Events

| Event | Trigger | Payload |
|---|---|---|
| `crm.activity.created` | Activity created | activity_id, company_id, activity_type |
| `crm.activity.completed` | status → COMPLETED | activity_id, company_id, activity_type |

**Total: 12 domain events.** No speculative AI-specific fields are added to any payload (per the input brief's explicit instruction) — payloads carry only the business data already listed, matching the terse style of the Sales/Accounting event tables above.

## 37. Database Design

All tables extend `TenantBaseModel` (id `gen_random_uuid()` server default, `company_id`, `created_by`, `is_deleted`/`deleted_at`, `created_at`/`updated_at` with `func.now()` server defaults) — matching migration `050_accounting_ai_readiness.py`'s pattern, which the pre-Epic-9 hardening audit confirmed correct, rather than the earlier Epic 5–7 migrations whose drift bugs (051–054) had to be fixed retroactively. Every CRM migration MUST declare `server_default` on every column exactly matching its ORM model — no exceptions, given this exact defect class was found and fixed four times already in this codebase.

### 37.1 `crm_lead_sources`

| Column | Type | Notes |
|---|---|---|
| id, company_id, audit/soft-delete | — | `TenantBaseModel` |
| code | String(30) | e.g. "WEBSITE", "REFERRAL" |
| name | String(100) | Display name |
| is_active | Boolean, default true | |

**Unique**: `UNIQUE(company_id, code)` where `is_deleted = false` (tenant-scoped uniqueness, not global — per the input brief's explicit instruction).
**Index**: `(company_id, is_active)`.

### 37.2 `crm_leads`

| Column | Type | Notes |
|---|---|---|
| id, company_id, created_by, audit/soft-delete | — | `TenantBaseModel` |
| first_name, last_name | String(100), nullable | |
| lead_company_name | String(200), nullable | |
| email | String(255), nullable | |
| phone, mobile | String(30), nullable | |
| address_line1/2, city, state, postal_code, country_code | String, nullable | |
| source_id | UUID, nullable, FK → `crm_lead_sources.id` | |
| status | String(20), not null, default 'NEW' | CHECK IN (NEW, CONTACTED, QUALIFIED, UNQUALIFIED, CONVERTED, LOST) |
| score | Integer, nullable | CHECK BETWEEN 0 AND 100 |
| owner_id | UUID, nullable | Same convention as `sales_orders.sales_rep_id` |
| notes | Text, nullable | |
| last_contact_date | Date, nullable | |
| next_follow_up_date | Date, nullable | |
| qualification_notes | Text, nullable | |
| disqualification_reason | Text, nullable | |
| converted_customer_id | UUID, nullable | References `customers.id` (no enforced FK across module boundary, matching `sales_orders.quotation_id`-style cross-aggregate reference convention) |
| converted_opportunity_id | UUID, nullable, FK → `crm_opportunities.id` | |
| converted_at | timestamptz, nullable | |
| version | Integer, not null, default 1 | Optimistic locking |

**Indexes**: `(company_id, status)`, `(company_id, owner_id)`, `(company_id, next_follow_up_date)`, `(company_id, email)`.
**Constraint**: CHECK (`first_name IS NOT NULL OR last_name IS NOT NULL OR lead_company_name IS NOT NULL`); CHECK (`email IS NOT NULL OR phone IS NOT NULL`).

### 37.3 `crm_pipelines`

| Column | Type | Notes |
|---|---|---|
| id, company_id, audit/soft-delete | — | `TenantBaseModel` |
| name | String(100), not null | |
| is_default | Boolean, not null, default false | |
| is_active | Boolean, not null, default true | |

**Constraint**: partial unique index `UNIQUE(company_id) WHERE is_default = true AND is_deleted = false` — enforces BR-008 at the database level, not just application logic (matching the codebase's established pattern of backstopping business invariants with DB constraints, e.g. the `is_balanced=true` CHECK on `accounting_journal_entries`).

### 37.4 `crm_pipeline_stages`

| Column | Type | Notes |
|---|---|---|
| id, company_id, audit/soft-delete | — | `TenantBaseModel` |
| pipeline_id | UUID, not null, FK → `crm_pipelines.id` | |
| name | String(100), not null | |
| sequence | Integer, not null | CHECK >= 1 |
| probability | Integer, not null | CHECK BETWEEN 0 AND 100 |
| is_won_stage | Boolean, not null, default false | |
| is_lost_stage | Boolean, not null, default false | |
| is_active | Boolean, not null, default true | |

**Indexes**: `(company_id, pipeline_id, sequence)`.
**Constraint**: partial unique indexes ensuring at most one `is_won_stage=true` and at most one `is_lost_stage=true` per `pipeline_id`.

### 37.5 `crm_opportunities`

| Column | Type | Notes |
|---|---|---|
| id, company_id, created_by, audit/soft-delete | — | `TenantBaseModel` |
| name | String(200), not null | |
| customer_id | UUID, not null | References `customers.id` (cross-module ref, same convention as `sales_orders.customer_id`) |
| owner_id | UUID, not null | |
| pipeline_id | UUID, not null, FK → `crm_pipelines.id` | |
| stage_id | UUID, not null, FK → `crm_pipeline_stages.id` | |
| value | Numeric(15,2), not null, default 0 | CHECK >= 0 |
| currency_code | String(3), not null | |
| probability | Integer, not null | CHECK BETWEEN 0 AND 100 |
| expected_close_date | Date, nullable | |
| source_lead_id | UUID, nullable, FK → `crm_leads.id` | |
| description | Text, nullable | |
| status | String(10), not null, default 'OPEN' | CHECK IN (OPEN, WON, LOST) |
| lost_reason | Text, nullable | |
| won_at, lost_at | timestamptz, nullable | |
| quotation_id | UUID, nullable | References `sales_quotations.id` |

**Indexes**: `(company_id, status)`, `(company_id, owner_id)`, `(company_id, customer_id)`, `(company_id, pipeline_id, stage_id)`, `(company_id, expected_close_date)`.

### 37.6 `crm_activities`

| Column | Type | Notes |
|---|---|---|
| id, company_id, created_by, audit/soft-delete | — | `TenantBaseModel` |
| activity_type | String(15), not null | CHECK IN (CALL, EMAIL, MEETING, TASK, NOTE, FOLLOW_UP) |
| subject | String(300), not null | |
| description | Text, nullable | |
| status | String(15), not null, default 'PLANNED' | CHECK IN (PLANNED, COMPLETED, CANCELLED) |
| priority | String(10), not null, default 'MEDIUM' | CHECK IN (LOW, MEDIUM, HIGH) |
| due_date | timestamptz, nullable | |
| completed_at | timestamptz, nullable | |
| assigned_to | UUID, not null | |
| lead_id | UUID, nullable, FK → `crm_leads.id` | |
| customer_id | UUID, nullable | References `customers.id` |
| opportunity_id | UUID, nullable, FK → `crm_opportunities.id` | |

**Indexes**: `(company_id, assigned_to, status)`, `(company_id, due_date)`, `(company_id, lead_id)`, `(company_id, customer_id)`, `(company_id, opportunity_id)`.
**Constraint**: CHECK (`lead_id IS NOT NULL OR customer_id IS NOT NULL OR opportunity_id IS NOT NULL`).

## 38. API Design

All endpoints are mounted at `/api/v1/companies/{company_id}/crm/...`, with `dependencies=[Depends(get_current_company_member)]` applied at `include_router()` time in `api/v1/router.py` (identical to Sales/Purchase/Accounting), returning `StandardResponse[T]` for single-item/action responses and `PaginatedResponse[T]` (via `PaginationParams`, `page`/`page_size`, max 100) for lists. Every endpoint additionally requires the specific `crm.*` permission from §31.1, checked inline via the module's `user_has_crm_permission()` helper.

### 38.1 Leads

| Method | Path | Permission | Notes |
|---|---|---|---|
| POST | `/crm/leads` | `crm.leads.create` | |
| GET | `/crm/leads` | `crm.leads.view` | Filters: status, source_id, owner_id, date range, search (§42) |
| GET | `/crm/leads/{id}` | `crm.leads.view` | |
| PATCH | `/crm/leads/{id}` | `crm.leads.update` | Includes qualify/disqualify via status field |
| DELETE | `/crm/leads/{id}` | `crm.leads.delete` | Soft-delete |
| POST | `/crm/leads/{id}/assign` | `crm.leads.assign` | Body: `owner_id` |
| POST | `/crm/leads/{id}/convert` | `crm.leads.convert` | Idempotent (§16.3); returns Customer + Opportunity ids |

### 38.2 Lead Sources

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/crm/lead-sources` | `crm.leads.view` | |
| POST | `/crm/lead-sources` | `crm.pipeline.manage` | Config-level action, same permission tier as pipeline management |
| PATCH | `/crm/lead-sources/{id}` | `crm.pipeline.manage` | |

### 38.3 Pipelines & Stages

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/crm/pipelines` | `crm.pipeline.view` | |
| POST | `/crm/pipelines` | `crm.pipeline.manage` | |
| PATCH | `/crm/pipelines/{id}` | `crm.pipeline.manage` | |
| GET | `/crm/pipelines/{id}/stages` | `crm.pipeline.view` | |
| POST | `/crm/pipelines/{id}/stages` | `crm.pipeline.manage` | |
| PATCH | `/crm/pipeline-stages/{id}` | `crm.pipeline.manage` | Rejects deactivation while any OPEN Opportunity occupies the stage (BR-007) |

### 38.4 Opportunities

| Method | Path | Permission | Notes |
|---|---|---|---|
| POST | `/crm/opportunities` | `crm.opportunities.create` | |
| GET | `/crm/opportunities` | `crm.opportunities.view` | Filters: status, stage_id, owner_id, customer_id, expected_close_date range, value range |
| GET | `/crm/opportunities/{id}` | `crm.opportunities.view` | |
| PATCH | `/crm/opportunities/{id}` | `crm.opportunities.update` | Value, description, probability override, expected_close_date |
| DELETE | `/crm/opportunities/{id}` | `crm.opportunities.delete` | Soft-delete, only while OPEN |
| POST | `/crm/opportunities/{id}/assign` | `crm.opportunities.assign` | Body: `owner_id` |
| POST | `/crm/opportunities/{id}/stage` | `crm.opportunities.update` | Body: `stage_id`; rejected if `status != OPEN` |
| POST | `/crm/opportunities/{id}/win` | `crm.opportunities.close` | |
| POST | `/crm/opportunities/{id}/lose` | `crm.opportunities.close` | Body: `lost_reason` (required) |

### 38.5 Activities

| Method | Path | Permission | Notes |
|---|---|---|---|
| POST | `/crm/activities` | `crm.activities.create` | |
| GET | `/crm/activities` | `crm.activities.view` | Filters: type, status, assigned_to, lead_id, customer_id, opportunity_id, due date range |
| GET | `/crm/activities/{id}` | `crm.activities.view` | |
| PATCH | `/crm/activities/{id}` | `crm.activities.update` | |
| DELETE | `/crm/activities/{id}` | `crm.activities.delete` | Soft-delete |
| POST | `/crm/activities/{id}/complete` | `crm.activities.update` | Sets `completed_at`; cascades Lead `last_contact_date` update (§19.2) |

### 38.6 Customer 360 & Reporting

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/crm/customers/{customer_id}/360` | `crm.opportunities.view` AND `crm.activities.view` (both required — a partial-permission user gets a partial 403, not a silently incomplete view) | §20 |
| GET | `/crm/dashboard` | `crm.reports.view` | Summary KPIs, §41 |
| GET | `/crm/reports/pipeline` | `crm.reports.view` | §40.1 |
| GET | `/crm/reports/leads` | `crm.reports.view` | §40.2 |
| GET | `/crm/reports/activities` | `crm.reports.view` | §40.3 |

### 38.7 Standard Error Cases (every endpoint)

- 401 — unauthenticated.
- 403 — authenticated but missing the required `crm.*` permission, OR `feature.crm.enabled` is off for the company (FR-020).
- 404 — resource not found OR belongs to a different company (§30.2).
- 409 — invalid state transition (e.g., converting a non-QUALIFIED Lead, editing a WON Opportunity).
- 422 — validation failure (schema-level or business-rule level, e.g. missing `lost_reason`).

## 39. Frontend Requirements

Uses the existing Next.js App Router structure under `frontend/src/app/(protected)/`, following the same route-group convention as `(sales)`/`(purchase)`/`(accounting)` established in Epics 6–8, and reusing existing shared UI components (tables, forms, modals) rather than introducing a new design system.

| Screen | Route (indicative) | Notes |
|---|---|---|
| CRM Dashboard | `(crm)/dashboard` | KPI summary (§41) |
| Leads list | `(crm)/leads` | Filterable/paginated table |
| Lead detail | `(crm)/leads/[leadId]` | Includes linked activities, convert action |
| Lead create/edit | `(crm)/leads/new`, inline edit on detail | |
| Opportunities list | `(crm)/opportunities` | Filterable/paginated table |
| Kanban pipeline | `(crm)/opportunities/pipeline` | Drag-and-drop stage view, calls `POST .../stage` |
| Opportunity detail | `(crm)/opportunities/[opportunityId]` | Includes linked activities, win/lose actions |
| Activities | `(crm)/activities` | List + a calendar/due-date view for TASK/FOLLOW_UP items |
| Customer 360 | `(crm)/customers/[customerId]` | Composed read view, §20 |
| CRM reports | `(crm)/reports` | §40–41 |
| Pipeline/lead-source settings | `(crm)/settings` | `crm.pipeline.manage`-gated |

No calendar/telephony widget, no drag-and-drop library beyond what the existing frontend already uses elsewhere (if any), and no redesign of the global navigation shell — CRM adds a new route group, matching the pattern `(accounting)`'s addition in Epic 8.

## 40. Reporting Requirements

### 40.1 Pipeline Report

- Pipeline value and weighted value by stage.
- Pipeline value by salesperson (owner).
- Pipeline value by lead source (traced via `source_lead_id` → `crm_leads.source_id`).
- Won value and lost value for a given period.
- Win rate (`won / (won + lost)`) for a given period.
- Average deal size (`avg(value)` of Won opportunities in a period).
- Average sales cycle (`avg(won_at - created_at)` for Won opportunities).

### 40.2 Lead Report

- Lead count total and by status.
- Leads by source.
- Lead conversion rate (`converted / total` for a period, or `converted / qualified` as a secondary "qualified-to-close" rate).

### 40.3 Activity Report

- Activities completed (count, by type) in a period.
- Overdue follow-ups (`status=PLANNED AND due_date < now()`), by owner.

All reports use existing reporting/KPI service conventions (the `*_service.py` "compute a dict of metrics" pattern already used by `modules.accounting.services.kpi_service` and `modules.sales.services.kpi_service`) — no new BI system.

## 41. KPI Requirements

The `GET /crm/dashboard` endpoint returns, at minimum: open pipeline value, weighted pipeline value, lead count (current period), conversion rate (current period), win rate (current period), overdue follow-up count, activities completed (current period). This is the CRM-specific KPI set requested in the input brief, deliberately kept to a single dashboard call rather than a general-purpose BI query builder (§6, out of scope).

## 42. Search Requirements

- Leads: search by name, phone, email, lead_company_name; filter by status, source, owner, created-date range.
- Opportunities: search by name; filter by stage, owner, customer, expected-close-date range, value range.
- Activities: filter by type, status, assigned_to, due-date range, related lead/customer/opportunity.
- All list endpoints use the shared `PaginationParams` (page/page_size, max page_size 100) — no unbounded query is exposed.
- Free-text search fields use a simple `ILIKE`-based match at Epic 9 launch (matching the pattern used by most existing list endpoints outside Sales' `Customer.tsvector_search` full-text index); a full-text search index is not introduced pre-emptively for CRM's smaller expected row counts relative to Sales' customer table, consistent with "avoid premature optimization."

## 43. Concurrency & Idempotency

- **Lead conversion**: optimistic locking via `version` + idempotent-by-status design (§16.3).
- **Opportunity stage/win/lose updates**: optimistic locking is NOT introduced as a separate mechanism beyond the state-machine guard itself — a stage-change or win/lose request against an Opportunity that has already left `OPEN` (by a concurrent request) is rejected with 409 by the same status check used for normal invalid-transition rejection; no separate `version` column is needed on Opportunity because the `status` field itself is the concurrency guard (simpler than Lead, since Opportunity has no "already converted, return existing result" idempotency requirement — a second `win()` call on an already-WON opportunity is a genuine error, not a safe no-op, unlike lead conversion).
- **Activity completion**: idempotent — completing an already-COMPLETED activity is a no-op returning 200 with the existing `completed_at`, not an error (logging tools should never fail on a double-click).
- **No distributed locking** anywhere in CRM (matching the explicit instruction) — all concurrency safety comes from row-level `UPDATE ... WHERE status = :expected` guards and, for Lead conversion only, the optimistic `version` column.

## 44. Audit Requirements

DevSphere ERP has no single platform-wide audit table (confirmed: `CompanyAuditLog` is Companies-module-scoped; `AccountingAuditLog` is Accounting-module-scoped and append-only). Per the constitution's own rule ("the audit log schema MUST be designed at the module specification stage") and the established per-module precedent, CRM defines its own append-only `crm_audit_log` table and a `CrmAuditService.record(*, company_id, actor_user_id, entity_type, entity_id, action, before_state=None, after_state=None) -> CrmAuditLog` method — same shape as `CompanyAuditService.record()`, generalized with an `entity_type` discriminator (since CRM, unlike Companies, has multiple auditable entity types: Lead, Opportunity, Activity) so one table serves all three rather than three near-identical tables.

**Auditable actions** (per the input brief's explicit list, all implemented):

- Lead creation, lead assignment, lead status change, lead conversion
- Opportunity creation, opportunity stage change, opportunity assignment, opportunity won/lost
- Activity status change (create/update of subject/description is not separately audited — only status transitions, to avoid excessive audit noise on routine note-taking)

**Rules** (identical to Accounting's and the constitution's): `crm_audit_log` is append-only — no `update`/`delete` method exists on its repository, matching `AccountingAuditLogRepository`'s exact precedent (confirmed via code inspection: it defines only `create`/`list_*`, no mutation methods at all).

## 45. Soft Delete & Data Retention

| Entity | Deletable? | Rationale |
|---|---|---|
| Lead | Soft-delete only (`is_deleted`/`deleted_at`) | Historical funnel reporting depends on retained lead records even if "deleted" from active views |
| Opportunity | Soft-delete only, and only while `status=OPEN` | A WON/LOST Opportunity is closed-immutable business history, matching Sales Invoice's "issued invoices are immutable" precedent — it is not deleted at all in practice, but the soft-delete flag exists structurally for consistency with `TenantBaseModel` |
| Pipeline / PipelineStage | Soft-delete (`is_active=false` is the day-to-day "disable" toggle; `is_deleted` is reserved for genuine removal of a never-used, empty pipeline) | Cannot deactivate/delete while any OPEN Opportunity references it (BR-007) |
| Activity | Soft-delete only | Preserves interaction history |
| `crm_audit_log` | Immutable, never deleted (subject to the platform's general data-retention policy, matching the 7-year retention precedent already documented for Accounting's audit trail) | |

No CRM entity is ever hard-deleted — consistent with the constitution's "never hard-delete historical business records if that would destroy auditability" instruction.

## 46. Security Requirements

Explicit security test cases (server-side enforced, not frontend-only):

| # | Test | Expected |
|---|---|---|
| SEC-01 | Unauthenticated request to any `/crm/*` endpoint | 401 |
| SEC-02 | Authenticated user without the specific `crm.*` permission | 403 |
| SEC-03 | Cross-tenant GET of a Lead/Opportunity/Activity by ID | 404 |
| SEC-04 | Cross-tenant UPDATE of a Lead/Opportunity/Activity by ID | 404 |
| SEC-05 | Cross-tenant DELETE of a Lead/Opportunity/Activity by ID | 404 |
| SEC-06 | Opportunity create with a `customer_id` belonging to another tenant | 422 (foreign-entity company validation, §30.4) |
| SEC-07 | Lead convert with a manually-forged `converted_customer_id` in the request body (not accepted as input at all) | Field ignored/rejected — conversion always computes this server-side |
| SEC-08 | Activity create with a `lead_id`/`opportunity_id` belonging to another tenant | 422 |
| SEC-09 | Invalid state transition (e.g., convert a NEW lead, win an already-WON opportunity) | 409 |
| SEC-10 | Duplicate/repeated lead conversion | 200 with existing result, not a duplicate (§16.3) — explicitly a security-adjacent correctness requirement, not just a UX nicety, since a naive retry-without-idempotency implementation could otherwise create duplicate Customers |
| SEC-11 | Unauthorized assignment (`assign` without `crm.leads.assign`/`crm.opportunities.assign`) | 403 |
| SEC-12 | Assign a lead/opportunity to a user who is not an active member of the company | 422 (§30.3) |

## 47. Performance Targets

| Operation | Target |
|---|---|
| Lead/Opportunity/Activity list (paginated) | p95 < 300ms at 100,000 rows |
| Lead conversion | p95 < 2s |
| Customer 360 composition | p95 < 1s |
| Pipeline report | p95 < 2s at 10,000 open opportunities |
| CRM dashboard | p95 < 1s |

Achieved via: tenant-scoped composite indexes on every filterable column (§37), server-computed `weighted_value` avoiding N+1 per-row calculation in list views, and bounded pagination everywhere (§42) — no Elasticsearch, Redis, materialized views, or microservice extraction introduced pre-emptively, per the explicit instruction.

## 48. Testing Strategy

### 48.1 Unit Tests

- Lead status-transition validation (all valid/invalid transition pairs).
- Qualification/disqualification reason requirement.
- Opportunity `weighted_value` calculation.
- Opportunity win/lose state-machine guards.
- Activity completion idempotency and `last_contact_date` cascade logic.
- Customer-matching logic (email → phone → legal_name priority) in isolation from the DB (given a mocked repository).

### 48.2 Integration Tests

- Repository-level tenant isolation for every CRM table (create in Company A, confirm invisible to Company B queries).
- RBAC enforcement for every `crm.*` permission against every system role in §31.2.
- Database constraint tests: partial-unique default-pipeline index, at-most-one-won/lost-stage index, the Activity "at least one relation" CHECK constraint.
- Lead-conversion transaction atomicity: force a failure mid-conversion (e.g., invalid Customer data) and assert the Lead is untouched and no partial Customer/Opportunity exists.

### 48.3 API Tests

- Full CRUD for Leads, Opportunities, Activities, Pipelines/Stages, Lead Sources.
- Conversion flow (new customer, matched customer, duplicate/idempotent retry).
- Pipeline stage-change, win, lose flows including invalid-transition rejection.
- Reports/dashboard endpoints return correct aggregates against seeded data.
- Every SEC-01 through SEC-12 case from §46, asserted via real HTTP requests.

### 48.4 E2E Test

Lead → Qualification → Conversion → Opportunity → (Create Quotation handoff into Sales) — verifying the full chain up to the point CRM hands off to Epic 7, per the input brief's explicit E2E scenario.

### 48.5 PostgreSQL-Specific Verification

Per the pre-Epic-9 hardening audit's own hard-won lesson (missing-commit defects and column-constraint drift were BOTH invisible to the SQLite-backed test suite and only surfaced against real Postgres), CRM's test strategy explicitly requires:

- Live-Postgres verification of every new migration (server defaults, constraints, indexes) via the same `docker compose exec api alembic upgrade head` + direct SQL verification pattern used throughout Epics 5–8's hardening.
- A live create → fresh-HTTP-GET verification for at least Lead creation, Opportunity creation, and Lead conversion (the three highest-risk write paths), mirroring exactly the pattern that caught the original missing-commit defect class.
- Do NOT rely on SQLite tests alone for anything involving a VARCHAR length, NOT NULL constraint, or UNIQUE/partial-index constraint — these have each independently caused a real, shipped defect in this codebase (migrations 051–054) that SQLite's test harness could not detect.

## 49. Cross-Module Dependencies

| Dependency | Direction | Epic | Nature |
|---|---|---|---|
| Authentication & Sessions | Consumes | Epic 2 | All CRM actions require authenticated sessions |
| Company Configuration & Feature Flags | Consumes | Epic 3 | `feature.crm.enabled` toggle |
| Users & RBAC | Consumes | Epic 4 | Permission catalog, role seeding, company membership |
| Customer Master | Consumes | Epic 7 (Sales) | CRM references, never duplicates, `Customer` |
| Sales Quotation | Consumes (reference only) | Epic 7 (Sales) | `Opportunity.quotation_id` traceability link |
| Accounts Receivable | Consumes (read-only) | Epic 8 (Accounting) | Customer 360 live balance/aging |
| Reporting/BI | Publishes to | Future Epic 11 | CRM data feeds future exec dashboards |
| AI Features | Publishes to | Future | See §51 |

## 50. Cross-Module Contracts

### Contract: CRM → Sales (Opportunity → Quotation handoff)

When a user creates a Quotation from an Opportunity (§21.1), CRM provides Sales with:
- `customer_id` (pre-fills the Quotation's customer)
- No line items (Opportunity has no line-level model, §35) — the salesperson builds Quotation lines in Sales as normal

Sales returns the created `quotation_id`, which CRM stores on `Opportunity.quotation_id` for Customer 360 traceability. This is a UI-orchestrated handoff (a redirect with pre-fill), not a synchronous backend API call between modules — consistent with §21.1's "not automatic" decision.

### Contract: Accounting → CRM (read-only)

CRM calls `AccountsReceivableService.get_customer_ledger()`/`.get_customer_aging()` directly (in-process function call, same pattern Sales' `credit_check_service.py` already uses to call into Accounting for credit-hold checks) — not an event, since this is a synchronous read needed to render Customer 360.

## 51. AI Readiness

No AI is implemented in Epic 9. The data model and event stream are designed so future AI features can consume clean, structured data without a redesign:

- **Lead scoring**: `crm_leads.score` field exists (nullable) for a future scoring job to populate; `crm.lead.created`/`crm.lead.status_changed` events provide the training signal (source, time-to-contact, time-to-qualify).
- **Sales forecasting**: `crm_opportunities.value`/`probability`/`expected_close_date`/`stage_id` history, plus `crm.opportunity.stage_changed`/`won`/`lost` events, provide the time-series needed for pipeline forecasting.
- **Next-best-action / follow-up recommendations**: `crm_activities` history (type, outcome, timing) per lead/opportunity provides the interaction-pattern data.
- **Churn prediction / customer segmentation**: Customer 360's composed view (CRM + Sales + Accounting) is the natural feature-aggregation point for a future churn model — no new data pipeline is needed, only a future read of the same composed data.
- **Sales assistant / anomaly detection**: the CRM audit log (§44) and domain events (§36) provide the same "who/what/when" signal structure that Accounting's own AI-readiness section (§54 of `specs/008-accounting-finance/spec.md`) already relies on for its anomaly-detection readiness — CRM follows the identical readiness pattern, not a new one.

No speculative AI fields, endpoints, or infrastructure are added in this epic.

## 52. Multi-Tenant SaaS

### 52.1 Tenant Isolation

Identical guarantee to every other module (§30): CRM data is isolated per company; enforced at repository, service, and API layers; never relies on frontend filtering.

### 52.2 Branch Readiness

Per constitution §10, CRM's tables are ready to add a `branch_id` column in a future multi-branch release without an architectural rewrite — not implemented in Epic 9 (no current requirement demands it), but no design decision here (e.g., unique constraints) precludes adding it later.

### 52.3 Feature Flags

See §32 — a single `feature.crm.enabled` flag, following the exact per-module `*FeatureFlagService` pattern already used by Sales (`SalesFeatureFlagService`) and Accounting (`AccountingFeatureFlagService`); CRM adds its own `CrmFeatureFlagService` rather than reusing either module's service directly (each module owns its own flag table today — confirmed no shared cross-module flag table exists).

### 52.4 Subscription Compatibility

CRM is a natural candidate for a **Professional/Enterprise**-tier feature (matching how Accounting's own AI-readiness and approval-workflow features are tier-gated in `specs/008-accounting-finance/spec.md` §56.6) — the feature flag mechanism (§32) is the enforcement point; specific tier mapping is a commercial/business decision outside this technical specification's scope.

## 53. Risks and Architectural Decisions

| # | Decision / Risk | Reasoning |
|---|---|---|
| AD-01 | CRM enforces real, fine-grained RBAC (Accounting's pattern) rather than Sales/Purchase's current auth-only pattern. | Customer-relationship and deal-value data justifies real access control; documented as a deliberate divergence from Sales/Purchase's current (weaker) enforcement, not an oversight. Recommend, as a follow-up outside Epic 9, that Sales/Purchase adopt the same real-RBAC pattern — this was already flagged as a gap by the pre-Epic-9 hardening audit. |
| AD-02 | No per-record ownership filtering (a Manager can see all leads; a Salesperson can see all leads too via `crm.leads.view`, not just their own). | Epic 9 scopes access by *role*, not by *record ownership* — a true "salesperson sees only their own pipeline" filter is a legitimate future enhancement (§60) but was judged out of scope to avoid a second, more complex authorization dimension (row-level security) in the epic that introduces CRM's foundational RBAC in the first place. Risk: some companies may want this on day one; mitigated by `owner_id`/`assigned_to` being present in the data model already, so filtering can be added additively later without a schema change. |
| AD-03 | Opportunity has no line-item model. | Avoids duplicating Quotation's line model; risk is that some deal-value nuance (multiple products with different probabilities) is lost, mitigated by `value` being a single aggregate figure that the salesperson estimates, refined once a real Quotation exists. |
| AD-04 | Customer 360 always fetches Accounting data live (no caching). | Prioritizes correctness over the marginal performance cost, directly following the "CRM should NOT duplicate financial values" instruction; risk is added latency on Customer 360 if AR services are slow, mitigated by the p95 targets in §47 assuming direct in-process calls (no network hop, since it is same-process). |
| AD-05 | CRM defines its own local audit table rather than a shared platform-wide one. | No shared audit table exists today (verified); inventing one now would be a cross-cutting platform change outside Epic 9's scope. Documented as a conscious continuation of the existing per-module pattern, not a gap. |
| AD-06 | Lead conversion customer-matching uses exact email/phone/legal_name matching only (no fuzzy matching). | Fuzzy/probabilistic matching is a legitimate future enhancement but introduces false-positive risk (merging two genuinely different customers) that is inappropriate to introduce without a human-review step, which is out of scope for Epic 9's atomic, synchronous conversion flow. |

## 54. Assumptions

- The `feature.crm.enabled` flag defaults to OFF for existing companies and must be explicitly enabled — no existing company's UI changes unless they opt in.
- A default Pipeline (with a small number of representative stages: e.g., Qualification → Proposal → Negotiation → Closed Won / Closed Lost) is auto-provisioned the first time CRM is enabled for a company, so the module is immediately usable without mandatory configuration first.
- "Owner" and "assigned_to" are the same concept applied to different entities (Lead/Opportunity use `owner_id`; Activity uses `assigned_to`) — this naming split matches the input brief's own terminology per-entity and is not intended to imply different semantics.
- Sales' `CustomerService.create()` accepts the subset of fields CRM can populate from a Lead (name, contact info) without requiring fields CRM does not collect (e.g., `category_id` is mandatory on Customer per §37's research — CRM's conversion flow will need to supply a sensible default category, e.g. a "General"/"CRM-Converted" category auto-provisioned alongside the default pipeline, resolved during planning).

## 55. Constraints

- No modification to any Epic 1–8 table, model, service, or API contract.
- No new shared/platform-wide infrastructure (audit table, event bus, RBAC engine) — CRM extends existing per-module patterns only.
- No microservices, Kubernetes, Redis, or background-worker dependency introduced.
- Must pass the full existing regression suite (Epics 1–8) with zero regressions, per the same standard the pre-Epic-9 hardening audit already established.

## 56. Success Metrics

- **SC-001**: A salesperson can capture a Lead and convert it to a Customer + Opportunity in under 2 minutes of active work (excluding qualification research time).
- **SC-002**: Zero duplicate Customers are created via CRM conversion when a matching Customer already exists (100% match-rate on exact email/phone/legal_name matches, verified by test).
- **SC-003**: Pipeline and dashboard reports return within the performance targets in §47 for a company with 100,000 leads / 10,000 open opportunities.
- **SC-004**: 100% of the auditable actions listed in §44 produce a corresponding audit record, verified by test.
- **SC-005**: Zero cross-tenant CRM data leakage across all entities, verified by the isolation test suite in §48.2.

## 57. Glossary

See §7 (CRM Terminology) for CRM-specific terms. General platform terms (Company, Tenant, RBAC, Feature Flag, Soft Delete) follow the definitions already established in the project constitution and prior epic specs.

## 58. Acceptance Criteria

### 58.1 Lead Management Acceptance

- AC-01: Users can create, qualify/disqualify, assign, and soft-delete Leads through the full status lifecycle (§14.2).
- AC-02: Lead search/list returns results within p95 < 300ms at 100,000 records (§47).
- AC-03: A Lead auto-advances NEW → CONTACTED when its first Activity is completed (§19.2).
- AC-04: Disqualification without a reason is rejected (§14.3, BR-005).

### 58.2 Lead Conversion Acceptance

- AC-05: Converting a QUALIFIED Lead with no matching Customer creates a new Customer + Opportunity, and the Lead becomes CONVERTED with both linkage fields populated (INV-002).
- AC-06: Converting a QUALIFIED Lead with a matching existing Customer (by email/phone/legal_name) does not create a duplicate Customer.
- AC-07: A repeated conversion request against an already-CONVERTED Lead returns the existing result idempotently, not an error and not a duplicate.
- AC-08: Conversion is atomic — a forced mid-conversion failure leaves the Lead untouched (no partial Customer/Opportunity).

### 58.3 Opportunity & Pipeline Acceptance

- AC-09: Opportunities follow the OPEN → WON | LOST lifecycle; terminal states reject further edits (§17.2, BR-003).
- AC-10: `weighted_value` is always server-computed and never accepted as client input (BR-010).
- AC-11: `lose()` without `lost_reason` is rejected (BR-004).
- AC-12: Exactly one Pipeline per company can be `is_default=true`, enforced at the database level (BR-008).
- AC-13: A Pipeline Stage with any OPEN Opportunity cannot be deactivated (BR-007).

### 58.4 Activity Acceptance

- AC-14: An Activity must reference at least one of Lead/Customer/Opportunity (BR-006).
- AC-15: Completing an already-COMPLETED Activity is idempotent (200, no error) (§43).

### 58.5 Customer 360 Acceptance

- AC-16: Customer 360 financial figures always match the live Accounting service response exactly — never a cached CRM value (§20.2).
- AC-17: Customer 360 degrades gracefully (200, empty sections) for a Customer with no CRM history.

### 58.6 RBAC & Multi-Tenancy Acceptance

- AC-18: All 19 `crm.*` permissions are enforced per the matrix in §31.2, across all 8 system roles.
- AC-19: Cross-tenant GET/UPDATE/DELETE on any CRM entity by ID returns 404, never leaking data or a 403 that confirms existence.
- AC-20: Assigning a lead/opportunity to a user outside the company is rejected with 422.

### 58.7 Audit & Events Acceptance

- AC-21: All auditable actions in §44 produce a `crm_audit_log` entry with correct before/after state.
- AC-22: All 12 domain events in §36 are published on their correct trigger, verified by an event-coverage test (mirroring Sales' own EC-11-style verification).

## 59. Epic Completion (Exit) Criteria

Epic 9 is COMPLETE only when ALL of the following are verified:

| EC | Criterion | Verification |
|---|---|---|
| EC-01 | Lead lifecycle fully operational (§14.2) | Integration test: create, contact (via activity), qualify, disqualify/reopen |
| EC-02 | Lead conversion complete, atomic, idempotent, duplicate-safe | Integration test: new-customer path, matched-customer path, repeat-conversion path, forced-failure rollback path |
| EC-03 | Opportunity lifecycle complete with pipeline tracking | Integration test: create, stage changes, win, lose |
| EC-04 | Pipeline/Stage configuration with default-pipeline and won/lost-stage invariants enforced at the DB level | Constraint test against real Postgres |
| EC-05 | Activity CRUD + completion + Lead-cascade operational | Integration test: create against each of lead/customer/opportunity, complete, verify cascade |
| EC-06 | Customer 360 composes CRM + live Sales/Accounting data correctly | Integration test against seeded AR data |
| EC-07 | RBAC enforcement across all 19 permissions × 8 roles | Permission matrix test |
| EC-08 | Multi-tenant isolation verified across all 6 CRM tables | Isolation test: zero cross-company data leakage |
| EC-09 | All 12 domain events published and verified | Event coverage test |
| EC-10 | CRM audit log records all listed auditable actions | Audit coverage test |
| EC-11 | Performance targets met (§47) | Benchmark test |
| EC-12 | All reports/KPIs (§40–41) operational | Report test against seeded data |
| EC-13 | Feature flag gating (`feature.crm.enabled`) verified | Flag-off returns documented error; flag-on works normally |
| EC-14 | PostgreSQL-specific live verification performed (§48.5) | Live Docker/Postgres verification, not SQLite-only |
| EC-15 | Full regression suite passes (Epics 1–9) | pytest: zero failures across all modules, matching the pre-Epic-9 hardening audit's own standard |
| EC-16 | Zero modification to any Epic 1–8 table, model, service, or API contract | Code review / diff audit |

## 60. Future Roadmap

Explicitly deferred beyond Epic 9 (see also §6, §53 AD-02, AD-03, AD-06):

- Per-record ownership filtering (row-level "see only my own pipeline" access).
- Fuzzy/probabilistic duplicate-customer matching with human review.
- Campaign management (budgets, channels, ROI attribution beyond simple lead source).
- Territory management, quota management, commission calculation.
- Email/telephony/SMS/WhatsApp integration (send/receive, not just log).
- AI lead scoring, forecasting, next-best-action, churn prediction (data/events made ready in §51; not implemented).
- External CRM synchronization (Salesforce, HubSpot, etc.).
- Multi-currency Opportunity value normalization for cross-currency pipeline reporting (Epic 9 reports pipeline value per `currency_code` without cross-currency aggregation, consistent with how Sales avoids this until a base-currency conversion service is explicitly requested).
