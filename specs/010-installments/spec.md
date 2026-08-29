# Epic 10 — Installments: Official Business Specification

**Feature Branch**: `010-installments`
**Epic Sequence**: Built directly on completed **Epic 8 — Accounting & Finance**, completed **Epic 9 — CRM**, and completed **Epic 9A — Platform Administration / Super Admin**. Sequence: Epic 8 ✅ → Epic 9 ✅ → Epic 9A ✅ → **Epic 10 ← Current**. This resolves a naming inconsistency found during repository inspection: `specs/005-inventory-management/spec.md` refers to this capability as "Epic 11 — Installments" (stale, pre-dates the Epic 9A insertion). `specs/008-accounting-finance/spec.md`, `specs/009a-platform-admin/spec.md`, and the project Constitution (§11) are the most recently authored/amended references and consistently use **Epic 10 — Installments**; this specification adopts that numbering as authoritative (see [§34](#34-open-questions--clarifications)).
**Created**: 2026-08-24
**Status**: Draft — Open Questions permanently resolved ([§34](#34-open-questions--clarifications)); ready for `/sp.plan`
**Input**: User description — "Epic 10 — Installments: create the complete specification-only `spec.md` for an enterprise-capable installment/payment-plan management domain for the DevSphere multi-tenant ERP SaaS, covering configuration, quotation, contract lifecycle, schedule generation, collections/allocation, delinquency, early settlement, cancellation/default/write-off, Sales and Accounting integration, tenant isolation, RBAC, audit, and reporting — without duplicating Sales, Accounting, or CRM ownership."

---

## Table of Contents

1. [Feature Overview](#1-feature-overview)
2. [Goals](#2-goals)
3. [Non-Goals](#3-non-goals)
4. [Actors / Roles](#4-actors--roles)
5. [Assumptions](#5-assumptions)
6. [Dependencies](#6-dependencies)
7. [Domain Ownership](#7-domain-ownership)
8. [User Stories with Priority](#8-user-stories-with-priority)
9. [Functional Requirements](#9-functional-requirements)
10. [Business Rules / Invariants](#10-business-rules--invariants)
11. [Installment Lifecycle](#11-installment-lifecycle)
12. [Schedule Rules](#12-schedule-rules)
13. [Collection / Allocation Rules](#13-collection--allocation-rules)
14. [Delinquency Rules](#14-delinquency-rules)
15. [Settlement / Cancellation / Default / Write-Off](#15-settlement--cancellation--default--write-off)
16. [Sales Integration](#16-sales-integration)
17. [Accounting Integration](#17-accounting-integration)
18. [Inventory / CRM Integration](#18-inventory--crm-integration)
19. [Multi-Tenancy](#19-multi-tenancy)
20. [RBAC](#20-rbac)
21. [Audit](#21-audit)
22. [Feature Entitlement](#22-feature-entitlement)
23. [Reporting](#23-reporting)
24. [Security Requirements](#24-security-requirements)
25. [Concurrency / Idempotency](#25-concurrency--idempotency)
26. [Failure / Recovery Behavior](#26-failure--recovery-behavior)
27. [Non-Functional Requirements](#27-non-functional-requirements)
28. [Edge Cases](#28-edge-cases)
29. [Acceptance Scenarios](#29-acceptance-scenarios)
30. [Success Criteria](#30-success-criteria)
31. [Out of Scope](#31-out-of-scope)
32. [Future Extension / AI Readiness](#32-future-extension--ai-readiness)
33. [Risks](#33-risks)
34. [Open Questions / Clarifications](#34-open-questions--clarifications)
35. [Constitution Compliance / Traceability](#35-constitution-compliance--traceability)

---

## 1. Feature Overview

Epic 10 introduces **Installment Management** — a capability that lets a tenant sell goods or services under a structured, multi-payment plan instead of requiring full payment at the time of sale. It targets home-appliance, electronics, furniture, and equipment retailers, distributors, and similar businesses, but is designed generically enough to serve any tenant vertical on the platform (Constitution §1: "the goal is to build a reusable ERP Platform").

The module owns the **complete installment-specific lifecycle**: eligibility and configuration → quotation/terms preview → contract creation → schedule generation → activation → collections → payment allocation → overdue/delinquency tracking → adjustments → early settlement → cancellation/default/write-off (where authorized) → closure → reporting/audit. It does **not** become a second accounting system, a second sales system, or a second customer master. Repository inspection (see [§6](#6-dependencies) and [§7](#7-domain-ownership)) confirms no installment or payment-plan concept exists anywhere in the codebase today — this Epic is genuinely greenfield, but every design choice below follows the closest existing precedent in Sales, Accounting, Platform Admin, and RBAC rather than inventing new patterns where a repository convention already exists.

## 2. Goals

- G1: Let an authorized tenant user quote, propose, and activate an installment agreement against an eligible existing sale/invoice, with deterministic, reproducible terms.
- G2: Generate and track a payment schedule whose contractual total reconciles exactly with the agreed contract amount, and whose due-state (upcoming/due/overdue/paid) is derivable and explainable at any time.
- G3: Orchestrate collections against scheduled installments using a deterministic allocation policy, without creating a second source of financial truth — Accounting remains the ledger of record for every payment, journal entry, and AR balance.
- G4: Support the full controlled lifecycle of an installment contract (approval, activation, amendment, early settlement, cancellation, default, write-off) with explicit, auditable state transitions and no arbitrary status mutation.
- G5: Make Installments an optional, tenant-entitled module consistent with the platform's existing SaaS entitlement and feature-toggle model (Constitution §11, §37, §50; Epic 9A), without ever destroying or hiding a tenant's existing financial obligations when entitlement changes.
- G6: Preserve strict tenant/branch isolation, RBAC-gated high-risk operations, and full auditability for every financially or operationally significant installment action.
- G7: Expose clean, permission-safe, structured installment data so a future reporting platform (Epic 11) and future AI layer can consume it without becoming the financial source of truth themselves.

## 3. Non-Goals

- NG1: Installments is not a second general ledger, accounts-receivable ledger, or payment-processing system. It orchestrates and schedules; Accounting posts and settles.
- NG2: Installments does not redefine or duplicate the Sales order/invoice lifecycle, the Customer master, or Inventory/stock movement rules established in prior epics.
- NG3: This Epic does not implement external credit-bureau integration, automated credit scoring, debt-collection-agency integration, repossession workflows, legal recovery workflows, payment-gateway autopay/direct debit, or an AI collection agent (see [§31](#31-out-of-scope)).
- NG4: This Epic does not implement the broader cross-domain analytics/reporting platform (Epic 11) — it exposes the domain data and queries that platform will need, not the presentation layer itself.
- NG5: This Epic does not renumber, redesign, or reopen any completed Epic (1–9, 9A). Where this specification references their behavior, that behavior is treated as authoritative and unchanged.

## 4. Actors / Roles

Consistent with the existing company-scoped RBAC model (Constitution §16; `specs/004-users-roles`), Installments does not introduce new actor *types* — it introduces new *permissions* (see [§20](#20-rbac)) assignable to existing and custom company roles. Representative actors:

| Actor | Description |
|---|---|
| **Company Owner / Admin** | Full authority within the tenant, including installment configuration and write-off authorization, subject to the same rank-based model as every other module. |
| **Sales / Installment Officer** | Creates draft installment quotes/contracts from an eligible sale; cannot approve their own submissions for high-risk actions (segregation of duties, [§20.2](#202-segregation-of-duties--maker-checker)). |
| **Approver (Sales Manager / Finance Manager)** | Approves contracts above configured thresholds, approves write-offs, approves waivers — distinct from the submitting actor. |
| **Cashier / Collector** | Records installment collections against active contracts; cannot approve, cancel, default, or write off contracts. |
| **Accountant / Finance User** | Consumes installment-driven accounting events; does not directly mutate installment contract state (owned by Installments, not Accounting). |
| **Auditor / Read-Only User** | Views installment contracts, schedules, and audit history; cannot mutate anything. |
| **Platform Administrator** | Governs tenant-level entitlement to the Installments module (Epic 9A); MUST NOT gain access to tenant installment business records merely by administering the platform ([§19.2](#192-platform-admin--support-access-boundaries)). |
| **Customer** | The subject of the installment contract; not a system actor in this Epic (no customer self-service portal — [§31](#31-out-of-scope)). |

## 5. Assumptions

- A1: "Epic 10" is the correct, current numbering for this capability (resolving the stale "Epic 11" reference in `specs/005-inventory-management/spec.md` — see epic-sequence note above and [OQ-1](#34-open-questions--clarifications)).
- A2: Installment contracts are created against an existing, authoritative Sales sale/invoice — Installments never originates a sale itself (Sales owns commercial sale context, [§7](#7-domain-ownership)).
- A3: Accounting's existing `Payment` / `PaymentAllocationLine` / `ARTransaction` model is the financial system of record for every installment down payment and collection; Installments records scheduling and allocation *explanation* metadata, not competing financial truth.
- A4: Money amounts for Installments follow **Accounting's existing precision convention** (`Decimal`, minimum `NUMERIC(20,6)` internally, `Decimal`/2-decimal presentation per currency), not Sales' `NUMERIC(15,2)` convention — because installment schedules settle against AR, which Accounting owns. This is a discovered, documented conflict between two existing conventions in the repository; Installments resolves it in Accounting's favor rather than picking arbitrarily (Constitution §17 Money Handling Standard requires `Decimal`/`NUMERIC` in all cases, so both conventions comply with the Constitution — this assumption only resolves *precision*, not the underlying rule).
- A5: Installments follows the CRM precedent (Epic 9) of being entitled as a **whole module** via the Platform Admin Capability/Plan model (`grain=module`), with its own tenant-level module-wide feature-flag/master-toggle, consistent with the existing `ModuleEnablementProvider` adapter pattern (see [§22](#22-feature-entitlement)).
- A6: No idempotency-key convention exists in Accounting's `Payment` model today for Installments to reuse; Installments defines its own idempotency mechanism for installment-collection requests, following the pattern already used elsewhere in the platform (e.g., recurring-journal generation) rather than inventing an unrelated one (see [§25](#25-concurrency--idempotency)).
- A7: Aging buckets reuse Accounting's existing convention exactly: `current`, `1–30`, `31–60`, `61–90`, `91–120`, `120+` days overdue (Accounting's `AgingCalculator`), rather than the coarser 4-bucket scheme informally suggested in early product framing.
- A8: No specific numeric performance/scale targets exist in the repository for a business module of this kind (matching Epic 9A's own resolved position, OQ-4 in `specs/009a-platform-admin/spec.md`); Non-Functional Requirements in this specification stay qualitative and testable rather than fabricated numeric SLOs (see [§27](#27-non-functional-requirements)).
- A9: A default down-payment/markup model without regulatory interest-rate constraints is assumed; if a tenant's jurisdiction imposes specific consumer-finance regulatory requirements (usury caps, mandatory disclosures), that is out of scope for this Epic and tracked as a future extension ([§31](#31-out-of-scope)).
- A10: Existing pre-Epic-10 sales/invoices are never automatically or implicitly reinterpreted as installment contracts; converting an eligible pre-existing sale into an installment contract is always an explicit, authorized user action (see [§16.2](#162-data-migration--pre-existing-sales-compatibility)).

## 6. Dependencies

### 6.1 Existing Dependencies (Reused, Not Redefined)

| Dependency | Source Epic | What Installments Reuses |
|---|---|---|
| Company / tenant model, `company_id` isolation | Epic 1/3 | Every installment table is company-scoped per Constitution §9. |
| Branch concept (multi-branch readiness) | Constitution §10 | Contract/collection records carry branch scope where the tenant has branches enabled. |
| Users, Roles, Permissions, rank hierarchy | Epic 4 | Installments defines new permission codes only; reuses the existing `Role`/`Permission`/`RolePermission` model, dot-notation permission convention, and rank-based hierarchy. |
| `SalesOrder`, `SalesInvoice`, `SalesReturn`, `Customer`, `SalesPaymentTerm`, credit-limit/credit-used fields | Epic 7 | The authoritative sale/invoice/customer context an installment contract references; Installments never forks or duplicates these records. |
| `Payment`, `PaymentAllocationLine`, `PaymentRefund`, `ARTransaction`, `CustomerLedger`, `JournalEntry`/`PostingEngine`, `FiscalYear`/`FiscalPeriod` (open/locked/closed), `AgingCalculator` | Epic 8 | The financial system of record for every installment-driven payment, allocation, reversal, and posting-period constraint. |
| `Capability`, `Plan`, `PlanCapability`, `Subscription`, `EntitlementOverride`, per-module `*FeatureFlag` pattern, `ModuleEnablementProvider`, `SupportAccessGrant` | Epic 9A | The entitlement/feature-toggle and cross-tenant support-access model Installments plugs into rather than reinventing. |
| Customer 360 / CRM activity & notes | Epic 9 | Where installment-related customer context surfaces to CRM users, without duplicating the Customer Master. |
| `StandardResponse`/`ErrorResponse` envelope, `PaginatedResponse`, `/api/v1/companies/{company_id}/...` routing, permission-based authorization at the API boundary | Epic 1–9A (platform convention) | API surface conventions for all new Installments endpoints. |
| Per-module audit-log pattern (`entity_type, entity_id, action, actor_user_id, occurred_at, before_state, after_state, session_context, reason`), flush-not-commit atomic-with-caller-transaction | Epic 8 / 9A | The shape Installments' own audit log follows (no shared/generic audit table exists platform-wide — confirmed by repository inspection). |
| Maker-checker / segregation-of-duty pattern (`SelfApprovalNotAllowedError`, permission-gated approval) | Epic 8 (Accounting), Epic 5 (Inventory) | The approval pattern for installment contract approval, write-off authorization, and charge waivers. |

### 6.2 New Requirements Introduced by Epic 10

- A first-class Installment Contract, Installment Plan/Template, Installment Schedule Line, and Installment Collection-Allocation concept — none exist in the repository today.
- A dedicated `InstallmentsFeatureFlag`-style tenant-level module toggle plus registration of an `installments` Capability (`grain=module`) with the Platform Admin Plan/Capability catalogue.
- A dedicated `InstallmentAuditLog`-shaped audit table (or equivalent) for installment-specific actions, following the established per-module pattern.
- New permission codes under the `installments.*` namespace (see [§20.1](#201-permission-catalogue)).
- Domain events (past-tense named, per Constitution §49) for cross-module consumption: `InstallmentContractActivated`, `InstallmentCollected`, `InstallmentOverdue`, `InstallmentSettled`, `InstallmentDefaulted`, `InstallmentWrittenOff`, `InstallmentCancelled`.

## 7. Domain Ownership

To prevent architectural duplication, ownership is explicitly partitioned:

**Sales domain owns**: the customer sale, sales order/invoice lifecycle (`DRAFT → ... → ISSUED/INVOICED → ...`), sold items/services, commercial sale context, returns, credit-limit checks.

**Accounting domain owns**: financial ledger truth (`JournalEntry`), accounts-receivable truth (`CustomerLedger`/`ARTransaction`), payment accounting (`Payment`/`PaymentAllocationLine`), reversals, write-off financial postings, accounting periods and posting locks (`FiscalPeriod`), chart of accounts.

**Installments domain owns**: the installment agreement/contract, installment-specific commercial terms (down payment %, markup, frequency, term), the payment schedule, the installment lifecycle state machine, due-date/delinquency state, collection *orchestration* (not payment recording itself), settlement calculation/business workflow, and installment-specific history/audit context.

**Explicit non-duplication rule**: Installments MUST NOT create its own invoice records, its own payment/receipt records, its own journal entries, its own customer master, or its own AR balance. Every financial fact an installment contract needs (has this been paid, how much is outstanding, is the period open) is either read from Accounting via a defined integration contract, or explained by Installments' own scheduling/allocation-reference metadata that points back to the authoritative `Payment`/`ARTransaction` records that satisfy it.

## 8. User Stories with Priority

### US-1 (P1) — Sales/Installment Officer creates and activates a standard installment contract

An officer selects an eligible, previously issued sales invoice, previews installment terms (down payment, number of installments, frequency), submits it for approval where required by configuration, and — once approved and any required down payment is recorded in Accounting — activates the contract, generating a deterministic payment schedule.

**Independent Test**: Can be fully tested by creating one eligible sale, generating a quote, approving it, activating it, and verifying a schedule exists whose total reconciles exactly with the contract amount.

### US-2 (P1) — Cashier/Collector records an installment collection

A collector records a payment against an active contract's next due installment(s), using the deterministic oldest-due-first allocation policy, without creating a duplicate financial record.

**Independent Test**: Can be fully tested by activating one contract, recording one payment that exactly matches one scheduled installment, and verifying that installment's status becomes `PAID` and the underlying Accounting allocation is the source of truth.

### US-3 (P1) — System surfaces overdue/delinquent installments

An authorized user views a contract or a customer's exposure and sees an accurate overdue amount, days-past-due, and aging bucket, derived deterministically from due dates, grace period, and payment allocations — without depending solely on a background job having run.

**Independent Test**: Can be fully tested by letting a due date pass without payment, then reading the contract/installment state on demand and confirming overdue amount and bucket are correct at read time.

### US-4 (P2) — Authorized approver settles a contract early

An approver generates a settlement quote for an active contract, and — only once the settlement payment is authoritatively recorded — the contract closes as `COMPLETED`, with all remaining scheduled obligations reconciled to zero.

**Independent Test**: Can be fully tested by activating a contract with 3+ remaining installments, generating a settlement quote, recording the settlement payment, and verifying the contract transitions to `COMPLETED` and no installment remains outstanding.

### US-5 (P2) — Authorized approver writes off an uncollectible contract

A user holding write-off authorization (distinct from ordinary collection permissions) marks a defaulted contract as written off, with a mandatory reason, triggering the appropriate Accounting write-off integration, fully audited.

**Independent Test**: Can be fully tested by defaulting a contract, attempting the write-off as an unauthorized user (denied), then performing it as an authorized user and verifying the audit record and Accounting event.

### US-6 (P2) — Tenant admin configures installment policy and plan templates

A company admin configures tenant-level installment policy (allowed frequencies, min/max term, min down payment, grace period, late-charge policy) and defines reusable plan templates (e.g., "6 Monthly Installments, 0% Markup"), without affecting any already-active contract's preserved terms.

**Independent Test**: Can be fully tested by changing a template's terms after a contract has already been created from it, and verifying the existing contract's snapshot terms are unchanged.

### US-7 (P3) — Platform Admin governs Installments entitlement without accessing tenant data

A Platform Admin enables/disables the Installments module for a tenant via the existing entitlement model, and confirms that doing so never grants them read/write access to that tenant's installment contracts or schedules.

**Independent Test**: Can be fully tested by disabling entitlement for Tenant A, confirming Tenant A cannot create new installment activity while existing contracts remain servicable per policy, and confirming the acting Platform Admin still cannot read Tenant A's contract data.

### US-8 (P3) — Auditor reviews installment history

An auditor reviews the full audit trail of a contract — creation, approval, activation, every collection, every allocation, any waiver, any reschedule, settlement, cancellation, default, or write-off — with before/after context where applicable, scoped strictly to their own tenant.

**Independent Test**: Can be fully tested by performing a representative sequence of lifecycle actions on one contract and confirming every action produced a corresponding, non-editable audit entry.

## 9. Functional Requirements

Requirements are grouped by domain. Each is unambiguous, testable, and implementation-independent (no database, framework, or API-shape prescriptions — those belong in `/sp.plan`).

### 9.1 Installment Configuration (Tenant-Level)

- **FR-INST-001**: The system MUST allow an authorized tenant admin to configure, per company: module enablement, allowed installment frequencies (at minimum monthly; weekly and quarterly where the tenant enables them), minimum and maximum installment term (count of installments), minimum down-payment percentage or amount, an optional maximum financed amount, a rounding policy, a grace-period policy, an overdue policy, an optional late-charge policy, an early-settlement policy, contract-approval thresholds, backdating restrictions, cancellation restrictions, and default/write-off authorization requirements.
- **FR-INST-002**: The system MUST allow configuration to optionally support branch-specific overrides where the tenant has multi-branch enabled (Constitution §10), falling back to the company-level configuration when no branch override exists.
- **FR-INST-003**: The system MUST allow a tenant to designate specific products/categories as installment-eligible or installment-ineligible, and to enable/disable customer-eligibility controls, without requiring these controls to be used.
- **FR-INST-004**: A configuration change MUST NOT retroactively alter the commercial terms of any already-approved or already-active installment contract (see [BR-INST-009](#10-business-rules--invariants)).

### 9.2 Installment Plans / Templates

- **FR-INST-010**: The system MUST allow an authorized user to define reusable, tenant-scoped installment plan templates specifying: name, description, active/inactive state, frequency, number of installments, down-payment rule, an optional markup/service-charge rule, grace period, an optional late-charge policy, an early-settlement rule, optional applicable products/categories, and optional approval requirements.
- **FR-INST-011**: The system MUST allow installment contracts to be created either from a template or with fully custom terms within the tenant's configured policy bounds ([§9.1](#91-installment-configuration-tenant-level)).
- **FR-INST-012**: Editing or deactivating a template MUST NOT mutate any contract previously created from that template's prior terms (see [BR-INST-009](#10-business-rules--invariants)).
- **FR-INST-013**: Deactivating a template MUST prevent its use for new contracts while leaving existing contracts created from it fully servicable.

### 9.3 Customer Eligibility

- **FR-INST-020**: The system MUST evaluate customer eligibility for an installment offer against tenant-configurable factors including at minimum: active (non-blocked) customer status, tenant ownership of the customer record, outstanding installment exposure, overdue/default history within Installments, and an optional configurable installment/credit limit.
- **FR-INST-021**: The system MUST allow an authorized approver to record a manually approved eligibility exception with a mandatory reason, distinct from the automated eligibility check.
- **FR-INST-022**: The system MUST NOT require external credit-bureau integration to determine eligibility; eligibility MUST be computable entirely from data already available within the tenant's own platform data (Sales, CRM, Installments' own history).
- **FR-INST-023**: The eligibility check MUST be re-evaluated at contract approval time, not solely at quote time, to reflect any change in customer status between preview and approval.

### 9.4 Installment Quote / Preview

- **FR-INST-030**: The system MUST allow an authorized user to preview installment terms for an eligible sale/invoice before any binding contract is created, showing: sale/invoice amount, eligible amount, down payment, financed principal, any markup/service charge, total contractual amount, number of installments, frequency, first due date, per-installment amounts, the final-installment rounding adjustment, and expected completion date.
- **FR-INST-031**: Preview calculations MUST be deterministic — the same inputs (sale amount, template/terms, as-of date) MUST always produce the same preview output.
- **FR-INST-032**: Generating a preview MUST NOT create any contract, schedule, or financial posting, and MUST NOT be recorded as a business event distinct from an ordinary read operation.

### 9.5 Installment Agreement / Contract (Data Requirements)

- **FR-INST-040**: The system MUST represent an installment contract as a first-class record referencing: a human-readable contract number (tenant-scoped, sequential per existing document-numbering conventions), the customer, the originating sale/invoice, the tenant/company, the branch (where applicable), an optional plan/template reference, contract date, principal/financed amount, down payment, markup/service charge, contractual total, installment count, frequency, first due date, maturity date, currency, contract status, a full terms snapshot, the creating actor, the approving actor (where approval is required), activation timestamp, and closure timestamp.
- **FR-INST-041**: The contract's terms snapshot MUST be sufficient, on its own, to explain the full financial obligation even if the originating configuration or template is later changed or deleted (see [BR-INST-009](#10-business-rules--invariants), [§10.4](#104-immutability--historical-integrity)).
- **FR-INST-042**: The system MUST prevent creating more than one non-terminal (i.e., not `CANCELLED`, `COMPLETED`, or `WRITTEN_OFF`) installment contract against the same originating sale/invoice obligation. Epic 10 supports at most one active installment contract per originating obligation at a time; split/multiple concurrent financing of a single invoice is not supported and is explicitly Out of Scope for this Epic (see [§16.1](#161-boundary), [§31](#31-out-of-scope)).

### 9.6 Notifications / Reminders

- **FR-INST-050**: The system MUST publish integration-ready business events for: an installment becoming due soon (configurable lead time), an installment due today, an installment becoming overdue, a payment received against a contract, and a contract completing — sufficient for a notification channel (in-app, email, SMS, WhatsApp) to consume without Installments itself implementing that channel.
- **FR-INST-051**: The system MUST NOT require any specific external notification-provider integration to satisfy this Epic; channel delivery is future-ready, not implemented here (see [§31](#31-out-of-scope)).

### 9.7 Documents

- **FR-INST-060**: The system MUST support generating, from authoritative stored data only: an installment agreement/contract document, a payment schedule document, a settlement quotation document, and an account/installment statement, using the tenant's existing document/receipt mechanisms where applicable (e.g., existing receipt generation for a recorded payment).
- **FR-INST-061**: Generating any installment document MUST NOT change financial or contract state.

### 9.8 Search and Operational Views

- **FR-INST-070**: The system MUST provide tenant-scoped operational views/queries for: all contracts, active contracts, due today, due this week, overdue, partially paid, completed, cancelled, defaulted, written-off, filtered by customer, branch, plan/template, and collector/user where applicable.
- **FR-INST-071**: The system MUST support search by contract number, customer, and originating invoice/sale reference, all strictly tenant-scoped ([§19](#19-multi-tenancy)).
- **FR-INST-072**: All list/search endpoints MUST support pagination and filtering consistent with the platform's existing `PaginatedResponse` convention.

### 9.9 Dashboard and KPIs

- **FR-INST-080**: The system MUST expose, per tenant: active contract count, total outstanding balance, amount due today, amount due this month, amount collected today, amount collected this month, overdue amount, overdue contract count, a collection-rate metric, an aging distribution, defaulted balance, written-off balance, and upcoming receivables.
- **FR-INST-081**: Every metric MUST be computed from authoritative installment/financial state and MUST NOT double-count an amount across more than one metric bucket (e.g., an overdue amount MUST NOT also be counted inside "due this month" once it has crossed into overdue).

### 9.10 API / Contract Expectations

- **FR-INST-090**: Every Installments API capability MUST be tenant-scoped, following the platform's existing `/api/v1/companies/{company_id}/...` routing convention, `StandardResponse`/`ErrorResponse` envelope, and permission-based authorization at the API boundary.
- **FR-INST-091**: Every list-returning endpoint MUST paginate; every filterable resource MUST support the platform's existing filtering conventions.
- **FR-INST-092**: Every high-risk command (collection recording, activation, settlement, write-off, default, cancellation, reschedule) MUST support idempotent request handling (see [§25](#25-concurrency--idempotency)) and MUST return a consistent, documented conflict response when a request cannot be satisfied due to contract or schedule state.
- **FR-INST-093**: Error semantics MUST follow the platform's existing error-code convention — business-rule violations return 4xx with a documented, stable error code; infrastructure failures return 5xx; internal error detail MUST NEVER be exposed to clients in production (Constitution §21).

## 10. Business Rules / Invariants

| ID | Rule |
|---|---|
| BR-INST-001 | A tenant can never access, infer, search, mutate, collect against, or settle another tenant's installment business data, under any circumstance. |
| BR-INST-002 | Platform administration does not imply unrestricted tenant-business-data access; enabling/disabling the Installments entitlement for a tenant grants no read/write access to that tenant's contracts. |
| BR-INST-003 | An installment contract MUST always reference an authoritative, existing Sales customer and sale/invoice context; Installments never originates a customer or a sale. |
| BR-INST-004 | Installments MUST NOT duplicate Accounting's financial source of truth — no shadow invoice, shadow payment, shadow journal entry, or shadow AR balance. |
| BR-INST-005 | The sum of an installment schedule's scheduled contractual amounts MUST reconcile exactly with the contract's contractual total, under the tenant's configured money precision and rounding rules — with any residual rounding difference resolved entirely in the final installment. |
| BR-INST-006 | Collections MUST NOT create duplicate financial effects — the same authoritative payment can satisfy installment obligations exactly once. |
| BR-INST-007 | Every payment allocation against a scheduled installment MUST be explainable and auditable back to the authoritative Accounting payment/allocation record that satisfies it. |
| BR-INST-008 | Once a contract is `ACTIVE` (or beyond), its core financial terms (principal, down payment, markup, installment count, frequency, contractual total) cannot be destructively edited — only through the controlled amendment workflow ([§15.2](#152-contract-amendments--rescheduling)) or explicit reversal/cancellation workflows. |
| BR-INST-009 | Configuration and plan/template changes never silently rewrite an already-created contract's preserved terms snapshot. |
| BR-INST-010 | A contract cannot transition to `COMPLETED` while any authoritative outstanding obligation remains against it. |
| BR-INST-011 | A contract can never be over-collected through concurrency or duplicate requests — total allocated amount can never exceed the contractual total. |
| BR-INST-012 | Write-off requires explicit, distinct authorization beyond ordinary collection/approval permissions, and MUST integrate with Accounting's write-off posting mechanism. |
| BR-INST-013 | `DEFAULTED` (a business/collection state) and `WRITTEN_OFF` (an authorized financial action) are distinct states/actions — reaching `DEFAULTED` never implies an automatic write-off. |
| BR-INST-014 | Disabling a tenant's Installments entitlement can never erase, hide, or make uncollectible an existing financial obligation already created while the module was entitled — existing obligations remain fully financially serviceable, including collection and early settlement necessary to discharge them, subject to all normal RBAC, audit, and Accounting controls (see [§22.4](#224-behavior-when-entitlement-is-disabled-after-contracts-exist)). |
| BR-INST-015 | Cross-tenant identifiers (contract numbers, customer IDs, sale/invoice IDs) must never leak another tenant's data through response content, search results, counts, error-message differences, or timing/metadata side channels. |
| BR-INST-016 | Every high-risk financial mutation (activation, collection, reversal, waiver, reschedule, settlement, cancellation, default, write-off, configuration change) MUST produce a full audit record. |
| BR-INST-017 | Reversals (payment reversal, allocation reversal) MUST preserve the original financial event in history — never delete or silently overwrite it; a reversal is itself a new, auditable event. |
| BR-INST-018 | Every installment financial calculation MUST use the platform's `Decimal`/`NUMERIC` money rules (Constitution §17) — never floating-point arithmetic — and MUST follow Accounting's precision convention for amounts that ultimately settle against AR ([Assumption A4](#5-assumptions)). |
| BR-INST-019 | Schedule generation and due-date/overdue calculation MUST be deterministic — the same contract terms and business date always produce the same schedule and the same due-state. |
| BR-INST-020 | AI or support tooling may never bypass normal financial authorization boundaries — no autonomous waive, write-off, settle, reverse, or contract mutation without an explicit, authorized human-initiated workflow ([§32](#32-future-extension--ai-readiness)). |
| BR-INST-021 | A closed/locked Accounting fiscal period blocks any Installments action that would require a new posting dated within that period, consistent with `FiscalPeriod` enforcement in `PostingEngine` ([§17](#17-accounting-integration)). |
| BR-INST-022 | An installment contract's currency is immutable once set at contract creation; multi-currency behavior never exceeds what the existing ERP already supports. |

## 11. Installment Lifecycle

### 11.1 Contract States

`DRAFT → PENDING_APPROVAL → APPROVED → ACTIVE → COMPLETED`, with off-ramps to `CANCELLED`, `DEFAULTED`, and `WRITTEN_OFF` at the points defined below. No installment/payment-plan lifecycle exists elsewhere in the repository to conflict with or reuse; these states are established fresh for this Epic.

| State | Meaning |
|---|---|
| `DRAFT` | Terms are being prepared; freely editable by the creator. |
| `PENDING_APPROVAL` | Submitted for required approval; the submitter can no longer freely edit terms. |
| `APPROVED` | Approved but not yet activated (e.g., awaiting required down payment). |
| `ACTIVE` | Financially live; schedule is authoritative; collections may be recorded. |
| `COMPLETED` | All scheduled obligations satisfied (ordinary payoff or early settlement); terminal. |
| `CANCELLED` | Terminated before or during activity, per [§15.3](#153-cancellation); terminal. |
| `DEFAULTED` | Business/collection state signaling severe, unresolved delinquency; not terminal — may lead to write-off, be cured back to `ACTIVE` where tenant policy permits ([§15.4](#154-default)), or complete directly (`COMPLETED`) if the outstanding obligation is fully satisfied while defaulted. |
| `WRITTEN_OFF` | Authorized financial write-off has occurred; terminal. |

> **Note on `REJECTED`**: `REJECTED` is an approval **outcome/event**, not a persisted contract state — the contract's status field never holds the value `REJECTED`. A rejected submission returns the contract to `DRAFT` via an explicit **REJECT** action (FR-INST-102); the rejection event itself remains permanently visible in the contract's audit history.

### 11.2 Legal Transitions

- **FR-INST-100**: `DRAFT` MAY be freely edited or discarded by its creator or any user holding contract-edit permission; no financial commitment exists yet.
- **FR-INST-101**: `DRAFT → PENDING_APPROVAL` requires submission by an authorized user; if the tenant's configured approval threshold does not require approval, the system MAY transition directly `DRAFT → APPROVED`.
- **FR-INST-102**: `PENDING_APPROVAL → APPROVED` requires an approver distinct from the submitter ([§20.2](#202-segregation-of-duties--maker-checker)). Alternatively, that approver may perform an explicit **REJECT** action, transitioning the contract `PENDING_APPROVAL → DRAFT` (`REJECTED` is an approval outcome/event, not a persisted contract state — see the note in [§11.1](#111-contract-states)). Rejection requires the same distinct-approver authority as approval, requires a mandatory reason, and MUST be audited (FR-INST-340). The contract becomes editable again as `DRAFT`; the prior submission/rejection event remains permanently visible in the contract's audit history and MUST NOT be deleted or overwritten by any subsequent resubmission.
- **FR-INST-103**: `APPROVED → ACTIVE` requires schedule generation to succeed and, where the tenant's policy requires a down payment before activation, requires that down payment to already be authoritatively recorded in Accounting ([§15](#15-settlement--cancellation--default--write-off) references down payment handling under [§13.3](#133-down-payments)).
- **FR-INST-104**: `ACTIVE → COMPLETED` or `DEFAULTED → COMPLETED` requires zero authoritative outstanding obligation remaining (BR-INST-010). A `DEFAULTED` contract that reaches zero outstanding balance through the servicing-continuity payment path ([§22.4](#224-behavior-when-entitlement-is-disabled-after-contracts-exist), FR-INST-356) or ordinary collection completes directly — a separate cure action is not required first.
- **FR-INST-105**: `ACTIVE → CANCELLED`, `ACTIVE → DEFAULTED`, `DEFAULTED → WRITTEN_OFF`, and `DEFAULTED → ACTIVE` (cure/restore-to-servicing, where tenant policy permits — [§15.4](#154-default), FR-INST-222) each require their own distinct permission and produce their own audit trail, per [§15](#15-settlement--cancellation--default--write-off).
- **FR-INST-106**: The system MUST explicitly reject any transition not enumerated in this section — there is no generic "set status" operation available to any actor, however privileged.
- **FR-INST-107**: An `ACTIVE` contract cannot be deleted; only the controlled transitions above are available to end its life.
- **FR-INST-108**: A `COMPLETED` contract MUST NOT accept ordinary new installment collections; any post-completion financial correction MUST go through Accounting's own reversal mechanism, not a reopened Installments collection.

## 12. Schedule Rules

### 12.1 Schedule Generation

- **FR-INST-110**: The system MUST generate a deterministic installment schedule at `APPROVED → ACTIVE` transition (or, where the tenant's policy allows schedule preview before activation, at contract creation with a "provisional" marker) supporting monthly frequency at minimum, and weekly/quarterly/custom where tenant-enabled.
- **FR-INST-111**: Due-date calculation MUST define: the first due date (from contract activation date or a configured offset), subsequent due dates at the configured frequency, explicit month-end behavior (e.g., a due date anchored to the 31st in a 30-day month resolves to that month's last day), explicit leap-year behavior for annual/day-count-sensitive calculations, and explicit rounding rules for splitting the contractual total across installments.
- **FR-INST-112**: Any residual amount from splitting the contractual total across equal installments MUST be resolved entirely in the final installment, never distributed silently across multiple installments in a way that breaks reproducibility.
- **FR-INST-113**: The schedule's total contractual amount MUST reconcile exactly with the contract's contractual total (BR-INST-005) — this reconciliation MUST be validated before the contract is allowed to become `ACTIVE`.
- **FR-INST-114**: Once a contract is `ACTIVE`, schedule regeneration is prohibited except through the controlled amendment/rescheduling workflow ([§15.2](#152-contract-amendments--rescheduling)); no operation may silently overwrite an active schedule.
- **FR-INST-115**: Schedule due dates MUST be evaluated against the tenant's/branch's established business-date convention (see [§10](#10-business-rules--invariants) and Accounting's existing business-date handling), never against server-local wall-clock time.

### 12.2 Installment Due-State Model

- **FR-INST-120**: Each scheduled installment MUST expose a business state derived, wherever possible, from authoritative dates and payment allocations rather than a freely editable status field: `UPCOMING` (not yet due), `DUE` (due today or within grace), `PARTIALLY_PAID`, `PAID`, `OVERDUE` (past grace with an outstanding balance), and only through controlled workflows: `WAIVED` or `CANCELLED`/`VOIDED`.
- **FR-INST-121**: The system MUST expose, per scheduled installment: scheduled amount, amount paid, amount remaining, overdue amount (if any), and days overdue (if any), computed consistently with [§12.1](#121-schedule-generation)'s deterministic due dates.
- **FR-INST-122**: Due-state and overdue calculation MUST be correct when computed on demand at read time, and MUST NOT depend solely on a background/scheduled process having already run (BR-INST-019; see also [§14.1](#141-overdue--grace-period)).

## 13. Collection / Allocation Rules

### 13.1 Collections

- **FR-INST-130**: The system MUST support recording an exact installment payment, a partial payment, a single payment covering multiple due installments, and an advance payment made before a future due date.
- **FR-INST-131**: The system MUST support payment reversal, consistent with Accounting's existing payment cancellation/refund mechanisms (see [§17](#17-accounting-integration)), and MUST recompute affected installment/contract state after a reversal.
- **FR-INST-132**: Overpayment MUST be handled according to Accounting's existing rules (e.g., recorded as an advance/credit) — Installments MUST NOT invent a separate overpayment-handling mechanism.
- **FR-INST-133**: Every collection request MUST be idempotent and protected against duplicate submission (see [§25](#25-concurrency--idempotency)).

### 13.2 Allocation Policy

- **FR-INST-140**: Unless a tenant explicitly configures an alternative business rule, the system MUST allocate a payment to the **oldest outstanding due obligation first** (FIFO by due date) across the contract's schedule.
- **FR-INST-141**: A single payment MAY allocate across multiple scheduled installments; a single scheduled installment MAY receive multiple payments over time.
- **FR-INST-142**: Installments MUST maintain allocation/reference metadata sufficient to explain, for any scheduled installment, exactly which authoritative Accounting payment(s)/allocation(s) satisfied it, in what order, and for what amount (BR-INST-007) — Installments MUST NOT create a parallel payment-truth record.

### 13.3 Down Payments

- **FR-INST-150**: The system MUST allow tenant policy to require a down payment before a contract may activate; where required, insufficient down payment MUST block the `APPROVED → ACTIVE` transition.
- **FR-INST-151**: A down payment MUST be recorded through Accounting's existing payment mechanism, referenced by the contract, and MUST NOT be double-counted in the financed principal, the schedule total, or Accounting's AR/revenue recognition.
- **FR-INST-152**: Down-payment refund/reversal MUST follow Accounting's existing refund/reversal mechanism and MUST be reflected in the contract's activation eligibility and financed-principal calculation if it occurs before activation.

## 14. Delinquency Rules

### 14.1 Overdue & Grace Period

- **FR-INST-160**: The system MUST support a tenant-configurable grace period after a due date before an installment is classified `OVERDUE`.
- **FR-INST-161**: The system MUST compute, at minimum on read/query and MAY additionally materialize via a scheduled process for reporting efficiency: days past due, outstanding overdue amount, customer-level overdue exposure, and contract-level delinquency — but correctness of the financial obligation itself MUST NEVER depend solely on the scheduled process having run (BR-INST-019, FR-INST-122).
- **FR-INST-162**: `DEFAULTED` is a distinct, explicitly triggered business state (not automatically inferred purely from days-overdue) requiring the permission and workflow defined in [§15.4](#154-default).

### 14.2 Late Charges / Penalties

- **FR-INST-170**: Late charges are OPTIONAL and MUST be governed entirely by tenant configuration; a tenant that does not enable late charges MUST see no late-charge behavior whatsoever.
- **FR-INST-171**: Where enabled, late-charge calculation MUST be deterministic (fixed or percentage policy, tenant-configured), MUST NOT be applied more than once for the same overdue occurrence, MUST be fully auditable, MUST support authorized waiver, and MUST integrate with Accounting for any resulting posting.
- **FR-INST-172**: A contract's terms snapshot MUST capture the late-charge policy applicable at contract activation, independent of later tenant configuration changes (BR-INST-009).
- **FR-INST-173**: Waiving a late charge requires a permission distinct from ordinary collection permission, and MUST record a mandatory reason.

### 14.3 Aging

- **FR-INST-180**: The system MUST compute installment receivable aging using Accounting's existing bucket convention: `current`, `1–30`, `31–60`, `61–90`, `91–120`, `120+` days overdue ([Assumption A7](#5-assumptions)).
- **FR-INST-181**: Aging MUST be reproducible as of any requested business date where the tenant's reporting architecture supports historical/as-of reporting, consistent with Accounting's own aging capability.

## 15. Settlement / Cancellation / Default / Write-Off

### 15.1 Early Settlement

- **FR-INST-190**: The system MUST allow an authorized user to generate a settlement quote for an `ACTIVE` contract, computing: remaining principal/contractual balance, outstanding charges, any settlement adjustment/discount permitted by tenant policy, the final settlement amount, quote validity (where applicable), and the resulting contract closure implication.
- **FR-INST-191**: Settlement calculation MUST be reproducible and auditable — the same contract state and as-of date always produce the same quote.
- **FR-INST-192**: Generating a settlement quote MUST NOT itself close the contract or create any financial posting; only the authoritative settlement payment, once recorded in Accounting and fully allocated, MAY transition the contract to `COMPLETED`.

### 15.2 Contract Amendments / Rescheduling

- **FR-INST-200**: Arbitrary editing of an `ACTIVE` contract's terms is prohibited (BR-INST-008).
- **FR-INST-201**: Where the tenant requires due-date rescheduling of an active contract, the system MUST provide a controlled amendment workflow requiring the same maker-checker discipline as contract approval, producing a new schedule version while preserving the prior schedule for historical explanation (BR-INST-017, [§10.4](#104-immutability--historical-integrity)).
- **FR-INST-202**: Full commercial-term restructuring (re-financing, changing principal/markup on an active contract) is explicitly **out of scope** for Epic 10 (see [§31](#31-out-of-scope)) — only due-date rescheduling within the existing contractual total is in scope; the system MUST reject restructuring requests with a clear, documented error rather than silently allowing unsafe editing.
- **FR-INST-203**: A `DRAFT` contract MAY be freely corrected without amendment workflow, per FR-INST-100.

### 15.3 Cancellation

- **FR-INST-210**: Cancellation rules differ by lifecycle stage: a `DRAFT` or `PENDING_APPROVAL` contract MAY be cancelled by its creator or an authorized user without further workflow; an `APPROVED` contract not yet activated MAY be cancelled by an authorized user with a mandatory reason; an `ACTIVE` contract with no collections yet recorded MAY be cancelled by an authorized user with a mandatory reason; an `ACTIVE` contract with recorded payments or accounting postings requires the controlled reversal/settlement behavior of [§17](#17-accounting-integration) before cancellation completes.
- **FR-INST-211**: Cancellation of a contract with financial activity MUST NOT make that activity disappear — the contract's history remains visible and explainable after cancellation (BR-INST-017).
- **FR-INST-212**: Cancellation MUST integrate with Sales/Accounting reversal rules where applicable (e.g., reversing a down payment) and MUST be fully audited.

### 15.4 Default

- **FR-INST-220**: The system MUST allow an authorized user to explicitly mark an `ACTIVE` contract as `DEFAULTED`, recording a mandatory reason, the acting user, and a timestamp; this is a business/collection state and MUST NOT itself trigger any Accounting posting.
- **FR-INST-221**: `DEFAULTED` MUST NOT be reachable through any implicit or automatic transition (BR-INST-013, FR-INST-162).
- **FR-INST-222**: Where tenant policy explicitly permits curing, a `DEFAULTED` contract MAY be restored to `ACTIVE` (`DEFAULTED → ACTIVE`, FR-INST-105) through an explicit, authorized **CURE / RESTORE TO SERVICING** action requiring a permission distinct from ordinary collection. Cure MUST: be policy-permitted (a tenant that has not enabled curing MUST NOT expose this action); record a reason/context where the tenant requires one; be fully audited; leave the contract's historical `DEFAULTED` event and all delinquency history permanently visible and undeleted; never rewrite or delete Accounting history; never create a new contract; and never alter the contract's original commercial terms. Any outstanding balance associated with the cure MUST be computed solely from authoritative Accounting records. If the contract's outstanding obligation is instead fully satisfied while `DEFAULTED` (rather than merely reduced), it completes directly per FR-INST-104 (`DEFAULTED → COMPLETED`) as part of the authorized servicing workflow — a separate cure action is not required in that case.

### 15.5 Write-Off

- **FR-INST-230**: Write-off of a `DEFAULTED` contract requires a permission distinct from ordinary collection, approval, and default permissions ([§20.1](#201-permission-catalogue)); normal cashiers/sales users MUST NOT be able to perform it.
- **FR-INST-231**: A write-off MUST record: authorization, mandatory reason, timestamp, actor, the outstanding balance being written off, and MUST integrate with Accounting's existing write-off posting mechanism (BR-INST-012).
- **FR-INST-232**: A write-off, once posted, MAY be reversed only through Accounting's own reversal mechanism, with corresponding installment-state recomputation; Installments MUST NOT silently mark a written-off contract as active again outside that reversal.

### 15.6 Refunds and Reversals

- **FR-INST-240**: When a previously allocated installment payment is reversed in Accounting, the affected installment(s)' paid/remaining/overdue amounts and the contract's delinquency state MUST be recalculated correctly and MUST remain reconciled with Accounting.
- **FR-INST-241**: When the originating sale is returned or its invoice is voided/adjusted in Sales, Installments MUST respect Sales'/Accounting's existing reversal rules; Installments state MUST remain explainable (not silently deleted or orphaned) after such an event.
- **FR-INST-242**: No reversal MAY destructively rewrite a historical payment allocation — every reversal is itself a new, auditable event layered on top of history (BR-INST-017).

## 16. Sales Integration

### 16.1 Boundary

- **FR-INST-250**: An installment contract MUST be creatable only against an eligible, existing Sales sale/invoice, per tenant-configured eligibility rules (e.g., an `ISSUED` invoice of sufficient outstanding amount); Sales' invoice lifecycle and immutability rules (issued invoices are immutable; corrections go through credit notes) are unaffected by Installments.
- **FR-INST-251**: The system MUST prevent creating a duplicate non-terminal installment contract against the same sale/invoice obligation (FR-INST-042) — Epic 10 does not support tenant-configurable split/multiple financing of a single invoice across concurrent active contracts, and no tenant configuration may enable this. If an existing invoice already has payments recorded in Accounting before installment conversion, the single installment contract's financed principal MUST be computed against only the invoice's remaining eligible outstanding amount, per the existing Sales/Accounting truth ([§16.2](#162-data-migration--pre-existing-sales-compatibility)).
- **FR-INST-252**: Installments MUST respect Sales' existing return/cancellation/invoice-adjustment rules; it MUST NOT modify Sales ownership semantics or Sales' own status model to accommodate installment financing.
- **FR-INST-253**: An installment contract's currency MUST match its originating sale/invoice's currency; Installments introduces no multi-currency behavior beyond what Sales/Accounting already support.

### 16.2 Data Migration / Pre-Existing Sales Compatibility

- **FR-INST-260**: No pre-existing sale, invoice, or payment record is automatically or implicitly reinterpreted as an installment contract when this Epic ships; every installment contract against a pre-existing sale requires an explicit, authorized user action, subject to the same eligibility rules as any newly created sale ([Assumption A10](#5-assumptions)).
- **FR-INST-261**: Where a pre-existing sale already has partial payments recorded in Accounting before an installment contract is created against it, the resulting schedule's financed principal MUST correctly account for those pre-existing payments as already-satisfied, never double-counted.

## 17. Accounting Integration

- **FR-INST-270**: Contract activation, down-payment recording, installment collection, late-charge posting, waiver, settlement, reversal, default (no posting), write-off, and cancellation-with-financial-activity each define a specific integration point with Accounting; Installments MUST publish/consume these as explicit business events or direct service calls consistent with Constitution §49's event-driven guidance, never as direct writes to Accounting's tables.
- **FR-INST-271**: Every Accounting-facing installment action MUST respect Accounting's existing double-entry rules, `FiscalPeriod` open/locked/closed enforcement (BR-INST-021), posting locks, reversal semantics, and chart-of-accounts ownership — Installments never bypasses `PostingEngine`.
- **FR-INST-272**: Installments MUST NOT create duplicate AR, duplicate revenue recognition, duplicate payment records, duplicate journal entries, or any installment-specific shadow accounting (BR-INST-004).
- **FR-INST-273**: Where an Accounting posting required by an installment action fails (e.g., a locked period), the installment action MUST fail atomically — no partial contract-state change may be committed without its corresponding Accounting effect (see [§26](#26-failure--recovery-behavior)).
- **FR-INST-274**: Accounting remains the sole financial source of truth for every amount Installments displays as "paid," "outstanding," or "collected" — Installments' own records exist to explain and orchestrate, never to override Accounting's figures.

## 18. Inventory / CRM Integration

### 18.1 Inventory

- **FR-INST-280**: Financing a sale via an installment contract MUST NOT itself cause any duplicate stock movement; inventory effects remain governed exclusively by Sales'/Inventory's existing contracts, occurring (if at all) at the point of sale, not at contract activation or collection.
- **FR-INST-281**: Installment collection MUST NOT move stock under any circumstance.
- **FR-INST-282**: Returns affecting an installment-financed sale follow Sales'/Inventory's existing return rules unchanged; repossession is explicitly out of scope for this Epic ([§31](#31-out-of-scope)).

### 18.2 CRM / Customer Integration

- **FR-INST-290**: Authorized users MUST be able to view, in appropriate customer context, a customer's active installment contracts, outstanding amount, overdue amount, next due date, payment history, and completed/defaulted contracts where permitted by their role — without Installments duplicating the Customer Master record itself.
- **FR-INST-291**: Where the tenant uses CRM activities/notes, installment-related collection notes and activity SHOULD use the existing CRM activity/audit mechanisms rather than a parallel Installments-only note system.

## 19. Multi-Tenancy

### 19.1 Tenant & Branch Isolation

- **FR-INST-300**: Every installment operation (configuration, template, quote, contract, schedule, collection, allocation, search, report) MUST be scoped to the authenticated tenant's `company_id`, enforced at API, Service, and Repository layers, consistent with Constitution §9.
- **FR-INST-301**: Where the tenant has multi-branch enabled, contract and collection records MUST carry branch scope and support branch-scoped queries and reporting.
- **FR-INST-302**: Tenant-aware search and reporting MUST NEVER return, count, or otherwise reveal another tenant's installment records, including through indirect signals (e.g., sequential contract-number probing, error-message differences between "not found" and "not authorized").

### 19.2 Platform Admin / Support-Access Boundaries

- **FR-INST-310**: A Platform Administrator MUST NOT gain read or write access to any tenant's installment contract, schedule, collection, or audit data merely by virtue of governing that tenant's Installments entitlement (BR-INST-002).
- **FR-INST-311**: Where a Platform Admin has an active, time-bounded `SupportAccessGrant` for a tenant (Epic 9A), that grant's existing inspection-only, business-record-excluded scope (per `specs/009a-platform-admin/spec.md` §18.4/BR-9A-021) applies unchanged to Installments — installment contracts and schedules are tenant business records and remain outside support-access scope unless a future, separate specification amendment explicitly changes that boundary.

## 20. RBAC

### 20.1 Permission Catalogue

Following the existing dot-notation convention (`{module}.{entity}.{action}`, e.g. `accounting.payment.customer.approve`):

| Permission (representative) | Capability |
|---|---|
| `installments.config.manage` | Configure tenant-level installment policy |
| `installments.plan.manage` | Create/edit/deactivate plan templates |
| `installments.contract.view` | View installment contracts and schedules |
| `installments.contract.create` | Create a draft installment contract / generate a quote |
| `installments.contract.approve` | Approve a submitted contract |
| `installments.contract.activate` | Activate an approved contract |
| `installments.collection.create` | Record an installment collection |
| `installments.collection.reverse` | Reverse a recorded collection |
| `installments.charge.waive` | Waive a late charge |
| `installments.contract.reschedule` | Perform a controlled due-date amendment |
| `installments.contract.cancel` | Cancel a contract |
| `installments.contract.default` | Mark a contract as defaulted |
| `installments.contract.writeoff` | Write off a defaulted contract's balance |
| `installments.settlement.execute` | Generate/execute an early settlement |
| `installments.report.view` | View installment reports and dashboards |

- **FR-INST-320**: Each permission above MUST be independently checked; holding one installment permission MUST NEVER implicitly grant another, consistent with the platform's existing least-privilege model.
- **FR-INST-321**: High-risk operations (`activate`, `collection.create`, `collection.reverse`, `charge.waive`, `reschedule`, `cancel`, `default`, `writeoff`, `settlement.execute`) MUST each require their own explicit permission, distinct from `contract.view`.

### 20.2 Segregation of Duties / Maker-Checker

- **FR-INST-330**: The user who submits a contract for approval MUST NOT also approve it (mirrors Accounting's `SelfApprovalNotAllowedError` pattern).
- **FR-INST-331**: The user who marks a contract `DEFAULTED` MAY differ from the user who authorizes its `WRITTEN_OFF` transition; a tenant MAY additionally require these to be distinct actors as a configurable policy, but the system MUST always enforce that `writeoff` requires its own distinct permission from `default` regardless.
- **FR-INST-332**: Waiver of a late charge requires a permission distinct from the permission used to record ordinary collections.

## 21. Audit

- **FR-INST-340**: The following actions MUST produce a full, append-only audit record: contract creation, term changes before activation, approval, rejection, activation, schedule creation, collection, payment allocation, reversal, late-charge creation, waiver, rescheduling/amendment, settlement quote generation, settlement, cancellation, default, cure/restore-to-servicing, write-off, and configuration/template changes.
- **FR-INST-341**: Each audit record MUST identify: tenant, actor, action, target entity/ID, timestamp, a reason where the action requires one, and before/after state for sensitive changes — consistent with the existing per-module audit-log shape (Constitution §35; `AccountingAuditLog`/`PlatformAuditEvent` precedent).
- **FR-INST-342**: Audit records MUST be tenant-scoped and MUST NEVER expose another tenant's information; access to audit history MUST itself be permission-gated (`installments.contract.view` or a dedicated audit-view permission, per tenant RBAC configuration).
- **FR-INST-343**: If the audit write for a privileged installment action fails, the action itself MUST NOT be considered successfully committed (fail-closed), consistent with the pattern already established for Accounting and Platform Admin (BR-9A-024 precedent).

## 22. Feature Entitlement

### 22.1 Default State

- **FR-INST-350**: The Installments module MUST be disabled by default for a tenant unless the tenant's assigned Plan explicitly grants the `installments` Capability and the tenant has explicitly enabled the module-level toggle, consistent with the two-tier Plan-ceiling + tenant-toggle model established in Epic 9A.

### 22.2 Tenant-Level Enablement

- **FR-INST-351**: The system MUST register `installments` as a `grain=module` Capability in the existing Platform Admin Capability catalogue, and MUST provide a tenant-level, module-wide feature flag (following the CRM precedent of a true module master flag, not only fine-grained sub-feature flags), resolved through the existing `ModuleEnablementProvider` adapter.
- **FR-INST-352**: A tenant's effective Installments entitlement MUST be resolved by combining Plan ceiling, tenant module toggle, and any active `EntitlementOverride`, using the exact resolution precedence already defined in `specs/009a-platform-admin/spec.md` §17.2 — Installments introduces no competing resolution logic.

### 22.3 Behavior When Disabled — New Origination Blocked

- **FR-INST-353**: When Installments entitlement is disabled for a tenant (via subscription lapse, Plan capability removal, module toggle change, or entitlement override), all *new installment origination* operations MUST be blocked, returning a consistent, documented "module not entitled" error, per Constitution §11. Blocked origination operations include, at minimum: creating a new installment quote/preview, creating a new installment contract, activating a new contract, creating or modifying installment plan/templates, and changing installment configuration. Because they are not explicitly authorized as continued servicing under FR-INST-356, contract rescheduling, cancellation, marking default, and write-off also remain blocked while disabled.
- **FR-INST-354**: When Installments is disabled for a tenant, existing contracts and their schedules MUST remain visible in read-only form to authorized users, so obligations remain explainable and auditable, in addition to the active servicing operations permitted by [§22.4](#224-behavior-when-entitlement-is-disabled-after-contracts-exist).

### 22.4 Behavior When Entitlement Is Disabled After Contracts Exist

- **FR-INST-355**: Disabling entitlement (or a subscription lapse) MUST NEVER destroy, hide, or make uncollectible an existing financial obligation already created while the module was entitled (BR-INST-014).
- **FR-INST-356**: While entitlement is disabled, servicing of existing, legally/financially valid installment contracts MUST remain available to appropriately authorized users, distinct from the blocked origination operations in FR-INST-353. Servicing includes, at minimum: viewing existing contracts, schedules, balances, and payment history; generating statements; recording customer collections/payments against existing active or defaulted-but-serviceable contracts; allocating those authoritative Accounting payments to existing installment obligations; issuing/using existing payment-receipt mechanisms; performing payment reversal/correction where financially required and otherwise authorized; completing an existing contract through ordinary payment (FR-INST-104); performing early settlement/payment where necessary to discharge an existing obligation and permitted by the contract's existing terms ([§15.1](#151-early-settlement)); and other financial corrections strictly necessary to keep Installments reconciled with Accounting.
- **FR-INST-357**: This servicing exception is strictly scoped to discharging obligations that already existed before entitlement was disabled — it does NOT authorize creating new installment obligations, new contracts, new plan/templates, or any other new commercial activity (FR-INST-353). This is the permanent, resolved policy (see [OQ-2](#34-open-questions--clarifications)); it is not a tenant-configurable choice.
- **FR-INST-358**: Continued servicing under a disabled entitlement MUST NOT weaken any normal control — every servicing action performed under [§22.4](#224-behavior-when-entitlement-is-disabled-after-contracts-exist) remains fully subject to the same RBAC permission checks, audit logging (§21), Accounting fiscal-period enforcement (BR-INST-021), tenant isolation (§19), and idempotency/concurrency protections (§25) that apply when the module is enabled.

## 23. Reporting

- **FR-INST-360**: Epic 10 MUST expose, without implementing the broader Epic 11 reporting platform, at minimum: an installment contract register, a collection report, a due report, an overdue report, an aging report, a customer installment statement, a settlement report, a default/write-off report, and plan/template performance data.
- **FR-INST-361**: Every report MUST be tenant-scoped, support the platform's existing pagination/filtering conventions, and be computed from authoritative installment/financial state without double-counting (mirrors FR-INST-081).
- **FR-INST-362**: Report data MUST be structured and API-accessible so a future Epic 11 reporting/analytics platform can consume it without requiring Installments' own internal schema knowledge beyond the documented contract.

## 24. Security Requirements

- **FR-INST-370**: Every Installments endpoint MUST require authentication and MUST enforce tenant-scoped, permission-based authorization before any service call (Constitution §15, §16).
- **FR-INST-371**: Every request MUST be validated server-side; client-supplied `company_id`, `branch_id`, or ownership fields MUST NEVER be trusted over the authenticated session's tenant context (mass-assignment protection).
- **FR-INST-372**: Direct-object-reference endpoints (contract by ID, schedule line by ID) MUST verify tenant ownership before returning any data or performing any mutation, returning an identical "not found" response for both "does not exist" and "exists but belongs to another tenant" to prevent enumeration (IDOR prevention, BR-INST-015).
- **FR-INST-373**: High-risk financial commands MUST be replay/duplicate-protected via idempotency (see [§25](#25-concurrency--idempotency)).
- **FR-INST-374**: Sensitive installment actions (write-off, default, waiver, reschedule, cancellation, configuration change) MUST be auditable per [§21](#21-audit), and that auditability MUST itself be considered a security control, not merely a reporting convenience.
- **FR-INST-375**: Internal error details (stack traces, SQL, internal identifiers) MUST NEVER be exposed to clients in production, consistent with Constitution §21.
- **FR-INST-376**: Support-access and Platform Admin boundaries defined in [§19.2](#192-platform-admin--support-access-boundaries) MUST be enforced identically for Installments as for every other tenant business-record domain.

## 25. Concurrency / Idempotency

- **FR-INST-380**: Two concurrent collection requests against the same installment(s) MUST NOT result in over-collection; the system MUST enforce this via a deterministic conflict-handling mechanism (e.g., optimistic concurrency on the contract/schedule aggregate) such that one request succeeds and the other either fails cleanly or is correctly reduced to the remaining outstanding amount.
- **FR-INST-381**: Duplicate submission of the same collection, activation, settlement, or reversal request (e.g., client retry after a timeout) MUST NOT produce a duplicate financial effect; each such command MUST accept and honor an idempotency key, returning the original result for a repeated key rather than reprocessing.
- **FR-INST-382**: Concurrent contract-modification attempts (e.g., two approvers acting on the same `PENDING_APPROVAL` contract) MUST be resolved deterministically — the losing request MUST receive a clear conflict response, never a silently overwritten result.
- **FR-INST-383**: Concurrent write-off and collection attempts against the same contract MUST NOT both succeed if their combined effect would violate BR-INST-011 (no over-collection) or BR-INST-013 (default ≠ write-off ambiguity).
- **FR-INST-384**: No installment operation may ever produce a negative remaining balance on a scheduled installment or contract as a result of a race condition.

## 26. Failure / Recovery Behavior

- **FR-INST-390**: The system MUST require atomic business outcomes for every installment operation whose partial completion would create inconsistent financial state (e.g., contract marked `ACTIVE` without a reconciled schedule, or a collection recorded in Installments without its corresponding Accounting posting).
- **FR-INST-391**: Expected failure conditions the system MUST handle explicitly and safely include: Accounting posting failure, payment recording failure, schedule generation failure, invalid configuration, a stale/conflicting contract version, a disabled module, a suspended tenant, a closed/locked accounting period, an unauthorized action, a duplicate request, a cross-tenant reference, and an unavailable dependency (e.g., Accounting service temporarily unreachable).
- **FR-INST-392**: On any of the failure conditions above, the system MUST leave no partially applied state — either the full operation (state change + Accounting posting + audit record) succeeds, or none of it does.
- **FR-INST-393**: A closed/locked accounting period MUST produce a clear, documented error identifying the period constraint, not a generic failure (BR-INST-021).
- **FR-INST-394**: A suspended tenant (Epic 9A tenant lifecycle) MUST be denied all Installments activity consistent with however suspension is already enforced platform-wide — Installments introduces no separate suspension-enforcement mechanism.

## 27. Non-Functional Requirements

No specific numeric performance/scale targets exist elsewhere in the repository for a business module of this kind ([Assumption A8](#5-assumptions)); the following remain qualitative and testable, matching the precedent set by Epic 9A:

- **Correctness**: Schedule totals, allocation amounts, and aging computations MUST be exactly reconcilable against Accounting's authoritative figures at all times (BR-INST-005, BR-INST-007).
- **Security**: Every requirement in [§24](#24-security-requirements) is independently verifiable via security testing (IDOR, tenant-isolation, permission-boundary tests).
- **Tenant Isolation**: Every list, search, report, and detail endpoint is independently testable for cross-tenant leakage (BR-INST-001, BR-INST-015).
- **Consistency**: Concurrent and duplicate-request scenarios in [§25](#25-concurrency--idempotency) are independently testable for deterministic, non-duplicative outcomes.
- **Auditability**: Every action enumerated in [§21](#21-audit) is independently testable for producing exactly one, correctly attributed audit record.
- **Performance**: List/search/report endpoints MUST remain responsive under pagination as data volume grows, consistent with the platform's existing N+1-query prohibition (Constitution §25); no specific latency figure is fabricated here.
- **Scalability**: The data model MUST NOT assume a fixed maximum number of contracts, schedule lines, or collections per tenant.
- **Maintainability**: Installments follows the existing modular monolith module structure (Constitution §12) — API/schemas/models/services/repositories/validators/permissions/tests/docs — enabling independent review and testing.
- **Observability**: Every mutating installment operation MUST be logged consistent with Constitution §22 (structured logs including `company_id`, actor, action, duration, status).
- **Concurrency Safety**: Verified via [§25](#25-concurrency--idempotency)'s explicit requirements.
- **Recoverability**: Verified via [§26](#26-failure--recovery-behavior)'s atomicity requirements.

## 28. Edge Cases

- What happens when a contract's final installment amount would be zero or negative after rounding adjustment? The system MUST reject schedule generation with a clear validation error rather than producing a degenerate schedule line.
- What happens when a customer's eligibility changes (becomes blocked/over-limit) between quote generation and approval? Re-evaluation at approval time (FR-INST-023) MUST block approval with a clear reason.
- What happens when the originating sale/invoice is returned or voided after the installment contract is already `ACTIVE`? Sales'/Accounting's reversal rules apply (§16.1, §15.6); the contract MUST become explainable-but-inconsistent-flagged rather than silently continuing to demand payment for a reversed sale, requiring an authorized cancellation/adjustment action.
- What happens when a payment is recorded that exceeds the contract's total remaining balance? The excess MUST be handled per Accounting's existing overpayment rules (FR-INST-132), never silently discarded or silently overpaying a future installment beyond what's due without an explicit advance-payment allocation.
- What happens when two administrators attempt to approve/reject the same `PENDING_APPROVAL` contract simultaneously? One transition succeeds; the other receives a deterministic conflict response (FR-INST-382).
- What happens when a tenant disables a plan/template while contracts are mid-approval using it? The `PENDING_APPROVAL` contract's terms snapshot is already captured at submission and remains valid for approval; the deactivated template simply becomes unavailable for *new* contract creation (FR-INST-013).
- What happens when the accounting period for a scheduled due date is closed at the moment a late charge would post? The late-charge posting is blocked per BR-INST-021/FR-INST-393; the overdue installment state itself remains correctly derived independent of the blocked posting (FR-INST-122).
- What happens when a Platform Admin disables the Installments Capability at the Plan level for many tenants simultaneously (bulk plan change)? Each affected tenant's entitlement resolution and existing-obligation servicing protection (FR-INST-355–358) apply independently and identically — a bulk platform action never produces a blended or partial effect per tenant.
- What happens when a contract reaches `DEFAULTED` and is later fully collected voluntarily by the customer? If the collection fully satisfies the outstanding obligation, the contract completes directly (`DEFAULTED → COMPLETED`, FR-INST-104) as part of the servicing-continuity payment path (FR-INST-356), fully audited. If the customer instead resumes partial servicing without yet reaching full payoff and tenant policy permits curing, an authorized user may explicitly restore the contract to `ACTIVE` (`DEFAULTED → ACTIVE`, FR-INST-105/222). Either path is fully audited, and neither rewrites the contract's historical `DEFAULTED` event or Accounting history.
- What happens when a settlement quote's validity window expires before the customer pays? The stale quote MUST be rejected at payment time and a new quote generated (FR-INST-190/191), since settlement is only realized by authoritative payment, never by the quote itself (FR-INST-192).

## 29. Acceptance Scenarios

- **Scenario A — Standard installment sale**: Given an eligible, issued sales invoice and an eligible customer, when an officer generates a quote, submits for required approval, records the required down payment, and activates the contract, then a reconciled schedule exists and the contract is `ACTIVE`; subsequent on-time collections eventually bring it to `COMPLETED`.
- **Scenario B — Partial installment payment**: Given an active contract with a due installment, when a payment smaller than the scheduled amount is recorded, then that installment becomes `PARTIALLY_PAID` with an accurate remaining balance; when a subsequent payment covers the remainder, it becomes `PAID`.
- **Scenario C — Multi-installment payment**: Given an active contract with two due installments, when one payment covering both is recorded, then both installments are correctly satisfied per the oldest-due-first allocation policy (FR-INST-140), fully explainable via allocation metadata.
- **Scenario D — Advance payment**: Given an active contract with a future-dated installment not yet due, when a payment is recorded before that due date, then it is allocated correctly and the next outstanding obligation remains accurate (FR-INST-130).
- **Scenario E — Overdue**: Given an active contract with a due date that has passed the configured grace period without payment, when the installment/contract state is read, then it correctly shows `OVERDUE` with accurate days-overdue and aging bucket, computed on demand (FR-INST-122, FR-INST-180).
- **Scenario F — Early settlement**: Given an active contract with remaining balance, when a settlement quote is generated and the authoritative settlement payment is then recorded, then all remaining obligations are reconciled to zero and the contract becomes `COMPLETED` (FR-INST-190–192).
- **Scenario G — Payment reversal**: Given a previously `PAID` installment, when its underlying Accounting payment is reversed, then the installment's paid/remaining/overdue amounts and the contract's delinquency state are correctly recalculated, and Accounting remains reconciled (FR-INST-240).
- **Scenario H — Sale return/cancellation interaction**: Given an active installment contract, when the originating sale is returned per Sales'/Accounting's existing reversal rules, then the installment contract's state remains explainable and is resolved through an authorized cancellation/adjustment action, never silently orphaned (FR-INST-241, §16.1).
- **Scenario I — Tenant isolation**: Given Tenant A's installment contract, when Tenant B's authenticated user attempts to read, search, mutate, collect against, or settle it by direct identifier or search, then the request is denied with a response indistinguishable from "not found" (BR-INST-001, FR-INST-372).
- **Scenario J — Concurrent collection**: Given an active contract with exactly one remaining due installment, when two concurrent collection requests for its full amount are submitted simultaneously, then exactly one succeeds and the contract is never over-collected (FR-INST-380).
- **Scenario K — Entitlement disabled**: Given a tenant whose Installments entitlement is disabled, when that tenant's user attempts to originate new installment activity (new quote, new contract, activation, new plan/template, or configuration change), then the request is denied with a documented entitlement error; when that same tenant's authorized user instead records a collection or performs an early settlement against an existing, already-active or defaulted-but-serviceable contract, then the action succeeds, subject to normal RBAC/audit/Accounting-period/idempotency controls, per the resolved servicing policy in [§22.4](#224-behavior-when-entitlement-is-disabled-after-contracts-exist) (FR-INST-353–358).
- **Scenario L — Support access**: Given an active Epic 9A `SupportAccessGrant` for a tenant, when the granted Platform Admin inspects that tenant during the grant, then they cannot read, search, or mutate that tenant's installment contracts, consistent with the existing inspection-only, business-record-excluded boundary (FR-INST-311).

## 30. Success Criteria

- **SC-001**: An authorized user can move an eligible sale from quote to an `ACTIVE` installment contract with a fully reconciled schedule without any manual reconciliation step.
- **SC-002**: 100% of recorded installment collections are traceable, via allocation metadata, to exactly one authoritative Accounting payment/allocation record — zero orphaned or duplicated financial effects across representative test scenarios.
- **SC-003**: Zero cross-tenant data exposure across all tenant-isolation test scenarios in [§29](#29-acceptance-scenarios) (Scenario I) and [§24](#24-security-requirements).
- **SC-004**: Zero over-collection or double-settlement outcomes across all concurrency/idempotency test scenarios in [§25](#25-concurrency--idempotency) (Scenario J).
- **SC-005**: 100% of the actions enumerated in [§21](#21-audit) produce a correctly attributed, tenant-scoped audit record in representative test scenarios.
- **SC-006**: Disabling a tenant's Installments entitlement never results in a lost, hidden, uncollectible, or unexplainable existing financial obligation — existing contracts remain fully serviceable (viewable, collectible, and settleable) throughout, verified against Scenario K.
- **SC-007**: Every mandatory invariant in [§10](#10-business-rules--invariants) is covered by at least one automated test at the unit, integration, or security level once implementation begins.

## 31. Out of Scope

The following remain explicitly future-ready rather than implemented in Epic 10:

- External credit-bureau integration and automated credit scoring.
- Debt-collection-agency integration.
- Repossession workflow.
- Legal recovery / court workflow.
- Advanced restructuring/refinancing of an active contract's core financial terms (only due-date rescheduling is in scope, per FR-INST-202).
- Customer self-service payment portal.
- Payment-gateway autopay / direct debit.
- AI collection agent, AI credit-risk scoring, predictive default analytics.
- Any specific external notification-provider integration (channels remain integration-ready only, per FR-INST-050/051).
- The broader Epic 11 cross-domain reporting/analytics presentation platform (Installments exposes the data; Epic 11 presents it).
- Jurisdiction-specific consumer-finance regulatory disclosures/usury constraints ([Assumption A9](#5-assumptions)).
- Split/multiple concurrent installment financing of a single sale/invoice obligation. Epic 10 supports exactly one non-terminal installment contract per originating obligation at a time (FR-INST-042, FR-INST-251); the data model remains architecturally open to a future extension, but no tenant configuration may enable multiple concurrent contracts against the same obligation in this Epic.

## 32. Future Extension / AI Readiness

Epic 10 exposes clean, permission-safe, structured domain data (contracts, schedules, allocations, delinquency state, aging) so a future AI layer can, without becoming the financial source of truth: explain a customer's installment status, identify upcoming dues, summarize overdue exposure, suggest collection priorities, analyze payment patterns, forecast collections, and identify potentially risky accounts.

- AI MUST NOT bypass RBAC or tenant isolation ([§19](#19-multi-tenancy), [§20](#20-rbac)).
- AI MUST NOT autonomously waive, write off, settle, reverse, or otherwise financially mutate a contract without an explicit, authorized human-initiated workflow (BR-INST-020).
- AI integration itself is not part of Epic 10; this section only establishes that nothing in this specification blocks it later.

## 33. Risks

| Risk | Mitigation |
|---|---|
| Installments becomes a de-facto second accounting system if allocation/collection logic drifts from Accounting's model over time. | Enforce BR-INST-004/BR-INST-007 as hard architectural constraints in `/sp.plan`; every financial figure must be traceable to Accounting. |
| Money-precision mismatch between Sales (`NUMERIC(15,2)`) and Accounting (`NUMERIC(20,6)`) causes silent rounding drift if not resolved consistently. | Assumption A4 resolves this explicitly in Accounting's favor; `/sp.plan` MUST carry this forward without reintroducing ambiguity. |
| Entitlement-disable logic accidentally blocks legitimate collection/settlement against existing obligations, stranding a customer mid-contract. | FR-INST-355–358 make continued servicing (viewing, collection, settlement) explicit, scoped away from origination, and independently testable (Scenario K). |
| Deterministic schedule/aging logic diverges from Accounting's own `AgingCalculator` bucket definitions, producing two different "truths" for the same customer. | Assumption A7 mandates reuse of Accounting's exact bucket convention. |
| Concurrency bugs in collection allocation could allow over-collection under load. | FR-INST-380–384 mandate explicit, testable concurrency guarantees. |

## 34. Open Questions / Clarifications

- **OQ-1 — Epic numbering conflict ("Epic 10" vs. the stale "Epic 11" reference in `specs/005-inventory-management/spec.md`).** Repository inspection found two competing numbering references.
  **Resolved (this specification): Epic 10.** The two most recently authored/amended sources (`specs/008-accounting-finance/spec.md`, `specs/009a-platform-admin/spec.md`, and Constitution §11's example table) consistently use Epic 10; the inventory reference is stale and pre-dates the Epic 9A insertion. No renumbering of any existing epic occurs as a result of this resolution.
- **OQ-2 — Does a disabled Installments entitlement still permit *recording collections/settlement* against already-existing contracts, or only pure read-only servicing?** *(Permanently resolved — final product decision; no longer pending.)*
  **Resolved: Yes.** Existing, legally/financially valid installment obligations remain fully financially serviceable while entitlement is disabled — including recording collections, allocating payments, issuing receipts, payment reversal/correction where required, and early settlement/completion necessary to discharge the obligation (FR-INST-356). Only *new installment origination* (new quotes, new contracts, activation of new contracts, new plan/templates, configuration changes, rescheduling, cancellation, default, write-off) remains blocked while disabled (FR-INST-353, FR-INST-357, BR-INST-014). This is a permanent platform policy, not a tenant-configurable option, and servicing continuity never weakens normal RBAC, audit, Accounting fiscal-period, tenant-isolation, or idempotency controls (FR-INST-358).
- **OQ-3 — Should Installments support partial/split financing of a single sale/invoice across multiple concurrent installment contracts?** *(Permanently resolved — final product decision; no longer pending.)*
  **Resolved: No, permanently, for Epic 10.** At most one non-terminal (not `CANCELLED`/`COMPLETED`/`WRITTEN_OFF`) installment contract may exist against a given originating sale/invoice obligation at any time (FR-INST-042, FR-INST-251); this is not a tenant-configurable capability in Epic 10, and no wording in this specification authorizes a tenant to enable it. Split/multiple concurrent financing of a single invoice is explicitly Out of Scope ([§31](#31-out-of-scope)) and remains architecturally possible as a future extension without requiring rework of this baseline.

No other blocking clarifications remain; OQ-1, OQ-2, and OQ-3 are all permanently resolved, so this specification is ready for `/sp.plan`.

## 35. Constitution Compliance / Traceability

| Constitution Section | How Epic 10 Complies |
|---|---|
| §9 Multi-Tenant Principles | Every installment table/query is `company_id`-scoped at every layer ([§19](#19-multi-tenancy)). |
| §10 Multi-Branch Readiness | Branch-scoped contracts/collections where multi-branch is enabled (FR-INST-301). |
| §11 Feature Toggles | Installments is toggle-controlled per tenant, matching the Constitution's own `feature.installments.enabled` example ([§22](#22-feature-entitlement)). |
| §12 Module Design | Installments follows the standard module vertical-slice structure (api/schemas/models/services/repositories/validators/permissions/tests/docs) — deferred to `/sp.plan`. |
| §16 Authentication & Authorization | Every endpoint is authenticated and RBAC-gated before service calls ([§20](#20-rbac), [§24](#24-security-requirements)). |
| §17 Database Principles (Money Handling Standard) | All monetary values use `Decimal`/`NUMERIC`, never floats; currency stored alongside amounts ([Assumption A4](#5-assumptions), BR-INST-018). |
| §19 Security Principles | OWASP-aligned requirements throughout [§24](#24-security-requirements). |
| §35 Audit Trail | Installments' own audit log follows the existing who/what/when/before/after/context schema; append-only ([§21](#21-audit)). |
| §37 SaaS Readiness | Installments plugs into the existing Plan/Capability/Subscription model rather than defining a parallel one ([§22](#22-feature-entitlement)). |
| §46 Business Configuration Philosophy | Installment policy is tenant-configurable, never hardcoded ([§9.1](#91-installment-configuration-tenant-level)). |
| §48 Shared Kernel Principles | Money/currency handling follows the platform's `Decimal` convention; no competing value-object type introduced. |
| §49 Event-Driven Communication Principles | Installments publishes past-tense domain events for cross-module consumption ([§6.2](#62-new-requirements-introduced-by-epic-10), [§17](#17-accounting-integration)). |
| §50 Platform Administration & SaaS Control Plane Principles | Platform Admin governs entitlement only, never tenant business data ([§19.2](#192-platform-admin--support-access-boundaries)); Epic 9A's `SupportAccessGrant` boundary is preserved unchanged. |

---

**Version**: 1.1.0 (Draft) | **Created**: 2026-08-24 | **Last Corrected**: 2026-08-24 (targeted correction pass: entitlement-servicing policy, one-contract-per-obligation rule, lifecycle transition consistency)
