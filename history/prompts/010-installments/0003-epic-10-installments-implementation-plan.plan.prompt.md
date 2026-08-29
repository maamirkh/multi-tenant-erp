---
id: 0003
title: Epic 10 Installments implementation plan
stage: plan
date: 2026-08-24
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: /sp.plan
labels: [installments, epic-10, planning, accounting-integration, entitlement, concurrency, idempotency]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/010-installments/plan.md
 - specs/010-installments/research.md
 - specs/010-installments/data-model.md
 - specs/010-installments/contracts/installments-api.yaml
 - specs/010-installments/quickstart.md
 - CLAUDE.md
tests:
 - none (planning-only phase; no code, migrations, or tests created per stop condition)
---

## Prompt

# Epic 10 — Installments

## `/sp.plan` — Full & Final Planning Prompt

Create the complete implementation plan for:

`specs/010-installments/plan.md`

for:

**Epic 10 — Installments**

Feature branch:

`010-installments`

The authoritative business specification is:

`specs/010-installments/spec.md`

The current specification has completed its targeted correction pass and is ready for planning.

---

# 1. PRIMARY INSTRUCTION

Generate an **implementation-ready technical plan**, not another business specification.

The plan MUST translate every relevant requirement, invariant, lifecycle rule, integration boundary, security rule, entitlement rule, concurrency requirement, and acceptance scenario from `spec.md` into a concrete architecture that fits the **existing repository**.

Do NOT implement code.

Do NOT generate `tasks.md`.

Do NOT create migrations.

Do NOT modify existing application source.

Do NOT redesign or reopen approved product decisions from `spec.md`.

Do NOT silently change business behavior because another implementation would be easier.

The output of this phase is the technical architecture and implementation strategy that `/sp.tasks` can later decompose into executable tasks.

---

# 2. MANDATORY REPOSITORY INSPECTION BEFORE PLANNING

Before writing `plan.md`, inspect the repository thoroughly.

Do not design Epic 10 as a greenfield application.

The existing ERP architecture is authoritative wherever it already defines a reusable pattern.

At minimum inspect:

* project Constitution
* Epic 7 — Sales
* Epic 8 — Accounting & Finance
* Epic 9 — CRM
* Epic 9A — Platform Administration / Super Admin
* Users / Roles / Permissions implementation
* company/tenant scoping
* branch scoping
* repository/service patterns
* API/router conventions
* response/error conventions
* database model conventions
* Alembic migration conventions
* audit implementations
* Accounting transaction/posting mechanisms
* payment and AR implementations
* fiscal-period enforcement
* entitlement resolution
* module enablement
* Platform Admin support-access boundaries
* existing idempotency implementations
* existing concurrency/versioning patterns
* testing architecture
* frontend architecture
* existing document/receipt mechanisms
* structured logging conventions
* domain-event conventions

Specifically locate and inspect repository implementations for concepts equivalent to:

`SalesInvoice`

`SalesOrder`

`Customer`

`Payment`

`PaymentAllocationLine`

`PaymentRefund`

`ARTransaction`

`CustomerLedger`

`JournalEntry`

`PostingEngine`

`FiscalPeriod`

`AgingCalculator`

`Capability`

`Plan`

`PlanCapability`

`Subscription`

`EntitlementOverride`

`ModuleEnablementProvider`

`SupportAccessGrant`

existing module feature flags

RBAC permission models/services

maker-checker implementations

audit-log implementations

idempotent command implementations

document numbering

branch handling

Do not rely only on prior specifications if actual implementation exists.

**Repository implementation wins for technical patterns.**

The approved Epic 10 `spec.md` wins for Epic 10 business behavior.

If repository implementation and `spec.md` appear incompatible, document the conflict and design the smallest safe adaptation necessary without silently changing the specification.

---

# 3. PLANNING PRINCIPLE

Epic 10 MUST be implemented as a new vertical domain inside the existing modular-monolith architecture.

Do NOT create:

* a microservice
* a second Accounting subsystem
* a second Sales subsystem
* a second Customer Master
* a second payment ledger
* a second AR ledger
* a generic workflow engine unless the repository already requires one
* a generic audit framework solely for Epic 10
* unnecessary infrastructure abstractions

Prefer existing repository conventions.

Introduce new abstractions only where Installments genuinely requires them.

---

# 4. REQUIRED PLAN STRUCTURE

The generated `plan.md` MUST include, at minimum, 39 numbered sections: Technical Context, Repository Findings, Constitution Compliance, Architecture Overview, Domain Boundary, Domain Model, Database/Persistence Design, Money & Precision Strategy, Installment Lifecycle Architecture, Schedule Engine, Collection/Allocation Architecture, Accounting Integration, Sales Integration, CRM/Inventory Integration, Entitlement Architecture, RBAC/Maker-Checker, Audit Architecture, Multi-Tenant/Branch Isolation, Concurrency Strategy, Idempotency Strategy, Transaction/Atomicity Boundaries, Failure/Recovery Design, API Architecture, Frontend Architecture, Reporting/Query Architecture, Domain Events, Documents/Statements, Background Processing, Security Architecture, Migration Strategy, Testing Strategy, Observability, Performance/Indexing, Deployment/Backward Compatibility, Future AI Readiness, Implementation Sequence/Dependency Graph, Risks/Trade-Offs, Requirement Traceability, Open Technical Decisions — plus additional sections where repository inspection proves necessary.

[Sections 5 through 45 of the original prompt specify, in exhaustive detail: the required domain model (InstallmentConfiguration, InstallmentPlan/Template, InstallmentContract, InstallmentScheduleLine, Schedule Version/Amendment, InstallmentAllocationReference, InstallmentAuditLog, Installments Feature Flag/Enablement); the hard one-contract-per-originating-obligation invariant requiring database-level (not merely application-level) enforcement; the money/decimal strategy requiring Accounting-compatible NUMERIC precision, exact schedule-to-contract-total reconciliation, and deterministic final-installment residual assignment; the explicit contract state machine (DRAFT, PENDING_APPROVAL, APPROVED, ACTIVE, DEFAULTED, COMPLETED, CANCELLED, WRITTEN_OFF) with REJECTED modeled as an event/action rather than a persisted state, and no generic set_status escape hatch; explicit DEFAULTED→ACTIVE cure/restore-to-servicing semantics distinct from write-off, and DEFAULTED→COMPLETED via full payoff without forcing an unnecessary cure; a deterministic, independently unit-testable schedule engine covering monthly/weekly/quarterly frequencies, month-end and leap-year handling, rounding, grace periods, and schedule versioning after rescheduling; due-state derivation preferring computation over a freely mutable status field, with authoritative-state-vs-cached-projection distinguished if materialization is used; an extremely detailed Accounting Integration section covering down payment, collection, payment allocation, reversal, late charge, waiver, early settlement, cancellation, default (explicitly no posting), write-off, and fiscal-period enforcement, each specifying caller/callee/transaction owner/authoritative data/Installments metadata/failure behavior/audit behavior/domain event, with no direct writes into Accounting tables permitted; explicit transaction/atomicity boundaries for activation, collection, settlement, reversal, cancellation, default, cure, write-off, and rescheduling, grounded in actual repository transaction management rather than assumed distributed-transaction complexity; concurrency protection against duplicate contract creation, over-collection, double settlement, duplicate activation, concurrent schedule modification, concurrent approval/rejection corruption, collection/write-off race, and collection/reversal race, with the specific protection mechanism named per race condition; idempotency requirements for activation, collection, settlement, reversal, rescheduling, cancellation, default, and write-off, including key ownership, tenant/operation scoping, request fingerprinting, stored result, retry behavior, conflicting-payload behavior, and atomic relationship to the business transaction; a critical corrected entitlement requirement distinguishing origination permission (blocked when entitlement disabled: new quotes, new contracts, activation of new contracts, plan/template creation/modification, configuration changes) from existing-obligation servicing (continues under disabled entitlement: viewing, collections, allocation, receipts, necessary payment correction/reversal, ordinary payoff, early settlement required to discharge the obligation) via a centralized policy/service rather than scattered ad-hoc `if installments_enabled` checks, with explicit reasoning about where entitlement is checked (API boundary vs. service vs. both) and how TOCTOU/race concerns are handled for financial commands; explicit non-confusion of suspended-tenant behavior (follows Epic 9A's platform-wide suspension) with disabled-module behavior (existing obligations remain serviceable); a full RBAC permission catalogue mapping (config.manage, plan.manage, contract.view/create/approve/activate, collection.create/reverse, charge.waive, contract.reschedule/cancel/default/writeoff, settlement.execute, report.view) plus explicit consideration of a distinct cure permission so cure authority is never accidentally granted through ordinary collection permission; maker-checker enforcement at the service/domain level (submitter cannot approve their own contract) plus explicit evaluation of maker-checker for rescheduling, write-off, and charge waiver; fail-closed audit covering creation, submission, rejection, approval, activation, collection, allocation, reversal, charge, waiver, reschedule, settlement quote generation, settlement, cancellation, default, cure, write-off, and configuration/template changes, participating in the same transaction as the business action where repository conventions allow; strict multi-tenancy enforcement at API/Service/Repository layers with cross-tenant ID access indistinguishable from non-existent resource, and tenant-scoped contract numbering; non-overbuilt branch readiness following existing platform patterns without inventing a new branch authorization system; strict preservation of Epic 9A's Platform Admin/SupportAccessGrant boundary — Platform Admin may manage Installments entitlement but must never gain tenant business-record access, with security tests proving this; explicit REST API architecture using command endpoints rather than generic PATCH status mutation, covering Configuration, Plans/Templates, Eligibility, Quote/Preview, Contracts, Submission/Approval/Rejection, Activation, Schedules, Collections, Reversals, Settlement Quotes, Settlement Execution, Rescheduling, Cancellation, Default, Cure, Write-Off, Reports/Dashboard, and Documents/Statements endpoint groups, each documenting method/path/permission/entitlement policy/tenant scope/idempotency requirement/major request-response contract/major failure codes; a Next.js frontend plan consistent with existing ERP conventions (not redesigning global navigation/design system) covering dashboard, contracts list, contract detail (as the operational center, with Summary/Terms/Schedule/Payments/Delinquency/Audit-History/Documents sections or the ERP's existing equivalent convention), new-quote/contract-creation, approval queue, schedule, collections, settlement, delinquency/default, plans/templates, configuration, reports, and statements/documents views, with permission-based action visibility while backend remains authoritative; explicit UI behavior when entitlement is disabled but contracts exist — never hiding the entire module in a way that strands existing obligations, disabling/hiding only "New Contract" and plan/config management while servicing routes and actions remain accessible per RBAC; operational reporting (contract register, collection report, due report, overdue report, aging, customer statement, settlement report, default/write-off report, plan performance data) distinguishing Installments-contractual-derived values from Accounting-authoritative-financial-derived values, without denormalizing financial truth merely for dashboard convenience unless clearly labeled non-authoritative; a database/indexing strategy (not migration code) covering company_id, company+contract number, company+customer, company+originating invoice, company+status, branch, due date, schedule outstanding queries, overdue operational queries, Accounting payment/allocation references, idempotency keys, audit target/time, and plan/template active state indexes, with unique/partial-unique constraints, FKs, check constraints, nullable decisions, and safe (non-cascading) delete behavior explicitly identified; a dependency-safe migration strategy (still no actual migration code) proposing table creation order, downgrade behavior, production-safe index-creation considerations, capability/permission seed/registration, and an explicit guarantee that no pre-existing Sales/Accounting data is rewritten and no pre-existing sale automatically becomes an installment contract; past-tense-named domain events (e.g. InstallmentContractActivated, InstallmentCollected, InstallmentOverdue, InstallmentSettled, InstallmentDefaulted, InstallmentCured, InstallmentWrittenOff, InstallmentCancelled) each defining producer/consumers/payload principles/tenant context/transaction timing/retry-duplicate implications, following whatever direct-in-process-vs-outbox mechanism the repository actually uses; background-processing guidance that overdue-state correctness must never depend solely on cron/background execution (read-time deterministic computation is required), with background jobs permitted only for reminders, notification-event generation, materialized reporting refresh, overdue event emission, or operational optimization, and no new Celery/Redis-style infrastructure introduced without strong justification; document generation (installment agreement, payment schedule, settlement quotation, customer installment statement) reusing existing document/receipt architecture, read-only with respect to contract/financial state, with receipts referencing Accounting's authoritative payment mechanism rather than inventing an Installments receipt ledger; failure/recovery guidance for Accounting failure, locked fiscal period, schedule-generation failure, stale version, concurrent collection, duplicate idempotency key, cross-tenant reference, entitlement change during request, tenant suspension, audit failure, invalid transition, and unavailable integration dependency, with no half-completed financial workflow permitted to remain; a concrete security plan covering authentication, RBAC, tenant isolation, branch scoping, IDOR, mass assignment, lifecycle authorization, maker-checker, Platform Admin boundary, support-access boundary, idempotency/replay, audit fail-closed, safe errors, sensitive logging, and financial command validation, with security-boundary tests explicitly identified; a layered testing strategy spanning unit (schedule calculations, rounding, month-end/leap-year behavior, eligibility, allocation policy, settlement calculation, lifecycle transitions, cure, due-state, aging mapping, entitlement access policy), repository (tenant isolation, unique contract invariant, filters, schedule persistence, allocation references, audit persistence, indexes/constraints), service (activation, approval/rejection, collection, reversal, settlement, rescheduling, cancellation, default, cure, write-off, disabled-entitlement servicing), Accounting integration (no duplicate Payment/AR/JournalEntry, period locks respected, reversal reconciliation, write-off integration, settlement reconciliation), security (tenant isolation, Platform Admin exclusion, SupportAccessGrant exclusion, missing-permission denial, maker-checker, no cross-tenant ID leakage), concurrency (no over-collection, no duplicate contract, deterministic concurrent approval/rejection, no double settlement, safe collection/write-off race), idempotency (single financial effect on repeated command), entitlement (enabled tenant, disabled-tenant origination denied, disabled-tenant existing collection/settlement allowed, normal RBAC still enforced, suspended tenant remains denied per Epic 9A), frontend (Jest/component/integration), and representative real-browser E2E flows (standard contract, partial collection, overdue, early settlement, disabled-entitlement servicing, tenant isolation, Platform Admin/support-access boundary); a full requirement-traceability matrix mapping FR groups, BR-INST-001–022, Scenarios A–L, and SC-001–007 to component/service, persistence entity, integration, API surface, and test layer with no orphan requirements; a recommended (not blindly mandatory) 15-phase implementation sequence — Domain Foundation, Configuration & Plans, Contract Persistence, Schedule Engine, Contract Lifecycle, Accounting Integration, Collections, Delinquency, Settlement, Advanced Lifecycle, Entitlement/Security Hardening, Reporting/Documents, Frontend, Concurrency/Idempotency Hardening, Integration/E2E/Regression — to be improved/reordered with explanation if actual repository dependencies require it; twelve required Architecture Decision Records (ADR-INST-01 through ADR-INST-12) covering Accounting-as-financial-source-of-truth, InstallmentContract-as-aggregate-root, the one-non-terminal-contract-per-obligation invariant, snapshotted/versioned schedule terms, derived-vs-persisted due-state, origination-vs-servicing entitlement policy, collection concurrency strategy, idempotency architecture, cross-module transaction strategy with Accounting, audit fail-closed architecture, REJECTED-as-event-not-state, and DEFAULTED→ACTIVE cure semantics; explicit future-AI-readiness guidance (no AI implementation, no vector databases/LLM dependencies/agent frameworks, clean future-consumable service/query boundaries for contract explanation, payment schedule, next due, overdue exposure, customer payment pattern, collection prioritization, and settlement information, with AI never becoming Accounting truth, authorization authority, or autonomous waive/write-off/settlement authority); an explicit prohibition on over-engineering (no Kafka/RabbitMQ/Celery/Redis/distributed sagas/workflow engines/event sourcing/CQRS/microservices/separate database unless the repository already demonstrably uses such infrastructure as an established pattern); a strict no-business-requirement-drift rule requiring any discovered spec/implementation conflict to be documented, explained, and resolved via the smallest possible change explicitly marked as requiring product-owner/specification approval rather than silently resolved in plan.md; a closing Open Technical Decisions section with Resolved Technical Decisions and, only if genuinely necessary, Blocking Technical Clarifications, explicitly stating "No blocking technical clarifications remain. Ready for /sp.tasks." if there are zero blocking issues; a pre-completion quality-gate self-review checklist (every spec requirement has an architectural destination, no duplicate Accounting truth, no duplicate Sales/Customer ownership, one-contract invariant is concurrency-safe, schedule arithmetic is deterministic, money precision matches Accounting, active schedule history cannot be silently destroyed, lifecycle transitions are explicit, REJECTED is not persisted, DEFAULTED cure is explicit, disabled entitlement permits servicing but blocks origination, suspended-tenant behavior remains distinct, RBAC is backend-enforced, cure has distinct authority, audit is fail-closed, tenant isolation exists at API/service/repository layers, Platform Admin cannot access tenant installment records, SupportAccessGrant does not expose installment business records, financial commands are idempotent, collection is concurrency-safe, Accounting period locks are respected, failure paths are atomic, no unnecessary infrastructure was introduced, testing covers Scenarios A–L, migration strategy does not mutate historical Sales/Accounting records, and future-AI-readiness does not weaken financial/security boundaries); and a required final planning report (25 specified items, ending with a READY FOR /sp.tasks or NOT READY FOR /sp.tasks — <exact blocker> status line) plus an explicit stop condition: do NOT run /sp.tasks, do NOT implement Epic 10, do NOT create migrations, do NOT modify application source — stop after repository inspection, creation/update of plan.md, any required planning artifacts/checklists/PHR, and the final planning report.]

This is a planning-only phase for Epic 10 (Installments), a new vertical domain to be added to the existing multi-tenant ERP modular monolith. The plan must be grounded in actual repository inspection of Epic 7 (Sales), Epic 8 (Accounting & Finance), Epic 9 (CRM), and Epic 9A (Platform Admin) implementations rather than assumptions.

(Followed by the standard `/sp.plan` command's own Outline/Phases/Key-rules instructions: run `setup-plan.sh --json`; load `spec.md` + constitution; fill Technical Context and Constitution Check; Phase 0 → `research.md` resolving all NEEDS CLARIFICATION; Phase 1 → `data-model.md`, `/contracts/`, `quickstart.md`, update agent context via `update-agent-context.sh claude`; re-evaluate Constitution Check; stop after Phase 2 planning; and a mandatory PHR-creation instruction to close out the exchange.)

## Response snapshot

Performed full mandatory repository inspection via 5 parallel background research agents (Accounting: Payment/PaymentAllocationLine/PaymentRefund/ARTransaction/CustomerLedger/JournalEntry/PostingEngine/FiscalPeriod/AgingCalculator/write-off/idempotency/concurrency/maker-checker/audit/module-structure/API/repository/events/documents; Sales: SalesInvoice/SalesOrder/Customer/document-numbering/branch-scoping/money-precision/module-structure/RBAC/return-reversal-rules/API; Platform Admin + CRM: Capability/Plan/PlanCapability/Subscription/EntitlementOverride/entitlement-resolution-precedence/ModuleEnablementProvider/SupportAccessGrant/tenant-suspension/platform-audit/CRM-module-flag/CRM-structure/CRM-audit/Customer-360; cross-cutting backend: RBAC model, company_id enforcement at every layer, response/error envelope, Alembic conventions, structured logging, domain-event mechanisms (found two incompatible ones), idempotency (found none reusable), optimistic/pessimistic concurrency, DB model base classes, testing architecture, and 11 Constitution sections; frontend: App Router structure, API-client/data-fetching conventions, detail-page patterns, permission-gated UI, entitlement-disabled UI, forms/validation, design-system components, testing conventions), plus a direct read of `spec.md` (674 lines) and the relevant Constitution sections (§5–6, §9–25, §31, §35, §37–39, §46–50).

Synthesized findings into `specs/010-installments/plan.md` (40 sections: the 39 required + an Architecture Decision Records section), covering: Technical Context; a Repository Findings table condensing all 5 research passes; a full Constitution Compliance table; an architecture-overview diagram; explicit domain-ownership boundary (Sales owns invoice/customer, Accounting owns GL/AR/payments, Installments owns contract/schedule/collection-orchestration); a 10-entity domain model (InstallmentConfiguration, InstallmentPlanTemplate, InstallmentContract as aggregate root, InstallmentScheduleVersion, InstallmentScheduleLine, InstallmentAllocationReference, InstallmentLateCharge, InstallmentAuditLog, InstallmentsFeatureFlag, InstallmentSequence, plus the new InstallmentIdempotencyKey primitive); conceptual table/constraint design including a PostgreSQL partial unique index for the one-non-terminal-contract-per-obligation invariant (mirroring an exact existing precedent — `Subscription.uq_subscriptions_company_active`); a money strategy resolving Accounting's `NUMERIC(20,6)` over Sales' `NUMERIC(15,2)` per spec Assumption A4, with deterministic residual-to-final-installment assignment; an explicit contract state machine with named service methods only (no generic `set_status`), REJECTED modeled as an audited event/transition rather than a persisted status, and distinct DEFAULTED→ACTIVE (cure) vs. DEFAULTED→COMPLETED (full payoff) paths; a pure, DB-independent schedule engine design; a detailed collection/allocation architecture (oldest-due-first policy, FOR-UPDATE-locked orchestration flow); an exhaustive Accounting Integration table (11 operations × caller/callee/transaction-owner/authoritative-data/Installments-metadata/failure-behavior/audit/event) built around Accounting's actual `stage_direct_posting()`/`finalize_and_publish()` two-phase API, with an explicit confirmation that `mark_defaulted()` never calls Accounting; Sales integration via read-only repository access plus event-bus subscription (`InvoiceCreditNoteIssued`/`InvoiceCancelled`) rather than any write path; a centralized `InstallmentAccessPolicy` (ORIGINATION/SERVICING/READ/ADMIN) checked per-service-method rather than at router-mount level — deliberately diverging from CRM's blunt `require_crm_enabled` router gate, since spec requires servicing continuity under disabled entitlement, documented as ADR-INST-06; a 16-permission RBAC catalogue including a new `installments.contract.cure` permission kept structurally distinct from `collection.create`; maker-checker applied identically to both approve and reject (explicitly avoiding a documented historical gap where sibling modules forgot to guard the "opposite" action); a fail-closed audit log following Accounting's richer shape; multi-tenant/branch isolation design (branch_id reserved but unenforced, since no platform-wide Branch entity exists yet); a mixed concurrency strategy (pessimistic FOR-UPDATE locks for money-mutating sequences, optimistic version-column for discrete approvals) with an explicit protection-mechanism mapping per named race condition; a new, deliberately narrow `InstallmentIdempotencyKey` primitive (no reusable idempotency infrastructure exists anywhere in the repository — closest analog was `RecurringJournalService`'s business-key pattern, judged insufficient for client-supplied replay keys); single-commit-per-workflow transaction boundaries for all 9 high-risk workflows; a full API surface (18 endpoint groups, command endpoints only, no generic PATCH); a frontend plan grounded in the actual (not idealized) frontend conventions found — flat routing, TanStack Query, stacked-section detail pages, CRM's exact entitlement-banner pattern; reporting/document architecture distinguishing Installments-contractual vs. Accounting-authoritative data sources; domain events published via the transactional outbox (`core/events/outbox.py`) rather than the non-durable in-process `EventBus` four sibling modules use — documented as ADR-INST-09, justified by Constitution §49's actual textual requirement, which only the outbox satisfies; a 12-migration sequence starting at `062` (confirmed current head: `061_platform_support_access.py`); a full layered testing strategy; a complete requirement-traceability matrix (by FR group, by all 22 BR-INST rules individually, and by all 12 Scenarios + 7 Success Criteria individually — zero orphans); a 15+1-phase implementation sequence (one phase inserted beyond the user's baseline — "5.5 Idempotency Primitive" — with explicit justification, since the baseline assumed a reusable component that inspection proved doesn't exist); and all 12 required ADRs with concrete rationale grounded in specific repository findings rather than generic justification.

Also produced Phase 0/1 artifacts: `research.md` (11 Decision/Rationale/Alternatives-formatted technical resolutions), `data-model.md` (full entity/field/relationship/validation/state-machine detail for all 13 entities), `contracts/installments-api.yaml` (OpenAPI 3.0 skeleton, 30 paths, permission/operation-class/idempotency annotations per endpoint, schema bodies deliberately left as placeholders since implementation-detail schemas belong to `/sp.tasks`), and `quickstart.md` (an end-to-end Scenario-A walkthrough plus tenant-isolation and entitlement-disabled-servicing checks). Attempted `update-agent-context.sh claude`, found it destructively stripped `CLAUDE.md`'s existing Active Technologies/Recent Changes entries without adding replacements (its plain-text `**Language/Version**:` parser doesn't match this plan's markdown-table Technical Context format) — reverted that script's edit via `git checkout` and updated `CLAUDE.md` manually instead, preserving all prior epics' entries and adding a 010-installments summary paragraph plus an Active Technologies line explicitly noting no new technology was introduced.

No blocking technical clarifications remain. Zero repository/spec conflicts were discovered requiring product-owner escalation (the two genuinely new pieces of infrastructure — the idempotency primitive and JSON-only document generation — are implementation decisions within this plan's authority, not business-requirement changes). Final status: **READY FOR /sp.tasks**.

## Outcome

- ✅ Impact: Epic 10 (Installments) now has a complete, implementation-ready technical plan grounded in actual repository patterns rather than assumptions — `/sp.tasks` can decompose it into executable tasks without further architectural research.
- 🧪 Tests: none created (planning-only phase, per explicit stop condition) — full layered testing strategy specified in plan.md §31 for the implementation phase to execute.
- 📁 Files: specs/010-installments/{plan.md, research.md, data-model.md, contracts/installments-api.yaml, quickstart.md} created; CLAUDE.md updated (Recent Changes + Active Technologies); this PHR.
- 🔁 Next prompts: `/sp.tasks` to decompose plan.md into T001... executable tasks; optionally `/sp.adr` to formalize ADR-INST-06 (entitlement policy granularity) and ADR-INST-09 (outbox over in-process bus) as standalone `history/adr/` records, since both are genuine deviations from sibling-module precedent worth a durable, independently-linkable record.
- 🧠 Reflection: The single highest-leverage finding was that no reusable idempotency-key infrastructure and no constitutionally-compliant event mechanism exist anywhere in the repository despite five business modules already existing — both required explicit, justified plan-level decisions (new module-local primitive; outbox over in-process bus) rather than simple reuse. Parallelizing repository inspection across 5 background agents kept the main context window free for direct Constitution reading and final synthesis.

## Evaluation notes (flywheel)

- Failure modes observed: `update-agent-context.sh claude` is fragile against a Technical Context section formatted as a markdown table rather than the template's expected `**Language/Version**:` bullet style — it silently deleted existing content instead of failing loudly. Caught via `git diff` before it could be mistaken for a successful update; reverted and applied the intended update by hand.
- Graders run and results (PASS/FAIL): N/A — planning-only phase, no automated grading harness invoked.
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): If this project runs another `/sp.plan` with a similarly large Technical Context, consider pre-formatting a `**Language/Version**:`-style bullet summary line specifically for `update-agent-context.sh`'s parser, immediately above the fuller table, so the script can succeed without a manual fallback.
