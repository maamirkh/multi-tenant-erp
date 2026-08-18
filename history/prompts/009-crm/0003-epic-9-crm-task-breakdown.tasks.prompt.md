---
id: 0003
title: Epic 9 CRM task breakdown
stage: tasks
date: 2026-08-15
surface: agent
model: claude-sonnet-5
feature: 009-crm
branch: 009-crm
user: Muhammad Amir
command: /sp.tasks
labels: ["crm", "tasks", "epic-9", "spec-driven-development"]
links:
  spec: specs/009-crm/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/009-crm/tasks.md
tests:
  - No tests run (task-breakdown-only phase; no code, migrations, models, routers, or frontend pages created or modified)
---

## Prompt

You are the senior implementation architect for DevSphere ERP. We are now starting Epic
9 — CRM. Generate ONLY the implementation task breakdown in specs/009-crm/tasks.md.

Do NOT implement code. Do NOT modify source code. Do NOT modify spec.md. Do NOT modify
plan.md. Do NOT start Epic 10 or any future work.

Authoritative sources: (1) specs/009-crm/spec.md — SSOT for WHAT; (2) specs/009-crm/plan.md
— SSOT for HOW; (3) the DevSphere ERP Constitution/project architecture rules — authoritative
for architecture/security/multi-tenancy/testing/code-quality/commits/phase-gates; (4) the
existing Epics 1–8 codebase — must be inspected so tasks reference REAL existing models/
services/repositories/permissions/event-bus/pagination/audit/feature-flag/frontend/testing
conventions, not assumed ones.

[Full brief covered, in order: primary objective — complete/sequential/dependency-aware/
independently-testable/traceable-to-spec/traceable-to-plan/codebase-aligned/multi-tenant-safe/
Claude-Code-implementable/phase-by-phase/regression-strict task breakdown, not inventing
architecture merely because it's common in CRM systems; the full 32-item Epic 9 scope list
(module foundation through epic closure documentation), with the existing Sales Customer
remaining the sole master and zero duplication of Customer/Sales Order/Invoice/Payment/
Accounting journal/AR-AP ledger; explicit instruction to inspect the real codebase's backend
structure/DB conventions/repository-service-DI patterns/auth/tenant-resolution/RBAC engine/
audit/event-bus/feature-flags/pagination/API conventions/frontend route groups/API clients/
UI components/test-and-DB fixtures/migration numbering/Docker setup/existing Customer model/
AR-AP services/Sales integration points before finalizing tasks, and to never silently invent
a solution when plan/spec conflicts with reality — instead identify/preserve-SSOT/create-an-
explicit-resolution-task/document; 14 CRITICAL ARCHITECTURAL RULES the tasks must explicitly
enforce (Customer Master ownership, multi-tenancy at every layer with never-trust-client-
company_id, explicit commits on every write service, all 19 RBAC permissions with denied+
authorized-role test pairs reusing the Epic 4 engine, feature.crm.enabled gating with
enabled/disabled tests, audit coverage for 8 named actions, all CRM domain events via the
existing event-bus with no second infrastructure, state-machine rejection of invalid
transitions including 5 named examples, lead-conversion's 11 explicitly-named atomicity/
idempotency/concurrency/rollback concerns, Decimal/Numeric(15,2) monetary values, existing
PaginationParams/PaginatedResponse[T] with max page_size 100, ILIKE-only search with no
premature Elasticsearch/vector-search, a 6-bounded-query N+1-free Customer 360 with query-
count testing, and 4 named performance-benchmark requirements not satisfiable by unit tests
alone); the required 10-phase task structure (Foundation&Scaffolding → Data Model&Migration →
Lead Management → Lead Conversion&Customer Integration → Pipeline&Opportunity → Activities →
Customer 360&Cross-Module → RBAC/Audit/Events&Feature Flag → API/Frontend/Dashboard&Reporting
→ Performance/Security/Regression&Epic Closure), adjustable in detail but not in scope; the
exact required task format (checkbox+ID+[P]?+[Story/FR]?+title, then Purpose/Files-areas/
Implementation/Dependencies/Acceptance/Tests sub-fields), explicitly forbidding vague tasks
like "Implement CRM"/"Add lead functionality"/"Add tests"; mandatory traceability to
US/FR/NFR/BR/INV/AC/EC tags plus a closing Spec-Requirement→Task-IDs→Test-IDs matrix ensuring
zero FR/AC is left uncovered; explicit acyclic-dependency rules with a worked example chain;
the requirement that testing is NOT one final task — every phase carries its own unit/
integration/API/security/RBAC-matrix/state-machine/concurrency/event/audit tests, with the
exact status-code matrix (200/201/400/409/401/403/404/422/feature-flag-disabled) required per
endpoint; explicit cross-module test requirements (CRM→Sales Customer, CRM→Sales Opportunity/
Quotation boundary, CRM→Accounting AR, CRM→Accounting financial summary, Customer 360→both)
with an explicit ban on modifying Sales/Accounting merely to ease CRM; database-task
requirements (every table's PK/FK/company_id/indexes/unique/CHECK/state-constraints/
timestamps/soft-delete/audit-fields/Postgres-specifics, migration up/down/fresh/against-
existing-DB, zero unintended Epic 1–8 table modification, verified by final diff); the
exhaustive frontend task list (12 named screens) with 7 required per-screen states (loading/
empty/error/permission-denied/feature-disabled/pagination/validation), reusing existing
components/route-groups, no new design system; the exhaustive reporting/KPI task list (10
pipeline metrics, 5 lead metrics, 4 activity metrics, 7 dashboard KPIs) with a ban on
duplicating accounting calculations; AI-readiness scoped to data/events/contracts only, zero
AI implementation of any kind; a 19-item explicit "MUST NOT become tasks" out-of-scope list
(campaign/territory/quota/commission/email/telephony/SMS-WhatsApp/Salesforce/HubSpot/AI-
scoring-forecasting-churn/external-sync/fuzzy-matching/per-record-ownership-filtering/multi-
currency-normalization/new-BI/Elasticsearch-vector-search/mobile-app); a required "Phase
Gate" checklist ending every phase (tasks complete/tests pass/no open P1-P2/tenant-isolation
pass/RBAC pass/lint-type pass/migration-valid/diff-reviewed/no-unrelated-Epic-1-8-changes)
that blocks automatic progression to the next phase on failure; an explicit two-tier final-
verification strategy (phase-level = phase tests + directly-affected cross-module + security/
RBAC + code quality; epic-level-only = complete CRM suite + relevant Epics 5-8 regression +
complete full-repository regression + real Docker/Postgres live verification) explicitly
NOT requiring the expensive full suite after every phase, based on the project's recent
testing experience; a 20-item mandatory Epic 9 closure verification list (DB/migration,
real-Postgres, real-HTTP-E2E, tenant-isolation, full-19-permission-RBAC, audit-trail,
domain-event, feature-flag, lead-conversion-E2E, opportunity-lifecycle-E2E, activity-
lifecycle-E2E, Customer-360-E2E-with-real-data, reports/KPIs, performance-benchmarks,
Docker/runtime-health, full-regression-Epics-1-9, code-quality, final-git-diff/architecture-
audit, no-unintended-Epic-1-8-changes, PHR/documentation/task-completion) — explicitly never
declaring the epic complete on unit tests alone; an 8-item explicit "Known Gaps"/deferred-
scope list that must NOT be accidentally implemented, to survive future context loss; a
6-step defect-handling process (never hide/classify/fix-if-Epic-9-own/document-if-pre-
existing/never-force-test-passes/never-weaken-security); an explicit "do not artificially
target a task count" instruction, favoring atomic tasks for high-risk work and grouped tasks
for low-risk repetitive work, sized purely by actual dependency/coverage need; a 17-item
required trailing-sections list for tasks.md (Task Summary, Dependency Graph, Requirement
Traceability Matrix, Test Traceability Matrix, Database/Migration/API/Frontend/Security-RBAC/
Tenant-Isolation/Audit-Event/Performance/Cross-Module-Integration Checklists, Known Deferred
Scope, Phase Gate Checklist, Epic 9 DoD, Epic 9 Final Verification Checklist, Epic Closure
Checklist), with the DoD required to map directly onto spec.md's acceptance/exit criteria; a
25-item mental self-review checklist to run before writing the file at all; and a final
instruction to, after writing, report phase/task counts, tasks-per-phase, major dependencies,
test-strategy summary, security/RBAC/tenant-isolation/cross-module coverage, final-
verification strategy, and any spec/plan inconsistency discovered — explicitly never silently
resolving a discovered inconsistency.]

## Response snapshot

Wrote `specs/009-crm/tasks.md` (103 atomic tasks, T001–T103, across the exact 10 phases the
brief specified, plus 10 in-line Phase Gates and 17 trailing sections) — following the user's
explicit rich per-task format (Purpose/Files-areas/Implementation/Dependencies/Acceptance/
Tests) rather than the generic single-line `/sp.tasks` template format or Epic 8's own denser
one-line-per-task precedent, since the user's brief was far more detailed and explicit than
either and "must be concrete enough that Claude Code can implement it without guessing" was
stated as a hard requirement — matching the same "user brief overrides generic template"
pattern already established for this epic's `/sp.specify` and `/sp.plan` invocations.

Every task cites the exact real file path, real existing service/repository/pattern it must
match or call (`BaseRepository`, `PaginationParams`/`PaginatedResponse[T]`, the `sales_rep_id`-
style cross-module UUID-FK convention, `_transition_status()` idiom from
`modules/inventory/services/product_service.py`, `CompanyMemberRepository` for ownership
validation, `AccountsReceivableService`'s exact method names, `CompanyAuditService.record()`'s
signature shape, `modules/sales/events/__init__.py`'s exact `InProcessEventBus`/`get_event_bus`
pattern, `modules/accounting/handlers/integration_handlers.py`'s cross-module-subscription
precedent) — grounded in the same repository-verified facts already established during this
epic's spec- and plan-writing phases, re-cited rather than re-derived.

Key structural decisions: (1) Lead conversion (T037, the single highest-risk task in the
whole document) is spelled out as an explicit 8-step numbered procedure directly encoding
spec.md §16/plan.md ADR-4's single-transaction/single-commit/idempotent/optimistic-lock
design — not left as a one-line "implement conversion" task. (2) A deliberate forward-
dependency-avoidance pattern is used throughout Phases 3–7: audit/permission/event call sites
are stubbed as explicit TODO comments referencing the exact later task that completes them
(e.g. T026 stubs the audit call, T069 wires it for real), rather than either building Phase 8's
infrastructure prematurely or leaving Phases 3–7 silently incomplete — this keeps each phase's
own Independent Test achievable without jumping ahead. (3) A genuine model-sharing dependency
between Phase 4 (Lead Conversion, needs the `Opportunity` model to create one) and Phase 5
(Pipeline & Opportunity, which formally owns that model) is called out explicitly in T034's
own note and in the Dependency Graph section as a shared-model dependency, not a circular one
— resolved by sequencing `Opportunity`'s model creation early in Phase 2 (T015) and its
service/API layer in Phase 5, with Phase 4 only ever calling the repository methods that
already exist by the time it runs. (4) The three Epic 1–8 files this epic is allowed to touch
(`modules/users_roles/constants.py`, `backend/main.py`, `backend/api/v1/router.py`) are each
tied to one specific, individually-numbered task (T060/T061, T077, T079) rather than being
folded anonymously into a larger task, so the final git-diff audit (T102) has an exact,
individually-checkable list to verify against. (5) A concrete, automated N+1-prevention
regression guard (T056, a query-count assertion) is specified as a NEW testing technique for
this codebase (flagged as such, since no existing precedent for query-count assertions was
found during research) — directly responding to plan.md's own R-04 risk entry rather than
leaving Customer 360 performance as an assumption.

All 17 required trailing sections were produced: Task Summary (103 tasks, phase/story
breakdowns), Dependency Graph (ASCII, explicitly annotated to explain the one non-obvious
Phase 4/5 relationship is not a cycle), Parallel Execution Examples, a full Requirement
Traceability Matrix (every FR-001–FR-022, every BR/INV, every US-1–US-5, every AC/EC mapped to
concrete task and test IDs — zero requirement left without both an implementation task and a
verification task), a Test Traceability Matrix (by test level and file), 8 named checklists
(Database/Migration, API, Frontend, Security/RBAC, Tenant Isolation, Audit/Event, Performance,
Cross-Module Integration), a Known Deferred Scope section (11 items, explicitly framed as
"read this before touching modules/crm/ again if context is lost"), a Phase Gate Checklist
(pointing back to the 10 in-line gates rather than duplicating them), an Epic 9 Definition of
Done (deliberately kept as a pointer to plan.md §35 rather than restating it, to avoid the two
documents drifting out of sync the way spec.md's event count briefly did during the plan
phase), a 20-item Epic 9 Final Verification Checklist mapping each of the brief's named items
to specific tasks, and an Epic Closure Checklist.

A pre-write self-consistency pass (mirroring the brief's own requested 25-item mental
checklist) confirmed: every FR/AC/EC has task+test coverage; every CRM entity has model/
repository/service/API/test coverage; every mutation has RBAC coverage; every entity has
tenant-isolation coverage; lead conversion has explicit transaction/idempotency/concurrency
coverage (T037–T039); Customer 360 has explicit N+1-prevention coverage (T056); feature flag
has enabled/disabled coverage (T010, T078); Postgres-specific constraints are tested against
real Postgres, not SQLite alone (T021, T039); full regression is scoped to Phase 10 only, not
after every phase; no out-of-scope item became a task (cross-checked against the Known
Deferred Scope list while writing); task IDs are sequential and acyclic.

Confirmed via `git status --porcelain`: only `specs/009-crm/` (now including `tasks.md`) and
`history/prompts/009-crm/` are new/modified — `spec.md` and `plan.md` were NOT touched in this
phase, per the explicit instruction. Zero application code was created or modified.

**Specification/plan inconsistency discovered**: none new. The one inconsistency found and
already corrected during the prior `/sp.plan` phase (spec.md's event-count summary line said
"11" when its own table lists 12) was already fixed in both documents before this phase began
— re-verified here as still consistent (T072/T073/T075/the Requirement Traceability Matrix all
correctly reference 12 events) and not re-reported as a new finding.

## Outcome

- ✅ Impact: A 103-task, fully traceable, dependency-ordered, phase-gated implementation
  breakdown exists at `specs/009-crm/tasks.md`, ready for actual Epic 9 implementation to
  begin task-by-task. Every spec.md FR/BR/INV/AC/EC has both an implementation task and a
  verification task. No architectural decision is left for an implementing agent to guess.
- 🧪 Tests: None run — task-breakdown-only phase, no code produced to test.
- 📁 Files: `specs/009-crm/tasks.md` (new). `spec.md`/`plan.md` confirmed untouched.
- 🔁 Next prompts: Epic 9 implementation, task-by-task starting at T001 (not started in this
  phase, per explicit instruction — no code, no Epic 10).
- 🧠 Reflection: The forward-dependency-avoidance stubbing pattern (explicit TODO comments
  naming the exact later task that completes a stub) is worth calling out as a reusable
  technique for any future multi-phase epic where security/audit/event infrastructure is
  naturally built in a later phase than the business logic that needs to call into it — it
  keeps each phase's own "Independent Test" claim honest without forcing either premature
  infrastructure work or silently-incomplete early phases.

## Evaluation notes (flywheel)

- Failure modes observed: none new in this phase — the one real inconsistency in this epic's
  artifacts (the event-count miscount) was already caught and fixed one phase earlier; this
  phase's own self-review pass found no new discrepancy between tasks.md and its two source
  documents.
- Graders run and results (PASS/FAIL): manual 25-item pre-write self-consistency checklist
  (mirroring the brief's own requested review) — PASS, all 25 items, documented above. Manual
  cross-check of the brief's "Final Self-Review" list against the finished document — PASS.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): none identified — tasks.md is ready for
  implementation to begin; no rework flagged.
