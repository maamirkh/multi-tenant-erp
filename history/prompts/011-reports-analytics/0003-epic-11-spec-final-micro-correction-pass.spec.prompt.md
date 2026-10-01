---
id: 0003
title: Epic 11 spec final micro-correction pass
stage: spec
date: 2026-09-11
surface: agent
model: claude-sonnet-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: (none — direct micro-correction-pass prompt, not a slash command)
labels: ["epic-11", "reports-analytics", "specification", "micro-correction-pass", "contradiction-audit"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: null
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

## Final Spec Micro-Correction Before `plan.md`

You are continuing work on:

`specs/011-reports-analytics/spec.md`

This is the **final targeted correction pass** before Epic 11 planning.

Do NOT rewrite the specification.

Do NOT create:

* `plan.md`
* `tasks.md`
* implementation
* migrations
* models
* services
* routes
* frontend code
* tests
* Epic 12 work
* AI work

Only correct the remaining specification inconsistencies below, revalidate the checklist, report the result, then STOP.

---

# 1. INSTALLMENTS ENTITLEMENT / SERVICING-CONTINUITY CONTRADICTION

The specification currently contains two rules that need explicit reconciliation.

### Existing Installments-specific rule

`FR-RPT-104` states that if Installments entitlement is disabled after contracts already exist, Installment reporting remains available read-only because existing contractual obligations must remain explainable and serviceable, following the established Epic 10 servicing-continuity invariant.

### Generic domain-entitlement rule

`FR-RPT-251` / `FR-RPT-252` currently state broadly that a disabled domain's reports become unreachable and return the normal "module not entitled" response.

These rules must not contradict each other.

## Required final rule

Preserve the Epic 10 servicing-continuity invariant.

Explicitly define Installments as a documented exception to the generic disabled-domain behavior.

The intended semantics are:

### Case A — Installments disabled and no existing serviceable contracts/obligations

Installment reporting is unavailable under the normal entitlement rule.

### Case B — Installments was previously active and serviceable contracts/obligations still exist

Required servicing-continuity reporting remains available in **read-only** form even though new origination/configuration/business-creation capabilities are disabled.

The user must retain enough visibility to:

* understand existing contracts;
* inspect schedules;
* inspect due/overdue status;
* understand collections;
* understand defaults/write-offs/settlements where relevant;
* reconcile obligations appropriately.

This must NOT reopen:

* new contract origination;
* configuration;
* new plan/template creation;
* disabled write capabilities.

## Required edits

Update:

* `FR-RPT-251`
* `FR-RPT-252`
* entitlement matrix
* Installments section
* edge cases
* acceptance scenarios
* any other wording implying that disabled Installments always becomes completely unreachable.

Add an explicit generic exception along the lines of:

> A disabled-domain report family is normally unreachable, except where the underlying domain already defines an established post-disable servicing-continuity invariant. Installments is currently such an exception under FR-INST-354 / FR-RPT-104.

Do not create a new entitlement mechanism.

Reuse the existing Installments policy semantics.

---

# 2. CUSTOMER 360 ENTITLEMENT WORDING

The current Customer 360 catalog row risks implying that:

`reports + sales + accounting`

must all be entitled before the report can be opened.

But the detailed Customer 360 requirements correctly define **partial composition**.

For example:

* Sales section may be visible;
* Accounting section may be omitted if its permission/entitlement is unavailable;
* CRM section may be omitted;
* Installments section may be omitted.

This needs one consistent contract.

## Required correction

Customer 360 must be treated as:

**section-level compound authorization**

not:

**all-or-nothing entitlement gating across every constituent module.**

The base Customer 360 request requires:

* authentication;
* tenant scope;
* `reports` entitlement;
* `reports.customer_360.view`.

Then each constituent section independently evaluates its own:

* domain entitlement;
* relevant report permission;
* tenant context.

A section the user cannot access is omitted.

No inaccessible domain data may leak.

## Update the catalog row

Replace ambiguous entitlement wording such as:

`reports + sales + accounting; +installments if entitled`

with wording clearly indicating:

**`reports` required globally; constituent domain sections independently entitlement/permission-gated.**

Preserve the existing `FR-RPT-111`, `FR-RPT-114`, and `FR-RPT-115` partial-composition behavior.

---

# 3. CUSTOMER 360 MINIMUM USEFUL RESPONSE

Clarify one small edge case:

If none of the constituent business sections is available after section-level authorization, determine the correct repository-consistent behavior.

Preferred recommendation:

Return the Customer 360 shell/customer identity only if the user is authorized to access that customer master record; otherwise deny/not-found using the existing IDOR-safe behavior.

Do not return an empty cross-module shell that itself leaks the existence of a customer the user cannot otherwise access.

Use repository security conventions to finalize the exact wording.

---

# 4. BRANCH PERFORMANCE OPEN QUESTION

The specification already consistently places:

`crossmodule.branch_performance`

in **Deferred** state because there is no real Branch domain/ACL and real populated branch data is not yet established.

Therefore it should no longer be framed as an unresolved product decision.

## Required correction

Mark OQ-3 as:

**RESOLVED — Deferred**

The future report may only be promoted from Deferred when its documented prerequisites exist.

Do not move it into Epic 11 "Now" scope.

---

# 5. REPORTS CAPABILITY DEFAULT

The existing OQ-4 recommends:

`reports` capability = disabled by default.

This is acceptable as a planning-time product decision.

However, ensure the specification is clear that:

* this is the recommended default;
* `/sp.plan` must explicitly implement/document the selected default;
* the decision must not accidentally inherit behavior from another module.

If the repository architecture already provides enough evidence to make disabled-by-default the clearly correct choice, you may lock it now.

Otherwise it may remain a **non-blocking planning decision**.

Do not let this block `plan.md`.

---

# 6. ACCEPTANCE SCENARIO CORRECTION

Review acceptance/edge-case wording for the Installments case.

There must not be two contradictory scenarios such as:

* "disabled Installments → module not entitled"
  and
* "disabled Installments with active contracts → read-only reports available"

The final scenarios must explicitly distinguish:

### Disabled without servicing obligations

normal entitlement denial.

### Disabled with existing servicing obligations

approved read-only servicing-continuity reporting.

---

# 7. ENTITLEMENT MATRIX FINAL AUDIT

After correction, the matrix must communicate:

* Sales disabled → reports unavailable
* Purchase disabled → reports unavailable
* Inventory disabled → reports unavailable
* Accounting disabled → reports unavailable
* CRM disabled → reports unavailable
* Installments disabled → normally unavailable, **except servicing-continuity read access for existing obligations**
* Customer 360 → section-level constituent gating
* Executive Dashboard → per-widget gating
* Branch Performance → Deferred

No contradictory wording should remain anywhere.

---

# 8. SEARCH FOR CONTRADICTIONS

Before finishing, search the specification for wording equivalent to:

* disabled Installments
* module not entitled
* every domain entitlement
* Customer 360 entitlement
* sales + accounting
* branch performance
* OQ-3
* FR-RPT-104
* FR-RPT-251
* FR-RPT-252

Ensure all occurrences tell the same story.

---

# 9. CHECKLIST REVALIDATION

Re-run/update:

`specs/011-reports-analytics/checklists/requirements.md`

Confirm:

* zero contradictions;
* zero `[NEEDS CLARIFICATION]`;
* entitlement matrix internally consistent;
* Customer 360 authorization internally consistent;
* Branch Performance definitively Deferred;
* Installments servicing continuity preserved.

---

# 10. FINAL REPORT

Return:

# Epic 11 Specification — Final Micro-Correction Report

## A. Files Modified

List exact files.

## B. Installments Entitlement Resolution

State the final rule for:

* disabled/no obligations;
* disabled/existing obligations;
* read-only servicing-continuity scope.

## C. Customer 360 Authorization Resolution

State:

* global gate;
* section-level gates;
* omitted-section behavior;
* minimum useful/secure response behavior.

## D. Branch Performance

Confirm:

**RESOLVED — DEFERRED**

and state the promotion prerequisite.

## E. Reports Capability Default

State whether:

* locked now;
  or
* remains a non-blocking `/sp.plan` decision.

## F. Contradiction Audit

Confirm no remaining contradictory entitlement behavior exists.

## G. Checklist

Report validation result and exact `[NEEDS CLARIFICATION]` count.

Expected:

**0**

## H. Git Status

Report branch and working-tree state.

Do NOT commit or push unless explicitly required by the existing workflow.

## I. Final Verdict

Return exactly:

**EPIC 11 SPECIFICATION READY FOR PLAN**

or

**EPIC 11 SPECIFICATION NOT READY FOR PLAN**

---

# 11. STOP

After this report:

STOP.

Do NOT run `/sp.plan`.

Do NOT create `plan.md`.

Do NOT create `tasks.md`.

Do NOT implement Epic 11.

Wait for explicit approval.

## Response snapshot

Applied nine targeted edits to `specs/011-reports-analytics/spec.md` resolving all five requested corrections. (1) Installments/generic-entitlement contradiction: rewrote FR-RPT-104 to explicitly split Case A (disabled, no obligations → normal "module not entitled" denial, identical to CRM) from Case B (disabled, obligations exist → narrowly-scoped read-only servicing-continuity, per FR-INST-354); rewrote FR-RPT-252 to state the generic disabled-domain rule applies unconditionally to CRM and to every domain except where that domain defines its own documented servicing-continuity carve-out (currently only Installments); added a callout box to §34's entitlement-matrix intro stating this generic-rule-plus-one-exception principle explicitly; updated the entitlement matrix's Installments row, the Executive Dashboard's Installments widget requirement (FR-RPT-041), the §45 edge-case bullets (split the old lumped "CRM, Installments disabled" bullet into two separate, non-contradictory bullets), and added new Acceptance Scenario M (Case A) alongside the existing Scenario H (Case B, relabeled). (2) Customer 360 entitlement wording: rewrote both the §9 catalog row and the §34 matrix row from the ambiguous "`reports` + `sales` + `accounting`; `+installments` if entitled" phrasing (which read as an AND-gate) to explicit "section-level compound authorization, not all-or-nothing" wording, preserving the already-correct FR-RPT-111/114/115 partial-composition requirements unchanged. (3) Added new FR-RPT-116 defining Customer 360's minimum-useful-response behavior when zero sections are available: return identity-only if the user can independently view the customer master record, otherwise deny via the platform's standard IDOR-safe "not found" response; added new Scenario O. (4) Converted OQ-3 (Branch Performance) from a "recommended decision" framing to an explicit strikethrough **RESOLVED — DEFERRED** entry matching OQ-2's style, with its sole promotion prerequisite restated. (5) Reviewed OQ-4 (reports capability default) against the instruction to lock it now if evidence clearly supports one answer — concluded repository evidence cannot fully determine this (no `reports` Capability exists yet to inspect), so it correctly remains an explicit, non-blocking `/sp.plan`-level recommendation rather than being locked, with the reasoning for not locking it now stated explicitly.

Performed the requested full-text contradiction search across all ten specified terms ("disabled Installments," "module not entitled," "FR-RPT-104," "FR-RPT-251," "FR-RPT-252," etc.) and confirmed every occurrence now tells the identical story. Updated `checklists/requirements.md` with a new "Final Micro-Correction-Pass Validation" section covering all nine numbered corrections plus the contradiction audit and no-scope-expansion checks. Final state: 864 lines (was 855), 149 unique FR-RPT requirements (was 148, +1: FR-RPT-116), zero `[NEEDS CLARIFICATION]` markers, 54/54 ToC-to-header match, no duplicate requirement IDs, zero existing requirement IDs renumbered. No `plan.md`, `tasks.md`, or implementation created. Verdict: EPIC 11 SPECIFICATION READY FOR PLAN.

## Outcome

- ✅ Impact: Resolved the one genuine internal contradiction remaining in the specification (Installments servicing-continuity vs. the generic disabled-domain rule) plus the Customer 360 entitlement-wording ambiguity; locked Branch Performance's deferral status definitively; left the `reports` capability default as a deliberate, justified non-blocking planning decision rather than force-locking it without evidence. Specification is now internally consistent with zero contradictions found across a systematic full-text audit.
- 🧪 Tests: None run/added (specification-only micro-correction pass).
- 📁 Files: `specs/011-reports-analytics/spec.md` (edited, +9 lines net), `specs/011-reports-analytics/checklists/requirements.md` (extended with a new validation section).
- 🔁 Next prompts: Await explicit user approval before `/sp.plan`. The only remaining non-blocking recommendations are OQ-1 (export row-count number) and OQ-4 (reports capability default state), both to be finalized during planning.
- 🧠 Reflection: The Installments contradiction was a genuine gap between a domain-specific exception rule (FR-RPT-104) and a generic rule (FR-RPT-252) that never cross-referenced each other — a common failure mode when a specification states both a general policy and a specific carve-out in different sections without an explicit "these two rules relate as follows" statement. Adding that explicit relationship (rather than just editing each rule in isolation) is what actually closes the contradiction, not just rewording either rule alone.

## Evaluation notes (flywheel)

- Failure modes observed: The prior correction pass (0002) introduced FR-RPT-104 (servicing continuity) and left FR-RPT-252 (generic disabled-domain rule) unchanged, creating an unreconciled contradiction between the two — a reminder that adding a new domain-specific exception requires also touching the generic rule it's an exception *to*, not just the domain-specific section.
- Graders run and results (PASS/FAIL): Self-validated against the updated `checklists/requirements.md` "Final Micro-Correction-Pass Validation" section — all items PASS, including the explicit contradiction-search audit.
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): N/A
