---
id: 0005
title: Epic 11 plan correction pass
stage: plan
date: 2026-09-11
surface: agent
model: claude-sonnet-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: /sp.plan
labels: ["reports-analytics", "planning", "type-safety", "installments", "exports", "audit", "saved-views"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/011-reports-analytics/plan.md
tests:
 - None executed (planning-only correction pass; no code/migrations created)
---

## Prompt

# DevSphere ERP SaaS

# Epic 11 — Reports & Analytics

## Final `plan.md` Correction Pass Before `tasks.md`

You are continuing work on:

`specs/011-reports-analytics/plan.md`

The Epic 11 plan is already structurally strong and has passed the main architecture/security/design audit.

This is a **targeted correction pass only**.

Do NOT rewrite the plan from scratch.

Do NOT create:

* `tasks.md`
* implementation code
* migrations
* models
* services
* routers
* frontend code
* tests
* ADR files
* Epic 12 work
* AI work

Only correct the four remaining plan issues below, revalidate plan readiness, return the correction report, then STOP.

---

# 1. REMOVE / CONTAIN `Any` FROM THE REPORTS TYPED BOUNDARY

The plan currently defines:

```python
class ReportAdapter(Protocol):
    def run(...) -> ReportResult[Any]:
        ...
```

while the plan also promises:

* fully typed Reports contracts;
* no `Any` escape hatches;
* `mypy . = 0`;
* source-domain `dict[str, Any]` shapes normalized at the adapter boundary.

These statements must be made consistent.

## Required correction

Do NOT allow `Any` to escape beyond a concrete domain adapter.

Existing source services may internally return:

* `dict[str, Any]`;
* `list[dict[str, Any]]`;
* other weakly typed legacy shapes.

That is existing domain reality.

However:

**Reports' public/internal orchestration boundary must become typed after adapter normalization.**

Use a type-safe design such as:

### Preferred option

A generic Protocol:

```python
ReportResultT_co = TypeVar(
    "ReportResultT_co",
    bound=BaseReportResult,
    covariant=True,
)

class ReportAdapter(Protocol[ReportResultT_co]):
    def run(...) -> ReportResultT_co:
        ...
```

with concrete typed result models.

or another repository-compatible design that achieves the same outcome.

A finite typed union is also acceptable if cleaner, for example:

* aggregate report result;
* paginated report result;
* cursor report result.

## Important

Do NOT introduce:

* broad `Any`;
* `cast(Any, ...)`;
* `# type: ignore` as architecture;
* untyped dispatch;
* dynamic eval/getattr tricks.

`Any` from legacy wrapped services may exist **inside the concrete adapter's translation implementation only**, where it is immediately validated/coerced into a typed Pydantic/domain result.

After that normalization point, no `Any` should cross the Reports orchestration boundary.

Update:

* §10 Domain Adapter Strategy;
* §32 Type Safety;
* relevant module/file layout notes;
* tests/gates if necessary.

---

# 2. RESTRICT INSTALLMENTS CASE B TO TRUE SERVICING-CONTINUITY REPORTS

The current plan interprets Case B as allowing every "Now" Installments report, including:

`installments.plan_performance`

because it is technically read-only.

This is wider than the approved specification's servicing-continuity intent.

The approved rule preserves only the visibility required to explain and service **existing obligations** after Installments has been disabled.

## Required correction

Create an explicit Case-B report allow-list.

At minimum, servicing-continuity reporting should include reports needed to explain existing obligations, such as:

* contract register;
* existing contract detail/schedule visibility;
* due / overdue;
* aging;
* collections;
* settlement/default/write-off history;
* servicing-related dashboard figures tied directly to existing obligations.

Do NOT automatically expose unrelated analytics simply because they are read-only.

Specifically:

`installments.plan_performance`

must NOT be available under Case B unless the approved specification is explicitly amended later.

When Installments is fully entitled, all approved "Now" Installments reports remain available normally.

When Installments is disabled:

### Case A

No serviceable obligations:

* all `installments.*` Reports surfaces unavailable.

### Case B

Existing serviceable obligations:

* only the explicit servicing-continuity allow-list remains available read-only.

Update:

* §13 Installments Servicing-Continuity Design;
* execution logic;
* dashboard semantics if needed;
* Customer 360 semantics;
* test matrix;
* phase gates.

Do not modify Installments business logic itself unless implementation discovery later proves a small public seam is genuinely required.

---

# 3. CLARIFY EXPORT EXECUTION, BATCHING/STREAMING, AND AUDIT COMMIT SEMANTICS

The current plan correctly says export must reuse the same report execution/security path as the online view.

However, wording around:

> "pagination replaced by a full-scope count-then-fetch"

is too ambiguous and could encourage loading 25k–50k rows into one Python list.

That must not be the architecture.

## Required correction

Separate the concerns clearly.

### Authorization / validation path

Export MUST reuse the same:

* report lookup;
* `reports` entitlement;
* domain entitlement;
* Installments Case A/B rule;
* RBAC;
* filter validation;
* sort validation;
* branch semantics;
* authoritative adapter;

as the normal online report path.

Do NOT implement a parallel security path.

### Export row retrieval

Define an explicit bounded export retrieval seam.

Possible shape:

```python
count_export_rows(...)
iter_export_rows(...)
```

or:

```python
export_batches(...)
```

or another typed equivalent.

The key invariants are:

* row limit checked before uncontrolled retrieval;
* CSV must be capable of bounded/chunked or streaming-style generation;
* do not materialize the entire maximum-size CSV result set in memory merely for convenience;
* XLSX may require more in-memory workbook state, so its configured limit can be lower;
* GL cursor pagination must be consumed iteratively rather than artificially converted into one giant offset query;
* exports must preserve stable ordering and exact filter scope.

Do not introduce async/background jobs in Epic 11.

### CSV

Plan chunked/iterative row writing.

If the framework ultimately returns final `bytes`, that is acceptable only if row retrieval itself remains bounded and memory behavior is explicitly controlled.

If a streaming HTTP response better fits repository conventions, plan may note it as an implementation option — but do not add unnecessary architecture unless supported by the repo.

### XLSX

Use bounded input iteration and the selected openpyxl write strategy.

Benchmark determines final row ceiling.

### PDF

Continue reusing Accounting's existing PDF path only where already supported.

---

# 4. EXPORT AUDIT MUST BE DURABLE BEFORE FILE RELEASE

Clarify transaction semantics.

An export is a data-exfiltration event and the approved specification requires an audit record.

Therefore:

**A successfully delivered export must have a successfully persisted audit record.**

Required behavior:

1. authorize/validate;
2. obtain bounded report data;
3. generate export successfully;
4. create export audit record;
5. commit audit transaction successfully;
6. only then release/return the file response.

If audit persistence/commit fails:

* fail the export request;
* do NOT deliver the file;
* return the documented internal/service error envelope;
* do not pretend the export succeeded.

Do not attempt distributed transactions with the client response.

The invariant is simply:

> no successful file delivery without durable export audit persistence.

Update:

* §21 Exports;
* §22 Audit;
* error/failure behavior;
* tests;
* export phase gate.

Add a test that simulates audit persistence failure and confirms no successful export response is produced.

---

# 5. FIX SAVED-VIEW DELETE SEMANTICS

The plan currently contains contradictory wording:

* "Deletion is a hard delete"
* then describes the standard soft-delete mechanism inherited from `TenantBaseModel`.

Choose exactly one.

## Required final decision

Use:

**soft delete**

because `SavedReportView` inherits `TenantBaseModel` and the repository already has lifecycle fields/conventions.

Final semantics:

* DELETE marks the view deleted using repository-standard soft-delete behavior;
* deleted views are excluded from normal list/load;
* owner isolation remains enforced;
* no restore UI/API is required in Epic 11;
* no physical hard-delete path is introduced in normal Reports API.

Update §15 and related persistence/tests wording.

---

# 6. REVALIDATE TYPE-SAFETY CLAIMS

After fixing item #1, search the plan for:

* `Any`
* `ReportResult[Any]`
* `dict[str, Any]`
* `list[dict`
* "no Any"
* "fully typed"
* "typed boundary"

Make sure the final plan clearly distinguishes:

### Existing legacy domain-service internals

May return weak shapes such as `dict[str, Any]`.

### Reports adapter normalization boundary

Must convert those shapes into typed Reports models immediately.

### Reports orchestration/public contracts

Must remain fully typed.

Do not falsely claim the underlying legacy modules contain no `Any`.

The claim is only that Epic 11 does not propagate their weak typing into its own contracts.

---

# 7. REVALIDATE INSTALLMENTS WORDING EVERYWHERE

Search plan for:

* Case A
* Case B
* servicing continuity
* `plan_performance`
* every "Now" Installments report
* Installments dashboard
* Customer 360 Installments
* Installments test matrix

Ensure no text still says all read-only Installments analytics remain available in Case B.

One rule everywhere:

**Case B exposes only the explicit servicing-continuity read allow-list.**

---

# 8. REVALIDATE EXPORT WORDING EVERYWHERE

Search for:

* full-scope fetch
* count-then-fetch
* export rows
* 50,000
* 25,000
* CSV
* XLSX
* cursor
* audit commit
* transaction
* successful export

Ensure no wording implies:

* loading an unbounded/full result graph;
* bypassing the normal authorization/filter execution path;
* returning a file before audit durability is known.

---

# 9. UPDATE TEST PLAN

At minimum add/confirm tests for:

## Type boundary

* weak legacy service payload normalized into a typed adapter result;
* no `Any` needed in Reports consumer code;
* `mypy . = 0`.

## Installments

* fully entitled → all approved Now reports accessible;
* Case A → all unavailable;
* Case B → servicing allow-list available;
* Case B → `installments.plan_performance` unavailable;
* dashboard servicing widget behavior correct;
* Customer 360 Installments section behavior correct.

## Export

* CSV retrieval uses bounded batches/iteration;
* row limit rejected before excessive retrieval;
* GL export iterates its cursor safely;
* XLSX limit independently enforced;
* CSV formula injection neutralized;
* export permission distinct from view;
* audit record written exactly once;
* audit commit failure → no successful file response.

## Saved views

* delete performs soft delete;
* deleted view excluded from list/load;
* another tenant/user cannot discover deleted row through ID probing.

---

# 10. PHASE GATE ADJUSTMENTS

Update relevant gates.

### Domain Adapter Gate

Must prove typed normalization boundary; legacy `Any` does not escape adapters.

### Installments Gate

Must prove explicit Case-B allow-list.

### Export Gate

Must prove:

* bounded retrieval;
* no data widening;
* independent row limits;
* formula injection protection;
* durable audit before file release;
* audit failure prevents successful export.

### Saved Views Gate

Must prove repository-standard soft-delete semantics.

---

# 11. DO NOT EXPAND SCOPE

Do not use this correction pass to:

* redesign Report Registry;
* change Customer 360 architecture;
* change `reports` disabled-by-default decision;
* change Recharts decision;
* implement Branch Performance;
* retrofit legacy module exports;
* add async export jobs;
* implement AI;
* resolve ADR-0004;
* perform unrelated refactors.

Everything else in the current plan should remain intact unless directly affected by these four corrections.

---

# 12. FINAL VALIDATION

Before finishing, verify:

* approved spec semantics remain unchanged;
* no plan section contradicts another;
* no architecture uses `Any` as a Reports-layer escape hatch;
* Installments Case B does not exceed servicing-continuity scope;
* export path remains the same security/data-definition path as online reports;
* export retrieval is bounded;
* export audit is durable before successful file delivery;
* saved views use one clear delete policy;
* no new blocking question has been introduced.

Target:

**No blocking decisions.**

---

# 13. REQUIRED FINAL REPORT

Return:

# Epic 11 Plan — Final Correction Report

## A. Files Modified

List exact files.

## B. Type-Safety Correction

State:

* final adapter typing design;
* where legacy `Any` may exist;
* where it is terminated;
* confirmation that Reports orchestration/public contracts do not expose it.

## C. Installments Servicing-Continuity Correction

List:

* Case A behavior;
* Case B explicit report allow-list;
* reports intentionally unavailable in Case B, including `plan_performance`.

## D. Export Architecture Correction

State:

* shared authorization/execution path;
* bounded row retrieval mechanism;
* CSV strategy;
* XLSX strategy;
* GL cursor strategy;
* configured row-limit strategy.

## E. Export Audit Durability

State exact success/failure ordering and confirm:

**no successful file delivery without durable audit persistence.**

## F. Saved View Deletion

Confirm:

**soft delete only**

and no restore UI/API in Epic 11.

## G. Test / Gate Updates

Summarize newly added/updated plan coverage.

## H. Open Decisions

Target:

**No blocking decisions.**

## I. Git Status

Report branch and working-tree state.

Do NOT commit or push unless the existing workflow explicitly authorizes it.

## J. Final Verdict

Return exactly:

**EPIC 11 PLAN READY FOR TASKS**

or

**EPIC 11 PLAN NOT READY FOR TASKS**

---

# 14. STOP

After correcting and validating `plan.md`:

STOP.

Do NOT create `tasks.md`.

Do NOT implement Epic 11.

Wait for explicit review/approval.

## Response snapshot

Read the full corrected `plan.md` (941 lines at the time) end-to-end, then applied 12 coordinated edits addressing all five substantive corrections plus their downstream consistency requirements:

1. **Type safety** (§10.1 new, §32 rewritten): replaced `ReportAdapter.run(...) -> ReportResult[Any]` with a covariant `Protocol[ReportResultT_co]` bound to a new closed `BaseReportResult` hierarchy (`AggregateReportResult[T]`/`PaginatedReportResult[T]`/`CursorReportResult[T]`). Defined three explicit zones (legacy domain internals may contain `Any`; adapter translation bodies may transiently touch it; Reports orchestration/public contracts never do) and rewrote §32 as a table making this precise rather than the previous blanket "no Any" claim that contradicted the adapter signature.
2. **Installments Case B allow-list** (§13 rewritten): added an explicit `frozenset` allow-list (`register`, `collections`, `due_overdue`, `aging`, `settlement_writeoff`) and an `is_allowed(report_key, state)` method on `InstallmentsServicingContinuityGate`. Explicitly excluded `installments.plan_performance` and the standalone `installments.dashboard` report key from Case B — the latter's two obligation-tied metrics remain reachable only via the Executive Dashboard's existing separate per-widget mechanism, not as the whole bundle. Updated §9's execution-flow pseudocode, §14's Customer 360 Installments section note, §29's Installments test matrix, §33 Phase 2/4, §34's Adapters gate, and §36's risk register to reference the allow-list consistently.
3. **Export architecture** (§21 fully restructured into §21.1–§21.9): separated the shared `_authorize_and_validate()` preamble (identical for `execute()` and `export()`, so no parallel security path exists) from bounded row retrieval (`adapter.count_export_rows()` checked against the row limit **before** any retrieval, then `adapter.iter_export_rows()` yielding typed batches — never a full materialized list). Documented CSV (bounded batches assembled into the repo's existing final-`bytes` contract, with streaming-response noted only as a future option), XLSX (openpyxl `write_only=True`), and GL (native cursor consumption to completion) strategies separately, per the correction's explicit per-format breakdown.
4. **Export audit durability** (§21.8 new, §22 updated): documented the exact 6-step ordering (authorize → count/limit-check → generate bytes → stage audit → commit audit → only then return the file), added a new `ExportAuditPersistenceError`/`EXPORT_AUDIT_FAILED` (500-class) exception in §26's error table, and added a dedicated simulated-audit-failure test requirement in §28 and the Exports phase gate in §34.
5. **Saved-view deletion** (§15 rewritten): resolved the "hard delete... however soft-delete" self-contradiction to a single, unambiguous soft-delete-only policy, with explicit owner-isolation-under-deletion and no-hard-delete-path statements.

Also updated: §6 module/file-layout comments (adapters/base.py, exceptions.py), §10's adapter table and pagination/export-mapping bullets, §28 test architecture (new type-boundary, Installments-allow-list, export-bounded-retrieval/audit-durability, and saved-view-soft-delete test bullets), §33 implementation phases (Phase 2 now builds `count_export_rows`/`iter_export_rows` alongside `run()` from the start, not bolted on later; Phase 6 updated accordingly), §36 risk register (2 new risk rows for allow-list scope creep and audit-durability ordering bugs), §40 open decisions (added export batch size as a non-blocking parameter alongside the existing row-limit item), and §41 (new §41.1 "Correction Pass" summary, renumbered checklist to §41.2, final verdict line changed from "READY FOR REVIEW" to "READY FOR TASKS").

Ran a final grep pass across the whole file for every term named in the correction brief's revalidation checklist (`ReportResult[Any]`, "full-scope"/"count-then-fetch", "hard delete", "plan_performance", "every Now Installments report", bare `Any`) — confirmed every remaining occurrence is either an explicitly-marked "corrected" historical reference or a legitimate zone-1 (legacy service) citation, with no unresolved contradiction anywhere in the document. No scope expansion occurred: Report Registry design, Customer 360 architecture, the `reports` disabled-by-default decision, Recharts, Branch Performance (deferred), legacy module exports, async jobs, AI, and ADR-0004 were all left untouched per the explicit "do not expand scope" instruction.

## Outcome

- ✅ Impact: All five correction items resolved consistently across every plan.md section that referenced the corrected material; no new blocking decisions introduced; plan is internally consistent end-to-end.
- 🧪 Tests: None run — planning-only correction pass, no code changes made. Test *requirements* for each correction were added to §28/§29/§34 as future task inputs.
- 📁 Files: `specs/011-reports-analytics/plan.md` only (12 targeted edits; no other file touched).
- 🔁 Next prompts: Human review of the corrected `plan.md`; upon approval, `/sp.tasks` to generate `specs/011-reports-analytics/tasks.md`.
- 🧠 Reflection: The most structurally important fix was recognizing that Installments' Case B allow-list needed to operate at the granularity of whole report keys (Reports' registry has no sub-report-field gating mechanism), which meant "servicing-related dashboard figures tied directly to existing obligations" from the correction brief had to be satisfied via the *already-existing* separate Executive Dashboard per-widget composition rather than by including the standalone `installments.dashboard` report key in the allow-list — a distinction worth calling out explicitly rather than leaving implicit, since it's the kind of granularity mismatch that's easy to miss during `/sp.tasks`.

## Evaluation notes (flywheel)

- Failure modes observed: None blocking. One interpretive judgment call flagged explicitly in the plan itself (§13): whether "servicing-related dashboard figures" from the correction brief meant the whole `installments.dashboard` report key or just its two obligation-tied metrics — resolved in favor of the narrower reading (metrics only, via the existing Executive Dashboard mechanism) since the correction brief's own framing ("only the explicit servicing-continuity allow-list... do not automatically expose unrelated analytics simply because they are read-only") argues for the narrowest defensible scope.
- Graders run and results (PASS/FAIL): Not applicable — no automated grading harness invoked; self-validated via an exhaustive grep pass (documented above) against every term the correction brief's own revalidation checklist (items 6–8) named.
- Prompt variant (if applicable): N/A (single-pass execution of the provided correction brief).
- Next experiment (smallest change to try): During `/sp.tasks`, confirm with a real implementation spike whether `EXPORT_BATCH_SIZE` interacts cleanly with GL's native cursor page size (Accounting's own `limit=100` default) or whether the export batch size should simply equal the wrapped service's own page size rather than being a separate independent constant — a small simplification opportunity noted but not resolved in this pass to avoid scope creep.
