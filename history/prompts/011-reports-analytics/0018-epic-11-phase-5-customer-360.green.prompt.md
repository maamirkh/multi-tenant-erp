---
id: 0018
title: Epic 11 Phase 5 Customer 360
stage: green
date: 2026-09-19
surface: agent
model: claude-sonnet-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: /sp.implement
labels: ["epic-11", "reports-analytics", "customer-360", "phase-5"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/reports/schemas/customer_360.py
  - backend/modules/reports/services/customer_360_service.py
  - backend/modules/reports/registry/catalog_crossmodule.py
  - backend/modules/reports/router.py
  - backend/tests/unit/modules/reports/test_customer_360_no_blending.py
  - backend/tests/unit/modules/reports/test_customer_360_boundary.py
  - backend/tests/unit/modules/reports/test_customer_360_no_persistence.py
  - backend/tests/unit/modules/reports/test_registry_consistency.py
  - backend/tests/integration/api/v1/reports/conftest.py
  - backend/tests/integration/api/v1/reports/test_customer_360_idor.py
  - backend/tests/integration/api/v1/reports/test_customer_360_partial.py
  - backend/tests/integration/api/v1/reports/test_customer_360_minimum_response.py
  - backend/tests/integration/api/v1/reports/test_customer_360_zero_vs_unavailable.py
  - backend/tests/integration/api/v1/reports/test_customer_360_installments_case_a_b.py
  - backend/tests/integration/api/v1/reports/test_customer_360_independent_tenant_scoping.py
  - backend/tests/integration/api/v1/reports/postgres/test_customer_360_installments_case_b.py
  - backend/tests/integration/api/v1/reports/postgres/test_customer_360_postgres.py
  - specs/011-reports-analytics/tasks.md
tests:
  - pytest tests/unit/modules/reports/ tests/integration/api/v1/reports/ --ignore=postgres (331 passed, 1 pre-existing documented flake)
  - real-Postgres: postgres/test_customer_360_installments_case_b.py + postgres/test_customer_360_postgres.py (2 passed)
  - mypy modules/reports/ + all touched tests (0 errors, 94 files)
  - ruff check / ruff format --check (clean)
---

## Prompt

# DevSphere ERP SaaS

# Epic 11 — Reports & Analytics

## Compact Reusable Implementation Master Prompt

Implement only the requested Epic 11 phase.

Set:

```text
PHASE_TO_IMPLEMENT = 5
```

[Full compact reusable master prompt as supplied by the user via /sp.implement
— identical structure to Phase 4's invocation: authoritative sources to read,
scope (implement only the requested phase, stop before the next),
prerequisite-check requirements, architecture rules, type/financial safety,
the sanctioned source-domain seams (T047/T075/T087 only), the 8-step
implementation method, the Phase 0–10 targeted-testing strategy, failure
rules, git rules, the required Phase N final report format, and the accuracy
rule. Ends with: "Now implement: PHASE_TO_IMPLEMENT = 0. Read the
authoritative files, verify prerequisites, implement the full requested
phase, run targeted/gate-required checks, produce the required report, and
STOP before the next phase."]

## Outline

[/sp.implement's standard 9-step workflow — identical to Phase 4's.]

## User Input

(verbatim, matches the "Prompt" section content above in full.)

## Response snapshot

Verified prerequisites: Phases 0–4 (T001–T159) all `[x]` in tasks.md,
independently re-confirmed by grepping for the first `[ ]` line (T160 —
Phase 5's own start). Read spec.md §20, plan.md §14 (Customer 360 Design,
the exact `SectionState`/`OmittedSection`/`UnavailableSection` snippet),
and every existing Phase 2 adapter/service call needed to source each of
the four sections from an already-authoritative domain call.

Implemented Phase 5 (T160–T177):
- `schemas/customer_360.py` — `SectionState` (3 values) + discriminated
  unions (`Annotated[Present*Section | OmittedSection | UnavailableSection,
  Field(discriminator="state")]`, exactly per plan.md §14's snippet) +
  `Customer360Response` + `Customer360Filter` registry placeholder.
- `services/customer_360_service.py` — `Customer360Service.get()`:
  permission gate before the Sales lookup (T162); Sales' own
  `CustomerService.get_by_id()` via DI, `NotFoundException` propagating
  uncaught (IDOR-safe, T161); four independent section evaluators
  (T163) each checking entitlement before permission (so a disabled
  domain always reports `not_entitled` even if permission is also
  missing); the minimum-useful-response behavior (T164) falls out
  naturally from composing four independently-OMITTED sections, no
  extra branch needed.
- `registry/catalog_crossmodule.py` — registers `crossmodule.customer_360`
  (`execution_kind=COMPOSITE`, registry 44→45) alongside the existing
  `crossmodule.branch_performance` DEFERRED entry; wires
  `COMPOSITE_REPORT_HANDLERS` using the same bound-method-identity fix
  Phase 4 established for `exec.dashboard` (`get_customer_360` pinned
  once at module scope).
- `GET /reports/customer-360/{customer_id}` route.
- 10 new tests (T167–T176): 8 SQLite (unit + integration) + 2 real-Postgres.

**Genuine repository discovery, investigated and reported, not silently
reused**: `modules/crm/services/customer_360_service.py` — CRM's own,
pre-existing, unrelated "Customer 360" composite read model (spec 009-crm
§14/§16/ADR-6) — already exists in the codebase but is never mentioned
anywhere in Epic 11's spec/plan/tasks. Read its full source before
deciding: its one public method, `get_customer_360()`, is monolithic
(Sales+CRM+Accounting composed together in one call, no Installments, no
per-section authorization) — reusing it wholesale would have broken Epic
11's settled section-level compound authorization architecture
(FR-RPT-111). Did not touch it, did not reuse it, and did not treat this
as a blocking contradiction (the two features serve genuinely different
purposes — one CRM-internal, one Reports-cross-module-analytics — and
nothing in Epic 11's architecture is invalidated by its existence).
Instead, sourced the CRM section from CRM's own pre-existing, public,
non-Reports-specific `OpportunityRepository.list_filtered(customer_id=...)`
(via `modules.crm.dependencies.get_opportunity_repository`) — a
repository-level call, following the exact precedent
`sales_adapter.py`'s own pre-existing `_resolve_customer_name()` helper
already established in Phase 2, since CRM is not one of the three
sanctioned T047/T075/T087 seam domains and T174's AST-scan boundary is
explicitly scoped to the Sales identity lookup only.

Other engineering judgment calls, each documented inline in code/tasks.md:
Sales section sums `sales.summary` rows filtered by `customer_id` (same
technique Phase 4's dashboard used for Gross Sales); Accounting AR section
reuses the pre-existing, unmodified `AccountsReceivableService.
get_customer_aging()`, distinguishing `CustomerLedgerNotFoundError` (real
zero) from no `AccountingConfiguration` row (`UNAVAILABLE(not_configured)`)
per FR-RPT-115; Installments section sums `installments.register`/
`installments.aging` rows filtered by `customer_id` in Python (no
`customer_id` param exists on the underlying service methods), bounded by
the same 50,000-row population cap `InstallmentsAdapter` itself uses, with
`InstallmentsServicingContinuityGate.is_allowed()` called explicitly per
report key per this task's own "fail closed" instruction.

A test-fixture gap was found and closed (not a defect, a missing test
utility): no existing helper created a Sales `Customer` row directly for
tests — added `create_sales_customer()` to
`tests/integration/api/v1/reports/conftest.py` (direct model construction;
`category_id` carries no DB-level `ForeignKey`, matching the same
"soft reference" convention already documented for `customer_id`
elsewhere in this Epic).

Targeted evidence: 331/332 unit+integration tests pass (SQLite) — the one
failure is the identical, already-documented (T144) cross-test SQLite
state-leak flake in `test_entitlement_roundtrip.py`, unrelated to Phase 5,
reconfirmed as pre-existing. Both real-Postgres tests
(`postgres/test_customer_360_installments_case_b.py`,
`postgres/test_customer_360_postgres.py`) verified PASS against a live
PostgreSQL 16 instance at migration head `076` (reachable in this sandbox
this session). `mypy`/`ruff` clean on every touched file. Full repository
regression intentionally not run (reserved for Phase 11).

Marked T160–T177 `[x]` in tasks.md with implementation notes, including
the CRM-discovery note and the registry-consistency test rename
(`test_gate_4_registry_shape` → `test_gate_5_registry_shape`, mirroring
Phase 4's own Gate 2→4 rename rationale). Gate 5 declared PASS. Stopped
before Phase 6 pending explicit authorization.

## Outcome

- ✅ Impact: Customer 360 (`GET /reports/customer-360/{customer_id}`)
  implemented end to end — four independently-gated sections (Sales,
  Accounting AR, CRM, Installments) composing one IDOR-safe, tenant-scoped
  read model, zero blended/re-derived formulas. `crossmodule.customer_360`
  registered as the epic's second `COMPOSITE`-kind report. Registry: 45
  NOW (43 ADAPTER + 2 COMPOSITE) + 3 DEFERRED — the final, complete count.
- 🧪 Tests: 10 new tests (8 SQLite + 2 real-Postgres), all passing; 331/332
  broader SQLite reports suite passing (1 pre-existing documented flake,
  non-regression). mypy/ruff clean.
- 📁 Files: 2 new service/schema modules, 1 registry catalog extended, 1
  router extended, 10 new test files, 1 conftest extended with a new
  fixture helper, 1 pre-existing Phase 4 test file extended (registry
  shape), tasks.md updated.
- 🔁 Next prompts: Phase 6 (Exports & Audit) on explicit authorization.
- 🧠 Reflection: discovering CRM's own pre-existing, unrelated Customer 360
  service mid-implementation was the notable event this phase — reading
  its full source before deciding NOT to reuse it (rather than either
  blindly wiring it in or stopping to ask) was the right call given it
  didn't actually block or contradict Epic 11's settled architecture, only
  ruled out one convenient-looking shortcut.

## Evaluation notes (flywheel)

- Failure modes observed: none new — reapplied the bound-method-identity
  fix Phase 4 already discovered for `COMPOSITE` registry entries.
- Graders run and results (PASS/FAIL): targeted pytest (SQLite + real
  Postgres) + mypy + ruff — PASS; full regression deliberately deferred to
  Phase 11.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a — Phase 5 was the last
  `COMPOSITE`-registration phase; Phase 6 onward returns to `ADAPTER`-only
  concerns (export/audit).
