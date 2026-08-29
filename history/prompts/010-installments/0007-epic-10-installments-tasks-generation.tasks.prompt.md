---
id: 0007
title: Epic 10 Installments tasks generation
stage: tasks
date: 2026-08-24
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: /sp.tasks
labels: [installments, epic-10, tasks, accounting-integration, migrations, rbac, frontend, testing]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/010-installments/tasks.md
tests:
 - none (task-generation-only phase; no code, migrations, or tests implemented per stop condition)
---

## Prompt

/sp.tasks

Generate the final implementation-ready `tasks.md` for:

Epic 10 — Installments
Feature branch: `010-installments`

AUTHORITATIVE INPUTS
====================

Treat the following as the authoritative planning chain, in this order:

1. `.specify/memory/constitution.md`
2. `specs/010-installments/spec.md`
3. `specs/010-installments/plan.md`
4. `specs/010-installments/research.md`
5. `specs/010-installments/data-model.md`
6. `specs/010-installments/contracts/installments-api.yaml`
7. `specs/010-installments/quickstart.md`
8. Existing repository implementation and established conventions

Read ALL of them before generating tasks.

`spec.md` owns business requirements and invariants.
`plan.md` owns the approved technical architecture and implementation sequence.

Do NOT reopen settled product or architecture decisions during task generation.

Do NOT generate implementation code.
Do NOT create or modify migrations.
Do NOT implement any task.

Your job in this command is ONLY to generate a complete, dependency-correct, implementation-ready `tasks.md`.

============================================================
1. REPOSITORY RE-INSPECTION BEFORE TASK GENERATION
============================================================

Before writing tasks.md, inspect the actual repository again.

At minimum inspect:

- `backend/modules/accounting/`
- `backend/modules/sales/`
- `backend/modules/crm/`
- `backend/modules/platform_admin/`
- `backend/modules/users_roles/`
- `backend/core/`
- `backend/api/`
- existing Alembic migrations and current migration head
- relevant backend tests
- frontend routing/components/query/API conventions
- existing permission seeding/backfill conventions
- existing outbox/event infrastructure

This inspection is verification, not a new architecture-design phase.

If the repository has materially changed since `plan.md` was produced and a planned task is now technically invalid:

1. document the exact mismatch,
2. identify the affected plan section,
3. stop before silently redesigning the architecture.

Do not invent a workaround that contradicts the approved plan.

============================================================
2. TASK GENERATION PRINCIPLES
============================================================

Every task must be:

- atomic,
- implementation-ready,
- dependency-aware,
- independently verifiable,
- mapped to concrete files/areas,
- traceable to the approved spec/plan,
- small enough for an implementation agent to complete safely.

Avoid vague tasks such as:

- "implement installments"
- "add accounting integration"
- "add tests"
- "build frontend"

Break these into concrete implementation units.

Each task must make it clear:

- WHAT is being implemented,
- WHERE it belongs,
- WHY/which requirement it satisfies where useful,
- what must already exist before it can run.

Use repository-realistic paths.

Do not create speculative abstractions or files not justified by the plan/repository.

============================================================
3. PRESERVE THE APPROVED IMPLEMENTATION SEQUENCE
============================================================

The approved plan defines the following implementation phases.

Preserve this ordering unless an intra-phase dependency requires finer ordering:

Phase 1 — Module Foundation
Phase 2 — Configuration & Plans
Phase 3 — Contract Persistence
Phase 4 — Schedule Engine
Phase 5 — Contract Lifecycle
Phase 5.5 — Idempotency Primitive
Phase 6 — Accounting Integration
Phase 7 — Collections
Phase 8 — Delinquency
Phase 9 — Settlement
Phase 10 — Advanced Lifecycle
Phase 11 — Entitlement / Security Hardening
Phase 12 — Reporting / Documents
Phase 13 — Frontend
Phase 14 — Concurrency / Idempotency Hardening
Phase 15 — Integration / E2E / Regression

Do NOT flatten these into an arbitrary checklist.

tasks.md must visibly preserve phase boundaries and dependency order.

============================================================
4. CRITICAL HARD GATE — PHASE 6 ACCOUNTING INTEGRATION
============================================================

This is the most important dependency rule in the entire tasks file.

The corrected plan discovered existing Accounting commit-ownership issues.

Phase 6 MUST therefore implement and prove all required Accounting-side staged/finalize APIs BEFORE any dependent Installments money-mutating workflow is implemented.

Required coordinated Accounting work includes the approved APIs from plan.md, including:

AccountsReceivableService:
- `stage_adjustment()`
- `finalize_adjustment()`
- `reverse_adjustment()`
- `stage_write_off()`
- `finalize_write_off()`

PaymentService:
- `stage_customer_payment()`
- `finalize_customer_payment()`

AllocationEngine:
- `stage_allocation()`
- `finalize_allocation()`

Preserve existing public APIs for backward compatibility unless the plan explicitly says otherwise.

The implementation must follow the approved principle:

STAGE → flush only → Installments stages its own related rows/audit/outbox → FINALIZE LAST → commit

No dependent workflow may be scheduled before its required staged API exists and is tested.

Explicitly encode dependencies so that: activation with down payment depends on staged payment/allocation support, collections depend on staged payment/allocation support, settlement execution depends on the collection/payment atomic path, late charges depend on staged AR adjustment support, write-off depends on staged write-off support.

Do not allow an implementation agent to bypass this ordering.

============================================================
5. REVERSAL / CANCELLATION SPECIAL CASE
============================================================

Do NOT invent staged versions of `PaymentService.reallocate_payment()` / `PaymentService.cancel_payment()` unless repository inspection proves the approved plan has become invalid. The approved plan deliberately keeps these Accounting methods unchanged. For Installments collection reversal/cancellation, tasks must preserve the approved staging-order discipline: (1) lock/validate, (2) stage Installments reversal/status/audit/outbox/idempotency rows first, (3) only then invoke the existing Accounting reversal/reallocation operation, (4) ensure the first Accounting commit includes the already-staged Installments rows. Preserve the documented recovery/idempotency behavior for the multi-call reversal sequence. Do not falsely describe `reallocate_payment()` as a single-commit method.

============================================================
6. ACCOUNTING REMAINS THE FINANCIAL SOURCE OF TRUTH
============================================================

No task may introduce shadow financial truth. Installments must NEVER directly write: GL entries, Accounting Payment rows, PaymentAllocationLine rows, Accounting AR truth, CustomerLedger balances. Those remain Accounting-owned. Installments may own: contract, terms snapshot, schedule versions/lines, allocation references, late-charge metadata, lifecycle state, audit, idempotency, Installments configuration. Any financial mutation must go through approved Accounting public services / AccountingIntegrationGateway.

============================================================
7. DATABASE / MIGRATION TASKS
============================================================

Generate migration tasks according to the exact approved plan. First re-confirm the actual current Alembic head. The plan observed head `061` and proposed Installments migrations beginning at `062`. Do not blindly assume this is still true. If head is still `061`, preserve the approved sequence. If repository head has moved, STOP and report the conflict rather than generating colliding migration numbers. Migration tasks must cover the planned tables, indexes, checks, FKs and partial unique indexes. Preserve: additive-only migration policy, working downgrade(), RESTRICT semantics, tenant isolation, partial unique one-contract-per-obligation enforcement, idempotency uniqueness, permission backfill where required. Do NOT put application-code imports inside Alembic migrations. Follow existing SQL/backfill precedent.

============================================================
8. PERMISSION / RBAC TASKS
============================================================

Generate explicit tasks for the complete Installments permission catalogue defined by plan/spec. Include the approved `installments.contract.cure` permission. Tasks must cover: constants, permission checks, default/system-role mappings, migration/backfill for existing companies where required, API/service enforcement, frontend action visibility, tests. Do not assume updating permission constants automatically updates existing tenants. Use the repository's CRM permission-backfill precedent. Custom/non-system roles must not be silently granted new permissions unless explicitly required by the approved design. Maker-checker must be enforced symmetrically for approve and reject, and tested independently.

============================================================
9. ENTITLEMENT / SERVICING CONTINUITY
============================================================

Do NOT copy CRM's router-level module-disable dependency. Installments has operation-sensitive entitlement semantics. Tasks must implement the approved `InstallmentAccessPolicy` operation classes, including ORIGINATION, SERVICING, READ, ADMIN. The entitlement-disabled state must preserve servicing continuity according to spec. Disabling Installments must not make existing financial obligations impossible to service. Entitlement checks belong at the approved service-method granularity. Tenant suspension remains the platform/global responsibility and must not be duplicated inside Installments.

============================================================
10. CONTRACT LIFECYCLE
============================================================

Generate tasks around explicit named business operations. Do NOT introduce a public generic `set_status()`/`update_status()` or equivalent. Preserve the approved lifecycle and transition guard. `REJECTED` is NOT a persisted contract status. Reject must: PENDING_APPROVAL → DRAFT while recording an audited REJECTED action. Preserve distinct business operations for: submit, approve, reject, activate, cancel, mark defaulted, cure, complete, write-off. Maker-checker must apply to both approve and reject.

============================================================
11. AUTHORITATIVE COMPLETION GUARD
============================================================

Generate explicit tasks for `InstallmentOutstandingService.assert_zero_outstanding()`. Completion must not rely only on schedule-line outstanding. Before ANY path transitions a contract to COMPLETED, it must check authoritative obligations including schedule outstanding and open Installments-created late-charge ARTransactions. Accounting remains authoritative for late-charge AR outstanding. Apply the guard to: normal collection completion, early settlement, DEFAULTED → COMPLETED payoff. Frontend/dashboard/detail outstanding figures must ultimately agree with the same authoritative sources.

============================================================
12. SCHEDULE ENGINE
============================================================

Treat ScheduleEngine as a pure domain component. Tasks must separately cover: frequency/date calculations, month-end handling, leap-year behavior, first-due-date policy, Decimal precision, ROUND_HALF_UP/default rounding policy, final-installment residual absorption, exact contractual-total reconciliation, degenerate schedule rejection, deterministic quote/authoritative generation parity, schedule versioning. Unit tests for ScheduleEngine should be created alongside/before persistence integration. Do not mix DB/HTTP behavior into the pure engine.

============================================================
13. IDEMPOTENCY
============================================================

Phase 5.5 is a HARD prerequisite for later high-risk commands. Generate tasks for the approved module-local idempotency primitive. Preserve IN_PROGRESS → COMPLETED. Do NOT persist FAILED as the normal failure outcome. Failed business operations must roll back the idempotency reservation so the key becomes retryable. Use the approved race-safe PostgreSQL strategy from plan.md. Do not regress to an unsafe check → insert → catch IntegrityError pattern that leaves the active transaction aborted. Generate tests for: same key + same request, same key + conflicting request, concurrent duplicate requests, retry after rolled-back failure, tenant isolation, operation isolation.

============================================================
14. CONCURRENCY
============================================================

Encode the plan's mixed concurrency strategy. Use SELECT ... FOR UPDATE where the plan requires serialization for money-mutating operations. Use optimistic version checks where the plan specifies discrete lifecycle approvals. Generate real PostgreSQL concurrency tests for critical races. At minimum cover: duplicate contract creation, simultaneous collections, collection vs late charge, collection vs settlement, concurrent lifecycle transition, duplicate idempotency-key submission. Do not treat SQLite-style unit tests as sufficient proof for PostgreSQL locking/partial-index behavior.

============================================================
15. LATE CHARGES
============================================================

Late charges are financial receivables. Do not implement them as GL-only postings. Tasks must preserve the corrected design: Installments late-charge metadata + Accounting ARTransaction + GL posting + CustomerLedger recomputation + audit/outbox as one coordinated transaction. The resulting Accounting ARTransaction must remain payment-allocatable through Accounting's existing allocation machinery. Late-charge waiver must reverse Accounting truth through the approved Accounting interface and preserve Installments audit/history.

============================================================
16. WRITE-OFF
============================================================

Treat write-off as a particularly sensitive implementation area. The repository inspection found the existing confirm_write_off() path contains multiple commit boundaries. Do NOT reuse that eager-commit shape for Installments. Generate Phase-6 prerequisite tasks for staged/finalized write-off behavior and corresponding regression tests before the Installments write-off lifecycle task. Write-off must atomically coordinate: Accounting GL, AR state, ledger state, InstallmentContract WRITTEN_OFF transition, Installments audit, outbox event.

============================================================
17. EVENTS / OUTBOX
============================================================

Installments must use the transactional outbox approved in plan.md. Do not replace it with the sibling modules' non-durable in-process EventBus for Installments-owned events. Generate explicit event/outbox tasks for relevant lifecycle/financial events. Event creation must occur in the same transaction as the associated business mutation. Sales-originated correction events may still be consumed through Sales' existing mechanism as documented in plan.md; do not redesign Sales during this Epic.

============================================================
18. TENANT / SECURITY BOUNDARIES
============================================================

Every Installments data path must remain company-scoped. Generate explicit tasks/tests for: repository company_id scoping, IDOR resistance, cross-tenant IDs, cross-tenant idempotency keys, tenant suspension, permission denial, entitlement denial, Platform Admin isolation, SupportAccessGrant boundary. Platform Admin must NEVER gain Installments business-record access merely because it governs the Installments entitlement. Preserve the structural boundary: platform_admin must not import Installments repositories/services to read tenant business data.

============================================================
19. FRONTEND
============================================================

Follow current modern frontend conventions, not legacy patterns. Use: Next.js App Router, TanStack Query, existing data-state components, existing permission patterns, existing API error classification conventions, stacked-section detail pages. Do NOT invent a Tabs-based UI if the repository still has no Tabs design-system precedent. Generate separate frontend tasks for: navigation/module entry, dashboard, contract list, contract detail, quote/creation, approval/rejection, schedule, collections, reversal, settlement, delinquency/late charges, rescheduling, configuration, plan templates, reports/documents, permission-gated actions, entitlement/service-only state, error/loading/empty states, frontend tests. Frontend task ordering must follow backend API availability.

============================================================
20. API CONTRACT
============================================================

Treat specs/010-installments/contracts/installments-api.yaml as authoritative for the planned route surface. Generate endpoint tasks in logical groups rather than one giant router task. Every command endpoint must preserve: authentication, tenant resolution, entitlement policy, RBAC, validation, service call, standard response envelope, domain-error mapping, audit where required, idempotency where required. Do not expose generic lifecycle mutation endpoints. Use command-style endpoints defined by the contract.

============================================================
21. TESTING MUST BE FIRST-CLASS TASK WORK
============================================================

Do NOT put all testing into Phase 15. Each implementation phase must contain its own appropriate tests. Then Phase 15 provides full cross-module/E2E/regression closure. Generate tasks for: Unit (schedule math, allocation policy, lifecycle transitions, entitlement classification, outstanding guard, settlement calculations, delinquency rules); Repository (tenant scoping, partial unique indexes, schedule version persistence, append-only behavior, idempotency uniqueness); Service/integration (Accounting staged/finalize APIs, collection, activation/down payment, late charge, waiver, settlement, reversal, cancellation, write-off, fiscal-period failure propagation); Security (RBAC, maker-checker, tenant isolation, IDOR, entitlement, suspension, Platform Admin/support boundary); Concurrency (real PostgreSQL race tests); Idempotency (retry and concurrent duplicate behavior); Frontend (query/mutation behavior, disabled state, permissions, forms, error states); E2E (core contract lifecycle, down-payment activation, partial collection, multi-installment collection, overpayment/advance behavior, delinquency, late charge + payment, settlement, default/cure, write-off, reversal/cancellation, entitlement-disabled servicing continuity).

============================================================
22. FAILURE-INJECTION / ATOMICITY TESTS — MANDATORY
============================================================

Because plan.md's correction passes centered on transaction ownership, create explicit failure-injection tests. For every cross-module money-mutating workflow, prove that failure before the final commit does not leave partial durable state. At minimum test atomicity for: activation + down payment, collection, late-charge creation, late-charge waiver, settlement, write-off. For reversal/cancellation, test the exact approved staging-order/recovery semantics rather than falsely asserting a single-commit implementation if the underlying Accounting method remains multi-commit. Tests should verify relevant combinations of: GL state, AR state, Payment state, allocation state, CustomerLedger, Installments metadata, contract lifecycle state, audit rows, outbox rows, idempotency state. This is a release-critical test family, not optional hardening.

============================================================
23. MIGRATION / PERMISSION / MODEL ORDERING
============================================================

Tasks must be ordered so an implementation agent never references a table before its migration/model exists, a permission before it is registered/backfilled, a service before its dependency exists, an Accounting staged API before it is implemented, an endpoint before its service behavior exists, a frontend mutation before its backend endpoint exists. Make dependency order executable, not merely descriptive.

============================================================
24. TRACEABILITY
============================================================

Maintain clear traceability from tasks to requirements. At minimum every major task/group should reference applicable FR-INST-*, BR-INST-*, scenarios, plan section, where that materially improves implementation safety. At the end of tasks.md include a traceability/coverage section proving that every required FR/BR/scenario has at least one implementation or verification task. Do not duplicate hundreds of references unnecessarily on trivial subtasks; keep traceability useful.

============================================================
25. TASK FORMAT
============================================================

Use the repository's existing SpecKit task format if present. Every executable task must have a stable sequential task ID: T001, T002, T003, ... Preserve globally increasing numbering across phases. Use [P] only where tasks are genuinely safe to execute in parallel. Do NOT mark tasks parallel merely because they are in the same phase. Two tasks are NOT parallel if they modify the same critical file, depend on the same unfinished API, depend on a migration/model not yet created, participate in the same transaction contract, or depend on an earlier test proving architecture correctness. Where useful include Depends on: Txxx or equivalent explicit dependency notation.

============================================================
26. PHASE EXIT GATES
============================================================

At the end of every phase add a concise verification gate. Later phases must not begin until their hard prerequisite gate passes. Especially enforce: Phase 5.5 gate → before idempotent financial commands. Phase 6 gate → before Collections/Delinquency/Settlement/write-off dependent work.

============================================================
27. SCOPE CONTROL
============================================================

Do NOT add unrelated platform refactors. Specifically do not turn this Epic into: a global UnitOfWork rewrite, a global Money value-object migration, a generic platform idempotency framework, a Branch module implementation, a Sales architecture rewrite, an Accounting architecture rewrite beyond the approved coordinated extensions, a CRM rewrite, a new microservice, a new database, a message-broker project, a PDF-generation infrastructure project, an AI implementation project. Future AI readiness remains architectural readiness only.

============================================================
28. BACKWARD COMPATIBILITY
============================================================

Accounting modifications are shared-platform changes. For every Accounting-side modification generate regression tasks proving existing callers continue to work. Existing APIs should remain available unless the approved plan explicitly requires otherwise. The staged APIs are primarily additive extraction/refactoring around existing behavior. Existing Accounting, Sales, CRM, Platform Admin and Users/Roles regression suites must remain green.

============================================================
29. IMPLEMENTATION AGENT SAFETY
============================================================

Write tasks so /sp.implement can execute them without needing to rediscover architecture. A task should never force the implementation agent to decide: who owns financial truth, who commits, whether a lifecycle transition is legal, whether REJECTED is a state, whether entitlement blocks servicing, whether late charge belongs in AR, whether schedule history is mutable, whether Platform Admin may inspect Installments data. Those decisions are already made. tasks.md must encode them.

============================================================
30. FINAL SELF-AUDIT BEFORE WRITING tasks.md
============================================================

Before finalizing, perform an internal task-graph audit. Verify: A. Dependency completeness (no task consumes an artifact/API before the task creating it). B. Accounting commit ownership (every workflow follows the exact approved commit strategy). C. No shadow financial truth. D. Lifecycle completeness (every legal transition has implementation + tests; illegal transitions have tests). E. Entitlement continuity. F. Tenant security. G. Idempotency. H. Concurrency (real PostgreSQL coverage). I. Audit (fail-closed). J. Outbox (transactionally persisted). K. Permissions (registered, seeded, backfilled, tested). L. Frontend (backend support before frontend work). M. Traceability (every mandatory FR-INST/BR-INST/scenario covered). If any mandatory requirement cannot be mapped to an implementation or verification task, do NOT silently omit it — fix the task graph before finalizing.

============================================================
31. REQUIRED FINAL OUTPUT / REPORT
============================================================

Create specs/010-installments/tasks.md. Then report: (1) tasks.md path, (2) total task count, (3) task count per phase, (4) [P] parallel task count, (5) hard dependency gates identified, (6) Phase 5.5 idempotency prerequisite confirmation, (7) Phase 6 Accounting prerequisite task IDs, (8) Accounting staged/finalize APIs covered, (9) migration range planned after re-verifying current head, (10) permission/backfill tasks, (11) concurrency test tasks, (12) atomicity/failure-injection test tasks, (13) security/tenant-isolation tasks, (14) frontend task groups, (15) E2E/regression tasks, (16) FR-INST coverage status, (17) BR-INST coverage status, (18) Scenario coverage status, (19) unresolved blockers if any, (20) final readiness status for /sp.implement.

FINAL STOP CONDITION: After generating and validating tasks.md, STOP. Do NOT execute /sp.implement, write application code, create migrations, modify models/services/routes/frontend, or run implementation tasks. The expected final status, only if the complete dependency/traceability audit passes, is: READY FOR /sp.implement

(Followed by the standard `/sp.tasks` command's own Outline/Task-Generation-Rules instructions specifying: run `check-prerequisites.sh --json`; load plan.md/spec.md/data-model.md/contracts/research.md; the strict checklist format `- [ ] [TaskID] [P?] [Story?] Description with file path`; organization by user story from spec.md as the template's own default; and a mandatory PHR-creation instruction to close out the exchange.)

## Response snapshot

Ran `check-prerequisites.sh --json` (confirmed `AVAILABLE_DOCS`: research.md, data-model.md, contracts/, quickstart.md). Re-verified the current Alembic migration head via `ls backend/migrations/versions/ | sort | tail`: still `061_platform_support_access.py` — the plan's proposed `062`–`071` range is confirmed valid with no renumbering required. Read `.specify/templates/tasks-template.md` and found its default organization is by spec.md user story (US1/US2/US3 labels) — determined that the user's own 31-section instruction set explicitly and repeatedly overrides this default for this specific epic ("Do NOT flatten these into an arbitrary checklist... tasks.md must visibly preserve phase boundaries and dependency order," §3), since plan.md's 15-phase sequence itself encodes critical, non-negotiable dependency gates (Phase 5.5 before any idempotent command, Phase 6 before Phases 7–10) that a user-story reorganization would obscure or break. Resolved this by using `plan.md`'s phase structure as the primary organizing axis while still cross-referencing spec.md's user stories (US-1..US-8) and FR-INST-*/BR-INST-*/Scenario IDs inline for traceability, and preserving the required checklist format (`- [ ] TXXX [P?] Description with file path`) exactly.

Generated `specs/010-installments/tasks.md` — 256 tasks (T001–T256) across 17 phase blocks (Phase 0 "Database Schema (Migrations)" inserted ahead of Phase 1 specifically to guarantee one valid, linear Alembic `down_revision` chain matching plan.md's exact `062→071` numbering, since spreading migrations across their "logically first needed" phase would have required either re-numbering mid-sequence or violating the true chronological creation order the down_revision chain depends on — documented as the resolution to this ordering tension rather than silently picking one without explanation). Phase 0 covers all 10 planned migrations plus a bidirectional upgrade/downgrade verification task. Phase 6 ("Accounting Integration — CRITICAL HARD GATE") is the largest single-purpose block: 24 tasks split into five sub-groups — 6.1 `AccountsReceivableService` staged/finalize extensions (`stage_adjustment`/`finalize_adjustment`/`reverse_adjustment`/`stage_write_off`/`finalize_write_off`, with `adjust_receivable()`/`confirm_write_off()` rewritten as thin backward-compatible wrappers), 6.2 `PaymentService`+`AllocationEngine` staged/finalize extensions (`stage_customer_payment`/`finalize_customer_payment`, `stage_allocation`/`finalize_allocation`), 6.3 `AccountingIntegrationGateway`+`InstallmentOutstandingService`, 6.4 four backward-compatibility regression tasks plus a full-existing-Accounting-suite green-run task, 6.5 four forced-failure atomicity tests (late charge, collection, write-off, fiscal-period propagation) — each task's file path, exact method signature, and "no commit anywhere in this method" constraint lifted directly from plan.md §12.3's already-corrected design, not re-derived. Explicitly did **not** generate any staged-version task for `reallocate_payment()`/`cancel_payment()`, per the correction's own instruction — instead generated T123/T133/T165 implementing and testing the staging-order discipline (stage Installments' rows first, call the unmodified Accounting method last) and the documented intermediate-state/idempotency-resume behavior.

Threaded the authoritative completion guard (`InstallmentOutstandingService.assert_zero_outstanding()`, T108) through every completion path (T121 collection, T153 settlement, and — since `DEFAULTED→COMPLETED` shares the same `complete()` method, T122 — automatically) with three dedicated Completion-Guard tests (A/B/C, T161–T163) plus a fourth concurrency test (T151) proving the collection/late-charge race is serialized by the same `FOR UPDATE` lock. Wove testing into every phase as first-class work (not deferred to Phase 15) per explicit instruction — every phase from 0 through 14 contains its own unit/repository/service/security/concurrency tests as appropriate, with Phase 15 reserved for cross-module/E2E/full-regression closure only (19 tasks: 12 Playwright scenario specs matching Scenarios A–L, 4 regression-suite-green tasks covering Installments/Accounting/Sales-CRM-PlatformAdmin-UsersRoles/frontend, a Sales-event-subscription integration test for Scenario H, and a final bidirectional migration re-verification). Generated explicit permission/RBAC tasks (T015, T016 for catalogue+per-role seeding via `constants.py`, T010 for the mandatory existing-tenant backfill migration mirroring `056_crm_permission_backfill.py` exactly) and confirmed `installments.contract.cure`'s permission-isolation from `collection.create` has its own dedicated regression test (T178). Generated the full frontend task group (T209–T230, 22 tasks) with every mutation-capable page/hook explicitly `Depends on:` its backend endpoint task, and the entitlement-disabled-UI task (T227) explicitly cross-referencing the CRM `apiErrors.ts`/`StateBanner` precedent rather than inventing new UI infrastructure.

Ran the required internal task-graph self-audit (plan.md/user-instruction §30's 13-point A–M checklist) via direct review of the generated dependency chains — confirmed no task consumes an artifact before its creating task, every Accounting workflow follows the corrected commit strategy, no shadow financial truth is introduced anywhere, every legal/illegal lifecycle transition has both implementation and test coverage, entitlement continuity is proven (T188–T190), tenant security is proven (T192–T198), idempotency/concurrency have dedicated real-Postgres tests (T089–T093, T231–T237), audit is threaded everywhere (T038, T184), outbox events are staged in-transaction throughout, permissions are registered/seeded/backfilled/tested (T015/T016/T010/T196), frontend strictly follows backend availability (verified via the `Depends on:` chain), and every FR-INST group/BR-INST rule/Scenario/SC has at least one mapped task in the closing traceability tables. Verified via grep: 256 unique, non-duplicated, globally sequential task IDs (T001–T256); 139 tasks marked `[P]`; per-phase counts sum correctly to 256.

## Outcome

- ✅ Impact: Epic 10 now has a complete, dependency-correct, implementation-ready `tasks.md` that an implementation agent can execute without rediscovering any of the architecture, commit-ownership, or entitlement decisions already settled across `spec.md`/`plan.md`'s three correction passes.
- 🧪 Tests: none implemented (task-generation-only phase, per explicit stop condition) — 256 tasks include ~100+ dedicated test tasks spanning unit/repository/service/security/concurrency/idempotency/atomicity/E2E layers, woven into every phase.
- 📁 Files: `specs/010-installments/tasks.md` created; this PHR.
- 🔁 Next prompts: `/sp.implement` to begin executing tasks in order, starting with Phase 0's migration block.
- 🧠 Reflection: The Alembic `down_revision` chain constraint (a real, mechanical Git/Alembic fact, not a design preference) was the one place this task-generation pass had to make an explicit organizational judgment call beyond directly transcribing `plan.md`'s already-settled architecture — resolved by grouping all 10 migrations into a new Phase 0 rather than silently spreading them across their "logically first needed" phases, which would have either broken the chain or required silent renumbering.

## Evaluation notes (flywheel)

- Failure modes observed: none in this pass's own execution.
- Graders run and results (PASS/FAIL): N/A — task-generation-only phase, no automated grading harness invoked.
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): When `/sp.implement` begins executing Phase 0, confirm the actual Alembic head one more time immediately before creating migration T001 — a meaningful amount of real time may elapse between task generation and execution, and another change could theoretically land on `main` in the interim.
