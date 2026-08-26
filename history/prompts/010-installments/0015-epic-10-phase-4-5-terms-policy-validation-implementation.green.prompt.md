---
id: 0015
title: Epic 10 Phase 4.5 terms policy validation implementation
stage: green
date: 2026-08-26
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: /sp.implement
labels: [installments, epic-10, phase-4-5, terms-policy-validation, fr-inst-011, retrofit, gap-closure]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/installments/services/terms_policy_validator.py
 - backend/modules/installments/exceptions.py
 - backend/modules/installments/services/quote_service.py
 - backend/modules/installments/services/contract_service.py
 - backend/modules/installments/dependencies.py
 - backend/tests/unit/modules/installments/test_terms_policy_validator.py
 - backend/tests/unit/modules/installments/test_terms_policy_enforced_everywhere.py
 - backend/tests/unit/modules/installments/test_quote_service.py
 - backend/tests/unit/modules/installments/test_contract_creation.py
 - backend/tests/security/installments/test_contract_tenant_isolation.py
 - specs/010-installments/tasks.md
tests:
 - backend/tests/unit/modules/installments/test_terms_policy_validator.py — 11 passed (10 arithmetic + 1 branch-override-vs-fallback, real SQLite-backed InstallmentConfigurationService)
 - backend/tests/unit/modules/installments/test_terms_policy_enforced_everywhere.py — 3 passed (single-validator reuse, direct-bypass proof, structural no-duplicate-logic proof)
 - backend/tests/unit/modules/installments/test_quote_service.py — 7 passed (1 new, 3 existing fixed for the retrofit)
 - backend/tests/unit/modules/installments/test_contract_creation.py — 5 passed (unaffected, fixture updated)
 - backend/tests/security/installments/test_contract_tenant_isolation.py — 5 passed (unaffected, fixture updated)
 - full Installments module regression (unit+repository+API+security) — 87 passed, 0 failed
---

## Prompt

Implement Phase 4.5

## Response snapshot

Implemented T073A-T073E exactly as scoped by the prior planning correction (PHR 0014) — no Phase 5 lifecycle/idempotency/Accounting-mutation work started.

**T073A**: `InstallmentTermsPolicyValidator.validate()` — a stateless static method taking an already-resolved `InstallmentConfiguration | None` plus proposed terms. Checks `frequency` membership in `allowed_frequencies`, `installment_count` within `[min_term, max_term]`, `down_payment_amount` against whichever of `min_down_payment_pct`/`min_down_payment_amount` is configured, and `financed_amount` against `max_financed_amount`. Collects **all** violations before raising once (better than fail-fast-on-first, since a client fixing one field shouldn't have to resubmit repeatedly to discover the next). `config is None` is a no-op. New `InstallmentTermsPolicyViolationError` added to `exceptions.py` (`ValidationException` subclass, `code="TERMS_POLICY_VIOLATION"`, `details.violations` names every violated field).

**Implementation-time refinement**: the task text's signature only named `financed_amount`, but validating `min_down_payment_pct` correctly requires the *pre-down-payment* principal too (percentage-of-what?). Added `principal_amount` as an explicit parameter — both call sites already have `eligibility.outstanding_amount` on hand, so this cost nothing extra to wire through. `financed_amount` is mapped to `financed_principal` (post-down-payment, pre-markup) — markup is a service charge, not part of what's being "financed," so `max_financed_amount` correctly caps the risk-bearing principal, not the contractual total.

**T073B/T073C**: both `InstallmentQuoteService.preview()` and `InstallmentContractService.create_draft()` now call the identical `InstallmentTermsPolicyValidator.validate()` before any further work (before `ScheduleEngine.generate()` in `preview()`; before consuming a sequence number in `create_draft()`, so a rejected draft never creates a numbering gap). `InstallmentContractService` gained a new required constructor parameter, `configuration_service: InstallmentConfigurationService` — updated its one production wiring point (`dependencies.py::get_installment_contract_service()`, reusing the existing `get_installment_configuration_service` factory) and its two existing test call sites (`test_contract_creation.py`'s `_build_service()` helper, `test_contract_tenant_isolation.py`'s `get()`-only IDOR test — both pass a config that resolves to `None`/no-config, since neither test exercises policy bounds).

**T073D**: 11 unit tests — 10 pure-arithmetic cases against a fake config (valid terms, disallowed frequency, below/above term bounds, both down-payment-minimum variants, a passing percentage-minimum boundary case, max-financed-amount exceeded, multiple-simultaneous-violations-all-reported) plus one integration-level test using the real `InstallmentConfigurationService`/repository (SQLite) proving a branch override's tighter bound is what's actually enforced when both a company-default and branch-override row exist for the same company.

**T073E**: 3 tests proving single-validator reuse — identical disallowed terms rejected identically (same exception type, same `code`, same `violations` dict) by both `preview()` and `create_draft()`; a direct `create_draft()` call (never touching `/quotes`) still rejects out-of-policy terms; a structural `inspect.getsource()` check confirms `contract_service.py` contains no independently-reimplemented `allowed_frequencies`/`min_term`/`max_term`/`min_down_payment`/`max_financed_amount` comparison — only a call into `InstallmentTermsPolicyValidator`.

**Regression fix required in already-committed Phase 4 tests**: `test_quote_service.py`'s `_FakeConfig` only had a `rounding_policy` field (all that T069's original scope needed); adding the retrofit broke 3 existing tests with `AttributeError`. Fixed by giving `_FakeConfig` permissive defaults for the new fields (wide term range, all three frequencies allowed, no down-payment/financed-amount caps) so unrelated rounding-policy tests are unaffected, and split the "unsupported frequency" test into two: one with `config=None` (proving `ScheduleEngine`'s own `ValueError`→`INVALID_SCHEDULE_TERMS` translation from Phase 4 still works when no policy is configured) and a new one with a configured tenant (proving the new, earlier `TERMS_POLICY_VIOLATION` gate now intercepts the same input first when a policy exists).

**Testing**: 11 + 3 = 14 new tests; `ruff check`/`black --check` clean on all files (one file needed a `black` reformat after hand-writing, applied and re-verified). Full Installments module regression: 87 passed, 0 failed (72 pre-existing + 15 new/modified). A live HTTP smoke test (throwaway, cleaned up) proved the full stack end-to-end through the real router/dependency wiring: a disallowed `WEEKLY` frequency against a `MONTHLY`-only configured tenant returned `422 TERMS_POLICY_VIOLATION` with the exact violated-field detail; valid terms returned `200`. (The smoke harness itself needed the real `core.exceptions.handler` global exception handlers registered — omitted in the Phase 3/4 smoke scripts since no test there actually exercised a raised-exception path — to correctly translate `InstallmentTermsPolicyViolationError` into an HTTP response, confirming this is genuinely wired through the same exception-handling path production traffic uses.)

Committed as a single Phase 4.5 completion commit; `tasks.md` T073A-T073E checked off with evidence; PHR written; Phase 5 not started per the standing Final Stop Rule.

## Outcome

- ✅ Impact: FR-INST-011's policy-bounds check is now live, enforced identically at both terms-setting call sites, and provably un-bypassable via direct service calls.
- 🧪 Tests: 14 new tests all passed; full Installments regression 87/87 passed (zero regressions from the retrofit).
- 📁 Files: 1 new service, 1 new exception, 2 retrofitted services, 1 dependency-wiring update, 2 new test files, 3 existing test files fixed for the new constructor parameter/behavior, tasks.md checkboxes.
- 🔁 Next prompts: Phase 5 (Contract Lifecycle, T074-T084) — awaiting explicit Product Owner instruction.
- 🧠 Reflection: retrofitting an already-completed, already-tested phase's code is exactly the scenario where "run the existing test suite before declaring done" earns its keep — the 3 broken `test_quote_service.py` tests were caught immediately, not discovered later as a surprise regression.

## Evaluation notes (flywheel)

- Failure modes observed: (1) the task text's validator signature under-specified `principal_amount` as a separate input from `financed_amount` — needed for percentage-based down-payment validation — caught and fixed during implementation, not left as a silent gap; (2) retrofitting `InstallmentContractService`'s constructor broke 2 already-committed test call sites and 3 already-committed `test_quote_service.py` assertions — all caught by running the existing suite immediately after the retrofit, not deferred to a later regression pass.
- Graders run and results (PASS/FAIL): self-audit against plan.md §10.6/tasks.md Phase 4.5 — PASS; exit gate ("single implementation... both call it... direct create_draft() bypass still rejected... branch-override resolution proven... unconfigured tenant never wrongly blocked") — PASS, each clause individually proven by a specific test.
- Prompt variant (if applicable): n/a.
- Next experiment (smallest change to try): none required; Phase 5 will reuse the standard master-phase-prompt template.
