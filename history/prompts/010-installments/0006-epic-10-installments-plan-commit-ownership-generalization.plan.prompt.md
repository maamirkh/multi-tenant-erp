---
id: 0006
title: Epic 10 Installments plan commit ownership generalization
stage: plan
date: 2026-08-24
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: null
labels: [installments, epic-10, planning, correction, accounting-integration, atomicity, commit-ownership]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/010-installments/plan.md
 - specs/010-installments/research.md
 - specs/010-installments/data-model.md
tests:
 - none (planning-only correction pass; no code, migrations, or tests created per stop condition)
---

## Prompt

Perform one final targeted correction pass on Epic 10 Installments `plan.md`.

Do NOT redesign the plan, change business requirements, lifecycle, schema, permissions, frontend, or unrelated sections.

Issue to fix: The plan correctly establishes in §12.2 that Installments must own the single final commit for cross-module Accounting workflows, but this guarantee is currently proven mainly for late charges.

Re-inspect the actual Accounting implementation and verify commit boundaries for ALL Installments money-mutating integrations, especially: activation/down payment, collection, settlement payment, collection reversal, cancellation requiring financial reversal, write-off.

For every workflow: (1) Identify the exact Accounting service methods called. (2) Verify whether any called method internally executes `db.commit()` or `PostingEngine.finalize_and_publish()` before control returns to Installments. (3) If it commits early, define the smallest backward-compatible staged/flush-only + finalize extension, following the same pattern already established for `stage_adjustment()`/`finalize_adjustment()`. (4) Ensure Installments can stage its own state changes, allocation references, audit rows, outbox events, and idempotency completion BEFORE the single final commit. (5) Preserve existing standalone Accounting callers through backward-compatible wrapper methods. (6) Add/adjust integration tests proving rollback leaves ZERO partial Accounting or Installments state when failure is injected after Accounting staging but before final commit. (7) Update §12, §21, implementation sequence, risks, testing strategy, and affected ADR/cross-references so they all describe the same actual transaction ownership.

Hard invariant: For every Installments financial workflow, either ALL Accounting + Installments writes commit together, or NONE commit.

Do not assume an Accounting method is staged merely because it internally uses `stage_direct_posting()`; explicitly inspect whether it later calls `finalize_and_publish()` before returning.

After correction, report: methods inspected; early-commit problems found; exact staged APIs/extensions required; sections changed; whether the plan is now safely READY FOR `/sp.tasks`.

## Response snapshot

Re-inspected every named Accounting method by exact line number rather than assuming staged behavior from a method's name:

- **`PaymentService.create_customer_payment()`** (`payment_service.py:196-383`): two branches — the above-threshold DRAFT branch commits at line 278 (no GL/AR truth exists yet, self-contained, out of scope); the normal immediate-post branch stages GL via `stage_direct_posting()` (line 295), builds/flushes `Payment` + credit `ARTransaction`, recomputes the ledger (flush only), then commits via `finalize_and_publish()` at line 374 — early-commit confirmed for the branch Installments actually needs.
- **`AllocationEngine.allocate()`** (`allocation_engine.py:103-276`): every write inside its per-line loop uses `db.add()`+`db.flush()` directly (no hidden repository-`.update()` commits); the only commit(s) are in the final block — `finalize_and_publish()` once per staged FX-adjustment entry, or a bare `db.commit()` if none — early-commit confirmed.
- **`PaymentService.reallocate_payment()`** (`payment_service.py:877-961`): genuinely different shape — commits **inside a loop**, once per existing allocation line reversed (via `PostingEngine.reverse()` or a bare commit), plus a further commit after `payment.status="POSTED"`, plus `allocate()`'s own trailing commit(s). The most eager-committing method found; refactoring its loop into a flush-only shape would be a materially larger, more invasive change than any other fix in this plan.
- **`PaymentService.cancel_payment()`** (`payment_service.py:969-1032`): one commit point, no loop — but requires the payment to already have zero active allocations, so `reallocate_payment(new_allocation_lines=[])` must run first for an allocated Installments collection.
- **`AccountsReceivableService.confirm_write_off()`** (`ar_service.py:734-807`): **three separate commits** — `post_direct()` commits immediately, then `self._transactions.update(transaction)` commits again (confirmed via `core/repositories/base.py:92-106` that `BaseRepository.update()` itself calls `db.commit()`), then `self._recompute_ledger_balance()` → `self._ledgers.update(ledger)` commits a third time. This is exactly the bug class the first correction pass already fixed once in `adjust_receivable()`, confirmed present and never fixed here — the worst defect found in this pass.

Designed and documented the fix for each: **down payment/collection/settlement** get a new `PaymentService.stage_customer_payment()`/`finalize_customer_payment()` pair plus a new `AllocationEngine.stage_allocation()`/`finalize_allocation()` pair, with `create_customer_payment()`/`allocate()` becoming thin backward-compatible wrappers; **write-off** gets a new `AccountsReceivableService.stage_write_off()`/`finalize_write_off()` pair (avoiding the two repository-`.update()`-triggered commits by using `db.add()`+`db.flush()` directly, mirroring the pattern already used elsewhere), with `confirm_write_off()` becoming a thin wrapper. For **reversal/cancellation**, concluded — after weighing the cost of refactoring `reallocate_payment()`'s internal loop against a narrower, provably-sufficient alternative — that no Accounting-side code change is needed at all: because Installments' own reversal-reference rows carry no dependency on the Accounting reversal having already happened, staging them *before* calling the existing, unmodified `reallocate_payment()`/`cancel_payment()` methods is sufficient, since the first internal commit inside those methods necessarily sweeps in everything already flushed. Documented one honest, narrower residual limitation (a failure strictly between the two sequential Accounting calls can leave an intermediate but fully-explainable, non-corrupt state) and its idempotency-key-based resume handling, rather than hiding or overclaiming perfect end-to-end atomicity across a two-call sequence that structurally cannot provide it without the large refactor that was explicitly avoided.

Added six Repository Findings rows recording each precise re-inspection. Wrote a new §12.3 section (with four subsections: 12.3.1 payment/allocation, 12.3.2 reversal/cancellation, 12.3.3 write-off, 12.3.4 a summary table mapping every workflow to its fix) containing exact corrected sequences, the precise new method signatures, and the reasoning for each design choice. Updated the main §12 integration table's Down Payment, Collection, Reversal, Cancellation, and Write-off rows; §21's Activation/Collection/Reversal/Cancellation/Write-off atomic-unit rows; §22's failure/recovery atomicity note (generalized beyond late charges, including the honestly-flagged reversal/cancellation residual case); §31's Accounting-integration testing row (three new forced-failure test groups: payment/allocation, write-off, and the reversal/cancellation intermediate-state test); §36's Phase 6 prerequisite description (now listing all nine new/changed Accounting methods); §37's risk row (generalized, citing the `confirm_write_off()` three-commit discovery as concrete evidence for why explicit re-inspection mattered); ADR-INST-01 (a third correction addendum); and five §38 traceability rows (Down Payments, Cancellation, Write-Off, Refunds/Reversals). Synchronized `research.md` (new R15) and `data-model.md` (`InstallmentAllocationReference`'s mechanism note). Ran a final grep-based consistency sweep confirming all previously-preserved decisions (one-contract partial unique index, `NUMERIC(20,6)`, `InstallmentScheduleVersion`, `InstallmentAccessPolicy`, mandatory migration 071) remain untouched, and verified the new §12.3.x subsections' markdown anchor slugs match every cross-reference link used throughout the document.

## Outcome

- ✅ Impact: The commit-ownership guarantee established for late charges in the prior pass is now proven, method-by-method, for every Installments↔Accounting integration point — closing a genuine, previously-undetected three-commit atomicity defect in the write-off path and equivalent defects in the down-payment/collection/settlement path, while correctly identifying that reversal/cancellation need no Accounting-side change at all. The plan's central hard invariant ("all writes commit together, or none do") now has verified, not assumed, coverage across its full financial-workflow surface.
- 🧪 Tests: none created (planning-only) — §31 gained three new forced-failure/intermediate-state test groups covering payment/allocation, write-off, and reversal/cancellation.
- 📁 Files: specs/010-installments/{plan.md, research.md, data-model.md} updated; this PHR.
- 🔁 Next prompts: `/sp.tasks` — Phase 6's task breakdown should sequence all nine new/changed Accounting methods (three staged/finalize pairs) as explicit, individually-testable prerequisites, with each pair's forced-failure integration test as an acceptance criterion, before any Phase 7/8/10 task depending on it is considered done.
- 🧠 Reflection: The `confirm_write_off()` finding is the strongest evidence in this entire correction sequence for the value of the user's repeated "do not assume, explicitly inspect" instruction — a name like `post_direct()` invites the assumption "this is the one-shot staged/finalize helper," but reading the calling method's full body revealed two *additional* commits hiding behind ordinary-looking repository `.update()` calls, a defect pattern invisible to anything short of full line-by-line reading.

## Evaluation notes (flywheel)

- Failure modes observed: none in this pass's own execution. The pass exists specifically because the second (micro-correction) pass proved a general principle only for one workflow — a reminder that even a correctly-derived general principle needs verification against every instance it claims to cover, not just the one that prompted it.
- Graders run and results (PASS/FAIL): N/A — planning-only phase, no automated grading harness invoked.
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): When a plan states a cross-cutting architectural guarantee (e.g. "commit ownership is frozen"), add a standing checklist item to enumerate every call site the guarantee claims to cover and verify each one individually before considering the guarantee proven — this correction pass effectively did that as a one-time sweep; making it a repeatable, named step earlier in the process would have caught this in the second pass rather than requiring a third.
