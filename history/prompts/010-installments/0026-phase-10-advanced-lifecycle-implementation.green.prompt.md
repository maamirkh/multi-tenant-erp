---
id: 0026
title: Phase 10 Advanced Lifecycle implementation
stage: green
date: 2026-08-30
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: /sp.implement
labels: ["installments", "phase-10", "reschedule", "cancellation", "default", "cure", "writeoff", "idempotency", "concurrency"]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/installments/services/rescheduling_service.py
 - backend/modules/installments/schemas/lifecycle.py
 - backend/modules/installments/services/contract_service.py
 - backend/modules/installments/exceptions.py
 - backend/modules/installments/router.py
 - backend/modules/installments/dependencies.py
 - backend/tests/integration/api/v1/installments/conftest.py
 - backend/tests/integration/api/v1/installments/test_reschedule.py
 - backend/tests/integration/api/v1/installments/test_cancellation_service.py
 - backend/tests/integration/api/v1/installments/test_cure.py
 - backend/tests/integration/api/v1/installments/test_default_command.py
 - backend/tests/integration/api/v1/installments/test_writeoff_integration.py
 - backend/tests/integration/api/v1/installments/test_writeoff_atomicity.py
 - backend/tests/integration/api/v1/installments/test_defaulted_payoff.py
 - backend/tests/integration/api/v1/installments/test_writeoff_collection_race.py
 - backend/tests/integration/api/v1/installments/test_approve_reject_race.py
 - backend/tests/integration/api/v1/installments/test_cross_tenant_idor.py
 - backend/tests/security/installments/test_cure_permission_isolation.py
 - backend/tests/unit/modules/installments/test_lifecycle_transition_matrix.py
 - specs/010-installments/tasks.md
tests:
 - Phase-10-specific new/modified test files (~45 tests across reschedule, cancel, cure, default, writeoff, races, cross-tenant, permission isolation)
 - full Installments module regression (unit + integration/api + integration/repositories + security): 306 passed, 0 failed, 0 skipped
---

## Prompt

Master Phase Implementation & Closure Prompt for Epic 10 — Installments, Phase 10 (Advanced Lifecycle), Task Range T166–T187, on branch `010-installments`. Same ~900-line master prompt template as prior phases (strict phase scope, architecture freeze, financial transaction hard rule, idempotency hard rule, Phase 5.5/Phase 6 hard gates, concurrency rule, tenant isolation audit, RBAC/maker-checker, API contract lock, adversarial completeness pass, full diff review, phase exit condition, required final report format). Target: implement Phase 10 (`default_command()`, `InstallmentReschedulingService.reschedule()`, complete `cancel()`'s financial-activity branch, `cure()`, `writeoff()`, their 5 endpoints, and all T177–T187 tests) to a standard requiring no later correction pass.

## Response snapshot

Read all 9 authoritative sources and re-verified every T166-T187 dependency (T078, T086, T044, T068/T057, T077, T107, T029, T034, T121/T122, T075/T076, T099) by reading actual implementation, not trusting checkboxes.

Hit three genuine, consequential ambiguities in the approved planning text where multiple defensible designs existed and getting it wrong would require a correction pass — asked the Product Owner directly via AskUserQuestion rather than guessing, per the master prompt's own "STOP and report / do not silently redesign" instruction combined with CLAUDE.md's "Human as Tool Strategy":
1. **Reschedule maker-checker mechanism**: FR-INST-201 requires "the same maker-checker discipline as contract approval" but there is no separate submit/approve workflow for reschedule in the approved data model. Resolved: add an explicit `requested_by` parameter distinct from `actor_id` (the approver/executor) — no new persisted state, no new status.
2. **Cancel's financial-activity scope**: T169 says cancel() delegates to a single `reverse_payment()` call "same shape as T123" (which reverses one caller-supplied payment id), but an ACTIVE contract could have multiple recorded payments (down payment + N collections). Resolved: only the single automatic down payment is reversible via cancel(); a contract with any recorded ordinary collection is blocked with a clear error, directing the caller to reverse those individually or use settlement/default+write-off instead.
3. **How cancel() locates the down payment's Payment id**: `InstallmentContract` has no field storing it (down-payment recording creates no `InstallmentAllocationReference` row), and adding one needs a migration (Epic 10's 062-071 range is closed). Resolved: the caller supplies `payment_id` explicitly in the request body (mirroring `reverse_collection()`'s own "caller supplies the id via the URL" shape) — cancel() rejects with a clear 422 if a down payment exists but no `payment_id` was given.

Implementation: `default_command()` (idempotency reservation → `FOR UPDATE` lock → `mark_defaulted()` primitive → outbox → idempotency completion → single commit, zero Accounting calls, BR-INST-013); `InstallmentReschedulingService.reschedule()` (new file — idempotency → lock → maker-checker → restructuring guard comparing caller-supplied `principal_amount`/`markup_amount`/`installment_count` against the contract's own recorded values → `ScheduleEngine.generate()` for the currently-unpaid remaining lines only, over new due dates → new `InstallmentScheduleVersion` persisted, prior version superseded via direct attribute mutation — mirrors `activate()`'s own idiom for mutating an already-loaded ORM instance, no new repository method needed since `InstallmentScheduleRepository` deliberately has none — → audit/outbox/idempotency staged → single commit); `cancel()`'s financial-activity branch (idempotency → lock → ordinary-collections-block check via `InstallmentAllocationReferenceRepository` → down-payment-without-`payment_id` guard → stages CANCELLED/audit/outbox/idempotency-completion *first*, then `reverse_payment(full_cancellation=False)` *last* — deliberately `full_cancellation=False`, matching `reverse_collection()`'s own choice: `full_cancellation=True` would additionally require the actor to hold Accounting's own `accounting.journal.reverse` SoD permission via `cancel_payment()`, which an Installments-side actor cannot be assumed to hold); `cure()` (policy-gated via `InstallmentConfiguration.cure_enabled`, optimistic-version discrete transition, no idempotency — not one of the 8 high-risk commands, no financial posting); `writeoff()` (idempotency → lock → `AccountingIntegrationGateway.writeoff()`'s `stage_write_off()`/`finalize_write_off()` staged/finalize pair, writing off the contract's originating invoice `ARTransaction`).

Discovered mid-implementation that `cancel()` becoming idempotency-protected (Postgres-only `ON CONFLICT DO NOTHING`) meant its existing SQLite-based unit tests in `test_lifecycle_transition_matrix.py` would break structurally — moved that coverage to a new Postgres-backed `test_cancellation_service.py`, consistent with how `activate()`'s tests already live separately from the SQLite lifecycle-matrix file. Also discovered `stage_write_off()` requires `AccountingConfiguration.default_bad_debt_account_id`, which the shared test fixture (`build_active_contract_with_schedule()`) didn't configure — added a Bad Debt Expense account to the fixture (additive-only; re-verified zero regression across the full suite).

Also found and fixed a real gap from the Phase 9 closure session: T164/T165 (Completion-Guard Tests B/C) had working, passing tests but their `tasks.md` checkboxes were never marked — corrected as part of this session's bookkeeping.

## Outcome

- ✅ Impact: Phase 10 (Advanced Lifecycle) fully implemented — reschedule (versioned, maker-checker, restructuring-guarded), cancellation (free path + down-payment reversal path, ordinary-collections block), the externally-callable default command, policy-gated cure, and staged/finalize write-off, all wired to endpoints matching the OpenAPI contract exactly.
- 🧪 Tests: 306 passed, 0 failed, 0 skipped (full Installments module regression: unit + integration/api + integration/repositories + security), up from 261 pre-Phase-10. All new concurrency tests (writeoff-vs-collection, approve-vs-reject) re-run 3-4× each to rule out flakiness.
- 📁 Files: 2 new service/schema files, 4 modified module files, 11 new test files, 2 modified test files (1 trimmed for the Postgres-dependency move), 1 planning doc.
- 🔁 Next prompts: Phase 11 (Entitlement / Security Hardening), not started per phase-scope discipline.
- 🧠 Reflection: All three clarifying questions this phase shared a root cause — the approved planning text (tasks.md/plan.md/spec.md) correctly named the *shape* of each solution ("same discipline as approval", "same call as T123") but the concrete mechanism was underspecified in a way that had real, divergent implementation consequences (new parameter vs. reused field; single-payment vs. multi-payment scope; caller-supplied vs. server-derived id). Recognizing "this is underspecified in a consequential way" rather than picking the first plausible reading was the main judgment call each time.

## Evaluation notes (flywheel)

- Failure modes observed: One test-only assumption error (expected `Payment.status == "POSTED"` after `reallocate_payment(new_allocation_lines=[])`; actual pre-existing Accounting behavior is `"ALLOCATED"`, since `AllocationEngine.stage_allocation()` unconditionally sets that status even for an empty line list — fixed the test assertion, not the production code, since this is the same pre-existing behavior `reverse_collection()` already relies on unremarked-upon). One missing fixture dependency (`default_bad_debt_account_id`) caught immediately by the first write-off test run.
- Graders run and results (PASS/FAIL): ruff PASS (0 errors across all touched files); mypy PASS (0 new errors — 2 pre-existing `contract_service.py` errors on unrelated, untouched lines confirmed via git diff); pytest PASS (306/306 full module regression + 3-4× repeat runs on both new concurrency tests).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a — phase closed per Product Owner instruction to await direction before Phase 11.
