---
id: 0013
title: Epic 11 Phase 2 Installments branch filter correction
stage: refactor
date: 2026-09-13
surface: agent
model: claude-sonnet-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: null
labels: ["epic-11", "reports-analytics", "phase-2", "installments", "branch-filter", "gate-2", "correction"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/reports/schemas/installments.py
 - backend/modules/reports/registry/catalog_installments.py
 - backend/modules/reports/services/adapters/installments_adapter.py
 - backend/tests/unit/modules/reports/test_installments_branch_filter.py
tests:
 - tests/unit/modules/reports/test_installments_branch_filter.py (16, rewritten to prove rejection)
 - tests/unit/modules/reports/ (213 total, all passing)
 - tests/unit/modules/reports/test_registry_consistency.py (48, Gate-2 shape unchanged)
 - tests/integration/api/v1/installments/test_installments_accounting_reconciliation.py (1, real Postgres)
 - mypy . (1410 files, 0 errors)
 - ruff check . (all checks passed)
---

## Prompt

Before starting Phase 3, correct the remaining Phase-2 Installments branch-filter contract.

The current Phase-2 report states that branch_id is accepted by the schemas for five Installments reports but is not functionally wired because Installments is not one of the sanctioned source-domain seam modules.

This must not remain as silent accept-and-ignore behavior.

Re-read the approved Epic 11 spec/plan/tasks branch semantics. Branch is only an optional data filter where the underlying approved source contract can genuinely support it; Epic 11 must not invent branch authorization or an unsanctioned fourth source-domain seam.

Make the smallest Phase-2 correction:
- If those Installments reports cannot actually honor branch_id through their existing approved public service contracts, remove branch_id from their supported filter contract/catalog/schema or explicitly reject it as unsupported.
- Do NOT add a new Installments source-domain seam.
- Do NOT implement Phase 3.
- Update the relevant Phase-2 tests so they prove branch_id cannot be silently accepted and ignored.
- Run only the directly affected Reports/Installments tests plus mypy/ruff if required.
- Update the Phase-2 report and Gate 2 evidence.
- STOP before Phase 3.

Return only the correction report and final Gate 2 PASS/BLOCKED verdict.

## Response snapshot

Re-read spec.md §25 (FR-RPT-160/161/162/163). FR-RPT-162 is decisive: a filter that cannot genuinely be honored MUST NOT be exposed at all — offering a no-op/silently-ignored filter misrepresents capability. Confirmed `InstallmentReportingService` (the only approved public source contract for these 7 reports) has no `branch_id` parameter on any method, even though the underlying `InstallmentContract` model carries the column — the column's existence alone doesn't satisfy FR-RPT-160 without a real service-layer path to apply it, and Installments remains outside the 3 sanctioned T047/T075/T087 seams, so no new seam was added.

Correction applied (removal, not runtime-rejection-plus-field, since that most closely mirrors the existing Sales/Accounting/CRM "no branch_id field at all" precedent under FR-RPT-162):
- Removed `branch_id` from all 5 previously-branch-linked filter schemas (`ContractRegisterFilter`, `CollectionsFilter`, `DueOverdueFilter`, `InstallmentAgingFilter`, `SettlementWriteoffFilter`) in `schemas/installments.py`; removed the now-unused `UUID` import.
- Flipped `branch_filterable=True` → `False` for all 5 in `catalog_installments.py`; also fixed `_CONTRACT_DRILL_DOWN.preserves_filters=("branch_id",)` → `()`, since it referenced a filter field that no longer exists (would have violated FR-RPT-182).
- Rewrote the adapter's module docstring to state the corrected contract plainly.
- Fully rewrote `test_installments_branch_filter.py`: it now proves, for all 7 report keys, that `branch_id` is not a field on any filter schema AND that passing it raises `pydantic.ValidationError` (since every schema is `extra="forbid"`) — a hard 422 at the API layer, never a silently-dropped value. Also added registry-level assertions that no Installments entry claims `branch_filterable=True` and no drill-down target's `preserves_filters` references `branch_id`.

Verified: all 213 Reports unit tests pass (up from 200 — net new assertions from the rewritten test), Gate 2's registry-shape test (48 tests) still passes unchanged (43 NOW / 3 DEFERRED — report count and domain breakdown are untouched, only a filter field was removed), the real-Postgres Installments↔Accounting reconciliation test still passes (it never used `branch_id`), `mypy .` clean across 1410 files, `ruff check .` clean.

## Outcome

- ✅ Impact: Closed a genuine silent-accept-and-ignore gap in the Installments branch-filter contract — corrected without adding a 4th source-domain seam or inventing branch authorization, per FR-RPT-160/162.
- 🧪 Tests: 16/16 rewritten branch-filter tests pass; 213/213 full Reports suite passes; 48/48 registry-consistency/Gate-2-shape tests pass; 1/1 real-Postgres reconciliation test passes; mypy 0 errors; ruff clean.
- 📁 Files: 3 modified (`schemas/installments.py`, `registry/catalog_installments.py`, `services/adapters/installments_adapter.py`), 1 test file fully rewritten.
- 🔁 Next prompts: Await explicit authorization, then `/sp.implement PHASE_TO_IMPLEMENT = 3`.
- 🧠 Reflection: The original Phase-2 choice to "accept but document as inert" was a defensible transparency move in isolation, but the user correctly identified it violated FR-RPT-162's actual requirement once held against the spec text directly — removal (matching the existing Sales/Accounting/CRM no-field precedent) is the smaller, more spec-faithful fix than adding a runtime-rejection branch to an adapter that otherwise has zero filter-validation logic of its own.

## Evaluation notes (flywheel)

- Failure modes observed: an "accept the field, document as inert" shortcut is not equivalent to explicit rejection and drifts from FR-RPT-162's letter even when transparently reported — schema removal (or a real 422) is required, not just prose.
- Graders run and results (PASS/FAIL): mypy PASS, ruff PASS, targeted branch-filter suite PASS (16/16), full Reports suite PASS (213/213), Gate-2 shape PASS.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a — awaiting Phase 3 authorization.
