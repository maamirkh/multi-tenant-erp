---
id: 0024
title: Phase 9 Settlement implementation
stage: green
date: 2026-08-29
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: /sp.implement
labels: ["installments", "settlement", "phase-9", "accounting-integration", "idempotency", "completion-guard"]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/installments/services/settlement_service.py
 - backend/modules/installments/schemas/settlement.py
 - backend/modules/installments/services/collection_service.py
 - backend/modules/installments/services/outstanding_service.py
 - backend/modules/installments/exceptions.py
 - backend/modules/installments/router.py
 - backend/modules/installments/dependencies.py
 - backend/tests/unit/modules/installments/test_settlement_calculation.py
 - backend/tests/integration/api/v1/installments/test_settlement_quote.py
 - backend/tests/integration/api/v1/installments/test_settlement_execution.py
 - backend/tests/integration/api/v1/installments/test_completion_guard.py
 - backend/tests/integration/api/v1/installments/test_cross_tenant_idor.py
 - backend/tests/integration/api/v1/installments/conftest.py
 - specs/010-installments/tasks.md
tests:
 - backend/tests/unit/modules/installments/test_settlement_calculation.py (12 tests)
 - backend/tests/integration/api/v1/installments/test_settlement_quote.py (4 tests)
 - backend/tests/integration/api/v1/installments/test_settlement_execution.py (6 tests)
 - backend/tests/integration/api/v1/installments/test_completion_guard.py (4 tests)
 - backend/tests/integration/api/v1/installments/test_cross_tenant_idor.py (7 tests, 2 new)
 - backend/tests/integration/repositories/installments/test_outstanding_service.py (3 tests, refactor regression check)
 - full module regression: 257 passed (unit/modules/installments + integration/api/v1/installments + integration/repositories/installments)
---

## Prompt

Master Phase Implementation & Closure Prompt for Epic 10 — Installments, Phase 9 (Settlement), Task Range T154–T165, on branch `010-installments`. Full verbatim prompt was the ~900-line "MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT" template covering: strict phase scope, authoritative sources, branch safety, pre-implementation task audit, repository-reality check, architecture freeze (Accounting ownership, Installments ownership, schedule immutability, no generic set_status, entitlement, platform boundary, no AI), financial transaction hard rule, Accounting source-of-truth rule, idempotency hard rule, Phase 5.5/Phase 6 hard gates, completion guard, late-charge/write-off rules, concurrency rule, audit fail-closed rule, transactional outbox rule, tenant isolation audit, RBAC/maker-checker, entitlement adversarial testing, platform/support boundary, database/migration hard rules, API contract lock, data model audit, testing pyramid, failure-injection/atomicity proof, pre-existing failure policy, real PostgreSQL verification, live HTTP verification, requirement traceability, self-review, adversarial completeness pass, full diff review, task checkbox rule, phase exit condition, hard gate rule, regression verification, no-correction-pass standard, PHR requirement, pre-commit check, commit policy, post-commit verification, and the required final report format. Target: implement Phase 9 (`InstallmentSettlementService.generate_quote()`/`execute()`, settlement schemas, settlement endpoints, quote-reproducibility unit tests, quote non-mutating service tests, settlement-execution Scenario F tests, stale-quote rejection tests, and completion-guard Tests A/B/C) to a standard requiring no later correction pass.

## Response snapshot

Read all 9 authoritative sources (constitution, spec, plan, tasks, research, data-model, OpenAPI contract, quickstart, existing repo code) before writing any code. Verified branch (`010-installments`, clean tree) and every T154-T165 dependency (T138, T108, T121, T086, T044, T107, T034, T018) by reading the actual implementation, not trusting checkboxes.

Key design decisions:
1. Added `InstallmentOutstandingService.compute_outstanding_breakdown()` (new `OutstandingBreakdown` dataclass) as the single shared live-read computation of schedule + late-charge outstanding; refactored `assert_zero_outstanding()` to be a thin wrapper over it (byte-identical raise semantics, verified by the pre-existing `test_outstanding_service.py` suite passing unchanged). This gives `InstallmentSettlementService.generate_quote()` a genuinely non-competing, reused source of truth for the quoted amount — no second "what does this contract still owe" computation exists anywhere in the module.
2. Refactored `InstallmentCollectionService.record_collection()` by extracting its post-reservation body into a new `execute_collection_sequence()` method, parametrized by `audit_action`/`outbox_event_type`/`pending_approval_audit_action` and taking an already-reserved `reservation` object rather than reserving its own. `record_collection()` becomes a thin wrapper reserving `operation="collection.create"`. This is the literal mechanism by which `InstallmentSettlementService.execute()` "reuses the exact atomic sequence" (T155) while reserving its own `operation="settlement.execute"` idempotency key — one shared sequence, one atomic commit, no hidden second commit, verified via the full 54/54 (then 257/257) regression passing unchanged after the refactor.
3. `InstallmentSettlementService.execute()` locks the contract itself (`FOR UPDATE`) before computing the live outstanding breakdown, compares it against the client-submitted `quoted_amount`/`quoted_as_of_date` (from the prior `/settlement/quote` call), and raises the new `InstallmentSettlementQuoteStaleError` (409, `SETTLEMENT_QUOTE_STALE`) on mismatch — the mechanism for spec §28's "stale settlement quote" edge case, since no `InstallmentSettlementQuote` persistence entity exists in the approved data model (FR-INST-190/191 only require reproducibility from live state + as_of_date, not a stored quote row).
4. `generate_quote()` is genuinely non-mutating for contract/schedule/Accounting state (no Accounting call, no lock) but still writes the FR-INST-341-required `SETTLEMENT_QUOTED` audit row and commits it — proven by `test_settlement_quote.py`.
5. Added `InstallmentSettlementNotAllowedError` (409) for non-ACTIVE/DEFAULTED contracts or zero-outstanding contracts.
6. New router endpoints `POST /contracts/{id}/settlement/quote` (non-idempotent) and `POST /contracts/{id}/settlement/execute` (idempotency-protected via `Idempotency-Key` header) — verified 1:1 against `installments-api.yaml`'s declared permission (`installments.settlement.execute`), operation class (SERVICING), and response schemas (`StandardResponse<InstallmentSettlementQuote>`/`StandardResponse<InstallmentContract>`).
7. Wrote Completion-Guard Tests A/B/C in `test_completion_guard.py` (open late charge withholds completion; schedule+late-charge both paid completes; schedule paid + late charge validly waived completes) plus an added Test D proving the identical guard also gates `DEFAULTED -> COMPLETED` payoff, matching the Phase 9 exit gate's explicit "settlement, ordinary collection, and defaulted payoff" wording.
8. Extended `test_cross_tenant_idor.py` with 2 new tests (`generate_quote()`/`execute()` cross-tenant IDOR) and `test_settlement_execution.py` with idempotency-payload-mismatch and non-settleable-status negative-path tests, closing gaps the master prompt's adversarial-completeness pass (§35) calls for beyond the literal T154-T165 task list.

Verification: ruff clean on all touched files; mypy shows zero NEW errors (the one collection_service.py:404 hit is a pre-existing unchanged line, confirmed via `git diff` showing no touch to that line); full module regression 257/257 passed (unit + integration/api + integration/repositories, real PostgreSQL, 71-migration chain). `git diff --stat` confirms scope is exactly Phase 9 (no migrations, no future-phase files, no unrelated changes). Committed as a single `feat(010)` commit.

## Outcome

- ✅ Impact: Phase 9 (Settlement) fully implemented — quote generation, settlement execution reusing the collection atomic path, and the authoritative completion guard extended/proven across ordinary collection, defaulted payoff, and (structurally, by construction) settlement.
- 🧪 Tests: 257 passed, 0 failed, 0 skipped (full installments module regression); zero pre-existing-failure carryover needing characterization.
- 📁 Files: 2 new service/schema files, 5 modified module files, 5 new/modified test files, 1 planning doc (tasks.md checkboxes).
- 🔁 Next prompts: Phase 10 (Advanced Lifecycle — reschedule/cancel/default-command/cure/write-off), not started per phase-scope discipline.
- 🧠 Reflection: The literal task wording ("reuses record_collection()'s exact atomic sequence... reserves its own idempotency key... distinct from the collection it wraps") was genuinely ambiguous between "calls record_collection() as a black box" (which would require a second commit, violating the atomicity hard rule) and "reuses the underlying sequence with its own reservation" (single commit). Resolved by re-reading plan.md §21's "exactly one db.commit()" invariant and the master prompt's explicit "search for hidden db.commit() inside called methods" instruction — extracting a shared, reservation-parametrized core method was the only design satisfying both the reuse requirement and the atomicity requirement simultaneously.

## Evaluation notes (flywheel)

- Failure modes observed: None blocking. One test-only bug caught by the run: `Payment.customer_id` doesn't exist (field is `party_id`); fixed before commit by asserting on `company_id` instead, which is the correct/sufficient assertion for the non-mutating-quote test's purpose.
- Graders run and results (PASS/FAIL): ruff PASS (0 errors after 1 auto-fixed import-order issue); mypy PASS (0 new errors, verified against baseline via git diff); pytest PASS (257/257).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a — phase closed per Product Owner instruction to await direction before Phase 10.
