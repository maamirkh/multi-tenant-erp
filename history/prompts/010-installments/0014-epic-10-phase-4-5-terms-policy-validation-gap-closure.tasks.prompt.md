---
id: 0014
title: Epic 10 Phase 4.5 terms policy validation gap closure
stage: tasks
date: 2026-08-26
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: /sp.tasks
labels: [installments, epic-10, phase-4-5, tasks-correction, fr-inst-011, terms-policy-validation, planning-only]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/010-installments/tasks.md
 - specs/010-installments/plan.md
tests:
 - none run — planning/tasks-only correction, no code changed
---

## Prompt

Perform one targeted planning/tasks correction for Epic 10 Installments.

Issue:
Phase 4 discovered that tenant-configured installment policy bounds are not explicitly assigned to any implementation task.

The approved spec already requires:
- allowed frequencies
- min/max installment term
- minimum down payment
- optional maximum financed amount
- configured policy bounds for fully custom contract terms

Do NOT modify spec.md.

Goal:
Assign explicit implementation ownership for validating installment terms against the effective tenant/branch configuration.

Requirements:

1. Introduce one reusable service/domain validator, repository-consistent in name, conceptually:
   `InstallmentTermsPolicyValidator`

2. It must validate at minimum:
   - frequency is allowed
   - installment_count within configured min/max
   - down payment satisfies configured minimum
   - financed amount does not exceed configured maximum when present
   - other already-defined commercial bounds from InstallmentConfiguration that are relevant to quote/contract terms

3. Reuse the SAME validator in all applicable paths, especially:
   - quote preview
   - contract draft/create
   - approval/activation re-validation where required by the approved spec/plan

4. Do not rely only on frontend validation.

5. Do not duplicate this logic independently in QuoteService and ContractService.

6. Add focused tests proving:
   - valid terms pass
   - disallowed frequency fails
   - below-min term fails
   - above-max term fails
   - insufficient down payment fails
   - max financed amount exceeded fails
   - branch override vs company fallback is respected
   - direct contract creation cannot bypass validation

7. Update only the minimum affected planning/task artifacts:
   - plan.md only if needed to clarify ownership
   - tasks.md to add/adjust explicit task(s), dependencies, counts, traceability and IDs
   - PHR as required

8. Preserve all completed Phase 0–4 implementation work and task evidence.
   Do NOT renumber completed tasks unless absolutely unavoidable.
   Prefer appending/inserting the smallest safe task set and updating downstream dependencies mechanically.

9. Do NOT implement the fix yet.
   Do NOT start Phase 5.

Return:
- exact requirement gap confirmed
- validator architecture chosen
- paths/workflows that must call it
- tasks added/modified
- any task renumbering
- updated total task count
- updated traceability
- whether Phase 4 remains technically complete
- final verdict: READY TO IMPLEMENT POLICY-VALIDATION GAP or BLOCKED

## Response snapshot

**Gap confirmed**: FR-INST-011 (spec.md §9.2 — "installment contracts ... created either from a template or with fully custom terms within the tenant's configured policy bounds") had no task anywhere in the 15-phase, 261-task breakdown assigning ownership of validating `frequency`/`installment_count`/`down_payment_amount`/`financed_amount` against `InstallmentConfiguration`. Confirmed by exhaustive grep of tasks.md for `min_down_payment`/`max_financed_amount`/`min_term`/`max_term`/`allowed_frequencies` — the only task that touches these fields is T029 (`InstallmentConfigurationService`'s own cross-field validation of the *configuration row itself*, e.g. `min_term <= max_term`), never validation of a *proposed contract's terms against* that configuration. Both already-implemented, already-committed call sites — Phase 3's `InstallmentContractService.create_draft()` (T049) and Phase 4's `InstallmentQuoteService.preview()` (T069) — accept caller-supplied terms with zero policy-bound check today.

**Validator architecture chosen**: a single stateless `InstallmentTermsPolicyValidator.validate(config, *, frequency, installment_count, down_payment_amount, financed_amount)` in a new `backend/modules/installments/services/terms_policy_validator.py`, taking an already-resolved `InstallmentConfiguration | None` (branch-override-or-company-fallback resolution stays exactly where it already lives, `InstallmentConfigurationService.get_effective_config()` — not duplicated inside the validator) plus the proposed terms, and raising one new exception, `InstallmentTermsPolicyViolationError` (a `ValidationException` subclass, `code="TERMS_POLICY_VIOLATION"`). `config is None` is treated as "no bounds configured" (no-op), not "reject everything" — consistent with `InstallmentConfiguration` being optional since Phase 2.

**Call sites requiring it**: `InstallmentQuoteService.preview()` and `InstallmentContractService.create_draft()` — both retrofitted to call the same validator, never two copies. Approval/activation re-validation was explicitly considered and **rejected** as out of scope: BR-INST-008/FR-INST-200 make a contract's core financial terms immutable once `ACTIVE`, and `submit()`/`approve()`/`reject()` never mutate terms — there is no second point where terms could newly violate policy after `create_draft()` already validated them, and no spec/plan section requires re-checking unchanged values. (This mirrors FR-INST-023's eligibility re-check, which explicitly *is* required — terms-policy has no equivalent explicit requirement, so it was not invented.)

**Tasks added**: five, using suffixed IDs `T073A`–`T073E`, inserted as a new **Phase 4.5** section between the already-closed Phase 4 and Phase 5 in tasks.md — specifically chosen over renumbering so that **zero** existing task ID (T001–T073 completed, or T074–T261 already-numbered-but-not-yet-implemented) changes. T073A (the validator + new exception), T073B (retrofit `preview()`), T073C (retrofit `create_draft()`), T073D (validator unit tests — all 6 required scenarios plus the branch-override-vs-fallback case), T073E (regression/structural proof of single-validator reuse and that direct `create_draft()` calls cannot bypass validation).

**Task renumbering**: none. Verified by diffing task-ID sets before/after and confirming T074 (Phase 5's first task) is byte-identical to its pre-correction text/position.

**Updated total task count**: 261 → 266 (73 already `[x]`-complete from Phases 0–4, 193 open including the 5 new Phase 4.5 tasks).

**Updated traceability**: added a new FR-group row "§9.2 Custom-terms policy bounds (FR-INST-011) | T073A-T073E [NEW]"; appended `T073A, T073B` to the existing "§9.4 Quote/Preview" row and `T073A, T073C` to "§9.5 Contract data" row; added a Phase 4.5 entry to the Parallel Execution Guidance section. `plan.md` gained a new, non-renumbering §10.6 ("Terms Policy Validation [NEW — Correction 7]") documenting ownership and explicitly stating this does not reopen Phase 3/4's frozen exit-gate proofs.

**Phase 4 status**: remains technically complete and unmodified — its own exit gate (`ScheduleEngine` purity, non-mutating preview, immutable schedule persistence) never depended on terms-policy enforcement, and none of its committed code/tests were touched by this correction.

**No implementation performed** — plan.md and tasks.md only. No code written, no tests run, Phase 5 not started.

## Outcome

- ✅ Impact: FR-INST-011's implementation ownership is now explicit and traceable; the "No orphan requirements" claim at the bottom of tasks.md remains true. Phase 5 is now correctly blocked-in-sequence behind Phase 4.5 rather than silently inheriting an unvalidated terms-creation path.
- 🧪 Tests: none — planning-only correction, per explicit instruction not to implement yet.
- 📁 Files: tasks.md (Correction 7 note, new Phase 4.5 section, 3 traceability rows, 1 parallel-guidance bullet), plan.md (new §10.6). spec.md untouched, as instructed.
- 🔁 Next prompts: implement Phase 4.5 (T073A-T073E) via the standard `/sp.implement` master-phase prompt, then resume Phase 5 (Contract Lifecycle, T074-T084).
- 🧠 Reflection: suffixed task IDs (T073A-E) were the correct call over mechanical renumbering here — the prior "Correction" pass in this same file's history *did* renumber ~150 tasks when it had to insert 6 new ones, and that was a materially riskier operation than this one; preferring the smallest-blast-radius option (letter suffixes) when the numeric gap doesn't exist is the generalizable lesson.

## Evaluation notes (flywheel)

- Failure modes observed: none — this was a pure documentation/planning correction; the main risk (accidentally renumbering completed/committed task references) was avoided by choosing suffixed IDs instead of shifting T074+.
- Graders run and results (PASS/FAIL): manual verification — grep confirmed zero duplicate task IDs, zero renumbering of T074 onward, task count reconciles (73 complete + 193 open = 266), Phase 4's own exit-gate text and evidence untouched.
- Prompt variant (if applicable): n/a.
- Next experiment (smallest change to try): when Phase 4.5 is implemented, re-run the full Installments regression (currently 72 passing) to confirm the two retrofits (T073B/T073C) introduce zero regressions in the already-committed Phase 3/4 test suites.
