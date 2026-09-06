---
id: 0016
title: Epic 10 Phase 5 contract lifecycle
stage: green
date: 2026-08-26
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: /sp.implement
labels: [installments, epic-10, phase-5, contract-lifecycle, maker-checker, legal-transitions, audit, submit-approve-reject-cancel-default]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/installments/services/contract_service.py
 - backend/modules/installments/dependencies.py
 - backend/modules/installments/router.py
 - backend/modules/installments/schemas/contract.py
 - backend/tests/unit/modules/installments/test_lifecycle_transition_matrix.py
 - backend/tests/unit/modules/installments/test_maker_checker.py
 - backend/tests/unit/modules/installments/test_rejection_not_persisted.py
 - backend/tests/security/installments/test_no_generic_status_setter.py
 - backend/tests/unit/modules/installments/test_contract_creation.py
 - backend/tests/security/installments/test_contract_tenant_isolation.py
 - backend/tests/unit/modules/installments/test_terms_policy_enforced_everywhere.py
 - specs/010-installments/tasks.md
tests:
 - backend/tests/unit/modules/installments/test_lifecycle_transition_matrix.py — 34 passed (incl. 5 commit-durability tests)
 - backend/tests/unit/modules/installments/test_maker_checker.py — 4 passed
 - backend/tests/unit/modules/installments/test_rejection_not_persisted.py — 4 passed
 - backend/tests/security/installments/test_no_generic_status_setter.py — 3 passed
 - full Installments module regression (unit+repository+API+security, all phases 0-5) — 132 passed, 0 failed
---

## Prompt

# Epic 10 — Installments
# MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT

Implement, verify, audit, and close ONLY the following phase of Epic 10.

Phase Number: `5`
Phase Name: `Contract Lifecycle`
Task Range: `T074 to T084`

Feature Branch: 010-installments

[Full 47-section master phase implementation prompt — identical structure
to Phases 0-4.5. Followed by the standing PHR-creation instruction.]

## Response snapshot

Implemented T074-T084 (Phase 5: Contract Lifecycle) exactly as scoped —
no Phase 6+ work (Accounting integration, idempotency, activation,
collections) started.

**Named lifecycle methods** added to `InstallmentContractService`:
`submit()`, `approve()`, `reject()`, `cancel()`, `mark_defaulted()` —
each asserts `_LEGAL_TRANSITIONS` before mutating, uses
`InstallmentContractRepository.update_with_version_check()` (Phase 3's
optimistic-lock primitive, unchanged) for the actual UPDATE, and audits
via `InstallmentAuditService.record()` (Phase 1's flush-only primitive).
`InstallmentContractService` gained a new `audit_service` constructor
dependency, wired through `dependencies.py` and three existing test call
sites.

**Critical defect found and fixed during implementation**: `approve()`
and `submit()` both need to reach "APPROVED," and `_LEGAL_TRANSITIONS`
has TWO predecessors for "APPROVED" — `DRAFT` (submit()'s own
no-threshold fast path) and `PENDING_APPROVAL` (approve()'s target). A
bare `_assert_transition(current, "APPROVED")` graph-membership check
would have let `approve()` succeed directly on a still-`DRAFT` contract
— where `submitted_by` is `None`, silently defeating the self-approval
(maker-checker) check FR-INST-102 requires, and letting `submit()` be
called a second time on an already-`PENDING_APPROVAL` contract to
fast-track it to `APPROVED`, bypassing `approve()`'s own gate entirely.
Fixed by requiring each method's *specific* expected current status
explicitly (`submit()` requires `DRAFT`; `approve()` requires
`PENDING_APPROVAL`) rather than relying on bare graph reachability —
`reject()`/`cancel()`/`mark_defaulted()` were checked and found safe
as originally written (each targets a status with either a single
predecessor, or — for `cancel()` — intentionally accepts all four
legal predecessor stages per T077's own design). A dedicated regression
test (`test_approve_rejected_from_non_pending_approval_status`) proves
this fix; it would have failed against the original bare-graph-check
implementation.

**`submit()`** (FR-INST-101): resolves the effective `InstallmentConfiguration`'s
`approval_threshold_amount`; `DRAFT → APPROVED` directly if unconfigured
or `contractual_total` is below it, otherwise `DRAFT → PENDING_APPROVAL`.
**`approve()`**/**`reject()`** (FR-INST-102, plan.md §16.2): identical
distinct-submitter maker-checker check on both, applied symmetrically
from day one (explicit regression guard named in the task text itself).
`reject()` requires a mandatory `reason`, transitions
`PENDING_APPROVAL → DRAFT`, and writes `InstallmentAuditLog(action=
"REJECTED")` — `REJECTED` is never a persisted `status` value.
**`cancel()`**: implements only the free (no-financial-activity) path
this phase can reach — no contract can be `ACTIVE` at all yet
(`activate()` is Phase 7's T124), so the free path is the only reachable
one; the financial-activity branch and this endpoint's router wiring
are explicitly Phase 10's T169/T174. **`mark_defaulted()`**: the pure
internal `ACTIVE → DEFAULTED` primitive only — flush-only, deliberately
does **not** commit (proven by a dedicated rollback test), not wired to
any router endpoint, zero Accounting calls; the externally-callable,
idempotency-protected "default" command is Phase 10's `default_command()`.

**T079/T080**: added `InstallmentContractRejectRequest`/
`InstallmentContractCancelRequest`/`InstallmentContractDefaultRequest`
schemas (the latter two not yet wired to any endpoint — their router
endpoints are Phase 10's T174/T167). Wired `POST /contracts/{id}/submit
|approve|reject` into `router.py`, matching the OpenAPI contract's
exact `x-permission` (`installments.contract.create` for submit,
`installments.contract.approve` for approve/reject) and
`x-operation-class: ORIGINATION`.

**Testing**: 34 lifecycle-matrix tests (every transition Phase 5's
methods can reach, both success and rejection, plus 5 dedicated
commit-durability tests re-fetching through a fresh query — guarding
against the exact "missing commit" defect class already documented once
in this codebase's Inventory module history), 4 maker-checker tests, 4
rejection-not-persisted tests (including a two-cycle reject→resubmit→
reject proof that both audit entries survive undisturbed), 3 structural
tests (no generic setter, all named methods present, no `status`/
`new_status` kwarg on any lifecycle method). A live HTTP smoke test
(throwaway, cleaned up) proved `POST /contracts/{id}/submit` and
`/reject` end-to-end through the real router/dependency wiring against
an in-memory SQLite-backed FastAPI app (reusing the root conftest's
JSONB/`gen_random_uuid()` compatibility shims) — submit correctly
auto-approved an unconfigured tenant's contract, and reject on an
already-`APPROVED` contract correctly returned 409 with the exact
illegal-transition detail. Full Installments module regression (all
phases 0-5 combined): 132 passed, 0 failed. `ruff check`/`black --check`
clean on every file.

Committed as a single Phase 5 completion commit; `tasks.md` T074-T084
checked off with evidence; PHR written; STOP per Section 47 — Phase 5.5
(Idempotency Primitive) not started.

## Outcome

- ✅ Impact: Phase 5 (Contract Lifecycle) complete — five named business
  actions replace any notion of a generic status setter; maker-checker
  is symmetric on approve/reject from day one; a subtle graph-ambiguity
  defect (approve() reachable from DRAFT) was caught and fixed before
  being marked complete, not discovered later.
- 🧪 Tests: 45 new tests, all passed; full Installments regression
  132/132 passed.
- 📁 Files: 1 heavily-extended service, 1 schema file extended, 1
  router extended, 1 dependency-wiring update, 4 new test files, 3
  existing test files fixed for the new constructor parameter.
- 🔁 Next prompts: Phase 5.5 (Idempotency Primitive, T085-T093) —
  awaiting explicit Product Owner instruction per the Final Stop Rule.
- 🧠 Reflection: the approve()/submit() graph-ambiguity defect is exactly
  the class of issue Section 35's adversarial-completeness pass ("which
  lifecycle transition could bypass its guard?") exists to catch — it
  was found by manually enumerating _LEGAL_TRANSITIONS' predecessor sets
  per target status before trusting the naive implementation, not by
  accident.

## Evaluation notes (flywheel)

- Failure modes observed: a purely graph-based transition-legality check
  is insufficient when two different named methods can reach the same
  target status from different source statuses — each method must
  additionally assert its own specific expected precondition, not just
  "is my target reachable from wherever the contract currently is."
- Graders run and results (PASS/FAIL): self-audit against Constitution/
  Spec/Plan/Tasks/OpenAPI/data-model — PASS; Exit Condition — PASS
  (every legal transition implemented via a named method; illegal
  transitions provably rejected; REJECTED never persisted; self-approval
  denied symmetrically; no generic status-setter exists).
- Prompt variant (if applicable): n/a — identical master-phase template
  reused verbatim from Phases 0-4.5.
- Next experiment (smallest change to try): when Phase 5.5 is
  implemented, the same "which named method owns which specific graph
  edge" analysis should be repeated for any new idempotency-protected
  command before trusting a first-draft transition guard.
