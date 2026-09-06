---
id: 0002
title: Epic 10 Installments spec targeted corrections
stage: spec
date: 2026-08-24
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: maamirkhan1983@gmail.com
command: /sp.specify (targeted correction follow-up, not a new /sp.spec run)
labels: [spec, installments, epic-10, correction, entitlement, lifecycle, consistency]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/010-installments/spec.md
 - specs/010-installments/checklists/requirements.md
tests:
 - none (specification-only correction task; no code, migrations, or tests created)
---

## Prompt

# Epic 10 — Installments `spec.md` — Targeted Corrections Only

Review and update the existing:

`specs/010-installments/spec.md`

This is a **targeted specification-correction task only**.

Do **not** redesign Epic 10.

Do **not** generate `plan.md`.

Do **not** generate `tasks.md`.

Do **not** implement code, migrations, tests, schemas, APIs, models, services, repositories, or UI.

Do **not** broadly rewrite requirements that are already correct.

Preserve all existing accepted requirements unless they must change directly to remove one of the three inconsistencies below.

Before editing, read the current `spec.md` completely and trace every affected requirement, business rule, acceptance scenario, open question, edge case, success criterion, and cross-reference.

---

# Correction 1 — Entitlement Disabled but Existing Contracts Must Remain Serviceable

The current specification defaults to blocking collection recording when the Installments entitlement is disabled.

Change this policy.

## Final Product Decision

If a tenant's Installments entitlement, subscription, Plan capability, module toggle, or entitlement override becomes disabled **after valid installment contracts already exist**, the system MUST distinguish:

### New installment origination / new commercial activity

These remain BLOCKED:

* creating new installment quotes
* creating new installment contracts
* activating new contracts
* creating or modifying installment plans/templates
* changing installment configuration
* introducing new financed obligations
* creating new commercial restructuring
* any other operation whose purpose is to originate new installment business

### Servicing existing legally/financially valid obligations

These MUST remain available to appropriately authorized users:

* viewing existing contracts
* viewing schedules
* viewing balances and payment history
* generating statements
* recording customer collections/payments against existing active/defaulted-but-serviceable contracts
* allocating those authoritative Accounting payments to existing installment obligations
* issuing/using existing payment-receipt mechanisms
* performing payment reversal/correction where financially required and otherwise authorized
* completing an existing contract through ordinary payment
* performing early settlement/payment where necessary to discharge an existing obligation and permitted by existing contract terms
* other strictly necessary financial corrections required to keep Installments reconciled with Accounting

The entitlement system MUST NOT strand a customer mid-contract or prevent a tenant from receiving money already contractually owed merely because SaaS entitlement changed.

Existing financial obligations must remain collectible, explainable, auditable, and reconcilable.

This servicing exception does **not** authorize creating new installment obligations.

## Required edits

Update all affected requirements including, where applicable:

* FR-INST-353
* FR-INST-354
* FR-INST-355
* FR-INST-356
* FR-INST-357
* BR-INST-014
* Scenario K
* OQ-2
* relevant edge cases
* success criteria
* entitlement wording elsewhere

Resolve OQ-2 permanently.

OQ-2 must no longer remain "pending product-owner confirmation."

The final policy is:

> **Entitlement disabled = no new installment origination, but existing valid installment obligations remain financially serviceable, including collection and settlement necessary to discharge those obligations.**

Clearly distinguish servicing from origination.

Do not allow entitlement disablement to weaken normal RBAC, audit, Accounting-period, tenant-isolation, idempotency, or other financial controls.

---

# Correction 2 — One Active Installment Contract per Originating Obligation in Epic 10

The current specification contains a contradiction.

The Open Questions section resolves Epic 10 baseline to:

> one active installment contract per originating sale/invoice obligation

but FR-INST-042 / FR-INST-251 still leave a path for tenant-configured partial/split financing with multiple concurrent contracts.

Remove that contradiction.

## Final Product Decision

For Epic 10 v1:

**One originating sale/invoice obligation may have at most one non-terminal active installment contract.**

Do not support:

* multiple concurrent installment contracts against the same invoice obligation
* split financing of one invoice across multiple active installment contracts
* tenant configuration that enables multiple active contracts per invoice
* partial financing by creating multiple installment contracts

If an existing invoice already has payments recorded before installment conversion, the single installment contract may finance only the remaining eligible amount according to the existing Sales/Accounting truth.

Future support for split/multiple financing may remain architecturally possible, but it is explicitly **Out of Scope** for Epic 10.

## Required edits

Update all affected specification areas, including:

* FR-INST-042
* FR-INST-251
* OQ-3
* assumptions if applicable
* Sales integration
* edge cases
* acceptance criteria if affected
* Out of Scope / Future Extension

Remove wording such as:

> "unless tenant configuration explicitly supports..."

for multiple active contracts.

OQ-3 must be permanently resolved and no longer describe this as a configurable Epic 10 capability.

---

# Correction 3 — Lifecycle State/Transition Consistency

The current lifecycle contains two inconsistencies.

## 3A — Rejection

The defined contract-state catalogue does not contain a first-class `REJECTED` state, but FR-INST-102 describes:

`PENDING_APPROVAL → REJECTED (returns to DRAFT with a reason)`

This is contradictory.

### Final Product Decision

`REJECTED` is an **approval outcome/event**, not a persisted contract lifecycle state.

The transition is:

`PENDING_APPROVAL → DRAFT`

through an explicit **REJECT** action.

Requirements:

* rejection requires appropriate approval authority
* rejection reason is mandatory
* rejection is audited
* contract returns to editable `DRAFT`
* previous submission/rejection history remains visible
* rejection MUST NOT delete or overwrite approval history

Update FR-INST-102 and every affected lifecycle reference accordingly.

Do not add a `REJECTED` lifecycle state.

---

## 3B — Cure of Defaulted Contract

The current specification correctly states that `DEFAULTED` is non-terminal and may be cured where tenant policy permits, but the legal-transition list does not explicitly define the transition.

This conflicts with FR-INST-106, which rejects all unenumerated transitions.

### Final Product Decision

Explicitly define:

`DEFAULTED → ACTIVE`

through an authorized **CURE / RESTORE TO SERVICING** action where tenant policy permits cure.

Requirements:

* cure must be explicitly authorized
* cure must be policy-permitted
* cure must record reason/context where appropriate
* cure must be audited
* the contract's historical `DEFAULTED` event remains permanently visible
* cure must not delete delinquency/default history
* cure must not itself rewrite Accounting history
* outstanding balances remain based on authoritative Accounting records
* cure does not create a new contract
* cure does not alter original commercial terms
* if the contract is fully satisfied while defaulted, normal completion rules may apply as part of the authorized servicing workflow

Add the transition to the legal-transition list so FR-INST-106 remains internally consistent.

Update:

* lifecycle state-transition section
* FR-INST-105/106 or nearby requirements as needed
* FR-INST-222
* relevant edge case concerning voluntary collection after default
* any acceptance or audit wording affected

---

# Preserve These Accepted Decisions

The following are already approved and MUST NOT be weakened or redesigned:

## Accounting ownership

Accounting remains the sole financial source of truth.

Installments must not create:

* shadow AR
* duplicate payment truth
* duplicate journal truth
* duplicate invoices
* duplicate revenue
* competing receivable balances

Every paid/outstanding/collected amount must remain traceable to authoritative Accounting records.

## Money precision

Preserve the existing decision that Installments follows Accounting's money precision for amounts that reconcile against AR:

* `Decimal` / `NUMERIC`
* no floating-point arithmetic
* Accounting precision internally
* currency-appropriate presentation precision
* deterministic rounding
* final-installment residual reconciliation

Do not reopen the Sales `NUMERIC(15,2)` vs Accounting `NUMERIC(20,6)` decision.

## Tenant isolation

Preserve strict tenant scoping at API, Service, and Repository layers.

Cross-tenant identifiers must not leak existence/data.

## Platform Admin / Support Access

Preserve Epic 9A boundaries:

* Platform Admin entitlement authority does not grant tenant business-record access
* support access remains business-record-excluded
* installment contracts/schedules remain tenant business records

## Concurrency and idempotency

Preserve:

* no over-collection
* idempotent high-risk commands
* deterministic concurrent conflict behavior
* no duplicate settlement/payment/reversal effects

## Audit

Preserve append-only, fail-closed audit behavior for privileged actions.

## Historical integrity

Preserve:

* no destructive edits to active financial contracts
* reversals preserve originals
* template/config changes do not rewrite existing contract terms
* prior schedules remain explainable after controlled amendments

---

# Consistency Review After Editing

After applying the three corrections, perform a full internal consistency pass.

Specifically verify:

1. No requirement still says collection is blocked solely because entitlement is disabled for an already-existing contract.
2. No requirement allows multiple concurrent active installment contracts for one originating sale/invoice obligation in Epic 10.
3. No lifecycle reference treats `REJECTED` as a persisted state.
4. `DEFAULTED → ACTIVE` cure is explicitly enumerated where allowed.
5. FR-INST-106 no longer conflicts with cure behavior.
6. Scenario K matches the corrected servicing policy.
7. OQ-2 and OQ-3 are fully resolved, not pending.
8. Business rules, edge cases, success criteria, assumptions, and acceptance scenarios do not contradict the corrected decisions.
9. Existing Accounting ownership and security boundaries remain unchanged.
10. Requirement IDs and internal links remain valid and consistent.

---

# Open Questions Section

After correction:

* OQ-1 may remain documented as resolved if useful.
* OQ-2 MUST be marked fully resolved with the new servicing policy.
* OQ-3 MUST be marked fully resolved as one active contract per originating obligation.
* No `[NEEDS CLARIFICATION]` marker should remain for these issues.

If no genuinely new blocking ambiguity is discovered during this targeted correction, do not introduce new open questions.

---

# Files / Scope

Modify only the files necessary for this specification correction, primarily:

`specs/010-installments/spec.md`

If the existing requirements checklist or PHR convention requires recording this clarification/correction, update only those expected specification-artifact files.

Do not modify application source code.

Do not modify completed Epic specifications.

Do not alter Constitution.

Do not generate implementation artifacts.

---

# Final Report

After correction, provide a concise report containing:

1. Exact files modified
2. Correction 1 — entitlement servicing policy: what changed
3. Correction 2 — one-contract-per-obligation rule: what changed
4. Correction 3 — lifecycle consistency: what changed
5. Requirement IDs changed
6. Business-rule/scenario/OQ sections changed
7. Confirmation that Accounting ownership remained unchanged
8. Confirmation that tenant isolation / Epic 9A boundaries remained unchanged
9. Remaining unresolved clarification markers, if any
10. Final recommendation:

* `READY FOR /sp.plan`
* or `NOT READY`, with exact blocker

Do not proceed to `/sp.plan`.

Stop after the corrected specification and correction report are complete.

## Response snapshot

Read the complete existing `spec.md` (670 lines) before editing, traced every cross-reference, then applied 16 surgical `Edit` operations (no full rewrite) to resolve exactly the three named inconsistencies:

**Correction 1 (entitlement servicing)**: Rewrote §22.3/§22.4 (FR-INST-353–357, plus new FR-INST-358) to split "origination" (blocked: new quotes/contracts/activation/plans/config, plus rescheduling/cancellation/default/write-off since those aren't in the explicit servicing allow-list) from "servicing" (now explicitly permitted while disabled: viewing, statements, collection recording, allocation, receipts, payment reversal/correction, ordinary completion, early settlement). Updated BR-INST-014 to state obligations remain "uncollectible" → "never uncollectible," fixed a pre-existing broken anchor (`#224-behavior-when-entitlement-is-disabled` → the correct `...-after-contracts-exist` slug) discovered while editing this exact line. Updated Scenario K, SC-006, the Risks table row, and the bulk-plan-disablement edge case to match. OQ-2 rewritten as permanently resolved (no more "pending product-owner confirmation").

**Correction 2 (one contract per obligation)**: Removed the "unless the tenant's Sales integration/configuration explicitly supports partial/multiple financing" escape hatch from FR-INST-042 and FR-INST-251 — both now state flatly that at most one non-terminal contract may exist per originating obligation, with FR-INST-251 additionally clarifying that a pre-existing invoice's prior payments reduce the single contract's financed principal rather than enabling a second contract. Added a new Out-of-Scope bullet for split/multiple financing. OQ-3 rewritten as permanently resolved, explicitly stating it is "not a tenant-configurable capability in Epic 10."

**Correction 3A (rejection)**: Added an explicit note under the §11.1 states table clarifying `REJECTED` is an approval outcome/event, never a persisted state value. Rewrote FR-INST-102 to describe the actual transition (`PENDING_APPROVAL → DRAFT` via an explicit REJECT action) with mandatory reason, distinct-approver requirement, and audit requirement, and added "rejection" to FR-INST-340's audit-triggering action list.

**Correction 3B (cure)**: Added `DEFAULTED → ACTIVE` (cure) and `DEFAULTED → COMPLETED` (direct payoff while defaulted) to FR-INST-105 and FR-INST-104 respectively, so FR-INST-106's "reject any unenumerated transition" rule stays internally consistent. Expanded FR-INST-222 with the full cure rule set (policy-permitted, reason, audited, never deletes DEFAULTED history, never rewrites Accounting, no new contract, no term changes, outstanding balance from Accounting only, direct-completion path when fully paid off without requiring a separate cure step). Updated the DEFAULTED-related edge case to describe both the direct-completion and the cure paths. Updated the §11.1 states table's DEFAULTED row description accordingly.

Performed the full 10-point consistency review requested: grepped for every residual instance of blocked-collection wording, "unless tenant configuration explicitly supports" phrasing, `REJECTED`-as-state references, and confirmed FR/BR/Scenario counts (146 FRs, up by exactly 1 for the new FR-INST-358; 22 BRs unchanged in count; 12 scenarios unchanged in count; zero `[NEEDS CLARIFICATION]` markers). Confirmed no edits touched §7 Domain Ownership, §17 Accounting Integration, BR-INST-004/006/007 (Accounting ownership), or §19/§20 Multi-Tenancy/RBAC and the Epic 9A `SupportAccessGrant` boundary (§19.2, FR-INST-310/311) — all preserved verbatim. Updated the spec's header Status line and version footer (1.0.0 → 1.1.0) to reflect the correction pass, and updated `specs/010-installments/checklists/requirements.md` to record the correction and drop the now-obsolete "recommend `/sp.clarify`" guidance.

## Outcome

- ✅ Impact: All three named inconsistencies resolved with minimal, surgical edits; zero previously-accepted requirements were broadly rewritten — only the specific lines each correction required were touched.
- 🧪 Tests: none (specification-only correction task)
- 📁 Files: specs/010-installments/spec.md (edited, 16 targeted changes); specs/010-installments/checklists/requirements.md (edited, 2 targeted changes)
- 🔁 Next prompts: none required from this task — spec is ready for `/sp.plan` directly (per user instruction, this task stops after the correction and does not proceed to `/sp.plan` itself).
- 🧠 Reflection: Reading the full file first and searching for every affected cross-reference (rather than editing FR-INST-353 etc. in isolation) surfaced two things the correction request didn't explicitly name but that internal consistency required: (a) a pre-existing broken markdown anchor on the BR-INST-014 row, fixed as a byproduct of already touching that exact string; (b) the audit list (FR-INST-340) was missing "rejection" as an explicit auditable action even though 3A's requirements mandated it be audited — both were in-scope, minimal fixes directly required by the named corrections, not scope creep.

## Evaluation notes (flywheel)

- Failure modes observed: none blocking. One `Edit` call failed on the first attempt against BR-INST-014 because my recalled text was missing one closing parenthesis versus the actual file content — recovered immediately by grepping the exact line before retrying, consistent with "read/grep the exact string, don't reconstruct from memory" discipline.
- Graders run and results (PASS/FAIL): Full 10-point consistency review specified in the correction prompt — PASS on all 10 points, verified via targeted grep passes (blocked-collection wording, partial-financing escape hatches, REJECTED-as-state, DEFAULTED-transition enumeration, OQ pending-language, FR/BR/Scenario counts, anchor validity).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
