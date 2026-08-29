---
id: 0001
title: Epic 10 Installments specification
stage: spec
date: 2026-08-24
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: maamirkhan1983@gmail.com
command: /sp.specify
labels: [spec, installments, epic-10, accounting-integration, sales-integration, entitlement, rbac, multi-tenancy]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/010-installments/spec.md
 - specs/010-installments/checklists/requirements.md
tests:
 - none (specification-only task; no code, migrations, or tests created)
---

## Prompt

# Epic 10 — Installments — `/sp.spec`

Create the complete `spec.md` for **Epic 10 — Installments** of the existing DevSphere multi-tenant ERP SaaS.

This is a **specification-only** task.

Do **not** implement code.
Do **not** create migrations.
Do **not** create or modify `plan.md` or `tasks.md`.
Do **not** redesign completed epics.
Do **not** invent implementation details that belong in the planning phase.

The specification must define the business behavior, functional requirements, security boundaries, lifecycle rules, integration contracts, acceptance criteria, edge cases, and measurable success criteria for a production-grade installment-management capability.

---

# 1. Mandatory Repository Inspection

Before writing the specification, inspect the actual repository and treat the existing implementation as authoritative.

At minimum inspect:

* project constitution
* current feature/spec structure
* completed Epic 1–9 and Epic 9A artifacts where relevant
* Sales domain
* Accounting/Finance domain
* CRM/customer domain
* Companies / tenant model
* Users / Roles / RBAC
* Platform Administration / Super Admin
* subscription / entitlement / feature-control mechanisms
* audit infrastructure
* existing repository/service patterns
* existing money/currency conventions
* existing invoice/payment/receivable models and workflows
* existing migrations relevant to sales, accounting, customers, payments, tenant isolation, and platform administration
* existing API conventions
* existing test/security conventions

Do not assume names, tables, routes, statuses, roles, accounting behavior, or architectural seams that can be discovered from the repository.

If this prompt conflicts with an established repository contract or constitution rule, preserve the established contract and document the conflict or required clarification rather than silently redesigning the system.

---

# 2. Product Intent

Epic 10 introduces an enterprise-capable **Installment Management** domain for businesses that sell goods or services on installment/payment-plan terms.

The module must support businesses such as:

* home-appliance retailers
* electronics retailers
* furniture businesses
* equipment sellers
* distributors
* other businesses offering structured customer payment plans

However, the design must remain sufficiently generic for the ERP's multi-business SaaS direction.

The module must support the complete lifecycle:

**eligibility/configuration → installment quotation/terms → contract creation → schedule generation → activation → collections → allocation → overdue/delinquency → adjustments → early settlement → cancellation/default/write-off where authorized → closure → reporting/audit**

The module must not become a second accounting system.

---

# 3. Core Domain Ownership Boundary

The specification must explicitly establish and preserve the following conceptual ownership:

### Sales domain owns

* customer sale
* sales order/invoice lifecycle where already established
* sold items/services
* commercial sale context

### Accounting domain owns

* financial ledger truth
* journal entries
* accounts receivable truth where already established
* payment accounting
* reversals
* write-offs and financial postings where already established
* accounting periods and posting constraints

### Installments domain owns

* installment agreement/contract
* installment-specific commercial terms
* payment schedule
* installment lifecycle
* due-date state
* collection orchestration
* delinquency state
* settlement calculation/business workflow
* installment-specific history and audit context

Do not duplicate invoices, payments, receivables, journals, customers, or accounting balances merely to make the installment module self-contained.

Define integration contracts instead.

---

# 4. Feature Availability / Default State

The Installments module must be designed as an **optional ERP capability**.

The specification must define:

* module disabled by default unless the existing product/entitlement architecture requires another default
* tenant-level enablement
* compatibility with Platform Admin subscription/entitlement controls introduced by Epic 9A
* behavior when the module is disabled
* behavior for existing active installment contracts if entitlement is later removed or subscription state changes
* whether read-only servicing must continue for legally/financially existing contracts
* prohibition against destroying or hiding financial obligations merely because a feature entitlement is removed

Feature availability and financial-record integrity must be treated separately.

---

# 5. Tenant and Branch Isolation

Every installment operation must obey the ERP's existing tenant isolation architecture.

Specify requirements covering:

* company/tenant isolation
* branch scope where applicable
* customer ownership
* sale/invoice ownership
* contract ownership
* schedule ownership
* payment ownership
* collection ownership
* cross-tenant identifier probing
* tenant-aware searches
* tenant-aware reporting
* support-access boundaries from Epic 9A
* Platform Admin boundaries

No tenant user may read, infer, mutate, settle, cancel, collect against, or enumerate another tenant's installment records.

Platform administrators must not automatically gain access to tenant business records merely because they administer the SaaS platform.

Preserve the support-access security model established in Epic 9A.

---

# 6. Installment Configuration

Define tenant-level installment configuration requirements.

Consider at minimum:

* module enablement
* allowed installment frequencies
* minimum and maximum installment term
* minimum down payment
* optional maximum financed amount
* rounding policy
* grace-period policy
* overdue policy
* late-charge policy if enabled
* early-settlement policy
* approval thresholds
* backdating restrictions
* cancellation restrictions
* default/write-off authorization
* whether branch-specific overrides are permitted
* whether products/categories can be installment-eligible or installment-ineligible
* whether customer eligibility controls are supported

Configuration changes must not silently rewrite existing contracts.

Existing contracts must preserve the commercial terms under which they were activated unless an explicit authorized amendment workflow applies.

---

# 7. Installment Plans / Templates

Specify reusable installment-plan templates.

Examples conceptually include:

* 3 monthly installments
* 6 monthly installments
* 12 monthly installments
* custom schedules
* down-payment + installments
* zero-markup plans
* markup-bearing plans where legally/business-valid

A plan/template may define:

* name
* description
* active/inactive state
* frequency
* number of installments
* down-payment rule
* markup/service-charge rule if supported
* grace period
* late-charge policy
* early-settlement rule
* applicable products/categories if required
* approval requirements

Templates must be tenant-scoped.

Changing a template must not mutate contracts already created from the previous terms.

---

# 8. Customer Eligibility

Define how the ERP determines whether an installment contract may be offered to a customer.

The specification should support business-configurable controls without turning Epic 10 into a full credit-bureau system.

Potential factors may include:

* active customer status
* tenant ownership
* outstanding installment exposure
* overdue/default status
* configurable credit/installment limit
* manually approved exception
* customer blocking
* required customer information
* required guarantor/reference information only if the business enables such requirements

Do not require external credit-bureau integration in this epic unless an existing repository contract already requires it.

Future external credit scoring should remain architecturally possible.

---

# 9. Installment Quote / Preview

Before creating a binding installment agreement, authorized users must be able to preview the proposed terms.

The preview should expose business-relevant values such as:

* sale/invoice amount
* eligible amount
* down payment
* financed principal
* markup/service charge if applicable
* total contractual amount
* number of installments
* frequency
* first due date
* installment amounts
* final installment rounding adjustment
* expected completion date

Preview calculations must be deterministic.

A preview must not create financial postings merely because a user viewed installment terms.

---

# 10. Installment Agreement / Contract

Define a first-class installment agreement tied to the authoritative customer and sale/invoice context.

The contract must preserve a historical snapshot of agreed commercial terms sufficient to explain the obligation even if future configuration changes.

Consider fields/concepts such as:

* human-readable contract number
* customer
* originating sale/invoice
* tenant/company
* branch
* plan/template reference where applicable
* contract date
* principal/financed amount
* down payment
* markup/service charge
* contractual total
* installment count
* frequency
* first due date
* maturity date
* currency
* contract status
* terms snapshot
* creation actor
* approval actor where required
* activation timestamp
* closure timestamp

Do not prescribe database implementation in `spec.md`; define required business information and invariants.

---

# 11. Contract Lifecycle

Define an explicit, controlled lifecycle.

Consider states conceptually such as:

* DRAFT
* PENDING_APPROVAL
* APPROVED
* ACTIVE
* COMPLETED
* CANCELLED
* DEFAULTED
* WRITTEN_OFF

Use repository conventions if equivalent states already exist.

Define legal transitions.

Examples:

* draft may be edited
* approved/active financial terms must not be freely edited
* active contract cannot simply be deleted
* completed contract cannot accept ordinary new installment collections
* cancellation after financial activity requires controlled reversal/settlement behavior
* default and write-off are not synonyms
* write-off requires appropriate accounting integration and authorization

The specification must explicitly reject arbitrary status mutation.

---

# 12. Schedule Generation

The module must generate a deterministic installment schedule.

Support appropriate frequencies such as:

* weekly if enabled
* monthly
* quarterly if enabled
* custom schedule where allowed

Define:

* due-date calculation
* first due date
* subsequent due dates
* month-end behavior
* leap-year behavior
* rounding
* final-installment residual handling
* currency precision
* schedule total invariant
* schedule regeneration restrictions

The sum of scheduled contractual amounts must reconcile exactly with the contract amount under the ERP's money precision rules.

Once a contract becomes financially active, schedule regeneration must not silently rewrite history.

---

# 13. Installment Due-State Model

Each scheduled installment must expose a reliable business state.

Consider concepts such as:

* UPCOMING
* DUE
* PARTIALLY_PAID
* PAID
* OVERDUE
* WAIVED where legally/business permitted
* CANCELLED/VOIDED only through controlled workflows

Do not rely solely on a manually editable status field if state can be derived from authoritative dates and allocations.

Define the distinction between:

* scheduled amount
* amount paid
* amount remaining
* overdue amount
* days overdue

---

# 14. Collections and Payment Allocation

Define collection behavior carefully.

Support:

* exact installment payment
* partial payment
* payment covering multiple installments
* advance payment
* overpayment handling according to existing accounting rules
* payment reversal
* failed/reversed payment
* idempotent payment processing
* duplicate-request protection

The specification must define a deterministic allocation policy.

Unless the existing Accounting domain establishes another rule, prefer:

**oldest outstanding due obligation first**

while allowing an explicit business rule where needed.

A single payment may allocate across multiple scheduled installments.

An installment may receive multiple payments.

Do not create a parallel payment truth if Accounting already owns payment records.

Installments should maintain allocation/reference information needed to explain how authoritative payments satisfy scheduled obligations.

---

# 15. Down Payments

Define treatment of down payments.

Clarify:

* whether down payment occurs before activation
* relationship with Sales/Accounting payment records
* whether insufficient required down payment prevents activation
* refund/reversal behavior
* cancellation implications
* how down payment affects financed principal

Avoid double-counting down payments in receivables or revenue.

---

# 16. Overdue and Delinquency

Define deterministic overdue behavior.

The system should support:

* grace periods
* overdue detection
* days past due
* outstanding overdue amount
* customer-level overdue exposure
* contract-level delinquency
* aging buckets compatible with reporting
* configurable late charges if enabled
* authorized waiver where supported

Specify whether overdue state is derived on read, materialized by a scheduled process, or both only at the business-requirement level; implementation mechanics belong in planning.

Do not make the correctness of financial obligations depend solely on a background job having run.

---

# 17. Late Charges / Penalties

If late charges are supported, define strict rules.

Requirements should include:

* tenant configuration
* fixed or percentage policy where allowed
* no accidental repeated charging
* deterministic calculation
* auditability
* waiver authorization
* accounting integration
* reversal behavior
* contract snapshot of applicable policy

The specification must not assume that every tenant uses late charges.

Late charges must be optional.

---

# 18. Early Settlement

Support early payoff/settlement of an active contract.

The system must be able to determine:

* remaining principal/contractual balance
* outstanding charges
* settlement adjustment/discount if policy permits
* final settlement amount
* quote validity if applicable
* payment required to settle
* resulting contract closure

Settlement calculation must be reproducible and auditable.

Generating a settlement quote must not itself close the contract.

Only authoritative settlement/payment completion may do so.

---

# 19. Contract Amendments / Rescheduling

Do not permit arbitrary editing of active contracts.

If the business requires rescheduling, define a controlled amendment workflow.

The specification should distinguish:

* correcting a draft
* approved amendment
* due-date rescheduling
* commercial-term restructuring
* payment reversal
* accounting correction

Historical schedules and previous terms must remain explainable.

If full restructuring is beyond Epic 10 scope, explicitly mark it as a future extension rather than allowing unsafe editing.

---

# 20. Cancellation

Define cancellation rules by lifecycle stage.

Examples:

* draft cancellation
* approved but not activated cancellation
* active contract cancellation before collection
* cancellation after payments
* cancellation after accounting postings

Active contracts with financial activity must not simply disappear.

Cancellation must integrate with Sales/Accounting reversal rules and preserve audit history.

---

# 21. Default and Write-Off

Define default separately from write-off.

**Default** represents a business/collection state.

**Write-off** represents an authorized financial action and must integrate with Accounting.

Requirements should cover:

* authorization
* reason
* timestamp
* actor
* outstanding balance
* accounting consequences
* reversals where permitted
* audit evidence

Normal cashiers/sales users must not be able to write off receivables without explicit permission.

---

# 22. Refunds and Reversals

Specify behavior when:

* a payment is reversed
* a sale is returned
* an invoice is voided
* a refund occurs
* an accounting posting is reversed

Installment schedules and contract balances must remain reconcilable with authoritative financial records.

No destructive rewriting of historical payment allocations.

---

# 23. Sales Integration

Define the Installments ↔ Sales boundary.

Address:

* which eligible sales/invoices can become installment contracts
* prevention of duplicate installment contracts for the same obligation unless explicitly supported
* sale/invoice status requirements
* down payment
* returns
* cancellations
* invoice adjustments
* fully paid sales
* partially paid sales
* sale currency

Do not modify Sales ownership semantics merely to simplify Installments.

---

# 24. Accounting Integration

This is a critical section.

Inspect the existing Accounting implementation and define integration with its actual contracts.

The specification must prevent:

* duplicate AR
* duplicate revenue
* duplicate payments
* duplicate journal entries
* silent ledger mutation
* installment-specific shadow accounting

Define business events/integration requirements for relevant actions such as:

* contract activation
* down payment
* installment collection
* late charge
* waiver
* settlement
* reversal
* default
* write-off
* cancellation

Respect existing:

* double-entry rules
* accounting periods
* posting locks
* reversal semantics
* chart-of-accounts ownership
* idempotency conventions

Accounting remains the financial source of truth.

---

# 25. Inventory Integration

Installment status must not accidentally create a second inventory lifecycle.

Inventory effects remain governed by the existing Sales/Inventory contracts.

Clarify that:

* financing a sale does not itself cause duplicate stock movement
* installment collection does not move stock
* returns follow existing Sales/Inventory rules
* repossession, if ever supported, is a separate future business workflow unless explicitly already required

---

# 26. CRM / Customer Integration

Customer installment information should be visible through appropriate customer context.

Authorized users should be able to understand:

* active installment contracts
* outstanding amount
* overdue amount
* next due date
* payment history
* completed/defaulted contracts where permitted

Do not duplicate Customer Master.

Customer notes and collection activity should use existing CRM/audit mechanisms where appropriate.

---

# 27. RBAC and Segregation of Duties

Inspect existing roles/permissions and specify granular installment permissions compatible with the current RBAC system.

Conceptually distinguish capabilities such as:

* view installment contracts
* create draft
* generate quote
* approve contract
* activate contract
* collect payment
* reverse collection
* waive charge
* reschedule
* cancel
* mark default
* write off
* settle
* configure installment plans
* view installment reports

High-risk operations must require stronger permissions.

Where appropriate, specify maker-checker / segregation-of-duty expectations for high-value or high-risk actions without inventing a parallel authorization framework.

---

# 28. Audit Requirements

All financially or operationally significant actions must be auditable.

Include at minimum:

* contract creation
* term changes before activation
* approval
* activation
* schedule creation
* collection
* payment allocation
* reversal
* late-charge creation
* waiver
* rescheduling/amendment
* settlement quote
* settlement
* cancellation
* default
* write-off
* configuration changes

Audit records must identify appropriate context such as:

* tenant
* actor
* action
* target
* timestamp
* reason where required
* before/after values for sensitive changes where supported by existing audit architecture

Audit history must not expose another tenant's information.

---

# 29. Search and Operational Views

Specify useful operational queries/views such as:

* all contracts
* active contracts
* due today
* due this week
* overdue
* partially paid
* completed
* defaulted
* customer-specific
* branch-specific
* plan-specific
* collector/user-specific where applicable

Support search by appropriate identifiers such as:

* contract number
* customer
* invoice/sale reference

All search must remain tenant scoped.

---

# 30. Dashboard and KPIs

Define business metrics required from the installment domain.

Examples:

* active contracts
* total outstanding
* due today
* due this month
* collected today
* collected this month
* overdue amount
* overdue contracts
* collection rate
* aging distribution
* defaulted balance
* written-off balance
* upcoming receivables

Metrics must be based on authoritative financial/installment state and must not double-count amounts.

---

# 31. Aging

Specify installment receivable aging requirements.

At minimum consider:

* current/not yet due
* 1–30 days overdue
* 31–60
* 61–90
* 90+

Use existing accounting aging conventions if already defined.

Aging must be reproducible as of a requested business date where the existing reporting architecture supports historical/as-of reporting.

---

# 32. Notifications / Reminders

Define integration-ready business events for reminders such as:

* upcoming installment
* installment due today
* overdue installment
* payment received
* contract completed

Do not require a full communications platform if one does not already exist.

The specification should keep future channels possible:

* in-app
* email
* SMS
* WhatsApp

No external provider integration is required merely because these channels are future-capable.

---

# 33. Documents

Define requirements for customer-facing installment documents where appropriate:

* installment agreement/contract
* payment schedule
* payment receipt through existing receipt mechanisms
* settlement quotation
* account/installment statement

Documents must use authoritative stored terms and payment information.

Document generation must not change financial state.

---

# 34. Currency and Money Rules

Follow the ERP's existing money/currency architecture.

Specify:

* decimal precision
* rounding consistency
* currency immutability where required
* no floating-point financial arithmetic
* schedule reconciliation
* payment reconciliation
* settlement reconciliation

Do not introduce multi-currency behavior beyond what the existing ERP supports.

---

# 35. Dates, Time Zones and Business Dates

Specify consistent handling for:

* contract date
* first due date
* due dates
* payment date
* grace periods
* overdue calculation
* settlement date
* branch/company timezone where applicable
* accounting business date where already established

Due-date correctness must not depend on server-local timezone assumptions.

---

# 36. Concurrency and Idempotency

The specification must explicitly cover concurrent/high-risk operations.

Examples:

* two cashiers collecting the same installment simultaneously
* duplicate payment requests
* repeated activation request
* repeated settlement request
* duplicate reversal
* concurrent write-off/collection
* concurrent contract modification

Required outcomes:

* no duplicate financial effect
* no negative remaining balance due to race conditions
* no duplicate schedule
* no double settlement
* deterministic conflict handling

---

# 37. Immutability and Historical Integrity

Once financially active, critical contract terms and financial history must not be destructively edited.

Require historical integrity for:

* original terms
* schedules
* allocations
* reversals
* settlements
* status transitions
* write-offs
* audit records

Corrections should use controlled compensating/amendment workflows where appropriate.

---

# 38. Data Migration / Existing ERP Data

The specification must address compatibility with existing customers, invoices, sales, payments, and accounting data.

Do not assume every existing sale becomes an installment sale.

Define eligibility/transition behavior for creating installment contracts against pre-existing records only if safe and explicitly permitted.

No migration should silently reinterpret historical cash/credit sales as installment contracts.

---

# 39. Failure Handling

Define expected behavior for failures such as:

* accounting posting failure
* payment recording failure
* schedule generation failure
* invalid configuration
* stale contract version
* disabled module
* suspended tenant
* closed accounting period
* unauthorized action
* duplicate request
* cross-tenant reference
* unavailable dependency

The specification must require atomic business outcomes where partial completion would create inconsistent financial state.

---

# 40. Security Requirements

Include explicit security requirements for:

* authentication
* authorization
* tenant isolation
* branch scope
* IDOR prevention
* mass-assignment protection
* financial-operation authorization
* replay/duplicate protection
* sensitive auditability
* support-access boundaries
* Platform Admin boundaries
* safe error behavior
* input validation

Cross-tenant identifiers must never reveal another tenant's financial/business data through response content, search results, counts, error differences, or indirect metadata.

---

# 41. Required End-to-End Business Scenarios

The specification must include acceptance scenarios covering at minimum:

### Scenario A — Standard installment sale

Sale → installment quote → required approval → down payment → activation → schedule → collections → completion.

### Scenario B — Partial installment payment

Installment receives partial payment → remains partially paid → remaining balance accurate → subsequent payment closes it.

### Scenario C — Multi-installment payment

One payment covers more than one due installment using deterministic allocation.

### Scenario D — Advance payment

Customer pays before future due date → allocation and next outstanding obligation remain correct.

### Scenario E — Overdue

Due date passes → installment becomes overdue according to business-date/grace rules → aging and customer exposure update correctly.

### Scenario F — Early settlement

Settlement quote → authoritative payment → all remaining obligations reconciled → contract completed.

### Scenario G — Payment reversal

Previously paid installment payment reversed → allocation/balance/delinquency state recalculated correctly → accounting remains reconciled.

### Scenario H — Sale return/cancellation interaction

Existing Sales/Accounting reversal rules are respected and installment state remains explainable.

### Scenario I — Tenant isolation

Tenant A cannot discover/read/modify/collect/settle Tenant B's installment contract using direct identifiers or search.

### Scenario J — Concurrent collection

Two concurrent attempts cannot over-collect or duplicate financial effect.

### Scenario K — Entitlement disabled

Tenant without Installments entitlement cannot create new installment activity, while existing financial obligations remain safely accessible/servicable according to the defined entitlement policy.

### Scenario L — Support access

Platform/support user behavior follows Epic 9A boundaries and cannot bypass business-record restrictions.

---

# 42. Reporting Requirements

Define Installment-specific reporting requirements without unnecessarily implementing the broader Epic 11 reporting platform.

Epic 10 should expose the domain data/queries necessary for later reporting.

At minimum specify:

* installment contract register
* collection report
* due report
* overdue report
* aging report
* customer installment statement
* settlement report
* default/write-off report
* plan performance where appropriate

Epic 11 may later provide richer cross-domain analytics/presentation.

---

# 43. API / Contract Expectations

Do not prematurely design exact endpoint implementation if repository conventions have not yet been inspected.

However, `spec.md` must define the business capabilities required from the API surface and require:

* tenant-scoped behavior
* stable request/response semantics
* validation
* pagination for collections
* filtering/search where appropriate
* idempotency for high-risk commands
* conflict handling
* consistent error semantics
* RBAC
* auditability

Reuse existing API conventions.

---

# 44. Non-Functional Requirements

Define measurable requirements where appropriate for:

* correctness
* security
* tenant isolation
* consistency
* auditability
* performance
* scalability
* maintainability
* observability
* concurrency safety
* recoverability

Avoid arbitrary performance numbers unless justified by the existing project conventions.

---

# 45. Out of Scope / Future Readiness

Explicitly identify items that should remain future-ready rather than being overbuilt in Epic 10.

Potential examples:

* external credit bureau integrations
* automated credit scoring
* debt-collection agency integration
* repossession workflow
* legal recovery/court workflow
* advanced restructuring/refinancing
* customer self-service payment portal if not already in roadmap
* payment-gateway autopay
* direct debit
* AI collection agent
* AI credit-risk scoring
* predictive default analytics

Do not implement speculative integrations in this epic.

Keep extension seams where appropriate.

---

# 46. AI Readiness

The ERP will later receive an AI layer.

Epic 10 must therefore expose clean, permission-safe domain capabilities and structured data so future AI can assist with activities such as:

* explaining customer installment status
* identifying upcoming dues
* summarizing overdue exposure
* suggesting collection priorities
* analyzing payment patterns
* forecasting collections
* identifying potentially risky accounts

However:

* AI must not become the financial source of truth
* AI must not bypass RBAC
* AI must not bypass tenant isolation
* AI must not autonomously waive, write off, settle, reverse, or financially mutate contracts without explicit authorized workflows
* AI integration itself is not part of Epic 10 unless already required by the repository roadmap

---

# 47. Specification Quality Requirements

The generated `spec.md` must be:

* implementation-agnostic where appropriate
* precise
* testable
* internally consistent
* aligned with existing repository architecture
* free of unresolved contradictions
* explicit about invariants
* explicit about lifecycle transitions
* explicit about security boundaries
* explicit about domain ownership
* explicit about failure behavior
* explicit about acceptance criteria

Avoid vague requirements such as:

* "handle securely"
* "support installments properly"
* "integrate with accounting"

Replace them with testable business requirements.

Use requirement IDs consistent with the repository/spec convention.

---

# 48. Required Specification Sections

Follow the repository's established SpecKitPlus/spec format, but ensure the final specification covers at least:

1. Feature Overview
2. Goals
3. Non-Goals
4. Actors / Roles
5. Assumptions
6. Dependencies
7. Domain Ownership
8. Functional Requirements
9. Business Rules / Invariants
10. Installment Lifecycle
11. Schedule Rules
12. Collection / Allocation Rules
13. Delinquency Rules
14. Settlement / Cancellation / Default / Write-Off
15. Sales Integration
16. Accounting Integration
17. Inventory / CRM Integration
18. Multi-Tenancy
19. RBAC
20. Audit
21. Feature Entitlement
22. Reporting
23. Security Requirements
24. Concurrency / Idempotency
25. Failure / Recovery Behavior
26. Edge Cases
27. Acceptance Scenarios
28. Success Criteria
29. Out of Scope
30. Future Extension / AI Readiness

If the existing template organizes these differently, preserve the repository template while ensuring none of these concerns are omitted.

---

# 49. Mandatory Invariants

The specification must explicitly encode at least these invariants:

1. A tenant can never access another tenant's installment business data.
2. Platform administration does not imply unrestricted tenant-business-data access.
3. An installment contract must reference authoritative existing customer/sales context.
4. Installments must not duplicate Accounting's financial source of truth.
5. Installment schedule totals must reconcile exactly with contractual totals.
6. Collections must not create duplicate financial effects.
7. Payment allocations must be explainable and auditable.
8. Active financial contracts cannot be destructively edited.
9. Configuration/template changes cannot silently rewrite active contracts.
10. A contract cannot be completed while an authoritative outstanding obligation remains.
11. A contract cannot be over-collected through concurrency or duplicate requests.
12. Write-off requires explicit authorization and Accounting integration.
13. Default and write-off are distinct states/actions.
14. Disabled feature entitlement cannot erase existing financial obligations.
15. Cross-tenant identifiers must not leak data.
16. Every high-risk financial mutation must be auditable.
17. Reversals must preserve history rather than deleting the original financial event.
18. Financial calculations must use the ERP's established decimal/money rules.
19. Schedule/date behavior must be deterministic.
20. AI or support tooling may never bypass normal financial authorization boundaries.

---

# 50. Final Self-Review Before Completion

Before declaring `spec.md` complete, perform a specification review against:

### Architecture

* Does this duplicate Sales?
* Does this duplicate Accounting?
* Does this duplicate CRM?
* Does this violate existing service/repository boundaries?

### Financial correctness

* Can any flow double-count AR?
* Can any flow double-record a payment?
* Can rounding create unreconciled schedules?
* Can reversal destroy history?
* Can concurrent collection overpay a contract?

### Security

* Is every business operation tenant scoped?
* Are Platform Admin/support boundaries preserved?
* Are high-risk operations permission protected?
* Are IDOR/cross-tenant enumeration paths addressed?

### Lifecycle

* Are legal state transitions explicit?
* Are cancellation/default/write-off distinct?
* Are active contracts immutable except through controlled workflows?

### SaaS

* Is module entitlement behavior defined?
* Are existing obligations protected when entitlement changes?
* Are tenant configuration and template snapshots preserved?

### Testing

* Can every important requirement be proven by unit/integration/security/E2E testing later?

Resolve contradictions before finalizing.

---

# 51. Final Output

Create/update **only the Epic 10 `spec.md`** required by the repository's SpecKitPlus structure.

At the end, report:

* specification path
* major requirement groups created
* number of functional requirements
* number of acceptance scenarios/user stories
* number of explicit business/security invariants
* assumptions made
* repository conflicts discovered, if any
* unresolved `[NEEDS CLARIFICATION]` items, if any

Do not create `plan.md`.

Do not create `tasks.md`.

Do not implement any application code.

Stop after the specification and summary are complete.

## Response snapshot

Inspected the repository (constitution, Sales, Accounting, Platform Admin/Epic 9A, RBAC, audit infrastructure, API conventions) via a research agent before writing anything, confirming Installments is fully greenfield (no existing installment/payment-plan concept) and surfacing two conflicts to resolve rather than silently redesign: (1) Sales uses `NUMERIC(15,2)` money precision vs. Accounting's `NUMERIC(20,6)` — resolved in Accounting's favor since installments settle against AR (Assumption A4); (2) `specs/005-inventory-management/spec.md` still calls this "Epic 11" — resolved as stale, "Epic 10" is authoritative per Constitution §11, `008-accounting-finance`, and `009a-platform-admin`.

Created branch `010-installments` via `.specify/scripts/bash/create-new-feature.sh --number 10 --short-name installments`, then wrote `specs/010-installments/spec.md` as a 35-section long-form specification following the same "Official Business Specification" convention established by `009a-platform-admin/spec.md` and `009-crm/spec.md` (Table of Contents, `US-N` prioritized user stories, `FR-INST-NNN` functional requirements grouped by domain, a `BR-INST-NNN` business-rules/invariants table, `Scenario A–L` acceptance scenarios, an `OQ-N` open-questions log with resolved defaults instead of unresolved `[NEEDS CLARIFICATION]` markers, and a closing Constitution-compliance traceability table) — the required 30-section minimum topic list is fully covered and cross-indexed.

Key design decisions encoded in the spec: Installments owns the contract/schedule/lifecycle/delinquency/settlement-workflow only, never a shadow invoice/payment/journal/AR balance (Accounting remains sole financial source of truth, enforced via `PostingEngine`/`FiscalPeriod`/`Payment`/`PaymentAllocationLine` integration contracts, never direct writes); entitlement follows the Epic 9A two-tier Plan-Capability + tenant module-toggle model with a CRM-style module-wide master flag, and disabling entitlement never hides or destroys existing obligations (read-only servicing continues); allocation policy is oldest-due-first FIFO; aging reuses Accounting's exact 6-bucket convention; RBAC follows the existing dot-notation permission convention with maker-checker segregation of duty mirroring Accounting's `SelfApprovalNotAllowedError` pattern; write-off is authorization-distinct from default. All 20 mandated invariants are encoded as BR-INST-001–020 plus 2 repository-grounded additions (fiscal-period locking, currency immutability) = 22 total. All 12 required acceptance scenarios (A–L) are present. Three Open Questions were raised and resolved with documented defaults (epic numbering, whether disabled-entitlement tenants can still record new collections against existing contracts, and single-vs-multiple contracts per invoice) — zero unresolved `[NEEDS CLARIFICATION]` markers remain.

Created the required `specs/010-installments/checklists/requirements.md` quality checklist; all items pass on first validation pass (one item carries an explicit note justifying the deliberate, precedent-matching exception of naming existing repository integration points like `PostingEngine`/`FiscalPeriod`/`ModuleEnablementProvider` for boundary-definition purposes, not as Epic 10 implementation prescription).

No `plan.md` or `tasks.md` was created or modified. No application code, migrations, or tests were written, per the specification-only scope of this task.

## Outcome

- ✅ Impact: Epic 10 — Installments now has a complete, repository-grounded, internally consistent `spec.md` (35 sections, ~180 FR-INST functional requirements, 22 BR-INST business rules/invariants, 8 prioritized user stories, 12 required acceptance scenarios, 10 edge cases, 7 measurable success criteria) ready for `/sp.clarify` and `/sp.plan`.
- 🧪 Tests: none (specification-only task; test creation belongs to future implementation phases)
- 📁 Files: specs/010-installments/spec.md (created); specs/010-installments/checklists/requirements.md (created)
- 🔁 Next prompts: `/sp.clarify` (recommended, to confirm OQ-2 — whether disabled-entitlement tenants may still record collections against pre-existing contracts) or directly `/sp.plan` once the product owner reviews the three resolved Open Questions in §34.
- 🧠 Reflection: The 51-section source prompt maps cleanly onto the repository's existing "Official Business Specification" long-form convention (already used twice, in Epic 9 and Epic 9A) rather than the shorter generic `spec-template.md` — recognizing and reusing that established pattern kept the new spec consistent with its siblings instead of introducing a third, competing format.

## Evaluation notes (flywheel)

- Failure modes observed: none blocking; the checklist's "no implementation details" item required one explicit, documented exception rather than a clean pass, since the mandatory repository-inspection instruction necessarily pulls in named existing constructs (e.g., `PostingEngine`, `FiscalPeriod`) for integration-boundary definition.
- Graders run and results (PASS/FAIL): Spec Quality Checklist (`specs/010-installments/checklists/requirements.md`) — PASS on first iteration, all items checked.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
