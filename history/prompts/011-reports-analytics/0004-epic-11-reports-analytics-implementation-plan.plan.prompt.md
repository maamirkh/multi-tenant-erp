---
id: 0004
title: Epic 11 Reports Analytics implementation plan
stage: plan
date: 2026-09-11
surface: agent
model: claude-sonnet-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: /sp.plan
labels: ["reports-analytics", "planning", "architecture", "entitlements", "cross-module"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/011-reports-analytics/plan.md
 - specs/011-reports-analytics/research.md
 - specs/011-reports-analytics/data-model.md
 - specs/011-reports-analytics/quickstart.md
 - specs/011-reports-analytics/contracts/reports-api.yaml
 - CLAUDE.md (Active Technologies / Recent Changes sections, via update-agent-context.sh)
tests:
 - None executed (planning-only phase; no code/migrations created)
---

## Prompt

# DevSphere ERP SaaS

# Epic 11 — Reports & Analytics

## Full & Final `plan.md` Prompt

You are working on the existing **DevSphere ERP SaaS** repository.

Epic 11 specification has completed its discovery, correction, and approval cycle.

The approved specification is:

`specs/011-reports-analytics/spec.md`

Your task now is to produce the **final implementation plan** for:

**Epic 11 — Reports & Analytics**

This is a **PLANNING-ONLY** phase.

Do NOT implement Epic 11.

---

# 1. GOVERNING SOURCE

Treat the approved:

`specs/011-reports-analytics/spec.md`

as the authoritative Epic 11 business specification.

Also inspect and obey:

* project Constitution;
* relevant ADRs;
* completed Epic specs/plans/tasks where helpful;
* current repository architecture;
* actual service/repository/router/test conventions.

Do NOT silently reinterpret or weaken the approved specification.

If the specification conflicts with repository reality discovered during planning, document the conflict explicitly rather than inventing an implementation.

---

# 2. CURRENT VERIFIED BASELINE

Epic 11 begins from a stabilized repository.

Current verified baseline:

* production MyPy: 0
* test MyPy: 0
* repository-wide `mypy .`: 0
* Ruff clean
* formatting clean
* repository-wide MyPy is blocking CI
* real PostgreSQL CI/test infrastructure exists
* pre-Epic-11 remediation is complete
* implementation must preserve all existing quality gates

The plan must preserve:

**`mypy . = 0`**

throughout implementation.

Do not plan broad suppressions, `Any`-based escape hatches, or CI weakening.

---

# 3. SPECIFICATION STATUS

The approved spec includes, among other things:

* centralized typed Report Registry;
* KPI/Metric semantic catalog;
* Executive Dashboard;
* wrapped domain reports for Sales, Purchase, Inventory, Accounting, CRM, Installments;
* Customer 360 composite read model;
* private saved report views;
* CSV/XLSX exports;
* limited PDF reuse where existing Accounting infrastructure already supports it;
* tenant isolation;
* domain entitlement checks;
* reports entitlement;
* RBAC;
* drill-down authorization;
* branch-as-data-filter semantics only;
* operational vs financial metric distinction;
* Inventory WAC valuation explicitly treated as operational and unreconciled;
* AI-ready report contracts without implementing AI.

Do not expand beyond approved Epic 11 scope.

---

# 4. REQUIRED PLAN OUTPUT

Create/update:

`specs/011-reports-analytics/plan.md`

Use the repository's normal planning format if one already exists.

Also update any plan-stage supporting documentation required by the existing project workflow.

Do NOT create `tasks.md` yet.

---

# 5. PLAN PURPOSE

The plan must translate the approved specification into an implementation architecture that is:

* concrete;
* sequenced;
* technically feasible;
* traceable;
* testable;
* migration-aware;
* security-aware;
* performance-conscious;
* compatible with existing module boundaries.

The plan should make the later `tasks.md` phase almost mechanical.

Avoid vague statements such as:

"Implement reports."

Instead define exactly:

* which layers are created;
* which existing layers are reused;
* where new state lives;
* how report execution flows;
* how permissions/entitlements are enforced;
* how tests are structured;
* what migrations are needed;
* what frontend architecture is added;
* how rollout is phased.

---

# 6. REPOSITORY RE-DISCOVERY BEFORE PLANNING

Before finalizing the plan, inspect the current repository again.

Planning must verify at minimum:

* exact module paths;
* router composition;
* service patterns;
* repository interfaces;
* permission-check helpers;
* entitlement helpers;
* Capability registration;
* Pydantic schema conventions;
* SQLAlchemy model conventions;
* Alembic conventions;
* audit/event conventions;
* export services;
* frontend route structure;
* auth context;
* existing report pages;
* existing test fixture topology;
* CI gates.

Do not rely only on the specification's historical discovery notes if the repository has changed.

---

# 7. ARCHITECTURAL PRINCIPLE — THIN REPORTING ORCHESTRATION

Epic 11 must NOT rebuild domain report computations.

The plan must preserve this architecture:

**Epic 11 owns orchestration, contracts, metadata, composition, security, saved views, and unified UX.**

Existing domains continue to own their own business/report computations.

For wrapped reports:

Reports layer
→ authoritative domain report/KPI service
→ typed result
→ unified response/export

Do NOT plan raw cross-module SQL where an existing domain service already provides the authoritative result.

---

# 8. REPORTS MODULE STRUCTURE

Plan the new Reports & Analytics backend module using the repository's actual vertical-slice conventions.

Likely areas to evaluate:

* router
* schemas
* services
* registry
* metric catalog
* permissions
* validators
* repositories
* models
* exports
* audit
* tests

Do not create folders merely because they appear above.

Use repository-established structure.

The plan must state the exact proposed file/module layout.

---

# 9. REPORT REGISTRY DESIGN

The approved spec requires a static typed Report Registry.

Plan the exact implementation shape.

Define:

* ReportDefinition type/model;
* stable report keys;
* domain;
* description;
* authoritative source adapter/service;
* required permission;
* required entitlements;
* supported filters;
* supported dimensions;
* supported measures;
* sortable fields;
* export formats;
* drill-down targets;
* branch-filter support;
* freshness classification.

The registry must remain:

* curated;
* code-defined;
* typed;
* non-user-editable;
* non-SQL-generating.

Do NOT turn it into a dynamic query engine.

---

# 10. REPORT EXECUTION SERVICE

Plan one clear execution/orchestration path.

Recommended conceptual flow:

Authenticated request
→ tenant context
→ `reports` entitlement
→ report definition lookup
→ report-specific domain entitlement
→ RBAC
→ filter validation
→ domain adapter/service
→ typed result
→ unified response/export

Adapt to the real repository.

Avoid duplicating these checks independently across dozens of endpoints.

Plan where centralized orchestration ends and domain-specific handling begins.

---

# 11. REPORT ADAPTER / WRAPPER STRATEGY

Because existing domains expose different report APIs, plan a consistent adapter strategy.

The implementation should normalize differences without rewriting calculations.

For each source domain define how Epic 11 wraps:

* Sales
* Purchase
* Inventory
* Accounting
* CRM
* Installments

The plan should explicitly document:

* adapter interface;
* typed input;
* typed output;
* error propagation;
* pagination mapping;
* export mapping;
* service reuse.

Avoid generic `dict[str, Any]` report plumbing.

---

# 12. METRIC CATALOG

Plan a typed metric-definition layer corresponding to the approved KPI catalog.

Every important reusable metric should have:

* stable semantic ID;
* source domain;
* source service/method;
* label;
* description;
* format;
* comparison support;
* currency semantics;
* inclusion rules.

Do not recompute existing domain metrics in the reporting layer.

---

# 13. EXECUTIVE DASHBOARD IMPLEMENTATION PLAN

Plan the Executive Dashboard as a bounded composition service.

Do not implement it as one uncontrolled mega-query.

Recommended execution model:

* resolve authorized widgets;
* evaluate each widget's domain entitlement;
* invoke authoritative source service;
* normalize result;
* return fixed typed dashboard response.

Plan how partial failures are handled.

A single unavailable domain should not necessarily fail the entire dashboard.

But do not swallow genuine platform/security errors.

---

# 14. INSTALLMENTS SERVICING-CONTINUITY EXCEPTION

This rule is now locked in the approved specification.

The plan MUST explicitly handle:

### Case A

Installments disabled and no existing serviceable obligations:

* Installment reports unavailable;
* normal module-not-entitled behavior.

### Case B

Installments disabled but existing serviceable obligations remain:

* servicing-continuity reports remain read-only;
* no origination;
* no configuration;
* no plan/template creation;
* no disabled write capability.

Plan exactly where this decision is evaluated.

Do NOT duplicate Installments' entitlement logic inside Reports.

Reuse the existing Installments access policy / service invariant.

The plan must identify the specific seam through which Reports asks Installments whether servicing-continuity reads are allowed.

---

# 15. CUSTOMER 360 IMPLEMENTATION

Customer 360 must remain a:

**composite read model**

not a persisted business aggregate.

Plan:

* base authorization;
* customer master lookup;
* section-by-section composition;
* section-level entitlements;
* section-level permissions;
* result-state representation;
* timeout/error behavior;
* drill-down links.

Sections:

* Sales/customer activity
* Accounting AR
* CRM
* Installments

Do not persist a Customer 360 table.

---

# 16. CUSTOMER 360 RESULT MODEL

Plan an explicit typed response that can distinguish:

* present;
* omitted due to authorization/entitlement;
* unavailable/not configured;
* valid zero.

Do not use ambiguous nulls if repository conventions support a stronger typed representation.

Ensure customer existence cannot leak through IDOR behavior.

---

# 17. CUSTOMER MASTER AUTHORIZATION

The plan must define the minimum authorization needed to open Customer 360.

A user should not learn that a customer exists merely from the composite endpoint if they cannot legitimately access that customer master record.

Plan:

* tenant check;
* customer lookup behavior;
* not-found/unauthorized indistinguishability;
* section authorization after base customer authorization.

---

# 18. REPORTS CAPABILITY DEFAULT — LOCK THIS IN PLAN

The approved specification left the new `reports` capability default as a non-blocking planning decision.

For this plan, use the following recommendation unless repository architecture makes it impossible:

**`reports` capability should be disabled by default.**

Reason:

* Reports & Analytics is a value-added SaaS capability;
* it is not a core transactional recording module;
* this supports future SaaS plan differentiation;
* it matches the optional capability pattern better than silently inheriting always-on behavior.

The plan must make this decision explicit.

Do not leave it accidental.

If the existing Capability system requires a different mechanism, document the exact compatible implementation while preserving the product intent.

---

# 19. CAPABILITY / ENTITLEMENT REGISTRATION

Plan:

* Capability catalogue update;
* migration/seed implications;
* plan assignment behavior;
* default state;
* Platform Admin visibility;
* tenant enablement.

Do not invent a parallel feature-flag system.

Reuse the existing entitlement platform.

---

# 20. REPORT PERMISSIONS

Plan the new `reports.*` permissions using existing RBAC seeding/registration conventions.

At minimum account for:

* executive
* sales
* purchase
* inventory
* accounting
* CRM
* installments
* customer_360
* export actions
* saved view management

Do not hardcode permissions to fixed roles.

Plan seed/registration only.

---

# 21. VIEW VS EXPORT PERMISSIONS

Keep `.view` and `.export` separate.

The plan must show:

* where each is checked;
* how exports reuse the view's exact filter scope;
* how export-specific permission is applied;
* how sensitive fields remain excluded.

Do not allow export to become a second data-access path.

---

# 22. SAVED REPORT VIEWS

Plan the new Epic 11-owned persistence for private saved views.

Define proposed model fields such as:

* id
* company_id
* user_id
* report_key
* name
* filter configuration
* grouping
* sorting
* visible columns
* date preset
* timestamps
* soft-delete if repository convention requires it

Use actual project conventions.

The plan must address:

* tenant scope;
* owner scope;
* schema validation;
* versioning;
* loading against changed registry definitions;
* deletion.

No shared views in Epic 11.

---

# 23. SAVED VIEW STORAGE FORMAT

Do not blindly store arbitrary JSON.

Plan a safe schema strategy.

If JSON/JSONB is used, define:

* validated structure;
* version field;
* allowed keys;
* migration/compatibility behavior.

Saved views must never store arbitrary SQL or unrestricted query expressions.

---

# 24. DATABASE MIGRATION PLAN

List every expected migration category.

Potential examples:

* saved report views;
* new permission seeds;
* reports Capability registration;
* indexes required for new cross-module access paths.

Do not create migrations yet.

Specify whether permission/capability changes are:

* migration-driven;
* seed-service-driven;
* application startup-driven;
* existing catalogue registration.

Use actual repository patterns.

---

# 25. INDEX STRATEGY

For new queries only, plan index review.

Especially inspect:

* saved-view ownership lookups;
* Customer 360 customer-key lookups;
* any new cross-module foreign/reference lookup;
* export pagination paths.

Do not create redundant indexes for existing wrapped reports.

---

# 26. INVENTORY VALUATION

The approved spec intentionally preserves the unresolved inventory-to-GL gap.

The plan MUST NOT attempt to fix ADR-0004.

Epic 11 should expose:

**Operational Stock Valuation (WAC)**

only.

Plan:

* exact service reuse;
* response naming;
* `valuation_basis`;
* disclaimer metadata;
* frontend labeling.

Do not present it as Balance Sheet inventory value.

---

# 27. FINANCIAL REPORT WRAPPING

Plan financial report wrappers around Accounting's existing services.

Financial reports must reconcile exactly with Accounting.

Plan equivalence tests for:

* Trial Balance;
* GL;
* P&L;
* Balance Sheet;
* Cash Flow;
* AR;
* AP;
* bank/cash books;
* financial KPIs.

No alternate formulas.

---

# 28. PAGINATION

Plan a unified pagination contract.

Where wrapped domains already use different pagination methods:

* offset/page;
* cursor;
* bounded aggregate;

the Reports layer should expose the approved public contract without introducing correctness bugs.

If cursor-based GL cannot safely be translated into page-number pagination, document a report-specific exception rather than forcing an artificial abstraction.

The plan should explicitly resolve this.

---

# 29. FILTER SCHEMAS

Plan typed Pydantic filter schemas.

Do not use one giant untyped filter dictionary for every report.

Recommended approach:

* common base/date filter components;
* domain/report-specific typed schemas;
* registry maps reports to supported filter model.

Avoid duplicate boilerplate where clean reusable components exist.

---

# 30. DATE / TIME RANGE SERVICE

Plan a shared Reports date-range utility only if no existing equivalent is sufficient.

It should normalize:

* presets;
* tenant timezone;
* half-open UTC range;
* comparison range.

Reuse `Company.default_timezone`, `utcnow()`, and `ensure_utc()`.

Do not implement new timezone infrastructure.

---

# 31. COMPARISON ENGINE

Plan how previous-period comparisons are produced.

Prefer a small shared helper that determines:

* comparison period;
* absolute change;
* percentage change;
* zero denominator behavior;
* not-comparable state.

Do not reimplement domain metrics.

It may call the same source service twice for two periods.

---

# 32. MONEY / CURRENCY NORMALIZATION

Plan shared presentation/normalization contracts without changing domain financial logic.

Do not introduce float arithmetic.

All money remains Decimal.

Cross-module dashboards must not sum unrelated currencies without Accounting-backed conversion.

The plan should identify where multi-currency behavior requires implementation-time verification.

---

# 33. EXPORT SERVICE

Plan a unified Reports export orchestration service.

It should:

* validate report key;
* validate filters;
* authorize view/export;
* call the same report execution path;
* produce selected format;
* enforce configured limit;
* audit export.

Do not create separate export calculations.

---

# 34. EXPORT ROW LIMIT

Implement the approved invariant:

**bounded synchronous exports.**

The plan must:

* define central config;
* permit different CSV/XLSX limits;
* specify how representative benchmarking finalizes values;
* treat 50,000 only as an initial candidate.

Do not hardcode 50,000 across endpoints.

---

# 35. CSV SECURITY

Plan formula-injection mitigation.

Define where CSV cell neutralization occurs.

Ensure this is centralized and tested.

---

# 36. PDF

Do not build a generic new PDF reporting framework.

Plan to reuse existing Accounting PDF export only for reports already supported there.

Other reports remain CSV/XLSX unless implementation discovery proves an existing safe reusable PDF path.

---

# 37. AUDIT

Plan audit coverage for:

* exports;
* saved-view create/update/delete;
* other sensitive reporting actions if justified.

Do not log every dashboard refresh unless the repository explicitly requires it.

Define audit payload fields.

Avoid storing full sensitive datasets in logs.

---

# 38. OBSERVABILITY

Plan lightweight reporting telemetry.

Suggested metadata:

* report key;
* tenant id;
* execution duration;
* outcome;
* result row count;
* export format;
* slow-query marker.

Avoid PII/report contents in logs.

Use existing logging/observability conventions.

---

# 39. FRONTEND ROUTING

Plan the frontend route architecture.

Recommended conceptual structure:

Reports

* Overview
* Sales
* Purchases
* Inventory
* Finance
* CRM
* Installments

But adapt to the existing App Router structure.

Define exact proposed pages/routes.

---

# 40. FRONTEND SHARED COMPONENTS

Plan reusable components such as:

* report page shell;
* date/period selector;
* comparison selector;
* filter bar;
* DataTable;
* KPI card;
* chart wrapper;
* export action;
* saved-view selector;
* empty/error/unavailable states.

Do not create an oversized generic "do everything" report component.

---

# 41. CHART LIBRARY

The spec found no existing charting library.

Plan one dependency only if charts genuinely need it.

Evaluate a lightweight React-compatible library.

Do not add multiple chart packages.

The plan must justify:

* chosen package;
* accessibility;
* bundle impact;
* compatibility with Next.js/React version;
* SSR/client-component boundary.

Do not install it during planning.

---

# 42. FRONTEND DATA FETCHING

Plan how report pages fetch data using current frontend conventions.

Avoid duplicating API client logic.

Respect:

* authentication;
* tenant context;
* permission-driven navigation;
* entitlement-aware discovery endpoint;
* loading/error states.

---

# 43. REPORT DISCOVERY ENDPOINT

Plan the authorized report discovery endpoint required by the spec.

It should return only report definitions the current user may see.

Define:

* route;
* response schema;
* permission filtering;
* entitlement filtering;
* frontend usage.

Avoid frontend 403-probing as a navigation strategy.

---

# 44. DRILL-DOWN ARCHITECTURE

Plan drill-down as explicit links/actions, not arbitrary generic entity browsing.

For each report family identify:

* source list;
* underlying record route;
* required domain permission;
* filter preservation.

Underlying record access must reauthorize independently.

---

# 45. ERROR MODEL

Plan reuse of existing error envelopes.

Document expected categories:

* report not found;
* permission denied;
* entitlement denied;
* invalid filter;
* unsupported sort;
* unavailable prerequisite;
* export too large;
* source-domain failure.

Do not expose internal SQL/service exceptions.

---

# 46. REPORT AVAILABILITY STATES

Plan typed availability states where needed.

Especially distinguish:

* zero;
* empty;
* omitted due to authorization;
* unavailable/not configured;
* deferred/not shipped.

This is important for Dashboard and Customer 360.

---

# 47. TEST ARCHITECTURE

The plan must define test layers.

At minimum:

### Unit

* registry validation;
* metric definitions;
* filter validation;
* comparison logic;
* saved-view validation;
* entitlement branching;
* export cell sanitization.

### Contract

* adapter ↔ domain service contracts;
* wrapper response schemas;
* report registry consistency.

### Security

* tenant isolation;
* IDOR;
* permissions;
* exports;
* saved-view ownership;
* Platform Admin boundary.

### Real PostgreSQL Integration

* aggregations;
* Decimal;
* date grouping;
* pagination;
* Customer 360;
* saved views;
* migrations.

### Financial Invariants

* Accounting wrapper equivalence;
* TB balance;
* BS equation;
* AR/AP reconciliation;
* Installments ↔ Accounting reconciliation.

### Frontend

* filters;
* permission-based visibility;
* entitlement-based visibility;
* export actions;
* saved views;
* disabled module states.

---

# 48. INSTALLMENTS TEST MATRIX

Explicitly plan tests for:

* enabled Installments;
* disabled + no obligations;
* disabled + existing obligations;
* read-only report access;
* blocked origination/configuration;
* dashboard widget Case A;
* dashboard widget Case B;
* Customer 360 Installments section Case A/B.

This exception is important enough to require dedicated coverage.

---

# 49. CUSTOMER 360 TEST MATRIX

Plan combinations including:

* all domains enabled;
* CRM disabled;
* Installments disabled;
* Accounting permission missing;
* customer not found;
* cross-tenant customer ID;
* valid zero AR;
* Accounting not configured;
* no Sales transactions;
* partial section composition.

---

# 50. ENTITLEMENT TEST MATRIX

Cover every report family against:

* reports enabled/disabled;
* domain enabled/disabled;
* domain permission present/absent;
* export permission present/absent.

Do not rely on UI hiding.

---

# 51. PERFORMANCE TESTING

Do not introduce shared-runner fragile wall-clock guards.

Plan:

* query-count assertions;
* no-N+1 tests;
* representative large datasets;
* query-plan inspection where appropriate;
* export memory/runtime profiling;
* isolated performance benchmarks if needed.

Carry forward the Pre-Epic-11 lesson.

---

# 52. MIGRATION TESTING

Plan real PostgreSQL validation of any new migration.

Include:

* clean upgrade;
* downgrade if repository convention requires it;
* migration chain continuity;
* constraints/index verification.

Do not use SQLite as the only migration validator.

---

# 53. TYPE SAFETY

Plan typed contracts end-to-end.

Avoid:

* `dict[str, Any]` registries;
* untyped service maps;
* dynamic callable dispatch without Protocols/typed interfaces;
* raw JSON payload passing internally.

Use:

* Pydantic schemas;
* enums/literals where appropriate;
* Protocols/abstract interfaces only where repository architecture supports them.

---

# 54. IMPLEMENTATION PHASING

Produce a concrete phase sequence.

My recommended high-level order:

### Phase 0 — Foundation / contracts

* Reports module scaffold
* Capability registration
* permissions
* typed registry
* report definition/metric contracts
* shared filter/date/comparison contracts

### Phase 1 — Saved Views persistence

* model
* migration
* repository
* service
* validation
* ownership security

### Phase 2 — Domain adapters

* Sales
* Purchase
* Inventory
* Accounting
* CRM
* Installments

### Phase 3 — Unified report execution API

* discovery
* report execution
* pagination
* drill-down metadata

### Phase 4 — Executive Dashboard

### Phase 5 — Customer 360

### Phase 6 — Exports & Audit

### Phase 7 — Frontend foundation

* route group
* report shell
* shared table/filter/formatting/chart primitives

### Phase 8 — Domain report pages

### Phase 9 — Dashboard + Customer 360 UI

### Phase 10 — Security / PostgreSQL / reconciliation / performance hardening

### Phase 11 — Full regression / documentation / release readiness

Adjust this sequence if repository dependencies justify a better one.

The final plan must explain dependency order.

---

# 55. GATES BETWEEN PHASES

Define objective gates.

Example:

Foundation gate must prove:

* registry compiles;
* permissions/entitlement wired;
* no implementation report endpoint bypasses registry.

Adapter gate must prove:

* wrappers produce equivalent results to existing source services.

Dashboard gate must prove:

* per-widget authorization and Installments exception.

Customer 360 gate must prove:

* section-level authorization and tenant isolation.

Export gate must prove:

* no data widening;
* CSV injection protection;
* audit.

Final gate must prove:

* `mypy . = 0`;
* Ruff/format;
* full tests;
* migrations;
* real Postgres;
* frontend tests/build.

---

# 56. BACKWARD COMPATIBILITY

Existing domain report endpoints MUST remain working.

Epic 11 adds a unified reporting surface; it does not delete or silently change:

* Sales reports;
* Purchase reports;
* Inventory reports;
* Accounting reports;
* CRM reports;
* Installments reports.

Plan compatibility tests where useful.

---

# 57. NO MASS REFACTOR

Do not use Epic 11 as justification to rewrite all existing domain reporting services.

Refactor only where required for:

* a stable adapter seam;
* type correctness;
* security;
* a proven bug.

Prefer thin adapters.

---

# 58. BUG DISCOVERY POLICY

If planning discovers an existing bug:

* document it;
* identify whether Epic 11 depends on fixing it;
* classify it as blocker / prerequisite / separate debt.

Do not silently bury unrelated fixes inside Epic 11.

---

# 59. DEFERRED REPORTS

Do not accidentally plan implementation of all deferred report variants.

Plan infrastructure so they can be registered later.

Current `Now` catalog drives Epic 11 implementation.

Deferred items remain deferred unless the approved spec explicitly changed them.

---

# 60. BRANCH PERFORMANCE

`crossmodule.branch_performance` is locked:

**DEFERRED**

Do not plan its implementation.

Do not build Branch ACL.

Do not invent Branch domain state.

Branch filtering in current reports remains a data-filter feature only where existing source fields support it.

---

# 61. AI BOUNDARY

Plan stable contracts so a future AI gateway can reuse them.

Do NOT implement:

* AI agents;
* LLM calls;
* OpenClaw;
* NL-to-SQL;
* embeddings;
* vector DB;
* AI billing.

Do not add AI dependencies.

---

# 62. PLAN TRACEABILITY

Every major implementation phase/component should reference relevant specification requirement IDs.

The plan should be traceable enough that `tasks.md` can map tasks to:

* FRs;
* security requirements;
* test scenarios;
* acceptance scenarios.

---

# 63. PLAN RISKS

Create a concrete risk register.

Include at minimum:

* divergence between existing domain report schemas;
* accidental metric recomputation;
* Customer 360 partial-authorization complexity;
* Installments servicing-continuity exception;
* export memory pressure;
* frontend/report schema sprawl;
* Accounting performance;
* loose UUID cross-module references;
* inventory valuation misunderstanding;
* migration/permission seed drift;
* chart dependency overhead.

For each provide mitigation.

---

# 64. PLAN DECISIONS / ADR NEEDS

Identify whether any Epic 11 decisions deserve ADRs.

Potential candidates:

* static typed Report Registry architecture;
* reports entitlement default;
* Customer 360 section-level authorization;
* unified report adapter contract.

Do not create unnecessary ADRs for trivial implementation details.

If existing ADR workflow requires them, list exactly what should be created during implementation.

---

# 65. PLAN OPEN QUESTIONS

The final plan should minimize open questions.

Allowed planning decisions include:

* exact CSV/XLSX export limits after benchmarking;
* final chart library;
* exact query-range limits;
* whether a small number of new indexes are needed.

These must not block architecture.

Target:

**No blocking implementation questions.**

---

# 66. DO NOT CREATE TASKS YET

This phase produces `plan.md` only.

Do NOT create:

`specs/011-reports-analytics/tasks.md`

Tasks will be generated only after the plan is reviewed and approved.

---

# 67. PLAN VALIDATION

Before finalizing:

check the plan against the approved spec.

Verify:

* every Now report is accounted for;
* every new persistence requirement is planned;
* every permission is planned;
* every entitlement behavior is planned;
* Installments exception is preserved;
* Customer 360 is partial-composition;
* Inventory valuation remains operational only;
* Branch Performance is deferred;
* export security is planned;
* financial invariant testing is planned;
* frontend scope is planned;
* `mypy . = 0` is preserved;
* no AI implementation appears.

---

# 68. REQUIRED `plan.md` STRUCTURE

Use project conventions, but ensure the plan covers at least:

1. Plan status
2. Approved specification reference
3. Repository findings
4. Architecture overview
5. Component/module structure
6. Report Registry design
7. Metric catalog implementation
8. Report execution flow
9. Domain adapter strategy
10. Permissions/RBAC
11. Entitlements
12. Reports capability default
13. Installments servicing-continuity design
14. Customer 360 design
15. Saved views
16. Database/migrations
17. Index strategy
18. API design
19. Pagination/filtering
20. date/comparison/money handling
21. exports
22. audit/observability
23. frontend architecture
24. charting decision
25. drill-down
26. availability/error states
27. security architecture
28. test architecture
29. real-Postgres validation
30. financial reconciliation
31. performance plan
32. type safety
33. implementation phases
34. phase gates
35. backward compatibility
36. risk register
37. ADR/decision needs
38. deferred scope
39. traceability
40. open questions
41. readiness verdict

Merge sections only where repository conventions make it cleaner.

---

# 69. FINAL RESPONSE FORMAT

After creating `plan.md`, return:

# Epic 11 Implementation Plan Report

## A. Files Created/Modified

List exact files.

## B. Repository Findings

Important implementation-relevant discoveries.

## C. Architecture

Summarize:

* Reports module structure;
* registry;
* execution service;
* adapters;
* saved views;
* dashboard;
* Customer 360.

## D. Reports Capability Default

State the final decision.

Preferred:

**disabled by default**

and explain how it plugs into the existing Capability/Plan model.

## E. Installments Servicing Continuity

Confirm exactly how Case A and Case B are implemented architecturally.

## F. Customer 360

Confirm:

* base gate;
* section-level authorization;
* result states;
* customer-IDOR behavior.

## G. Database Changes Planned

List proposed migrations/models/index changes.

Do NOT create them.

## H. Export Strategy

State:

* formats;
* central limits;
* audit;
* formula-injection mitigation.

## I. Frontend Strategy

Summarize routes/shared components/chart decision.

## J. Test Strategy

Summarize all test layers.

## K. Implementation Phases

List final phases and gates.

## L. Risks

Top implementation risks.

## M. Open Decisions

List remaining non-blocking decisions.

Target:

**No blocking decisions.**

## N. Git Status

Branch and working-tree state.

Do NOT commit/push unless existing workflow explicitly requires it and authority already exists.

## O. Verdict

Return exactly:

**EPIC 11 PLAN READY FOR REVIEW**

or

**EPIC 11 PLAN BLOCKED**

---

# 70. STOP CONDITION

After `plan.md` is complete and validated:

STOP.

Do NOT create `tasks.md`.

Do NOT implement Epic 11.

Do NOT begin Epic 12.

Do NOT start AI Layer work.

Wait for explicit review and approval.

---

# FINAL INSTRUCTION

The approved Epic 11 specification is already mature.

Your job in `plan.md` is not to redesign the product.

Your job is to convert the approved specification into a precise, low-risk, repository-aligned implementation architecture.

The plan must preserve:

**One Metric → One Authoritative Definition → Many Consumers**

and:

**One Report → One Registered Contract → One Security Path → One Authoritative Source**

while ensuring:

* financial truth remains in Accounting;
* operational truth remains in its owning domain;
* Reports owns orchestration, not duplicated business logic;
* Customer 360 remains a composite read model;
* Installments servicing continuity remains intact;
* exports never widen access;
* tenant isolation remains non-negotiable;
* future AI can consume the same curated contracts without raw SQL or security bypass.

Create `plan.md`.

Validate it against the approved `spec.md`.

Then STOP.

## Response snapshot

Re-verified the repository directly (not just spec's historical discovery notes) via two parallel Explore agents covering backend conventions (module layout, router/entitlement gating, `InstallmentAccessPolicy`, permission-check pattern, the six report/KPI services to wrap, export services, Pydantic/SQLAlchemy/Alembic/audit conventions, test fixtures, CI gates) and frontend conventions (App Router structure, auth/tenant context, data fetching, shared components, existing report pages, discovery-endpoint precedent). Read the full 865-line approved spec.md.

Produced `specs/011-reports-analytics/plan.md` (41-section structure) covering: repository re-discovery findings with file:line citations; thin-orchestration architecture and execution flow (domain entitlement checked in-service via `PlatformEntitlementService.resolve_effective_entitlement()` rather than at router-mount, since one Reports router serves all six domains); full module/file layout for `backend/modules/reports/` and the new `(reports)` frontend route group; typed Report Registry (`ReportDefinition` frozen dataclasses + registry-consistency unit test) and Metric Catalog design; per-domain adapter strategy normalizing six structurally incompatible report/KPI services; RBAC (13 `reports.*` permission codes) and entitlement design; **`reports` Capability locked disabled-by-default**, requiring a new `ReportsFeatureFlagService`/`ReportsModuleEnablementProvider` (mirroring CRM/Installments) rather than the four core modules' `DefaultAlwaysEnabledModuleProvider`; **Installments servicing-continuity design** — a novel finding that `InstallmentAccessPolicy.authorize(READ)` permits unconditionally regardless of entitlement, so Case A/B is actually distinguished by a new `InstallmentsServicingContinuityGate` combining the standard entitlement check with a zero-new-code existence check via `get_contract_register(limit=1)`'s existing `total`; Customer 360 as a section-level, IDOR-safe composite read model with a three-state (`present`/`omitted`/`unavailable`) discriminated-union result model; `SavedReportView` persistence with a new validated-JSONB-plus-schema-version convention (none existed to reuse); migrations (`073`–`076` candidates); index strategy (only two new tables + no speculative indexes); API/pagination design (including a documented `CursorPage[T]` exception for Accounting's GL report only); exports (central row-limit config, new centralized CSV formula-injection sanitizer — flagging the pre-existing, unaddressed gap in four other modules' exports as separate debt); audit/observability; frontend architecture (Recharts selected and justified as the one new dependency); drill-down, availability/error states, security architecture, full test architecture (including dedicated Installments and Customer 360 test matrices), financial reconciliation testing, performance plan, type safety, an 11-phase rollout with objective gates, backward-compatibility guarantees (only 4 precedented additive edits to existing modules), a risk register, 2 ADR suggestions (queued for consent, not auto-created), deferred scope, traceability, and 8 non-blocking open decisions.

Also produced the existing project workflow's companion planning artifacts (present in prior epics 009a/010 but not explicitly requested by name in this prompt): `research.md` (11 decision/rationale/alternatives entries), `data-model.md` (2 persisted entities + 3 code-defined typed structures + Customer 360's cross-module reference shape), `quickstart.md` (8-step scenario walkthrough mirroring spec Scenarios A/B/C/H/J/E/N), and `contracts/reports-api.yaml` (OpenAPI sketch). Ran `.specify/scripts/bash/update-agent-context.sh claude`, which updated `CLAUDE.md`'s Active Technologies/Recent Changes sections automatically. No `tasks.md` was created (explicit stop condition honored). No code, migration, or dependency was installed.

Final verdict recorded in plan.md §41: **EPIC 11 PLAN READY FOR REVIEW**.

## Outcome

- ✅ Impact: Complete, repository-verified implementation plan for Epic 11 produced across 5 files; no blocking open questions; ready for human review before `/sp.tasks`.
- 🧪 Tests: None run — planning-only phase, no code changes made.
- 📁 Files: `specs/011-reports-analytics/{plan.md,research.md,data-model.md,quickstart.md,contracts/reports-api.yaml}`; `CLAUDE.md` auto-updated by `update-agent-context.sh`.
- 🔁 Next prompts: Human review of `plan.md`; upon approval, `/sp.tasks` to generate `specs/011-reports-analytics/tasks.md`; optionally `/sp.adr` for the two suggested ADRs (static Report Registry architecture; Customer 360 section-level compound authorization) at implementation kickoff.
- 🧠 Reflection: The most valuable discovery was that `InstallmentAccessPolicy.authorize(operation=READ)` passes unconditionally regardless of entitlement state — meaning the spec's Case A/B distinction cannot be enforced by that policy alone and required designing a new, small `InstallmentsServicingContinuityGate` in Reports' own module that reuses (never duplicates) an existing self-authorizing method's `total` return value. This is exactly the kind of repository-reality check the governing prompt's re-discovery mandate (§6) was designed to catch.

## Evaluation notes (flywheel)

- Failure modes observed: None blocking. One judgment call requiring plan-level clarification (not a spec deviation): the spec's Case B exclusion of "plan/template creation" reads naturally as targeting Installments' own write surface, not Reports' read-only `installments.plan_performance` report — documented explicitly in plan.md §13 rather than silently assumed either way.
- Graders run and results (PASS/FAIL): Not applicable — no automated grading harness invoked for this planning artifact; self-validated against spec.md §67's checklist inline in plan.md §41 (all items checked).
- Prompt variant (if applicable): N/A (single-pass execution of the provided 70-section governing prompt).
- Next experiment (smallest change to try): During `/sp.tasks`, confirm the small number of items plan.md §40 left as non-blocking open decisions (exact Sales customer-view permission code name, Accounting's "is COA configured" check, frontend test runner) before generating tasks that depend on them, to avoid a mid-task-generation pause.
