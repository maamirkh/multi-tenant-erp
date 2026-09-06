---
id: 0012
title: Epic 10 Phase 3 contract persistence
stage: green
date: 2026-08-25
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: /sp.implement
labels: [installments, epic-10, phase-3, contract-persistence, sales-integration, accounting-gateway, one-contract-per-obligation, tenant-isolation, concurrency]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/installments/models/contract.py
 - backend/modules/installments/models/__init__.py
 - backend/modules/installments/repositories/contract.py
 - backend/modules/installments/services/sales_read_gateway.py
 - backend/modules/installments/services/accounting_gateway.py
 - backend/modules/installments/services/eligibility_service.py
 - backend/modules/installments/services/contract_service.py
 - backend/modules/installments/schemas/contract.py
 - backend/modules/installments/schemas/eligibility.py
 - backend/modules/installments/dependencies.py
 - backend/modules/installments/router.py
 - backend/modules/accounting/services/ar_service.py
 - backend/tests/integration/repositories/installments/test_contract_one_per_obligation.py
 - backend/tests/security/installments/test_contract_tenant_isolation.py
 - backend/tests/unit/modules/installments/test_contract_creation.py
 - backend/tests/unit/modules/installments/test_accounting_gateway_boundary.py
 - specs/010-installments/tasks.md
tests:
 - backend/tests/integration/repositories/installments/test_contract_one_per_obligation.py (real Postgres, genuine two-thread/two-session race) — 1 passed, re-run 4x for flake-check, stable
 - backend/tests/security/installments/test_contract_tenant_isolation.py — 5 passed
 - backend/tests/unit/modules/installments/test_contract_creation.py — 5 passed
 - backend/tests/unit/modules/installments/test_accounting_gateway_boundary.py — 3 passed
 - Full Installments regression (unit/repo/security/API) — 37 passed
 - Full Accounting regression (unit/repository/API+E2E) — 513 passed, 0 failed (ar_service.py touched)
 - ruff check (all new/modified files) — all checks passed
 - Manual live-HTTP smoke test (throwaway, not committed): GET/POST /contracts, GET /contracts/{id}, GET /eligibility, duplicate-invoice 409, missing/cross-tenant 404 — all correct
 - Manual Postgres column-drift check: zero drift for InstallmentContract vs. migration 064's live schema
---

## Prompt

# Epic 10 — Installments
# MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT

Implement, verify, audit, and close ONLY the following phase of Epic 10.

Phase Number: `3`
Phase Name: `Persistence` (tasks.md's own heading: "Contract Persistence")
Task Range: `T043 to T056`

Feature Branch: 010-installments

[Full 47-section master prompt supplied verbatim by the user — identical
structure/rules to the Phase 0/1/2 closure prompts (PHRs 0009-0011):
primary objective and no-correction-pass standard; strict phase scope
(implement only T043-T056, no Schedule/Lifecycle/Idempotency artifacts
pre-created); authoritative sources and authority order; branch/
working-tree safety; pre-implementation task audit; repository-reality
check before new abstractions; per-task IMPLEMENT/TEST/VERIFY/NEGATIVE-
PATH/DEPENDENCY-RECHECK discipline; architecture freeze (Accounting
source-of-truth, single controlled AccountingIntegrationGateway boundary,
no shadow financial balances) — directly load-bearing this phase via
T046; financial-transaction/idempotency/Phase-5.5/Phase-6 hard-gate
rules — N/A, no financial *mutation* in this phase, reads only; database
& migration hard rules — N/A, no new migrations (reuses 064 from Phase
0); API contract lock (explicit instruction to inspect
installments-api.yaml before implementation) — directly exercised for
the new /contracts and /eligibility endpoint groups; data-model↔
implementation audit; frontend rules — N/A; full testing pyramid;
failure-injection/atomicity proof — N/A (no staged/finalize workflow
touched); pre-existing-failure policy; real PostgreSQL/Docker
verification requirement — directly exercised for T053's concurrency
proof; live HTTP/browser verification; requirement traceability review;
mandatory self-review and adversarial-completeness pass; full diff
review before closure; task-checkbox truthfulness rule; exact phase
Exit Condition proof requirement; hard-gate rule — N/A; regression
verification (explicitly including Accounting, since this phase touches
`ar_service.py`); no-correction-pass final contradiction search; PHR
requirement; pre-commit check; commit policy; post-commit verification;
the exhaustive Required Final Report template (sections A-S); and the
final stop rule.]

## Response snapshot

Verified branch (`010-installments`) and working tree matched the exact
pre-existing baseline confirmed at every prior phase's closure. Confirmed
Phases 0-2's commits (`2607731`, `70a1736`, `c7c9c29`) present. Read
tasks.md T043-T056 plus plan.md §13 (Sales Integration table — the
authoritative source for T045/T047/T049's exact design), and dispatched
a research agent to gather exact, verified facts (not summaries) before
writing any cross-module code: `SalesInvoiceRepository`/`CustomerRepository`
exact signatures and `SalesInvoice`/`Customer` model field/status values
(confirming `"ISSUED"` and `"ACTIVE"` are real, valid values, not
assumed); `AccountsReceivableService`'s actual public method surface
(confirmed `get_open_transactions()` is by-customer, not by-invoice, and
that NEITHER a public "find AR transaction by source document" NOR a
public "get AR transaction by id" method exists yet — only private/
repository-level equivalents); and `AdjustmentRepository.update_status()`'s
exact optimistic-lock conditional-`UPDATE...RETURNING` pattern (Core
`update()`, not ORM attribute-set, zero-rows-returned = conflict).

**Repository-reality contradiction found and resolved (Section 2/41,
not silently)**: T046 explicitly asserts "no new Accounting-side method
required for reads," but the research above proved this false for
`get_ar_transaction(company_id, ar_transaction_id)` — the only existing
implementation is `_get_transaction()`, a *private* method that raises
rather than returning `None`, and `find_by_source_document()` exists
only on the *repository*, never the service (which T046 explicitly
forbids importing). Resolved via the smallest safe addition per Section
41's "Implementation error → FIX IT": added two trivial, additive,
read-only, backward-compatible public wrapper methods to
`AccountsReceivableService`
(`find_transaction_by_source_document()`/`get_transaction_by_id()`),
each a 3-line delegation to the already-existing, already-tested
repository method — zero behavior change to any existing caller, zero
new architecture, matching this epic's own stated philosophy for every
other Accounting extension ("additive, backward-compatible extractions
of existing internals"). Verified via the full Accounting regression
suite (513 passed) that this is genuinely risk-free.

Implemented all 14 tasks:
- **T043**: `InstallmentContract` model — column-for-column match to
  migration 064 (verified via live Postgres introspection, zero drift).
  `active_schedule_version_id` deliberately has no ORM-level
  `ForeignKey()`/`relationship()` (the real DB constraint already exists
  from migration 065; no Python class for that table exists until Phase
  4 — matches the "no future-phase model pre-creation" discipline).
- **T044**: `InstallmentContractRepository` — `get_by_id_locked()`
  (`SELECT...FOR UPDATE`), `find_active_by_sales_invoice()`, and
  `update_with_version_check()` (mirrors `AdjustmentRepository.update_status()`'s
  exact Core-`update()`+`RETURNING` pattern, raising
  `InstallmentConcurrentModificationError` on zero rows).
- **T045**: `SalesInvoiceReadGateway`/`SalesCustomerReadGateway` — thin
  read-only wrappers, mirroring `Customer360Service`'s exact
  cross-module-repository-import precedent.
- **T046**: `AccountingIntegrationGateway` read-only skeleton
  (`get_invoice_outstanding_amount()`, `get_ar_transaction()`), importing
  only `modules.accounting.services.AccountsReceivableService` — proven
  via a dedicated structural/import-lint test
  (`test_accounting_gateway_boundary.py`, mirroring the CRM/Sales
  `test_no_sales_module_ships_a_raw_orm_import_in_conversion_service`
  convention exactly) that neither `.models` nor `.repositories` is
  imported.
- **T047**: `InstallmentEligibilityService.check_invoice_eligibility()` —
  raises (never returns `eligible=false`) with documented codes
  (`INVOICE_NOT_ISSUED`, `NO_OUTSTANDING_BALANCE`, `CUSTOMER_NOT_ACTIVE`),
  matching the OpenAPI contract's explicit "422: ineligible, with
  documented reason code" (not a 200 with a boolean flag).
- **T048/T049**: `build_terms_snapshot()` (pure function) +
  `InstallmentContractService.create_draft()` — `financed_principal`
  computed from the gateway's *live* outstanding read (never the
  invoice's stale original total), `contract_number` via T028's locked
  sequence generator, a pre-check against `find_active_by_sales_invoice()`
  for a clean 409 in the non-race case, **plus** (a defect fix, see
  below) an `IntegrityError`-catching wrapper around the actual insert
  for the *race* case, translating the specific
  `uq_installment_contracts_one_nonterminal_per_obligation` constraint
  violation into the identical clean `ConflictException`.
- **T050**: `InstallmentContractCreate`/`Read`/`Summary` Pydantic
  schemas — `currency_code` is deliberately absent from `Create` (never
  an input; always sourced from the invoice, making a mismatch
  structurally impossible, not merely validated away).
- **T051/T052**: Contracts (`GET /contracts`, `GET /contracts/{id}`,
  `POST /contracts`) and Eligibility (`GET /eligibility`) endpoint
  groups in `router.py`, per-operation permission/class cross-checked
  against `installments-api.yaml` exactly.

**Second defect found and fixed** (T053's own explicit requirement,
Section 41): tasks.md T053 requires "the loser receives a clean 409
translated from IntegrityError" for the concurrent-race case — but my
initial `create_draft()` only had the pre-check (handles the sequential/
non-race case cleanly; a genuine race would have let a raw
`IntegrityError` surface as an uncaught 500). Cross-checked the closest
existing precedent (`platform_administrator_service.py`'s `create()`)
and found that precedent explicitly documents *not* catching this race
window at all — a weaker guarantee than Epic 10's task list demands.
Since tasks.md is the authoritative source (outranks "repository
conventions" per the stated hierarchy) and Installments is explicitly
held to a higher bar as a money-adjacent module, implemented the
catch-and-translate wrapper properly rather than reproducing the weaker
existing pattern.

Verified every task with runtime evidence: T053's real-Postgres
two-thread/two-session race test (careful to avoid a barrier-based
deadlock — discovered during test-writing that placing a
`threading.Barrier` *between* a pre-flushed INSERT and its commit
creates a genuine deadlock risk against Postgres's own row-level lock
wait, since the second session's `flush()` can block *before* ever
reaching the barrier while the first session waits at the barrier for
the second; fixed by removing the barrier entirely and letting
Postgres's native unique-index lock-then-block-then-resolve mechanism
serialize the two sessions, exactly as plan.md §20.2/§20.3 already
describes for the idempotency primitive) — ran 4 times to confirm zero
flakiness, asserts not just "one succeeded" but that the loser's
`IntegrityError.orig.diag.constraint_name` is *exactly*
`uq_installment_contracts_one_nonterminal_per_obligation` (the precise
signature `create_draft()`'s catch block is built to detect). T054's 5
tests prove cross-tenant reads return `None`/raise the *identical*
`InstallmentNotFoundError` (same type, code, http_status) for both a
genuinely-nonexistent and a genuinely-cross-tenant contract id — true
BR-INST-015 indistinguishability, not just "both return 404." T055/T056's
5 tests use fake Sales/Accounting gateways (unit-level) to prove
currency mismatch is impossible *by construction* (asserted via
`inspect.signature()` that `create_draft()` has no `currency_code`
parameter at all, not just that a mismatch gets rejected), and that a
pre-existing partial invoice payment (live outstanding 600 vs. an
original total that could have been anything) correctly drives
`financed_principal`, never a stale full-total figure.

**Third defect found and fixed** (discovered while writing T053/T054's
tests, not part of any single named task but a genuine cross-cutting
gap): `modules/installments/models/__init__.py` was left empty since
Phase 2 — every other module (confirmed via `modules/crm/models/__init__.py`)
explicitly imports every model class there specifically so
`Base.metadata.create_all()` (the SQLite test fixture) and Alembic
autogenerate can resolve inter-model foreign keys regardless of which
test file happens to run first in a given pytest session. Its absence
surfaced as an intermittent `NoReferencedTableError` for
`installment_contracts.plan_template_id`'s FK whenever a test file
imported only `models.contract` without also (accidentally) importing
`models.plan_template` first. Fixed at the source (populated
`models/__init__.py` with all 6 models, matching CRM's exact
convention) rather than patching each affected test file individually
with a defensive import — the correct, permanent fix, verified across
both previously-failing test files plus the full regression suite.

Ran the full Installments regression (37 passed) and, since this phase
extended a widely-used Accounting file, the **full** Accounting
regression — unit, repository, and API/E2E, not just an AR-scoped
subset — 513 passed, 0 failed (two independent redundant confirmations
of the API-only subset also came back 177/177 clean). A live-HTTP smoke
test (throwaway, not committed) exercised the full request/response
cycle for every new endpoint via `TestClient` with fake gateways wired
through FastAPI's `dependency_overrides` (avoiding the need to seed
deep Sales/Accounting prerequisite rows just for a routing/schema-
validation proof, since the business logic itself is already proven by
the unit/integration suites) — all correct status codes (200/201/404/409)
and payload shapes.

Full diff review (`git status`/`git diff --stat`) confirmed only
Phase-3-scoped files changed: the new contract model/repository/
services/schemas, the extended `dependencies.py`/`router.py`, the
now-populated `models/__init__.py`, the two additive AR-service
methods, and 4 new test files. No `models/schedule.py`,
`services/idempotency_service.py`, or any named lifecycle-transition
method (`submit()`/`approve()`/etc.) exists anywhere in the diff —
confirmed no Phase 4/5 leakage.

## Outcome

- ✅ Impact: Phase 3 (T043-T056) complete. A draft contract can be
  created against an eligible invoice, with `financed_principal`
  correctly reflecting any pre-existing partial payment via a live
  Accounting read (never a stale duplicate); the one-contract-per-
  obligation invariant is proven race-safe under a genuine real-Postgres
  concurrent-session race, with the loser's raw database error verified
  to carry exactly the signature the service's translation logic
  detects; cross-tenant access is proven indistinguishable from
  non-existence (identical exception type/code/status, not just "both
  404"); contract numbering is gap-free and tenant-scoped (T028's
  locked sequence, reused unchanged). The single controlled
  Installments→Accounting boundary (`AccountingIntegrationGateway`) is
  established and structurally proven closed to `.models`/`.repositories`
  imports — the load-bearing architectural decision the rest of Epic 10
  depends on.
- 🧪 Tests: T053 — 1 passed (real Postgres, re-run 4× for flake-check).
  T054 — 5 passed. T055/T056 — 5 passed. T046's structural boundary — 3
  passed. Full Installments regression — 37 passed. Full Accounting
  regression (unit+repo+API/E2E) — 513 passed, 0 failed. `ruff check` —
  all checks passed.
- 📁 Files: 9 new files under `backend/modules/installments/`, 3
  modified Installments files (`dependencies.py`, `router.py`,
  `models/__init__.py`), 1 modified shared Accounting file
  (`ar_service.py`, 2 additive methods), 4 new test files, `tasks.md`
  checkbox update.
- 🔁 Next prompts: Phase 4 (Schedule Engine, T057-T073) — pure,
  DB/HTTP-independent schedule generation — not started, per the master
  prompt's explicit stop rule.
- 🧠 Reflection: Two of this phase's three real defects were the same
  underlying pattern — a planning document's confident claim ("no new
  method required," "the pre-check is sufficient") turning out to be
  narrower than reality once actually inspected via code, not
  assumption. The corrective instinct both times was the same: find the
  *closest already-proven-correct precedent* (`AdjustmentRepository`'s
  conditional UPDATE; `AccountingAuditLogRepository`'s flush-only
  pattern from Phase 2) and replicate its exact mechanics rather than
  inventing a new one — even when that meant discovering the existing
  platform-wide precedent (`platform_administrator_service.py`) was
  itself weaker than what this specific task demanded, and choosing to
  exceed it deliberately rather than assume "existing convention" is
  always the ceiling. The third defect (empty `models/__init__.py`)
  is a reminder that "smallest viable diff" per-phase work can silently
  skip a boilerplate file every other module treats as mandatory
  scaffolding — worth an explicit checklist item in future phases: does
  this module's `models/__init__.py` import everything, the moment a
  second model file exists?

## Evaluation notes (flywheel)

- Failure modes observed: (1) T046 assumed a public Accounting read
  method existed where only a private/repository one did — fixed with
  two additive public wrappers. (2) T053's "clean 409" requirement
  wasn't met by the pre-check alone — fixed with an `IntegrityError`
  catch-and-translate wrapper, deliberately exceeding a weaker existing
  platform precedent. (3) Empty `models/__init__.py` caused intermittent
  FK-resolution test failures depending on import order — fixed at the
  source, matching CRM's established convention.
- Graders run and results (PASS/FAIL): T053/T054/T055/T056/T046-boundary
  — PASS (14/14); full Installments regression — PASS (37/37); full
  Accounting regression — PASS (513/513); ruff — PASS.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): when a new module's second
  model file is added, immediately populate/update `models/__init__.py`
  in the SAME task rather than deferring it — this phase's defect #3
  would never have occurred if that had been treated as part of every
  model-adding task's own acceptance criteria.
