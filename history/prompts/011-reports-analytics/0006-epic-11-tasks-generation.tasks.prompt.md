---
id: 0006
title: Epic 11 tasks generation
stage: tasks
date: 2026-09-11
surface: agent
model: claude-sonnet-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: /sp.tasks
labels: ["reports-analytics", "tasks", "planning", "installments", "exports", "customer-360"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/011-reports-analytics/tasks.md
tests:
 - None executed (planning-only phase; no code/migrations created — task file only)
---

## Prompt

/sp.tasks was invoked with a full 86-section governing prompt titled "Epic 11 — Reports & Analytics: Full & Final `tasks.md` Generation Prompt" (verbatim below), followed by the sp.tasks skill's standard Outline/Task-Generation-Rules wrapper, which re-embedded the identical governing-prompt text a second time as "Context for task generation" (omitted here to avoid duplicating several thousand words of byte-identical content — the governing prompt below is the complete, unabridged, verbatim instruction the user provided; the wrapper added no additional instructions beyond the standard sp.tasks skill scaffolding: run `check-prerequisites.sh`, load design documents, generate tasks organized by phase, and the standard checklist-format rules).

# DevSphere ERP SaaS

# Epic 11 — Reports & Analytics

## Full & Final `tasks.md` Generation Prompt

You are continuing work on the existing **DevSphere ERP SaaS** repository.

Epic 11 has completed:

* specification;
* specification correction/audit;
* implementation planning;
* plan correction/audit.

The following artifacts are now approved and authoritative:

```text
specs/011-reports-analytics/spec.md
specs/011-reports-analytics/plan.md
```

Your task is to create the **final implementation task breakdown** for:

# Epic 11 — Reports & Analytics

Create:

```text
specs/011-reports-analytics/tasks.md
```

This must be an **implementation-ready, dependency-correct, final task plan**.

The goal is to make `tasks.md` strong enough that implementation can proceed phase-by-phase **without needing a later task-rewrite or task-correction pass**.

Therefore:

> Do not merely generate tasks once.

You MUST:

1. inspect repository reality;
2. derive tasks from both approved `spec.md` and `plan.md`;
3. generate the full task graph;
4. run an internal second-pass dependency and coverage audit;
5. correct all issues you discover;
6. only then present the final `tasks.md`.

Do NOT implement Epic 11.

---

# 1. GOVERNING SOURCES

Use these in authority order:

1. Project Constitution.
2. Approved Epic 11 `spec.md`.
3. Approved Epic 11 `plan.md`.
4. Current repository implementation.
5. Existing completed epics' task conventions.

The plan may contain implementation-specific assumptions that still require repository verification.

If current repository reality differs from a literal implementation detail in the plan:

* preserve the plan's architecture and business intent;
* use the actual repository API/path/type;
* document the adjustment;
* do NOT invent unavailable infrastructure.

Do not silently weaken the specification.

---

# 2. CURRENT VERIFIED BASELINE

[... 84 further numbered sections specifying: verified baseline preservation of `mypy . = 0`; task-generation-only scope (no code/migrations/packages/ADRs during this phase); a final-quality requirement demanding zero "TBD"/"refine later" language; mandatory repository re-discovery across backend module structure, Alembic head, Capability catalogue, entitlement resolver, router composition, permission constants/seed pattern, TenantBaseModel, audit conventions, response/pagination envelopes, all six domain services' actual public methods, and the full frontend stack (routing, auth, API client, TanStack Query, test runner, package manager, Recharts absence); a strict task-ID/format/`[P]`-marking specification; an executable-task-content requirement; task-granularity guidance; a mandatory forward-dependency audit; the required 12-phase structure (Foundation, Saved Views, Domain Adapters in Accounting→Sales→Purchase→Inventory→CRM→Installments order, Unified Execution API, Executive Dashboard, Customer 360, Exports & Audit, Frontend Foundation, Domain Report Pages, Dashboard+Customer 360 UI, Security/Postgres/Reconciliation/Performance Hardening, Regression/Docs/Release Readiness) with exhaustive per-phase content requirements; explicit migration-numbering re-verification instructions; capability/feature-flag task requirements; a full Installments servicing-continuity task section locking the five-report Case-B allow-list (`register, collections, due_overdue, aging, settlement_writeoff`) and explicitly excluding `plan_performance`/`dashboard`; an instruction to re-verify whether `get_contract_register(..., limit=1)` remains the cleanest obligation-existence seam; per-adapter task patterns for every domain including explicit Accounting statement/AR/AP/KPI/PDF coverage, GL cursor-specific tasks, Sales/Purchase/Inventory/CRM adapter requirements (including Inventory's mandatory `valuation_basis="operational_wac"` labeling and the prohibition on resolving ADR-0004), registry and registry-consistency-test requirements (explicitly warning against a brittle `inspect.signature()` check that would reject legitimate adapter translation), execution-service (`_authorize_and_validate()`/`execute()`) task requirements, discovery-endpoint requirements, saved-view task requirements (soft-delete-only, explicitly), a fully broken-down Customer 360 task section (base gate, four sections, three section states, required semantics, test matrix) with an explicit **critical instruction to verify the Customer 360 Sales customer-master lookup against the modular-monolith cross-module-repository-import prohibition, and to use a Sales-owned service instead of `CustomerRepository.get_by_id` if that boundary rule applies** (§60/§61 of the governing prompt); Executive Dashboard task requirements; a fully broken-down export task section covering the shared authorization preamble, `count_export_rows()`/`iter_export_rows()` seams, the hard bounded-retrieval-before-fetch invariant, CSV/XLSX/PDF-specific tasks, export-audit-durability tasks (explicitly requiring `ExportAuditPersistenceError`/`EXPORT_AUDIT_FAILED` and a simulated-audit-failure integration test), and **explicit instructions (§62/§63) to inspect each wrapped report API's actual count/pagination capability rather than assuming a universal cheap-count implementation, and to distinguish list reports, aggregate summaries, financial statements, and dashboard metrics rather than forcing aggregate reports into row-count semantics**; audit-model tasks; date/comparison/money/branch task requirements; a frontend dependency task for Recharts (not installed during generation) plus full frontend architecture, accessibility, navigation, and per-domain page tasks; a test-alongside (not test-deferred-to-Phase-10) strategy requirement; real-PostgreSQL and migration-test task requirements; a full security-matrix and Platform-Admin-boundary task requirement; financial-invariant and performance-task requirements (explicitly forbidding brittle wall-clock CI gates); export-limit-benchmarking tasks using "exceeds configured synchronous export limit" wording rather than a hardcoded number in test descriptions; backward-compatibility, type-safety, and code-quality task requirements; an explicit instruction (§64) to **enumerate and count the actual `reports.*` permission list from spec.md rather than trust the plan's stale "13 codes" claim, and to correct the count without dropping entries**; traceability and three separate coverage-matrix requirements (FR-RPT-* requirement coverage, report-catalog coverage mapping every "Now" report from source-service through adapter/registry/API/frontend, and acceptance-scenario A–O coverage); a Deferred-catalog audit requirement; task-count-quality guidance (no arbitrary target, correctness over count); a no-placeholder/no-TODO requirement; a "0 blocking open questions unless a genuine repository blocker exists" requirement; an exhaustive, 18-point **mandatory second-pass self-audit** (dependency, parallelization, spec/plan/report-catalog/security/Installments/Customer-360/migration/type/export/saved-view/frontend/test/gate/requirement-ID/file-conflict/deferred-scope audits) that must be performed and corrected *before* the report is returned, not merely acknowledged; a third "task graph sanity pass"; a set of ten execution rules to embed at the top of `tasks.md`; a completion-evidence-format specification for phase gates; a final-release-gate specification (exact repository-appropriate ruff/mypy/pytest/migration/frontend-build/regression/security/repository-hygiene commands, discovered rather than assumed); git/commit-preparation tasks (no push during generation); PHR/history and ADR-consent-checkpoint task requirements (explicitly forbidding automatic ADR creation); a required 20-point `tasks.md` document structure; a required final-report structure (Files Created/Modified, Repository Re-Discovery, Task Count, Phase Breakdown, Critical Dependency Decisions, Type Safety, Installments, Customer 360 Boundary, Export Architecture, Permissions, Coverage, Parallelization Audit, Forward Dependency Audit, Open Questions, Git Status, Final Verdict as exactly `EPIC 11 TASKS READY FOR IMPLEMENTATION` or `EPIC 11 TASKS BLOCKED`); an absolute stop condition (no T001 execution, no migrations, no package installs, no unconsented ADRs, no Epic 12, no AI work); and a closing 28-item "FINAL QUALITY BAR" yes/no checklist that must all be answerable YES before returning the ready verdict. ...]

*(The complete, unabridged text of all 86 sections was provided verbatim in the user's actual message and was read and acted upon in full; it is compressed here only to avoid reproducing several thousand words of already-actioned instruction a second time inside this history record — every numbered requirement listed above was individually addressed in `tasks.md` and is traceable to a specific task ID or task-file section, as documented in the Response snapshot below and in `tasks.md`'s own "Final Readiness Statement.")*

## Response snapshot

Ran `.specify/scripts/bash/check-prerequisites.sh --json` (confirmed `research.md`/`data-model.md`/`contracts/`/`quickstart.md` all present alongside the approved `plan.md`/`spec.md`), then dispatched a single thorough repository-re-discovery pass (foreground Explore agent) covering exactly the items the governing prompt flagged as needing re-verification rather than blind trust in `plan.md`'s text:

1. **`backend/modules/reports/` confirmed absent** (green field).
2. **Migration head confirmed still `072`** (`072_installments_requires_review.py`) — Epic 11's four migrations (`073`–`076`) chain correctly from it.
3. **Customer 360 cross-module boundary corrected**: `plan.md` had proposed calling Sales' `CustomerRepository.get_by_id(...)` directly. Constitution §12/§13 forbid this. Discovery found a public Sales **service** method already exists — `CustomerService.get_by_id(company_id, customer_id)` (`backend/modules/sales/services/customer_service.py:199-204`), the same method Sales' own `GET /customers/{customer_id}` route already calls — and confirmed the exact structural precedent for this class of cross-module call already exists (`InstallmentAccessPolicy`'s sibling, Installments' `AccountingIntegrationGateway`, which imports only Accounting's *services*, enforced by a dedicated structural test). Also discovered **no `sales.customers.view` permission exists anywhere in Sales** — the plan's assumption for gating Customer 360's identity-only fallback was unfounded; resolved by using tenant-membership-scoped lookup success as the gate (identical to what Sales' own detail page already requires), documented explicitly as a repository-reality correction rather than silently substituted.
4. **Per-adapter export-count capability enumerated precisely, not assumed universal**: confirmed which of the six domains' wrapped report methods have a genuine cheap SQL-COUNT (Sales all reports, Installments' `register`/`collections`/`settlement_writeoff`/`default_writeoff`, Inventory's `stock_ledger`), which are cursor-only with no total ever (Accounting's `get_gl_report`), which return a full unpaginated list with no count/limit parameter at all (Purchase's entire report service, Inventory's `stock_position_report`, Accounting's bank/cash books), and which are aggregate/fixed-shape with no "rows" concept at all (all CRM reports, Accounting's four statements + AR/AP aging/statements, several Inventory aggregates, Installments' `plan_performance`/`dashboard`). This directly informed four materially different export-retrieval task patterns (cheap-count, cursor-native, full-fetch-then-guard, bounded-population-then-slice) rather than one misleading universal `count_export_rows()` implementation.
5. **Frontend test runner confirmed**: Jest + `@testing-library/react` + Playwright, npm as package manager (`frontend/package.json` scripts `test`/`test:ci`/`e2e`) — used throughout every frontend test task, never left as a placeholder.
6. **Permission count corrected**: enumerated spec.md §33's table precisely — **16** distinct `reports.*` codes, not the plan's stale "13 codes" claim (1 executive + 12 view/export pairs across six domains + customer_360.view + branch_performance.view + saved_view.manage). Used the actual 16-entry list throughout, with the discrepancy documented explicitly in `tasks.md`'s baseline section.
7. **Backend/CI commands confirmed** (`poetry run ruff check .`, `poetry run ruff format --check .`, `poetry run mypy .`, the exact `pytest --cov=... --cov-fail-under=80` invocation from `.github/workflows/backend.yml`) — used verbatim in Phase 11's release-gate tasks.
8. **`RoleSeedService`/`INITIAL_PERMISSIONS` exact append syntax confirmed** (`INSTALLMENTS_PERMISSIONS` tuple pattern, union at the `INITIAL_PERMISSIONS` closing line) — replicated exactly for `REPORTS_PERMISSIONS`.

Produced `specs/011-reports-analytics/tasks.md`: 296 tasks (T001–T296) across 12 phases with 12 explicit gate tasks, organized by the plan's own phase structure (not user-story labels, since Epic 11 is architecturally phased and documented as such in the file's own opening rationale). Phase 2 (Domain Adapters, T048–T133) is the largest, covering all 45 "Now" report keys across six domains in the mandated Accounting→Sales→Purchase→Inventory→CRM→Installments order, each with typed filter/response schemas, adapter implementation, registry entries, contract tests, source-equivalence/reconciliation tests, and domain-appropriate export-seam tasks reflecting the four distinct retrieval patterns discovered above. The Installments sub-phase (T111–T128) implements the `InstallmentsServicingContinuityGate` with its explicit five-report Case-B allow-list and a dedicated unit test individually asserting `plan_performance`/`dashboard` are denied. Phase 5 (Customer 360, T164–T182) uses the corrected `CustomerService.get_by_id` boundary with a dedicated structural AST-scan test (T179) proving no repository/model import ever occurs. Phase 6 (Exports & Audit, T183–T220) implements the shared `_authorize_and_validate()` preamble reused by both `execute()` and `export()`, the four export-retrieval patterns, a dedicated GL mid-stream-abort pattern for its cursor-only shape, and — the single most emphasized test in the governing prompt — a simulated audit-commit-failure integration test (T212) proving zero successful file delivery when the audit transaction fails to commit.

Performed the mandated internal second-pass audit before finalizing: grepped the completed file for stray placeholders (`TBD`/`TODO`/etc. — found only the word "TBD" appearing three times, each inside a sentence explicitly stating something is *not* TBD, i.e. false positives, not actual placeholders), verified all 296 task IDs are unique with no gaps (`T001`–`T296`, `grep -c` on both the ID pattern and the checkbox-line count agreeing exactly), and audited every `[P]`-marked task for shared-file conflicts — found and corrected one genuine defect: T132 (the registry-catalog import checkpoint task, which aggregates all six prior domain catalogs) was marked `[P]` despite its own description explicitly stating it should not be parallel; removed the `[P]` marker. No other `[P]` marking or forward-dependency defect was found on this second pass. Removed one leftover drafting artifact (a stray "T134–T145 intentionally reserved" note that was factually incorrect — there is no gap; Phase 3 begins immediately at T134 after Phase 2 ends at T133).

Included all three required coverage matrices (FR-RPT-* requirement coverage with zero orphans and one explicit `DEFERRED` mapping for the AI-readiness family per NG6; a report-catalog matrix mapping all 45 "Now" reports from adapter task → registry task → API/test task → frontend task; and an acceptance-scenario A–O matrix with zero orphans), a Deferred-scope verification table (confirming `accounting.tax`/`accounting.cost_center_pl`/`crossmodule.branch_performance` are registered only as unreachable `DEFERRED` stubs, and that the ~30 un-enumerable "remaining variant" rows from spec §9 have no registry entry of any kind), a complete expected-file map (new files + exactly four additive existing-file edits, matching `plan.md`'s own backward-compatibility guarantee), and a Final Readiness Statement walking through every item of the governing prompt's closing 28-point quality-bar checklist.

Created this PHR. No `tasks.md`-adjacent code, migration, or package was created or installed, per the absolute stop condition.

## Outcome

- ✅ Impact: Complete, repository-verified, dependency-audited 296-task implementation breakdown for Epic 11 produced in one file; zero forward-dependency defects remaining after self-audit; zero blocking open questions; ready for `/sp.implement` or manual execution starting at T001.
- 🧪 Tests: None run — task-generation-only phase, no code changes made. Every task in the file states its own required test evidence.
- 📁 Files: `specs/011-reports-analytics/tasks.md` (created, then corrected once via Edit to remove a stray `[P]` marker and a leftover drafting note).
- 🔁 Next prompts: Human review of `tasks.md`; upon approval, begin implementation at T001 (or `/sp.implement` if that command drives task execution in this workflow); the two ADR suggestions from `plan.md` §37 surface for consent at T291, not before.
- 🧠 Reflection: The most valuable discovery this pass was that the export-row-count capability is genuinely non-uniform across the six wrapped domains — a naive `count_export_rows()` design (reusing a `total` field wherever `total` happens to exist) would have silently produced an incorrect/misleading implementation for Purchase, several Inventory reports, and Accounting's bank/cash books, none of which expose any count or pagination parameter at all. Distinguishing four genuinely different retrieval patterns (cheap-count, cursor-native, full-fetch-then-guard, bounded-population-then-slice) rather than one universal pattern is exactly the kind of repository-reality check the governing prompt's re-discovery mandate was designed to force, and it materially changed several task descriptions from what a plan-text-only reading would have produced.

## Evaluation notes (flywheel)

- Failure modes observed: One genuine self-audit catch (T132's contradictory `[P]` marker), corrected before finalization — exactly the class of defect the mandated second-pass audit exists to catch. No other forward-dependency, coverage, or consistency defect survived the audit.
- Graders run and results (PASS/FAIL): Not applicable — no automated grading harness invoked; self-validated via the governing prompt's own 28-item quality-bar checklist, walked through explicitly in `tasks.md`'s "Final Readiness Statement" section, and via direct `grep`/`wc` verification of task-ID uniqueness (296 unique IDs, 296 checkbox lines, exact match) and placeholder absence.
- Prompt variant (if applicable): N/A (single-pass execution of the provided 86-section governing prompt, with one internal self-correction cycle as explicitly mandated by the prompt itself).
- Next experiment (smallest change to try): During implementation of Phase 2's Purchase/Inventory "full-fetch-then-guard" export tasks (T085, T098), confirm empirically (not just by code inspection) that the mandatory max-date-range filter bounds chosen here (366 days / 90 days, T080) actually keep worst-case fixture-scale fetches within acceptable memory bounds — if not, tighten the bound rather than relaxing the export row limit, to preserve the "bounded before uncontrolled retrieval" invariant.
