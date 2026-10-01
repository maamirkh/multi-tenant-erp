---
id: 0002
title: Epic 11 spec correction pass
stage: spec
date: 2026-09-11
surface: agent
model: claude-sonnet-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: (none — direct correction-pass prompt, not a slash command)
labels: ["epic-11", "reports-analytics", "specification", "correction-pass", "audit"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: history/adr/0004-gl-account-resolution-for-sales-purchase-inventory-integration-events.md
  pr: null
files:
 - specs/011-reports-analytics/spec.md
 - specs/011-reports-analytics/checklists/requirements.md
tests:
 - none (specification-only correction pass; no code changes made)
---

## Prompt

# DevSphere ERP SaaS

# Epic 11 — Reports & Analytics

## Final Specification Correction & Approval Pass

You are continuing work on the existing:

`specs/011-reports-analytics/spec.md`

This is a **targeted correction and audit pass only**.

Do NOT rewrite the specification from scratch.

Do NOT create:

* `plan.md`
* `tasks.md`
* migrations
* models
* repositories
* services
* routes
* frontend implementation
* tests
* Epic 12 work
* AI implementation

The purpose of this pass is to resolve the remaining architectural ambiguities before Epic 11 is approved for planning.

---

# 1. CURRENT STATUS

The existing Epic 11 specification has already completed deep repository discovery.

Current reported state:

* `spec.md` created
* requirements checklist created
* 143 unique requirements
* zero `[NEEDS CLARIFICATION]` markers
* approximately 45 report catalog entries
* existing per-module reporting/KPI services discovered and reused
* reporting architecture defined as a thin registry/gateway over existing domain services
* tenant/RBAC/entitlement/security boundaries defined
* future AI readiness defined without implementing AI

The specification is strong overall.

However, several findings require explicit reconciliation before planning begins.

---

# 2. GENERAL RULE

Repository evidence is authoritative.

Do not make a decision merely because this prompt recommends one.

For every correction below:

1. inspect the relevant repository evidence;
2. inspect ADRs/specs/models/services/permissions/entitlements/tests;
3. determine the actual architectural truth;
4. update `spec.md` accordingly;
5. update the requirements checklist if needed;
6. preserve stable requirement IDs wherever possible.

Do not create unnecessary new requirements if an existing requirement can be corrected.

---

# 3. CORRECTION 1 — BRANCH AUTHORIZATION

Repository discovery reportedly found:

* no implemented Branch entity;
* no branch membership/ACL model;
* only nullable/reserved branch-related fields in some models.

This is a load-bearing architectural fact.

## Required action

Verify this finding thoroughly.

If confirmed, explicitly state in the specification that:

**Branch is NOT currently an authorization boundary in DevSphere ERP.**

Any current branch-like field may only be used as a reporting/filtering dimension where the source data legitimately contains it.

Do NOT imply that Epic 11 can enforce branch ACLs that do not exist.

---

# 4. BRANCH PERFORMANCE REPORT

The existing report catalog reportedly includes:

**Branch Performance Summary — Deferred**

Unless repository evidence reveals an actual implemented branch-security model, lock this decision as:

**DEFERRED**

Do not ship Branch Performance Summary in Epic 11 merely because nullable `branch_id` fields exist.

The specification should clearly state that a future Branch domain/ACL capability must exist before branch-level authorization-sensitive analytics can be considered authoritative.

If branch fields can currently be used safely as descriptive/filtering dimensions, document that distinction explicitly:

**data dimension ≠ authorization boundary**

---

# 5. CORRECTION 2 — INVENTORY VALUATION AUTHORITY

The discovery summary contains a potential ambiguity:

* Accounting does not own inventory valuation;
* ADR-0004 reportedly exposes a valuation ownership gap;
* the specification reportedly states that Inventory owns valuation.

These statements must be reconciled.

## Required action

Inspect:

* ADR-0004;
* Inventory models/services;
* Inventory reporting services;
* valuation algorithms;
* Accounting integration;
* journal/posting flows;
* existing tests;
* prior specs.

Determine the real current authority for inventory valuation.

There are only three acceptable outcomes:

### Outcome A — Inventory is authoritative

Use this only if repository evidence proves that Inventory already owns the definitive valuation calculation/state.

Then explicitly document:

* valuation method;
* authoritative service/data;
* Accounting relationship;
* reconciliation expectations.

### Outcome B — Accounting is authoritative

Use this only if repository evidence proves it.

### Outcome C — Authority is currently unresolved/incomplete

If ADR-0004 genuinely identifies an unresolved architectural gap, do NOT falsely declare Inventory or Accounting authoritative.

Instead:

* mark inventory valuation reporting as constrained/deferred where necessary;
* specify only the reporting behavior currently supported safely;
* document the prerequisite required for authoritative valuation reporting.

Do not create a new valuation algorithm inside Epic 11 to fill an earlier domain gap.

---

# 6. INVENTORY VALUATION REPORT SAFETY

If current valuation authority is incomplete, ensure the report catalog does not expose a misleading report labeled simply:

**Inventory Valuation**

as if it were financially authoritative.

Use terminology that matches actual repository guarantees.

Where appropriate distinguish:

* operational stock valuation;
* accounting inventory balance;
* reconciliation gap.

Do not imply equivalence unless the existing system proves it.

---

# 7. CORRECTION 3 — ALWAYS-ON MODULES VS ENTITLEMENTS

The current spec reportedly leaves an open decision about whether:

* Sales
* Purchase
* Inventory
* Accounting

are always-on modules or entitlement-controlled modules.

This is not merely a cosmetic product decision.

It affects authorization and report availability.

## Required action

Inspect the actual entitlement/capability implementation and completed module specs.

Determine for each report family whether its source module:

* has an existing entitlement/capability;
* is part of the guaranteed ERP core;
* can be disabled;
* is conditionally available.

Do not guess from UI behavior.

---

# 8. ENTITLEMENT MATRIX MUST BE FINAL

Update the Epic 11 entitlement matrix so that each report family has a definitive rule.

For example, conceptually:

| Report Family | Underlying Module Entitlement | Reports Entitlement |
| ------------- | ----------------------------- | ------------------- |
| Sales         | actual repository truth       | actual Epic 11 rule |
| Purchase      | actual repository truth       | actual Epic 11 rule |
| Inventory     | actual repository truth       | actual Epic 11 rule |
| Accounting    | actual repository truth       | actual Epic 11 rule |
| CRM           | actual repository truth       | actual Epic 11 rule |
| Installments  | actual repository truth       | actual Epic 11 rule |

Do not copy this table blindly.

Use real capability keys and conventions from the repository.

After this correction there should be no unresolved open question about whether the major report families are entitlement-gated.

---

# 9. `reports.*` CAPABILITIES

Review the proposed new reporting permissions/entitlements carefully.

Do not introduce a redundant or contradictory entitlement architecture.

Clarify the relationship between:

* underlying domain module permission;
* underlying domain entitlement;
* report-specific permission;
* report-specific entitlement if one is genuinely needed.

Recommended principle:

A report should never provide access to a domain that the tenant/user cannot otherwise access under established product policy.

But reporting may legitimately require additional permissions such as:

* view analytics;
* export analytics.

Do not create double-gating without a clear product reason.

---

# 10. CORRECTION 4 — EXPORT ROW LIMIT

The specification currently recommends approximately:

**50,000 synchronous export rows**

Treat this as a planning/performance candidate, not an immutable business invariant, unless repository benchmarking already proves it.

## Required correction

Specify that the synchronous export threshold:

* must be configurable or centrally defined;
* may vary by format if justified;
* should be finalized during implementation planning using measured memory/runtime behavior;
* must remain bounded.

CSV and XLSX may have different operational characteristics.

Do not require identical limits unless justified.

---

# 11. EXPORT ARCHITECTURE

The spec should define the invariant rather than prematurely freezing the number:

**Large exports must not create unbounded memory/CPU/database load.**

The implementation plan may later choose thresholds based on:

* CSV;
* XLSX;
* environment limits;
* query cost;
* row width.

Keep `50,000` as the recommended initial candidate if useful, but label it clearly as configurable/planning-finalized.

---

# 12. CORRECTION 5 — CUSTOMER 360

The existing catalog reportedly places:

**Customer 360**

in Epic 11 "Now" scope.

This is acceptable only if its semantics are tightly controlled.

## Required correction

Define Customer 360 explicitly as a:

**composite read model / analytical projection**

and NOT as:

* a new customer system of record;
* a new financial source of truth;
* a replacement for CRM;
* a replacement for Sales;
* a replacement for Accounting;
* a replacement for Installments.

---

# 13. CUSTOMER 360 SOURCE OWNERSHIP

Customer 360 must compose existing authoritative facts.

For example, where supported:

* identity/master data → authoritative customer/domain source;
* CRM activity → CRM;
* orders/invoices → Sales;
* accounting balance/receivables → Accounting;
* installment operational state → Installments.

Do not recompute financial truth from Sales or Installments if Accounting already owns it.

The specification must contain a source mapping for Customer 360.

---

# 14. CUSTOMER 360 SECURITY

A Customer 360 response must perform compound authorization.

The user must not gain access to data from a module merely because they can open the Customer 360 report.

If a user lacks access to a constituent domain, decide from repository/product policy whether that section is:

* omitted;
* unavailable;
* denied.

Document the behavior explicitly.

Do not leak hidden module data through a composite report.

---

# 15. CUSTOMER 360 PARTIAL AVAILABILITY

Specify how Customer 360 behaves when:

* CRM is disabled;
* Installments are disabled;
* Accounting is unavailable/not configured;
* Sales exists but no transactions exist.

Prefer graceful partial composition where product/security rules allow it.

But never substitute fabricated zeros for unavailable authoritative data.

Differentiate:

**zero**

from:

**not available / not configured / not entitled**

---

# 16. OPEN DECISIONS CLEANUP

Review the existing §53 open decisions.

After this pass:

* Branch Performance should have a final scope decision.
* Core module entitlement behavior should be resolved from repository evidence.
* Export threshold may remain a planning-time implementation parameter, but it should not be framed as an unresolved product architecture question.

The specification should ideally end with:

**No blocking open decisions for plan.md.**

If a genuine owner-level decision remains, retain it explicitly and explain why repository evidence cannot resolve it.

---

# 17. REPORT CATALOG AUDIT

Re-audit every "Now" report.

For each ensure:

* authoritative source exists today;
* necessary domain service exists or the new read aggregation is justified;
* tenant scope is clear;
* permission rule is clear;
* entitlement rule is clear;
* financial semantics are not fabricated;
* branch semantics do not assume nonexistent ACL;
* drill-down destination exists or is clearly defined;
* export support is defensible.

If any report fails these conditions, move it to Deferred or constrain its scope.

Do not keep a report in "Now" merely to make the catalog look comprehensive.

---

# 18. DEFERRED REPORT CATALOG

Ensure deferred reports state WHY they are deferred.

Examples:

* missing branch ACL;
* missing authoritative domain data;
* unsupported accounting source;
* missing lifecycle information;
* future infrastructure required.

This will prevent future implementation agents from accidentally implementing deferred reports early.

---

# 19. KPI CATALOG AUDIT

Re-check KPI definitions against the newly reconciled source-of-truth decisions.

Especially inspect:

* Inventory Value;
* Gross Profit / Gross Margin;
* Receivables;
* Payables;
* Outstanding Installments;
* Sales totals.

Ensure operational and financial metrics remain explicitly distinct.

---

# 20. GROSS PROFIT / MARGIN NAMING

The original discovery reportedly found two concepts:

* an operational margin;
* Accounting's `Gross Profit Margin`.

Verify that the specification gives these distinct semantic identifiers and names.

Do not allow two different calculations to appear under the same user-facing metric name without explanation.

---

# 21. SOURCE-OF-TRUTH MATRIX AUDIT

Rebuild or amend the source-of-truth matrix after resolving Inventory valuation and Customer 360.

Every major reporting domain must have exactly one clear statement of authority.

Where authority is genuinely split, describe the split explicitly.

Example conceptual distinction:

* operational installment status → Installments;
* posted receivable balance → Accounting.

Avoid ambiguous phrases such as "Sales/Accounting".

State what each owns.

---

# 22. BRANCH WORDING AUDIT

Search the entire specification for terms such as:

* branch access;
* branch ACL;
* authorized branch;
* branch permission;
* branch-scoped authorization.

Ensure none falsely imply functionality that the repository does not implement.

Where current filters exist, call them accurately:

**branch/reporting data filters**

rather than security boundaries.

---

# 23. SECURITY MATRIX AUDIT

After the entitlement correction, revalidate the security matrix.

Each report family should clearly address:

* authentication;
* tenant scope;
* permission;
* underlying module entitlement;
* report capability;
* drill-down authorization;
* export permission.

No report should rely solely on frontend hiding.

---

# 24. FUTURE BRANCH SUPPORT

Where useful, make Epic 11 architecture branch-ready without pretending branch security exists now.

It is acceptable for contracts to preserve optional branch dimensions if they already exist in source data.

But future branch ACL enforcement must be introduced by the proper Branch domain/security capability, not invented inside Reports.

---

# 25. NO SCOPE EXPANSION

This correction pass must NOT add major new report families.

Do not expand scope into:

* forecasting;
* predictive analytics;
* BI warehouse;
* custom SQL reports;
* report designer;
* scheduled email reports;
* AI;
* NL-to-SQL;
* new Branch domain implementation.

Fix ambiguity; do not expand Epic 11.

---

# 26. PRESERVE CLEAN TYPE BASELINE

The project enters Epic 11 with:

* production MyPy 0;
* test MyPy 0;
* repository-wide MyPy 0.

Although this is specification-only work, ensure no proposed architecture depends on:

* dynamic untyped dictionaries everywhere;
* arbitrary JSON query DSLs;
* unchecked runtime report definitions.

Keep typed report/filter/result contracts as a core requirement.

---

# 27. SPEC CHECKLIST REVALIDATION

After corrections, update/re-run:

`specs/011-reports-analytics/checklists/requirements.md`

or the repository's actual checklist path.

Confirm:

* no unresolved contradiction;
* no `[NEEDS CLARIFICATION]`;
* no report with unsupported source;
* no false branch security assumptions;
* source-of-truth matrix coherent;
* entitlement matrix coherent;
* all required catalog/matrix sections complete.

---

# 28. TRACEABILITY

If correcting requirements changes semantics, update:

* requirement text;
* catalog references;
* acceptance criteria;
* matrices.

Preserve requirement IDs where feasible.

Do not renumber the entire specification unnecessarily.

---

# 29. FINAL QUALITY QUESTIONS

Before declaring the specification ready, answer internally:

1. Can any report leak another tenant's data?
2. Does any report assume branch ACL exists?
3. Can reporting bypass a disabled/unauthorized module?
4. Does any financial KPI conflict with Accounting authority?
5. Is Inventory valuation authority actually proven?
6. Can Customer 360 create a new source of truth?
7. Can export bypass view/export permissions?
8. Are report queries bounded?
9. Are operational and financial metrics distinguished?
10. Can future AI consume these contracts without raw SQL access?
11. Are all "Now" reports implementable from current system capabilities?
12. Are deferred reports clearly blocked for documented reasons?

Correct the spec if any answer is unsafe or ambiguous.

---

# 30. FINAL RESPONSE

After making only the necessary corrections, return:

# Epic 11 Specification — Final Correction Report

## A. Files Modified

List exact files.

## B. Branch Decision

State:

* whether a real Branch entity/ACL exists;
* exact final treatment of branch filtering;
* final status of Branch Performance Summary.

## C. Inventory Valuation Authority

State the exact repository-backed conclusion and evidence category.

Use one:

* Inventory authoritative;
* Accounting authoritative;
* authority unresolved / report constrained.

Explain briefly.

## D. Entitlement Resolution

Give the final entitlement behavior for:

* Sales;
* Purchase;
* Inventory;
* Accounting;
* CRM;
* Installments;
* Reports capability.

No ambiguity.

## E. Export Guardrail

State how the previous 50,000-row recommendation is now represented.

## F. Customer 360

Confirm:

* composite read model;
* constituent authoritative sources;
* security behavior;
* disabled/unavailable module behavior.

## G. Report Catalog Changes

List reports:

* kept Now;
* changed;
* moved to Deferred.

## H. KPI / Source-of-Truth Corrections

List substantive semantic corrections.

## I. Open Decisions

List genuine remaining decisions.

Target:

**None blocking plan.md.**

## J. Checklist Validation

Report result and number of `[NEEDS CLARIFICATION]` markers.

Expected:

**0**

## K. Git Status

Report:

* branch;
* modified/untracked files;
* whether anything was committed/pushed.

Do NOT commit/push unless existing workflow requires it and explicit authority already exists.

## L. Final Verdict

Return exactly:

**EPIC 11 SPECIFICATION READY FOR PLAN**

or:

**EPIC 11 SPECIFICATION NOT READY FOR PLAN**

---

# 31. STOP

After the correction report:

STOP.

Do NOT create `plan.md`.

Do NOT create `tasks.md`.

Do NOT implement anything.

Wait for explicit approval to proceed to Epic 11 planning.

## Response snapshot

Performed a targeted correction pass (not a rewrite) on `specs/011-reports-analytics/spec.md`. Dispatched two focused verification agents against primary repository evidence: (1) full text of ADR-0004 (Status: Proposed, never Accepted) plus Inventory's `_compute_wac()`/`StockPosition.unit_cost`, Accounting's `coa_templates.py` seeded-but-unpopulated Inventory ASSET GL accounts, and the `TestInventoryAdjustmentGLGap` test's own "deliberate tripwire" docstring — conclusion: inventory valuation authority is genuinely **unresolved/incomplete (Outcome C)**, overturning the prior spec's flat "Inventory is authoritative" claim; (2) `CapabilitySeedService.MODULE_CAPABILITY_CATALOGUE`, `module_enablement.py`'s `DefaultAlwaysEnabledModuleProvider`, and router-mount code in `api/v1/router.py` — conclusion: all six modules (Sales, Purchase, Inventory, Accounting, CRM, Installments) are genuinely registered, individually-gated `grain=module` Capabilities; none is structurally exempt from entitlement, they differ only in default-resolved state (four default-entitled via a stateless always-on toggle provider plus no auto-subscription at signup; CRM/Installments default-disabled).

Applied 12 targeted edits to spec.md: corrected §7 Source-of-Truth Matrix and §9/§10 catalog entries for inventory valuation (renamed to "Operational Stock Valuation (WAC)" / "Operational Inventory Value (WAC)", added `valuation_basis` disclaimer requirement, FR-RPT-071 rewritten, FR-RPT-074 added); rewrote §34 Entitlement Matrix with a `Domain Default State` column and added FR-RPT-254/255; strengthened §25 Branch Semantics with the exact required opening statement and re-confirmed no branch-ACL wording exists anywhere in the doc; reframed §30's export guardrail (FR-RPT-214) from a fixed 50,000-row requirement to a bounded-but-configurable invariant with 50,000 demoted to a non-binding planning candidate; added §20.1/§20.2 to Cross-Module Analytics defining Customer 360 as an explicit composite read model with a source-mapping table and new FR-RPT-114/115 distinguishing omitted/unavailable/confirmed-zero states; updated Assumptions (A3 strengthened, A6 rewritten, A11 added); resolved and removed former OQ-2 from Open Questions (§53), added OQ-4 (reports capability's own default state, non-blocking); added two new Risk rows (§52) and one new Out-of-Scope item (§51, explicitly excluding ADR-0004 resolution from Epic 11). All 5 new requirement IDs (FR-RPT-074/114/115/254/255) were appended within their sections' existing numeric blocks; zero existing requirement IDs were renumbered or removed. Rewrote `checklists/requirements.md` to document every correction and re-validate all quality gates. Final state: 855 lines (was 821), 148 unique FR-RPT requirements (was 143), zero `[NEEDS CLARIFICATION]` markers, 54/54 ToC-to-header match, no duplicate requirement IDs, no stale "Inventory-owned"/"always-on core" claims remaining outside clearly-superseded quoted references. No `plan.md`, `tasks.md`, or implementation created. Verdict: EPIC 11 SPECIFICATION READY FOR PLAN.

## Outcome

- ✅ Impact: Resolved all five requested corrections with primary-evidence verification; closed the one true open question (OQ-2) definitively; reframed one implementation-planning parameter (export row limit) so it no longer reads as a frozen product invariant; specification is now internally consistent and ready for `/sp.plan`.
- 🧪 Tests: None run/added (specification-only correction pass).
- 📁 Files: `specs/011-reports-analytics/spec.md` (edited, +34 lines net), `specs/011-reports-analytics/checklists/requirements.md` (rewritten).
- 🔁 Next prompts: Await explicit user approval before `/sp.plan`; remaining non-blocking recommendations (OQ-1 export limit, OQ-3 branch-performance deferral, OQ-4 reports' own default entitlement state) may be revisited during planning.
- 🧠 Reflection: The two corrections requiring primary-evidence re-verification (inventory valuation authority, entitlement gating) both overturned or significantly refined conclusions from the original discovery pass — a reminder that broad discovery-agent summaries can overstate certainty on nuanced architectural questions, and a targeted, evidence-first re-verification pass is the right tool to catch that before planning locks in a wrong premise.

## Evaluation notes (flywheel)

- Failure modes observed: The original spec's Inventory-valuation claim ("Inventory owns it, not Accounting") was an overstatement not fully supported by the evidence available at the time — ADR-0004 is Proposed-not-Accepted and explicitly declines to resolve the question; this pass corrected it to the more accurate "unresolved/incomplete" framing.
- Graders run and results (PASS/FAIL): Self-validated against the rewritten `checklists/requirements.md` — all items PASS, including a new "Correction-Pass-Specific Validation" section added for this pass's specific asks.
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): N/A
