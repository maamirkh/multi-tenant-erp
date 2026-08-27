---
id: 0020
title: Epic 10 Phase 7 Collections
stage: green
date: 2026-08-27
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: /sp.implement
labels: [installments, epic-10, phase-7, collections, allocation, idempotency, atomicity, concurrency, postgresql]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/installments/models/allocation_reference.py
 - backend/modules/installments/models/__init__.py
 - backend/modules/installments/repositories/allocation_reference.py
 - backend/modules/installments/services/allocation_policy.py
 - backend/modules/installments/services/collection_service.py
 - backend/modules/installments/services/contract_service.py
 - backend/modules/installments/services/accounting_gateway.py
 - backend/modules/installments/services/outstanding_service.py
 - backend/modules/installments/schemas/collection.py
 - backend/modules/installments/schemas/schedule.py
 - backend/modules/installments/exceptions.py
 - backend/modules/installments/router.py
 - backend/modules/installments/dependencies.py
 - backend/tests/unit/modules/installments/test_allocation_policy.py
 - backend/tests/integration/api/v1/installments/conftest.py
 - backend/tests/integration/api/v1/installments/test_activation_service.py
 - backend/tests/integration/api/v1/installments/test_collection_service.py
 - backend/tests/integration/api/v1/installments/test_collection_completion.py
 - backend/tests/integration/api/v1/installments/test_reversal_service.py
 - backend/tests/integration/api/v1/installments/test_reversal_intermediate_state.py
 - backend/tests/integration/api/v1/installments/test_collection_no_duplication.py
 - backend/tests/integration/api/v1/installments/test_collection_atomicity.py
 - backend/tests/integration/api/v1/installments/test_concurrent_collections.py
 - backend/tests/integration/api/v1/installments/test_schedule_read.py
 - specs/010-installments/tasks.md
tests:
 - backend/tests/unit/modules/installments/test_allocation_policy.py (pure, no DB) — 8 passed
 - backend/tests/integration/api/v1/installments/test_activation_service.py (real Postgres) — 3 passed
 - backend/tests/integration/api/v1/installments/test_collection_service.py (real Postgres) — 6 passed
 - backend/tests/integration/api/v1/installments/test_collection_completion.py (real Postgres) — 3 passed
 - backend/tests/integration/api/v1/installments/test_reversal_service.py (real Postgres) — 3 passed
 - backend/tests/integration/api/v1/installments/test_reversal_intermediate_state.py (real Postgres) — 2 passed
 - backend/tests/integration/api/v1/installments/test_collection_no_duplication.py (real Postgres) — 2 passed
 - backend/tests/integration/api/v1/installments/test_collection_atomicity.py (real Postgres, forced-failure Layer B) — 2 passed
 - backend/tests/integration/api/v1/installments/test_concurrent_collections.py (real Postgres, two-session race) — 1 passed
 - backend/tests/integration/api/v1/installments/test_schedule_read.py (real Postgres) — 2 passed
 - Full Installments regression, Phases 0-7 (unit+repository+API+security+performance) — 191 passed, 0 failed
 - Full Accounting regression (unit+API+repositories+security) — 583 passed, 0 failed (zero regressions from Phase 7's touches to outstanding_service.py/accounting_gateway.py)
 - ruff check / black --check — all touched files clean
tests_run: true
---

## Prompt

# Epic 10 — Installments
# MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT

Implement, verify, audit, and close ONLY the following phase of Epic 10.

Phase Number: `7`
Phase Name: `Collections`
Task Range: `T118 to T137`

Feature Branch: 010-installments

[Full 47-section master implementation and closure prompt, identical in structure to Phases 0–6: primary objective, strict phase scope, authoritative sources, branch safety, pre-implementation task audit, repository-reality check, per-task Inspect→Implement→Focused-Test→Acceptance-Proof→Negative-Path-Proof→Dependency-Recheck rule, architecture freeze (Accounting sole source of truth, no shadow balances, AccountingIntegrationGateway as the only crossing point, immutable schedule history, no generic set_status(), REJECTED never persisted, operation-sensitive entitlement, Platform/Support boundary, no AI), financial transaction hard rule, Accounting source-of-truth rule, idempotency hard rule, Phase 5.5 hard gate, Phase 6 Accounting hard gate, reversal/cancellation special rule, completion guard, late-charge rule (N/A this phase), write-off rule (N/A), concurrency rule, audit fail-closed rule, transactional outbox rule, tenant isolation audit, RBAC/maker-checker, entitlement adversarial testing (deferred to Phase 11 per architecture), Platform/Support boundary, database/migration hard rules (no new migration needed — reuses migration 066), API contract lock, data-model↔implementation audit, frontend rule (N/A, backend-only phase), testing pyramid, failure-injection/atomicity proof, pre-existing failure policy, real PostgreSQL verification, live HTTP/browser verification (N/A — router not yet mounted per its own docstring, T190/Phase 11), requirement traceability review, self-review after implementation, adversarial completeness pass, full diff review, task checkbox rule, phase exit condition, hard gate rule, regression verification, no-correction-pass standard, PHR/implementation history, pre-commit check, commit policy, post-commit verification, and the Required Final Report sections A–S ending in an exact verdict, plus the standing PHR-creation instruction.]

## Response snapshot

Implemented T118–T137 (Phase 7 — Collections) in full:

**T118–T120**: `InstallmentAllocationReference` model (plain `Base`, matching migration 066 exactly — no new migration needed) + append-only repository (`create`, `list_for_contract`, `list_for_schedule_line`, `get_net_allocated_by_line`, `get_by_payment_id`) + pure `InstallmentAllocationPolicy.allocate_oldest_first()` (greedy, oldest-due-date-first, raises `ValueError` on over-amount/non-positive input — mirrors `ScheduleEngine`'s pure-function convention).

**T121/T123**: New `InstallmentCollectionService` (`collection_service.py`) — `record_collection()` and `reverse_collection()`, both following the idempotency-reservation → `FOR UPDATE` lock → business computation → Accounting staged mutation → Installments rows staged → Accounting finalize-last sequence (plan.md §21). `record_collection()` computes live per-line outstanding via the new allocation-reference repository, guards over-collection (`InstallmentOverCollectionError`, BR-INST-011) before calling the policy, and auto-completes the contract at zero outstanding (catching `InstallmentOutstandingBalanceRemainsError` specifically, not a bare except, so a future Phase-8 late-charge block only withholds completion, never the collection itself). `reverse_collection()` derives its owning contract from the `InstallmentAllocationReference` rows themselves (never an extra, undeclared request parameter — kept the OpenAPI contract's single-path-parameter shape intact) and stages reversal rows before calling the unmodified `reallocate_payment()`.

**T122/T124**: `InstallmentContractService.complete()` (flush-only internal primitive) and `activate()` (idempotency-protected: live eligibility re-check, conditional down-payment posting via `record_down_payment()`, `ScheduleEngine.generate()` + persistence, BR-INST-005 reconciliation re-verification, status transition — commits via the Accounting finalize call when a down payment exists, or an explicit `db.commit()` when it doesn't, since no Accounting call exists to be the commit point in that branch).

**T125–T129**: Pydantic schemas (`InstallmentCollectionCreate/ResultRead/ReverseRequest`, `InstallmentScheduleRead/LineRead`) and four router endpoints (activate, collections POST, reverse POST, schedule GET x2), each enforcing its documented permission inline exactly matching `contracts/installments-api.yaml`.

**T130–T137**: Full test suite — pure-function allocation-policy unit tests; service tests for exact/partial/multi/advance collection scenarios, auto-completion, reversal (BR-INST-017: original rows never mutated), reversal/cancellation intermediate-state resume (`reallocate_payment()` then `cancel_payment()` as two separate calls — the honest limitation plan.md §12.3.2 documents), no-duplication (exactly one `Payment`/`JournalEntry` per collection, the invoice `ARTransaction` never duplicated across collections), a real-Postgres forced-failure Layer-B atomicity test (replicating `record_collection()`'s exact staged sequence, proving `Payment`/`PaymentAllocationLine`/`InstallmentAllocationReference`/`InstallmentAuditLog`/outbox/idempotency-key are all simultaneously absent post-rollback and the key is retry-available, not stranded `IN_PROGRESS`), and a real two-session concurrency test proving the `FOR UPDATE` lock serializes two simultaneous full-amount collections against the same last-remaining installment (exactly one succeeds, BR-INST-011 never violated).

**Genuine defect found and fixed during adversarial testing**: `InstallmentOutstandingService.assert_zero_outstanding()` (built in Phase 6 as a documented "correct-by-omission" placeholder, summing raw `scheduled_amount` since `InstallmentAllocationReference` didn't exist yet) was never actually extended once T118/T119 landed — a full-payoff collection never auto-completed the contract, because the check always saw the raw un-netted schedule total as still outstanding. Applied the exact Phase-7 extension the Phase 6 PHR had already documented as the expected follow-up: subtract net allocated amounts (non-reversal minus reversal) per line via the new repository. Fixed three test assertions in `test_collection_service.py` that had encoded the pre-fix (incorrect) "never completes" behavior.

**Design decisions made, not contradictions requiring a STOP**: (1) `record_collection()`/`activate()` accept optional `bank_account_id`/`cash_account_id` keyword parameters beyond tasks.md's abbreviated signature list — Accounting's frozen `stage_customer_payment()` genuinely requires one of these and no tenant-level default deposit account exists anywhere in the system to substitute; this is exposing an already-approved Phase 6 method's real parameter, not new architecture. (2) `reverse_collection()` uses `full_cancellation=False` (only `reallocate_payment()`, never `cancel_payment()`) — matches T123's literal text exactly; T133's `cancel_payment()`/`full_cancellation=True` intermediate-state property is proven directly against the Accounting layer instead, since no Phase 7 task actually wires that branch through `InstallmentCollectionService`. (3) Reversal of a collection that completed its contract is out of scope — `_LEGAL_TRANSITIONS["COMPLETED"]` is terminal by design (frozen since Phase 5); tests deliberately use partial collections so contracts stay `ACTIVE` throughout reversal testing, rather than inventing un-completion logic no task requested.

## Outcome

- ✅ Impact: Phase 7's Exit Gate is satisfied — a contract can be activated with a down payment, collected against with every payment shape (exact/partial/multi/advance), reversed with correct staging-order atomicity, and auto-completes at zero outstanding, all proven under real Postgres concurrency, all traced through `InstallmentAllocationReference` back to authoritative Accounting records.
- 🧪 Tests: 32 new Phase 7 tests passing (8 pure-function unit + 24 real-Postgres integration/service/atomicity/concurrency). Full Installments regression 191/191. Full Accounting regression 583/583 (zero regressions from this phase's touches to `outstanding_service.py`/`accounting_gateway.py`).
- 📁 Files: 5 new service/model/repository files, 9 modified existing Installments files, 11 new test files, 1 modified test file (assertion corrections), tasks.md.
- 🔁 Next prompts: Phase 8 (Delinquency) may now begin — do not start automatically per the master prompt's hard-stop instruction.
- 🧠 Reflection: The `InstallmentOutstandingService` gap is a direct, expected consequence of the documented Phase-6-to-Phase-7 extension point working as designed — the PHR that introduced the placeholder explicitly named this exact follow-up, and writing the completion test immediately surfaced it rather than letting it ship silently. The lesson from Phase 6's `get_or_create_ledger()` incident (a too-lenient assertion masking a defect) generalized here too: writing the dedicated completion test with a concrete full-payoff scenario, rather than only checking `record_collection()`'s narrower per-call postconditions, is what caught this.

## Evaluation notes (flywheel)

- Failure modes observed: One genuine defect (stale outstanding-service extension point) caught by writing the completion-focused test; several test-authoring corrections (wrong assumed status strings — "POSTED" vs the real "ALLOCATED" `AllocationEngine` produces for an empty allocation list; an invented undeclared query parameter for the reversal endpoint, caught by re-checking the OpenAPI contract before finalizing the router).
- Graders run and results (PASS/FAIL): Full Installments regression PASS (191/191); full Accounting regression PASS (583/583); Phase 7 Exit Gate clauses individually verified PASS against dedicated tests.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): When adding a new gateway/service method whose downstream extension point was explicitly documented in a prior phase's PHR, grep for that documented TODO/extension-point language before considering the current phase's related task "done" — it is easy to build the new consumer (T121) without noticing the placeholder it depends on (T108) was never actually upgraded.

---

## Required Final Report

**A. PHASE**: 7 — Collections, tasks T118–T137.

**B. TASK COMPLETION**: All 20 tasks (T118–T137) COMPLETE with evidence — see per-task test files listed above; every task's acceptance criteria individually exercised by at least one passing real-Postgres test.

**C. FILES**: 5 created (model, repository, allocation_policy service, collection_service, 11 test files), 9 modified (dependencies, exceptions, models/__init__, router, schemas/schedule, accounting_gateway, contract_service, outstanding_service, tasks.md).

**D. DATABASE**: No new migration — reused migration 066 (`installment_allocation_references`, already created in Phase 0). Alembic head unchanged at 071. `InstallmentAllocationReference` ORM model verified column-for-column against migration 066's real schema.

**E. TESTS**: 32 new Phase 7 tests, 32 passed, 0 failed, 0 skipped. Full Installments regression: 191 passed, 0 failed. Full Accounting regression: 583 passed, 0 failed. No non-zero-failure suite anywhere in this phase's evidence.

**F. ACCOUNTING/FINANCIAL INTEGRITY**: `AccountingIntegrationGateway.record_collection()`/`record_down_payment()`/`reverse_payment()` (Phase 6, unmodified) plus one new read-only method (`get_invoice_ar_transaction_id()`). Transaction ownership: Installments' service methods own every commit (either via Accounting's `finalize_*()` call or an explicit `db.commit()` in the no-Accounting-call branch) — verified zero hidden commits via direct source grep of every new method. Source-of-truth verification: `test_collection_no_duplication.py` proves exactly one `Payment`/`JournalEntry` per collection and the invoice `ARTransaction` is reused, never duplicated. Atomicity/failure-injection: `test_collection_atomicity.py` (Layer B) proves full rollback of `Payment`+`PaymentAllocationLine`+`InstallmentAllocationReference`+`InstallmentAuditLog`+outbox+idempotency-key together.

**G. IDEMPOTENCY**: Commands: `contract.activate`, `collection.create`, `collection.reverse`. Reservation: `InstallmentIdempotencyService.reserve()` (Phase 5.5, unmodified). Replay: proven for `activate()` (`test_activate_is_idempotent_on_replay`) — identical result, zero duplicate schedule version. Rollback/retry: proven in `test_collection_atomicity.py` — forced failure leaves the idempotency key absent (not stranded `IN_PROGRESS`), immediately re-reservable. Concurrency: proven in `test_concurrent_collections.py` — the `FOR UPDATE` lock, not the idempotency mechanism, is what serializes two distinct (differently-keyed) concurrent requests correctly.

**H. SECURITY**: Every new endpoint (`activate`, `collections` POST, `reverse` POST, schedule GET x2) calls `_require_permission()` with its documented code before any business logic — verified by direct grep of `router.py`.

**I. TENANT ISOLATION**: Every new repository query (`allocation_reference.py`, all 4 methods) filters by `company_id`. `reverse_collection()` cannot cross tenants — `get_by_payment_id(company_id, collection_id)` returns empty for a foreign-tenant id, raising `InstallmentReversalNotAllowedError`, never leaking or succeeding.

**J. RBAC/ENTITLEMENT**: RBAC — permission checks present and correct on all 5 endpoints (installments.contract.activate, installments.collection.create, installments.collection.reverse, installments.contract.view x2). Entitlement (`InstallmentAccessPolicy`) — correctly NOT wired in this phase; it is Phase 11's T188, threaded in by T189 (which explicitly depends on T121/T123, confirming this phase precedes and does not need it).

**K. CONTRACT**: All 5 new/verified operations checked against `contracts/installments-api.yaml` — permission, operation-class annotation, idempotency flag, and response status code all match exactly. No declared-but-missing route; no implemented-but-undeclared route (the reversal endpoint's request shape was corrected mid-implementation specifically to avoid inventing an undeclared query parameter).

**L. GATE**: N/A — Phase 7 has no independent hard gate of its own; it depends on and re-verified Phase 5.5 (idempotency, reconfirmed via the replay/rollback tests above) and Phase 6 (Accounting integration, reconfirmed via zero Accounting regressions and the Layer-B atomicity test) rather than introducing a new one.

**M. EXIT CONDITION**: PASS. Evidence: activation-with-down-payment (`test_activate_with_down_payment_posts_to_accounting_and_reduces_outstanding`), every payment shape (`test_collection_service.py`'s 4 scenario tests), reversal with staging-order atomicity (`test_reversal_service.py` + `test_collection_atomicity.py`), auto-completion at zero outstanding (`test_collection_completion.py`), real-Postgres concurrency (`test_concurrent_collections.py`), full Accounting traceability (`test_collection_no_duplication.py`).

**N. DEFECTS DISCOVERED**:
1. Defect: `InstallmentOutstandingService.assert_zero_outstanding()` never subtracted net-allocated amounts, so no collection could ever auto-complete a contract. Cause: Phase 6 left this as a documented, correct-at-the-time placeholder pending Phase 7's `InstallmentAllocationReference`; the Phase 7 extension was never actually applied when T118/T119 landed. Fix: `assert_zero_outstanding()` now subtracts `InstallmentAllocationReferenceRepository.get_net_allocated_by_line()` per line. Verification: `test_collection_completion.py` (3/3 passed) plus re-run of Phase 6's own `test_outstanding_service.py` (3/3 unaffected).
2. Defect (test-authoring only, caught before merge): reversal endpoint initially required an undeclared `contractId` query parameter not in the OpenAPI contract. Cause: designing `reverse_collection()`'s signature before re-checking the contract. Fix: derive the owning contract from `InstallmentAllocationReference` rows instead. Verification: endpoint signature re-checked against `installments-api.yaml`, single path parameter only.

**O. PRE-EXISTING FAILURES**: None encountered this phase — both full regressions (Installments 191/191, Accounting 583/583) were unconditionally green.

**P. SELF-AUDIT**: Architecture — no new infrastructure, no generic set_status(), REJECTED still unpersisted, schedule history still immutable (confirmed no update path added). Dependency — every T118-T137 dependency (T005, T012, T044, T068, T074, T075, T086, T107, T108, T119, T120, T034) verified present and complete before use. Accounting ownership — zero direct writes to any Accounting table; grep-confirmed the gateway imports only `modules.accounting.services`. Transaction/atomicity — zero hidden commits (grep-verified every new method). Idempotency — reservation is the first statement in both `record_collection()`/`reverse_collection()`/`activate()`; no `FAILED` status introduced. Concurrency — `FOR UPDATE` lock used for money-mutating operations (collection, reversal, activation), proven under real Postgres. Security — permission check present at the top of every new endpoint. Tenant isolation — every new query scoped by `company_id`, cross-tenant reversal attempt structurally impossible. Contract — re-verified against `installments-api.yaml` after catching and fixing the undeclared-parameter defect. Data-model — `InstallmentAllocationReference` ORM model checked field-for-field against migration 066. Future-phase leakage — grep-confirmed no `InstallmentLateCharge`/`DueStateCalculator`/`InstallmentAccessPolicy` files exist; `git diff --stat` contains only Phase 7-scoped files plus the pre-existing, untouched `CLAUDE.md` baseline noise.

**Q. GIT**: Commit hash: (see below, post-commit). Branch: `010-installments`. Status: clean except pre-existing `CLAUDE.md`/untracked planning-doc baseline noise (present since before Phase 6, never committed on this branch, confirmed unrelated).

**R. SCOPE CONFIRMATION**: Next phase (8 — Delinquency) NOT started — no `DueStateCalculator`/`InstallmentAgingCalculator`/`InstallmentLateCharge` files exist anywhere. No unauthorized architecture change. No unauthorized migration (0 new migrations; reused existing 066). No unrelated scope expansion beyond the two genuinely necessary smallest-safe-resolution decisions documented above. No AI implementation. Planning documents (spec.md/plan.md/tasks.md) were not redesigned — only tasks.md's own checkboxes were updated with evidence.

**S. FINAL VERDICT**:

PHASE 7 COMPLETE — READY FOR NEXT PHASE
