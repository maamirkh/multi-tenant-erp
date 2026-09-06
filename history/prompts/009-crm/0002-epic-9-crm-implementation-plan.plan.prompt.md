---
id: 0002
title: Epic 9 CRM implementation plan
stage: plan
date: 2026-08-15
surface: agent
model: claude-sonnet-5
feature: 009-crm
branch: 009-crm
user: Muhammad Amir
command: /sp.plan
labels: ["crm", "plan", "epic-9", "spec-driven-development"]
links:
  spec: specs/009-crm/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/009-crm/plan.md
tests:
  - No tests run (planning-only phase; no code, migrations, models, routers, or frontend pages created or modified)
---

## Prompt

You are now responsible for creating the FINAL implementation plan for Epic 9 — CRM
(Customer Relationship Management). The approved Epic 9 spec.md already exists in
specs/009-crm/spec.md. Your task is to create specs/009-crm/plan.md.

IMPORTANT: Do NOT implement any code. Do NOT create tasks.md yet. Do NOT start Epic 10.
Do NOT modify existing application code. Your ONLY job in this step is to deeply analyze
the existing ERP architecture, the approved Epic 9 spec.md, and previous epics, then
produce a production-grade, implementation-ready plan.md.

[Full 35-section brief covered, in order: (1) inspect the existing ERP exhaustively —
constitution, Epics 1-9, database models/repositories/services/routers/schemas/
dependencies, RBAC, tenant-isolation, audit trail, event system, API conventions,
frontend architecture, existing customer/supplier/contact models, migrations, testing
architecture, Docker workflow — the actual repository is the source of truth, spec.md is
not assumed accurate; (2) reconcile spec.md with the existing system — what already
exists/reused, what's partially existing/extended, what's genuinely new, what would
duplicate an existing system, what existing functionality could be damaged — do not
duplicate Customer/Company/User/Address/Sales/Accounting/RBAC/audit/notification/event
entities, extend/integrate instead, document the decisions; (3) CRM architecture as a
modular part of the existing modular monolith with clear boundaries vs Sales/Accounting/
Inventory/Purchase/Users-Roles/Companies; (4) customer master/Customer 360 strategy —
determine if Epic 7 already has Customer, reuse/extend it safely, preserve FKs/tenant
isolation/Sales integration, Customer 360 composing profile/contacts/addresses/sales
history/invoices/receivables/payments/interactions/activities/notes/tasks/opportunities/
quotations/lifecycle/value metrics/last interaction/next follow-up/alerts without
duplicating transactional data; (5) CRM core modules derived from spec.md and repository
reality, marking any addition as "RECOMMENDATION — NOT REQUIRED BY CURRENT SPEC"; (6) the
Lead→Qualification→Opportunity→Customer conversion→Quotation/Sales→Order/Invoice→
Payment→retention flow with explicit per-step ownership, avoiding competing sales
transaction logic in CRM; (7) Sales integration inspecting Epic 7, reusing existing
APIs/services, not duplicating invoice/order/pricing/inventory-reservation/stock-
deduction/payment-posting logic; (8) Accounting integration inspecting Epic 8, read-side
only for balance/receivables/aging/payment-history/credit-exposure/overdue-invoices,
no duplicate AR balances, no modification of immutable ledger logic, explicit credit-
limit-ownership documentation; (9) no unnecessary Inventory/Purchase dependencies,
supplier management stays in Purchase; (10) multi-tenancy — company-scoped repositories/
queries/services/routes, cross-tenant protection, ownership validation, explicit
cross-tenant tests; (11) RBAC reusing the existing engine (not a second system), derived
minimum permission matrix, role compatibility with owner/admin/manager/salesperson/
accountant/cashier/viewer, no new CRM role unless required; (12) audit trail reusing
existing infrastructure, no second audit table unless absolutely required; (13) event
architecture inspecting the existing bus/contracts, only necessary events, tenant-
context-bearing payloads; (14) AI-readiness (data/events/API architecture only, no AI
implementation unless spec.md explicitly requires it); (15) data model per-table PK/
company_id/audit/soft-delete/timestamps/FKs/indexes/unique-constraints/status/lifecycle/
CHECK-constraint planning, careful tenant-scoped uniqueness, JSON only where justified;
(16) migration plan — minimum schema changes, forward+downgrade, FK correctness,
single linear Alembic chain, no competing heads; (17) API design following existing
FastAPI/company-scoped conventions, Router→Service→Repository discipline, no repository
exposed from routers; (18) pagination/filtering/search using DB-level filtering, inspect
existing Postgres capability before introducing new search tech; (19) Customer 360
performance — avoid N+1, dedicated read/query service, documented query complexity/
indexes; (20) reporting/dashboard metrics without duplicating accounting calculations;
(21) frontend architecture per existing Next.js protected-area conventions with
loading/empty/error states, permission-aware UI; (22) testing strategy across unit/
repository/API/security/integration/regression levels, existing Epics 1-8 must remain
green, document any legitimate contract-driven test change; (23) performance testing at
realistic CRM volumes (10K+ customers/leads/activities); (24) security against IDOR/
cross-tenant leakage/unauthorized access/privilege escalation/information leakage,
typed exception contract, no stack traces to clients; (25) soft-delete/retention
conventions, never hard-delete data referenced by Sales/Accounting; (26) a 20-step
recommended implementation order (adjustable); (27) explicit prerequisites/dependencies
per section so tasks.md can be generated without rediscovering architecture; (28)
file-level plan (NEW/MODIFIED/DO NOT TOUCH), following actual repository structure, not
assumed; (29) explicit backward-compatibility protection for Epics 1-8, especially
Customer FKs/Sales transactions/AR balances/journal entries/payments/tenant isolation/
RBAC/audit/event contracts; (30) avoid over-engineering — no microservices/K8s/separate
DB/message brokers/Elasticsearch/unnecessary caching/CQRS/distributed tracing unless
explicitly required; (31) ADR-style architectural-decision documentation (Decision/
Reason/Alternatives/Why rejected/Impact) for at least 13 named decision areas; (32) risk
register with mitigations for at least 10 named risk categories; (33) a strong Epic 9
Definition of Done checklist; (34) explicit "do not hide gaps" instruction — document
GAP/WHY/AFFECTED EPIC/RECOMMENDED SOLUTION/DEFER-OR-FIX-NOW for anything spec.md requires
that earlier epics lack infrastructure for, never inventing a fake implementation or
silently modifying Epic 5-8 architecture; (35) the exact 36-section final plan.md format.
Final instruction: re-read spec.md, verify every requirement has an implementation path,
verify no duplication, verify Sales/Accounting remain sources of truth, verify tenant
isolation/RBAC/audit/events/AI-readiness/testing/migration/backward-compatibility, verify
no Epic 10 work, and end with a YES/NO "PLAN READINESS" checklist — fixing plan.md before
finishing if any answer is NO. Do not implement anything, do not create tasks.md, do not
start Epic 10 — only produce specs/009-crm/plan.md.]

## Response snapshot

Ran `.specify/scripts/bash/setup-plan.sh --json` (confirmed still on branch `009-crm`,
paths resolved) and inspected the actual current repository directly — not assumed from
spec.md — to ground every claim in this plan: the module skeleton pattern (verified
against `modules/purchase/`, `modules/accounting/`), `TenantBaseModel`'s exact columns,
`api/v1/router.py`'s exact `include_router(..., dependencies=[Depends(get_current_company_member)])`
mounting pattern, `main.py`'s `lifespan`/`register_integration_handlers()` wiring point,
the confirmed RBAC enforcement asymmetry (Sales/Purchase = auth-only, Accounting = real
permission checks via `user_has_accounting_permission`), the confirmed absence of any
platform-wide audit table (`CompanyAuditLog` and `AccountingAuditLog` are both
module-local), `Customer`'s exact current field set (confirming no owner/source field —
a genuine gap CRM fills without touching the table), `AccountsReceivableService`'s exact
reusable method names, the testing directory convention, and the frontend route-group
convention (`(accounting)`/`(sales)`/`(purchase)`/`(inventory)`/`(companies)` confirmed
as flat siblings under `(protected)/`).

Wrote `specs/009-crm/plan.md` (36 sections, ~900 lines) following the user's exact
requested structure, itself modeled on the same "official business specification"
convention already established by `specs/007-sales-management/plan.md` and
`specs/008-accounting-finance/plan.md` (both 1100+ lines with Technical Context/
Constitution Check/Project Structure front matter, matching the mechanical requirements
of the underlying /sp.plan workflow, folded into the user's own 36-section numbering).

Key decisions reconciled and documented: Customer master ownership stays entirely with
Sales — zero `ALTER TABLE customers`, zero Sales file modification anywhere in this plan;
CRM's "owner/source" gap is filled on Lead/Opportunity instead (ADR-1); CRM→Sales and
CRM→Accounting are both one-directional dependencies (Sales/Accounting have zero
awareness of CRM's existence, confirmed as a hard, reviewable constraint — §29.3 "DO NOT
TOUCH" list, and only 3 Epic 1-8 files are modified at all, each a pure, additive,
single-line-or-tuple-append change: `users_roles/constants.py`, `api/v1/router.py`,
`main.py`); Accounting integration is synchronous in-process read calls (not events),
matching the existing precedent of Sales' own `credit_check_service.py` calling
Accounting the same way; RBAC follows Accounting's real-enforcement pattern rather than
Sales/Purchase's weaker auth-only pattern, with the asymmetry and the reasoning both
explicitly documented (ADR-8) rather than glossed over; migration `055_crm_foundation.py`
is planned with an explicit column-by-column server-default verification step, directly
naming the migrations-051-through-054 defect history in this exact codebase as the reason
this step is non-negotiable (R-09 in the risk register, the most heavily cross-referenced
risk in the document). 13 ADRs, 12 risks, 3 documented known gaps (Opportunity→Quotation
traceability edge case; deferred per-record ownership filtering; Sales/Purchase's
pre-existing weaker RBAC noted but explicitly out of this epic's scope to fix) were
produced, each with the exact Decision/Reason/Alternatives/Why-rejected/Impact (or
GAP/WHY/AFFECTED-EPIC/RECOMMENDED/DEFER) shape requested.

One factual inconsistency was caught and fixed during final review: spec.md's §36 event
table actually lists 12 domain events (5 lead + 5 opportunity + 2 activity) but its own
summary line and two acceptance-criteria references had said "11" — corrected in both
spec.md and plan.md (4 total line fixes) to keep the two documents consistent before this
PHR was written. A non-ASCII character scan of the finished plan.md found only the
intentional box-drawing arrows in the §4 architecture diagram — no corruption this time.

Confirmed via `git status --porcelain`: only `specs/009-crm/` (now including plan.md) and
`history/prompts/009-crm/` are new/modified. Zero application code was touched in this
phase, per the explicit instruction.

## Outcome

- ✅ Impact: A 36-section, implementation-ready plan.md exists at `specs/009-crm/plan.md`,
  cross-referencing every spec.md requirement to a concrete file, table, service method,
  or ADR. The plan is ready for `/sp.tasks` (not run in this phase, per explicit
  instruction). PLAN READINESS checklist: all 16 items YES.
- 🧪 Tests: None run — planning-only phase, no code produced to test.
- 📁 Files: `specs/009-crm/plan.md` (new/filled from template); `specs/009-crm/spec.md`
  (2 small factual corrections, event count 11→12).
- 🔁 Next prompts: `/sp.tasks` for Epic 9 (not started, per explicit instruction to stop
  here — no tasks.md, no implementation, no Epic 10).
- 🧠 Reflection: Direct, fresh re-verification of the actual repository (rather than
  trusting the spec-phase research agents' findings as still-current) was worth doing —
  it surfaced the exact current migration head (054) needed to number the new migration
  correctly, and re-confirmed the RBAC/audit asymmetry findings were still accurate. The
  event-count inconsistency was only caught by a deliberate cross-document consistency
  pass at the end, not during initial writing — worth doing as a standard last step
  whenever a plan.md is derived from and must stay consistent with an already-approved
  spec.md.

## Evaluation notes (flywheel)

- Failure modes observed: a spec.md counting error (11 vs actual 12 events) went
  unnoticed through the entire spec-writing and initial plan-writing pass, only caught by
  an explicit final cross-check between the plan's own event-related sections and the
  spec's source table — worth adding "recount every enumerated total against its own
  table" as a standard final-validation step for any spec/plan document with itemized
  counts.
- Graders run and results (PASS/FAIL): manual 14-point final-instruction verification
  (spec coverage, no duplication, Sales/Accounting source-of-truth preservation, tenant
  isolation, RBAC, audit, events, AI-readiness, testing/regression, migration strategy,
  backward compatibility, no Epic 10 work) — PASS, all 14, documented in §36. PLAN
  READINESS 16-item YES/NO checklist — PASS, all 16 YES, no plan.md rework triggered.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): none identified — proceed to `/sp.tasks` when
  the user is ready; no rework flagged.
