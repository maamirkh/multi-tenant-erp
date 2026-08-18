---
id: 0001
title: Epic 9 CRM specification
stage: spec
date: 2026-08-15
surface: agent
model: claude-sonnet-5
feature: 009-crm
branch: 009-crm
user: Muhammad Amir
command: /sp.specify
labels: ["crm", "spec", "epic-9", "spec-driven-development"]
links:
  spec: specs/009-crm/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/009-crm/spec.md
  - specs/009-crm/checklists/requirements.md
tests:
  - No tests run (specification-only phase; no code, migrations, models, routers, or frontend pages created or modified)
---

## Prompt

You are working on DevSphere ERP — a production-oriented, multi-tenant SaaS ERP system.

EPICS 1–8 ARE COMPLETE AND MUST BE TREATED AS THE STABLE FOUNDATION.

Completed foundation: Epic 1 — Foundation, Epic 2 — Authentication, Epic 3 — Companies /
Multi-Tenancy, Epic 4 — Users & Roles / RBAC, Epic 5 — Inventory, Epic 6 — Purchase,
Epic 7 — Sales, Epic 8 — Accounting & Finance.

Before starting Epic 9, a comprehensive pre-Epic-9 hardening audit was completed. Important
verified fixes from that audit: missing transaction commits across Inventory/Purchase/Sales
write services fixed; tenant-isolation gaps in Sales invoice lookups fixed; Accounting RBAC
asymmetries fixed; Purchase/Sales ORM-vs-PostgreSQL nullability drift fixed; zero-line invoice
crash fixed; Sales quotation PostgreSQL VARCHAR length defect fixed; regression tests added;
real PostgreSQL verification performed; Sales/Purchase/Accounting/Inventory regression suites
green apart from one known unrelated timing/flaky test; system explicitly READY_FOR_EPIC_9.

DO NOT restart, redesign, or replace the architecture of Epics 1–8.

EPIC 9 — CRM. Task in THIS PHASE is ONLY to create/update specs/009-crm/spec.md. Do NOT
implement code, migrations, models, routers, or frontend pages. Specification-first SDD.

[Full 32-section brief covered, in order: (1) study the existing system exhaustively before
writing anything — constitution, specs 001-008 (especially Sales and Accounting), data models,
contracts/events.md, backend modules, frontend structure, RBAC, multi-tenancy, audit-log
architecture, API/repository/service/test/migration/soft-delete/event-bus conventions;
(2) CRM objective — a professional B2B/B2C CRM foundation (leads, prospects, contacts,
qualification, conversion, opportunities/deals, pipeline, activities/tasks/calls/meetings/
notes/follow-ups, interaction history, ownership, source tracking, campaign-attribution
readiness, probability/stages/close-dates/value, CRM-to-Sales/Customer/Accounting
integration) that must NOT duplicate existing Customer, Sales Order, Invoice, Payment, or
Accounting entities; (3) explicit domain-boundary rules — what CRM owns vs must not
duplicate; (4) multi-tenancy — company_id/created_by/audit on every CRM entity, tenant
isolation at repository/service/API layers, not frontend-only; (5) RBAC — reuse Epic 4's
engine, a justified crm.* permission matrix across owner/admin/manager/salesperson/
accountant/cashier/viewer with separation of duties, not blanket grants; (6) lead
management — full lifecycle, identity/contact/source/status/score/owner fields, validation,
invalid-transition prevention; (7) lead conversion — existing-vs-new customer matching, no
duplicates, idempotent and tenant-safe, transaction boundaries, audit trail, rollback
behavior; (8) opportunities — value/currency/probability/weighted-value/expected-close-
date/lost-reason/won-lost timestamps, OPEN→WON|LOST lifecycle with in-OPEN stage
progression; (9) sales pipeline — configurable Pipeline/PipelineStage, no workflow engine;
(10) activities — unified CALL/EMAIL/MEETING/TASK/NOTE/FOLLOW_UP entity, explicit nullable
FKs not polymorphic design; (11) Customer 360 — CRM+Sales+Accounting read-model, no
duplicated financial values; (12) Sales integration — Lead→Opportunity→Quotation→SO→
Delivery→Invoice→Payment, events, no forced automatic transitions; (13) Accounting
integration — read-only AR/balance via existing services, no duplicate ledgers; (14)
reporting/KPIs — lead/pipeline/conversion/win-rate/cycle-time/activity metrics, no full BI
system; (15) search/filtering — bounded pagination; (16) audit trail — reuse existing
conventions, no second audit system; (17) soft-delete/retention conventions; (18)
concurrency/idempotency — DB constraints/transactions, no unnecessary distributed locking;
(19) database design — normalized Postgres tables with tenant-scoped uniqueness, only
justified entities; (20) API design derived from the actual domain model, not a blind
endpoint checklist, each with auth/RBAC/tenant-isolation/schema/validation/error/
transaction specification; (21) frontend — existing Next.js App Router conventions, no
redesign; (22) performance — pagination/indexes, no premature Elasticsearch/Redis/
materialized-views/microservices; (23) security — explicit 401/403/cross-tenant/invalid-
transition/duplicate-conversion/unauthorized-assignment test cases, server-side enforced;
(24) test strategy — unit/integration/API/E2E, not SQLite-only where Postgres-specific
behavior matters; (25) event contracts — existing contracts/events.md envelope, no
speculative AI fields; (26) AI readiness without AI implementation; (27) explicit
out-of-scope list (WhatsApp/SMS/email infra/telephony/AI agent/marketing automation/BI
platform/external CRM sync/microservices/K8s/event-sourcing rewrite); (28) architecture
rules — no microservices/second RBAC/second audit/second event bus, continue the modular
monolith; (29) required 27-part spec.md content outline; (30) do-not-invent mandate — reuse
existing entities/services, document conflicts rather than silently modifying Epic 1-8;
(31) final spec validation checklist (16 consistency checks); (32) deliverable — ONLY
specs/009-crm/spec.md, plus a concise final report covering inspection scope, domain
boundaries, entities, reused entities, API surface, RBAC permissions, events, architectural
decisions, out-of-scope items, risks/assumptions, acceptance criteria, and confirmation no
application code was modified. STOP after spec.md — no plan.md, no tasks.md, no
implementation, no Epic 10.]

## Response snapshot

Created branch `009-crm` (via `.specify/scripts/bash/create-new-feature.sh --number 9
--short-name crm`) and wrote `specs/009-crm/spec.md` (60 sections, ~1,400 lines), modeled
directly on the established project convention observed in `specs/007-sales-management/
spec.md` and `specs/008-accounting-finance/spec.md` (both "official business specification"
documents with 60-61 numbered sections), rather than the generic minimal spec-template.md —
justified because the input brief's own 27-part outline maps almost one-to-one onto that
existing convention and explicitly asked for an implementation-ready document matching
existing project conventions.

Research performed before writing (via 2 parallel Explore agents plus direct reading):
constitution.md (multi-tenancy §9, feature toggles §11 — confirms `feature.crm.enabled` is
named explicitly as an example toggle-controlled module, audit trail §35, shared kernel §48,
event-driven principles §49); Sales spec (domain boundaries, permission matrix, domain
events, acceptance criteria, epic completion criteria sections read in full for style);
Accounting spec (security requirements, cross-module dependencies/contracts, AI readiness,
multi-tenant SaaS sections read for pattern); Users & Roles spec (permission architecture,
actual system role slugs); actual `Customer`/`SalesOrder`/`SalesQuotation`/`Invoice` models
(confirmed no owner/source field on Customer — a genuine gap, not a duplication risk;
confirmed the `sales_rep_id: PG_UUID(as_uuid=False), nullable=False` convention for a
cross-module "assigned user" FK; confirmed `AccountsReceivableService.get_customer_ledger()`/
`.get_customer_aging()`/`.get_customer_statement()` as the exact reuse points for Customer
360); audit architecture (confirmed no platform-wide audit table exists — `CompanyAuditLog`
and `AccountingAuditLog` are both module-local, so CRM correctly defines its own per-module
audit table following the same shape, not a second cross-cutting system); API/RBAC
conventions (confirmed `StandardResponse[T]`/`PaginatedResponse[T]`/`PaginationParams` shared
schemas; confirmed Sales/Purchase currently enforce authentication only, no fine-grained
RBAC, while Accounting does real permission checks via `user_has_accounting_permission` — an
explicit, documented architectural decision was made for CRM to follow Accounting's stronger
pattern, not Sales/Purchase's weaker one); migration conventions (confirmed `TenantBaseModel`'s
exact server-default columns, and cited migration 050 as the clean pattern to follow, with
051-054 cited as the cautionary precedent for why every server default/constraint must
match the ORM model exactly); event bus conventions (confirmed each module owns its own
`InProcessEventBus` instance via a local `get_event_bus()` accessor, no shared singleton).

Domain design decisions made and justified in-spec: 6 new tables only (`crm_leads`,
`crm_lead_sources`, `crm_pipelines`, `crm_pipeline_stages`, `crm_opportunities`,
`crm_activities`) — no Contact entity (none exists generically in the codebase; Customer's
existing nested contacts are reused as-is), no duplicate Customer/Quotation/Invoice/Payment/
GL entities anywhere. Lead lifecycle kept as 6 distinct states (not merging UNQUALIFIED and
LOST) with reporting-driven justification. Opportunity has no line-item child (avoids
duplicating Quotation's own line model). Lead conversion designed with an explicit single-
transaction/single-commit boundary (directly citing the pre-Epic-9 hardening audit's own
missing-commit finding as the reason this must not be repeated), idempotent-by-status design,
and optimistic-locking (`version` column) race-condition handling — no distributed locking.
19 `crm.*` permission codes with a full 8-role × 19-permission access matrix reflecting
separation of duties (Cashier/Store Keeper get zero CRM access; Accountant is view-only;
Salesperson cannot delete/reassign/close). 11 domain events, same envelope as
`specs/008-accounting-finance/contracts/events.md`. §53 documents 6 explicit architectural
decisions/risks (real-RBAC-over-auth-only, no per-record ownership filtering deferred to a
future epic, no Opportunity line items, always-live Customer 360 financial data, no shared
audit table, exact-match-only duplicate detection) with reasoning for each.

Created `specs/009-crm/checklists/requirements.md` per the sp.specify workflow's mandatory
quality-gate step; all items pass on first validation (no [NEEDS CLARIFICATION] markers were
needed — three judgment calls that could have warranted one were instead resolved with
documented informed defaults, per the input brief's own preference for defaults over
clarification markers where a reasonable default exists).

One text-corruption artifact (a stray CJK character injected mid-word during generation) was
caught during a full non-ASCII character scan of the finished file and corrected before this
PHR was written.

Confirmed via `git status --porcelain`: only `specs/009-crm/` was created. Zero application
code, migrations, models, routers, or frontend files were touched, satisfying the input
brief's explicit "STOP after spec.md is complete" instruction.

## Outcome

- ✅ Impact: A 60-section, implementation-ready CRM specification exists at
  `specs/009-crm/spec.md`, grounded in the actual codebase (every integration/reuse claim
  cites a real, verified service/model/table name) rather than generic CRM conventions.
  Zero Epic 1-8 code was modified. The spec is ready for `/sp.clarify` (though zero
  clarification markers remain) or `/sp.plan`.
- 🧪 Tests: None run — specification-only phase, no code produced to test.
- 📁 Files: `specs/009-crm/spec.md` (new), `specs/009-crm/checklists/requirements.md` (new).
- 🔁 Next prompts: `/sp.plan` for Epic 9 (not started, per explicit instruction to stop here).
- 🧠 Reflection: The two parallel research agents (Customer/Sales model facts;
  audit/API/RBAC/migration/event-bus conventions) were essential to avoid inventing
  plausible-sounding but false architectural claims — several assumed conventions (a generic
  audit table, page/page_size-only pagination, uniform RBAC enforcement across modules)
  turned out to be wrong or inconsistent when actually verified against the code, and the
  spec was written to reflect the verified reality (including explicitly documenting where
  CRM deliberately diverges from an inconsistent existing pattern, e.g. RBAC strictness).

## Evaluation notes (flywheel)

- Failure modes observed: one generation-time text-corruption artifact (stray non-ASCII
  character) was introduced and caught by a full-file non-ASCII scan before finalizing —
  worth doing this scan as a standard last step on any long generated document.
- Graders run and results (PASS/FAIL): spec quality checklist (`checklists/requirements.md`)
  — PASS, all items, first iteration. Manual 16-point final-validation review (per the input
  brief's own §31) — PASS, all 16 checks (entity ownership, no duplication, tenant isolation,
  RBAC coverage, audit coverage, tenant-safe cross-module FKs, conversion transaction safety,
  pipeline consistency, no accounting/sales duplication, API/event convention match, AI
  readiness without implementation, no speculative infrastructure, realistic single-epic
  scope, testable acceptance criteria).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): none identified — proceed to `/sp.plan` when the
  user is ready; no rework flagged.
